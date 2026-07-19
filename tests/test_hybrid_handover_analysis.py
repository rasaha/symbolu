#!/usr/bin/env python3
"""Tests for the capability-isolation analysis (oracle-retrieval counterfactual).

Analysis-only: reads SEEB, modifies nothing. These tests lock the central result
— that a maximal retrieval oracle still fails the unresolved cases (retrieval
insufficient), i.e. the residual is not a retrieval problem.
"""

from __future__ import annotations

import json

from agentic.hybrid_handover.evaluation.corpus import (
    case_later_amendment_override,
    case_policy_override,
)
from agentic.hybrid_handover.evaluation.validators import SpanIntegrityValidator
from agentic.hybrid_handover.analysis.oracle import OracleRetriever
from agentic.hybrid_handover.analysis.capability_isolation import run_all

EXPECTED_INSUFFICIENT = {
    "order_of_precedence", "conflicting_versions", "hidden_negation",
    "conflicting_tables", "circular_reference", "inconsistent_numbering",
    "policy_override",
}


def test_oracle_retrieves_everything_and_grounds():
    case = case_later_amendment_override()
    pkt = OracleRetriever(case).extract(case.question, case.corpus)
    # every sentence present, all grounded verbatim
    assert pkt.evidence
    out = SpanIntegrityValidator().validate(case, pkt, case.corpus)
    assert out.passed, out.findings


def test_oracle_cannot_fix_precedence_case():
    # perfect retrieval still cannot record the policy-override relationship
    case = case_policy_override()
    pkt = OracleRetriever(case).extract(case.question, case.corpus)
    # the policy span IS present...
    assert any("notwithstanding any contract term" in s.quote.lower() for s in pkt.evidence)
    # ...but the precedence relationship is still absent (not a span)
    assert not pkt.conflicts_resolved or all(
        "policy" not in c.superseded_by.lower() for c in pkt.conflicts_resolved
    )


def test_capability_isolation_summary():
    out = run_all()
    s = out["summary"]
    assert s["n_cases"] == 16
    assert s["retrieval_limited"] == 0          # no unresolved case is retrieval-fixable
    assert s["retrieval_insufficient"] == 7
    assert s["retrieval_saturated"] is True
    assert set(s["retrieval_insufficient_ids"]) == EXPECTED_INSUFFICIENT


def test_every_insufficient_case_fails_under_perfect_retrieval():
    out = run_all()
    for c in out["cases"]:
        if c["classification"] == "RETRIEVAL INSUFFICIENT":
            assert c["oracle_solved"] is False, c["case_id"]


def test_analysis_is_deterministic():
    a = json.dumps(run_all(), sort_keys=True)
    b = json.dumps(run_all(), sort_keys=True)
    assert a == b
