"""Role dependency/interface graph tests (§31 Dependency graph; P2-I10)."""
from __future__ import annotations

from ugence_agent_workforce_composer.dependency import build_role_dependency_graph
from ._p2 import adaptation


def _graph(name="procurement"):
    adapt = adaptation(name)
    return adapt, build_role_dependency_graph(tuple(adapt.role_requirements))


def test_valid_dependencies_from_contracts():
    adapt, g = _graph("procurement")
    # supplier_evidence (out: supplier_evidence) -> supplier_risk (in: supplier_evidence)
    pairs = {(d.upstream_role_id, d.downstream_role_id) for d in g.dependencies}
    assert ("role::proc_supplier_evidence", "role::proc_supplier_risk") in pairs
    for d in g.dependencies:
        assert d.dependency_fingerprint.startswith("sha256:")


def test_all_role_references_resolve():
    adapt, g = _graph("procurement")
    role_ids = {r.role_id for r in adapt.role_requirements}
    for d in g.dependencies:
        assert d.upstream_role_id in role_ids and d.downstream_role_id in role_ids


def test_no_cycle_in_linear_workflows():
    for name in ("procurement", "support", "security"):
        _a, g = _graph(name)
        assert g.has_cycle is False


def test_graph_deterministic():
    _a1, g1 = _graph("procurement")
    _a2, g2 = _graph("procurement")
    assert g1.graph_fingerprint == g2.graph_fingerprint


def test_provenance_preserved():
    _a, g = _graph("procurement")
    assert all(d.provenance.source_kind == "p1_role_contracts" for d in g.dependencies)


def test_unknown_overlay_reference_flagged():
    adapt = adaptation("procurement")
    g = build_role_dependency_graph(tuple(adapt.role_requirements),
                                    overlay={"dependencies": [
                                        {"upstream_role_id": "ghost", "downstream_role_id": "role::proc_supplier_risk",
                                         "contract": "x"}]})
    assert any("unknown role" in d for d in g.diagnostics)
