# Layered / composite generation — distilled techniques

What the field actually does to make multi-element images read as one
photograph, mapped onto our two routes. Sources in `sources.md`. These are the
rules the pilot uses and, if they hold, what codifies into the `layered`
pattern.

## 1. The compositing formula (model-native, Route 1)

`[Reference images] + [Relationship instruction] + [New scenario]`

Narrative scene direction, **not** keyword lists. Start with a strong verb
(compose / place / relight). One clause names each element's role, one names
how they relate, one names the scene. Example shape:

> "Place the ceramic mug from image 1 on the marble counter. Relight it to
> match the soft window light from the left, cast a soft contact shadow to the
> right, keep the mug's exact shape and glaze."

## 2. Reference-slot strategy (when passing `imageUrls`)

- **Start with 2–4 references, not 10.** A reference earns its slot only if it
  owns a *distinct* role.
- **First-six rule:** whatever must survive at highest fidelity goes in the
  earliest slots. "Early slots are for identity and structural fidelity, later
  slots are for influence." Order: main subject/product → identity/face →
  pose/composition → environment → material detail → style → lighting.
- **One anchor per role.** Two references fighting for the same dimension
  (two backgrounds, two styles) produce a muddy averaged result. Remove the
  duplicate.
- **Split the ask three ways in words:** *must keep* (silhouette, face, logo,
  glaze) / *can adapt* (background, light warmth, crop, angle) / *should
  avoid* (shape change, person swap, merged style).

## 3. Stop the subject drifting

- List the hero subject **first** and add explicit preservation language
  ("keep the subject identical, do not redesign it").
- A drift usually means a later reference (style/light) is out-shouting the
  subject — move the subject earlier, cut the competing reference.
- **Debug by removing, not adding:** when a run fails, cut the reference set
  back to the minimum that should still work, then add back one at a time.

## 4. Harmonisation — the four properties of light

Flat, directionless light is the single biggest "AI look" giveaway. Every
element must agree on all four:

1. **Direction** — name it ("key from camera-left"). Read it from a plate by
   which way shadows fall (shadows running right = light on the left).
2. **Hardness** — hard (sharp-edged shadow, direct sun) vs soft (gradual
   shadow, window/overcast). Mixing hard and soft across elements reads fake.
3. **Colour temperature** — warm (golden morning/tungsten), neutral (midday),
   cool (shade/overcast). Tint the inserted element's shadow with the plate's
   ambient colour.
4. **Height** — short shadow = overhead light, long shadow = low sun.

## 5. Contact shadow and the pasted look

- A subject with no ground shadow floats — always ask for a contact shadow and
  name its direction and softness.
- Give the model the surface *around* where the subject lands (in Route 2,
  don't cut too tight; keep some plate context) so it knows how light behaves.
- To stop a placement pass from relighting the whole frame, add: "keep the
  existing lighting and shadows in the scene."

## 6. Two focused passes beat one complex prompt

Fix one thing per pass. If only the shadow is wrong, correct the shadow in a
second pass rather than regenerating everything ("fix the scene, vary one
thing"). Upscale/enhance **last**, after the light is finalised.

## 7. Words carry the photograph, the reference carries the thing

"Describe the photograph, not the product." The reference already shows the
subject; spend words on lens, light, surface, mood — "soft diffused daylight
from the left, shallow depth of field, fine water droplets on the stone."
Match depth-of-field and focal length across elements (a crisp subject on a
soft-focus plate reads as a sticker).

## Evaluation checklist (→ the harmonisation gate)

1. Shadow **direction** agrees across the frame.
2. Shadow **softness** consistent (no hard-on-soft mix).
3. **Highlights** sit on the side facing the light.
4. **Colour temperature** matches (mismatch = sticker effect).
5. **Contact shadow** present and correctly placed.
6. **Scale / perspective / occlusion** plausible.
7. **Depth-of-field / grain** match between elements.

## What this changes in our design

- Route 1 prompt = the §1 formula with the §2 slot order and §3 preservation
  language baked in.
- Route 2's harmonise step (step 4) gets the §4–§5 language explicitly, plus
  "keep the existing lighting and shadows" so it seats rather than relights.
- The design's harmonisation gate already matches the §Evaluation checklist —
  confirmed against three independent sources.
