# Planned recipes: author the whole board up front

A board is **planned, not grown**. Before the first call you write every node
the slot's family recipe calls for — the base generate, the i2i refine, the
family's edit/compose steps, the finishing upscale — preflight the whole board,
`lp-flow check` it, then run each node with its gate. You do **not** ship a lone
generate and add a refine only if a gate happens to find a flaw; the refine and
the finish are part of the plan and always run. A gate that fails re-runs *its
own* node (a new node, same recipe slot); it never decides whether a planned
node exists.

`lp-flow check` enforces this. Put `family: <family>` at the top of the board;
the check then requires the board to realise that family's recipe below and
fails a board that skips a planned step. This is automatic and rigorous: a
shallow board does not wire, so the manager's `precheck.py` rejects it.

## The recipes

Each row is the minimum planned pipeline (START and END omitted). "generate" and
"refine" are both `image` nodes on `gemini-3-pro-image`; "refine" is an i2i node
fed the base pass with the base in `imageUrls` and a prompt describing only the
improvement (tighter subject, fuller frame, cleaner light).

| family | planned nodes (in order) |
|---|---|
| full-bleed | generate → i2i refine → **enhance** (finishing upscale) |
| cinematic-still | generate → i2i refine → **enhance** |
| graphic-collage | generate → i2i refine |
| outcome-tile | generate → i2i refine |
| dark-composite | generate(panel) → i2i refine(panel) → **compose** |
| template-mockup | generate(panel) → i2i refine(panel) → **compose** |
| prompt-card | generate(panel) → i2i refine(panel) → **compose** |
| mockup-card | generate(panel) → i2i refine(panel) → **compose** |
| vs-two-up | generate(panel) → i2i refine(panel) → **compose** |
| panel-overlay | generate(photo) → i2i refine(photo) → **compose** |
| crop-frame | generate(source) → i2i refine(source) → **compose** |
| before-after | generate(before) → **edit** (after: enhance/change_bg/remove_bg) → **compose** |
| cutout-checkerboard | generate → **cutout** (remove_bg) → **compose** |

These are the floor. A slot may plan **more** than its row — a second refine, a
`background` node to place a cutout, a `variation` node for a hero the reviewer
will choose among, a multi-panel composite's extra `image` nodes — but never
fewer. Multi-panel composites (reference-thumbs, two-up, model-picker) plan a
generate + refine for each panel the device names.

## Planned finishes

- **enhance** (upscale) is planned on every `full-bleed` and `cinematic-still`
  slot, and on any slot whose natural width is over 1000 px. `picsart-enhance`
  ×2, or `topaz-upscale-image` for faces.
- **vectorize** is planned as the last node when the slot's subject is a logo,
  icon, emblem or flat mark that ships as artwork: generate → refine → enhance →
  `vectorize` (`picsart_vectorize`) → END, so the mark is delivered as a clean
  SVG. Photographic slots are never vectorized.

## Why planned, not reactive

Reactive boards (add a node only when a gate names a flaw) collapse to a single
generate whenever the first pass looks acceptable, so the "workflow" is one
call. Planning the whole recipe up front makes every slot a real multi-step
Picsart Flow board, makes the depth deterministic and reviewable before a credit
is spent, and lets `preflight` price the whole board against the cap in advance.
State what each planned node changed in its `reason`; the refine still has to
earn its place at its gate, but its existence is not in question.
