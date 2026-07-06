"""The verification layer: the credibility core of clinicalcompress.

`verify()` runs deterministic checks that confirm every protected
clinical meaning from the source text survives, unaltered and
unreversed, in the compressed text. If a check fails, the orchestrator
in `api.py` reverts the affected span to source text and re-verifies —
compressed output that fails `negation_preserved` or `no_meaning_reversal`
must never be returned when `strict=True`.

Copyright 2026 Anurag Chatterjee
Licensed under the Apache License, Version 2.0.
"""

from __future__ import annotations

import regex as re

from clinicalcompress.models import ProtectedSpan, SafetyCheck, SafetyReport, SpanCategory


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _contains(haystack: str, needle: str) -> bool:
    """Check whether `needle` appears in `haystack` as a whole word/phrase,
    not merely as a substring. Plain substring matching would let a short
    cue like "no" falsely match inside an unrelated word like "known" or
    "note", which could let a genuinely dropped negation slip past
    verification undetected."""
    if not needle.strip():
        return True
    normalized_needle = _normalize(needle)
    normalized_haystack = _normalize(haystack)
    pattern = r"(?<!\w)" + re.escape(normalized_needle) + r"(?!\w)"
    return re.search(pattern, normalized_haystack) is not None


def _governed_term_present(compressed: str, governed_term: str) -> bool:
    if not governed_term:
        return True
    words = [w.strip(",.;:") for w in governed_term.split() if w.strip(",.;:")]
    if not words:
        return True
    normalized_compressed = _normalize(compressed)
    hits = sum(1 for w in words if _contains(normalized_compressed, w.lower()))
    return hits >= max(1, len(words) // 2)


def _check_negation_preserved(original: str, compressed: str, spans: list[ProtectedSpan]) -> list[SafetyCheck]:
    """A negation cue is a protected span: it must always survive
    compression verbatim, regardless of whether its governed term also
    survives. Dropping an entire negated clause (cue AND governed term)
    is a loss of clinical meaning just as much as dropping the cue alone
    while keeping the governed term (which flips the meaning outright) —
    both are guarded against here so compression can never silently
    discard what a clinician documented as absent/ruled out.
    """
    checks: list[SafetyCheck] = []
    for span in spans:
        if span.category != SpanCategory.NEGATION:
            continue
        cue_present = _contains(compressed, span.text)
        governed_present = _governed_term_present(compressed, span.governs or "")
        if cue_present:
            checks.append(
                SafetyCheck(
                    name="negation_preserved",
                    passed=True,
                    detail=f"Negation cue '{span.text}' preserved in the output.",
                    span=span,
                )
            )
        elif governed_present:
            checks.append(
                SafetyCheck(
                    name="negation_preserved",
                    passed=False,
                    detail=(
                        f"Negation cue '{span.text}' was dropped while its governed "
                        f"term '{span.governs}' survived in the output — this flips "
                        "clinical meaning."
                    ),
                    span=span,
                )
            )
        else:
            checks.append(
                SafetyCheck(
                    name="negation_preserved",
                    passed=False,
                    detail=(
                        f"Negation cue '{span.text}' and its governed term "
                        f"'{span.governs}' were both dropped from the output — the "
                        "negated finding was lost entirely, not just its wording."
                    ),
                    span=span,
                )
            )
    return checks


def _check_values_intact(original: str, compressed: str, spans: list[ProtectedSpan]) -> list[SafetyCheck]:
    checks: list[SafetyCheck] = []
    for span in spans:
        if span.category != SpanCategory.VALUE:
            continue
        passed = span.text.strip() in compressed
        checks.append(
            SafetyCheck(
                name="values_intact",
                passed=passed,
                detail=(
                    f"Value '{span.text}' present unchanged in output."
                    if passed
                    else f"Value '{span.text}' is missing or was altered in the output."
                ),
                span=span,
            )
        )
    return checks


def _check_allergies_preserved(original: str, compressed: str, spans: list[ProtectedSpan]) -> list[SafetyCheck]:
    checks: list[SafetyCheck] = []
    for span in spans:
        if span.category != SpanCategory.ALLERGY:
            continue
        passed = _contains(compressed, span.text)
        checks.append(
            SafetyCheck(
                name="allergies_preserved",
                passed=passed,
                detail=(
                    f"Allergy statement '{span.text}' present in output."
                    if passed
                    else f"Allergy statement '{span.text}' is missing from the output."
                ),
                span=span,
            )
        )
    return checks


def _check_laterality_preserved(original: str, compressed: str, spans: list[ProtectedSpan]) -> list[SafetyCheck]:
    checks: list[SafetyCheck] = []
    for span in spans:
        if span.category != SpanCategory.LATERALITY:
            continue
        cue_present = _contains(compressed, span.text)
        referent_present = _governed_term_present(compressed, span.governs or "")
        passed = cue_present and referent_present
        checks.append(
            SafetyCheck(
                name="laterality_preserved",
                passed=passed,
                detail=(
                    f"Laterality '{span.text}' preserved with its referent."
                    if passed
                    else f"Laterality '{span.text}' or its referent '{span.governs}' was dropped."
                ),
                span=span,
            )
        )
    return checks


def _check_no_meaning_reversal(original: str, compressed: str, spans: list[ProtectedSpan]) -> list[SafetyCheck]:
    """Specifically check that no term negated in the source appears
    un-negated (positive) in the output — the "denies chest pain" ->
    "chest pain" flip case."""
    checks: list[SafetyCheck] = []
    for span in spans:
        if span.category != SpanCategory.NEGATION or not span.governs:
            continue
        governed_present = _governed_term_present(compressed, span.governs)
        cue_present = _contains(compressed, span.text)
        reversed_meaning = governed_present and not cue_present
        checks.append(
            SafetyCheck(
                name="no_meaning_reversal",
                passed=not reversed_meaning,
                detail=(
                    f"'{span.governs}' does not appear asserted-positive without its negation."
                    if not reversed_meaning
                    else (
                        f"Meaning reversal detected: '{span.text} {span.governs}' became "
                        f"an unqualified positive assertion of '{span.governs}'."
                    )
                ),
                span=span,
            )
        )
    return checks


def verify(original: str, compressed: str, protected_spans: list[ProtectedSpan]) -> SafetyReport:
    """Run every deterministic safety check and return a SafetyReport.

    Args:
        original: The source text before compression.
        compressed: The candidate compressed text to check.
        protected_spans: Spans detected by `protect(original)`.

    Returns:
        A SafetyReport with one SafetyCheck per protected span (across the
        applicable check types) and `all_passed` set accordingly.
    """
    checks: list[SafetyCheck] = []
    checks += _check_negation_preserved(original, compressed, protected_spans)
    checks += _check_values_intact(original, compressed, protected_spans)
    checks += _check_allergies_preserved(original, compressed, protected_spans)
    checks += _check_laterality_preserved(original, compressed, protected_spans)
    checks += _check_no_meaning_reversal(original, compressed, protected_spans)

    all_passed = all(check.passed for check in checks)
    return SafetyReport(checks=checks, all_passed=all_passed, reverted_spans=[])
