"""Page grammar: what Picsart landing pages put where, learned from the corpus.

One context row per generated-role slot (creative, thumbnail), deduplicated per
page and src. The row pairs the slot's *immediate* context (section type, size,
aspect, headline words, copy cues, sibling media) and its *wider* context (page
family, position band, neighbouring section types, other videos on the page)
with the *decisions* the original made there (image or video, length, style
family, subject, art style, motion). From those rows:

- `sequences`: the typical section order per page family;
- `priors`: backoff tables (type|family|size -> type|family -> type -> all) for
  P(video), the style family, and a video's motion and length;
- `rules`: context -> decision associations with support and lift, a pair of
  features kept only when it beats both of its single parts;
- `motifs`: recurring subject x art style x family per page family and type;
- `themes`: recurring headline terms per section type and what they carry.

`lp-corpus grammar` writes `corpus/grammar/grammar.yaml` (machine, no asset
ids: the brief reads it) and `report.md` (human, with example slots), and
`--write-doc` renders `page-grammar.md` from the yaml alone, so `doctor` can
check the doc against it. The priors advise; they never override what the
original page did.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median, quantiles

import yaml

from . import attrs, db, sectionize

GRAMMAR_DIR = Path("corpus/grammar")
GRAMMAR_YAML = GRAMMAR_DIR / "grammar.yaml"
REPORT = GRAMMAR_DIR / "report.md"
DOC = Path(".claude/skills/picsart-workflows/page-grammar.md")
MIN_SUPPORT = 10
MIN_LIFT = 1.5
MIN_CONF = 0.25
PAIR_GAIN = 1.1         # a pair must lift 10 % above its better single part
UNUSUAL_N = 30          # a prior this well supported ...
UNUSUAL_SHARE = 0.10    # ... that gives the original's kind this little share flags it
RULES_KEPT = 25         # per decision, in the yaml
MIN_CLUSTERS = 3        # a rule must hold on this many page clusters: one CMS template on 60 pages is one example
SEQUENCE_SHARE = 0.4    # a type in the canonical sequence appears on this share of the family's pages

DECISIONS = ("kind", "style", "subject", "art_style", "ui_mockup", "text_in_image",
             "motion_kind", "pace", "loop", "length")
VIDEO_ONLY = ("motion_kind", "pace", "loop", "length")
STOP = set("""a an and are as at be by can for from get how in into is it its make more new of on one or our out
over the their them this to up use using with you your yours all any best easy free fast just like now online
picsart what when where which who why will than that then there these those was were has have had not no so
own get's it's you're""".split())
MOTION_WORDS = re.compile(r"\b(videos?|animat\w*|motion|clips?|footage|reels?|film\w*|cinematic)\b")
STEP_WORDS = re.compile(r"\bstep\s*\d\b|\b(first|second|third),? ")
MODEL_WORDS = re.compile(r"\b(flux|seedance|seedream|kling|veo|sora|gemini|gpt|recraft|ideogram|midjourney|dall-?e|"
                         r"imagen|runway|luma|hailuo|minimax|wan|qwen|grok|nano banana|stable diffusion|sdxl|pika)\b")
BEFORE_AFTER = re.compile(r"\bbefore\b.{0,40}\bafter\b")
TEMPLATE_WORDS = re.compile(r"\btemplates?\b")
CTA_VERBS = ("try", "create", "generate", "start", "make", "upload", "design", "edit", "explore", "get")


# --- context rows -------------------------------------------------------------------------

def page_families(con):
    """{slug: page family}; a sub-page with none (`design--flyer`) takes the
    nearest ancestor's (`design`), else `other`."""
    fams = {r["slug"]: r["family"] for r in con.execute("SELECT slug, family FROM pages")}
    out = {}
    for slug, fam in fams.items():
        up = slug
        while not fam and "--" in up:
            up = up.rsplit("--", 1)[0]
            fam = fams.get(up)
        out[slug] = fam or "other"
    return out


def words(text):
    """Headline content words, lowercased, stopwords and short words dropped."""
    toks = re.findall(r"[a-z][a-z0-9'-]+", (text or "").lower())
    return [t for t in toks if len(t) >= 3 and t not in STOP]


def terms(text):
    """Words plus adjacent-word bigrams: the copy-theme vocabulary."""
    w = words(text)
    return sorted(set(w) | {f"{a} {b}" for a, b in zip(w, w[1:])})


def band(idx, n):
    """Where on the page a section sits: top (first), upper, middle, lower."""
    if idx == 0:
        return "top"
    rel = idx / max(1, n - 1)
    return "upper" if rel < 0.34 else "middle" if rel < 0.67 else "lower"


def cues(text, buttons):
    """Boolean copy cues of a section's text, as feature names."""
    t = (text or "").lower()
    out = []
    for name, rx in (("motion", MOTION_WORDS), ("steps", STEP_WORDS), ("model", MODEL_WORDS),
                     ("before-after", BEFORE_AFTER), ("template", TEMPLATE_WORDS)):
        if rx.search(t):
            out.append(name)
    for b in buttons:
        first = ((b or "").lower().split() or [""])[0]
        if first in CTA_VERBS:
            out.append(f"cta-{first}")
            break
    return out


def length_band(s):
    if s is None:
        return None
    return "<=5s" if s <= 5.5 else "6-10s" if s <= 10.5 else "11-20s" if s <= 20.5 else ">20s"


def page_rows(slug, family, sections, dedupe=True):
    """The context rows of one page. `sections` is skeleton.load_page's list of
    (section, texts, media); returns (rows, section_rows). The corpus counts a
    src once per page (`dedupe`); the skeleton wants a row for every slot."""
    n = len(sections)
    seen = set()
    rows, srows = [], []
    video_sections = [any(m["kind"] == "video" and m["role"] in db.GENERATED_ROLES for m in media)
                      for _, _, media in sections]
    page_videos = sum(1 for _, _, media in sections for m in media
                      if m["kind"] == "video" and m["role"] in db.GENERATED_ROLES)
    ordinal = 0
    for i, (s, texts, media) in enumerate(sections):
        text = " ".join(t["text"] for t in texts)
        buttons = [t["text"] for t in texts if t["tag"] in ("button", "a")]
        c = cues(text, buttons)
        gen = [m for m in media if m["role"] in db.GENERATED_ROLES]
        ctx = {"page": slug, "sid": s["sid"], "type": s["type"], "pfam": family, "pos": band(i, n),
               "prev": sections[i - 1][0]["type"] if i else "start",
               "next": sections[i + 1][0]["type"] if i + 1 < n else "end",
               "prev_video": bool(i and video_sections[i - 1]), "cues": c, "words": words(s["headline"]),
               "headline": s["headline"] or ""}
        srows.append({**ctx, "media": len(gen), "video": sum(1 for m in gen if m["kind"] == "video")})
        for m in gen:
            if dedupe and m["src"] in seen:
                continue
            seen.add(m["src"])
            at = json.loads(m["attrs"]) if m["attrs"] else {}
            video = m["kind"] == "video"
            if video:
                ordinal += 1
            dur = m["duration"] or at.get("duration")
            rows.append({**ctx, "slot": m["slot_id"], "asset": attrs.asset_id(m["src"]),
                         "size": sectionize.size_class(m["width"], m["height"]) if m["width"] and m["height"] else None,
                         "aspect": sectionize.aspect_class(m["width"], m["height"]) if m["width"] and m["height"] else None,
                         "media_n": len(gen),
                         "sib_video": any(o["kind"] == "video" for o in gen if o is not m),
                         "page_other_video": page_videos - (1 if video else 0) > 0,
                         "video_ordinal": ordinal if video else None,
                         "kind": m["kind"], "style": m["style"], "duration": dur,
                         "length": length_band(dur) if video else None,
                         **{k: at.get(k) for k in ("subject", "art_style", "ui_mockup", "text_in_image",
                                                   "motion_kind", "pace", "loop")}})
            if not video:
                for k in VIDEO_ONLY:
                    rows[-1][k] = None
    return rows, srows


def contexts(con):
    """(rows, section_rows) over every indexed page, in slug order."""
    from .skeleton import load_page
    fams = page_families(con)
    rows, srows = [], []
    for slug in sorted(fams):
        page, sections = load_page(con, slug)
        r, s = page_rows(slug, fams[slug], sections)
        rows += r
        srows += s
    return rows, srows


def source_hash(con):
    """A fingerprint of everything the grammar reads: a changed section, slot,
    style or attribute makes `doctor` call the grammar stale."""
    h = hashlib.sha1()
    for r in con.execute("""SELECT p.slug, p.family, s.sid, s.idx, s.type, s.headline, m.slot_id, m.kind, m.role,
                                   m.src, m.style, m.attrs, m.duration, m.width, m.height
                            FROM media m JOIN sections s ON s.id = m.section_id JOIN pages p ON p.id = s.page_id
                            ORDER BY p.slug, s.idx, m.id"""):
        h.update(repr(tuple(r)).encode())
    return h.hexdigest()[:16]


# --- features -----------------------------------------------------------------------------

STRUCTURAL = ("type", "pfam", "size", "aspect", "pos", "prev", "next")


def features(row):
    """The antecedent vocabulary of one row: `key=value` for the structural
    context, `cue=<name>`, `word=<w>`, and the neighbouring-video flags."""
    f = [f"{k}={row[k]}" for k in STRUCTURAL if row.get(k)]
    f += [f"cue={c}" for c in row.get("cues", ())]
    if row.get("sib_video"):
        f.append("sib=video")
    if row.get("prev_video"):
        f.append("prev=video-section")
    f.append("page-video=" + ("yes" if row.get("page_other_video") else "no"))
    return f, [f"word={w}" for w in sorted(set(row.get("words", ())))]


def antecedents(row):
    """Single features, plus pairs that involve the section type or the page
    family (the two axes every rule is read along)."""
    single, wordf = features(row)
    out = single + wordf
    anchors = [x for x in single if x.startswith(("type=", "pfam="))]
    for a in anchors:
        for b in single + wordf:
            if b != a and not (b.startswith(("type=", "pfam=")) and b < a):
                out.append(" & ".join(sorted((a, b))))
    return out


def cluster(page):
    """A page's template cluster: sibling pages (`design--flyer`, `design--menu`)
    share one CMS template, so they are one piece of evidence, not sixty."""
    return (page or "").split("--")[0]


def mine(rows, decisions=DECISIONS, min_support=MIN_SUPPORT, min_lift=MIN_LIFT, min_conf=MIN_CONF,
         min_clusters=MIN_CLUSTERS):
    """{decision: [rule]}: rule = {when, then, n, of, clusters, conf, lift,
    base}, ranked by lift x sqrt(n). Population per decision is the rows where
    it is known; a rule seen on fewer than min_clusters page clusters is
    dropped (its n counts one template's copies)."""
    out = {}
    per_row = [antecedents(r) for r in rows]
    for dec in decisions:
        pop = [(r[dec], a) for r, a in zip(rows, per_row) if r.get(dec) is not None]
        if not pop:
            out[dec] = []
            continue
        base = Counter(str(v) for v, _ in pop)
        total = len(pop)
        n_a, n_av = Counter(), Counter()
        for v, ants in pop:
            for a in ants:
                n_a[a] += 1
                n_av[(a, str(v))] += 1
        found = {}
        for (a, v), k in n_av.items():
            na = n_a[a]
            if k < min_support or na < min_support:
                continue
            conf = k / na
            lift = conf / (base[v] / total)
            if lift >= min_lift and conf >= min_conf:
                found[(a, v)] = {"when": a, "then": v, "n": k, "of": na, "conf": round(conf, 2),
                                 "lift": round(lift, 2), "base": round(base[v] / total, 3)}
        spread = defaultdict(set)
        for r, ants in zip(rows, per_row):
            if r.get(dec) is not None:
                for a in ants:
                    if (a, str(r[dec])) in found:
                        spread[(a, str(r[dec]))].add(cluster(r.get("page")))
        kept = []
        for (a, v), r in found.items():
            r["clusters"] = len(spread[(a, v)])
            if r["clusters"] < min_clusters:
                continue
            if " & " in a:
                parts = a.split(" & ")
                best = max((found.get((p, v), {}).get("lift") or _lift(n_a, n_av, base, total, p, v)) for p in parts)
                if r["lift"] < PAIR_GAIN * best:
                    continue
            r["score"] = round(r["lift"] * math.sqrt(r["n"]), 2)
            kept.append(r)
        # rules with the same counts almost always name one slot set three ways
        # (5:4 slots = link-grids = after a faq on compare pages): keep the simplest
        kept.sort(key=lambda r: (r["then"], r["n"], r["of"], r["when"].count(" & "), r["when"]))
        seen, unique = set(), []
        for r in kept:
            if (r["then"], r["n"], r["of"]) not in seen:
                seen.add((r["then"], r["n"], r["of"]))
                unique.append(r)
        unique.sort(key=lambda r: (-r["score"], r["when"], r["then"]))
        out[dec] = unique
    return out


def _lift(n_a, n_av, base, total, a, v):
    na = n_a.get(a)
    if not na:
        return 1.0
    return (n_av.get((a, v), 0) / na) / (base[v] / total)


# --- backoff priors ------------------------------------------------------------------------

LEVELS = (("type", "pfam", "size"), ("type", "pfam"), ("type",), ())


def key_of(row, level):
    return "|".join(str(row.get(k)) for k in level) or "*"


def priors(rows, srows, min_support=MIN_SUPPORT):
    """Backoff tables keyed `type|pfam|size`, `type|pfam`, `type`, `*`: kind
    (video share), style (top three), motion (videos: modal kind, pace, loop
    share, length median and IQR), and section media (sections carrying a
    generated slot, and a video)."""
    kind, style, motion, smedia = {}, {}, {}, {}
    for level in LEVELS:
        groups = defaultdict(list)
        for r in rows:
            groups[key_of(r, level)].append(r)
        for key, rs in groups.items():
            if len(rs) >= min_support:
                kind[key] = {"n": len(rs), "video": round(sum(r["kind"] == "video" for r in rs) / len(rs), 3)}
            styled = [r["style"] for r in rs if r.get("style")]
            if len(styled) >= min_support:
                style[key] = {"n": len(styled), "top": [[s, round(c / len(styled), 2)]
                                                        for s, c in Counter(styled).most_common(3)]}
            vids = [r for r in rs if r["kind"] == "video"]
            if len(vids) >= min(5, min_support) and level != LEVELS[0]:
                motion[key] = motion_summary(vids)
        if len(level) <= 2:
            sg = defaultdict(list)
            for s in srows:
                sg[key_of(s, level)].append(s)
            for key, ss in sg.items():
                if len(ss) >= min_support:
                    smedia[key] = {"n": len(ss), "media": round(sum(s["media"] > 0 for s in ss) / len(ss), 3),
                                   "video": round(sum(s["video"] > 0 for s in ss) / len(ss), 3)}
    return {"kind": dict(sorted(kind.items())), "style": dict(sorted(style.items())),
            "motion": dict(sorted(motion.items())), "section_media": dict(sorted(smedia.items()))}


def motion_summary(vids, min_n=5):
    def mode(key):
        c = Counter(r[key] for r in vids if r.get(key) is not None)
        return c.most_common(1)[0][0] if sum(c.values()) >= min_n else None
    durs = sorted(r["duration"] for r in vids if r.get("duration"))
    out = {"n": len(vids), "motion_kind": mode("motion_kind"), "pace": mode("pace"),
           "loop": round(sum(1 for r in vids if r.get("loop")) / len(vids), 2)}
    if durs:
        out["median_s"] = round(median(durs), 1)
        if len(durs) >= 4:
            q = quantiles(durs, n=4)
            out["iqr_s"] = [round(q[0], 1), round(q[2], 1)]
    return out


def lookup(table, ctx, levels=LEVELS):
    """(key, entry) at the most specific level the table has, else (None, None)."""
    for level in levels:
        key = key_of(ctx, level)
        if key in table:
            return key, table[key]
    return None, None


def prior(g, ctx):
    """What the grammar expects of one slot context {type, pfam, size, kind}:
    {kind: (key, entry), style: (key, entry), motion: (key, entry) for a video,
    unusual: text or None}. The plain backoff prior only: blending in the
    context rules made it worse on held-out pages (`evaluate`), so the rules
    describe the corpus in page-grammar.md and do not score a slot."""
    p = g["priors"]
    out = {"kind": lookup(p["kind"], ctx), "style": lookup(p["style"], ctx), "motion": (None, None), "unusual": None}
    video = ctx.get("kind") == "video"
    if video:
        out["motion"] = lookup(p["motion"], ctx, LEVELS[1:])
    key, e = out["kind"]
    if e and e["n"] >= UNUSUAL_N:
        share = e["video"] if video else 1 - e["video"]
        if share <= UNUSUAL_SHARE:
            out["unusual"] = (f"{'a video' if video else 'an image'} where {round(share * 100)} % of "
                              f"{phrase_key(key)} slots are (n={e['n']}): keep it, and say why in the report")
    return out


def prior_line(g, ctx):
    """The skeleton's `> prior:` value for one slot. Segments: `video N %`,
    `style a N %, b N %`, and for a video `motion k, pace p, loop N %` and
    `length N s (IQR a-b)`; then the basis, then `# unusual:` when it applies."""
    pr = prior(g, ctx)
    key, e = pr["kind"]
    if not e:
        return None
    segs = [f"video {round(e['video'] * 100)} %"]
    skey, se = pr["style"]
    if se:
        segs.append("style " + ", ".join(f"{s} {round(sh * 100)} %" for s, sh in se["top"]))
    mkey, me = pr["motion"]
    if me:
        bits = [x for x in (me.get("motion_kind"), me.get("pace") and f"pace {me['pace']}") if x]
        segs.append("motion " + ", ".join(bits + [f"loop {round(me['loop'] * 100)} %"]))
        if me.get("median_s"):
            iqr = f" (IQR {me['iqr_s'][0]}-{me['iqr_s'][1]})" if me.get("iqr_s") else ""
            segs.append(f"length {me['median_s']} s{iqr}")
    line = " · ".join(segs) + f" · basis {phrase_key(key)} n={e['n']}"
    if pr["unusual"]:
        line += f"  # unusual: {pr['unusual']}"
    return line


def section_prior_line(g, ctx):
    """For a section with no generated slot: how often such sections carry
    one, when that is the norm (the manager may still leave it empty)."""
    key, e = lookup(g["priors"]["section_media"], ctx, LEVELS[1:])
    if not e or e["media"] < 0.6:
        return None
    return (f"no generated media here; {round(e['media'] * 100)} % of {phrase_key(key)} sections carry one "
            f"(a video in {round(e['video'] * 100)} %) · n={e['n']}")


def phrase_key(key):
    if not key or key == "*":
        return "all"
    return "×".join(key.split("|"))


# --- sequences, motifs, themes -------------------------------------------------------------

def sequences(srows):
    """Per page family: pages, the canonical order (types on >= 40 % of its
    pages, by the median position of every occurrence, with the median count),
    and the commonest transitions."""
    by_page = defaultdict(list)
    fam_of = {}
    for s in srows:
        by_page[s["page"]].append(s["type"])
        fam_of[s["page"]] = s["pfam"]
    by_fam = defaultdict(list)
    for page, types in by_page.items():
        by_fam[fam_of[page]].append(types)
    out = {}
    for fam, pages in sorted(by_fam.items()):
        stats = {}
        for t in {t for types in pages for t in types}:
            having = [types for types in pages if t in types]
            stats[t] = {"share": round(len(having) / len(pages), 2),
                        "count": median(types.count(t) for types in having),
                        "pos": round(median(i / max(1, len(types) - 1) for types in having
                                            for i, x in enumerate(types) if x == t), 2)}
        canon = sorted((t for t, s in stats.items() if s["share"] >= SEQUENCE_SHARE), key=lambda t: (stats[t]["pos"], t))
        trans = Counter()
        for types in pages:
            collapsed = [t for i, t in enumerate(types) if not i or t != types[i - 1]]
            trans.update(set(zip(collapsed, collapsed[1:])))
        out[fam] = {"pages": len(pages), "median_sections": median(len(p) for p in pages),
                    "canonical": [[t, int(stats[t]["count"]), stats[t]["share"]] for t in canon],
                    "transitions": [[a, b, round(c / len(pages), 2)] for (a, b), c in
                                    sorted(trans.items(), key=lambda kv: (-kv[1], kv[0]))[:8]],
                    "types": {t: stats[t] for t in sorted(stats)}}
    return out


def motifs(rows, min_support=MIN_SUPPORT):
    """Per `pfam|type`: the top three subject / art style / family combinations,
    with share and lift over their corpus-wide share."""
    full = [r for r in rows if r.get("subject") and r.get("art_style") and r.get("style")]
    if not full:
        return {}
    combo = lambda r: f"{r['subject']} / {r['art_style']} / {r['style']}"  # noqa: E731
    base = Counter(combo(r) for r in full)
    groups = defaultdict(list)
    for r in full:
        groups[f"{r['pfam']}|{r['type']}"].append(r)
    out = {}
    for key, rs in sorted(groups.items()):
        if len(rs) < min_support:
            continue
        c = Counter(combo(r) for r in rs)
        out[key] = {"n": len(rs), "top": [[m, round(k / len(rs), 2), round((k / len(rs)) / (base[m] / len(full)), 1)]
                                          for m, k in c.most_common(3)]}
    return out


def themes(rows, srows, min_support=MIN_SUPPORT, per_type=10):
    """Per section type: headline terms in >= min_support distinct headlines, each with
    the share of those sections carrying a video (vs the type's), the top
    family of their slots, and the CTA verbs the type uses."""
    slots_by_section = defaultdict(list)
    for r in rows:
        slots_by_section[(r["page"], r["sid"])].append(r)
    by_type = defaultdict(list)
    for s in srows:
        by_type[s["type"]].append(s)
    out = {}
    for t, ss in sorted(by_type.items()):
        withm = [s for s in ss if s["media"]]
        if len(withm) < min_support:
            continue
        base_video = sum(1 for s in withm if s["video"]) / len(withm)
        # distinct headlines, so one boilerplate headline repeated on 100 pages counts once
        tc = Counter(term for h in {s["headline"] for s in withm} for term in terms(h))
        entries = []
        for term, n in tc.most_common():
            if n < min_support:
                break
            hit = [s for s in withm if term in terms(s["headline"])]
            vid = sum(1 for s in hit if s["video"]) / len(hit)
            styles_ = Counter(r["style"] for s in hit for r in slots_by_section[(s["page"], s["sid"])] if r.get("style"))
            top = styles_.most_common(1)[0][0] if styles_ else None
            entries.append([term, n, round(vid, 2), top])
            if len(entries) == per_type:
                break
        ctas = Counter(c for s in ss for c in s["cues"] if c.startswith("cta-"))
        out[t] = {"sections": len(withm), "video": round(base_video, 2), "terms": entries,
                  "cta": [[c[4:], k] for c, k in ctas.most_common(4)]}
    return out


# --- build, save, render -------------------------------------------------------------------

def build(con, min_support=MIN_SUPPORT):
    rows, srows = contexts(con)
    rules = mine(rows, min_support=min_support)
    g = {"source": {"hash": source_hash(con), "pages": len({s["page"] for s in srows}), "slots": len(rows),
                    "videos": sum(1 for r in rows if r["kind"] == "video"), "min_support": min_support},
         "sequences": sequences(srows),
         "priors": priors(rows, srows, min_support),
         "rules": {d: [{k: r[k] for k in ("when", "then", "n", "of", "clusters", "conf", "lift")} for r in rs[:RULES_KEPT]]
                   for d, rs in rules.items()},
         "motifs": motifs(rows, min_support),
         "themes": themes(rows, srows, min_support),
         "durations": durations(rows),
         "evaluation": evaluate(rows, srows, min_support)}
    return g, rows, rules


def evaluate(rows, srows, min_support=MIN_SUPPORT, fold=5):
    """Hold out every fifth page cluster, build the priors on the rest, and
    score them on the held-out slots against the naive baseline: P(video)
    Brier (lower is better), the style family top-1 / top-3, and a clip's
    length error against the flat 5 s default. The numbers the doc's advice
    rests on."""
    held = lambda r: int(hashlib.md5(cluster(r["page"]).encode()).hexdigest(), 16) % fold == 0  # noqa: E731
    tr, te = [r for r in rows if not held(r)], [r for r in rows if held(r)]
    if not tr or not te:
        return None
    pri = priors(tr, [s for s in srows if not held(s)], min_support)
    base = sum(r["kind"] == "video" for r in tr) / len(tr)

    def pv(r):
        e = lookup(pri["kind"], r)[1]
        return e["video"] if e else base

    brier = lambda f: round(sum((f(r) - (r["kind"] == "video")) ** 2 for r in te) / len(te), 4)  # noqa: E731
    tagged = [r for r in te if r.get("style")]
    mode = Counter(r["style"] for r in tr if r.get("style")).most_common(1)[0][0]
    tops = [[s for s, _ in (lookup(pri["style"], r)[1] or {"top": [[mode, 1]]})["top"]] for r in tagged]
    clips = [r for r in te if r["kind"] == "video" and r.get("duration")]
    mlen = lambda r: (lookup(pri["motion"], r, LEVELS[1:])[1] or {}).get("median_s", 5)  # noqa: E731
    mae = lambda f: round(sum(abs(f(r) - r["duration"]) for r in clips) / len(clips), 1) if clips else None  # noqa: E731
    return {"held_out_slots": len(te), "held_out_videos": sum(r["kind"] == "video" for r in te),
            "video_brier": {"prior": brier(pv), "baseline": brier(lambda r: base)},
            "style_top1": {"prior": round(sum(t[0] == r["style"] for t, r in zip(tops, tagged)) / len(tagged), 2),
                           "baseline": round(sum(mode == r["style"] for r in tagged) / len(tagged), 2)},
            "style_top3": round(sum(r["style"] in t for t, r in zip(tops, tagged)) / len(tagged), 2),
            "length_mae_s": {"prior": mae(mlen), "flat_5s": mae(lambda r: 5)}}


def durations(rows, min_n=5):
    """type|motion_kind|pfam -> the length distribution of those clips."""
    groups = defaultdict(list)
    for r in rows:
        if r["kind"] == "video" and r.get("duration"):
            groups[f"{r['type']}|{r.get('motion_kind') or 'unlabelled'}|{r['pfam']}"].append(r)
    return {k: motion_summary(v) for k, v in sorted(groups.items()) if len(v) >= min_n}


def save(g, path=GRAMMAR_YAML):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# generated by `lp-corpus grammar`; do not hand-edit (re-run after sectionize / labels)\n"
                    + yaml.safe_dump(g, sort_keys=False, allow_unicode=True, width=1000))
    return path


def load(path=GRAMMAR_YAML):
    path = Path(path)
    return yaml.safe_load(path.read_text()) if path.exists() else None


def feature_phrase(a, drop=()):
    """`type=hero & pfam=ai-tool` -> `hero sections · ai-tool pages`; parts in
    `drop` are left out (the type a doc block is already about)."""
    out = []
    for part in a.split(" & "):
        if part in drop:
            continue
        k, _, v = part.partition("=")
        art = "an" if v[:1] in "aeiou" else "a"
        if k == "cue" and v.startswith("cta-"):
            out.append(f"a “{v[4:]}” CTA")
        elif part == "prev=video-section":
            out.append("after a video section")
        else:
            out.append({"type": f"{v} sections", "pfam": f"{v} pages", "size": f"{v}-size slots",
                        "aspect": f"{v} slots", "pos": f"the {v} of the page", "prev": f"after {art} {v}",
                        "next": f"before {art} {v}", "cue": f"copy mentions {v}", "word": f"headline has “{v}”",
                        "sib": "beside another video", "page-video": "other video on the page" if v == "yes"
                        else "no other video on the page"}.get(k, part))
    return " · ".join(out)


def _num(x):
    return int(x) if float(x).is_integer() else x


DECISION_NAMES = {"kind": "the slot is a", "style": "the family is", "subject": "the subject is",
                  "art_style": "the art style is", "ui_mockup": "the UI mockup is", "text_in_image": "in-image text is",
                  "motion_kind": "the clip is", "pace": "the pace is", "loop": "the clip loops:", "length": "the clip runs"}


def rule_sentence(dec, r):
    return (f"{feature_phrase(r['when'])}: {DECISION_NAMES[dec]} **{r['then']}** in {round(r['conf'] * 100)} % "
            f"(lift {r['lift']}, n={r['n']}/{r['of']}, {r['clusters']} page clusters)")


def evaluation_lines(ev):
    """What the priors are worth on held-out page clusters, in plain words."""
    if not ev:
        return []
    return [f"How much to trust it (every fifth page cluster held out, {ev['held_out_slots']} slots): "
            f"a clip's length from the prior is off by {ev['length_mae_s']['prior']} s against "
            f"{ev['length_mae_s']['flat_5s']} s for a flat 5 s; the video share scores Brier "
            f"{ev['video_brier']['prior']} against {ev['video_brier']['baseline']} for the base rate; the "
            f"family prior's first pick is right {round(ev['style_top1']['prior'] * 100)} % of the time against "
            f"{round(ev['style_top1']['baseline'] * 100)} % for always the commonest family, and the right family "
            f"is in its top three {round(ev['style_top3'] * 100)} % of the time. So: use the length, read the "
            "family shares as a shortlist rather than a ranking, and read the rules below as a description "
            "of the corpus, not a forecast for one slot.", ""]


def render_doc(g, top=30):
    """page-grammar.md from grammar.yaml alone (doctor compares the two)."""
    src = g["source"]
    p = g["priors"]
    L = ["# Page grammar", "",
         "Generated by `uv run lp-corpus grammar --write-doc` from `corpus/grammar/grammar.yaml`; do not hand-edit.",
         f"Source: {src['pages']} pages, {src['slots']} generated-role slots ({src['videos']} videos), "
         f"rules need n >= {src['min_support']}. Lift = how many times likelier than across the corpus.", "",
         "How to use it: the skeleton's `> prior:` line per slot is this table applied to that slot. It advises. "
         "The original page's image-or-video and length stand. A `# unusual:` note asks for a one-line "
         "keep-or-change decision in the report, and a video's unknown length is taken from the prior.", "",
         *evaluation_lines(g.get("evaluation")),
         "## Page sequences", ""]
    for fam, s in g["sequences"].items():
        canon = " → ".join(f"{t}" + (f" ×{c}" if c > 1 else "") for t, c, _ in s["canonical"])
        L.append(f"- **{fam}** ({s['pages']} pages, median {_num(s['median_sections'])} sections): {canon or '(no common order)'}")
    L += ["", "## Per section type", ""]
    for t in db.SECTION_TYPES:
        e = p["kind"].get(t)
        if not e:
            continue
        L.append(f"### {t}")
        L.append("")
        L.append(f"- **Video share:** {round(e['video'] * 100)} % of {e['n']} slots.")
        fam_keys = sorted(((k, v) for k, v in p["kind"].items() if k.count("|") == 1 and k.startswith(t + "|")),
                          key=lambda kv: (-kv[1]["video"], kv[0]))
        vids = [f"{k.split('|')[1]} {round(v['video'] * 100)} %" for k, v in fam_keys if v["video"] >= 0.15]
        imgs = [k.split("|")[1] for k, v in fam_keys if v["video"] < 0.05]
        whens = [r for r in g["rules"].get("kind", []) if r["then"] == "video" and f"type={t}" in r["when"].split(" & ")]
        if vids or whens:
            L.append("- **When video:** " + "; ".join(
                ([f"on {', '.join(vids)} pages"] if vids else [])
                + [feature_phrase(r["when"], drop=(f"type={t}",)) + f" {round(r['conf'] * 100)} %"
                   for r in whens[:3]]) + ".")
        if imgs:
            L.append(f"- **When image:** almost always on {', '.join(imgs)} pages (video < 5 %).")
        me = p["motion"].get(t)
        if me and me.get("median_s"):
            iqr = f", IQR {me['iqr_s'][0]}-{me['iqr_s'][1]} s" if me.get("iqr_s") else ""
            L.append(f"- **Length:** median {me['median_s']} s{iqr}; {me.get('motion_kind') or 'motion unlabelled'}"
                     f"{', pace ' + me['pace'] if me.get('pace') else ''}, {round(me['loop'] * 100)} % loop "
                     f"({me['n']} clips).")
        se = p["style"].get(t)
        if se:
            L.append("- **Families:** " + ", ".join(f"{s} {round(sh * 100)} %" for s, sh in se["top"]) + ".")
        mk = sorted(((k, v) for k, v in g["motifs"].items() if k.endswith("|" + t)), key=lambda kv: -kv[1]["n"])[:3]
        if mk:
            L.append("- **Motifs:** " + "; ".join(f"{k.split('|')[0]}: {v['top'][0][0]} ({round(v['top'][0][1] * 100)} %, "
                                                   f"×{v['top'][0][2]})" for k, v in mk) + ".")
        th = g["themes"].get(t)
        if th and th["terms"]:
            L.append("- **Copy cues:** " + ", ".join(
                f"“{term}” ({n}; video {round(v * 100)} %{', ' + st if st else ''})" for term, n, v, st in th["terms"][:6])
                     + (f"; CTAs {', '.join(c for c, _ in th['cta'])}" if th["cta"] else "") + ".")
        L.append("")
    L += ["## Context → decision rules", "",
          f"The {top} strongest across every decision, ranked by lift × √n (a pair is kept only when it lifts "
          f"{round((PAIR_GAIN - 1) * 100)} % above both of its parts).", ""]
    ranked = sorted(((d, r) for d, rs in g["rules"].items() for r in rs),
                    key=lambda dr: (-dr[1]["lift"] * math.sqrt(dr[1]["n"]), dr[0], dr[1]["when"]))
    for d, r in ranked[:top]:
        L.append(f"- {rule_sentence(d, r)}")
    return "\n".join(L).rstrip() + "\n"


def render_report(g, rows, rules, per=15):
    """report.md: everything in the yaml, plus example slots for each rule."""
    index = defaultdict(list)
    for r in rows:
        ants = set(antecedents(r))
        for dec in DECISIONS:
            if r.get(dec) is not None:
                index[(dec, str(r[dec]))].append((ants, f"{r['page']} {r['slot']} ({r['asset']})"))

    def examples(dec, rule, k=3):
        return [e for ants, e in index[(dec, rule["then"])] if rule["when"] in ants][:k]

    src = g["source"]
    L = ["# Page grammar report", "", f"Source hash {src['hash']}: {src['pages']} pages, {src['slots']} slots, "
         f"{src['videos']} videos, min support {src['min_support']}.", "",
         "Slot classes here key on the full section type (`feature-callout`), as `brief.slot_class` does; "
         "style-families.md's table shortens some (`callout-1:1`).", "", "## 1. Section sequences", ""]
    for fam, s in g["sequences"].items():
        L.append(f"### {fam} ({s['pages']} pages, median {_num(s['median_sections'])} sections)")
        L.append("")
        L.append("| type | on pages | median count | median position |")
        L.append("|---|---|---|---|")
        for t, st in sorted(s["types"].items(), key=lambda kv: (kv[1]["pos"], kv[0])):
            L.append(f"| {t} | {round(st['share'] * 100)} % | {st['count']} | {st['pos']} |")
        L.append("")
        L.append("Transitions: " + ", ".join(f"{a} → {b} ({round(sh * 100)} %)" for a, b, sh in s["transitions"]))
        L.append("")
    L += ["## 2. Media kind by context", "", "| key | slots | video |", "|---|---|---|"]
    for k, e in g["priors"]["kind"].items():
        if k.count("|") <= 1:
            L.append(f"| {phrase_key(k)} | {e['n']} | {round(e['video'] * 100)} % |")
    L += ["", "## 3. Video length", "", "| type × motion × page family | clips | median s | IQR | loop | pace |",
          "|---|---|---|---|---|---|"]
    for k, e in g["durations"].items():
        iqr = f"{e['iqr_s'][0]}-{e['iqr_s'][1]}" if e.get("iqr_s") else ""
        L.append(f"| {phrase_key(k)} | {e['n']} | {e.get('median_s', '')} | {iqr} | {round(e['loop'] * 100)} % | "
                 f"{e.get('pace') or ''} |")
    L += ["", "## 4. Visual motifs", "", "| page family × type | slots | top subject / art style / family (share, lift) |",
          "|---|---|---|"]
    for k, e in g["motifs"].items():
        L.append(f"| {phrase_key(k)} | {e['n']} | " + "; ".join(f"{m} ({round(s * 100)} %, ×{l})" for m, s, l in e["top"]) + " |")
    L += ["", "## 5. Copy themes", ""]
    for t, e in g["themes"].items():
        L.append(f"- **{t}** ({e['sections']} sections with media, video {round(e['video'] * 100)} %): "
                 + ", ".join(f"“{term}” {n} (video {round(v * 100)} %, {st})" for term, n, v, st in e["terms"])
                 + (f". CTAs: {', '.join(f'{c} {n}' for c, n in e['cta'])}" if e["cta"] else ""))
    L += ["", "## 6. Context → decision associations", ""]
    for dec, rs in rules.items():
        if not rs:
            continue
        L.append(f"### {dec}")
        L.append("")
        for r in rs[:per]:
            ex = examples(dec, r)
            L.append(f"- {rule_sentence(dec, r)}" + (f" e.g. {'; '.join(ex)}" if ex else ""))
        L.append("")
    return "\n".join(L).rstrip() + "\n"
