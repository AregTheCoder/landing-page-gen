---
name: review-pool
description: Keep or drop the licensed stock candidates of one style family from the pool contact sheets, in parallel, with no vision API, then calibrate the ranker on the answers. Invoke as /review-pool [family] [--sheets N].
disable-model-invocation: true
---

# review-pool

You judge licensed stock photographs by looking at contact sheets yourself.
There is no vision API here either: `lp-corpus pool search` finds and ranks the
candidates, this procedure decides which of them are on-style, and
`lp-corpus pool calibrate` turns those answers into the threshold that stops
the next search from spending your tokens on the same kind of miss.

Arguments: `$ARGUMENTS` = an optional family (one of `db.STYLES`) and
`--sheets N` (how many sheets this pass, default 8).

## 1. Build the sheets

```
uv run lp-corpus pool search <family> --dry-run     # what it would ask for; make sure the budget is there
uv run lp-corpus pool search <family>               # only if you need new candidates
uv run lp-corpus pool sheets <family>               # -> corpus/pool/sheets/*.png + *.yaml + README-<family>.md
```

Read `corpus/pool/sheets/README-<family>.md` once: it carries the family's
photography genre and the answer format. Pick the first N sheets with no
`.answers.yaml` yet.

An entry is stamped with its sheet when the sheet is built and is never
sheeted again, so a second `pool sheets` run offers only what a new search
found. `--resheet` overrides that; use it only when a sheet was lost.

## 2. Fan out, one subagent per sheet

Spawn the subagents in a single message, at most 8 at a time. Give each one
exactly this task, with `<sheet>` and `<family>` filled in:

> Review one contact sheet of licensed stock candidates for a Picsart style family.
> 1. Read `corpus/pool/sheets/README-<family>.md` (the family's photography
>    genre and the answer format) and `corpus/pool/sheets/<sheet>.yaml` (the
>    manifest: the source, score and search term behind each numbered cell).
> 2. Read `corpus/pool/sheets/<sheet>.png`. **Row 1 is three Picsart originals
>    of this family, captioned `ref <id>` — the target, not candidates. Do not
>    judge them.** Numbered cells `#1`, `#2`, ... start on row 2.
> 3. Write `corpus/pool/sheets/<sheet>.answers.yaml`: one line per cell number,
>    `keep` or `drop`, or a mapping with `keep` plus an optional `subject`,
>    `best_family` or `note`.
> Judge the photograph, not the layout: the tiles, pills, panels and badges of
> the family are drawn by `lp-compose` afterwards, so a bare photo is what you
> should be seeing. Keep what a worker could build this family's slot from;
> drop what is off-style, watermarked, text-heavy, or a near-duplicate of
> another cell. If a photo is good but belongs to another family, answer
> `best_family` — it moves there instead of being lost.
> Leave a cell out entirely if the thumbnail cannot settle it.
> Report the cells you kept, dropped, moved and left out, and any search term
> whose candidates were consistently wrong.

> If you crop or zoom part of the sheet to see it better, name the file after
> the sheet (`<sheet>-row4.png`, not `row4.png`): the reviewers share one
> scratchpad and a generic name will be overwritten by a sibling mid-review.

Do not review the sheets yourself while subagents are running on them.

## 3. Merge

```
uv run lp-corpus pool labels <family>   # validates, flips states, moves best_family entries
```

`labels` reports every rejected value and never writes one. It also re-checks
each kept entry against the corpus hashes, because a keep must not smuggle in
a photo that IS one of Picsart's own source images.

## 4. Calibrate

```
uv run lp-corpus pool calibrate <family> --write --family-check
```

Then report:

- **threshold and would_skip** — the score below which the next search stops
  sheeting, and the share of the labelled set that would have been skipped.
  It is set at 95% recall of what you kept, so a rising `would_skip` is the
  ranker earning its place.
- **terms marked `prune: true`** — search terms whose candidates you almost
  never keep. Report them; they live in `corpus/references/<family>.yaml` and
  belong to `/collect-references`, not to this pass.
- **family_check** — how often the ranker's own argmax family agrees with the
  tag, with `family_hint`, and with the two photo families merged. Read the
  merged number first: `family_hint` calls every vertical `full-bleed`, so the
  raw disagreement indicts the hint, not the ranker.

## Rules

- Never edit `corpus/pool/*.yaml` by hand; answer sheets and merge.
- `best_family` takes only a name from `db.STYLES`. A photo that fits no
  family is a `drop`, not a new family.
- Do not run `pool search` while a merge is in flight, and do not merge while
  a search runs. Each writes only what it produced, but the counts will read
  stale.
- A calibrated threshold is only as honest as its exploration slice: 10% of
  below-threshold candidates are sheeted anyway and marked `explored`. Judge
  those exactly as you judge the rest — they are how the threshold stays
  falsifiable.
- The pool is a look reference, never material: nothing here is uploaded,
  passed as `imageUrls`, or injected.
- Keep on the photograph, not on the subject's suitability alone — but a frame
  that could not appear on a Picsart product page (explicit, smoking, branded)
  is a drop whatever its grade, and worth saying so in the `note`.
- Watch for one shoot filling a sheet: several cells from one creator's session
  are near-duplicates and only the best is worth keeping. Report it — a
  per-creator cap in `pool search` is the fix, not more review.
