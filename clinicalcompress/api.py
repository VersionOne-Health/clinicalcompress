"""The orchestrator: wires protect -> compress -> verify together and
enforces the strict safety guarantee.

Copyright 2026 Anurag Chatterjee
Licensed under the Apache License, Version 2.0.
"""

from __future__ import annotations

from typing import Optional

from clinicalcompress.compress import compress_deterministic, compress_llm
from clinicalcompress.models import CompressionResult, ProtectedSpan, SafetyReport
from clinicalcompress.protect import protect
from clinicalcompress.tokenizer import count_tokens
from clinicalcompress.verify import verify


def _revert_failed_spans(
    original: str,
    compressed: str,
    protected_spans: list[ProtectedSpan],
    report: SafetyReport,
) -> tuple[str, list[str]]:
    """Revert compressed text to the original for every span whose safety
    checks failed, by reinserting the original span context around the
    governed term. Since the deterministic compressor never edits inside a
    protected span itself, a failed check means context around the span
    (e.g. the negation cue) was dropped by sentence-level pruning — the
    safest correct fix is to fall back to the ORIGINAL full text for that
    guarantee, since we cannot safely graft partial sentences without
    risking a different corruption.
    """
    reverted: list[str] = []
    failed = [c for c in report.checks if not c.passed and c.span is not None]
    if not failed:
        return compressed, reverted

    result = compressed
    for check in failed:
        span = check.span
        assert span is not None
        reverted.append(f"{span.category.value}: '{span.text}' ({check.name})")
        # The span's cue is missing from the compressed text (that's why
        # the check failed). Re-insert the original clinical statement by
        # falling back to the sentence context: since sentence-level
        # granularity is what the compressor operates on, the safest
        # guaranteed-correct action is to fall back to the full original
        # text for this call. This trades some compression for an
        # ironclad safety guarantee.
        result = original
    return result, reverted


def compress(
    text: str,
    *,
    target_reduction: float = 0.4,
    use_llm: bool = False,
    strict: bool = True,
    llm_config: Optional[dict] = None,
) -> CompressionResult:
    """Compress clinical text while guaranteeing protected meaning survives.

    Pipeline:
        1. `protect(text)` identifies clinically load-bearing spans
           (negations, values, allergies, laterality, temporal markers).
        2. `compress_deterministic(...)` removes redundancy from
           unprotected text. If `use_llm=True`, `compress_llm(...)` is
           also applied to unprotected spans (requires an API key;
           silently skipped otherwise).
        3. `verify(...)` runs deterministic safety checks against the
           result.
        4. If `strict=True` (the default) and any check fails, the
           affected content is reverted to source and re-verified.

    Safety guarantee: with `strict=True`, the returned `compressed_text`
    NEVER contains a lost negation or a reversed clinical meaning. This is
    the whole credibility premise of this package — do not disable
    `strict` unless you independently re-verify the output yourself.

    Args:
        text: The clinical text to compress.
        target_reduction: Desired fractional reduction (0-1), best-effort.
        use_llm: Whether to additionally apply LLM-based compression to
            unprotected spans. No-ops without an API key.
        strict: When True (default), revert-and-reverify any failed
            safety check so unsafe output is never returned.
        llm_config: Optional dict passed through to `compress_llm`
            (e.g. `{"api_key": ..., "model": ...}`).

    Returns:
        A CompressionResult with the compressed text, token counts,
        reduction percentage, detected protected spans, and safety report.
    """
    protected_spans = protect(text)

    compressed_text, _trace = compress_deterministic(text, protected_spans, target_reduction)

    used_llm = False
    if use_llm:
        # `protected_spans` holds offsets relative to the ORIGINAL text, but
        # `compress_deterministic` has already changed the text's length and
        # content (whitespace collapsed, sentences dropped, etc). Passing
        # those stale offsets into `compress_llm` would misalign protected
        # boundaries against `compressed_text` and risk sending protected
        # content to the LLM. Since the deterministic compressor guarantees
        # protected span text passes through untouched, re-running
        # `protect()` on `compressed_text` re-detects the same protected
        # content with offsets that are actually valid for it.
        llm_spans = protect(compressed_text)
        compressed_text, used_llm = compress_llm(compressed_text, llm_spans, llm_config)

    report = verify(text, compressed_text, protected_spans)

    if not report.all_passed and strict:
        compressed_text, reverted = _revert_failed_spans(text, compressed_text, protected_spans, report)
        report = verify(text, compressed_text, protected_spans)
        report.reverted_spans = reverted
        if not report.all_passed:
            # Ultimate fallback: source text always passes verification
            # against its own spans trivially, so this branch guarantees
            # `strict=True` never returns unsafe output.
            compressed_text = text
            report = verify(text, compressed_text, protected_spans)
            report.reverted_spans = reverted or ["full text reverted to source"]

    original_tokens = count_tokens(text)
    compressed_tokens = count_tokens(compressed_text)
    reduction_pct = 0.0
    if original_tokens > 0:
        reduction_pct = round((1 - (compressed_tokens / original_tokens)) * 100, 2)

    return CompressionResult(
        original_text=text,
        compressed_text=compressed_text,
        original_tokens=original_tokens,
        compressed_tokens=compressed_tokens,
        reduction_pct=reduction_pct,
        protected_spans=protected_spans,
        safety=report,
    )
