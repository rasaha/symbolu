"""
Provenance attachment for TAP-E2.

Every candidate evidence unit is given complete provenance (source id, in-document
location, retrieval path, retrieval method, retrieval score, extraction method).
The provenance-filtering stage (baseline D and up) can then drop or deprioritize any
candidate whose provenance is incomplete — enforcing "no evidence without provenance".
"""

from __future__ import annotations

from typing import Tuple

from truth_assurance_pipeline.tap_e2_trusted_retrieval.evidence_unit import (
    EvidenceProvenance, EvidenceUnit, RetrievalMethod,
)


def attach(unit: EvidenceUnit, method: RetrievalMethod, score: float,
           path: Tuple[str, ...]) -> EvidenceProvenance:
    return EvidenceProvenance(
        source_id=unit.doc_id,
        source_location=unit.location,
        retrieval_path=path,
        retrieval_method=method,
        retrieval_score=score,
        extraction_method=unit.extraction_method,
    )


def provenance_complete(prov: EvidenceProvenance) -> bool:
    return prov.is_complete()
