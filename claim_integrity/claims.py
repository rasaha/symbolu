"""Reference ClaimIntegrity component (Phase 9). Orchestrates segmentation, reference resolution, and
dimension preservation into a set of self-contained claim units, WITHOUT stripping any qualifier,
negation, modality, condition, exception, temporal, jurisdiction, numeric, attribution, or
evidence-status token. Emits per-unit dimensions, a disposition, confidence, and reason codes, plus an
audit record.

What it may NOT do (by construction): determine truth, retrieve evidence, invent an unstated claim,
silently normalize uncertainty into certainty, discard a source span, or authorize delivery/actions.
It is a decomposition-integrity stage, nothing more.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from . import segmentation, references, detect
from .taxonomy import Disposition


@dataclass
class ProducedClaim:
    text: str
    dimensions: Dict[str, Any]
    reference_resolved: bool
    reason_codes: List[str] = field(default_factory=list)


@dataclass
class ClaimIntegrityResult:
    claims: List[ProducedClaim]
    disposition: str
    confidence: float
    reason_codes: List[str] = field(default_factory=list)
    audit: Dict[str, Any] = field(default_factory=dict)


ALL_FEATURES = frozenset({"reference_resolution", "safe_split", "nonassertive_filter"})


def decompose(text: str, enabled: frozenset = ALL_FEATURES) -> ClaimIntegrityResult:
    """`enabled` selects which mechanisms are active - the full set by default; the ablation study
    (Phase 22) removes one at a time to measure its downstream weight."""
    spans = segmentation.segment(text)
    produced: List[ProducedClaim] = []
    codes: List[str] = []
    unresolved = False
    prev_text = ""

    for span, dependent in spans:
        if "nonassertive_filter" in enabled and _non_assertive(span):
            codes.append("CI.NON_ASSERTIVE_SKIPPED")   # rhetorical question / aside: do NOT extract
            continue
        working = span
        ref_ok = True
        rcodes: List[str] = []
        if dependent and "reference_resolution" in enabled:
            working, ref_ok, antecedent = references.resolve(span, prev_text)
            if ref_ok:
                rcodes.append("CI.REFERENCE_RESOLVED")
            else:
                rcodes.append("CI.REFERENCE_UNRESOLVED")
                unresolved = True

        # split a conjunction only when safe (both sides independent, no spanning modifier)
        pieces = _safe_split(working) if "safe_split" in enabled else _naive_split(working)
        for piece in pieces:
            dims = detect.detect_dimensions(piece)
            produced.append(ProducedClaim(text=piece, dimensions=dims,
                                          reference_resolved=ref_ok, reason_codes=list(rcodes)))
        prev_text = working

    disposition, conf = _disposition(produced, unresolved)
    if disposition != Disposition.VALID.value:
        codes.append(f"CI.{disposition}")
    return ClaimIntegrityResult(
        claims=produced, disposition=disposition, confidence=conf, reason_codes=codes,
        audit={"n_input_spans": len(spans), "n_output_claims": len(produced),
               "any_unresolved_reference": unresolved})


def _non_assertive(span: str) -> bool:
    """Rhetorical question or non-assertive aside: ends with '?' (and is not a claim). The taxonomy
    commits that rhetorical_non_assertive text must not be extracted as a claim (failure type 45)."""
    return span.strip().endswith("?")


def _naive_split(clause: str) -> List[str]:
    """Ablation of safe_split: split on any ' and '/' but ', ignoring spanning modifiers."""
    import re
    parts = re.split(r"\s+\b(?:and|but)\b\s+", clause)
    return [p.rstrip(". ") + "." for p in parts if p.strip()]


def _safe_split(clause: str) -> List[str]:
    if segmentation.splittable_conjunction(clause):
        # split on the top-level ' and ' but keep each side punctuated
        left, _, right = clause.partition(" and ")
        left = left.rstrip(". ") + "."
        right = right[0].upper() + right[1:] if right else right
        return [left, right]
    return [clause]


def _disposition(produced: List[ProducedClaim], unresolved: bool):
    if unresolved:
        return Disposition.REFERENCE_ERROR.value, 0.5
    if not produced:
        return Disposition.INDETERMINATE.value, 0.3
    return Disposition.VALID.value, 0.9
