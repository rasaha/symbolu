"""Phase-3 dependency-topology tests (matrix C: dependency evidence validation)."""

from __future__ import annotations

import pytest

from ugence_cloud_scaling_controller.canonical import CapacitySubject
from ugence_cloud_scaling_controller.planning import (
    DependencyEdge,
    DependencyKind,
    DependencyTopology,
    TopologyError,
)
import ph_helpers as H


def _s(wid, tenant="tenant-1"):
    return CapacitySubject(workload_id=wid, tenant_id=tenant)


def test_self_edge_rejected():
    with pytest.raises(TopologyError):
        DependencyEdge(_s("app"), _s("app"), DependencyKind.CAPACITY_BOUND)


def test_cross_tenant_edge_rejected():
    app = _s("app", "tenant-1")
    db = _s("db", "tenant-2")  # different tenant
    with pytest.raises(TopologyError):
        DependencyTopology(subject=app, as_of=H.at(0), edges=(
            DependencyEdge(app, db, DependencyKind.CAPACITY_BOUND,
                           downstream_current_capacity=100, required_per_upstream_unit=20.0),))


def test_duplicate_edge_rejected():
    app, db = _s("app"), _s("db")
    e = DependencyEdge(app, db, DependencyKind.INFORMATIONAL)
    with pytest.raises(TopologyError):
        DependencyTopology(subject=app, as_of=H.at(0), edges=(e, e))


def test_conflicting_edge_rejected():
    app, db = _s("app"), _s("db")
    e1 = DependencyEdge(app, db, DependencyKind.INFORMATIONAL)
    e2 = DependencyEdge(app, db, DependencyKind.THROUGHPUT_BOUND)
    with pytest.raises(TopologyError):
        DependencyTopology(subject=app, as_of=H.at(0), edges=(e1, e2))


def test_cycle_detected_but_not_a_construction_error():
    a, b = _s("a"), _s("b")
    topo = DependencyTopology(subject=a, as_of=H.at(0), edges=(
        DependencyEdge(a, b, DependencyKind.INFORMATIONAL),
        DependencyEdge(b, a, DependencyKind.INFORMATIONAL),
    ))
    assert topo.has_cycle() is True


def test_acyclic_topology_reports_no_cycle():
    a, b, c = _s("a"), _s("b"), _s("c")
    topo = DependencyTopology(subject=a, as_of=H.at(0), edges=(
        DependencyEdge(a, b, DependencyKind.INFORMATIONAL),
        DependencyEdge(b, c, DependencyKind.INFORMATIONAL),
    ))
    assert topo.has_cycle() is False


def test_informational_edge_must_not_carry_capacity_evidence():
    app, db = _s("app"), _s("db")
    with pytest.raises(TopologyError):
        DependencyEdge(app, db, DependencyKind.INFORMATIONAL,
                       downstream_current_capacity=10, required_per_upstream_unit=1.0)


def test_capacity_evidence_negative_rejected():
    app, db = _s("app"), _s("db")
    with pytest.raises(TopologyError):
        DependencyEdge(app, db, DependencyKind.CAPACITY_BOUND,
                       downstream_current_capacity=-1, required_per_upstream_unit=1.0)
    with pytest.raises(TopologyError):
        DependencyEdge(app, db, DependencyKind.CAPACITY_BOUND,
                       downstream_current_capacity=10, required_per_upstream_unit=0.0)


def test_topology_digest_order_independent():
    app, b, c = _s("app"), _s("b"), _s("c")
    e1 = DependencyEdge(app, b, DependencyKind.INFORMATIONAL)
    e2 = DependencyEdge(app, c, DependencyKind.INFORMATIONAL)
    t1 = DependencyTopology(subject=app, as_of=H.at(0), edges=(e1, e2))
    t2 = DependencyTopology(subject=app, as_of=H.at(0), edges=(e2, e1))
    assert t1.digest() == t2.digest()


def test_topology_round_trip():
    app, db = _s("app"), _s("db")
    t = DependencyTopology(subject=app, as_of=H.at(0), edges=(
        DependencyEdge(app, db, DependencyKind.CAPACITY_BOUND,
                       downstream_current_capacity=100, required_per_upstream_unit=20.0),),
        evidence_source="obs")
    t2 = DependencyTopology.from_dict(t.to_canonical_dict())
    assert t2.digest() == t.digest()


def test_topology_from_dict_rejects_unknown_field():
    app, db = _s("app"), _s("db")
    t = DependencyTopology(subject=app, as_of=H.at(0))
    d = t.to_canonical_dict()
    d["surprise"] = 1
    with pytest.raises(TopologyError):
        DependencyTopology.from_dict(d)
