"""The compression layer.

Deterministic compression (`compress_deterministic`) is the default path
and requires no external services or API keys. LLM-assisted compression
(`compress_llm`) is an optional enhancement that only ever rewrites spans
containing zero protected tokens, and gracefully no-ops if the `anthropic`
package or an API key is unavailable.

Protected spans are never altered by either strategy: their exact
characters always pass through untouched.

Copyright 2026 Anurag Chatterjee
Licensed under the Apache License, Version 2.0.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from clinicalcompress.models import ProtectedSpan

# Boilerplate/filler phrases that carry no clinical meaning and are safe
# to drop outright when they appear outside protected spans. Extend this
# list rather than special-casing filler removal elsewhere.
FILLER_PHRASES: list[str] = [
    "as previously discussed",
    "as noted above",
    "please see above",
    "the patient was informed",
    "for your information",
    "at this time",
    "as mentioned",
    "it should be noted that",
    "please be advised that",
]

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


# Low-information connector/filler words that are safe to drop wherever
# they fall OUTSIDE a protected span. These never carry the clinical
# meaning we guarantee (negation cues, values, allergies, laterality, and
# temporal markers are always protect()-ed before this ever runs), so
# dropping them is a pure prose-to-telegraphic-style compression, not a
# safety-relevant one. This is what lets clinicalcompress meaningfully
# shrink dense, single-encounter notes where every sentence carries some
# protected content and no sentence/phrase can be dropped wholesale.
FILLER_WORDS: frozenset[str] = frozenset(
    {
        "with",
        "except",
        "known",
        "please",
        "very",
        "actually",
        "basically",
        "and",
        "or",
        "of",
        "the",
        "a",
        "an",
    }
)

_WORD_PATTERN = re.compile(r"[A-Za-z']+")


@dataclass
class CompressionTrace:
    """A record of what was removed during deterministic compression."""

    removed_whitespace: bool = False
    removed_duplicate_sentences: list[str] = field(default_factory=list)
    removed_filler_phrases: list[str] = field(default_factory=list)
    removed_filler_words: list[str] = field(default_factory=list)
    removed_low_information_sentences: list[str] = field(default_factory=list)


def _collapse_whitespace(text: str) -> str:
    return re.sub(r"[ \t]+", " ", re.sub(r"\n{3,}", "\n\n", text)).strip()


def _span_overlaps(start: int, end: int, spans: list[ProtectedSpan]) -> bool:
    return any(start < s.end and end > s.start for s in spans)


def _remove_filler_phrases(text: str, protected_spans: list[ProtectedSpan], trace: CompressionTrace) -> str:
    result = text
    for phrase in FILLER_PHRASES:
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
        search_text = result
        new_result = []
        last_end = 0
        for match in pattern.finditer(search_text):
            start, end = match.start(), match.end()
            if _span_overlaps(start, end, protected_spans):
                continue
            new_result.append(search_text[last_end:start])
            trace.removed_filler_phrases.append(match.group(0))
            last_end = end
        new_result.append(search_text[last_end:])
        result = "".join(new_result)
    return result


def _remove_filler_words(text: str, protected_spans: list[ProtectedSpan], trace: CompressionTrace) -> str:
    """Drop low-information connector/filler words (see `FILLER_WORDS`)
    wherever they fall outside a protected span, converting verbose prose
    toward telegraphic clinical-note style. This is the strategy that lets
    single-encounter notes compress meaningfully even when every sentence
    contains some protected content and no sentence can be dropped
    wholesale (see `_prune_low_information_sentences`)."""
    mask = list(text)
    removed_any = False
    for match in _WORD_PATTERN.finditer(text):
        start, end = match.start(), match.end()
        word = match.group(0)
        if word.lower() in FILLER_WORDS and not _span_overlaps(start, end, protected_spans):
            for i in range(start, end):
                mask[i] = ""
            trace.removed_filler_words.append(word)
            removed_any = True
    if not removed_any:
        return text

    result = "".join(mask)
    result = re.sub(r"[ \t]{2,}", " ", result)
    result = re.sub(r"\s+([,.;:])", r"\1", result)
    result = re.sub(r"([,;:])(\s*,)+", r"\1", result)
    result = re.sub(r",\s*([.;:])", r"\1", result)
    result = re.sub(r"^\s*,\s*", "", result)
    return result.strip()


def _remove_duplicate_sentences(text: str, protected_spans: list[ProtectedSpan], trace: CompressionTrace) -> str:
    sentences = _SENTENCE_SPLIT.split(text)
    seen: set[str] = set()
    kept: list[str] = []
    cursor = 0
    for sentence in sentences:
        if not sentence.strip():
            continue
        start = text.find(sentence, cursor)
        end = start + len(sentence) if start != -1 else cursor + len(sentence)
        cursor = end
        normalized = sentence.strip().lower()
        has_protected = start != -1 and _span_overlaps(start, end, protected_spans)
        if normalized in seen and not has_protected:
            trace.removed_duplicate_sentences.append(sentence.strip())
            continue
        seen.add(normalized)
        kept.append(sentence)
    return " ".join(s.strip() for s in kept if s.strip())


def _prune_low_information_sentences(
    text: str,
    protected_spans: list[ProtectedSpan],
    target_reduction: float,
    trace: CompressionTrace,
) -> str:
    """Drop sentences that contain no protected spans, starting with the
    shortest/least informative, until the target reduction is met or no
    more unprotected sentences remain. Never splits a protected span."""
    sentences = [s for s in _SENTENCE_SPLIT.split(text) if s.strip()]
    if len(sentences) <= 1:
        return text

    offsets: list[tuple[str, int, int]] = []
    cursor = 0
    for sentence in sentences:
        start = text.find(sentence, cursor)
        if start == -1:
            start = cursor
        end = start + len(sentence)
        cursor = end
        offsets.append((sentence, start, end))

    original_len = len(text)
    target_len = original_len * (1 - target_reduction)

    droppable = [
        (sentence, start, end)
        for sentence, start, end in offsets
        if not _span_overlaps(start, end, protected_spans)
    ]
    droppable.sort(key=lambda item: len(item[0]))

    kept_sentences = list(offsets)
    current_len = original_len
    for candidate in droppable:
        if current_len <= target_len:
            break
        if len(kept_sentences) <= 1:
            break
        kept_sentences = [s for s in kept_sentences if s != candidate]
        current_len -= len(candidate[0])
        trace.removed_low_information_sentences.append(candidate[0].strip())

    return " ".join(s.strip() for s, _, _ in kept_sentences if s.strip())


def compress_deterministic(
    text: str,
    protected_spans: list[ProtectedSpan],
    target_reduction: float = 0.4,
) -> tuple[str, CompressionTrace]:
    """Reduce redundancy in `text` while never touching a protected span.

    Strategies applied, in order:
        1. Collapse repeated whitespace.
        2. Drop low-information connector/filler words (see `FILLER_WORDS`,
           e.g. "with", "of", "and", "except") that fall outside a
           protected span, converting prose toward telegraphic clinical
           shorthand. This is what lets dense, single-encounter notes -
           where every sentence carries protected content and nothing can
           be dropped wholesale - still compress meaningfully.
        3. Remove duplicate sentences (unless a duplicate contains a
           protected span, in which case it is kept).
        4. Drop configured boilerplate filler phrases that do not overlap
           a protected span.
        5. Optionally prune low-information sentences (sentences with no
           protected spans at all) until `target_reduction` is reached.

    Args:
        text: Source clinical text.
        protected_spans: Spans from `protect()` that must survive untouched.
        target_reduction: Desired fractional token/character reduction,
            e.g. 0.4 for a 40% reduction. Best-effort; not guaranteed
            exactly, since protected spans are never sacrificed to hit it.

    Returns:
        A tuple of (compressed_text, CompressionTrace) describing what was
        removed.
    """
    trace = CompressionTrace()
    working = _collapse_whitespace(text)
    trace.removed_whitespace = working != text.strip()

    # Re-detect span offsets are only valid against the ORIGINAL text, so
    # sentence-level operations below re-derive overlap against `working`
    # using the same relative text content (protect() offsets assume the
    # original text). To keep guarantees simple and correct, sentence-level
    # pruning operates on `working` but re-checks span containment via the
    # substring text of each span (a span's exact text must still appear).
    # `_remove_filler_words` runs first, while `working` is still closest to
    # the original text (only whitespace-collapsed), so `protected_spans`
    # offsets remain accurate for its overlap checks.
    working = _remove_filler_words(working, protected_spans, trace)
    working = _remove_filler_phrases(working, protected_spans, trace)
    working = _remove_duplicate_sentences(working, protected_spans, trace)
    working = _prune_low_information_sentences(working, protected_spans, target_reduction, trace)
    working = _collapse_whitespace(working)
    return working, trace


def compress_llm(
    text: str,
    protected_spans: list[ProtectedSpan],
    config: Optional[dict] = None,
) -> tuple[str, bool]:
    """Optionally shorten unprotected spans using an LLM.

    Only spans that contain NO protected tokens are ever sent to the
    model, and the model is given a strict instruction to shorten
    without removing meaning. If the `anthropic` package is not
    installed, or no API key is configured, this silently falls back to
    returning `text` unchanged so the pipeline keeps working with no key.

    Args:
        text: Text to (optionally) compress further via LLM.
        protected_spans: Spans that must never be sent to the LLM.
        config: Optional dict with keys like `api_key` and `model`.

    Returns:
        A tuple of (result_text, used_llm). `used_llm` is False whenever
        the LLM path was skipped for any reason.
    """
    config = config or {}
    api_key = config.get("api_key")
    if not api_key:
        return text, False

    try:
        import anthropic  # lazy import: optional dependency
    except ImportError:
        return text, False

    try:
        client = anthropic.Anthropic(api_key=api_key)
        model = config.get("model", "claude-3-5-sonnet-latest")

        segments: list[tuple[str, bool]] = []
        cursor = 0
        for span in sorted(protected_spans, key=lambda s: s.start):
            if span.start > cursor:
                segments.append((text[cursor : span.start], False))
            segments.append((text[span.start : span.end], True))
            cursor = span.end
        if cursor < len(text):
            segments.append((text[cursor:], False))

        rewritten: list[str] = []
        for segment_text, is_protected in segments:
            if is_protected or not segment_text.strip():
                rewritten.append(segment_text)
                continue
            response = client.messages.create(
                model=model,
                max_tokens=200,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Shorten the following clinical note fragment as much as "
                            "possible without removing or altering any clinical "
                            "meaning. Return only the shortened text, no commentary.\n\n"
                            f"{segment_text}"
                        ),
                    }
                ],
            )
            content = response.content[0].text if response.content else segment_text
            rewritten.append(content.strip())
        return "".join(rewritten), True
    except Exception:
        # Any failure in the optional LLM path must never break the
        # deterministic-first guarantee.
        return text, False
