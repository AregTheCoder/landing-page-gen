# Layered / composite image generation — sources

Web research, 2026-09-10, for the layered-photograph method. Annotated; the
distilled rules are in `findings.md`. No paid calls; reading only.

## Model-specific (Nano Banana Pro / gemini-3-pro-image)

- **Google Cloud — Ultimate prompting guide for Nano Banana**
  <https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-nano-banana>
  The compositing formula `[Reference images] + [Relationship instruction] +
  [New scenario]`; narrative scene direction over keyword lists; explicit
  role attribution per image ("Using image 1 as the structure…"); relight-to-
  match phrasings; up to 14 references, 4K.
- **AI Free API — Nano Banana Pro Reference Images: setup and drift fixes (2026)**
  <https://www.aifreeapi.com/en/posts/nano-banana-pro-reference-images>
  The slot strategy (first-six rule; identity/structure early, style/light
  late), the must-keep / can-adapt / should-avoid split, and a drift
  troubleshooting table. Best single source on stopping subject drift.
- **Google blog — Nano Banana Pro prompting tips**
  <https://blog.google/products-and-platforms/products/gemini/prompting-tips-nano-banana-pro/>
  Official. Subject, composition, action, location, style; refine with camera
  angle and lighting. (Corroborates the above.)
- **Leonardo.Ai — Nano Banana Prompt Guide**
  <https://www.leonardo.ai/news/nano-banana-prompt-guide> (corroborating)

## Harmonisation (the hard part: light, shadow, colour)

- **OpenArt — How to Match Lighting in AI Image Inpainting**
  <https://openart.ai/blog/match-lighting-in-ai-image-inpainting/>
  Read light from existing shadows (direction/hardness/temperature/height);
  describe direction+softness+colour+ground-shadow in the region prompt;
  "keep the existing lighting and shadows in the scene" to stop a full
  relight; select wider than the object for shadow context; the four quality
  checks. This is the source of our harmonisation gate.
- **Nightjar — 6 Prompt Patterns for Realistic AI Product Photos**
  <https://nightjar.so/blog/prompt-patterns-realistic-ai-product-photos>
- **Envato Elements — Prompts for realistic AI images: what actually works**
  <https://elements.envato.com/learn/prompts-for-realistic-ai-images>
  Flat, directionless light is the single biggest "AI look" giveaway.

## Pipeline (compositing a subject into a scene)

- **Krea — AI Product Photography in 2026: Tools, Prompts, and a Working Pipeline**
  <https://www.krea.ai/blog/ai-product-photography-in-2026-tools-prompts-pipeline>
  Three deliberate steps (generate from product ref → region-edit the wrong
  detail → upscale); reference carries product identity, words carry "lens,
  light, surface, mood"; "describe the photograph, not the product"; "fix the
  scene, vary one thing".
- **Luma — 25 AI Product Photography Prompts for E-commerce (2026)**
  <https://lumalabs.ai/news/ai-product-photography-prompts>
- **Scalio — AI Photoshoot Prompts for Product Photography (2026)**
  <https://scalio.app/blog/ai-prompts-for-product-photography/> (copy-paste recipes)
