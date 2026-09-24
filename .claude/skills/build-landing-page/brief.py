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
DEGRADE_RE = re.compile(r"degrade: (\w+)")

sys.path.insert(0, str(HERE))
import blindcheck  # noqa: E402
from landing_page_gen.flow import board  # noqa: E402
from landing_page_gen.compose import bank, cli as compose_cli, fitcheck, models, plan, roles, timeline  # noqa: E402
from landing_page_gen.compose import families  # noqa: E402
from landing_page_gen.compose.families import FAMILIES  # noqa: E402
from landing_page_gen.corpus import attrs, genmode, grammar, readings  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402
from landing_page_gen.corpus.db import GENERATED_ROLES  # noqa: E402


def _preset(family, device, size=None, section=None):
    """The compose preset a device selects for this family, else the one the
    section type selects, else the variant whose aspect the slot size has when
    the default's does not, or None."""
    preset = device if device in (FAMILIES.get(family, {}).get("variants") or {}) else None
    return compose_cli.preset_for_size(family, size, preset, section)


def composition_section(family, device, size=None, sizes=None, section=None, plans=None):
    """For a composable family, the panels the worker generates (with the ratio
    and fit) and the keep-clear region each carries — so it stops guessing.
    `sizes` is [(slot id, size)] for the section: slots whose sizes select
    different presets (a 1:1 and a 21:10 before-after slot) each get their own
    table, so the brief never contradicts the per-slot composition plans."""
    if not board.composable(family):
        return ""
    groups = {}  # (preset, derived panels) -> the slot ids it serves, in section order
    for sid, sz in (sizes or [(None, size)]):
        derived = tuple(p["panel"] for p in ((plans or {}).get(sid) or {}).get("panels") or [] if p.get("from"))
        groups.setdefault((_preset(family, device, sz, section), derived), []).append(sid)
    rows = ["## Panels and keep-clear", "",
            "Generate one panel per row at the ratio given; keep the subject out of any keep-clear "
            "region (an overlay sits there). A panel holds only the model's picture: a *scene* is a whole "
            "picture with its own backdrop, a *design* a finished card or poster, a *subject* a cut-out whose "
            "surround is the template's. The background (ground, cards) and every block are lp-compose's, "
            "never a model's: never paint a card, frame, border or UI into a panel.", ""]
    for i, ((preset, _), sids) in enumerate(groups.items()):
        if len(groups) > 1:
            rows += ([""] if i else []) + [f"Slots {', '.join(sids)} ({preset or 'default'} layout):", ""]
        rows += ["| panel | holds | generate at | fit | keep clear (fractions of the panel) |", "|---|---|---|---|---|"]
        built = next((plans[sid] for sid in sids if sid in (plans or {})), None)
        derived = {p["panel"]: p for p in (built or {}).get("panels") or [] if p.get("from")}
        for p in plan.contract(family, preset):
            if p["panel"] in derived:
                d = derived[p["panel"]]
                src = "the After slot's final image" if d["from"] == "pair" else f"panel {d['from']}"
                rows.append(f"| {p['panel']} | — | — | — | derived: lp-compose makes it from {src} "
                            f"(degrade: {d['degrade']}); do not generate |")
                continue
            kc = "; ".join(f"{r['item']} {r['frac']}" for r in p["keep_clear"]) or "—"
            rows.append(f"| {p['panel']} | {p.get('holds', 'scene')} | {p['ratio']} | {p['fit']} | {kc} |")
    return "\n".join(rows) + "\n"

SLOT_RE = re.compile(r"^```slot\n(.*?)\n```", re.M | re.S)
SECTION_HEAD_RE = re.compile(r"^## (S\d+) ([\w-]+)", re.M)  # types are hyphenated: feature-callout, how-it-works
DIRECTIVE_RE = re.compile(r"^> (annotation|style|attrs|prior|text|device|duration|chrome|motion|mode): (.*)$", re.M)
MOTION_LINE_RE = re.compile(r"^\*\*Motion:\*\* (.+)$", re.M)
N_PLACEHOLDER = re.compile(r" \(n=…\)")
EXAMPLES_LINE_RE = re.compile(r"^\*\*Examples:\*\* .*$\n?", re.M)  # corpus asset ids; must not reach a blind worker
STANDS_IN = re.compile(r"none;\s*brief as ([a-z0-9-]+)", re.I)


def read_frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not m:
        return {}, text
    return (yaml.safe_load(m.group(1)) or {}), m.group(2)


def only_slot(block, slot):
    """The section block cut to its copy and one slot's fence with the `>`
    lines under it: a live check briefs one slot of a section whose other
    slots stay unresolved (kept from source)."""
    fences = list(re.finditer(r"^```slot\n.*?\n```.*?(?=^```slot|\Z)", block, re.M | re.S))
    mine = [m for m in fences if re.search(rf"^id: {re.escape(slot)}$", m.group(0), re.M)]
    if not mine:
        raise SystemExit(f"brief.py: slot {slot} is not in this section")
    head = block[:fences[0].start()] if fences else block
    return head + mine[0].group(0).rstrip()


ORIGINAL_LINES = ("annotation", "style", "attrs", "device", "text", "chrome", "mode")  # what the manager read off the original
PROPOSAL_KEYS = ("style", "device", "annotation", "text", "chrome", "mode")


def blind_block(block, proposals=None):
    """The section block with every line read off the original removed (its
    measured attrs, its labelled family, the manager's description); with a
    worker's proposals ({slot id: {key: value}}) their lines take the place of
    those under each slot fence. A blind worker decides from context alone."""
    block = re.sub(rf"^> ({'|'.join(ORIGINAL_LINES)}): .*\n?", "", block, flags=re.M)
    for sid, prop in (proposals or {}).items():
        val = lambda v: " | ".join(f'"{x}"' for x in v) if isinstance(v, list) else v  # noqa: E731  a list of strings is the skeleton's `"a" | "b"`
        lines = "".join(f"> {k}: {val(prop[k])}\n" for k in PROPOSAL_KEYS if prop.get(k) is not None)
        block = re.sub(rf"(^```slot\n(?:(?!```).)*?^id: {re.escape(sid)}\n.*?^```\n)", lambda m: m.group(1) + lines,
                       block, count=1, flags=re.M | re.S)
    return block


def proposals_of(run, sxx, slots):
    """{slot id: proposal} from sections/<Sxx>/proposal-<slot>.yaml, for the slots that have one."""
    out = {}
    for sid in slots:
        f = Path(run) / "sections" / sxx / f"proposal-{sid}.yaml"
        if f.exists():
            out[sid] = read_proposal(f.read_text())
    return out


def read_proposal(text):
    """A proposal file: YAML, or the skeleton's own `key: value` lines when a
    value carries its own colon (`device: none: a claim`)."""
    try:
        doc = yaml.safe_load(text)
        if isinstance(doc, dict):
            return doc
    except yaml.YAMLError:
        pass
    out, key = {}, None
    for line in text.splitlines():
        m = re.match(r"^([a-z_]+): ?(.*)$", line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            out[key] = val.strip('"').split("  # ")[0].rstrip() if val not in (">-", "|", ">") else ""
        elif key and line.startswith(" "):
            out[key] = (out[key] + " " + line.strip()).strip()
    return out


def families_that_fit(size):
    """The generated families that have a layout at a slot's size (WxH): every
    family without a compose template, and each template family whose default
    or one of its variants (induced ones included) takes that aspect."""
    w, h = compose_cli.parse_size(size) if isinstance(size, str) else size
    out = []
    for f in family_names():
        if never_generated(family_block(f)[0]):
            continue
        if f not in FAMILIES or compose_cli.fits(FAMILIES[f], w, h) or compose_cli.preset_for_size(f, (w, h)):
            out.append(f)
    return out


LAYOUTS_SHOWN = 8  # per family and slot: the hand-made ones first, then measured ones


def layout_line(family, name, tmpl, planned=None):
    """One layout as a blind worker sees it: its id, its panels and its slots
    with the bank blocks that may fill each on this page (never the corpus
    asset it was measured from)."""
    panels = ", ".join(f"{p} {p_['ratio'] if p_.get('ratio') else ''} holds {p_.get('holds', 'scene')}".replace("  ", " ")
                       for p, p_ in tmpl["panels"].items())
    cands = {sl["id"]: [c["block"] for c in sl.get("candidates") or []] for sl in planned or []}
    slots = "; ".join(f"{sl['id']} ({sl.get('shape', 'tile')}: {' | '.join(sl.get('accepts') or [])}"
                      f"{', required' if sl.get('required') else ''}"
                      + (f"; blocks here: {', '.join(cands[sl['id']]) or 'none'}" if sl["id"] in cands else "") + ")"
                      for sl in tmpl.get("slots") or [])
    return f"  - `{name or 'default'}`: {len(tmpl['panels'])} panel{'s' if len(tmpl['panels']) != 1 else ''} ({panels})" + \
        (f"; slots: {slots}" if slots else "; no chrome slots")


def layouts_menu(size, fams, facts=None):
    """The compose layouts of each family that fit a slot's size: what a
    proposal chooses between, so the layout carries the device (blind-2: three
    plans fell back to a default that could not show the proposed set, stack or
    prompt box)."""
    w, h = compose_cli.parse_size(size) if isinstance(size, str) else size
    out = []
    for f in fams:
        if f not in FAMILIES:
            continue
        rows = []
        for name in families.layout_names(f, None):
            tmpl = compose_cli.template(f, name)
            if not compose_cli.fits(tmpl, w, h) or len(rows) >= LAYOUTS_SHOWN:
                continue
            planned = None
            if facts:
                try:
                    planned = plan.build(f, f"{w}x{h}", preset=name, facts=facts)["slots"]
                except (SystemExit, KeyError, ValueError):
                    continue
                if any(sl["required"] and not sl.get("candidates") for sl in planned):
                    continue  # a required slot no bank block can fill on this page (blind-2-1's m-133f23)
            rows.append(layout_line(f, name, tmpl, planned))
        if rows:
            out.append(f"- `{f}`:\n" + "\n".join(rows))
    return "\n".join(out)


def families_menu():
    """Every style family's name and **Use:** line: what a blind worker chooses from."""
    text = STYLE_FAMILIES.read_text()
    return "\n".join(f"- `{m.group(1)}`: {m.group(2).strip()}" for m in
                      re.finditer(r"^## ([a-z0-9-]+)\n\*\*Use:\*\* (.*)$", text, re.M)
                      if not never_generated(family_block(m.group(1))[0]))


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


def never_generated(fam_block):
    """A family whose **Never:** line says it is not generated (editor-canvas, model-card): kept from source."""
    return bool(re.search(r"^\*\*Never:\*\* generated", fam_block, re.M))


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


def section_copy(block):
    """Every text node of the section, the copy a block's claim is checked against."""
    return " ".join(re.findall(r"^- t\d+ \w+: (.+?)(?: -> \S+)?$", block, re.M))


def page_strings(skeleton):
    """The short strings (60 characters or fewer) of the page's hero, where its
    tool's own interface sits (a calculator's field names): a block may show
    them though the section copy does not say them. Never pricing or footer."""
    heads = list(SECTION_HEAD_RE.finditer(skeleton))
    out = []
    for i, h in enumerate(heads):
        if h.group(2) != "hero":
            continue
        body = skeleton[h.start():heads[i + 1].start() if i + 1 < len(heads) else len(skeleton)]
        out += [t for t in re.findall(r"^- t\d+ \w+: (.+?)(?: -> \S+)?$", body, re.M) if len(t) <= 60]
    return " | ".join(dict.fromkeys(out))


def page_facts(records, fm, block, labels, skeleton=""):
    """What the section's blocks may claim (compose/roles.facts_for): the page's
    tool, the tools its copy names, the models it presents, the model its
    pictures are generated on, its copy, the page's short strings and the
    `> chrome:` strings."""
    page = source_page(records[0], fm) if records else fm.get("page", "")
    names = [n for n in (models.model_name(m) for m in models.page_models(page)) if n]
    default = models.name_for_id((fm.get("defaults") or {}).get("image_model") or "gpt-image-2.5-sunburst")
    return roles.facts_for(page, section_copy(block), labels, names, generator=default,
                           page_copy=page_strings(skeleton))


def _candidate(c):
    b = bank.block(c["block"])
    bound = ", ".join(f"{k} {v}" for k, v in c.items() if k not in ("block", "give"))
    params = b.get("params") or {}
    give = ("; give " + ", ".join(f"`{g}:`" + (f" ({params[g]['note']})" if params.get(g, {}).get("note") else "")
                                  for g in c["give"])) if c.get("give") else ""
    return f"**{c['block']}**{' (' + bound + ')' if bound else ''}: {b['means']}. *When:* {b['when']}{give}"


def blocks_section(plans):
    """## Blocks: each slot of each composition, the categories it takes, and
    the bank blocks that may honestly fill it on this page, with what each
    means and when it belongs. The worker picks; nothing is pre-filled."""
    if not plans:
        return ""
    rows = ["## Blocks", "",
            "The layout is a skeleton: every slot is empty until you fill it. For each slot pick ONE block "
            "from its candidates, only if its *When* is true of this section (its copy, its page, the picture "
            "you will make); leave an optional slot empty (`block: none`) rather than fill it with a block "
            "that does not belong. Candidates already pass the hard checks (category, shape, the page's own "
            "tool, the generating model's mark, two states for a Before/After); excluded blocks say why. "
            "Labels you give come verbatim from the page copy.", "",
            "**Every string and value is about your picture.** An example a block works (a calculator's numbers, "
            "an adjustment's values) is your picture's own: numbers you choose for the thing you made, computed. "
            "A list names where your picture goes. Never an example, a name or a number from anywhere else, and "
            "leave out a block whose text would read the same beside any picture. Everything you need is in this "
            "brief and `blocks.md`; never read `src/`, `tests/` or `corpus/`.", ""]
    for sid, cp in plans.items():
        derived = [p for p in cp["panels"] if p.get("from") or p.get("degrade")]
        for p in derived:
            src = "the After slot " + str(cp.get("pair")) + "'s final image" if p.get("from") == "pair" else p.get("from")
            rows.append(f"- {sid} panel {p['panel']}: " + (f"derived from {src}, degraded: {p['degrade']}" if p.get("from")
                        else f"degraded left of the handle: {p['degrade']}"))
        rows += [f"### {sid}" + (f" ({cp['preset']})" if cp.get("preset") else ""), ""]
        for sl in cp.get("slots") or []:
            need = "required" if sl["required"] else "optional"
            state = f", the {sl['state']} panel" if sl.get("state") else ""
            rows.append(f"- slot **{sl['id']}** ({sl['shape']}; takes {' | '.join(sl['accepts'])}; {need}{state})")
            for c in sl.get("candidates") or []:
                rows.append(f"  - {_candidate(c)}")
            for e in sl.get("excluded") or []:
                rows.append(f"  - ~~{e['block']}~~{' (' + e['tool'] + ')' if e.get('tool') else ''}: {e['why']}")
        rows.append("")
    rows += ["Write `blocks-<slot>.yaml` before any paid call:", "", "```yaml",
             "slot: <slot id>", "fills:",
             "  - {slot: <slot>, block: <block>, <param>: <value>, because: <the copy or page fact that makes it fit>}",
             "  - {slot: <optional slot>, block: none, because: <why nothing belongs here>}", "```", "",
             "then `uv run lp-compose --check-blocks composition-<slot>.yaml blocks-<slot>.yaml` (absolute paths) and "
             "fix what it names; it binds any attribution block into `made-by.yaml`.", ""]
    return "\n".join(rows) + "\n"


def timeline_section(run, sxx, records, motion, labels, facts):
    """For `> motion: timeline <preset>`: write motion-<slot>.yaml per video
    slot (compose/timeline.build) and brief the panels to generate and the
    render. Stops on a TODO preset or a block the page cannot claim."""
    words = motion.split("#")[0].split()
    if len(words) < 2 or words[1] == "TODO" or words[1] not in timeline.PRESETS:
        raise SystemExit(f"brief.py: {sxx}: resolve `> motion:` to `timeline <preset>` ({', '.join(timeline.PRESETS)}) "
                         "or `generative`")
    preset = words[1]
    _, panels, strings = timeline.PRESETS[preset]
    out = [f"## Timeline ({preset})", "",
           "This clip is a composition changing state on a static camera, not generated motion. Generate the "
           "panels below as stills (the family's still recipe), then render it locally (0 credits):", "",
           "| panel | what |", "|---|---|"]
    out += [f"| {k} | {v} |" for k, v in panels.items()]
    out += ["", f"Page strings, in `> chrome:` order: {', '.join(strings)}.", ""]
    for s in records:
        if s.get("kind") != "video" or s.get("role") not in GENERATED_ROLES:
            continue
        w, h = (int(v) for v in render_size(s).split("x"))
        size = f"{w - w % 2}x{h - h % 2}"
        spec = timeline.build(preset, size, labels, facts, slot=s["id"])
        probs = timeline.validate(spec)
        if probs:
            raise SystemExit(f"brief.py: {sxx} timeline for {s['id']}: {'; '.join(probs)}")
        path = run / "sections" / sxx / f"motion-{s['id']}.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(spec, sort_keys=False, allow_unicode=True))
        imgs = " ".join(f"--image {k}=steps/<{k}>.png" for k in panels if k not in timeline.OPTIONAL_PANELS)
        out.append(f"- {s['id']}: `uv run lp-compose --timeline sections/{sxx}/motion-{s['id']}.yaml {imgs} "
                   f"--out steps/{s['id']}.webm --poster steps/{s['id']}-poster.png` ({spec['duration']:.1f} s; the "
                   f"board's last node is `node: motion`, `tool: lp-compose`, `timeline: motion-{s['id']}.yaml`)")
    out += ["", "Judge the clip on its strip (`lp-corpus frames`), as any video. `result.md` carries `poster:` and "
            "`duration_s:`."]
    return "\n".join(out) + "\n"


def render_size(s, fits=None, aspects=()):
    """The size a slot is composed at: its display box scaled up to the source
    image's resolution (a 480x480 box showing a 720x720 image renders at 720,
    not soft at 480). The display aspect is kept, since the page crops a
    natural image of another shape with object-fit; never below the display.
    `fits(w, h)`, the chosen layout's aspect test: when the box's shape misses
    it but the source's own shape fits and differs by at most 5 % (a 738x590
    file in a 342x282 box, trimmed a few pixels by the page), the slot
    composes at the source's size, the one its layout was measured at."""
    size, natural = s.get("size"), s.get("natural")
    if not size or not natural:
        return size
    (w, h), (nw, nh) = compose_cli.parse_size(size), compose_cli.parse_size(natural)
    k = max(1, min(nw / w, nh / h))
    box = (round(w * k), round(h * k))
    if fits and not fits(*box) and fits(nw, nh) and nw >= w and abs((nw / nh) / (w / h) - 1) <= 0.05:
        return f"{nw}x{nh}"
    near = [(fw, fh) for fw, fh in aspects if abs((fw / fh) / (w / h) - 1) <= 0.05]
    if fits and not fits(*box) and near:  # a 5:4 layout in a 342x282 box: the page's object-fit trims the few pixels
        fw, fh = near[0]
        return f"{box[0]}x{round(box[0] * fh / fw)}"
    return f"{box[0]}x{box[1]}"


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
    cmd = ["uv", "run", "lp-corpus", "similar", "--type", section_type, "--query", query, "--exclude", page, "-k", "2",
           "--out", str(out_dir)] + (["--style", family] if family else [])  # a blind proposal has no family yet
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


def mode_expectation(fm, section_type, n_media):
    """The generation modes the corpus allows for this context (corpus/genmode.py)."""
    return genmode.expect(genmode.load(str(REPO / "corpus" / "corpus.db")), section_type, n_media,
                          fm.get("page", ""), fm.get("page_family"))


def family_names():
    return [m.group(1) for m in re.finditer(r"^## ([a-z0-9-]+)\n\*\*Use:\*\*", STYLE_FAMILIES.read_text(), re.M)]


def mode_section(e, n_media):
    """`## Generation mode`: standalone, design or layered, as Picsart uses it here,
    and the families that make it. brief.py refuses any other family."""
    fams = [f for f in family_names() if not never_generated(family_block(f)[0])
            and (set(genmode.family_modes(f)) | set(genmode.family_modes(f, "x"))) & set(e["allowed"])]
    lines = [f"This section holds {n_media} image{'s' if n_media != 1 else ''}. Across the corpus, pictures in this "
             f"context are {genmode.line(e)}.", ""]
    lines += [f"- **{m}**: {genmode.MEANING[m]}" for m in e["allowed"]]
    lines += ["", "Picsart uses a bare standalone generation only where it showcases many options side by side (a "
              "scrolling gallery of different characters, styles or subjects) and on tutorial thumbnails; elsewhere "
              "its images are templates or layered compositions.",
              "Families that make an allowed mode: " + ", ".join(f"`{f}`" for f in fams) + ". Any other family is "
              "refused by brief.py unless the slot carries `mode: <mode> because <the copy that demands it>`."]
    return "\n".join(lines)


def check_mode(sxx, e, family, text, override):
    """Refuse a family whose mode this context does not allow (the blind-1 link tiles went full-bleed)."""
    if genmode.fits(e, family, text) or (override and " because " in override):
        return
    raise SystemExit(f"brief.py: {sxx}: {family} makes {' or '.join(genmode.family_modes(family, text))}, but this "
                     f"context is {genmode.line(e).replace('**', '')}. Choose a family of an allowed mode, or add "
                     "`> mode: <mode> because <the copy that demands it>` under the slot")


def placements(fm, records):
    """{slot id: where it sits}: the card heading the image belongs to, the
    card's own text, and its position among the section's images, read from the
    page snapshot. Layout context, not the original picture."""
    out, soups = {}, {}
    n = len(records)
    for i, r in enumerate(records):
        page = source_page(r, fm)
        html = REPO / "corpus" / "pages" / page / "page.html"
        if not html.exists():
            continue
        soup = soups.get(page) or soups.setdefault(page, BeautifulSoup(html.read_text(), "html.parser"))
        el = soup.select_one(f'[data-lp="{r["id"]}"]')
        if el is None:
            continue
        card = None
        for anc in el.parents:
            heads = anc.find_all(["h2", "h3", "h4"])
            if heads:
                card = (heads[0].get_text(" ", strip=True), anc.get_text(" ", strip=True)) if len(heads) == 1 else None
                break
        where = f"image {i + 1} of {n} in this section"
        if card:
            where += f", in the card headed “{card[0]}”"
            if card[1] != card[0]:
                where += f" (card text: “{card[1][:240]}”)"
        out[r["id"]] = where
    return out


def placement_lines(places):
    return "\n".join(f"- {sid}: {w}" for sid, w in places.items())


def block_of(skeleton, sxx):
    return section_block(skeleton, sxx)[0]


def headline_and_body(block):
    """The section's headline and first paragraph, as the similar query."""
    texts = re.findall(r"^- t\d+ \w+: (.+?)(?: -> \S+)?$", block, re.M)
    return " ".join(texts[:2]).strip()[:300]


def assemble(run, sxx, pool=0, seed=None, widen=0, replan=False, slot=None, blind=False):
    run = Path(run)
    skeleton = (run / "skeleton.md").read_text()
    fm, _ = read_frontmatter(skeleton)
    block, section_type = section_block(skeleton, sxx)
    all_records = slot_records(block)
    n_media = len(all_records)
    expected = mode_expectation(fm, section_type, n_media)
    places = placements(fm, all_records)
    if slot:
        block = only_slot(block, slot)
    if blind:
        ids = [r["id"] for r in slot_records(block) if r.get("role") in GENERATED_ROLES]
        props = proposals_of(run, sxx, ids)
        if len(props) < len(ids):
            return proposal_brief(run, sxx, blind_block(block), section_type, fm, [i for i in ids if i not in props],
                                  expected, n_media, places)
        block = blind_block(block, props)
    d = directives(block)
    family = (d.get("style") or "").split("/")[0].strip()
    if not family or family.upper() == "TODO":
        raise SystemExit(f"brief.py: {sxx} has no resolved `> style:` line yet")
    ground = (d.get("style") or "").split("/", 1)[1] if "/" in (d.get("style") or "") else "default"
    device = re.match(r"([a-z0-9-]+)", d.get("device", "none")).group(1)  # induced layouts are i-<asset id>

    owner = [f for f, fam in FAMILIES.items() if device in (fam.get("variants") or {})]
    if device not in ("none", "default") and owner and family not in owner:
        raise SystemExit(f"brief.py: {sxx}: layout {device!r} belongs to {', '.join(owner)}, not {family}: a layout "
                         f"renders only under its own family, so write `style: {owner[0]}` or choose one of "
                         f"{family}'s layouts")
    check_mode(sxx, expected, family, d.get("text", "none"), d.get("mode"))
    if len(line_strings(d.get("text", "none"))) > 2:
        raise SystemExit(f"brief.py: {sxx}: `> text:` names {len(line_strings(d.get('text')))} strings; at most 2 "
                         "(a 1-3 word headline and one 1-2 word call-to-action, SKILL §1.5)")
    invented = [t for t in line_strings(d.get("text", "none")) if re.search(r"\d", t) and t not in skeleton]
    if invented:
        raise SystemExit(f"brief.py: {sxx}: {', '.join(map(repr, invented))} carries a figure the page copy does not "
                         "give (a percentage, price or date); picture text never invents one (SKILL §1.5)")
    fam_block, stands_in = family_block(family)
    if never_generated(fam_block):
        raise SystemExit(f"brief.py: {sxx}: {family} is never generated (its **Never:** line): keep the source "
                         "asset, or restyle the slot to a family whose look it really has")
    records = slot_records(block)
    cls = slot_class(section_type, records[0]) if records else section_type

    slots_meta = json.loads((run / "slots.json").read_text())["slots"]
    exclude_ids = sorted(blindcheck.identifiers(slots_meta))
    query = headline_and_body(block)

    dry = "yes" if (fm.get("budget") or {}).get("dry_run") or _dry(run) else "no"
    budget = (fm.get("budget") or {})
    is_video = section_type_is_video(records)
    kind = "video" if is_video else "image"
    timelined = is_video and (d.get("motion") or "").strip().startswith("timeline")
    board_kind = "timeline" if timelined else kind
    chrome = d.get("chrome", "none")
    labels = line_strings(chrome)
    facts = page_facts(records, fm, block, labels, skeleton)
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
    parts.append("## Generation mode\n")
    parts.append(mode_section(expected, n_media) + "\n")
    own = {sid: w for sid, w in places.items() if any(r["id"] == sid for r in records)}
    if own:
        parts.append("## Where each image sits\n")
        parts.append(placement_lines(own) + "\n")
    parts.append(f"## Style family: {family}" + (f"/{ground}" if ground != "default" else "") + "\n")
    parts.append(fam_block + "\n")
    parts.append("Signature checklist (the block's **Signature** line):\n" + signature_checklist(fam_block) + "\n")
    parts.append(f"Ground variant: {ground}.")
    if stands_in:
        parts.append(f"Stands in for: {stands_in} (a fallback block is used).")
    parts.append(f"Device: {d.get('device', 'none')}\n")
    parts.append("## Flow board\n")
    parts.append(flow_board(family, device, query) + "\n")
    parts.append(f"**Planned recipe (mandatory).** Write `family: {family}`"
                 + (f" and `kind: {board_kind}`" if is_video else "")
                 + f" on the board and author the whole recipe up front:\n\n{board.recipe_row(family, board_kind)}\n\n"
                 "`lp-flow check` reads `family:` and fails a board that skips a planned node.\n")
    if timelined:
        parts.append(timeline_section(run, sxx, records, d["motion"], labels, facts))
    elif is_video:
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
        at = len(parts)  # the panel table goes here once the plans say which panels are derived
        parts.append(composition)
        # write one composition-<slot>.yaml per composable slot: the machine
        # contract the worker renders (spec-from-plan) and precheck/review read
        preset = _preset(family, device)
        twice = sorted(set(labels) & set(line_strings(d.get("text", "none"))))
        if twice:
            raise SystemExit(f"brief.py: {sxx}: {', '.join(map(repr, twice))} is on both `> text:` and `> chrome:`; "
                             "a string is drawn once, by the model or by the chrome")
        derived = {"style": d.get("style"), "device": d.get("device"), "text": d.get("text", "none"), "chrome": chrome}
        (run / "sections" / sxx).mkdir(parents=True, exist_ok=True)
        names = []
        plans = {}
        # a pill pair (one picture per slot, Before | After): each slot takes its own state string
        paired = preset == "pill" and len(to_compose) == 2 and len(labels) == 2
        for i, s in enumerate(to_compose):
            own = [labels[i]] if paired else labels
            pair = to_compose[1 - i]["id"] if paired else None
            if chrome.startswith("TODO"):
                raise SystemExit(f"brief.py: {sxx} has no resolved `> chrome:` line yet: the strings the chrome may "
                                 "say beyond the page copy (a picker's model, the Before | After of a pill pair), or none")
            fit = (lambda w, h, p=preset: compose_cli.fits(compose_cli.template(family, p), w, h)) if family in FAMILIES else None
            tmpl = compose_cli.template(family, preset) if family in FAMILIES else {}
            aspects = tmpl.get("aspects") or ((tmpl["aspect"],) if tmpl else ())
            if not facts.get("degrade") and (m := DEGRADE_RE.search(d.get("device") or "")):
                facts = {**facts, "degrade": m.group(1)}  # the device names the fault when the page's tool does not
            cp = plan.build(family, render_size(s, fit, aspects), preset=preset, labels=own or None, section=section_type,
                            ground=(ground if ground != "default" else None), slot=s["id"], derived_from=derived,
                            facts=facts, pair=pair)
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
            plans[s["id"]] = cp
        parts[at] = composition_section(family, device, sizes=[(s["id"], s.get("size")) for s in to_compose],
                                        section=section_type, plans=plans)
        if not blind:  # the layout check reads the original; a blind brief never does
            parts.append(layout_check(run, sxx, family, to_compose, plans))
        parts.append(blocks_section(plans))
        parts.append(f"A composition plan is written per slot ({', '.join(names)}). Pick the blocks, generate the "
                     f"panels above, then `uv run lp-compose --spec-from-plan <plan> --blocks blocks-<slot>.yaml "
                     f"--image <panel>=<path> ... --out compose-<slot>.yaml` to make the compose spec.\n")
    attribution = model_attribution(run, sxx, records, fm, locals().get("plans") or {})
    if attribution:
        parts.append(attribution)
    parts.append("## Examples from the corpus (same section type)\n")
    parts.append(run_similar(run, sxx, section_type, family, fm.get("page", ""),
                             exclude_ids, query, pool, seed, widen, kind if is_video else None) + "\n")
    parts.append("## References\n")
    parts.append(references_section(family, cls) + "\n")
    parts.append("Build the photo prompt from this genre; the section copy gives the subject matter.\n")
    parts.append("## Shared context\n")
    shared = run / "shared-context.md"
    parts.append((shared.read_text().strip() if shared.exists() else "none yet: you are the hero") + "\n")
    run_cap = json.loads((run / "budget.json").read_text()).get("run_credits") if (run / "budget.json").exists() else None
    if run_cap is not None and run_cap < cap:  # the credit guard enforces budget.json, not the skeleton's advisory figure
        cap = run_cap
    parts.append("## Budget\n")
    parts.append(f"Cap for this section: {cap} credits (the credit guard denies a call past it). Plan the whole "
                 "board within it, preflight every paid step, and if the quoted total exceeds the cap, stop and report.\n")
    parts.append("## Output contract\n")
    parts.append("See output-contract.md.\n")
    parts.append((HERE / "output-contract.md").read_text().strip() + "\n")
    return "\n".join(parts)


def layout_check(run, sxx, family, slots, plans):
    """Each slot's layout against its own original's reading, before anything
    is spent: the warnings go in the brief and on stdout for the manager, and a
    sheet (original | skeleton) goes beside the plan."""
    rows = ["## Layout check", "",
            "Each slot's layout measured against its own original (`compose/fitcheck.py`), beside it in "
            "`layout-check-<slot>.png`. A warning is resolved by the manager before the worker starts.", ""]
    for s in slots:
        preset = plans[s["id"]].get("preset")
        tmpl = compose_cli.template(family, preset)
        reading = readings.load(attrs.asset_id(s["src"])) if s.get("src") else None
        warn = fitcheck.check(tmpl, reading)
        own = families.induced_for(attrs.asset_id(s["src"])) if warn and s.get("src") else None
        if own and (own[0], own[1]) != (family, preset):
            left = fitcheck.check(compose_cli.template(*own), reading)
            warn.append(f"this slot's own measured layout is {own[0]}/{own[1]}"
                        + (f" ({'; '.join(left)})" if left else ", which fits it"))
        if s.get("local") and Path(s["local"]).exists():
            fitcheck.sheet(s["local"], compose_cli.skeleton_image(family, preset),
                           run / "sections" / sxx / f"layout-check-{s['id']}.png")
        for w in warn:
            print(f"brief.py: {sxx} {s['id']} ({preset or 'default'}): {w}")
        rows.append(f"- {s['id']} ({preset or 'default'}): " + ("; ".join(warn) if warn else "fits its original"))
    return "\n".join(rows) + "\n"


TEXT_RULES = """Only when the family's **Use** allows picture text (a design, a poster, a template headline); otherwise `text: none`:
- a headline of 1 to 3 words: a marketing fragment this section implies (a promotion, an event, a season, a product the copy names), not the H2 itself and never the HTML copy beside the image;
- at most one call-to-action of 1 to 2 words, from the section's link text when it has one;
- at most 2 strings in all; ordinary words in the page's language; no brand, model or people's names, no invented figures (percentages, prices, dates the copy does not give).
brief.py refuses a proposal with more than 2 strings."""


def proposal_brief(run, sxx, block, section_type, fm, slots, expected=None, n_media=1, places=None):
    """Phase 1 of a blind brief: context only, no line read off the original.
    The worker decides what each slot should be and writes proposal-<slot>.yaml;
    the manager then re-runs brief.py --blind for the full brief built from it."""
    priors = slot_priors(block)
    slots_meta = json.loads((run / "slots.json").read_text())["slots"]
    exclude_ids = sorted(blindcheck.identifiers(slots_meta))
    records = [r for r in slot_records(block) if r["id"] in slots]
    kind = "video" if section_type_is_video(records) else None
    parts = [f"# Proposal brief: {sxx} {section_type} (blind)\n",
             f"Run: {run.name}. Work only inside this folder. You have not seen, and will not see, the image this slot "
             "had on the live page. Decide from the context below what the slot should show and how, as the page's "
             "designer would, and write your decision; nothing is generated in this phase.\n",
             "## Page context\n",
             yaml.safe_dump({k: fm.get(k) for k in ("page", "brand", "audience", "defaults") if k in fm},
                            sort_keys=False, allow_unicode=True).rstrip() + "\n",
             "## Section (copy and slot geometry)\n", strip_asset_lines(block) + "\n"]
    placement = placement_section(read_skeleton(run), sxx, section_type, fm, priors)
    if placement:
        parts += ["## Where this section sits\n", placement + "\n"]
    own = {sid: w for sid, w in (places or {}).items() if sid in slots}
    if own:
        parts += ["## Where each image sits\n", "The card or heading each image belongs to: the picture shows what "
                  "that card is about.\n", placement_lines(own) + "\n"]
    if expected:
        parts += ["## Generation mode (binding)\n", mode_section(expected, n_media) + "\n"]
    fit_lines = [f"- {r['id']} ({r['size']}): " + ", ".join(f"`{f}`" for f in families_that_fit(r["size"]))
                 for r in records if r.get("size")]
    if fit_lines:
        parts += ["## Families with a layout at each slot's size\n", "A family missing here has no layout at this "
                  "aspect; brief.py refuses it.\n", "\n".join(fit_lines) + "\n"]
    for r in records:
        if not r.get("size"):
            continue
        allowed = [f for f in families_that_fit(r["size"]) if expected is None or genmode.fits(expected, f)
                   or genmode.fits(expected, f, "x")]
        menu = layouts_menu(r["size"], allowed, page_facts([r], fm, block, [], read_skeleton(run)))
        if menu:
            parts += [f"## Layouts for {r['id']} ({r['size']})\n",
                      "A composite's layout is its device: choose the one whose panels and slots show what you "
                      "propose (a set of variants needs several design panels; a prompt box needs a slot that takes "
                      "`action`) and name it first on the device line, `device: \"<layout>: <claim>\"` "
                      "(`default` for the family's own), and set `style:` to the family it is listed under (a layout "
                      "renders only in its own family). A layout's panels are all generated; its slots take bank "
                      "blocks only.\n", menu + "\n"]
    parts += ["## Text in the picture (rules)\n", TEXT_RULES + "\n"]
    parts += ["## Style families (choose one per slot)\n",
              "The `> prior:` line under each slot says how often each family is used in this context across the "
              "corpus (other pages); it is a shortlist, not a pick. The full blocks are in "
              "`.claude/skills/picsart-workflows/style-families.md`.\n", families_menu() + "\n",
              "## Examples from other pages (same section type)\n",
              run_similar(run, sxx, section_type, None, fm.get("page", ""), exclude_ids, headline_and_body(block),
                          0, None, 0, kind) + "\n"]
    shared = run / "shared-context.md"
    if shared.exists():
        parts += ["## Shared context\n", shared.read_text().strip() + "\n"]
    parts += ["## Your decision\n",
              "Write one `proposal-<slot>.yaml` per slot below, then stop:\n",
              "```yaml\nstyle: <family>[/<ground variant>]\n"
              "device: \"<none | the layout you chose>: <the claim the picture demonstrates>\"\n"
              "annotation: <what the picture shows: subject, setting, light, finish>\n"
              "text: none | \"<exact string>\" | ...   # only strings the family's Text line allows\n"
              "chrome: none | <strings the chrome may say beyond the page copy>\n"
              "mode: <only to leave the allowed modes: '<mode> because <the copy that demands it>'>\n"
              "because: <one or two sentences: which copy, prior and examples led here>\n```\n",
              "Slots: " + ", ".join(f"`{i}`" for i in slots) + ".\n"]
    return "\n".join(parts)


def read_skeleton(run):
    return (Path(run) / "skeleton.md").read_text()


def source_page(record, fm):
    """The corpus page a slot comes from: its `local:` path, else the run's page."""
    m = re.match(r"corpus/pages/([^/]+)/", str(record.get("local") or ""))
    return m.group(1) if m else fm.get("page", "")


def model_attribution(run, sxx, records, fm, plans):
    """Write made-by.yaml for the section — the model each generated panel must
    come from because its page or its chrome presents it as that model's output
    (`compose.models.made_by`) — and brief it. Stops when a panel cannot be
    generated truthfully (a model the connector lacks, or an unmapped slug)."""
    required = {}
    for s in records:
        if s.get("role") not in GENERATED_ROLES:
            continue
        cp = plans.get(s["id"])
        req = models.made_by(source_page(s, fm), cp and cp["family"], cp and cp.get("preset"),
                             (cp or {}).get("items") or (), plan.claimed_panels(cp) if cp else ["*"])
        if req:
            required[s["id"]] = req
    path = run / "sections" / sxx / "made-by.yaml"
    if not required:
        if path.exists():
            path.unlink()
        return ""
    bad = [f"{sid} {p}: {r['model'][3:].strip()}" for sid, req in required.items()
           for p, r in req.items() if r["model"].startswith("no:")]
    if bad:
        raise SystemExit(f"brief.py: {sxx} cannot be generated truthfully: " + "; ".join(bad)
                         + ". Keep the original asset for this slot or drop the attribution (the page, the picker's model).")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(required, sort_keys=False))
    rows = ["## Model attribution", "",
            "This page presents these pictures as a named model's output, so they are made on that model "
            "(`made-by.yaml`; `lp-flow check` refuses any generate, edit or background node upstream of them on "
            "another model, refine passes included). Mark each panel's final node `panel: <name>`.", "",
            "| slot | panel | model | because |", "|---|---|---|---|"]
    rows += [f"| {sid} | {p} | `{r['model']}` | {r['because']} |" for sid, req in required.items() for p, r in req.items()]
    kind = {m.get("id"): m["kind"] for m in models.catalogue()["models"] if m.get("id")}
    stills = {s["id"] for s in records if s.get("kind") == "image"}
    video_made = sorted({r["model"] for sid, req in required.items() if sid in stills for r in req.values()
                         if kind.get(r["model"]) == "video"})
    for m in video_made:  # an image model's still would claim to be this model's: caught here, not by lp-flow check after the spend
        print(f"brief.py: {sxx}: still(s) attributed to {m}, a video model: each is a frame of a {m} clip; quote the clip first")
        rows += ["", f"**{m} makes video only.** Each still attributed to it is a frame of a `{m}` clip "
                 "(`lp-corpus frames` grabs it); quote that clip before any other node, and stop and report if "
                 "the section cap cannot cover it. An image model's picture here would claim to be this model's."]
    return "\n".join(rows) + "\n"


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
    p.add_argument("--slot", help="brief this one slot of the section (the others stay kept from source)")
    p.add_argument("--blind", action="store_true",
                   help="no line read off the original: first a proposal brief (the worker picks family, device, "
                        "subject, text, chrome from context), then, once proposal-<slot>.yaml exists, the full brief from it")
    p.add_argument("--replan", action="store_true",
                   help="rebuild the section's composition plans even when they exist (drops hand edits)")
    a = p.parse_args(argv)

    text = assemble(a.run, a.section, pool=a.pool, seed=a.seed, widen=a.widen, replan=a.replan, slot=a.slot, blind=a.blind)
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
