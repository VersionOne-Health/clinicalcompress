"""Lightweight token estimation.

This is NOT a model tokenizer (e.g. it does not replicate BPE/GPT/Claude
tokenization). It is a fast, dependency-light approximation used only to
report before/after token counts and a reduction percentage. If `tiktoken`
is installed, it is used for a closer approximation of common LLM
tokenizers; otherwise a regex-based word/punctuation splitter is used.

Copyright 2026 Anurag Chatterjee
Licensed under the Apache License, Version 2.0.
"""

from __future__ import annotations

import re

_WORD_OR_PUNCT = re.compile(r"\w+|[^\w\s]", re.UNICODE)

try:
    import tiktoken as _tiktoken

    _ENCODING = _tiktoken.get_encoding("cl100k_base")
except Exception:  # pragma: no cover - exercised only when tiktoken absent
    _ENCODING = None


def count_tokens(text: str) -> int:
    """Estimate the number of tokens in `text`.

    Uses `tiktoken`'s cl100k_base encoding when available for a closer
    approximation of real LLM tokenizers. Falls back to a simple regex
    split on word and punctuation boundaries. Either way, this is an
    estimate, not an exact count for any specific model.

    Args:
        text: The text to estimate token count for.

    Returns:
        The estimated number of tokens. Empty or whitespace-only text
        returns 0.
    """
    if not text or not text.strip():
        return 0
    if _ENCODING is not None:
        return len(_ENCODING.encode(text))
    return len(_WORD_OR_PUNCT.findall(text))
