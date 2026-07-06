# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2026-07-06

  ### Fixed

  - `compress_deterministic` re-detects protected spans against the
    current (mutated) working text immediately before each overlap-
    sensitive step (filler-word removal, filler-phrase removal,
    duplicate-sentence removal, low-information-sentence pruning),
    instead of reusing stale offsets computed against the original text.
    Previously, on longer notes, earlier steps shrinking the text could
    invalidate those offsets, causing a sentence that genuinely contained
    a protected value (e.g. an oxygen saturation percentage) to be
    misjudged as droppable. Combined with the orchestrator's strict
    whole-text revert on any failed safety check, this could silently
    collapse compression output to 0% reduction on dense notes.
  - Removed `fastapi`, `uvicorn`, `pytest`, `pytest-cov`, `ruff`, and
    `mypy` from core `dependencies`; they belong only in the `ui` and
    `dev` optional extras and should not be required for a base install.

  ## [0.1.0] - 2026-07-06

### Added

- Initial release.
- Deterministic protection layer detecting five categories of clinically
  load-bearing text: negations, values, allergies, laterality, and
  temporal markers.
- Deterministic compression layer (whitespace collapsing, duplicate
  sentence removal, filler-phrase removal, low-information sentence
  pruning) that never alters protected spans.
- Optional LLM-assisted compression for unprotected spans (requires an
  API key; the package works fully without one).
- Deterministic verification layer with five safety checks, including
  explicit detection of negation flips (e.g. "denies chest pain" ->
  "chest pain").
- Strict orchestrator (`compress(..., strict=True)`) that reverts any
  compression which fails a safety check, guaranteeing no lost or
  reversed clinical meaning in the output.
- `clinicalcompress run` and `clinicalcompress check` CLI commands.
- Full test suite covering protection, compression, verification, and
  the orchestrator's revert guarantee.
- FastAPI + vanilla JS demo UI (`webui/`) with a side-by-side
  original / naive / safe comparison.
