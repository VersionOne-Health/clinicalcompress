"""The key tests: verification must catch lost or reversed clinical meaning."""

from clinicalcompress.protect import protect
from clinicalcompress.verify import verify


def test_dropped_negation_fails_negation_preserved():
    original = "Patient denies chest pain."
    compressed = "Patient chest pain."  # negation cue dropped
    spans = protect(original)
    report = verify(original, compressed, spans)

    negation_checks = [c for c in report.checks if c.name == "negation_preserved"]
    assert negation_checks, "Expected at least one negation_preserved check"
    assert not all(c.passed for c in negation_checks)
    assert not report.all_passed


def test_dropped_negated_clause_fails_negation_preserved():
    original = "Patient denies chest pain."
    compressed = "Patient stable."  # entire negated clause dropped, not just reworded
    spans = protect(original)
    report = verify(original, compressed, spans)

    negation_checks = [c for c in report.checks if c.name == "negation_preserved"]
    assert negation_checks, "Expected at least one negation_preserved check"
    assert not all(c.passed for c in negation_checks)
    assert not report.all_passed


def test_denies_chest_pain_to_chest_pain_is_meaning_reversal():
    original = "Patient denies chest pain."
    compressed = "Patient chest pain."
    spans = protect(original)
    report = verify(original, compressed, spans)

    reversal_checks = [c for c in report.checks if c.name == "no_meaning_reversal"]
    assert reversal_checks
    assert not all(c.passed for c in reversal_checks)


def test_dose_change_fails_values_intact():
    original = "Continue lisinopril 10 mg daily."
    compressed = "Continue lisinopril 5 mg daily."  # dose changed
    spans = protect(original)
    report = verify(original, compressed, spans)

    value_checks = [c for c in report.checks if c.name == "values_intact"]
    assert value_checks
    assert not all(c.passed for c in value_checks)
    assert not report.all_passed


def test_clean_compression_passes_all_checks():
    original = "Patient denies chest pain. No history of MI. BP 120/80. Allergic to penicillin."
    compressed = original  # unmodified: everything should pass trivially
    spans = protect(original)
    report = verify(original, compressed, spans)

    assert report.all_passed
    assert all(c.passed for c in report.checks)


def test_allergy_dropped_fails_allergies_preserved():
    original = "Allergic to penicillin. Continue treatment."
    compressed = "Continue treatment."
    spans = protect(original)
    report = verify(original, compressed, spans)

    allergy_checks = [c for c in report.checks if c.name == "allergies_preserved"]
    assert allergy_checks
    assert not all(c.passed for c in allergy_checks)


def test_laterality_dropped_fails_laterality_preserved():
    original = "Left knee pain, stable."
    compressed = "Knee pain, stable."
    spans = protect(original)
    report = verify(original, compressed, spans)

    laterality_checks = [c for c in report.checks if c.name == "laterality_preserved"]
    assert laterality_checks
    assert not all(c.passed for c in laterality_checks)


def test_short_negation_cue_substring_collision_is_not_a_false_positive():
    """Regression test: a short negation cue like "no" must not be treated
    as "present" just because it appears as a substring inside an
    unrelated word (e.g. "no" inside "known"). Naive substring matching
    would let this genuinely-dropped negation slip past verification."""
    original = "No history of MI."
    compressed = "Known history of MI."  # "No" cue actually dropped
    spans = protect(original)
    report = verify(original, compressed, spans)

    negation_checks = [c for c in report.checks if c.name == "negation_preserved"]
    reversal_checks = [c for c in report.checks if c.name == "no_meaning_reversal"]
    assert negation_checks and not all(c.passed for c in negation_checks)
    assert reversal_checks and not all(c.passed for c in reversal_checks)
    assert not report.all_passed


def test_not_cue_substring_collision_is_not_a_false_positive():
    """Same substring-collision class of bug, but for "not" colliding with
    "noted"."""
    original = "Patient is not febrile."
    compressed = "It was noted patient febrile."  # "not" cue actually dropped
    spans = protect(original)
    report = verify(original, compressed, spans)

    negation_checks = [c for c in report.checks if c.name == "negation_preserved"]
    assert negation_checks
    assert not all(c.passed for c in negation_checks)
    assert not report.all_passed


def test_word_boundary_matching_still_accepts_exact_cue_presence():
    """Sanity check: the stricter word-boundary matching must not produce
    false negatives for a negation cue that is genuinely preserved."""
    original = "No history of MI."
    compressed = "No history of MI noted today."
    spans = protect(original)
    report = verify(original, compressed, spans)

    assert report.all_passed
    assert all(c.passed for c in report.checks)
