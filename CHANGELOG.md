# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
