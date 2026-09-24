# Chrome blocks: skeletons, the bank, and choosing by context

A composite has three layers, and only one of them is a model's:

| layer | what it is | who makes it |
|---|---|---|
| background | the ground (transparent, black, light) and fixed surfaces (the card a design is printed on, the dark card a prompt sits on, a checker behind a cut-out) | lp-compose, from the template |
| panels | the pictures: a *scene* (a whole picture with its own backdrop), a *design* (a finished card or poster), a *subject* (a cut-out on transparency, the template's background around it) | the worker's generate nodes |
| blocks | every piece of chrome: pills, tiles, marks, lists, cards, frames, handles | lp-compose, from bank blocks the worker picks |

A template (`compose/families.py`) is a **skeleton**: its background, its
panels and its **slots**. A slot has a geometry, a look (a fill, a pill
style), a `shape` and the `categories` it accepts. It says nothing about any
page: no text, no glyph, no model. `uv run lp-compose --skeleton <family>
--preset <layout> --out wire.png` draws it.

## Categories: what a block means

| category | means | hard check (code) |
|---|---|---|
| state-label | which state of one picture a panel shows (Before / After) | two states of one picture; the word matches the panel |
| tool | the Picsart tool that made the change: its glyph, or its own interface (an adjust panel, a calculator) | the tool is the page's own or one its copy names |
| attribution | the model that generated the picture: its maker's mark, a picker, the generator's toolbar | the mark is the generating model's maker's (the four-point sparkle is Gemini's); made-by.yaml binds it |
| comparison | two pictures compared (VS, a compare handle) | two pictures, or two states |
| spec | a measurable property of the output (x2, 4K, 16:9, 50 photos) | the tool always delivers it, or the copy says it |
| action | the reader's step (a button), or the prompt that made the picture | the copy's words or the tool's own verb; a prompt is the opening of the real prompt |
| statement | the section's point in its own words, set large (a formula, a figure) | verbatim page copy |
| derived | content lifted from a panel (its palette, its fonts) | takes it from a panel of this composition |
| context | the output where it is used (a posted card, the channels the copy names) | strings from the copy |
| editor | editor furniture around a subject (a crop frame, a selection box, a batch check, the pointer) | — |
| process | the tool at work between the reader's picture and the result (a progress ring); a clip's state | — |

## Measured layouts

Beside the hand-made layouts, every corpus composite has been read (OCR and a
pixel layout) and turned into a skeleton of its own, named `m-<code>`
(`lp-compose --induce`, `compose/assets/layouts.yaml`): its pictures as panels,
its cards, chip rows and pills as slots, each slot keeping the fill, radius,
inset and type it was measured with, so a block drawn there looks like the
original's. Its slots accept the categories the original's words showed (a
model name is attribution, "Before" a state label, "4K" a spec, "Generate" an
action) and name no words: you still give every string, about your picture.

## The bank

`compose/assets/blocks.yaml` holds every block: its category, what it
`means`, `when` it belongs (its soft context), the shapes it can draw in and
the parameters it takes. Some parameters are fixed by the page (`tool`: one of
the page's tools; `model`: the generating model); some you give (`text`,
`rows`, `fields`), always from the page copy. `lp-corpus roles` counts the
corpus evidence behind each block.

## How a slot gets filled

1. **Category** — the block's category is one the slot accepts.
2. **Shape** — the block can draw in the slot's shape.
3. **Hard context** — its claim is true of this page (the table above).
   The brief's `## Blocks` lists, per slot, only the candidates that pass 1–3,
   and the excluded ones with why.
4. **Soft context** — you judge. Pick a candidate only when its *When* is
   true of this section: its copy, its page, the picture you will make. A
   font-pairing tile belongs beside a typographic design, not a sneaker photo;
   a product's price card only where a product is sold; a calculator only on a
   calculator page. When nothing fits an optional slot, leave it empty
   (`block: none`): an empty slot draws nothing and the background shows. When
   nothing fits a required slot, stop: write `result.md` with `status:
   blocked` and say which slot and why, so the manager can choose a layout the
   page can fill.

Write the picks before any paid call, in `blocks-<slot>.yaml`:

```yaml
slot: S05-m1
fills:
  - {slot: card-a, block: statement, text: "<a short line of the copy>", because: "the copy's formula line"}
  - {slot: card-b, block: channel-list, rows: [<platform>, <platform>], because: "the copy names where it runs"}
  - {slot: tile-3, block: none, because: "no palette: the section is about returns, not design"}
```

Every pick carries `because:`, the copy or page fact that makes it fit;
the reviewer checks it.

**Every string and value is about your picture.** Labels come verbatim from
the page copy, but what a block says about the picture is yours: a
calculator's example is the picture's own (the spend and revenue of the ad
you made, computed), a channel list names where this picture runs, a
statement is the line the composition puts to work on it. Never reuse an
example, name or number from anywhere else, and leave out a block whose text
would read the same beside any picture: that is the text that looks out of
place. The bank's `note:` on each parameter gives its shape, so you never
need the code: never read `src/`, `tests/` or `corpus/` (the templates'
records describe the corpus originals, and a blind worker must not copy them).

Then
`uv run lp-compose --check-blocks composition-<slot>.yaml blocks-<slot>.yaml`
refuses a wrong category or shape, a false claim, a string not in the copy, a
block twice, an empty required slot; it also binds an attribution pick into
`made-by.yaml` (so `lp-flow check` holds the picture's lineage to that model).
`--spec-from-plan <plan> --blocks blocks-<slot>.yaml --image ...` resolves the
picks into the compose spec; precheck holds the spec to them exactly. After
drawing, `lp-compose` reads the render back (on-device OCR) and prints a
`verify:` line for every string that does not read as given, inside its block:
symbols and numbers exactly (a ÷ that reads + is a fault), long words to one
letter. A `verify:` line fails the compose gate; `--strict` makes it an error.

## Choosing the layout (the manager)

A layout fits a section when the page can fill its required slots with blocks
that belong there. A page with no image tool (a calculator, a guide) gets no
image-tool tile, and a borrowed one (the old default crop tile) is a false
claim, so `dark-composite`'s three-tile column is left with a mark, a palette
and whatever else passes the checks, whether it belongs or not. Its `bento`
layout — a statement card, a context card and the page's own tool across the
foot, around one picture — is what a calculator page shows. `brief.py`
refuses a layout whose required slot has no candidate at all and names the
layouts of the family that can be filled; when candidates exist but none
belongs, the worker reports the slot blocked and you change `> device:`.
