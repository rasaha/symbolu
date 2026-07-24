"""Provenance graph + source identity + duplicate/citation detection (Phase 7). Deterministic,
stdlib-only, no network. Operates on the OBSERVED metadata of a case (upstream ids, content hashes,
retrieval paths, publishers, publication years, provenance confidence).

Core rule (enforced): **different URLs / publishers do NOT imply independent evidence.** Apparent
diversity is discounted by (a) shared upstream source, (b) shared content hash, (c) shared retrieval
path, and (d) low provenance_confidence (fabricated/unverifiable metadata is NOT trusted as
independent). Missing provenance is treated as UNKNOWN independence, never as independence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ProvenanceFindings:
    n_items: int
    distinct_upstream: int
    distinct_hashes: int
    distinct_paths: int
    distinct_publishers: int
    direct_duplication: bool            # >=2 items share a content hash
    common_upstream: bool               # >=2 items share an upstream source (or all derive from one)
    retrieval_path_collapse: bool       # many items, very few retrieval paths
    circular_or_derivative: bool        # derivation forms a chain/loop to one root
    missing_provenance: bool            # upstream/publisher unknown or metadata incomplete
    superseded_or_stale: bool           # publication years old
    provenance_confidence: float
    # the estimate that matters: how many GENUINELY independent sources do we believe there are?
    effective_independent_estimate: float
    reason_codes: List[str] = field(default_factory=list)


_STALE_BEFORE = 2018


def analyze(case: Dict[str, Any], now_year: int = 2024) -> ProvenanceFindings:
    n = case["n_evidence_items"]
    upstream = case.get("observed_upstream_ids", []) or []
    hashes = case.get("observed_content_hashes", []) or []
    paths = case.get("observed_distinct_retrieval_paths", 1)
    pubs = case.get("observed_distinct_publishers", n)
    years = case.get("observed_publication_years", []) or []
    prov_conf = case.get("observed_provenance_confidence", 1.0)
    complete = case.get("metadata_complete", True)

    distinct_upstream = len(set(upstream)) if upstream else 0
    distinct_hashes = len(set(hashes)) if hashes else 0
    codes: List[str] = []

    direct_dup = distinct_hashes < n and n >= 2
    if direct_dup:
        codes.append("EA.DUPLICATE_CONTENT")
    # common upstream: all items trace to few upstream roots
    common_up = (distinct_upstream <= max(1, n // 2)) and n >= 2 and distinct_upstream >= 1
    if common_up:
        codes.append("EA.COMMON_UPSTREAM")
    path_collapse = paths <= 1 and n >= 3
    if path_collapse:
        codes.append("EA.RETRIEVAL_PATH_COLLAPSE")
    # derivative/circular: a single upstream root feeding all items (all same upstream id)
    circular = distinct_upstream == 1 and n >= 2
    if circular:
        codes.append("EA.DERIVATIVE_CHAIN")
    missing = (not complete) or (not upstream) or (pubs == 0)
    if missing:
        codes.append("EA.MISSING_PROVENANCE")
    stale = bool(years) and max(years) < _STALE_BEFORE
    if stale:
        codes.append("EA.STALE_PROVENANCE")

    # effective-independent estimate: start from distinct upstream sources (the only thing that
    # actually confers independence), collapse duplicates, then DISCOUNT by provenance confidence.
    base = max(distinct_upstream, 1) if not missing else 1
    if direct_dup:
        base = min(base, distinct_hashes or 1)
    if path_collapse:
        base = 1
    # low provenance confidence => cannot trust apparent independence; pull toward 1 (single source)
    effective = 1.0 + (base - 1.0) * prov_conf
    if missing:
        effective = min(effective, 1.0)          # unknown provenance is NOT independence
        codes.append("EA.INDEPENDENCE_UNKNOWN")

    return ProvenanceFindings(
        n_items=n, distinct_upstream=distinct_upstream, distinct_hashes=distinct_hashes,
        distinct_paths=paths, distinct_publishers=pubs, direct_duplication=direct_dup,
        common_upstream=common_up, retrieval_path_collapse=path_collapse,
        circular_or_derivative=circular, missing_provenance=missing, superseded_or_stale=stale,
        provenance_confidence=prov_conf, effective_independent_estimate=round(effective, 3),
        reason_codes=codes)
