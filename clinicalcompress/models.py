"""Data models shared across the protect / compress / verify pipeline.

Copyright 2026 Anurag Chatterjee
Licensed under the Apache License, Version 2.0.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class SpanCategory(str, Enum):
    """The five categories of clinically load-bearing text that must never
    be dropped or altered during compression."""

    NEGATION = "negation"
    VALUE = "value"
    ALLERGY = "allergy"
    LATERALITY = "laterality"
    TEMPORAL = "temporal"


@dataclass(frozen=True)
class ProtectedSpan:
    """A span of text identified as clinically load-bearing.

    Attributes:
        text: The exact substring from the source text.
        start: Start character offset in the source text (inclusive).
        end: End character offset in the source text (exclusive).
        category: Which protection category this span belongs to.
        governs: The clinical term this span modifies or governs, if any.
            For example, in "denies chest pain", a NEGATION span for
            "denies" governs the term "chest pain".
    """

    text: str
    start: int
    end: int
    category: SpanCategory
    governs: Optional[str] = None

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError("ProtectedSpan.end must be >= start")


@dataclass
class SafetyCheck:
    """The result of a single deterministic verification check.

    Attributes:
        name: Machine-readable identifier for the check, e.g.
            "negation_preserved".
        passed: Whether the check passed.
        detail: Human-readable explanation of the result.
        span: The protected span this check pertains to, if applicable.
    """

    name: str
    passed: bool
    detail: str
    span: Optional[ProtectedSpan] = None


@dataclass
class SafetyReport:
    """Aggregated result of running all verification checks.

    Attributes:
        checks: Every individual SafetyCheck that was run.
        all_passed: True only if every check in `checks` passed.
        reverted_spans: Human-readable descriptions of spans that were
            reverted to their source text because a check failed.
    """

    checks: list[SafetyCheck] = field(default_factory=list)
    all_passed: bool = True
    reverted_spans: list[str] = field(default_factory=list)

    @property
    def failed_checks(self) -> list[SafetyCheck]:
        return [c for c in self.checks if not c.passed]


@dataclass
class CompressionResult:
    """The full output of a `compress()` call.

    Attributes:
        original_text: The unmodified source text.
        compressed_text: The compressed (and, if needed, reverted) output.
        original_tokens: Estimated token count of `original_text`.
        compressed_tokens: Estimated token count of `compressed_text`.
        reduction_pct: Percentage reduction in tokens, 0-100.
        protected_spans: Every ProtectedSpan detected in `original_text`.
        safety: The SafetyReport produced by verification.
    """

    original_text: str
    compressed_text: str
    original_tokens: int
    compressed_tokens: int
    reduction_pct: float
    protected_spans: list[ProtectedSpan]
    safety: SafetyReport
