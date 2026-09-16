"""What the reviewers' keep/drop answers say about the ranker.

The sheet pass is the expensive half of the pool (agent tokens, one cell at a
time), so the answers it produces are worth reading back: which score bands
actually keep, which search terms never do, and where the auto-drop threshold
can sit without losing a photo a reviewer would have kept. `pool calibrate`
writes `corpus/pool/_calibration.yaml`; `search` reads the threshold (to skip
sheeting the bottom of the pile) and the per-term keep rates (to decide which
terms are worth a second page).

This module holds the accessors; `calibrate()` and `family_check()` — the
analysis that writes the file — land with the ranker they measure."""

import datetime
from collections import Counter
from pathlib import Path

import numpy as np
import yaml

CALIBRATION_YAML = Path("corpus/pool/_calibration.yaml")
MIN_LABELS = 30        # per family, below which the ranker's global threshold applies
TARGET_RECALL = 0.95   # a threshold may not cost more than 5% of what reviewers kept
PRUNE_MIN = 20         # a term is only judged once it has been seen this often
PRUNE_KEEP_RATE = 0.1


def load(path=CALIBRATION_YAML):
    path = Path(path)
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}


def threshold_for(cal, ranker, family):
    """The score below which a candidate is not worth a sheet cell: the
    family's own threshold once it has enough labels, else the ranker's
    global one, else None (sheet everything)."""
    block = ((cal or {}).get("rankers") or {}).get(ranker) or {}
    fam = (block.get("families") or {}).get(family) or {}
    if fam.get("threshold") is not None:
        return fam["threshold"]
    return block.get("threshold")


def keep_rate_for(cal, ranker, family, term):
    """How often this term's candidates survived review, or None if it has
    never been judged — which `search` reads as 'worth one more page'."""
    block = ((cal or {}).get("rankers") or {}).get(ranker) or {}
    terms = (block.get("terms") or {}).get(family) or {}
    rec = terms.get(term)
    if not rec:
        return None
    return rec.get("keep_rate")


def labelled(entries):
    """The judged set: an entry a reviewer actually saw and answered. Auto
    drops and duplicate drops never reached a sheet, so counting them would
    measure the threshold rather than the ranker."""
    out = []
    for eid, e in entries.items():
        if not e.get("sheet") or e.get("state") not in ("kept", "dropped"):
            continue
        if e.get("drop") and "sheet answer" not in e["drop"]:
            continue  # dropped by dedupe or threshold, not by a reviewer
        out.append((eid, e))
    return out


def deciles(rows, bands=10):
    """How often each score band was kept: the shape the threshold reads."""
    out = []
    for i in range(bands):
        lo, hi = i / bands, (i + 1) / bands
        band = [k for sc, k in rows if (lo <= sc < hi or (i == bands - 1 and sc >= hi))]
        out.append({"lo": round(lo, 2), "hi": round(hi, 2), "n": len(band), "kept": sum(band)})
    return out


def threshold_at_recall(rows, target=TARGET_RECALL):
    """The highest score we can drop below while still keeping `target` of
    what the reviewers kept. None when nothing was kept."""
    total_kept = sum(k for _, k in rows)
    if not total_kept:
        return None, None, None
    best = (None, 1.0, 0.0)
    for edge in sorted({sc for sc, _ in rows}):
        kept_above = sum(k for sc, k in rows if sc >= edge)
        recall = kept_above / total_kept
        if recall < target:
            break
        skipped = sum(1 for sc, _ in rows if sc < edge) / len(rows)
        best = (edge, recall, skipped)
    return best


def auc(rows):
    """Probability a kept candidate outranks a dropped one (0.5 = no signal)."""
    kept = [sc for sc, k in rows if k]
    dropped = [sc for sc, k in rows if not k]
    if not kept or not dropped:
        return None
    wins = sum((a > b) + 0.5 * (a == b) for a in kept for b in dropped)
    return round(wins / (len(kept) * len(dropped)), 3)


def precision_at(rows, ks=(12, 24, 48)):
    ordered = [k for _, k in sorted(rows, key=lambda r: -r[0])]
    return {k: round(sum(ordered[:k]) / min(k, len(ordered)), 3) for k in ks if ordered}


def summarise(rows):
    total = len(rows)
    kept = sum(k for _, k in rows)
    edge, recall, skipped = threshold_at_recall(rows)
    return {"labels": total, "keep_rate": round(kept / total, 3) if total else 0.0,
            "auc": auc(rows), "precision_at": precision_at(rows),
            "deciles": deciles(rows), "threshold": edge,
            "threshold_recall": round(recall, 3) if recall is not None else None,
            "would_skip": round(skipped, 3) if skipped is not None else None}


def calibrate(families, min_labels=MIN_LABELS, target_recall=TARGET_RECALL, today=None):
    """{family: entries} -> the calibration block. Per ranker, because a
    threshold set on histogram scores means nothing to the clip ranker."""
    by_ranker = {}
    for family, entries in families.items():
        for eid, e in labelled(entries):
            name = e.get("ranker") or "histogram"
            block = by_ranker.setdefault(name, {"rows": [], "families": {}, "terms": {}, "platforms": {}})
            keep = int(e["state"] == "kept")
            row = (float(e.get("score") or 0.0), keep)
            block["rows"].append(row)
            block["families"].setdefault(family, []).append(row)
            block["terms"].setdefault(family, {}).setdefault(e.get("term") or "", []).append(keep)
            block["platforms"].setdefault(e.get("platform") or "", []).append(keep)
    out = {}
    for name, block in by_ranker.items():
        rec = summarise(block["rows"])
        rec["families"] = {}
        for family, rows in sorted(block["families"].items()):
            fam = summarise(rows)
            # a family with too few answers borrows the ranker's global threshold
            rec["families"][family] = {"labels": fam["labels"], "keep_rate": fam["keep_rate"],
                                       "auc": fam["auc"],
                                       "threshold": fam["threshold"] if fam["labels"] >= min_labels else None}
        rec["terms"] = {}
        for family, terms in sorted(block["terms"].items()):
            rec["terms"][family] = {}
            for term, keeps in sorted(terms.items()):
                n, kept = len(keeps), sum(keeps)
                rate = round(kept / n, 3)
                entry = {"n": n, "kept": kept, "keep_rate": rate}
                if n >= PRUNE_MIN and rate < PRUNE_KEEP_RATE:
                    entry["prune"] = True  # reported only: the terms belong to /collect-references
                rec["terms"][family][term] = entry
        rec["platforms"] = {pf: {"n": len(k), "keep_rate": round(sum(k) / len(k), 3)}
                            for pf, k in sorted(block["platforms"].items()) if k}
        out[name] = rec
    return {"generated": today or datetime.date.today().isoformat(),
            "min_labels": min_labels, "target_recall": target_recall, "rankers": out}


def family_check(emb, hints=None, k=5):
    """The non-circular check: leave one corpus asset out, ask the embedding
    which family it looks like, and compare that to the tag and to the
    labellers' independent `family_hint`.

    The two photo families are reported merged as well, because the hint
    calls every vertical `full-bleed` — without that column the check indicts
    the hint's error as if it were the ranker's."""
    vectors, families, ids = emb.vectors, emb.families, emb.ids
    if len(vectors) < 2:
        return {}
    sims = vectors @ vectors.T
    np.fill_diagonal(sims, -1.0)
    photo = {"full-bleed", "cinematic-still"}
    agree = agree_merged = agree_hint = hint_agree = 0
    hinted = hint_total = 0
    confusion = {}
    for i, tag in enumerate(families):
        scores = {}
        for fam in {f for f in families if f}:
            idx = np.flatnonzero(families == fam)
            own = np.sort(sims[i, idx])[-min(k, len(idx)):]
            scores[fam] = float(own.mean())
        guess = max(scores, key=scores.get)
        confusion.setdefault(tag, Counter())[guess] += 1
        agree += guess == tag
        agree_merged += (guess == tag) or ({guess, tag} <= photo)
        hint = (hints or {}).get(ids[i])
        if hint:
            hint_total += 1
            agree_hint += guess == hint
            hint_agree += hint == tag
            hinted += 1
    n = len(vectors)
    return {"method": f"leave-one-out top-{k} nearest cluster over the corpus embeddings",
            "n": n,
            "argmax_vs_tag": round(agree / n, 3),
            "argmax_vs_tag_merged_photo": round(agree_merged / n, 3),
            "argmax_vs_hint": round(agree_hint / hint_total, 3) if hint_total else None,
            "hint_vs_tag": round(hint_agree / hinted, 3) if hinted else None,
            "confusion": {t: dict(c.most_common(4)) for t, c in sorted(confusion.items())}}


def save(data, path=CALIBRATION_YAML):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=1000))
    return path
