"""Tests for the orchestrator's strict safety guarantee."""

import re

from clinicalcompress import compress
from clinicalcompress.models import CompressionResult
from clinicalcompress.protect import protect
from clinicalcompress.verify import verify
from tests.fixtures import CLEAN_NOTE, REDUNDANT_NOTE


def test_compress_returns_compression_result():
    result = compress(CLEAN_NOTE)
    assert isinstance(result, CompressionResult)
    assert result.original_text == CLEAN_NOTE
    assert result.compressed_text


def test_token_counts_populated():
    result = compress(CLEAN_NOTE)
    assert result.original_tokens > 0
    assert result.compressed_tokens > 0
    assert isinstance(result.reduction_pct, float)


def test_strict_mode_never_loses_a_negation():
    """Even when the deterministic compressor is pushed hard (high target
    reduction), strict=True must never return text where a negation was
    lost or reversed relative to the source."""
    text = "Patient denies chest pain, shortness of breath, and fever today. " * 1
    result = compress(text, target_reduction=0.9, strict=True)

    spans = protect(text)
    report = verify(text, result.compressed_text, spans)
    assert report.all_passed
    for span in spans:
        if span.category.value == "negation":
            assert span.text in result.compressed_text


def test_strict_mode_reverts_on_forced_unsafe_compression(monkeypatch):
    """Simulate a compressor that strips negations, and confirm the
    strict orchestrator's revert path restores safety."""
    import clinicalcompress.api as api_module

    def unsafe_compress_deterministic(text, protected_spans, target_reduction):
        stripped = re.sub(r"\bdenies\b", "", text, flags=re.IGNORECASE)
        from clinicalcompress.compress import CompressionTrace

        return stripped, CompressionTrace()

    monkeypatch.setattr(api_module, "compress_deterministic", unsafe_compress_deterministic)

    text = "Patient denies chest pain."
    result = api_module.compress(text, strict=True)

    assert "denies" in result.compressed_text.lower()
    assert result.safety.all_passed
    assert result.safety.reverted_spans


def test_non_strict_mode_can_return_unsafe_output(monkeypatch):
    """Sanity check: strict=False intentionally skips the revert path so
    callers who explicitly opt out get the raw (possibly unsafe) result."""
    import clinicalcompress.api as api_module

    def unsafe_compress_deterministic(text, protected_spans, target_reduction):
        stripped = re.sub(r"\bdenies\b", "", text, flags=re.IGNORECASE)
        from clinicalcompress.compress import CompressionTrace

        return stripped, CompressionTrace()

    monkeypatch.setattr(api_module, "compress_deterministic", unsafe_compress_deterministic)

    text = "Patient denies chest pain."
    result = api_module.compress(text, strict=False)

    assert not result.safety.all_passed


def test_compress_on_redundant_note_reduces_size():
    result = compress(REDUNDANT_NOTE, target_reduction=0.3)
    assert result.compressed_tokens <= result.original_tokens
    assert result.safety.all_passed
