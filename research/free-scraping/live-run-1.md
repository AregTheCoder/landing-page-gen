# Pool live run 1 — cinematic-still (2026-09-16)

First live sweep of the stock pool, end to end: search → sheets → agent review
→ merge → calibrate. Everything below is on disk; nothing is committed.

## Result

| | |
|---|---|
| API requests | 6 (re-run: 0, all cache hits) |
| Candidates | 476 results → 474 admitted (2 prefiltered) |
| Corpus near-dups dropped | 23 (Pexels photos that ARE Picsart source images) |
| Sheets | 36 × 12 cells, reviewed by 36 agents |
| Kept / dropped | 253 / 135, plus 86 moved to other families |
| Thumbs | 76 MB (`corpus/pool/thumbs/`, gitignored) |
| Cost | 0 credits, $0 |

## The ranker barely works — AUC 0.596

363 labels, keep rate 0.697. Threshold 0.221 at 95% recall skips only **7.2%**
of the pile (design assumed ~50%). Top decile (0.9–1.0) keeps at 0.63, *below*
the 0.697 base rate; precision@12 is 0.583, also below base. CLIP scores "same
kind of photograph" well and "has the family's look" barely at all — the
highest scorer in the family was a black-and-white portrait, which reviewers
drop automatically.

**Recommendation: keep the score as a sort order, retire it as a filter.**

## Terms are 2× more predictive than the score

| keep rate | term |
|---|---|
| 0.91 | teal orange portrait moody |
| 0.78 | cinematic portrait vertical |
| 0.78 | golden hour portrait film |
| 0.75 | colorful food photography blue background |
| 0.51 | neon pink bedroom portrait |
| 0.42 | surreal miniature photography |

Failure modes reviewers found: `surreal miniature` returns toy/prop macros
(wrong genre); `neon pink bedroom` pulls bedroom lifestyle + neon *signage*
(text in frame) + boudoir/nudity; `golden hour ... film` pulls film-stock
emulation with KODAK PORTRA sprocket borders; `cinematic portrait vertical`
pulls black-and-white.

Editing these six strings in `corpus/references/cinematic-still.yaml` would
raise yield more than any ranker tuning. Terms belong to `/collect-references`.

## Bugs found and fixed (all with regression tests; 168 tests green)

1. **Span collapse.** `clip_part = (sim-bg)/(self-bg)`; span was 0.011 for
   outcome-tile (16 assets) and 0.029 for full-bleed (630, so broad it IS the
   background). Saturated everything to 1.0 → 219 portraits dumped into
   outcome-tile. Fix: floor the divisor at `SPAN_MIN=0.05`; a family below it
   cannot RECEIVE a reallocation (`ClipRanker.reliable`).
2. **Embed cache thrashing.** Cache keyed by `asset_id`, which is not unique
   (renditions share it): 1852 rows / 1785 ids → 67 re-embedded every run.
   Fix: `corpus_rows` emits one row per asset id.
3. **Per-creator flooding.** One shoot filled 8 of 12 cells on a sheet; pHash
   passes them (genuinely different frames) but they score alike. Fix:
   `MAX_PER_CREATOR=3` per pass.
4. **YAML answer format.** 19% of answer files broke: `#10` in a note starts a
   comment and eats the closing `}`; a comma silently truncates the note and
   invents a junk key. Fix: block-form/quoted guidance in the prompt, unknown
   keys rejected, and `ingest_labels` no longer dies on one bad file.
5. Also: `best_family` reported only for reliable families; sheets README
   wording; ledger no longer created before the key check.

## Things reviewers catch that no score can

Brand safety: smoking, nudity/boudoir, visible brands (Starbucks, VW roundel),
legible text ("NO MERCY", neon signs), a licensed cartoon figurine. Argues for
keeping the human/agent sheet pass rather than auto-accepting the top.

## Open

- **Nothing is committed.** `corpus/pool/` and the new modules are untracked.
- 86 entries moved to other families are pending on their sheets.
- `cinematic-still` corpus tags are noisy (anchors included a traffic light, a
  bowl of noodles, a marketing card with text) — the rule table catches any
  `photo-full-bleed + 9:16 + gallery/hero`. Weak target by construction.
- `--limit-per-term 30` gave 474 not ~180: the cap ends a term after a full
  page is admitted rather than truncating the page.
- Other families never swept; video still phase 2.
