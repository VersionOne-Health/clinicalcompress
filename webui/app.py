"""FastAPI demonstration front end for clinicalcompress.

IMPORTANT: This is a demonstration UI for the library, NOT a production
service. It is stateless — no database, no accounts, no sessions, and no
browser storage. It exists to show, side-by-side, what a deliberately
unsafe naive compressor does versus the real clinicalcompress library.

The `/api/compress` endpoint calls the REAL `clinicalcompress.compress()`
function (strict=True) — this demo shows genuine library behavior, not a
mock. The `/api/naive` endpoint is a DELIBERATELY UNSAFE baseline that
strips low-frequency short tokens (including negations), the way a
generic compressor might, purely to visualize the contrast. It must never
be used for anything beyond this demo.

Run locally with:
    uvicorn webui.app:app --reload --port 8000

Copyright 2026 Anurag Chatterjee
Licensed under the Apache License, Version 2.0.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from clinicalcompress import compress as clinicalcompress_compress
from clinicalcompress.protect import NEGATION_CUES, protect
from clinicalcompress.tokenizer import count_tokens

# The app is served behind a reverse proxy that does NOT rewrite paths, so
# every route must be registered under the same prefix the proxy forwards
# (e.g. "/clinicalcompress-demo"). BASE_PATH defaults to "" for local runs.
BASE_PATH = os.environ.get("BASE_PATH", "").rstrip("/")

app = FastAPI(
    title="clinicalcompress demo",
    description="Demonstration UI for the clinicalcompress library. Not a production service.",
)
router = APIRouter(prefix=BASE_PATH)

_STATIC_DIR = Path(__file__).parent


class CompressRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=20_000)
    target_reduction: float = Field(0.4, ge=0.1, le=0.9)


class NaiveRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=20_000)


@router.get("/")
def index() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html")


@router.post("/api/compress")
def api_compress(payload: CompressRequest) -> dict:
    """Calls the REAL clinicalcompress library, strict=True."""
    result = clinicalcompress_compress(
        payload.text,
        target_reduction=payload.target_reduction,
        strict=True,
    )
    return {
        "original_text": result.original_text,
        "compressed_text": result.compressed_text,
        "original_tokens": result.original_tokens,
        "compressed_tokens": result.compressed_tokens,
        "reduction_pct": result.reduction_pct,
        "protected_spans": [
            {
                "text": span.text,
                "start": span.start,
                "end": span.end,
                "category": span.category.value,
                "governs": span.governs,
            }
            for span in result.protected_spans
        ],
        "safety": {
            "all_passed": result.safety.all_passed,
            "reverted_spans": result.safety.reverted_spans,
            "checks": [
                {
                    "name": check.name,
                    "passed": check.passed,
                    "detail": check.detail,
                    "category": check.span.category.value if check.span else None,
                }
                for check in result.safety.checks
            ],
        },
    }


_NEGATION_PATTERN = re.compile(
    r"(?<![\w-])(?:" + "|".join(re.escape(c) for c in NEGATION_CUES) + r")(?![\w-])",
    re.IGNORECASE,
)
_SHORT_FILLER_WORDS = {"the", "a", "an", "of", "on", "in", "and", "or"}


def _naive_unsafe_compress(text: str) -> tuple[str, list[str]]:
    """DEMO-ONLY unsafe baseline.

    Mimics what a generic, meaning-blind compressor does: it strips
    negation cues and other short, "low-frequency" filler words to save
    tokens, with no awareness that "no"/"denies"/"without" carry the
    entire clinical meaning of the sentence. This function exists SOLELY
    to produce the flipped-meaning contrast for the demo UI and must
    never be used to actually compress clinical text.
    """
    dropped: list[str] = []

    def _strip_negation(match: re.Match) -> str:
        dropped.append(match.group(0))
        return ""

    stripped = _NEGATION_PATTERN.sub(_strip_negation, text)

    words = stripped.split()
    kept_words = []
    for word in words:
        bare = word.strip(".,;:").lower()
        if bare in _SHORT_FILLER_WORDS:
            dropped.append(word)
            continue
        kept_words.append(word)

    naive_output = " ".join(kept_words)
    naive_output = re.sub(r"\s+([.,;:])", r"\1", naive_output)
    naive_output = re.sub(r"\s{2,}", " ", naive_output).strip()
    return naive_output, dropped


def _as_naive_would_render(fragment: str) -> str:
    """Apply the same filler-word stripping the naive compressor uses to a
    standalone fragment (e.g. a governed clinical term), so the result is
    the literal substring that will actually appear in `naive_output` for
    highlighting purposes, instead of the untouched original phrasing.
    """
    kept = [
        word
        for word in fragment.split()
        if word.strip(".,;:").lower() not in _SHORT_FILLER_WORDS
    ]
    return " ".join(kept).strip()


@router.post("/api/naive")
def api_naive(payload: NaiveRequest) -> dict:
    """DEMO-ONLY unsafe baseline endpoint. See `_naive_unsafe_compress`."""
    naive_output, dropped_tokens = _naive_unsafe_compress(payload.text)
    spans = protect(payload.text)

    from clinicalcompress.verify import verify

    report = verify(payload.text, naive_output, spans)

    dropped_lower = {tok.strip(".,;:").lower() for tok in dropped_tokens}
    flipped_terms = sorted(
        {
            rendered
            for span in spans
            if span.category.value == "negation"
            and span.governs
            and span.text.strip(".,;:").lower() in dropped_lower
            and (rendered := _as_naive_would_render(span.governs))
        },
        key=len,
        reverse=True,
    )

    return {
        "naive_text": naive_output,
        "dropped_tokens": dropped_tokens,
        "flipped_terms": flipped_terms,
        "original_tokens": count_tokens(payload.text),
        "naive_tokens": count_tokens(naive_output),
        "meaning_reversed": not report.all_passed,
        "failed_checks": [
            {"name": c.name, "detail": c.detail}
            for c in report.checks
            if not c.passed
        ],
    }


app.include_router(router)
