"""``bbh-ld7.v3`` — the deterministic programmatic scorer ratified in revisions 13-15
of ``docs/architecture/WORKFLOW_FIT_PILOT_4C_COMMISSIONING_NOTE.md``.

``SCORING_PROCEDURE_TEXT`` below is the **normative preimage**, reproduced verbatim; it
is the single shared constant, and the module refuses to import if its byte length or
digest ever drifts from the recorded values. The implementation follows that text and
nothing else: ASCII-only case folding and upper-casing (never ``str.upper()``, which
maps characters outside A-Z), U+000A line splitting, the six-character WHITESPACE set,
one balanced parenthesis pair, and a payload of exactly one code point in A-G.

The scorer receives a case digest and a final response. It never receives the query, and
its expected answers come only from scorer-side custody keyed by case digest.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Dict, Mapping

from ugence_jcs import canonical_sha256_hex

SCORING_PROCEDURE_ID = "bbh-ld7.v3"

SCORING_PROCEDURE_TEXT = (
    'bbh-ld7.v3: LINES. Split the final response on U+000A only; from each line remove a single trailing U+000D '
    'if present. WHITESPACE means exactly the six characters U+0009, U+000A, U+000B, U+000C, U+000D and U+0020; '
    'no other character is whitespace for this procedure. SELECTION. A line is prefix-bearing when, after '
    "removing leading and trailing WHITESPACE, it begins with the seven characters 'ANSWER:' compared using ASCII "
    'case folding only (A-Z to a-z; no other case mapping). If the response contains no prefix-bearing line the '
    "score is Decimal('0'). Otherwise select the LAST prefix-bearing line in the response; never fall back to any "
    "earlier line, even when the selected line's payload is malformed. NORMALIZATION. Take the selected line's "
    'text after the prefix; replace every maximal run of WHITESPACE with a single U+0020; remove leading and '
    "trailing U+0020; if and only if the result both begins with '(' and ends with ')', remove exactly one "
    "leading '(' and exactly one trailing ')'; remove leading and trailing U+0020 again; map ASCII lowercase a-z "
    'to uppercase A-Z and change nothing else. The normalized payload must be exactly one character and that '
    'character must be one of A B C D E F G, compared by Unicode code point; any non-ASCII character, including '
    'visually similar ones, fails this test. EXPECTED. Normalize the upstream target with the identical steps, so '
    "an upstream '(B)' normalizes to 'B'. SCORE. Return Decimal('1') when the normalized payload and the "
    "normalized expected value are equal as code-point sequences, and Decimal('0') in every other case, including "
    'a failed payload test. No partial credit. No semantic judgment. No prose fallback. No inspection of the case '
    'query.'
)

SCORING_PROCEDURE_BYTE_LENGTH = 1704
SCORING_PROCEDURE_DIGEST = "9cc587889c5b43dbc1f6ae796840d6af90cfe95c0e6e49cbe245f2ca5dfc1813"

ONE = Decimal("1")
ZERO = Decimal("0")

_PREFIX = "ANSWER:"
_WHITESPACE = frozenset("\t\n\v\f\r ")
_PERMITTED_LETTERS = frozenset("ABCDEFG")
_CASE_DIGEST_LENGTH = 64
_HEX = frozenset("0123456789abcdef")


class ScorerConstructionError(ValueError):
    """The scorer's custody mapping is not the shape the procedure requires."""


class ScorerCustodyError(KeyError):
    """No expected answer is held for the case digest presented at scoring time."""


def _guard_procedure_text() -> None:
    length = len(SCORING_PROCEDURE_TEXT.encode("utf-8"))
    digest = canonical_sha256_hex(SCORING_PROCEDURE_TEXT)
    if length != SCORING_PROCEDURE_BYTE_LENGTH or digest != SCORING_PROCEDURE_DIGEST:
        raise AssertionError(
            "the normative bbh-ld7.v3 procedure text has drifted: "
            f"{length} bytes, digest {digest}"
        )


_guard_procedure_text()


def _ascii_upper(text: str) -> str:
    """Upper-case a-z only. ``str.upper()`` also maps non-ASCII characters, which the
    procedure forbids."""
    return "".join(chr(ord(c) - 32) if "a" <= c <= "z" else c for c in text)


def _ascii_lower(text: str) -> str:
    return "".join(chr(ord(c) + 32) if "A" <= c <= "Z" else c for c in text)


def _strip_whitespace(text: str) -> str:
    start, end = 0, len(text)
    while start < end and text[start] in _WHITESPACE:
        start += 1
    while end > start and text[end - 1] in _WHITESPACE:
        end -= 1
    return text[start:end]


def _collapse_whitespace(text: str) -> str:
    out, in_run = [], False
    for ch in text:
        if ch in _WHITESPACE:
            in_run = True
            continue
        if in_run and out:
            out.append(" ")
        in_run = False
        out.append(ch)
    return "".join(out)


def _lines(response: str) -> list:
    return [line[:-1] if line.endswith("\r") else line for line in response.split("\n")]


def normalize_payload(text: str) -> str:
    """The NORMALIZATION steps of the procedure, in order."""
    payload = _strip_whitespace(_collapse_whitespace(text)).strip(" ")
    if len(payload) >= 2 and payload.startswith("(") and payload.endswith(")"):
        payload = payload[1:-1]
    return _ascii_upper(payload.strip(" "))


def extract_answer(response: str) -> str:
    """The SELECTION steps: the last prefix-bearing line's normalized payload, or the
    empty string when no line carries the prefix. There is no fallback to an earlier
    line when the last one is malformed — the malformed payload is returned as it is."""
    lowered_prefix = _ascii_lower(_PREFIX)
    selected = None
    for line in _lines(response):
        stripped = _strip_whitespace(line)
        if _ascii_lower(stripped[: len(_PREFIX)]) == lowered_prefix:
            selected = stripped[len(_PREFIX) :]
    if selected is None:
        return ""
    return normalize_payload(selected)


def _is_permitted_letter(value: str) -> bool:
    return len(value) == 1 and value in _PERMITTED_LETTERS


class BbhLd7Scorer:
    """A ``QualityScorerPort``: ``score(case_digest, response) -> Decimal``.

    Construction validates the whole custody mapping, so a malformed expected answer is
    refused before any run rather than silently scoring every case zero."""

    procedure_id = SCORING_PROCEDURE_ID
    procedure_digest = SCORING_PROCEDURE_DIGEST

    def __init__(self, expected_by_case_digest: Mapping[str, str]) -> None:
        if not isinstance(expected_by_case_digest, Mapping):
            raise ScorerConstructionError("expected answers must be supplied as a mapping")
        if not expected_by_case_digest:
            raise ScorerConstructionError("the custody mapping must not be empty")
        normalized: Dict[str, str] = {}
        for case_digest, expected in expected_by_case_digest.items():
            if not isinstance(case_digest, str) or len(case_digest) != _CASE_DIGEST_LENGTH or not set(case_digest) <= _HEX:
                raise ScorerConstructionError(f"case digest {case_digest!r} is not 64 lowercase hex characters")
            if not isinstance(expected, str):
                raise ScorerConstructionError(f"expected answer for {case_digest} must be a string")
            value = normalize_payload(expected)
            if not _is_permitted_letter(value):
                raise ScorerConstructionError(
                    f"expected answer for {case_digest} does not normalize to exactly one letter A-G"
                )
            normalized[case_digest] = value
        self._expected = normalized

    def score(self, case_digest: str, response: str) -> Decimal:
        if not isinstance(case_digest, str):
            raise ScorerCustodyError("case_digest must be a string")
        if not isinstance(response, str):
            raise TypeError("response must be a string")
        try:
            expected = self._expected[case_digest]
        except KeyError:
            raise ScorerCustodyError(f"no expected answer is held for case digest {case_digest}") from None
        answer = extract_answer(response)
        if not _is_permitted_letter(answer):
            return ZERO
        return ONE if answer == expected else ZERO


__all__ = [
    "SCORING_PROCEDURE_ID",
    "SCORING_PROCEDURE_TEXT",
    "SCORING_PROCEDURE_BYTE_LENGTH",
    "SCORING_PROCEDURE_DIGEST",
    "ScorerConstructionError",
    "ScorerCustodyError",
    "BbhLd7Scorer",
    "extract_answer",
    "normalize_payload",
]
