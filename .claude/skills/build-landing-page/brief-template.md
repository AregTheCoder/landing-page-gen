# Brief template

Written by the manager to `<run>/sections/<Sxx>/brief.md`. Angle brackets are
placeholders; everything else is copied verbatim.

```markdown
# Brief: <Sxx> <type>

Run: <run>. Work only inside this folder. Dry run: <yes|no>.

## Page context

<page frontmatter verbatim: page, brand, audience, defaults, budget, notes>

## Section (verbatim from skeleton.md)

<the whole `## Sxx type` block: text with t: ids, slot blocks, annotations>

## Style family: <style>

<the `## <style>` block from picsart-workflows/style-families.md, verbatim>

You generate only the panels listed under **Panels**, one prompt per panel,
each at the panel's generate ratio (`uv run lp-compose --describe <style>`).
Chrome is composited afterwards by `lp-compose`; never ask a model for it.

## Slots to produce

| slot | kind | role | size | natural | family | panels |
|---|---|---|---|---|---|---|
| <Sxx-m1> | image | creative | 480x480 | 720x720 | <style> | <A photo 3:4> |

Kept from source (do not produce): <list or "none">

## Examples from the corpus (same section type)

<for each of 2-3 examples: page slug, section type, the excerpt markdown,
and the local media paths under examples/>

## Shared context

<contents of <run>/shared-context.md, or "none yet: you are the hero">

Anchored means: take light and palette from the hero. Subject, composition
and finish come from this section's annotation and its examples, never from
the hero's composition.

## Budget

Advisory cap for this section: <n> credits. Run cap is enforced by hook.
Preflight every paid step; if the quoted total exceeds the cap, stop and
report instead of trimming quality silently.

## Output contract

See output-contract.md (copied below).
<contents of output-contract.md>
```
