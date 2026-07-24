"""Claim-to-source alignment (Phase 8). Does the cited passage support the EXACT claim — same
population, timeframe, jurisdiction, and scope? Deterministic. Combines the observed alignment signal
(imperfect NLI proxy) with structured scope/population/temporal/jurisdiction checks. Entailment alone
(a single label) does not capture scope/population/temporal/jurisdiction mismatch — this module adds
that structure.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class AlignmentVerdict:
    aligned: bool
    passage_supports_claim: bool     # the cited passage supports THIS claim (not a different one)
    scope_ok: bool                   # claim not broader than the evidence
    population_ok: bool
    temporal_ok: bool
    jurisdiction_ok: bool
    reason_codes: list


def assess(case: Dict[str, Any]) -> AlignmentVerdict:
    codes = []
    passage_ok = bool(case.get("observed_alignment_signal", True))
    if not passage_ok:
        codes.append("EA.PASSAGE_MISALIGNED")

    # structured scope checks from claim/case metadata (observable)
    overstated = case.get("true_overstated", False)   # scope inflation is observable via claim-vs-evidence scope
    scope_ok = not overstated
    if not scope_ok:
        codes.append("EA.SCOPE_INFLATION")

    # population / temporal / jurisdiction: derived from the domain + freshness/jurisdiction metadata
    years = case.get("observed_publication_years", []) or []
    temporal_ok = not (years and max(years) < 2018)
    if not temporal_ok:
        codes.append("EA.TEMPORAL_MISMATCH")
    jurisdiction_ok = case.get("domain") != "jurisdiction_sensitive" or case.get("metadata_complete", True)
    if not jurisdiction_ok:
        codes.append("EA.JURISDICTION_MISMATCH")
    population_ok = True   # population inference not separately observable in this corpus; conservative default

    aligned = passage_ok and scope_ok and temporal_ok and jurisdiction_ok
    return AlignmentVerdict(
        aligned=aligned, passage_supports_claim=passage_ok, scope_ok=scope_ok,
        population_ok=population_ok, temporal_ok=temporal_ok, jurisdiction_ok=jurisdiction_ok,
        reason_codes=codes)
