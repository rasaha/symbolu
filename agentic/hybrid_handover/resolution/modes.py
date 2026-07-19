#!/usr/bin/env python3
"""
Evidence modes — the resolution layer runs every resolver under identical
evidence so relationship reasoning is measured independently of retrieval.

  Mode A — Oracle evidence     : every sentence (retrieval upper bound)
  Mode B — BM25 evidence       : current strongest conventional retrieval
  Mode C — Candidate extractor : interface only (bring your own ExtractorProtocol)
"""

from __future__ import annotations

from agentic.hybrid_handover.baselines.bm25 import BM25Extractor
from agentic.hybrid_handover.schema import EvidenceSpan

_BM25 = BM25Extractor()


def mode_oracle(case) -> list[EvidenceSpan]:
    from agentic.hybrid_handover.analysis.oracle import OracleRetriever
    return OracleRetriever(case).extract(case.question, case.corpus).evidence


def mode_bm25(case) -> list[EvidenceSpan]:
    return _BM25.retrieve(case.question, case.corpus)


def mode_candidate(case, extractor) -> list[EvidenceSpan]:
    """Interface for future work: any ExtractorProtocol supplies the evidence."""
    if extractor is None:
        return []
    return extractor.extract(case.question, case.corpus).evidence


MODES = {"A_oracle": mode_oracle, "B_bm25": mode_bm25}
