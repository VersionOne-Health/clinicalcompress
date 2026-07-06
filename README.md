# clinicalcompress

**Compress clinical text without flipping a negation.**

```
"Patient denies chest pain."  →  a naive compressor drops "denies"  →  "Patient chest pain."
```

That single dropped word turns a normal finding into a medical emergency.
`clinicalcompress` is a deterministic-first Python library that compresses
clinical text for LLM context windows, storage, or transmission — while
guaranteeing that negations, values, allergies, laterality, and temporal
status markers can never be silently lost or reversed.

No API key required. The protection and verification layers are fully
deterministic; LLM-assisted compression is an optional add-on.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)](pyproject.toml)

## Install

```bash
pip install clinicalcompress
```

## Quickstart

```python
from clinicalcompress import compress

note = "Patient denies chest pain. No history of MI. BP 120/80. Allergic to penicillin."
result = compress(note, target_reduction=0.3)

print(result.compressed_text)
print(result.safety.all_passed)   # True — nothing clinically load-bearing was lost
print(result.reduction_pct)       # best-effort token reduction, %
```

Run the built-in demo (no API key needed):

```bash
python examples/quickstart.py
```

It compresses a sample note, then deliberately shows a naive, unsafe
compression dropping a negation — and `verify()` catching the flip.

## The five protected categories

`clinicalcompress` never drops or alters text in these categories, no
matter how aggressive the compression target is:

| Category      | Example                                  |
| ------------- | ----------------------------------------- |
| Negation      | "denies", "no", "ruled out", "without"    |
| Value         | "BP 120/80", "HR 88 bpm", "10 mg"          |
| Allergy       | "Allergic to penicillin", "NKDA"          |
| Laterality    | "left knee", "bilateral", "R) shoulder"   |
| Temporal      | "history of", "chronic", "resolved"       |

## The verification guarantee

This is the whole point of the library. `compress(text, strict=True)`
(the default) runs deterministic safety checks after every compression:

- `negation_preserved` — every negation cue in the source is still
  present and still adjacent to its governed clinical term.
- `values_intact` — every numeric value + unit is present, unchanged.
- `allergies_preserved` — every allergy statement is present.
- `laterality_preserved` — every left/right/bilateral marker is present
  with its referent.
- `no_meaning_reversal` — no term that was negated in the source appears
  as an unqualified positive assertion in the output.

If any check fails, the orchestrator reverts the affected content to the
source text and re-verifies. **With `strict=True`, the result can never
contain a lost negation or a reversed clinical meaning.** This is a
guarantee the test suite enforces directly (see `tests/test_verify.py`
and `tests/test_api.py`).

## Architecture

```
protect()  →  compress_deterministic() [+ optional compress_llm()]  →  verify()  →  (revert if unsafe)
```

- **Protect** (deterministic): scan the source text and mark every
  clinically load-bearing span before any compression happens.
- **Compress** (deterministic by default): remove redundancy — repeated
  whitespace, duplicate sentences, boilerplate filler, low-information
  sentences — from everything *outside* protected spans. LLM-assisted
  compression is optional, only ever touches unprotected spans, and
  silently no-ops without an API key.
- **Verify** (deterministic): confirm every protected span's meaning
  survived. Revert on any failure.

## CLI reference

```bash
# Compress a note and print the safety report
clinicalcompress run --file note.txt --reduction 0.4

# Show what would be protected, without compressing (good for demos)
clinicalcompress check --file note.txt

# Optionally enable LLM-assisted compression of unprotected spans
clinicalcompress run --file note.txt --use-llm
```

## API example

```python
from clinicalcompress import compress
from clinicalcompress.protect import protect

text = "Denies fever. History of asthma. Left knee pain. BP 118/76."

spans = protect(text)
for span in spans:
    print(span.category, span.text, span.governs)

result = compress(text, target_reduction=0.4, use_llm=False, strict=True)
print(result.compressed_text)
print(result.safety.checks)
```

## Disclaimer

`clinicalcompress` is a text-compression utility, not a medical device.
It is not clinically validated and must not be used as the sole basis
for clinical decisions. Always review compressed output before use in
any workflow that affects patient care.

## Live demo

A hosted demo showing the safe compression side-by-side against a
deliberately unsafe naive baseline lives at
[versionone.health/tools/clinicalcompress](https://versionone.health/tools/clinicalcompress).
The same UI can be run locally — see `webui/README.md`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to add a new protected
category, add a detector, and the project's no-PHI rule.

## License

Apache 2.0. See [LICENSE](LICENSE). Copyright 2026 Anurag Chatterjee.
