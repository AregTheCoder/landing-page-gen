"""Style families for corpus media: which composite-card family of
`.claude/skills/picsart-workflows/style-families.md` an existing Picsart
image belongs to. Tags live in corpus/styles.yaml keyed by CDN src (stable
across re-fetch and re-index) and are mirrored into media.style, which is
what `similar --style` prefers and `skeleton` pre-fills. `lp-corpus styles
--from-attrs` derives the yaml from corpus/attributes.yaml through the rule
table; `apply` re-mirrors the yaml after any re-index."""

from pathlib import Path

import yaml

# The libyaml C loader/dumper where PyYAML was built with it (attributes.yaml is
# 2.4 MB and 6-9x slower under the pure-Python parser). Semantically identical to
# the safe loader/dumper; the only round-trip differences are cosmetic (a >128-char
# key loses the `? key` explicit form, non-BMP emoji are \U-escaped).
LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
DUMPER = getattr(yaml, "CSafeDumper", yaml.SafeDumper)


def load_yaml(text):
    return yaml.load(text, Loader=LOADER)


def dump_yaml(data, **kw):
    kw.setdefault("Dumper", DUMPER)
    kw.setdefault("allow_unicode", True)
    return yaml.dump(data, **kw)


STYLES_YAML = Path("corpus/styles.yaml")
DOC = Path(__file__).resolve().parents[3] / ".claude" / "skills" / "picsart-workflows" / "style-families.md"


def load(path=STYLES_YAML):
    path = Path(path)
    return (load_yaml(path.read_text()) or {}) if path.exists() else {}


def save(mapping, path=STYLES_YAML):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_yaml(dict(sorted(mapping.items())), sort_keys=False, width=1000))


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
        entry = {"style": style, "variant": variant, "confidence": round(float(rec.get("confidence") or 0), 2),
                 "page": rec.get("page"), "slot": rec.get("slot"), "source": "rules"}
        # A family inferred from pixels alone (chrome never answered) can be wrong:
        # the measurer reads a black composite card as photo-full-bleed/single and
        # mislabels it full-bleed. Flag it so retrieval and the manager distrust it.
        if rec.get("chrome") is None:
            entry["provisional"] = True
        out[src] = entry
    return out
