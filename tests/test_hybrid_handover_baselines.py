#!/usr/bin/env python3
"""Tests for the conventional baseline extractors and the comparison runner.

These verify the baselines conform to the frozen ExtractorProtocol and run
through the unchanged SEEB benchmark, and they lock in the qualitative findings
(retrieval fixes definition/defeater recall; precedence is retrieval-invariant).
"""

from __future__ import annotations

import json

from agentic.hybrid_handover.schema import EvidencePacket, ResolvedAnswer
from agentic.hybrid_handover.evaluation import DEFAULT_VALIDATORS, evaluate_case
from agentic.hybrid_handover.evaluation.corpus import (
    case_conflicting_definitions,
    case_later_amendment_override,
)
from agentic.hybrid_handover.evaluation.validators import SpanIntegrityValidator
from agentic.hybrid_handover.baselines import ORDER, build
from agentic.hybrid_handover.baselines.compare import run_all


def test_registry_has_four_baselines():
    assert ORDER == ["keyword", "bm25", "embedding", "hybrid_retriever"]


def test_all_baselines_conform_to_protocol():
    case = case_later_amendment_override()
    for name in ORDER:
        ex = build(name)
        pkt = ex.extract(case.question, case.corpus)
        ans = ex.resolve(case.question, case.corpus)
        assert isinstance(pkt, EvidencePacket)
        assert isinstance(ans, ResolvedAnswer)
        assert pkt.evidence  # produced some evidence


def test_retrieved_spans_ground_verbatim():
    # every retriever's spans must slice to their quote (else grounding refuses)
    case = case_later_amendment_override()
    for name in ("bm25", "embedding", "hybrid_retriever"):
        ex = build(name)
        pkt = ex.extract(case.question, case.corpus)
        out = SpanIntegrityValidator().validate(case, pkt, case.corpus)
        assert out.passed, (name, out.findings)


def test_keyword_reproduces_frozen_baseline():
    # the keyword wrapper must equal the frozen InHouseExtractor behaviour
    case = case_conflicting_definitions()
    r = evaluate_case(case, build("keyword"), DEFAULT_VALIDATORS, "augmented")
    assert r.definition == (0, 2)      # keyword is blind to definitions
    assert r.unsafe_handover           # and this is unsafe


def test_retrieval_fixes_definition_recall():
    case = case_conflicting_definitions()
    for name in ("bm25", "embedding", "hybrid_retriever"):
        r = evaluate_case(case, build(name), DEFAULT_VALIDATORS, "augmented")
        assert r.definition == (2, 2), name          # definitions now retrieved
        assert not r.unsafe_handover, name           # ...so no longer unsafe


def test_precedence_is_retrieval_invariant():
    # precedence comes from the shared resolver, identical across all extractors
    out, _ = run_all()
    prec = {n: out["metric_matrix_augmented_pct"]["precedence_recall"][n] for n in ORDER}
    assert len(set(prec.values())) == 1, prec  # all identical


def test_comparison_is_deterministic():
    a, _ = run_all()
    b, _ = run_all()
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_absolute_unsafe_count_unchanged_but_definition_gap_closed():
    # headline finding: retrieval closes the definition gap; residual unsafe is
    # all precedence/relationship reasoning (4 absolute for every extractor)
    out, rows = run_all()
    unsafe = {n: 0 for n in ORDER}
    for r in rows:
        if r["unsafe"] == 1:
            unsafe[r["extractor"]] += 1
    assert all(v == 4 for v in unsafe.values()), unsafe
