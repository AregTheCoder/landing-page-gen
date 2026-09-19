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

sys.path.insert(0, str(HERE))
import blindcheck  # noqa: E402
from landing_page_gen.flow import board  # noqa: E402

SLOT_RE = re.compile(r"^```slot\n(.*?)\n```", re.M | re.S)
SECTION_HEAD_RE = re.compile(r"^## (S\d+) ([\w-]+)", re.M)  # types are hyphenated: feature-callout, how-it-works
DIRECTIVE_RE = re.compile(r"^> (annotation|style|attrs|text|device|duration): (.*)$", re.M)
MOTION_LINE_RE = re.compile(r"^\*\*Motion:\*\* (.+)$", re.M)
N_PLACEHOLDER = re.compile(r" \(n=…\)")
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
    return N_PLACEHOLDER.sub("", block), stands_in


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


def slots_table(records, section_type, family, device):
    rows = ["| slot | kind | role | size | natural | class | family | panels |",
            "|---|---|---|---|---|---|---|---|"]
    for s in records:
        cls = slot_class(section_type, s)
        rows.append(f"| {s['id']} | {s.get('kind')} | {s.get('role')} | {s.get('size')} | "
                    f"{s.get('natural', '')} | {cls} | {family} | 1 panel |")
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


def target_duration(record, directive, cap):
    """(target seconds, note): the `> duration:` line's leading number, else the
    slot's own duration_s rounded, else 5; never above budget.video_seconds."""
    m = re.match(r"\s*(\d+(?:\.\d+)?)", directive or "")
    original = record.get("duration_s")
    wanted = round(float(m.group(1))) if m else (round(original) if original else 5)
    wanted = max(4, wanted)
    if cap and wanted > cap:
        return cap, f"original {original} s; capped at budget.video_seconds {cap}: note the shortfall in result.md"
    return wanted, f"original {original} s" if original else "no original length; 5 s default"


def video_section(records, fam_block, fm, directive):
    """The `## Video` paragraph of a video slot's brief: the still-to-motion
    recipe on the run's models, the target duration per slot (faithful to the
    original, `> duration:` overriding, budget.video_seconds capping), the
    family's **Motion:** line and the result keys, per video-workflows.md."""
    defaults, budget = fm.get("defaults") or {}, fm.get("budget") or {}
    draft, final = defaults.get("video_draft", "seedance-2.0-mini"), defaults.get("video_model", "seedance-2.5")
    cap = budget.get("video_seconds", 30)
    m = MOTION_LINE_RE.search(fam_block)
    motion = m.group(1) if m else ("no **Motion:** line for this family yet: prompt slow, subtle subject motion on "
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
        target, note = target_duration(s, directive, cap)
        lines.append(f"  - {s['id']}: **{target} s** ({note})")
    lines += ["- After each clip: `curl` it to `steps/`, then `uv run lp-corpus frames steps/<slot>-<node>-<n>.mp4 "
              "--out steps/<slot>-<node>-strip.png` and `Read` the strip; `picsart_media_probe_media` gives the length. "
              "Write the clip URL into the node's `outputs` the instant `job_status` returns it.",
              "- `result.md`: `chosen:` is the final clip URL, plus `poster:` (the accepted still) and `duration_s:` (measured); "
              "scores add `first_frame`, `motion`, `loop`."]
    return "\n".join(lines)


def headline_and_body(block):
    """The section's headline and first paragraph, as the similar query."""
    texts = re.findall(r"^- t\d+ \w+: (.+?)(?: -> \S+)?$", block, re.M)
    return " ".join(texts[:2]).strip()[:300]


def assemble(run, sxx, pool=0, seed=None, widen=0):
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
    parts.append(strip_asset_lines(block) + "\n")
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
        parts.append(video_section(records, fam_block, fm, d.get("duration")) + "\n")
    parts.append("## Text in image\n")
    parts.append(text_in_image(d.get("text", "none"), records, section_type) + "\n")
    parts.append("## Slots to produce\n")
    parts.append(slots_table(records, section_type, family + (f"/{ground}" if ground != "default" else ""), device) + "\n")
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
    a = p.parse_args(argv)

    text = assemble(a.run, a.section, pool=a.pool, seed=a.seed, widen=a.widen)
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
