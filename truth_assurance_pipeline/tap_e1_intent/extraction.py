"""
Deterministic-first extraction (Sections 7 & 8 of the brief).

Pure functions over the raw request text. No randomness, no model. Every element
these functions return retains its source ``Span`` and is tagged with
``DETERMINISTIC_EXTRACTION`` provenance so a downstream stage can prove the value
was actually present in the input (rather than inferred).

Deterministic extractions are AUTHORITATIVE: they must not be silently replaced by
probabilistic interpretation. The interpreter layers a probabilistic (here:
heuristic stand-in) pass *on top of* these, never underneath.

The extractors are intentionally conservative — they only emit an element when a
concrete lexical trigger is present, so precision is favored over recall. Recall
gaps are filled (visibly, with weaker provenance) by the heuristic pass.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

from truth_assurance_pipeline.tap_e1_intent.schema import (
    Constraint, ConstraintPolarity, Provenance, ProvenanceKind, Span,
    TemporalConstraint,
)


# --------------------------------------------------------------------------- #
# Lexicons                                                                    #
# --------------------------------------------------------------------------- #

# Prohibition triggers -> the constraint is a PROHIBITION. Order matters only for
# display; matching is by regex below.
PROHIBITION_TRIGGERS = (
    "do not", "don't", "do n't", "never", "without", "must not", "cannot",
    "can't", "no longer", "avoid", "refrain from", "nothing", "untouched",
    "leave everything",
)
# Requirement triggers -> REQUIREMENT.
REQUIREMENT_TRIGGERS = ("must", "only", "always", "required to", "need to",
                        "has to", "have to", "shall", "ensure", "exactly",
                        "at least", "at most", "no more than", "no less than",
                        "under", "over", "above", "below", "within", "keep",
                        "maintain", "preserve", "intact", "unchanged", "zero")

IMPERATIVE_VERBS = (
    "add", "remove", "delete", "update", "edit", "change", "rewrite", "write",
    "create", "generate", "summarize", "summarise", "compare", "analyze",
    "analyse", "explain", "list", "fix", "refactor", "rename", "move", "merge",
    "revert", "implement", "build", "review", "check", "find", "replace",
    "insert", "append", "translate", "convert", "extend", "shorten", "expand",
    "keep", "make", "set", "draft", "redesign", "restructure",
)

# named output formats
OUTPUT_FORMATS = (
    "json", "yaml", "csv", "tsv", "markdown", "html", "pdf", "xml", "table",
    "bullet points", "bulleted list", "numbered list", "plain text", "latex",
    "docx", "xlsx", "pptx", "sql", "diff", "patch",
)

# very small month lexicon for date detection
_MONTHS = ("january", "february", "march", "april", "may", "june", "july",
           "august", "september", "october", "november", "december")

_DATE_PATTERNS = [
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),                       # 2026-01-31
    re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),                 # 01/31/2026
    re.compile(r"\b(?:%s)\s+\d{1,2}(?:,\s*\d{4})?\b" % "|".join(_MONTHS), re.I),
    re.compile(r"\b\d{1,2}\s+(?:%s)(?:\s+\d{4})?\b" % "|".join(_MONTHS), re.I),
    re.compile(r"\bQ[1-4]\s+\d{4}\b"),                          # Q3 2026
    re.compile(r"\b(?:19|20)\d{2}\b"),                          # bare year
]

_RELATIVE_TIME = re.compile(
    r"\b(?:before|after|by|since|until|as of|prior to)\s+"
    r"(?:the\s+)?[a-z0-9][\w\s-]{0,40}", re.I)

_QUOTE = re.compile(r"[\"“”']([^\"“”']{1,80})[\"“”']")
_URL = re.compile(r"\bhttps?://[^\s)\]]+", re.I)
_FILENAME = re.compile(r"\b[\w./-]+\.(?:py|md|txt|json|yaml|yml|csv|tsv|html|"
                       r"pdf|docx|xlsx|pptx|js|ts|tsx|cpp|c|h|go|rs|java|toml|"
                       r"ini|cfg|sh|sql)\b")
_IDENTIFIER = re.compile(
    r"\b(?:PR|#|issue|ticket|CVE|RFC|TAP-E\d|v\d+(?:\.\d+)*)"
    r"[-\s]?[A-Za-z0-9.\-]*\b")
_NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?![\w.])")


# --------------------------------------------------------------------------- #
# Result container                                                            #
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class DeterministicExtraction:
    quotes: Tuple[Span, ...]
    urls: Tuple[Span, ...]
    filenames: Tuple[Span, ...]
    identifiers: Tuple[Span, ...]
    numbers: Tuple[Span, ...]
    dates: Tuple[Span, ...]
    imperatives: Tuple[Tuple[str, Span], ...]        # (verb, span)
    output_formats: Tuple[Tuple[str, Span], ...]     # (format, span)
    constraints: Tuple[Constraint, ...]              # requirement + prohibition
    temporal: Tuple[TemporalConstraint, ...]

    def all_spans(self) -> Tuple[Span, ...]:
        out: List[Span] = []
        out.extend(self.quotes)
        out.extend(self.urls)
        out.extend(self.filenames)
        out.extend(self.identifiers)
        out.extend(self.numbers)
        out.extend(self.dates)
        return tuple(out)


def _prov(span: Span, note: str) -> Provenance:
    return Provenance(ProvenanceKind.DETERMINISTIC_EXTRACTION, (span,), note=note)


def _spans_for(pattern: re.Pattern, text: str) -> List[Span]:
    return [Span(m.start(), m.end(), m.group(0)) for m in pattern.finditer(text)]


def _clause_after(text: str, start: int, max_len: int = 60) -> Tuple[str, int]:
    """Return the clause following ``start`` up to a stop punctuation or length."""
    tail = text[start:start + max_len]
    stop = re.search(r"[.;,\n]|\band\b|\bbut\b", tail)
    end = start + (stop.start() if stop else len(tail))
    return text[start:end].strip(), end


def _clause_around(text: str, start: int, end: int) -> Tuple[int, int]:
    """Return (lo, hi) bounds of the clause containing [start, end), split on
    clause boundaries (punctuation, 'and', 'but')."""
    left = text[:start]
    lb = 0
    for m in re.finditer(r"[.;,\n]|\band\b|\bbut\b", left):
        lb = m.end()
    tail = text[end:]
    m = re.search(r"[.;,\n]|\band\b|\bbut\b", tail)
    hi = end + (m.start() if m else len(tail))
    return lb, min(hi, len(text))


# --------------------------------------------------------------------------- #
# Extractors                                                                  #
# --------------------------------------------------------------------------- #

def extract_constraints(text: str) -> List[Constraint]:
    """Extract explicit requirement/prohibition constraints with spans.

    Prohibitions are detected FIRST and their trigger span is recorded, so a
    later stage can never present the prohibited action as a requested action
    (the "reversing an explicit prohibition" critical failure)."""
    constraints: List[Constraint] = []
    low = text.lower()
    claimed: List[Tuple[int, int]] = []

    def _overlaps(lo: int, hi: int) -> bool:
        return any(not (hi <= a or lo >= b) for a, b in claimed)

    def _emit(trig: str, m: re.Match, polarity: ConstraintPolarity) -> None:
        lo, hi = _clause_around(text, m.start(), m.end())
        if _overlaps(lo, hi):
            return
        claimed.append((lo, hi))
        clause = text[lo:hi].strip().strip(",").strip()
        span = Span(lo, hi, text[lo:hi])
        subject = _first_content_word(text[m.end():hi]) or _first_content_word(clause)
        constraints.append(Constraint(
            clause, polarity, _prov(span, f"{polarity.value}:{trig}"), subject=subject))

    # prohibitions first so their spans are claimed before requirement cues run
    for trig in PROHIBITION_TRIGGERS:
        for m in re.finditer(r"\b" + re.escape(trig) + r"\b", low):
            _emit(trig, m, ConstraintPolarity.PROHIBITION)

    for trig in REQUIREMENT_TRIGGERS:
        for m in re.finditer(r"\b" + re.escape(trig) + r"\b", low):
            if trig == "must" and low[m.start():m.start() + 8] == "must not":
                continue
            _emit(trig, m, ConstraintPolarity.REQUIREMENT)

    # quantity / length / assignment requirements (e.g. "two paragraphs",
    # "one-page", "under 150 words", "to 30 seconds", "15%", "$200").
    _QTY = re.compile(
        r"\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)[-\s]?"
        r"(?:page|pages|word|words|paragraph|paragraphs|section|sections|bullet|"
        r"bullets|chapter|chapters|sentence|sentences|second|seconds|minute|"
        r"minutes|hour|hours|day|days|dpi|character|characters|line|lines)\b"
        r"|\bto\s+\d+(?:\.\d+)*\b|\b\d+\s?%|\$\s?\d+", re.I)
    for m in _QTY.finditer(text):
        lo, hi = _clause_around(text, m.start(), m.end())
        if _overlaps(lo, hi):
            continue
        claimed.append((lo, hi))
        span = Span(lo, hi, text[lo:hi])
        constraints.append(Constraint(
            text[lo:hi].strip().strip(",").strip(), ConstraintPolarity.REQUIREMENT,
            _prov(span, "quantity"), subject=_first_content_word(m.group(0))))

    # named output formats are explicit requirement constraints too
    for fmt, span in extract_output_formats(text):
        if not _overlaps(span.start, span.end):
            claimed.append((span.start, span.end))
            constraints.append(Constraint(
                fmt, ConstraintPolarity.REQUIREMENT, _prov(span, f"format:{fmt}"),
                subject=fmt))

    constraints.sort(key=lambda c: c.provenance.spans[0].start if c.provenance.spans else 0)
    return constraints


def _first_content_word(fragment: str) -> str:
    for tok in re.findall(r"[A-Za-z][A-Za-z-]+", fragment):
        if tok.lower() not in ("the", "a", "an", "to", "any", "of", "it", "that",
                               "this", "your", "my", "our"):
            return tok.lower()
    return ""


def extract_temporal(text: str) -> List[TemporalConstraint]:
    out: List[TemporalConstraint] = []
    seen: set = set()
    for pat in _DATE_PATTERNS:
        for m in pat.finditer(text):
            key = (m.start(), m.end())
            if key in seen:
                continue
            seen.add(key)
            span = Span(m.start(), m.end(), m.group(0))
            out.append(TemporalConstraint(m.group(0), _prov(span, "date"),
                                          normalized=m.group(0)))
    for m in _RELATIVE_TIME.finditer(text):
        span = Span(m.start(), m.end(), m.group(0).strip())
        out.append(TemporalConstraint(m.group(0).strip(),
                                      _prov(span, "relative_time")))
    return out


def extract_imperatives(text: str) -> List[Tuple[str, Span]]:
    out: List[Tuple[str, Span]] = []
    low = text.lower()
    for verb in IMPERATIVE_VERBS:
        for m in re.finditer(r"\b" + verb + r"\b", low):
            out.append((verb, Span(m.start(), m.end(), text[m.start():m.end()])))
    out.sort(key=lambda vs: vs[1].start)
    return out


def extract_output_formats(text: str) -> List[Tuple[str, Span]]:
    out: List[Tuple[str, Span]] = []
    low = text.lower()
    for fmt in OUTPUT_FORMATS:
        for m in re.finditer(r"\b" + re.escape(fmt) + r"\b", low):
            out.append((fmt, Span(m.start(), m.end(), text[m.start():m.end()])))
    return out


def run_extraction(text: str) -> DeterministicExtraction:
    return DeterministicExtraction(
        quotes=tuple(Span(m.start(1), m.end(1), m.group(1))
                     for m in _QUOTE.finditer(text)),
        urls=tuple(_spans_for(_URL, text)),
        filenames=tuple(_spans_for(_FILENAME, text)),
        identifiers=tuple(_spans_for(_IDENTIFIER, text)),
        numbers=tuple(_spans_for(_NUMBER, text)),
        dates=tuple(s for tc in extract_temporal(text)
                    for s in tc.provenance.spans if tc.provenance.note == "date"),
        imperatives=tuple(extract_imperatives(text)),
        output_formats=tuple(extract_output_formats(text)),
        constraints=tuple(extract_constraints(text)),
        temporal=tuple(extract_temporal(text)),
    )
