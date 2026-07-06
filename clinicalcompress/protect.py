"""The protection layer: deterministic detection of clinically load-bearing
spans that must never be dropped or altered by compression.

Five categories are detected: NEGATION, VALUE, ALLERGY, LATERALITY, and
TEMPORAL. Each detector is a pure function `text -> list[ProtectedSpan]`
so new detectors can be added independently (see CONTRIBUTING.md).

Copyright 2026 Anurag Chatterjee
Licensed under the Apache License, Version 2.0.
"""

from __future__ import annotations

import regex as re

from clinicalcompress.models import ProtectedSpan, SpanCategory

# ---------------------------------------------------------------------------
# Module constants - intentionally extensible. Add new cues/units here
# rather than forking the detector functions. See CONTRIBUTING.md.
# ---------------------------------------------------------------------------

NEGATION_CUES: list[str] = [
    "denies",
    "denied",
    "negative for",
    "absence of",
    "ruled out",
    "free of",
    "without",
    "not",
    "no",
    "nil",
    "neg",
]

VALUE_UNITS: list[str] = [
    "mg/dl",
    "mmol/l",
    "mmhg",
    "mcg",
    "mg",
    "ml",
    "bpm",
    "units",
    "unit",
    "%",
]

VALUE_LABELS: list[str] = ["bp", "hr", "rr", "temp", "spo2", "o2 sat", "sao2"]

ALLERGY_CUES: list[str] = [
    "allergic to",
    "allergy to",
    "allergies to",
    "allerg",
    "nkda",
    "no known drug allergies",
    "no known allergies",
]

LATERALITY_CUES: list[str] = [
    "bilateral",
    "b/l",
    "left",
    "right",
    "l)",
    "r)",
]

TEMPORAL_CUES: list[str] = [
    "history of",
    "h/o",
    "new onset",
    "current",
    "active",
    "discontinued",
    "d/c'd",
    "d/c",
    "resolved",
    "past",
    "prior",
    "chronic",
    "acute",
]

# Governed-term heuristic: how many following words to capture as the
# clinical term a negation/temporal/laterality cue modifies.
_GOVERNED_TERM_WORDS = 4

_WORD_RE = re.compile(r"\S+")


def _capture_governed_term(text: str, after_index: int, max_words: int = _GOVERNED_TERM_WORDS) -> str:
    """Return the next `max_words` whitespace-delimited words after
    `after_index`, stopping at sentence-ending punctuation.

    This is a simple heuristic, not a full noun-phrase parser: it is
    deliberately conservative (captures a few words) so downstream
    verification can check whether the governed term still appears near
    its negation/qualifier after compression.
    """
    remainder = text[after_index:]
    words: list[str] = []
    for match in _WORD_RE.finditer(remainder):
        word = match.group(0).strip(",;:")
        if not word:
            continue
        words.append(word)
        if len(words) >= max_words or word.endswith((".", "!", "?")):
            break
    return " ".join(words).rstrip(".!?")


def _merge_and_dedupe(spans: list[ProtectedSpan]) -> list[ProtectedSpan]:
    """Merge overlapping spans of the same category and drop exact
    duplicates, keeping spans sorted by start offset."""
    if not spans:
        return []
    spans = sorted(spans, key=lambda s: (s.start, s.end))
    merged: list[ProtectedSpan] = [spans[0]]
    for span in spans[1:]:
        last = merged[-1]
        if span.category == last.category and span.start <= last.end:
            if span.end > last.end:
                merged[-1] = ProtectedSpan(
                    text=last.text + span.text[last.end - span.start :],
                    start=last.start,
                    end=span.end,
                    category=last.category,
                    governs=last.governs or span.governs,
                )
            continue
        merged.append(span)
    return merged


def detect_negations(text: str) -> list[ProtectedSpan]:
    """Detect negation cues and the clinical term each one governs.

    Examples:
        >>> [s.text for s in detect_negations("Patient denies chest pain.")]
        ['denies']
        >>> detect_negations("No history of MI.")[0].governs
        'history of MI'

    Word-boundary and case-insensitive matching is used throughout.
    """
    spans: list[ProtectedSpan] = []
    for cue in sorted(NEGATION_CUES, key=len, reverse=True):
        pattern = re.compile(rf"(?<![\w-]){re.escape(cue)}(?![\w-])", re.IGNORECASE)
        for match in pattern.finditer(text):
            governs = _capture_governed_term(text, match.end())
            spans.append(
                ProtectedSpan(
                    text=match.group(0),
                    start=match.start(),
                    end=match.end(),
                    category=SpanCategory.NEGATION,
                    governs=governs or None,
                )
            )
    return _merge_and_dedupe(spans)


_UNITS_ALTERNATION = "|".join(re.escape(u) for u in VALUE_UNITS)

_VALUE_PATTERNS: list[re.Pattern] = [
    # Blood pressure: 120/80
    re.compile(r"\b\d{2,3}/\d{2,3}\b"),
    # Label = value or label value with optional unit, e.g. "HR 88", "SpO2 97%"
    re.compile(
        r"\b(?:{labels})\s*[:=]?\s*\d+(?:\.\d+)?\s*(?:(?:{units})(?!\w))?".format(
            labels="|".join(re.escape(label) for label in VALUE_LABELS),
            units=_UNITS_ALTERNATION,
        ),
        re.IGNORECASE,
    ),
    # Bare numeric value with a unit, e.g. "500 mg", "10 units", "97%"
    re.compile(
        r"\b\d+(?:\.\d+)?\s?(?:{units})(?!\w)".format(units=_UNITS_ALTERNATION),
        re.IGNORECASE,
    ),
    # Lab value "X = N"
    re.compile(r"\b[A-Za-z][\w\s]{0,15}=\s*\d+(?:\.\d+)?\b"),
]


def detect_values(text: str) -> list[ProtectedSpan]:
    """Detect numeric clinical values with optional units/labels.

    Covers blood pressure (120/80), vitals (HR/RR/Temp/SpO2), lab values
    ("X = N"), and medication doses ("500 mg", "10 units").

    Examples:
        >>> [s.text for s in detect_values("BP 120/80, HR 88 bpm.")]
        ['BP 120/80', 'HR 88 bpm']
    """
    spans: list[ProtectedSpan] = []
    for pattern in _VALUE_PATTERNS:
        for match in pattern.finditer(text):
            spans.append(
                ProtectedSpan(
                    text=match.group(0).strip(),
                    start=match.start(),
                    end=match.end(),
                    category=SpanCategory.VALUE,
                )
            )
    return _merge_and_dedupe(spans)


def detect_allergies(text: str) -> list[ProtectedSpan]:
    """Detect allergy statements and the substance named.

    Examples:
        >>> [s.text for s in detect_allergies("Allergic to penicillin.")]
        ['Allergic to penicillin']
        >>> [s.text for s in detect_allergies("NKDA.")]
        ['NKDA']
    """
    spans: list[ProtectedSpan] = []
    phrase_cues = ["allergic to", "allergy to", "allergies to"]
    for cue in phrase_cues:
        pattern = re.compile(rf"\b{re.escape(cue)}\s+([A-Za-z][\w\-]*(?:\s+[A-Za-z][\w\-]*)?)", re.IGNORECASE)
        for match in pattern.finditer(text):
            substance = match.group(1).rstrip(".,;:")
            end = match.start(1) + len(substance)
            spans.append(
                ProtectedSpan(
                    text=text[match.start() : end],
                    start=match.start(),
                    end=end,
                    category=SpanCategory.ALLERGY,
                    governs=substance,
                )
            )
    standalone_cues = ["no known drug allergies", "no known allergies", "nkda"]
    for cue in standalone_cues:
        pattern = re.compile(rf"(?<![\w-]){re.escape(cue)}(?![\w-])", re.IGNORECASE)
        for match in pattern.finditer(text):
            spans.append(
                ProtectedSpan(
                    text=match.group(0),
                    start=match.start(),
                    end=match.end(),
                    category=SpanCategory.ALLERGY,
                )
            )
    generic_pattern = re.compile(r"\ballerg\w*\b", re.IGNORECASE)
    for match in generic_pattern.finditer(text):
        already_covered = any(s.start <= match.start() and match.end() <= s.end for s in spans)
        if not already_covered:
            governs = _capture_governed_term(text, match.end())
            spans.append(
                ProtectedSpan(
                    text=match.group(0),
                    start=match.start(),
                    end=match.end(),
                    category=SpanCategory.ALLERGY,
                    governs=governs or None,
                )
            )
    return _merge_and_dedupe(spans)


def detect_laterality(text: str) -> list[ProtectedSpan]:
    """Detect laterality markers (left/right/bilateral) and the term
    they qualify.

    Examples:
        >>> detect_laterality("Left knee pain.")[0].governs
        'knee pain'
    """
    spans: list[ProtectedSpan] = []
    for cue in LATERALITY_CUES:
        pattern = re.compile(rf"(?<![\w-]){re.escape(cue)}(?![\w-])", re.IGNORECASE)
        for match in pattern.finditer(text):
            governs = _capture_governed_term(text, match.end())
            spans.append(
                ProtectedSpan(
                    text=match.group(0),
                    start=match.start(),
                    end=match.end(),
                    category=SpanCategory.LATERALITY,
                    governs=governs or None,
                )
            )
    return _merge_and_dedupe(spans)


def detect_temporal(text: str) -> list[ProtectedSpan]:
    """Detect temporal/status markers (history of, active, resolved, etc.)
    and the term they qualify.

    Examples:
        >>> detect_temporal("History of MI.")[0].governs
        'MI'
    """
    spans: list[ProtectedSpan] = []
    for cue in sorted(TEMPORAL_CUES, key=len, reverse=True):
        pattern = re.compile(rf"(?<![\w-]){re.escape(cue)}(?![\w-])", re.IGNORECASE)
        for match in pattern.finditer(text):
            governs = _capture_governed_term(text, match.end())
            spans.append(
                ProtectedSpan(
                    text=match.group(0),
                    start=match.start(),
                    end=match.end(),
                    category=SpanCategory.TEMPORAL,
                    governs=governs or None,
                )
            )
    return _merge_and_dedupe(spans)


def protect(text: str) -> list[ProtectedSpan]:
    """Run every detector over `text` and return the combined, deduped,
    merged list of protected spans, sorted by position.

    This is the single entry point the rest of the pipeline should use.

    Args:
        text: The clinical text to scan.

    Returns:
        All detected ProtectedSpan instances, sorted by start offset.
    """
    all_spans = (
        detect_negations(text)
        + detect_values(text)
        + detect_allergies(text)
        + detect_laterality(text)
        + detect_temporal(text)
    )
    return sorted(all_spans, key=lambda s: (s.start, s.end))
