"""Quickstart: no API key required.

Run with `python examples/quickstart.py` or `make run-example`.

This script:
    1. Compresses a synthetic clinical note with clinicalcompress and
       prints the result plus its safety report.
    2. Shows a deliberately BROKEN naive compression (drops the word
       "no") and demonstrates verify() catching the meaning flip.

Copyright 2026 Anurag Chatterjee
Licensed under the Apache License, Version 2.0.
"""

from __future__ import annotations

from clinicalcompress import compress
from clinicalcompress.protect import protect
from clinicalcompress.verify import verify

SAMPLE_NOTE = (
    "Patient denies chest pain. No history of MI. BP 120/80. "
    "Allergic to penicillin."
)


def run_safe_compression() -> None:
    print("=" * 70)
    print("1. Safe compression with clinicalcompress")
    print("=" * 70)
    print(f"\nOriginal:\n  {SAMPLE_NOTE}\n")

    result = compress(SAMPLE_NOTE, target_reduction=0.3)

    print(f"Compressed:\n  {result.compressed_text}\n")
    print(f"Tokens: {result.original_tokens} -> {result.compressed_tokens} "
          f"({result.reduction_pct}% reduction)\n")

    print("Safety report:")
    for check in result.safety.checks:
        status = "PASS" if check.passed else "FAIL"
        print(f"  [{status}] {check.name}: {check.detail}")

    print(f"\nAll checks passed: {result.safety.all_passed}")
    if result.safety.reverted_spans:
        print(f"Reverted spans: {result.safety.reverted_spans}")


def run_naive_compression_flip_demo() -> None:
    print("\n" + "=" * 70)
    print("2. Deliberately unsafe naive compression (the flip this exists to catch)")
    print("=" * 70)

    naive_broken_output = SAMPLE_NOTE.replace("denies chest pain", "chest pain")
    print(f"\nOriginal:\n  {SAMPLE_NOTE}")
    print(f"\nNaive 'compression' (a generic compressor dropped the negation):"
          f"\n  {naive_broken_output}\n")

    protected_spans = protect(SAMPLE_NOTE)
    report = verify(SAMPLE_NOTE, naive_broken_output, protected_spans)

    print("verify() result on the naive output:")
    for check in report.checks:
        status = "PASS" if check.passed else "FAIL"
        marker = " <-- CAUGHT THE FLIP" if not check.passed else ""
        print(f"  [{status}] {check.name}: {check.detail}{marker}")

    assert not report.all_passed, "verify() should have caught the negation flip"
    print("\nverify() correctly flagged the lost negation as UNSAFE.")
    print("clinicalcompress's strict orchestrator would revert this to source")
    print("instead of ever returning the flipped meaning.")


if __name__ == "__main__":
    run_safe_compression()
    run_naive_compression_flip_demo()
