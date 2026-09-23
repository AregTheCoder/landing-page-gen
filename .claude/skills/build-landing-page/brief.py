"""Assemble one section's brief.md deterministically, so the manager stops
reading style-families.md (44 KB), slots.json (55 KB), the example excerpts and
the references during the wave.

    uv run python .claude/skills/build-landing-page/brief.py <run> <Sxx> \
        [--pool N --seed <run>] [--widen N]

The manager still makes the judgements: it writes the four `>` lines
(annotation, style, text, device) into skeleton.md first (SKILL sections 1.4-1.7).
This tool reads them and fills brief-template.md: the section block (verbatim,
minus src/local/alt), the family's style-families.md block and Signature
checklist, the recipe row from flow/board.py RECIPES (never a hand-typed table),
lp-flow templates, similar's examples (with the page's own asset ids excluded via
blindcheck.identifiers), the references genre, shared-context.md, budget and the
output contract. It runs blindcheck and refuses to write on a hit.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
STYLE_FAMILIES = REPO / ".claude" / "skills" / "picsart-workflows" / "style-families.md"
REFERENCES_DIR = REPO / "corpus" / "references"
GRAMMAR_YAML = REPO / "corpus" / "grammar" / "grammar.yaml"
PRIOR_LENGTH_RE = re.compile(r"length (\d+(?:\.\d+)?) s")
PRIOR_MOTION_RE = re.compile(r"motion ([^·]+?) ·")
PRIOR_BASIS_RE = re.compile(r"basis (\S+) n=(\d+)")

sys.path.insert(0, str(HERE))
import blindcheck  # noqa: E402
from landing_page_gen.flow import board  # noqa: E402
from landing_page_gen.compose import cli as compose_cli, plan  # noqa: E402
from landing_page_gen.compose.families import FAMILIES, LABELS  # noqa: E402
from landing_page_gen.corpus import grammar  # noqa: E402
from landing_page_gen.corpus.db import GENERATED_ROLES  # noqa: E402


def _preset(family, device, size=None, section=None):
    """The compose preset a device selects for this family, else the one the
    section type selects, else the variant whose aspect the slot size has when
    the default's does not, or None."""
    preset = device if device in (FAMILIES.get(family, {}).get("variants") or {}) else None
    return compose_cli.preset_for_size(family, size, preset, section)


def composition_section(family, device, size=None, sizes=None, section=None):
    """For a composable family, the panels the worker generates (with the ratio
    and fit) and the keep-clear region each carries — so it stops guessing.
    `sizes` is [(slot id, size)] for the section: slots whose sizes select
    different presets (a 1:1 and a 21:10 before-after slot) each get their own
    table, so the brief never contradicts the per-slot composition plans."""
    if not board.composable(family):
        return ""
    groups = {}  # preset -> the slot ids it serves, in section order
    for sid, sz in (sizes or [(None, size)]):
        groups.setdefault(_preset(family, device, sz, section), []).append(sid)
    rows = ["## Panels and keep-clear", "",
            "Generate one panel per row at the ratio given; keep the subject out of any keep-clear "
            "region (an overlay sits there). The chrome is composited by lp-compose, never by a model.", ""]
    for i, (preset, sids) in enumerate(groups.items()):
        if len(groups) > 1:
            rows += ([""] if i else []) + [f"Slots {', '.join(sids)} ({preset or 'default'} layout):", ""]
        rows += ["| panel | generate at | fit | keep clear (fractions of the panel) |", "|---|---|---|---|"]
        for p in plan.contract(family, preset):
            kc = "; ".join(f"{r['item']} {r['frac']}" for r in p["keep_clear"]) or "—"
            rows.append(f"| {p['panel']} | {p['ratio']} | {p['fit']} | {kc} |")
    return "\n".join(rows) + "\n"

SLOT_RE = re.compile(r"^```slot\n(.*?)\n```", re.M | re.S)
SECTION_HEAD_RE = re.compile(r"^## (S\d+) ([\w-]+)", re.M)  # types are hyphenated: feature-callout, how-it-works
DIRECTIVE_RE = re.compile(r"^> (annotation|style|attrs|prior|text|device|duration|chrome): (.*)$", re.M)
MOTION_LINE_RE = re.compile(r"^\*\*Motion:\*\* (.+)$", re.M)
N_PLACEHOLDER = re.compile(r" \(n=…\)")
EXAMPLES_LINE_RE = re.compile(r"^\*\*Examples:\*\* .*$\n?", re.M)  # corpus asset ids; must not reach a blind worker
STANDS_IN = re.compile(r"none;\s*brief as ([a-z0-9-]+)", re.I)


def read_frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not m:
        return {}, text
    return (yaml.safe_load(m.group(1)) or {}), m.group(2)


def section_block(skeleton_text, sxx):
    """The `## Sxx type` block, up to the next `## ` heading or EOF."""
    heads = list(SECTION_HEAD_RE.finditer(skeleton_text))
    for i, h in enumerate(heads):
        if h.group(1) == sxx:
            end = heads[i + 1].start() if i + 1 < len(heads) else len(skeleton_text)
            return skeleton_text[h.start():end].rstrip(), h.group(2)
    raise SystemExit(f"brief.py: section {sxx} not found in skeleton.md")


def strip_asset_lines(block):
    """Drop src/local/alt from the block's slot fences; the brief never points a
    worker at the original (blindcheck enforces it)."""
    def clean(m):
        body = "\n".join(l for l in m.group(1).splitlines()
                         if not re.match(r"\s*(src|local|alt):", l))
        return f"```slot\n{body}\n```"
    return SLOT_RE.sub(clean, block)


def slot_records(block):
    """The slot dicts of a section, in order (from the skeleton fences)."""
    return [yaml.safe_load(b) for b in SLOT_RE.findall(block)]


def line_strings(line):
    """The quoted strings of a `> text:` or `> chrome:` line, in order; none for
    `none`, a TODO or no line."""
    if not line or line.strip().lower() == "none" or line.startswith("TODO"):
        return []
    return [s.strip().strip('"') for s in line.split("|")]


def slot_priors(block):
    """{slot id: its `> prior:` line}, the page-grammar advice under each slot
    fence (the manager's `# unusual:` note stripped)."""
    out = {}
    for m in re.finditer(r"^```slot\n(.*?)\n```(.*?)(?=^```slot|\Z)", block, re.M | re.S):
        rec = yaml.safe_load(m.group(1)) or {}
        p = re.search(r"^> prior: (.*)$", m.group(2), re.M)
        if p and rec.get("id"):
            out[rec["id"]] = p.group(1).split("  # unusual:")[0].strip()
    return out


def directives(block):
    """First value of each `>` line in the section (the manager sets them per
    section; a Series shares one family/device)."""
    out = {}
    for key, val in DIRECTIVE_RE.findall(block):
        out.setdefault(key, val.strip())
    return out


def family_block(family):
    """The `## <family>` block of style-families.md, verbatim minus the (n=…)
    placeholders. Returns (block_text, stands_in_for) — following a
    `Template: none; brief as X` to X's block."""
    text = STYLE_FAMILIES.read_text()
    blocks = {}
    for m in re.finditer(r"^## ([a-z0-9-]+)\n(.*?)(?=^## |\Z)", text, re.M | re.S):
        blocks[m.group(1)] = m.group(0).rstrip()
    if family not in blocks:
        raise SystemExit(f"brief.py: family {family!r} not in style-families.md")
    block = blocks[family]
    stands_in = None
    tm = re.search(r"^\*\*Template:\*\* (.+)$", block, re.M)
    if tm:
        sm = STANDS_IN.search(tm.group(1))
        if sm and sm.group(1) in blocks:
            stands_in, block = family, blocks[sm.group(1)]
    # drop the block's **Examples:** line: it lists the family's corpus asset
    # ids, which must not reach a worker (blindcheck refuses a brief that names
    # the page's own ids) — the worker's examples come from the `## Examples`
    # (similar) section, never this line.
    block = EXAMPLES_LINE_RE.sub("", N_PLACEHOLDER.sub("", block)).rstrip()
    return block, stands_in


def signature_checklist(block):
    """The **Signature:** line as one `- [ ] attr=value` item per clause."""
    m = re.search(r"^\*\*Signature:\*\* (.+)$", block, re.M)
    if not m:
        return "- [ ] (no Signature line)"
    clauses = [c.strip().rstrip(".") for c in m.group(1).split(";") if c.strip()]
    return "\n".join(f"- [ ] {c}" for c in clauses)


def references_section(family, slot_class):
    """prompt_guidance, search_terms and two examples (matching the slot class
    when possible) from corpus/references/<family>.yaml."""
    path = REFERENCES_DIR / f"{family}.yaml"
    if not path.exists():
        return f"(no corpus/references/{family}.yaml)"
    data = yaml.safe_load(path.read_text()) or {}
    photo = data.get("photography") or {}
    lines = [(photo.get("genre") or "").strip(), ""]
    terms = photo.get("search_terms") or []
    if terms:
        lines.append("Search terms: " + "; ".join(terms))
    examples = data.get("examples") or []
    matched = [e for e in examples if slot_class and slot_class in str(e.get("matches", ""))]
    for e in (matched or examples)[:2]:
        lines.append(f"- {e.get('url')} — {e.get('creator')} ({e.get('platform')})")
    return "\n".join(l for l in lines if l is not None)


def slot_class(section_type, record):
    """`<type>-<aspect class>`, the snapped aspect_class the family Slots line
    uses (SKILL 1.4.1), not the raw measured aspect."""
    aspect = record.get("aspect_class") or record.get("aspect")
    return f"{section_type}-{aspect}" if aspect else section_type


def composed(s):
    """A slot lp-compose draws: a generated still. Kept-from-source roles
    (icons, screenshots) are never generated, and a video slot is briefed as its
    family's main panel with no compose step."""
    return s.get("role") in GENERATED_ROLES and s.get("kind") != "video"


def slots_table(records, section_type, family, device):
    fam = family.split("/")[0]
    rows = ["| slot | kind | role | size | natural | class | family | panels |",
            "|---|---|---|---|---|---|---|---|"]
    for s in records:
        # each slot's own size picks its preset, so its panel count is its own
        if not board.composable(fam) or s.get("kind") == "video":
            panels = "1 panel"
        elif not composed(s):
            panels = "kept from source"
        else:
            n = len(plan.contract(fam, _preset(fam, device, s.get("size"), section_type)))
            panels = f"{n} panel{'s' if n != 1 else ''} (see below)"
        cls = slot_class(section_type, s)
        rows.append(f"| {s['id']} | {s.get('kind')} | {s.get('role')} | {s.get('size')} | "
                    f"{s.get('natural', '')} | {cls} | {family} | {panels} |")
    return "\n".join(rows)


def _run(cmd):
    """stdout of a helper command, or a one-line note on failure."""
    try:
        r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=300)
        return r.stdout.strip() or r.stderr.strip()
    except Exception as exc:  # a missing key or corpus is reported, not fatal
        return f"({' '.join(cmd[-3:])} unavailable: {exc})"


def flow_board(family, device, headline):
    return _run(["uv", "run", "lp-flow", "templates", "--family", family,
                 "--device", device or "none", "--query", headline])


def run_similar(run, sxx, section_type, family, page, exclude_ids, query, pool, seed, widen, kind=None):
    out_dir = run / "sections" / sxx / "examples"
    cmd = ["uv", "run", "lp-corpus", "similar", "--type", section_type,
           "--style", family, "--query", query, "--exclude", page, "-k", "2",
           "--out", str(out_dir)]
    if kind:
        cmd += ["--kind", kind]  # a video slot's examples are clips, excerpted as 3-frame strips
    for i in exclude_ids:
        cmd += ["--exclude-asset", i]
    if pool:
        cmd += ["--pool", str(pool), "--seed", seed or run.name]
    if widen:
        cmd += ["--widen", str(widen)]
    note = _run(cmd)
    excerpts = sorted(out_dir.glob("*.md")) if out_dir.exists() else []
    body = "\n\n".join(f"### {p.name}\n\n{p.read_text().strip()}" for p in excerpts)
    return body or note


def target_duration(record, directive, cap, prior=None):
    """(target seconds, note): the `> duration:` line's leading number, else the
    slot's own duration_s rounded, else the page grammar's median length for a
    slot in this context (the `> prior:` line), else 5; never above
    budget.video_seconds."""
    m = re.match(r"\s*(\d+(?:\.\d+)?)", directive or "")
    original = record.get("duration_s")
    pm = PRIOR_LENGTH_RE.search(prior or "")
    if m or original:
        wanted, why = round(float(m.group(1))) if m else round(original), None
    elif pm:
        basis = PRIOR_BASIS_RE.search(prior)
        wanted, why = round(float(pm.group(1))), ("no original length; the page grammar's median for "
                                                  f"{basis.group(1) if basis else 'this context'}")
    else:
        wanted, why = 5, "no original length; 5 s default"
    wanted = max(4, wanted)
    if cap and wanted > cap:
        return cap, f"original {original} s; capped at budget.video_seconds {cap}: note the shortfall in result.md"
    return wanted, why or f"original {original} s"


def video_section(records, fam_block, fm, directive, priors=None):
    """The `## Video` paragraph of a video slot's brief: the still-to-motion
    recipe on the run's models, the target duration per slot (faithful to the
    original, `> duration:` overriding, budget.video_seconds capping), the
    family's **Motion:** line and the result keys, per video-workflows.md."""
    defaults, budget = fm.get("defaults") or {}, fm.get("budget") or {}
    draft, final = defaults.get("video_draft", "seedance-2.0-mini"), defaults.get("video_model", "seedance-2.5")
    cap = budget.get("video_seconds", 30)
    priors = priors or {}
    m = MOTION_LINE_RE.search(fam_block)
    pm = next((PRIOR_MOTION_RE.search(priors.get(s["id"], "") + " ·") for s in records if s.get("kind") == "video"
               and PRIOR_MOTION_RE.search(priors.get(s["id"], "") + " ·")), None)
    motion = m.group(1) if m else (f"no **Motion:** line for this family yet; corpus clips in this section context: "
                                   f"{pm.group(1).strip()}" if pm else
                                   "no **Motion:** line for this family yet: prompt slow, subtle subject motion on "
                                   "a static camera and make it loop")
    lines = [f"**VIDEO slot.** The board is `kind: video`; `lp-flow check` enforces the still recipe plus the two video "
             f"nodes and every rule in `video-workflows.md`.",
             "",
             f"- Still: the family recipe above produces the accepted still. It is the `poster:` and the `startFrame`.",
             f"- Draft: `{draft}`, 5 s, 720p, `generateAudio: false`, `async: true`, "
             f"`extra: {{startFrame: \"<step N passed>\"}}` where N is the finishing still node (also in `in:`). "
             f"Gate the motion on the strip before any final.",
             f"- Final: `{final}`, same wiring, `duration:` = the target below (7 credits per second at 720p; "
             f"`endFrame` is free). Preflight it and record the quote. Above 30 s: a `{final}-video-extend` node "
             f"per remaining stretch (25 cr / 5 s, 75 / 15 s).",
             f"- Motion (what this family's corpus clips do): {motion}",
             f"- Loop: when the Motion line says the clips loop, add `extra.endFrame: \"<step N passed>\"` on the same still.",
             "- Target duration:"]
    for s in records:
        if s.get("kind") != "video":
            continue
        target, note = target_duration(s, directive, cap, priors.get(s["id"]))
        lines.append(f"  - {s['id']}: **{target} s** ({note})")
    lines += ["- After each clip: `curl` it to `steps/`, then `uv run lp-corpus frames steps/<slot>-<node>-<n>.mp4 "
              "--out steps/<slot>-<node>-strip.png` and `Read` the strip; `picsart_media_probe_media` gives the length. "
              "Write the clip URL into the node's `outputs` the instant `job_status` returns it.",
              "- `result.md`: `chosen:` is the final clip URL, plus `poster:` (the accepted still) and `duration_s:` (measured); "
              "scores add `first_frame`, `motion`, `loop`."]
    return "\n".join(lines)


def placement_section(skeleton, sxx, section_type, fm, priors, g=None):
    """`## Where this section sits`: the page family, the neighbours, the
    family's typical order, each slot's `> prior:` line and the copy themes the
    headline shares with the corpus, from the page grammar. Empty without one."""
    g = g if g is not None else grammar.load(GRAMMAR_YAML)
    fam = fm.get("page_family")
    if not g or not fam:
        return ""
    heads = [(h.group(1), h.group(2)) for h in SECTION_HEAD_RE.finditer(skeleton)]
    i = [sid for sid, _ in heads].index(sxx)
    prev = f"after {heads[i - 1][1]} ({heads[i - 1][0]})" if i else "first on the page"
    nxt = f"before {heads[i + 1][1]} ({heads[i + 1][0]})" if i + 1 < len(heads) else "last on the page"
    lines = [f"Page family: {fam}. {sxx} is section {i + 1} of {len(heads)}, {prev}, {nxt}."]
    seq = (g["sequences"].get(fam) or {}).get("canonical") or []
    if seq:
        lines.append(f"A typical {fam} page: " + " → ".join(
            (f"**{t}**" if t == section_type else t) + (f" ×{c}" if c > 1 else "") for t, c, _ in seq) + ".")
    if priors:
        lines.append("What slots in this context usually are (the page grammar; advice: the original's image-or-video "
                     "and length stand, the family is the `> style:` above):")
        lines += [f"- {sid}: {p}" for sid, p in priors.items()]
    head = re.search(r"^- t\d+ h\d: (.+)$", block_of(skeleton, sxx), re.M)
    have = set(grammar.terms(head.group(1))) if head else set()
    shared = [t for t in ((g["themes"].get(section_type) or {}).get("terms") or []) if t[0] in have]
    if shared:
        lines.append("Copy themes this headline shares with the corpus's " + section_type + " sections: " + ", ".join(
            f"“{term}” ({n} sections; video {round(v * 100)} %{', mostly ' + st if st else ''})"
            for term, n, v, st in shared) + ".")
    return "\n".join(lines)


def block_of(skeleton, sxx):
    return section_block(skeleton, sxx)[0]


def headline_and_body(block):
    """The section's headline and first paragraph, as the similar query."""
    texts = re.findall(r"^- t\d+ \w+: (.+?)(?: -> \S+)?$", block, re.M)
    return " ".join(texts[:2]).strip()[:300]


def assemble(run, sxx, pool=0, seed=None, widen=0, replan=False):
    run = Path(run)
    skeleton = (run / "skeleton.md").read_text()
    fm, _ = read_frontmatter(skeleton)
    block, section_type = section_block(skeleton, sxx)
    d = directives(block)
    family = (d.get("style") or "").split("/")[0].strip()
    if not family or family.upper() == "TODO":
        raise SystemExit(f"brief.py: {sxx} has no resolved `> style:` line yet")
    ground = (d.get("style") or "").split("/", 1)[1] if "/" in (d.get("style") or "") else "default"
    device = re.match(r"([a-z-]+)", d.get("device", "none")).group(1)

    fam_block, stands_in = family_block(family)
    records = slot_records(block)
    cls = slot_class(section_type, records[0]) if records else section_type

    slots_meta = json.loads((run / "slots.json").read_text())["slots"]
    exclude_ids = sorted(blindcheck.identifiers(slots_meta))
    query = headline_and_body(block)

    dry = "yes" if (fm.get("budget") or {}).get("dry_run") or _dry(run) else "no"
    budget = (fm.get("budget") or {})
    is_video = section_type_is_video(records)
    kind = "video" if is_video else "image"
    cap = budget.get("video_slot" if is_video else "image_slot", 40)

    parts = []
    parts.append(f"# Brief: {sxx} {section_type}\n")
    parts.append(f"Run: {run.name}. Work only inside this folder. Dry run: {dry}.\n")
    parts.append("## Page context\n")
    parts.append(yaml.safe_dump({k: fm.get(k) for k in ("page", "brand", "audience", "defaults", "budget", "notes") if k in fm},
                                sort_keys=False, allow_unicode=True).rstrip() + "\n")
    parts.append("## Section (verbatim from skeleton.md)\n")
    parts.append(re.sub(r"^> prior: .*\n?", "", strip_asset_lines(block), flags=re.M) + "\n")  # shown below
    priors = slot_priors(block)
    placement = placement_section(skeleton, sxx, section_type, fm, priors)
    if placement:
        parts.append("## Where this section sits\n")
        parts.append(placement + "\n")
    parts.append(f"## Style family: {family}" + (f"/{ground}" if ground != "default" else "") + "\n")
    parts.append(fam_block + "\n")
    parts.append("Signature checklist (the block's **Signature** line):\n" + signature_checklist(fam_block) + "\n")
    parts.append(f"Ground variant: {ground}.")
    if stands_in:
        parts.append(f"Stands in for: {stands_in} (a fallback block is used).")
    parts.append(f"Device: {d.get('device', 'none')}\n")
    parts.append("## Flow board\n")
    parts.append(flow_board(family, device, query) + "\n")
    parts.append(f"**Planned recipe (mandatory).** Write `family: {family}`" + (" and `kind: video`" if is_video else "")
                 + f" on the board and author the whole recipe up front:\n\n{board.recipe_row(family, kind)}\n\n"
                 "`lp-flow check` reads `family:` and fails a board that skips a planned node.\n")
    if is_video:
        parts.append("## Video\n")
        parts.append(video_section(records, fam_block, fm, d.get("duration"), priors) + "\n")
    parts.append("## Text in image\n")
    parts.append(text_in_image(d.get("text", "none"), records, section_type) + "\n")
    parts.append("## Slots to produce\n")
    parts.append(slots_table(records, section_type, family + (f"/{ground}" if ground != "default" else ""), device) + "\n")
    to_compose = [s for s in records if composed(s)]
    composition = composition_section(family, device, sizes=[(s["id"], s.get("size")) for s in to_compose],
                                      section=section_type) if to_compose else ""
    if composition:
        parts.append(composition)
        # write one composition-<slot>.yaml per composable slot: the machine
        # contract the worker renders (spec-from-plan) and precheck/review read
        preset = _preset(family, device)
        chrome = d.get("chrome", "none")
        labels = line_strings(chrome)
        twice = sorted(set(labels) & set(line_strings(d.get("text", "none"))))
        if twice:
            raise SystemExit(f"brief.py: {sxx}: {', '.join(map(repr, twice))} is on both `> text:` and `> chrome:`; "
                             "a string is drawn once, by the model or by the chrome")
        derived = {"style": d.get("style"), "device": d.get("device"), "text": d.get("text", "none"), "chrome": chrome}
        (run / "sections" / sxx).mkdir(parents=True, exist_ok=True)
        names = []
        for s in to_compose:
            cp = plan.build(family, s.get("size"), preset=preset, labels=labels or None, section=section_type,
                            ground=(ground if ground != "default" else None), slot=s["id"], derived_from=derived)
            slots = LABELS.get((family, cp.get("preset")))
            if chrome.startswith("TODO") and slots:
                raise SystemExit(f"brief.py: {sxx} has no resolved `> chrome:` line yet; {family} "
                                 f"{cp.get('preset') or 'default'} draws: {', '.join(n for n, _ in slots)}")
            fname = f"composition-{s['id']}.yaml"
            path = run / "sections" / sxx / fname
            kept = None if replan or not path.exists() else (yaml.safe_load(path.read_text()) or {})
            if kept is not None:
                source = ("family", "size", "derived_from")
                if {k: kept.get(k) for k in source} != {k: cp.get(k) for k in source}:
                    raise SystemExit(f"brief.py: {sxx}: {fname} was built from other skeleton lines or another slot "
                                     "size; re-run with --replan to rebuild it (hand edits to it are dropped)")
                cp = kept  # the manager's hand edits (a moved select.rect, a checker tone, panel state) survive
            probs = plan.validate(cp)
            if probs:
                raise SystemExit(f"brief.py: {sxx} composition plan for {s['id']}: {'; '.join(probs)}")
            if kept is None:
                plan.write_plan(path, cp)
            names.append(fname)
        parts.append(f"A composition plan is written per slot ({', '.join(names)}). Generate the panels above, "
                     f"then `uv run lp-compose --spec-from-plan <plan> --image <panel>=<path> ... --out compose-<slot>.yaml` "
                     f"to make the compose spec; add only image paths.\n")
    parts.append("## Examples from the corpus (same section type)\n")
    parts.append(run_similar(run, sxx, section_type, family, fm.get("page", ""),
                             exclude_ids, query, pool, seed, widen, kind if is_video else None) + "\n")
    parts.append("## References\n")
    parts.append(references_section(family, cls) + "\n")
    parts.append("Build the photo prompt from this genre; the section copy gives the subject matter.\n")
    parts.append("## Shared context\n")
    shared = run / "shared-context.md"
    parts.append((shared.read_text().strip() if shared.exists() else "none yet: you are the hero") + "\n")
    parts.append("## Budget\n")
    parts.append(f"Advisory cap for this section: {cap} credits. Preflight every paid step; if the "
                 "quoted total exceeds the cap, stop and report.\n")
    parts.append("## Output contract\n")
    parts.append("See output-contract.md.\n")
    parts.append((HERE / "output-contract.md").read_text().strip() + "\n")
    return "\n".join(parts)


def section_type_is_video(records):
    return any(s.get("kind") == "video" for s in records)


def text_in_image(text_line, records, section_type):
    if not text_line or text_line.strip().lower() == "none":
        return "`none` (this slot carries no text; the prompt ends with \", no text, no logos or watermarks\")."
    strings = [s.strip().strip('"') for s in text_line.split("|")]
    rows = ["| slot | string | role | panel | position |", "|---|---|---|---|---|"]
    sid = records[0]["id"] if records else section_type
    for i, s in enumerate(strings):
        role = "headline" if i == 0 else "call-to-action"
        rows.append(f"| {sid} | \"{s}\" | {role} | photo | per the family's Text line |")
    return "\n".join(rows)


def _dry(run):
    try:
        return bool(json.loads((run / "budget.json").read_text()).get("dry_run"))
    except Exception:
        return False


def main(argv=None):
    p = argparse.ArgumentParser(prog="brief.py", description="Assemble one section's brief.md.")
    p.add_argument("run", type=Path)
    p.add_argument("section", help="Sxx")
    p.add_argument("--pool", type=int, default=0)
    p.add_argument("--seed")
    p.add_argument("--widen", type=int, default=0)
    p.add_argument("--replan", action="store_true",
                   help="rebuild the section's composition plans even when they exist (drops hand edits)")
    a = p.parse_args(argv)

    text = assemble(a.run, a.section, pool=a.pool, seed=a.seed, widen=a.widen, replan=a.replan)
    dest = Path(a.run) / "sections" / a.section / "brief.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text)

    problems = blindcheck.check(a.run, a.section)
    if problems:
        dest.unlink()
        print(f"brief.py: NOT written — blindcheck failed for {a.section}:", file=sys.stderr)
        for pr in problems:
            print("  " + pr, file=sys.stderr)
        return 1
    print(f"{dest}: written, blindcheck clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
