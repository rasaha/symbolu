"""Fallback-planning tests (§31 Fallback; P2-I14,I15,I16)."""
from __future__ import annotations

from ugence_agent_workforce_composer import fixtures
from ugence_agent_workforce_composer.composition_contracts import FallbackState
from ugence_agent_workforce_composer.contracts import EligibilityState as ES
from ugence_agent_workforce_composer.fallback import build_fallback_plan
from ugence_agent_workforce_composer.ranking import rank_eligible_candidates
from ._p2 import role_report


def _plan(name, node):
    role, rep, snap = role_report(name, node)
    ranking = rank_eligible_candidates(role, rep, snap, fixtures.ranking_policy(), fixtures.LOGICAL_TIME)
    primary = ranking.ranked_candidates[0]
    fp = build_fallback_plan(role, ranking, primary.agent_id, primary.agent_version, snap,
                             fixtures.enterprise_policy(), fixtures.permission_policy(),
                             fixtures.fallback_policy())
    return role, rep, snap, ranking, primary, fp


def test_fallback_only_from_eligible_and_excludes_primary():
    role, rep, snap, ranking, primary, fp = _plan("procurement", "proc_supplier_evidence")
    eligible = {(r.agent_id, r.agent_version) for r in rep.results if r.state is ES.ELIGIBLE}
    for c in fp.candidates:
        assert (c.agent_id, c.agent_version) in eligible          # P2-I14
        assert (c.agent_id, c.agent_version) != (primary.agent_id, primary.agent_version)  # P2-I15
        assert snap.profile(c.agent_id, c.agent_version) is not None  # P2-I16 snapshot pinning


def test_fallback_unique_and_ordered():
    _r, _rep, _s, _rk, _p, fp = _plan("procurement", "proc_supplier_evidence")
    idents = [(c.agent_id, c.agent_version) for c in fp.candidates]
    assert len(idents) == len(set(idents))
    assert [c.fallback_order for c in fp.candidates] == list(range(1, len(fp.candidates) + 1))


def test_fallback_depth_respected():
    _r, _rep, _s, _rk, _p, fp = _plan("procurement", "proc_supplier_evidence")
    assert len(fp.candidates) <= fixtures.fallback_policy().maximum_fallback_depth


def test_no_fallback_reported_honestly():
    # supplier-risk has exactly one eligible agent → no alternative exists
    _r, _rep, _s, _rk, _p, fp = _plan("procurement", "proc_supplier_risk")
    assert fp.fallback_state is FallbackState.NO_FALLBACK_AVAILABLE
    assert fp.candidates == ()


def test_fallback_permission_feasible():
    _r, _rep, _s, _rk, _p, fp = _plan("procurement", "proc_supplier_evidence")
    for c in fp.candidates:
        assert c.permission_bound_ref  # a feasible permission bound was computed


def test_fallback_deterministic():
    r1 = _plan("procurement", "proc_supplier_evidence")[5]
    r2 = _plan("procurement", "proc_supplier_evidence")[5]
    assert r1.plan_fingerprint == r2.plan_fingerprint


def test_fallback_diversity_preferred():
    _r, _rep, _s, _rk, primary, fp = _plan("procurement", "proc_supplier_evidence")
    # with diversity preference, a different-provider candidate is ordered first when present
    comps = [c.failure_domain_comparison for c in fp.candidates]
    if "different_provider" in comps and "same_provider" in comps:
        assert comps.index("different_provider") < comps.index("same_provider")
