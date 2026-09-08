---
name: collect-references
description: Collect external reference examples (stock photography sources and creators on Pexels and Unsplash) for every style family in the corpus, one subagent per family, and write them to corpus/references/<family>.yaml plus a References line in style-families.md. Invoke as /collect-references [family ...] [--pages].
disable-model-invocation: true
---

# collect-references

Picsart's landing-page creatives are stock photographs with compose chrome
laid over them (the hsl-color hero is Pexels 2180474 by R. Fera). A worker
who knows the stock genre a family uses writes a better photo prompt than one
who reads the section copy. This procedure gives every family a set of
external examples that match Picsart's photography the way the corpus
examples match its layout. No paid Picsart calls anywhere in it.

Arguments: `$ARGUMENTS` = optional family ids (default: every family in
`db.STYLES` that has no `corpus/references/<family>.yaml` yet, or whose file
is older than `style-families.md`) and `--pages` (second wave: one subagent
per page with creatives, writing `corpus/pages/<slug>/references.yaml`;
see "Wave 2" below).

## 1. Build the manifest

```
uv run python .claude/skills/collect-references/manifest.py [family ...]   # -> corpus/references/_manifest.yaml + examples/<family>/*.png
```

The manifest lists per family: the doc's Use, Ground, Panels and Text lines,
its example assets converted to PNG (agents view with `Read`, which cannot
open AVIF or WebP), the pages that carry the family and how many assets are
tagged with it. Read `reference-format.md` once: the yaml schema and the
rules every subagent follows.

## 2. Fan out, one subagent per family

Spawn the subagents in one message, all families at once (they only read
the web and write one file each). Use `subagent_type: reference-collector`
when the agent is loaded (it is defined in `.claude/agents/`); in a session
started before that file existed, use `general-purpose` and paste the agent's
Procedure section into the prompt. Give each one exactly this task, with
`<family>` filled in:

> Collect external references for the Picsart style family `<family>`.
> Read `.claude/skills/collect-references/reference-format.md`, then the
> `<family>` entry of `corpus/references/_manifest.yaml`, then open every
> example PNG it lists with `Read`. Find 5 to 10 Pexels or Unsplash photos
> whose photography matches those examples (subject, light, backdrop,
> colour, framing), verify each on its own page, name the creators, and write
> `corpus/references/<family>.yaml` in the format. Report the file, the
> number of examples, and anything you could not find.

Do not collect for a family yourself while its subagent runs.

## 3. Apply and check

```
uv run python .claude/skills/collect-references/apply.py     # validates every yaml, writes the **References:** lines
uv run pytest -q tests/test_styles.py
```

`apply.py` exits 1 and names the file when a yaml is missing a required key,
has fewer than 5 examples, or names a URL that is not on pexels.com or
unsplash.com. It rewrites the `**References:**` line after `**Examples:**`
in each family block of `style-families.md` (the line is the file path, the
creator names and the example count), and nothing else in the doc.

Then read the `prompt_guidance` of each file side by side. Where two families
describe the same genre, say so in `plan.md`; where a family's guidance
contradicts its **Panels (worker)** line, the doc line wins and the yaml is
sent back to a subagent with the conflict quoted.

## Wave 2: pages (`--pages`)

One subagent per page with a `creative` slot, same rules, writing
`corpus/pages/<slug>/references.yaml`: which family each creative really is,
whether the family's chrome is present or absent on this page (hair-color-changer
carries panel-overlay's photography and tilted ground with no panel), and the
stock source of each photo when it can be found. The manager merges the
absent-chrome findings into the family blocks' **Use** lines.

## Rules

- Pexels and Unsplash only: their licences allow the comparison, and their
  photo pages carry creator and description. No downloads in the pass; URLs
  are the deliverable. The manager fetches a file only to put it on a board.
- Every URL comes from a search result or a fetched page, never from memory.
  An example the agent could not open is not an example.
- Subject, light, backdrop, colour and framing decide a match; the chrome and
  the ground are Picsart's and are recorded under `picsart_specific`, never
  searched for.
- `prompt_guidance` is written for a worker's photo prompt: the genre in
  words, what to keep clear for the chrome, what never appears. It must not
  contradict the family's **Panels (worker)** and **Never** lines.
