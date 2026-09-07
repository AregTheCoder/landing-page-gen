"""Merging sheet answers back into the attributes.

`lp-corpus labels` reads every `<sheet>.answers.yaml` in the labels folder,
validates each cell against the attribute enums, joins it with the manifest's
measured fields and writes the completed record into attributes.yaml. An
answer that names a value outside an enum is reported and dropped, never
written: the rule table in `taxonomy` assumes the vocabulary holds."""

import datetime
from pathlib import Path

import yaml

from . import attrs, measure, sheets

ANSWER_SUFFIX = ".answers.yaml"


def manifests(out_dir=sheets.LABELS_DIR):
    """Every sheet manifest in the folder, in sheet order."""
    return sorted(p for p in Path(out_dir).glob("*.yaml") if not p.name.endswith(ANSWER_SUFFIX))


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
    stats = {"sheets": 0, "answered": 0, "cells": 0, "unknown": 0, "errors": []}
    today = datetime.date.today().isoformat()
    for man_path in manifests(out_dir):
        man = yaml.safe_load(man_path.read_text()) or {}
        stats["sheets"] += 1
        answers_path = Path(out_dir) / man.get("answers", man_path.stem + ANSWER_SUFFIX)
        if not answers_path.exists():
            continue
        stats["answered"] += 1
        answers = yaml.safe_load(answers_path.read_text()) or {}
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
