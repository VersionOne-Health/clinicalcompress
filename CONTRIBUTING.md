# Contributing to clinicalcompress

Thanks for considering a contribution. This project's credibility rests
entirely on its safety guarantee, so contributions that touch `protect.py`
or `verify.py` get extra scrutiny — that's expected, not a bad sign.

## Adding a new protected-token category

1. Add the category to `SpanCategory` in `clinicalcompress/models.py`.
2. Add a `detect_<category>(text) -> list[ProtectedSpan]` function to
   `clinicalcompress/protect.py`, following the existing detectors as a
   template. Keep cue lists as module-level constants (e.g.
   `NEGATION_CUES`) so they're easy to extend without touching detector
   logic.
3. Wire your detector into `protect()`.
4. Add corresponding checks to `clinicalcompress/verify.py` if the new
   category needs its own safety check (most categories should).
5. Add tests to `tests/test_protect.py` and `tests/test_verify.py`
   covering at least: a positive detection case, a case where the term
   the span governs is captured correctly, and a case where dropping the
   span should fail verification.

## Adding a new detector to an existing category

Extend the relevant module constant (e.g. add a new phrase to
`NEGATION_CUES` in `protect.py`) rather than writing a parallel detector
function. Add a regression test showing the new cue is detected.

## The no-PHI rule

This repository must never contain real patient data. All sample notes,
test fixtures, and demo text must be obviously synthetic (fake names,
fake identifiers, clearly fictional scenarios). CI runs a grep-based
guard against common real-PHI-looking patterns; do not weaken or remove
it without discussion.

## Code style

- Python 3.9+ compatible. Type-hint all public functions.
- Docstrings on every public function/class, with at least one example
  for detector functions.
- Formatting and linting via `ruff` (`make lint`).
- Prefer pure functions in `protect.py`, `compress.py`, and `verify.py` —
  no hidden state, no I/O.

## Pull request process

1. Fork and branch from `main`.
2. Add or update tests for any behavior change.
3. Run `make test` and `make lint` locally; both must pass.
4. Open a PR describing the change and, if relevant, which protected
   category or safety check it affects.
5. Be prepared to discuss any change to `verify.py`'s safety checks in
   detail — regressions there are the most serious kind of bug this
   project can ship.
