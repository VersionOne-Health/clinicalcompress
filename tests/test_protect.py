"""Tests for the deterministic protection layer."""

from clinicalcompress.models import SpanCategory
from clinicalcompress.protect import (
    detect_allergies,
    detect_laterality,
    detect_negations,
    detect_temporal,
    detect_values,
    protect,
)


def test_detect_negations_basic():
    spans = detect_negations("Patient denies chest pain.")
    assert len(spans) == 1
    assert spans[0].category == SpanCategory.NEGATION
    assert spans[0].text.lower() == "denies"
    assert "chest pain" in (spans[0].governs or "")


def test_detect_negations_captures_governed_term():
    spans = detect_negations("No history of MI.")
    assert len(spans) == 1
    assert spans[0].governs == "history of MI"


def test_detect_negations_multiple_cues():
    text = "Denies fever. No history of MI. Ruled out pneumonia."
    spans = detect_negations(text)
    cues = {s.text.lower() for s in spans}
    assert "denies" in cues
    assert "no" in cues
    assert "ruled out" in cues


def test_detect_values_blood_pressure():
    spans = detect_values("BP 120/80 today.")
    assert any("120/80" in s.text for s in spans)


def test_detect_values_dose_and_unit():
    spans = detect_values("Continue lisinopril 10 mg daily.")
    assert any("10 mg" in s.text for s in spans)


def test_detect_values_vitals():
    spans = detect_values("HR 88 bpm, SpO2 97%, Temp 98.6.")
    texts = [s.text for s in spans]
    assert any("HR 88" in t or "88 bpm" in t for t in texts)
    assert any("97%" in t for t in texts)


def test_detect_allergies_phrase():
    spans = detect_allergies("Allergic to penicillin.")
    assert len(spans) >= 1
    assert any("penicillin" in (s.governs or s.text) for s in spans)


def test_detect_allergies_nkda():
    spans = detect_allergies("NKDA.")
    assert any(s.text.upper() == "NKDA" for s in spans)


def test_detect_laterality():
    spans = detect_laterality("Left knee pain, right shoulder stable.")
    assert len(spans) == 2
    categories = {s.category for s in spans}
    assert categories == {SpanCategory.LATERALITY}


def test_detect_temporal():
    spans = detect_temporal("History of hypertension. Chronic back pain. Resolved infection.")
    cues = {s.text.lower() for s in spans}
    assert "history of" in cues
    assert "chronic" in cues
    assert "resolved" in cues


def test_protect_combines_all_categories():
    text = "Denies chest pain. History of MI. BP 120/80. Allergic to penicillin. Left knee pain."
    spans = protect(text)
    categories = {s.category for s in spans}
    assert SpanCategory.NEGATION in categories
    assert SpanCategory.TEMPORAL in categories
    assert SpanCategory.VALUE in categories
    assert SpanCategory.ALLERGY in categories
    assert SpanCategory.LATERALITY in categories


def test_protect_spans_sorted_by_offset():
    text = "BP 120/80. Denies chest pain."
    spans = protect(text)
    starts = [s.start for s in spans]
    assert starts == sorted(starts)
