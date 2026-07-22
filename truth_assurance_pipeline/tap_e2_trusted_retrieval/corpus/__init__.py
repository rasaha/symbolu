"""
TAP-E2 retrieval corpus: synthetic enterprise documents + graded query gold.
NEW for this study; no TAP-E1 prompt reused.
"""

from truth_assurance_pipeline.tap_e2_trusted_retrieval.corpus import documents, queries
from truth_assurance_pipeline.tap_e2_trusted_retrieval.corpus.documents import (
    DOCUMENTS, UNITS,
)
from truth_assurance_pipeline.tap_e2_trusted_retrieval.corpus.queries import (
    ALL_QUERIES, QueryCase, queries_for_split,
)
from truth_assurance_pipeline.tap_e2_trusted_retrieval.evidence_unit import stable_hash


def corpus_manifest():
    doc_stats = {}
    for d in DOCUMENTS:
        doc_stats[d.doc_type.value] = doc_stats.get(d.doc_type.value, 0) + 1
    return {
        "n_documents": len(DOCUMENTS),
        "n_evidence_units": len(UNITS),
        "document_types": doc_stats,
        "documents_hash": stable_hash([d.to_meta() for d in DOCUMENTS]),
        "units_hash": stable_hash([u.to_public_dict() for u in UNITS]),
        "queries": queries.manifest(),
    }


__all__ = ["documents", "queries", "DOCUMENTS", "UNITS", "ALL_QUERIES", "QueryCase",
           "queries_for_split", "corpus_manifest"]
