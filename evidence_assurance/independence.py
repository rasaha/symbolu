"""Evidence independence (Phase 9). Multiple notions of independence, kept separate, then combined
into an INDEPENDENCE VERDICT (not an opaque score). Builds on the provenance graph. Deterministic.

Notions: document · publisher · upstream-source · retrieval-path · temporal · institutional. Model
and methodological independence are only partially observable from evidence metadata and are reported
as UNKNOWN rather than assumed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from evidence_assurance import provenance as prov


@dataclass
class IndependenceVerdict:
    verdict: str                 # INDEPENDENT | DEPENDENT | DUPLICATE | UNKNOWN
    effective_independent: float
    apparent_count: int          # naive source count (what count-baselines see)
    inflation_ratio: float       # apparent_count / effective_independent (>1 => fake corroboration)
    document_independent: bool
    publisher_independent: bool
    upstream_independent: bool
    path_independent: bool
    provenance_trusted: bool
    reason_codes: list


def assess(case: Dict[str, Any]) -> IndependenceVerdict:
    f = prov.analyze(case)
    n = f.n_items
    eff = f.effective_independent_estimate
    apparent = n
    inflation = round(apparent / eff, 3) if eff > 0 else float(apparent)

    doc_ind = not f.direct_duplication
    pub_ind = f.distinct_publishers >= 2 and f.provenance_confidence >= 0.6
    up_ind = f.distinct_upstream >= 2 and not f.common_upstream
    path_ind = f.distinct_paths >= 2
    prov_trusted = f.provenance_confidence >= 0.6 and not f.missing_provenance

    codes = list(f.reason_codes)
    if not prov_trusted:
        verdict = "UNKNOWN"                       # cannot trust apparent diversity
        codes.append("EA.INDEPENDENCE_UNTRUSTED")
    elif eff >= 2.0 and up_ind:
        verdict = "INDEPENDENT"
    elif f.direct_duplication:
        verdict = "DUPLICATE"
    else:
        verdict = "DEPENDENT"

    if inflation >= 2.0:
        codes.append("EA.SOURCE_COUNT_INFLATED")

    return IndependenceVerdict(
        verdict=verdict, effective_independent=eff, apparent_count=apparent,
        inflation_ratio=inflation, document_independent=doc_ind, publisher_independent=pub_ind,
        upstream_independent=up_ind, path_independent=path_ind, provenance_trusted=prov_trusted,
        reason_codes=codes)
