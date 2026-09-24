"""The purpose of every labelled chrome block in the corpus.

Derived, never labelled: a block's role (a category of compose/assets/
blocks.yaml) follows from its `chrome_items` kind and text (a pill saying
"Before" is a state label, a model-logo or a pill naming a catalogue model is
attribution, "4K" is a spec, "Generate" an action). Nothing is written back
into attributes.yaml. `report` counts roles per style family and placement,
sets them beside each template slot's `accepts`, so a slot takes the blocks the
corpus puts there, and counts the corpus evidence behind each bank block. The
residual is the blocks whose purpose the kind and text leave open: tiles with
no text, where the tool they show is unknown."""

import re
from collections import Counter, defaultdict

from ..compose import bank, models
from ..compose import cli as compose_cli
from ..compose.families import FAMILIES

STATES = re.compile(r"^(before|after|original|enhanced|old|new|input|output)$", re.I)
SPEC = re.compile(r"^(x\d+|\d+x|\d+k|hd|full hd|\d+p|\d+:\d+|\d+\s?(fps|s|sec)|gif|mp4|png|svg|jpe?g|webm|\d+(\.\d+)?s"
                  r"|\d+ ?(photos?|images?|variations?)|\d{3,4}\s*[x×|]\s*\d{3,4}|\d{3,4})$", re.I)
KIND_ROLE = {
    "model-logo": "attribution", "option-list": "attribution",
    "button": "action", "prompt-panel": "action", "step-chip": "action", "cursor": "action",
    "tile": "tool", "adjust-panel": "tool", "adjust-slider": "tool", "colour-picker": "tool", "toggle": "tool",
    "dropdown": "tool", "tab-row": "tool",
    "mockup-card": "context", "badge": "context",
    "swatch": "derived",
    "vs-badge": "comparison", "compare-handle": "comparison",
    "size-label": "spec", "play-button": "spec", "waveform": "spec", "timeline": "spec", "volume": "spec",
    "progress": "spec",
    "selection-handles": "editor", "brackets": "editor", "crop-grid": "editor", "arrow": "editor", "loupe": "editor",
}


# model families the pages name, hosted or not (DALL-E and Midjourney are advertised, not on the connector)
MODEL_WORDS = re.compile(r"\b(gpt[- ]image|dall-?e|midjourney|flux|recraft|ideogram|imagen|nano banana|seedream|seedance|kling"
                         r"|veo|sora|runway|luma|grok|qwen|wan \d|pixverse|minimax|hailuo|gemini|stable diffusion)\b", re.I)


def _is_model(text):
    return any(models.lookup(t.strip()) or MODEL_WORDS.search(t) for t in str(text).split("|") if t.strip())


def role_of(item):
    """The role of one corpus chrome item {kind, placement, anchor, text}."""
    kind, text = item.get("kind"), str(item.get("text") or "").strip()
    first = text.split("|")[0].strip()
    if kind in ("pill", "chip"):
        if STATES.match(first):
            return "state-label"
        if _is_model(text):
            return "attribution"
        if SPEC.match(first):
            return "spec"
        return "action" if kind == "pill" else "spec"
    if kind == "tile" and _is_model(text):
        return "attribution"  # a tile carrying a model's name is that model's mark
    if kind == "tile" and re.fullmatch(r"(aa|ab|abc|aa bb|ai)( ?(aa|bb))*", text.replace("|", " ").lower() or "-"):
        return "derived"  # a font-pairing tile
    return KIND_ROLE.get(kind, "unknown")


def blocks(mapping, styles=None):
    """(asset, family, item, role) for every labelled chrome item."""
    styles = styles or {}
    for src, rec in mapping.items():
        fam = (styles.get(src) or {}).get("style") or rec.get("family_hint") or "unresolved"
        for it in rec.get("chrome_items") or []:
            yield src, fam, it, role_of(it)


def report(mapping, styles=None):
    """The Markdown report: role counts per family and placement, the corpus
    order of the blocks set beside a picture against each compose zone's
    `accepts`, the commonest texts per role, and the residual."""
    per_fam = defaultdict(Counter)
    placed = defaultdict(Counter)  # (family, beside|overlay) -> roles
    anchors = defaultdict(Counter)
    texts = defaultdict(Counter)
    residual = Counter()
    evidence = {}
    assets = set()
    n = 0
    for src, fam, it, role in blocks(mapping, styles):
        n += 1
        for name in bank.evidence_matches(it, role_of):
            ev = evidence.setdefault(name, {"n": 0, "fam": Counter(), "pages": Counter()})
            ev["n"] += 1
            ev["fam"][fam] += 1
            ev["pages"][(mapping.get(src) or {}).get("page")] += 1
        assets.add(src)
        per_fam[fam][role] += 1
        if it.get("placement"):
            placed[(fam, it["placement"])][role] += 1
        if it.get("anchor"):
            anchors[role][it["anchor"]] += 1
        if it.get("text"):
            texts[role][str(it["text"])[:40]] += 1
        if it.get("kind") == "tile" and not it.get("text") and not it.get("tool"):
            residual["tile with no text (which tool?)"] += 1
        if it.get("kind") == "model-logo" and not it.get("text"):
            residual["model-logo with no text (which model?)"] += 1
        if role == "unknown":
            residual[f"unknown kind {it.get('kind')}"] += 1
    total = Counter()
    for c in per_fam.values():
        total.update(c)
    lines = ["# Block roles in the corpus", "",
             f"{n} chrome blocks on {len(assets)} labelled assets, each given the role its kind and text "
             "settle (`lp-corpus roles`; vocabulary in `compose/assets/roles.yaml`). Derived, never written "
             "into attributes.yaml.", "", "## Roles overall", "", "| role | blocks | share |", "|---|---|---|"]
    lines += [f"| {r} | {c} | {c / n:.0%} |" for r, c in total.most_common()]
    lines += ["", "## Per style family", "", "| family | blocks | roles (commonest first) |", "|---|---|---|"]
    for fam, c in sorted(per_fam.items(), key=lambda kv: -sum(kv[1].values())):
        lines.append(f"| {fam} | {sum(c.values())} | " + ", ".join(f"{r} {k}" for r, k in c.most_common()) + " |")
    lines += ["", "## Slots against the corpus", "",
              "Each template slot's `accepts` next to the roles the corpus places the same way in that family "
              "(`beside` the pictures, or `overlay` on one). A role holding 10 % or more of those blocks that "
              "the slot does not take is listed.", "",
              "| family | layout | slot | shape | where | accepts | corpus (commonest first) | not taken |",
              "|---|---|---|---|---|---|---|---|"]
    for fam in FAMILIES:
        for variant in (None, *(FAMILIES[fam].get("variants") or {})):
            for sl in compose_cli.template(fam, variant)["slots"]:
                where = "overlay" if sl.get("at") or sl["shape"] in ("seam", "panel", "frame", "badge") else "beside"
                c = placed.get((fam, where), Counter())
                n_z = sum(c.values())
                corpus = ", ".join(f"{r} {k}" for r, k in c.most_common(5)) or "—"
                missing = [r for r, k in c.most_common() if r not in sl["accepts"] and n_z and k / n_z >= 0.10]
                lines.append(f"| {fam} | {variant or 'default'} | {sl['id']} | {sl['shape']} | {where} | "
                             f"{', '.join(sl['accepts'])} | {corpus} | {', '.join(missing) or '—'} |")
    lines += ["", "## Bank evidence", "",
              "The corpus blocks each bank block stands for (its `evidence:` kinds and text), the families "
              "they appear in and the pages that show them most. A bank block with no corpus evidence comes "
              "from an unmeasured original.", "",
              "| block | category | corpus blocks | families | pages (commonest first) |", "|---|---|---|---|---|"]
    for name, b in bank.vocab()["blocks"].items():
        ev = evidence.get(name) or {"n": 0, "fam": Counter(), "pages": Counter()}
        lines.append(f"| {name} | {b['category']} | {ev['n']} | "
                     + (", ".join(f"{f} {k}" for f, k in ev["fam"].most_common(3)) or "—") + " | "
                     + (", ".join(f"{pg} {k}" for pg, k in ev["pages"].most_common(4)) or "—") + " |")
    lines += ["", "## Where each role sits", "", "| role | anchors (commonest first) |", "|---|---|"]
    for role, c in sorted(anchors.items()):
        lines.append(f"| {role} | " + ", ".join(f"{a} {k}" for a, k in c.most_common(5)) + " |")
    lines += ["", "## What each role says", "", "| role | commonest texts |", "|---|---|"]
    for role, c in sorted(texts.items()):
        lines.append(f"| {role} | " + "; ".join(f"{t!r} ({k})" for t, k in c.most_common(6)) + " |")
    lines += ["", "## Residual", "",
              "Blocks whose purpose the kind and text leave open. A tile's tool is read from its icon on the "
              "contact sheet; until then a tool block is offered only for the page's own tool "
              "(`roles.yaml pages:`) or one its copy names.", ""]
    lines += [f"- {k}: {v}" for k, v in residual.most_common()] or ["- none"]
    return "\n".join(lines) + "\n", {"blocks": n, "assets": len(assets), "residual": sum(residual.values())}
