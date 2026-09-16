"""Close the loop from a run's outcome back to the corpus data. `lp-bench`
flags a slot `[resemblance]` when the original's family differs from the
generated one; when that original's family is a pixel-only guess (its `chrome`
was never answered), the mismatch may be the DATA's fault, not the worker's —
the measurer reads a black composite card as full-bleed. Such originals are
queued for (re)labelling so `lp-corpus sheets`/`labels` fix them first, instead
of the finding living only as a prose rule."""

import json
import re
from pathlib import Path

import yaml

from . import attrs as attrs_mod

QUEUE_PATH = Path("corpus/labels/_relabel_queue.yaml")
FLAG_RE = re.compile(r"^- (\S+) \(.*?\): family .+ \[resemblance\]$")


def suspect_originals(run_dir, attrs_mapping):
    """Original `src`s a run's benchmark flagged for a family mismatch whose own
    family is provisional (chrome unanswered) — data-suspect, worth relabelling.
    Returns a set of srcs."""
    run_dir = Path(run_dir)
    bench = run_dir / "benchmark.md"
    slots_path = run_dir / "slots.json"
    if not bench.exists() or not slots_path.exists():
        return set()
    slots = (json.loads(slots_path.read_text()) or {}).get("slots", {})
    out = set()
    for line in bench.read_text().splitlines():
        m = FLAG_RE.match(line.strip())
        if not m:
            continue
        src = (slots.get(m.group(1)) or {}).get("src")
        if src and (attrs_mapping.get(src) or {}).get("chrome") is None:
            out.add(src)
    return out


def load_queue(path=QUEUE_PATH):
    path = Path(path)
    return set(yaml.safe_load(path.read_text()) or []) if path.exists() else set()


def enqueue(srcs, path=QUEUE_PATH):
    """Merge srcs into the persistent re-label queue; returns the full queue."""
    path = Path(path)
    merged = sorted(load_queue(path) | set(srcs))
    if merged:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(merged, allow_unicode=True))
    return merged


def from_run(run_dir, attrs_path=None, path=QUEUE_PATH):
    """Read a finished run's benchmark, queue its data-suspect originals, and
    return (queued this run, full queue)."""
    mapping = attrs_mod.load(attrs_path) if attrs_path else attrs_mod.load()
    suspects = suspect_originals(run_dir, mapping)
    return suspects, enqueue(suspects, path)
