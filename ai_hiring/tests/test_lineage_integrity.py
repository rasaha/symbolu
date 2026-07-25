"""Lineage DAG integrity tests."""

from __future__ import annotations

import pytest

from ai_hiring.errors import (
    LineageConflictingParentError,
    LineageContextMismatchError,
    LineageCycleError,
    LineageParentNotFoundError,
    LineageVersionRegressionError,
)
from ai_hiring.normalization.lineage import LineageGraph
from ai_hiring.normalization.models import LineageNode
from ai_hiring.policies import lineage_integrity_policy as lp


def _node(node_id, parents=(), *, tenant="t1", candidate="c1", version=1, ts=0):
    from datetime import datetime, timezone

    return LineageNode(
        node_id=node_id, evidence_id="ev1", version=version, operation="OP",
        actor="svc", timestamp=datetime(2026, 1, 1, 0, 0, ts, tzinfo=timezone.utc),
        parent_ids=tuple(parents), tenant_id=tenant, candidate_id=candidate)


def test_valid_chain():
    a = _node("a", ts=0)
    b = _node("b", ["a"], ts=1)
    c = _node("c", ["b"], ts=2)
    lp.validate_graph(LineageGraph(nodes=(a, b, c)))  # no raise


def test_valid_branch():
    a = _node("a", ts=0)
    b = _node("b", ["a"], ts=1)
    c = _node("c", ["a"], ts=2)
    lp.validate_graph(LineageGraph(nodes=(a, b, c)))


def test_missing_parent():
    b = _node("b", ["ghost"])
    with pytest.raises(LineageParentNotFoundError):
        lp.validate_new_node(b, ())


def test_self_parent():
    n = _node("a", ["a"])
    with pytest.raises(LineageCycleError):
        lp.validate_new_node(n, ())


def test_two_node_cycle():
    a = _node("a", ["b"], ts=0)
    b = _node("b", ["a"], ts=1)
    with pytest.raises(LineageCycleError):
        lp.validate_graph(LineageGraph(nodes=(a, b)))


def test_deep_cycle():
    a = _node("a", ["c"], ts=0)
    b = _node("b", ["a"], ts=1)
    c = _node("c", ["b"], ts=2)
    with pytest.raises(LineageCycleError):
        lp.validate_graph(LineageGraph(nodes=(a, b, c)))


def test_cross_tenant_parent_rejected():
    a = _node("a", tenant="t1", ts=0)
    b = _node("b", ["a"], tenant="t2", ts=1)
    with pytest.raises(LineageContextMismatchError):
        lp.validate_new_node(b, (a,))


def test_cross_candidate_parent_rejected():
    a = _node("a", candidate="cand-A", ts=0)
    b = _node("b", ["a"], candidate="cand-B", ts=1)
    with pytest.raises(LineageContextMismatchError):
        lp.validate_new_node(b, (a,))


def test_version_regression_rejected():
    a = _node("a", version=3, ts=0)
    b = _node("b", ["a"], version=2, ts=1)
    with pytest.raises(LineageVersionRegressionError):
        lp.validate_new_node(b, (a,))


def test_conflicting_predecessors_rejected():
    with pytest.raises(LineageConflictingParentError):
        lp.check_conflicting_predecessors(3, (1, 2))
    # a single predecessor is fine
    lp.check_conflicting_predecessors(3, (2, 2))


def test_ingested_lineage_is_valid(platform):
    from .conftest import text_sub

    ing = platform.evidence_ingestion_service.ingest(text_sub("A" * 2500, tenant_id="t1"))
    graph = platform.provenance_service.lineage(ing.evidence_id)
    lp.validate_graph(graph)  # no raise — the real pipeline builds a valid DAG
