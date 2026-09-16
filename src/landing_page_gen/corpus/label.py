"""Merging sheet answers back into the attributes.

`lp-corpus labels` reads every `<sheet>.answers.yaml` in the labels folder,
validates each cell against the attribute enums, joins it with the manifest's
measured fields and writes the completed record into attributes.yaml. An
answer that names a value outside an enum is reported and dropped, never
written: the rule table in `taxonomy` assumes the vocabulary holds."""

import datetime
from pathlib import Path

import yaml

from . import attrs, measure, sheets, styles

ANSWER_SUFFIX = ".answers.yaml"

# Fields whose vocabulary was renamed. `ingest` rewrites any record, answers
# file or manifest that still names the old field, idempotently, so a stray
# file (e.g. an orphan answers file with no manifest) is fixed on arrival. A
# value with no mapping is dropped and reported, never silently kept.
RENAMED = {
    "finish": ("art_style", {"photo": "photo", "3d": "3d-render", "flat-illustration": "flat-vector",
                             "collage": "collage", "screenshot": "ui-screenshot", "mixed": "mixed"}),
}


def manifests(out_dir=sheets.LABELS_DIR):
    """Every sheet manifest in the folder, in sheet order."""
    return sorted(p for p in Path(out_dir).glob("*.yaml") if not p.name.endswith(ANSWER_SUFFIX))


def _map_value(old_field, value, stats, where):
    """The renamed field's mapped value, or None (with a report) when dropped."""
    valmap = RENAMED[old_field][1]
    if value in valmap:
        return valmap[value]
    stats["errors"].append(f"{where}: {old_field} value {value!r} has no {RENAMED[old_field][0]} mapping, dropped")
    return None


def migrate_record(rec, stats):
    """Rename any dropped-vocabulary key in a record in place; True if changed."""
    changed = False
    for old_field, (new_field, _) in RENAMED.items():
        if old_field in rec:
            changed = True
            mapped = _map_value(old_field, rec.pop(old_field), stats, f"record {rec.get('page', '?')}/{rec.get('slot', '?')}")
            if mapped is not None:
                rec[new_field] = mapped
            lab = rec.get("labelled")
            if lab:
                rec["labelled"] = sorted({new_field if f == old_field else f for f in lab})
    return changed


def _lead_comments(text):
    """Leading comment/blank lines of a file (safe_dump drops them)."""
    out = []
    for line in text.splitlines(keepends=True):
        if line.strip() and not line.lstrip().startswith("#"):
            break
        out.append(line)
    return "".join(out)


def migrate_files(out_dir, stats):
    """Rewrite every answers file and manifest still naming a renamed field."""
    out_dir = Path(out_dir)
    for path in sorted(out_dir.glob("*" + ANSWER_SUFFIX)):
        raw = path.read_text()
        try:
            data = styles.load_yaml(raw) or {}
        except yaml.YAMLError:
            continue  # ingest reports and skips it
        touched = False
        for cell, answer in data.items():
            if not isinstance(answer, dict):
                continue
            for old_field, (new_field, _) in RENAMED.items():
                if old_field in answer:
                    touched = True
                    mapped = _map_value(old_field, answer.pop(old_field), stats, f"{path.name} cell {cell}")
                    if mapped is not None:
                        answer[new_field] = mapped
        if touched:
            path.write_text(_lead_comments(raw) + styles.dump_yaml(data, sort_keys=False, allow_unicode=True))
            stats["migrated"] += 1
    for path in manifests(out_dir):
        man = styles.load_yaml(path.read_text()) or {}
        fields = man.get("fields") or []
        if any(f in RENAMED for f in fields):
            man["fields"] = sorted({RENAMED[f][0] if f in RENAMED else f for f in fields})
            path.write_text(styles.dump_yaml(man, sort_keys=False, allow_unicode=True))
            stats["migrated"] += 1


def check(field, value):
    """(clean value, error) for one answered field."""
    if field not in attrs.FIELDS:
        return None, f"unknown field {field}"
    spec = attrs.FIELDS[field][0]
    if field == "chrome":
        if isinstance(value, str):
            value = [v.strip() for v in value.split(",") if v.strip()]
        if not isinstance(value, list):
            return None, "chrome must be a list"
        bad = [v for v in value if v not in spec]
        return (None, f"chrome: {', '.join(bad)}") if bad else (sorted(set(value)), None)
    if isinstance(spec, tuple):
        return (value, None) if value in spec else (None, f"{field}: {value!r}")
    if spec == "integer":
        try:
            return max(0, min(8, int(value))), None
        except (TypeError, ValueError):
            return None, f"{field}: {value!r} is not a number"
    if spec == "number":
        try:
            return round(float(value), 2), None
        except (TypeError, ValueError):
            return None, f"{field}: {value!r} is not a number"
    if spec == "boolean":
        return bool(value), None
    return str(value), None


def cell_answer(answer):
    """(clean fields, errors) for one cell's block."""
    clean, errors = {}, []
    for field, value in (answer or {}).items():
        if value is None:
            continue
        ok, err = check(field, value)
        if err:
            errors.append(err)
        else:
            clean[field] = ok
    return clean, errors


def ingest(mapping, out_dir=sheets.LABELS_DIR, log=print):
    """Merge every answered sheet into the mapping in place. Returns
    (mapping, stats)."""
    stats = {"sheets": 0, "answered": 0, "cells": 0, "unknown": 0, "migrated": 0, "errors": []}
    today = datetime.date.today().isoformat()
    migrate_files(out_dir, stats)
    for rec in mapping.values():
        migrate_record(rec, stats)
    for man_path in manifests(out_dir):
        man = styles.load_yaml(man_path.read_text()) or {}
        stats["sheets"] += 1
        answers_path = Path(out_dir) / man.get("answers", man_path.stem + ANSWER_SUFFIX)
        if not answers_path.exists():
            continue
        stats["answered"] += 1
        try:
            answers = styles.load_yaml(answers_path.read_text()) or {}
        except yaml.YAMLError as exc:
            stats["errors"].append(f"{answers_path.name}: unparseable YAML, skipped ({exc.__class__.__name__})")
            continue
        cells = man.get("cells") or {}
        for key, answer in answers.items():
            try:
                n = int(key)
            except (TypeError, ValueError):
                stats["errors"].append(f"{man_path.name} cell {key!r}: not a cell number")
                continue
            info = cells.get(n)
            if info is None:
                stats["errors"].append(f"{man_path.name} cell {n}: not on this sheet")
                continue
            src = info["src"]
            if src not in mapping:
                stats["unknown"] += 1
                stats["errors"].append(f"{man_path.name} cell {n}: {attrs.asset_id(src)} is not in the attributes yaml")
                continue
            clean, errors = cell_answer(answer)
            for err in errors:
                stats["errors"].append(f"{man_path.name} cell {n}: {err}")
            if not clean:
                continue
            rec = mapping[src]
            rec.update(clean)
            rec["labelled"] = sorted(set(rec.get("labelled") or []) | set(clean))
            rec["source"] = "sheet"
            rec["sheet"] = man.get("sheet", man_path.stem)
            rec["at"] = today
            stats["cells"] += 1
    return mapping, stats


def coverage(mapping):
    """{field: share of assets that have an answer}, plus the fully answered
    share, so a labelling pass can be reported without opening the yaml."""
    n = len(mapping) or 1
    fields = list(sheets.SEMANTIC) + list(measure.FIELDS)
    out = {f: round(sum(1 for r in mapping.values() if r.get(f) is not None) / n, 3) for f in fields}
    out["complete"] = round(sum(1 for r in mapping.values()
                                if all(r.get(f) is not None for f in fields)) / n, 3)
    return out
