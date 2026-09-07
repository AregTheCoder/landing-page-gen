---
name: label-corpus
description: Fill the semantic attribute fields of the corpus assets from the labelling contact sheets, in parallel, with no vision API. Invoke as /label-corpus [--sheets N] [--skip-resolved].
disable-model-invocation: true
---

# label-corpus

You label Picsart corpus assets by looking at contact sheets yourself. There
is no vision API in this pipeline: `lp-corpus attrs` measures what the pixels
can say, this procedure answers the rest, and `taxonomy.family_of` turns the
finished records into style families.

Arguments: `$ARGUMENTS` = optional `--sheets N` (how many sheets to do this
pass, default 8) and `--skip-resolved` (leave out assets the measured fields
alone already place in a family).

## 1. Build the sheets

```
uv run lp-corpus attrs                      # only if corpus/attributes.yaml is missing or stale
uv run lp-corpus sheets [--skip-resolved]   # -> corpus/labels/*.png + *.yaml + README.md
```

Read `corpus/labels/README.md` once: it carries the field definitions, the
family reference and the answer format. Pick the first N sheets that have no
`.answers.yaml` yet.

## 2. Fan out, one subagent per sheet

Spawn the subagents in a single message, at most 8 at a time. Give each one
exactly this task, with `<sheet>` filled in:

> Label one contact sheet of Picsart landing-page assets.
> 1. Read `corpus/labels/README.md` (the field definitions, the families and
>    the answer format) and `corpus/labels/<sheet>.yaml` (the manifest: what
>    is already known about each numbered cell, and the `fields` list you
>    have to answer).
> 2. Read `corpus/labels/<sheet>.png`. Cells are numbered `#1`, `#2`, ...
>    left to right, top to bottom.
> 3. Write `corpus/labels/<sheet>.answers.yaml`: one block per cell number,
>    only the fields the manifest asks for, only values from the enums.
>    Leave a cell out entirely if the thumbnail cannot settle it — a guess
>    costs more than a gap, because the rule table trusts the vocabulary.
> Report the cells you answered, the cells you left out and why, and any
> value you wanted but the vocabulary does not have.

Do not label the sheets yourself while subagents are running on them.

## 3. Merge and check

```
uv run lp-corpus labels          # validates, merges, mirrors into media.attrs/style
uv run lp-corpus taxonomy --out corpus/taxonomy
uv run lp-corpus styles --from-attrs
```

`labels` exits 1 and prints every rejected value; a rejected cell is never
written. Fix the answers file (or the vocabulary, see below) and run it again
— merging is idempotent.

Then read `corpus/taxonomy/report.md` and check two things:

- **Unresolved list.** Assets with a complete record and no family mean the
  rule table has a gap. Report the pattern; do not invent a family.
- **Rules-vs-hint matrix.** Where the labellers' `family_hint` disagrees with
  `family_of`, the rule table and the eye disagree. Report the cases with
  their asset ids. Changing `taxonomy.family_of` or the vocabulary is a
  decision for `plan.md`, not a fix to slip into a labelling pass.

## Rules

- A value outside an enum is not a label. If several assets need a word the
  vocabulary lacks, report it — `attrs.FIELDS`, the enums in
  `picsart-workflows/style-families.md` and `tests/test_styles.py` are pinned
  to each other and change together.
- Never edit `corpus/attributes.yaml` by hand; answer sheets and merge.
- Do not run `lp-corpus attrs` while a labelling merge is in flight, and do not
  merge while a measuring pass runs. Each writes only what it produced, so
  nothing is lost, but the run's counts will read stale.
- A cell on flat mid-grey is a transparent cutout: answer `ground` for what
  is baked into the picture, not for the grey the sheet paints behind it.
