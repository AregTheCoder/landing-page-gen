# Block roles in the corpus

2948 chrome blocks on 1481 labelled assets, each given the role its kind and text settle (`lp-corpus roles`; vocabulary in `compose/assets/roles.yaml`). Derived, never written into attributes.yaml.

## Roles overall

| role | blocks | share |
|---|---|---|
| tool | 561 | 19% |
| spec | 537 | 18% |
| action | 524 | 18% |
| context | 505 | 17% |
| attribution | 442 | 15% |
| derived | 120 | 4% |
| editor | 111 | 4% |
| comparison | 90 | 3% |
| state-label | 58 | 2% |

## Per style family

| family | blocks | roles (commonest first) |
|---|---|---|
| full-bleed | 497 | attribution 160, spec 134, tool 107, action 43, context 16, state-label 15, comparison 8, derived 8, editor 6 |
| prompt-card | 486 | action 293, spec 68, tool 47, attribution 46, context 25, derived 4, editor 3 |
| template-mockup | 445 | context 243, tool 76, derived 60, spec 29, action 26, attribution 7, editor 3, state-label 1 |
| mockup-card | 302 | context 128, spec 53, tool 49, action 48, derived 15, attribution 4, state-label 3, editor 2 |
| before-after | 198 | comparison 48, attribution 41, state-label 35, tool 27, spec 21, action 20, context 4, editor 2 |
| crop-frame | 171 | spec 60, editor 44, tool 24, attribution 14, context 14, action 13, derived 1, comparison 1 |
| dark-composite | 166 | tool 102, derived 18, attribution 14, action 13, spec 11, context 5, editor 2, state-label 1 |
| vs-two-up | 151 | attribution 107, comparison 20, spec 14, tool 9, action 1 |
| model-card | 142 | spec 67, attribution 40, tool 16, comparison 13, derived 4, context 1, action 1 |
| editor-canvas | 136 | editor 37, tool 34, spec 28, action 21, context 13, attribution 2, derived 1 |
| cutout-checkerboard | 98 | context 38, tool 19, spec 16, action 13, derived 6, editor 4, state-label 2 |
| panel-overlay | 64 | tool 42, context 10, spec 7, action 3, editor 1, derived 1 |
| other | 53 | action 21, spec 8, tool 7, attribution 7, context 6, editor 4 |
| cinematic-still | 29 | spec 21, action 8 |
| graphic-collage | 9 | derived 2, tool 2, editor 2, context 2, state-label 1 |
| outcome-tile | 1 | editor 1 |

## Slots against the corpus

Each template slot's `accepts` next to the roles the corpus places the same way in that family (`beside` the pictures, or `overlay` on one). A role holding 10 % or more of those blocks that the slot does not take is listed.

| family | layout | slot | shape | where | accepts | corpus (commonest first) | not taken |
|---|---|---|---|---|---|---|---|
| before-after | default | before-pill | pill | overlay | state-label | comparison 48, state-label 35, attribution 7, spec 6, action 5 | comparison |
| before-after | default | after-pill | pill | overlay | state-label | comparison 48, state-label 35, attribution 7, spec 6, action 5 | comparison |
| before-after | default | tile | tile | beside | tool, attribution, spec | attribution 34, tool 22, spec 15, action 15, context 3 | action |
| before-after | stacked-square | before-pill | pill | overlay | state-label | comparison 48, state-label 35, attribution 7, spec 6, action 5 | comparison |
| before-after | stacked-square | after-pill | pill | overlay | state-label | comparison 48, state-label 35, attribution 7, spec 6, action 5 | comparison |
| before-after | stacked-square | tile | tile | beside | tool, attribution, spec | attribution 34, tool 22, spec 15, action 15, context 3 | action |
| before-after | pill | state | pill | overlay | state-label | comparison 48, state-label 35, attribution 7, spec 6, action 5 | comparison |
| before-after | compare-slider | handle | seam | overlay | comparison | comparison 48, state-label 35, attribution 7, spec 6, action 5 | state-label |
| crop-frame | default | icon | tile | beside | tool, spec, attribution | spec 42, tool 20, attribution 12, action 10, context 10 | action, context |
| crop-frame | default | brackets | frame | overlay | editor | editor 38, spec 18, tool 4, context 4, action 3 | spec |
| crop-frame | crop-grid | grid | frame | overlay | editor | editor 38, spec 18, tool 4, context 4, action 3 | spec |
| crop-frame | crop-grid | crop-badge | seam | overlay | tool | editor 38, spec 18, tool 4, context 4, action 3 | editor, spec |
| crop-frame | crop-grid | ratio | tile | beside | spec | spec 42, tool 20, attribution 12, action 10, context 10 | tool, attribution, action, context |
| cutout-checkerboard | default | badge-a | badge | overlay | editor, tool | context 29, spec 15, editor 4, action 4, tool 4 | context, spec |
| cutout-checkerboard | default | badge-b | badge | overlay | editor, tool | context 29, spec 15, editor 4, action 4, tool 4 | context, spec |
| cutout-checkerboard | default | button | pill | beside | action | tool 15, context 9, action 9, derived 5, spec 1 | tool, context, derived |
| cutout-checkerboard | selection-frame | badge-a | badge | overlay | editor, tool | context 29, spec 15, editor 4, action 4, tool 4 | context, spec |
| cutout-checkerboard | selection-frame | badge-b | badge | overlay | editor, tool | context 29, spec 15, editor 4, action 4, tool 4 | context, spec |
| cutout-checkerboard | selection-frame | button | pill | beside | action | tool 15, context 9, action 9, derived 5, spec 1 | tool, context, derived |
| cutout-checkerboard | selection-frame | select | frame | overlay | editor | context 29, spec 15, editor 4, action 4, tool 4 | context, spec |
| template-mockup | default | tile-1 | tile | beside | attribution, tool, derived | context 183, tool 62, derived 40, action 19, spec 4 | context |
| template-mockup | default | tile-2 | tile | beside | tool, attribution, derived | context 183, tool 62, derived 40, action 19, spec 4 | context |
| template-mockup | default | swatch | tile | beside | derived, tool, attribution | context 183, tool 62, derived 40, action 19, spec 4 | context |
| template-mockup | palette-card | swatch | tile | beside | derived | context 183, tool 62, derived 40, action 19, spec 4 | context, tool |
| template-mockup | palette-card | tile-accent | tile | beside | attribution, tool | context 183, tool 62, derived 40, action 19, spec 4 | context, derived |
| template-mockup | palette-card | tile-tool | tile | beside | tool, attribution | context 183, tool 62, derived 40, action 19, spec 4 | context, derived |
| template-mockup | selection-frame | tile-1 | tile | beside | attribution, tool, derived | context 183, tool 62, derived 40, action 19, spec 4 | context |
| template-mockup | selection-frame | tile-2 | tile | beside | tool, attribution, derived | context 183, tool 62, derived 40, action 19, spec 4 | context |
| template-mockup | selection-frame | swatch | tile | beside | derived, tool, attribution | context 183, tool 62, derived 40, action 19, spec 4 | context |
| template-mockup | selection-frame | select | frame | overlay | editor | context 60, spec 25, derived 20, tool 14, action 7 | context, spec, derived, tool |
| template-mockup | editor | select | frame | overlay | editor | context 60, spec 25, derived 20, tool 14, action 7 | context, spec, derived, tool |
| template-mockup | editor | type | tile | beside | derived, tool | context 183, tool 62, derived 40, action 19, spec 4 | context |
| template-mockup | editor | swatch | bar | beside | derived | context 183, tool 62, derived 40, action 19, spec 4 | context, tool |
| dark-composite | default | tile-1 | tile | beside | attribution, tool, derived, spec | tool 102, derived 18, attribution 14, spec 7, context 5 | — |
| dark-composite | default | tile-2 | tile | beside | tool, attribution, derived, spec | tool 102, derived 18, attribution 14, spec 7, context 5 | — |
| dark-composite | default | tile-3 | tile | beside | derived, tool, attribution, spec | tool 102, derived 18, attribution 14, spec 7, context 5 | — |
| dark-composite | reference-thumbs | tile-1 | tile | beside | attribution, tool | tool 102, derived 18, attribution 14, spec 7, context 5 | derived |
| dark-composite | reference-thumbs | chip | tile | beside | spec | tool 102, derived 18, attribution 14, spec 7, context 5 | tool, derived |
| dark-composite | model-picker | list | card | beside | attribution | tool 102, derived 18, attribution 14, spec 7, context 5 | tool, derived |
| dark-composite | two-up | tile-1 | tile | beside | attribution, tool | tool 102, derived 18, attribution 14, spec 7, context 5 | derived |
| dark-composite | bento | card-a | card | beside | statement, spec | tool 102, derived 18, attribution 14, spec 7, context 5 | tool, derived |
| dark-composite | bento | card-b | card | beside | context, attribution, action | tool 102, derived 18, attribution 14, spec 7, context 5 | tool, derived |
| dark-composite | bento | foot | card | beside | tool, action, context | tool 102, derived 18, attribution 14, spec 7, context 5 | derived |
| panel-overlay | default | panel | panel | overlay | tool | tool 39, spec 6, context 5, action 2, editor 1 | spec |
| panel-overlay | hero | tool-pill | tile | beside | tool | context 5, tool 3, spec 1, action 1 | context, spec, action |
| prompt-card | default | prompt-text | text | beside | action, statement | action 267, attribution 45, tool 45, spec 34, context 21 | attribution, tool |
| prompt-card | default | generate | pill | beside | action | action 267, attribution 45, tool 45, spec 34, context 21 | attribution, tool |
| prompt-card | column | mark | tile | beside | attribution | action 267, attribution 45, tool 45, spec 34, context 21 | action, tool |
| prompt-card | column | prompt | card | beside | action | action 267, attribution 45, tool 45, spec 34, context 21 | attribution, tool |
| prompt-card | strip | mark | tile | beside | attribution | action 267, attribution 45, tool 45, spec 34, context 21 | action, tool |
| prompt-card | strip | prompt | card | beside | action | action 267, attribution 45, tool 45, spec 34, context 21 | attribution, tool |
| prompt-card | caption | prompt | card | beside | action | action 267, attribution 45, tool 45, spec 34, context 21 | attribution, tool |
| prompt-card | toolbar | prompt | card | beside | action | action 267, attribution 45, tool 45, spec 34, context 21 | attribution, tool |
| prompt-card | toolbar | toolbar | bar | beside | attribution, spec | action 267, attribution 45, tool 45, spec 34, context 21 | action, tool |
| prompt-card | settings | quality | bar | beside | spec | action 267, attribution 45, tool 45, spec 34, context 21 | action, attribution, tool |
| prompt-card | settings | ratios | bar | beside | spec | action 267, attribution 45, tool 45, spec 34, context 21 | action, attribution, tool |
| prompt-card | wide | prompt | card | beside | action | action 267, attribution 45, tool 45, spec 34, context 21 | attribution, tool |
| prompt-card | wide | mark | tile | beside | attribution | action 267, attribution 45, tool 45, spec 34, context 21 | action, tool |
| vs-two-up | default | vs | seam | overlay | comparison | attribution 52, comparison 13, spec 5 | attribution |
| mockup-card | default | post | card | beside | context | context 97, tool 36, action 32, spec 25, derived 11 | tool, action, spec |

## Bank evidence

The corpus blocks each bank block stands for (its `evidence:` kinds and text), the families they appear in and the pages that show them most. A bank block with no corpus evidence comes from an unmeasured original.

| block | category | corpus blocks | families | pages (commonest first) |
|---|---|---|---|---|
| state-pill | state-label | 61 | before-after 35, full-bleed 15, template-mockup 4 | ai-image-enhancer 9, ai-replace 8, image-enlarger 6, ai-design-tools 6 |
| tool-tile | tool | 495 | dark-composite 101, full-bleed 99, template-mockup 75 | ai-design-tools 16, collage-maker 12, flip-video 8, ai-photo-editing 8 |
| tool-icon | tool | 495 | dark-composite 101, full-bleed 99, template-mockup 75 | ai-design-tools 16, collage-maker 12, flip-video 8, ai-photo-editing 8 |
| tool-disc | tool | 495 | dark-composite 101, full-bleed 99, template-mockup 75 | ai-design-tools 16, collage-maker 12, flip-video 8, ai-photo-editing 8 |
| tool-pill | tool | 517 | dark-composite 101, full-bleed 99, template-mockup 75 | ai-design-tools 16, collage-maker 12, design 9, flip-video 8 |
| adjust-panel | tool | 66 | panel-overlay 37, full-bleed 8, editor-canvas 5 | hsl-color 10, video-studio--video-speed 4, face-editor 4, watermark-photos 4 |
| calculator | tool | 0 | — | — |
| generator-mark | attribution | 309 | full-bleed 112, vs-two-up 61, prompt-card 39 | compare-models--dall-e-3-vs-midjourney 17, ai-models 11, ai-models--dall-e-3 10, compare-models--ideogram-3-0-flash-vs-flux-2-pro 9 |
| maker-glyph | attribution | 309 | full-bleed 112, vs-two-up 61, prompt-card 39 | compare-models--dall-e-3-vs-midjourney 17, ai-models 11, ai-models--dall-e-3 10, compare-models--ideogram-3-0-flash-vs-flux-2-pro 9 |
| model-picker | attribution | 303 | full-bleed 108, vs-two-up 61, prompt-card 37 | compare-models--dall-e-3-vs-midjourney 16, ai-models 11, ai-models--dall-e-3 10, compare-models--ideogram-3-0-flash-vs-flux-2-pro 9 |
| model-pill | attribution | 133 | full-bleed 48, vs-two-up 46, before-after 19 | compare-models--dall-e-3-vs-midjourney 9, compare-models--nano-banana-2-vs-flux-2-pro 8, compare-models--luma-ray-2-vs-kling-3-0 8, compare-models--recraft-v4-vs-ideogram-3-0-flash 7 |
| generator-toolbar | attribution | 64 | full-bleed 36, prompt-card 7, model-card 7 | compare-models--seedance-2-0-vs-veo-3-1 6, compare-models--seedance-2-5-vs-kling-3-0 4, compare-models--seedance-2-vs-runway-gen-4 3, ai-image-generator 3 |
| vs-badge | comparison | 43 | vs-two-up 20, model-card 13, full-bleed 8 | compare-models--dall-e-3-vs-midjourney 10, ai-models 5, compare-models 3, compare-models--sora-vs-veo 2 |
| compare-handle | comparison | 47 | before-after 47 | ai-image-enhancer 7, ai-design-tools 5, image-tools 4, hd-photo-converter 4 |
| spec-label | spec | 433 | full-bleed 107, model-card 64, crop-frame 57 | video-to-gif 13, compare-models--dall-e-3-vs-midjourney 11, ai-models 11, ai-models--elevenlabs-music-v2 11 |
| spec-pill | spec | 394 | full-bleed 108, model-card 64, prompt-card 47 | video-to-gif 15, compare-models--dall-e-3-vs-midjourney 11, ai-models 11, ai-models--elevenlabs-music-v2 11 |
| options-bar | spec | 390 | full-bleed 107, model-card 64, prompt-card 47 | video-to-gif 13, compare-models--dall-e-3-vs-midjourney 11, ai-models 11, ai-models--elevenlabs-music-v2 11 |
| cta-button | action | 301 | prompt-card 133, mockup-card 46, full-bleed 33 | ai-design-tools 10, ai-poster-generator 7, ai-content-generator 6, remove-object-from-photo 6 |
| prompt-line | action | 170 | prompt-card 159, before-after 7, crop-frame 3 | ai-design-tools 7, ai-poster-generator 7, ai-models--async-flash-v1 5, ai-design-generator 5 |
| prompt-card | action | 170 | prompt-card 159, before-after 7, crop-frame 3 | ai-design-tools 7, ai-poster-generator 7, ai-models--async-flash-v1 5, ai-design-generator 5 |
| statement | statement | 0 | — | — |
| palette | derived | 89 | template-mockup 42, dark-composite 14, mockup-card 12 | brand-identity-generator 6, brand-kit-generator 5, design 4, background-changer 3 |
| font-pair | derived | 31 | template-mockup 18, dark-composite 4, mockup-card 3 | ai-font-generator 2, resume-maker 2, quote-maker 2, instagram-video-maker 1 |
| profile-card | context | 0 | — | — |
| channel-list | context | 0 | — | — |
| crop-brackets | editor | 27 | crop-frame 26, before-after 1 | resize-image 4, ai-image-extender 3, crop-image 3, ai-background 2 |
| transform-box | editor | 55 | editor-canvas 30, crop-frame 12, template-mockup 3 | crop-image 4, batch-photo-editor 3, photo-editor 3, add-shadow-to-image 3 |
| batch-check | editor | 57 | cutout-checkerboard 28, template-mockup 8, mockup-card 7 | batch-photo-editor 4, image-tools 4, background-changer 3, background-remover 3 |

## Where each role sits

| role | anchors (commonest first) |
|---|---|
| action | bl 113, left 99, tl 70, centre 69, bottom 60 |
| attribution | bl 186, bottom 112, tl 63, top 27, left 15 |
| comparison | centre 82, bl 2, bottom 2, top 1, right 1 |
| context | centre 153, right 90, left 64, tr 49, bl 40 |
| derived | left 32, bl 25, bottom 16, tl 13, br 11 |
| editor | centre 40, left 17, tr 15, right 11, tl 7 |
| spec | bottom 119, bl 108, centre 78, br 65, left 62 |
| state-label | bl 38, br 15, left 2, tl 2, tr 1 |
| tool | bl 140, left 118, tl 79, centre 71, tr 42 |

## What each role says

| role | commonest texts |
|---|---|
| action | 'Generate' (111); 'Start Creating' (16); 'Download' (7); 'BUY' (6); 'Blur' (4); 'A smooth, cinematic half-circle movement' (4) |
| attribution | 'Luma Ray 2|Kling 3.0' (9); 'Runway Gen 4|Veo 3.1' (8); 'GPT Image 1.5|Midjourney V7' (8); 'Recraft V4|Midjourney V7' (8); 'Recraft V4|Ideogram 3.0 Flash' (8); 'Nano Banana 2|Flux 2 Pro' (7) |
| comparison | 'VS' (43) |
| context | 'Color palette' (6); 'Logos' (4); 'Fonts' (3); 'plump' (3); 'EXPLORE OFFERS' (2); 'LIMITED EDITION' (2) |
| derived | 'Aa Aa' (8); 'Aa' (5); 'Aa|Aa|Aa' (5); 'Ai' (4); 'Aa Bb' (3); 'ABC' (2) |
| spec | 'GIF' (14); '4K' (7); '16:9|9:16' (6); 'Audio: On' (5); '2' (5); 'Aa|Aa' (5) |
| state-label | 'Before' (22); 'Before|After' (16); 'After' (15); 'BEFORE|AFTER' (2); 'Before|Before' (1); 'before' (1) |
| tool | '1x' (4); 'HSL' (4); 'Hue' (2); 'Saturation' (2); 'Lightness' (2); 'Stickers' (2) |

## Residual

Blocks whose purpose the kind and text leave open. A tile's tool is read from its icon on the contact sheet; until then a tool block is offered only for the page's own tool (`roles.yaml pages:`) or one its copy names.

- tile with no text (which tool?): 477
- model-logo with no text (which model?): 221
