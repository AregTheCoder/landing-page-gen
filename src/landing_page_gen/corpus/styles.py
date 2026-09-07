"""Style families for corpus media: which composite-card family of
`.claude/skills/picsart-workflows/style-families.md` an existing Picsart
image belongs to. Tags live in corpus/styles.yaml keyed by CDN src (stable
across re-fetch and re-index) and are mirrored into media.style, which is
what `similar --style` prefers and `skeleton` pre-fills. `lp-corpus styles
--from-attrs` derives the yaml from corpus/attributes.yaml through the rule
table; `apply` re-mirrors the yaml after any re-index."""

from pathlib import Path

import yaml

STYLES_YAML = Path("corpus/styles.yaml")
DOC = Path(__file__).resolve().parents[3] / ".claude" / "skills" / "picsart-workflows" / "style-families.md"


def load(path=STYLES_YAML):
    path = Path(path)
    return (yaml.safe_load(path.read_text()) or {}) if path.exists() else {}


def save(mapping, path=STYLES_YAML):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(dict(sorted(mapping.items())), sort_keys=False, allow_unicode=True, width=1000))


def apply(con, mapping):
    """Mirror the yaml into media.style; returns the number of rows set."""
    before = con.total_changes
    con.executemany("UPDATE media SET style = ? WHERE src = ?", [(v["style"], src) for src, v in mapping.items()])
    con.commit()
    return con.total_changes - before


def guide():
    """The labeller's family reference: the doc's preamble plus every family's
    Use, Ground and Chrome lines, read at run time so the doc stays the one
    source of truth."""
    lines = DOC.read_text().splitlines()
    out, in_block = [], False
    for line in lines:
        if line.startswith("## "):
            in_block = True
            out.append(line)
        elif not in_block or line.startswith(("**Use:**", "**Signature:**", "**Ground:**", "**Chrome")):
            out.append(line)
    return "\n".join(out) + "\n\nName the closest family id, or other."


def derive(attrs_mapping, existing):
    """styles.yaml from attributes.yaml through the rule table: every tagged
    asset that resolves to a family gets `source: rules`; entries that a human
    wrote (`source: manual`, or no source at all, the legacy shape) are kept."""
    from . import taxonomy
    out = {src: v for src, v in existing.items() if v.get("source", "manual") == "manual"}
    for src, rec in attrs_mapping.items():
        if src in out:
            continue
        style, variant = taxonomy.family_of(rec)
        if style is None:
            continue
        out[src] = {"style": style, "variant": variant, "confidence": round(float(rec.get("confidence") or 0), 2),
                    "page": rec.get("page"), "slot": rec.get("slot"), "source": "rules"}
    return out
