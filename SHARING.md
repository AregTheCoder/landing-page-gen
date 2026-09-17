# Setting up a shared copy of landing-page-gen

This project has two halves: **code + committed sources** (in git, ~52 MB) and
the **heavy generated data** (snapshots, downloaded media, the SQLite index, the
browsable library) which is gitignored and travels out-of-band.

## From a full archive (`landing-page-gen-full.tar`)

A self-contained tarball carries everything except the Python virtualenv and the
regenerable `library/`.

```bash
tar -xf landing-page-gen-full.tar
cd landing-page-gen

# Python 3.12+ via uv (https://docs.astral.sh/uv/)
uv sync                       # or: uv sync --extra embed   (for the CLIP pool ranker)

# Rebuild the library/ tree (excluded from the archive to save ~220 MB)
uv run lp-corpus organise

# Verify the corpus is intact and conforms to metastructure.md
uv run lp-corpus doctor       # expect: 0 errors (a few warnings are normal)

# Run the tests
uv run pytest
```

## From a git clone + a data side-car

If you cloned the code from GitHub, you have the sources but **not** the 4.8 GB of
`corpus/pages/` (snapshots + media) or `corpus/corpus.db` — `sectionize`/`attrs`
can't rebuild those without them. Extract the data side-car over the clone:

```bash
git clone <repo> && cd landing-page-gen
tar -xf corpus-data.tar        # adds corpus/pages/ and corpus/corpus.db
uv sync && uv run lp-corpus organise && uv run lp-corpus doctor
```

## Secrets and connectors — NOT included

No API keys are in the archive. To use the paid Picsart tools or the free-tier
stock pool you supply your own:

- `PICSART_API_KEY` — exported from your shell (see `../CLAUDE.md`).
- `PEXELS_API_KEY`, `UNSPLASH_ACCESS_KEY`, `PIXABAY_API_KEY` — in a gitignored
  `.env` (a missing key just skips that platform).
- The Picsart MCP connectors are authorised per-user in claude.ai → Settings →
  Connectors, not stored in the repo.

## What regenerates vs what is source

Regenerate freely (never hand-edit): `corpus/corpus.db`, `library/`, `dist/`.
Hand-editable sources: `sections.md`, `meta.json`, `pages.yaml`, label
`*.answers.yaml`, `skeleton.md`, the reference/research YAML. See
`metastructure.md` for the full map and `lp-corpus doctor` for the check.
