# Creators, sources and galleries that match Picsart's landing-page looks

2026-09-09. Collected for the context-gap work (plan: `~/.claude/plans/so-far-the-image-shimmering-beacon.md`,
Phase 3.1). Two looks: **A** the flat-vector illustration of the Recraft pages, **B** the
composite-card structure (a picture with product chrome laid over or beside it). Every URL was
opened by the research agents on the day; nothing here is from memory. No downloads, no paid calls.

## A. Flat-vector illustration (bold flat figures, saturated grounds, limited palette, frame-cropped)

The Recraft page's art (`corpus/pages/ai-models--recraft-v4-styles-pro-vector/media/`) is served
from `pcdn.picsart.com` and `cdn-cms-uploads.picsart.com`: Picsart's own art direction, generated
with Recraft, not Recraft showcase assets. Recraft's own galleries are style-diverse; the
"flat vector illustrations with bold color blocking" bucket sits in
https://www.recraft.ai/generate/stock-illustrations and https://www.recraft.ai/community.

| creator | where | why it matches | use |
|---|---|---|---|
| Malika Favre | https://www.handsomefrank.com/illustrators/malika-favre | flat colour, geometric shapes, negative-space crops on single-hue grounds; the canonical reference | reference, commission |
| Owen Davey | https://owendavey.com/ · https://folioart.co.uk/illustrator/owen-davey/ · https://www.instagram.com/owendaveydraws/ | flat vector, retro indigo/coral/sand/teal palette, thick uniform shapes | reference, commission, prints |
| Tom Haugomat | https://www.behance.net/tomhaugomat · https://www.handsomefrank.com/illustrators/tom-haugomat | two-to-three-colour flat figures, hard silhouettes, cinematic tight crops | reference, commission |
| Charlie Davis | https://www.charliedavisillustration.com/ · https://www.behance.net/Charlie_Davis | gestures reduced to flat shapes, saturated grounds | reference, commission |
| Petra Eriksson | https://www.petraeriksson.com/ · https://www.instagram.com/petraerikssonstudio/ | bold flat portraits of women, big bright colour; closest to the S01 hero crop | reference, commission |
| Bratislav Milenković | https://www.bratislavmilenkovic.com/ · https://www.behance.net/BratislavMilenkovic | vector colour blocking, conceptual, high polish | reference, commission |
| Nico189 (Nicola Laurora) | https://nico189.com/ · https://www.behance.net/Nico189 | clean-cut lines, pure geometric forms, flat saturated fills | reference, commission, prints |
| Studio MUTI | https://dribbble.com/studioMUTI | clean vector character sets and emblem marks (the S04/S08 half) | reference, studio |
| Xoana Herrera | https://www.behance.net/xoanaherrera · https://agentpekka.com/artist/xoana-herrera/ | stylish flat character scenes on saturated grounds | reference, commission |
| Darya Semenova | https://dribbble.com/patrisxa · https://www.behance.net/patrisxa | bold-shape characters and matching icon sets; closest to the S04 icon grid | reference, commission |
| Ana Miminoshvili | https://dribbble.com/Anano · https://www.behance.net/AnaMiminoshvili | strict geometric shapes plus free lines, warm limited palettes | reference, commission |
| Handsome Frank roster | https://www.handsomefrank.com/ | agency curated toward this idiom | discovery |
| Folio Art roster | https://folioart.co.uk/ | same, UK | discovery |
| Workbook "Vector/Flat Graphic" | https://www.workbook.com/portfolios/illustrators/vector-flat-graphic | pre-filtered directory of exactly this category | discovery |

Licensable libraries, best match first:

| library | URL | licence | API / bulk |
|---|---|---|---|
| Craftwork | https://craftwork.design/catalog/illustrations · https://craftwork.design/license/ | paid commercial, no resale | pack downloads |
| Ouch! by Icons8 | https://icons8.com/illustrations · https://icons8.com/license | free with link-back, paid without | Icons8 API and plugins on subscription |
| Blush | https://blush.design · https://blush.design/license | free commercial, no attribution | Figma plugin, no REST API |
| Vecteezy | https://www.vecteezy.com/developers | commercial | REST API, ~$50/mo, 10k calls per cycle |
| Adobe Stock (vectors) | https://developer.adobe.com/stock/docs/getting-started/ | Adobe Stock licences | free search API with a similar-image endpoint; licensing separate |
| Freepik / Storyset | https://www.freepik.com/ai/docs/freepik-api · https://storyset.com | free tier needs attribution | REST API, pay per use, 100 stock downloads/day |
| DrawKit | https://drawkit.com | MIT free packs, no attribution | ZIP packs |
| Iconfinder | https://developer.iconfinder.com/reference/overview-1 | free plan = free content | API v4 with a style filter (icon sets) |
| Noun Project | https://thenounproject.com/api/ | royalty-free | API with style and line-weight filters, $25/mo minimum |

Too pale and SaaS-flavoured for this palette: unDraw, Humaaans, Open Peeps, IRA Design.

Search vocabulary that returns the look: `flat vector <subject> <ground colour>`, `bold flat
character illustration`, `editorial vector portrait`, `geometric flat figure`, `limited palette
illustration`, `colour block illustration`; Dribbble tags `flat-vector-illustration`,
`flat-illustration`, `bold-illustration`; Behance search `flat character design`, `vector shapes`,
`graphic illustration`. Avoid `3d`, `isometric`, `line art`, `hand drawn`, `watercolor`,
`corporate memphis`.

## B. Composite-card structure (picture + floating tool chrome)

Picsart has no official Dribbble or Behance presence: https://dribbble.com/picsart and
https://dribbble.com/Picsart return 404, https://www.behance.net/picsart is an unrelated
individual; https://dribbble.com/search/picsart is community work.

First-party pages carrying the same devices, closest first:

| page | devices seen |
|---|---|
| https://vsco.co/features/hsl | HSL slider panel over a photo; before/after pairs per channel (the panel-overlay family) |
| https://www.photoroom.com/tools/background-remover | checkerboard cutout, before/after, floating panels over product photos, tool-tile grid (nearest to dark-composite) |
| https://www.kittl.com/ | floating panels over artwork, tool tiles, chips, before/after, "all the latest AI models in one canvas" (nearest to the model picker) |
| https://www.vectorizer.ai/ | raster to vector before/after, checkerboard alpha, corner zoom brackets (nearest to crop-frame) |
| https://www.adobe.com/express/feature/image/remove-background | checkerboard hero, before/after carousel, floating action panel |
| https://pixlr.com/remove-background/ | cutout, before/after, floating panel, tool tiles |
| https://www.fotor.com/features/hue-changer/ | offset labelled Before/After pair with an arrow on flat blue |
| https://www.recraft.ai/ · https://www.remove.bg/ | fetchable as text only; imagery needs a browser pass |
| https://www.canva.com/features/photo-editor/ · https://www.freepik.com/ai/image-generator | 403 to fetchers; view in the browser or through Saaspo/Mobbin captures |

Studios and teams producing this marketing-card style:

| who | URL | why |
|---|---|---|
| Canva (Dribbble team) | https://dribbble.com/canva | first-party creative-tool marketing design account |
| Kittl | https://dribbble.com/Kittl · https://www.behance.net/kittldesign | in-house; their site uses the devices |
| The Design Crew | https://www.thedesigncrew.co/studio-cases/photoroom | produced Photoroom's marketing visual assets; Photoroom's own brand story: https://www.photoroom.com/inside-photoroom/brand-refresh |
| Ramotion | https://dribbble.com/ramotion · https://www.ramotion.com/saas-web-design/ | "tailored visual mockups showing actual software screens" instead of stock |
| Cuberto | https://dribbble.com/cuberto | UI panels over photography and gradients |
| HALO LAB | https://dribbble.com/halolab | feature-section and hero cards |
| Outcrowd | https://dribbble.com/outcrowd | landing-page feature cards, bento sections |
| Orizon | https://dribbble.com/Orizon | marketing website design service |
| Zajno | https://dribbble.com/zajno | conversion-focused product marketing |
| Unfold | https://dribbble.com/unfold | AI-product brand and marketing cohort |
| Upnow Studio | https://dribbble.com/UpNow_Studio | marketing landing pages |
| Awsmd | https://dribbble.com/awsmd | SaaS marketing pages |
| Ronas IT | https://dribbble.com/ronasit | sectioned marketing sites |
| Desire Creative | https://dribbble.com/shots/21748655-A-Landing-page-for-an-AI-Based-Photo-Editor | the exact page genre |

Tag surfaces: https://dribbble.com/tags/feature-card · https://dribbble.com/tags/features-section ·
https://dribbble.com/tags/bento-features · https://dribbble.com/tags/ai-photo-editor.

Galleries with section-level browsing:

| gallery | URL | filter by section | cost | bulk / API |
|---|---|---|---|---|
| Saaspo | https://saaspo.com/section-type/saas-features-section-examples · https://saaspo.com/style/bento | yes, best | freemium | none; 403 to fetchers, browser only |
| SaaSFrame | https://www.saasframe.io/examples/bento-landing-page | 37 section patterns | $10-14/mo | Figma files on paid |
| Mobbin | https://mobbin.com/ | screens and flows | ~$20-40/seat/mo | bulk export on paid, API on Enterprise, official MCP server (May 2026) |
| Page Flows | https://pageflows.com/ | flows, screens, UI elements (Screenlane merged in, July 2024) | $39/quarter | none |
| Lapa Ninja | https://www.lapa.ninja/ | Sections area, industry and colour filters | free | none |
| Nicely Done | https://nicelydone.club/ | pages, apps, components | freemium | none (use the apex domain) |
| Dark Mode Design | https://www.darkmodedesign.com/ | dark UI sites | free | none |
| Are.na | https://www.are.na/developers | channels, search | free | open API, 30-600 req/min by tier, no bulk harvesting |
| Cosmos | https://www.cosmos.so/ | search by image and palette | free, ~$6 premium | app only |

## C. Stock photographers already in `corpus/references/*.yaml`

60 creators across 15 families (Pexels and Unsplash). Most cited: MART PRODUCTION (4 files), Weezy
Mie, Vika Glitter, Daniil Kondrashin, DS stories (2 each). Godisable Jacob and R. Fera are the
confirmed sources of hsl-color's cards (`research/live-1-style-gap/refs.yaml`). These remain the
photography references; nothing above replaces them.

## Programmatic access, in one place

Open: Pexels API (free, 200/h and 20k/month, colour and orientation filters), Unsplash API (50/h
demo, 5000/h after review; now carries SVG illustrations), Freepik API, Adobe Stock search API,
Vecteezy API, Iconfinder API, Noun Project API, Are.na API, Behance API (150/h, unmaintained).
Closed or gone: Dribbble API v2 (publishing only, no shot feeds), Bing Visual Search (retired
11 Aug 2025), Pinterest v5 (no visual search). Reverse search by URL without keys: Google Lens
`https://lens.google.com/uploadbyurl?url=<src>`, TinEye `https://tineye.com/search?url=<src>`
(exact and modified copies only), Yandex `https://yandex.com/images/search?rpt=imageview&url=<src>`
(visually similar). Store only Pexels, Unsplash, Freepik, Are.na and first-party competitor
pages credited by URL; Dribbble and Pinterest stay human-in-the-loop viewing.
