# Data

The code is in git; the image data is not (≈22 GB, 63,800 files: scraped
page media and licensed stock photos cannot go on a public repo). It is shared
as a Google Drive folder, `landing-page-gen-data`, with the same layout as this
repo, so dropping its folders into a clone restores everything.

Drive folder: _link added when shared_ (private; viewers by invitation).

## Where to look first

- `runs/blind-1-sheet.png`, `runs/blind-2-sheet.png`: the blind trials, each
  original page image beside what a worker made from the page context alone.
- `runs/<run>/sections/<Sxx>/steps/`: every step a worker's board produced
  (`<slot>-<node>-<n>.png`); the chosen one is named in that folder's `result.md`,
  the board in `workflow.yaml`/`flow.md`, the reviews in `review-N.md`.
- `runs/<run>/dist/`: the page snapshot with the generated media injected
  (`index.html`; open it locally, Drive does not render HTML).
- `corpus/labels/*.png`, `corpus/taxonomy/*.png`: contact sheets of the corpus.

## What each folder holds

| folder | size | what it is | rebuilt by |
|---|---|---|---|
| `corpus/pages/<slug>/` | 8.0 GB | 476 Picsart landing pages: `page.html` snapshot, `page.png` screenshot, `sections.md`, `media/` (every image and clip on the page) | `lp-corpus fetch` (the live pages change) |
| `corpus/pool/` | 2.7 GB | stock photos from Pexels, Unsplash, Pixabay ranked per style family (`<family>.yaml`), their descriptions and search cache | `lp-corpus pool search` (API keys) |
| `corpus/storyboards/` | 5.0 GB | each clip's holds, transitions and keyframes | `lp-corpus storyboard` |
| `corpus/frames/` | 3.3 GB | first/middle/last frame strips of every clip | `lp-corpus frames`, `attrs` |
| `corpus/labels/`, `corpus/taxonomy/` | 270 MB | labelling contact sheets and their answers; the cross-tab sheets | `lp-corpus sheets`, `taxonomy` |
| `corpus/readings/` | 20 MB | every image read: OCR lines and pixel layout | `lp-corpus read` |
| `corpus/corpus.db`, `attributes.yaml`, `styles.yaml`, `grammar/`, `references/`, `roles/` | 50 MB | the indexed corpus, measured and labelled attributes, style families, page grammar, reference photographers | `lp-corpus sectionize`, `attrs`, `labels`, `grammar` |
| `library/` | 190 MB | a browsable view of the corpus: page dossiers, assets by model, art style and structure, a sidecar per asset | `lp-corpus organise` |
| `research/` | 122 MB | studies behind the decisions: template reviews and audits, the probe renders (`lp-compose --probe`), style-gap and context-gap sheets, scrape and Flow notes; the write-ups are also in git, the sheets only here | the studies (their `README`/report per folder) |
| `runs/` | 2.3 GB | 45 runs: skeletons, briefs, boards, every generated step, reviews, reports, ledgers (every paid call and its URL) | the runs themselves (paid) |

## Terms

- Picsart page media belong to Picsart; stock photos keep their platform's
  licence (Pexels, Unsplash, Pixabay: free to use, not to redistribute as a
  collection). Keep the folder private.
- Generated images were made on the team's Picsart account; `runs/*/ledger.jsonl`
  records the model and cost of each.

## Check a copy

`share/MANIFEST.sha256` lists every file's SHA-256:

```
shasum -a 256 -c share/MANIFEST.sha256 --quiet
```

prints only files that differ or are missing.
