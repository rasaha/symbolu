"""Exact-output parser / classifier for the unseen-identifier diagnostic.

Classifies a raw model output into exactly one category, per example context. No post-processing
silently repairs a malformed identifier; no constrained decoding. The parser is a pure function of
(raw output, example).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .config import ABSTENTION_TOKEN, IDENTIFIER_ALPHABET, IDENTIFIER_LENGTH
from .tasks import Example


class OutputCategory(str, Enum):
    EXACT_CORRECT = "exact_correct"
    TOKEN_PARTIAL = "token_partial"          # right length/alphabet, wrong value, partial char overlap
    MALFORMED = "malformed"                  # not a valid identifier and not the abstention token
    WRONG_IN_CONTEXT = "wrong_in_context"    # a valid identifier present in context but not the answer
    FABRICATED_OUT_OF_CONTEXT = "fabricated_out_of_context"  # valid identifier not present in context
    CORRECT_ABSTENTION = "correct_abstention"
    FALSE_ABSTENTION = "false_abstention"    # abstained when an answer was expected


@dataclass(frozen=True)
class ParseResult:
    category: OutputCategory
    normalized: str


def _is_wellformed_id(text: str) -> bool:
    return len(text) == IDENTIFIER_LENGTH and all(ch in IDENTIFIER_ALPHABET for ch in text)


def parse(raw: str, example: Example) -> ParseResult:
    """Classify `raw` against the example's gold output and context (no repair)."""
    text = raw.strip()
    context = set(example.context_ids)

    if example.expected_abstention:
        if text == ABSTENTION_TOKEN:
            return ParseResult(OutputCategory.CORRECT_ABSTENTION, text)
        if _is_wellformed_id(text):
            # answered instead of abstaining: still classify in/out of context for the false-answer rate
            cat = OutputCategory.WRONG_IN_CONTEXT if text in context else OutputCategory.FABRICATED_OUT_OF_CONTEXT
            return ParseResult(cat, text)
        return ParseResult(OutputCategory.MALFORMED, text)

    # answer expected
    if text == ABSTENTION_TOKEN:
        return ParseResult(OutputCategory.FALSE_ABSTENTION, text)
    if text == example.expected_output:
        return ParseResult(OutputCategory.EXACT_CORRECT, text)
    if not _is_wellformed_id(text):
        return ParseResult(OutputCategory.MALFORMED, text)
    if text in context:
        return ParseResult(OutputCategory.WRONG_IN_CONTEXT, text)
    # well-formed, not in context, not correct: fabricated (with a token-partial nuance)
    overlap = sum(1 for a, b in zip(text, example.expected_output) if a == b)
    if overlap >= 1:
        return ParseResult(OutputCategory.TOKEN_PARTIAL, text)
    return ParseResult(OutputCategory.FABRICATED_OUT_OF_CONTEXT, text)
