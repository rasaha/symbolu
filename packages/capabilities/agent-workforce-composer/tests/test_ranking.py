"""Ranking tests (§31 Ranking; invariants P2-I1..I6)."""
from __future__ import annotations

from ugence_agent_workforce_composer import fixtures
from ugence_agent_workforce_composer.contracts import EligibilityState
from ugence_agent_workforce_composer.ranking import rank_eligible_candidates
from ugence_agent_workforce_composer.scoring import (
    SCORE_REPRESENTATION,
    normalize_higher_better,
    normalize_lower_better,
)
from ._p2 import role_report


def _rank(name="procurement", node="proc_supplier_evidence"):
    role, rep, snap = role_report(name, node)
    return role, rep, snap, rank_eligible_candidates(role, rep, snap, fixtures.ranking_policy(),
                                                     fixtures.LOGICAL_TIME)


def test_only_eligible_agents_ranked():
    role, rep, snap, ranking = _rank()
    eligible = {(r.agent_id, r.agent_version) for r in rep.results
                if r.state is EligibilityState.ELIGIBLE}
    ranked = {(c.agent_id, c.agent_version) for c in ranking.ranked_candidates}
    assert ranked == eligible
    assert ranking.excluded_candidate_count == len(rep.results) - len(eligible)


def test_every_eligible_agent_ranked_once():
    _r, _rep, _s, ranking = _rank()
    idents = [(c.agent_id, c.agent_version) for c in ranking.ranked_candidates]
    assert len(idents) == len(set(idents))


def test_ineligible_never_ranked():
    _r, rep, _s, ranking = _rank()
    ranked = {(c.agent_id, c.agent_version) for c in ranking.ranked_candidates}
    for r in rep.results:
        if r.state is not EligibilityState.ELIGIBLE:
            assert (r.agent_id, r.agent_version) not in ranked


def test_score_reconstruction():
    _r, _rep, _s, ranking = _rank()
    for c in ranking.ranked_candidates:
        assert c.total_score == c.reconstruct_total()
        assert c.total_score == sum(cr.weighted_contribution_bp for cr in c.criterion_results)


def test_scores_are_integer_basis_points():
    _r, _rep, _s, ranking = _rank()
    assert SCORE_REPRESENTATION == "integer_basis_points"
    for c in ranking.ranked_candidates:
        assert isinstance(c.total_score, int)
        assert 0 <= c.total_score <= 10000


def test_ranking_determinism_and_ordering_independence():
    role, rep, snap, r1 = _rank()
    r2 = rank_eligible_candidates(role, rep, snap, fixtures.ranking_policy(), fixtures.LOGICAL_TIME)
    assert r1.ranking_fingerprint == r2.ranking_fingerprint
    # ranks strictly increasing and total order
    ranks = [c.rank for c in r1.ranked_candidates]
    assert ranks == sorted(ranks) == list(range(1, len(ranks) + 1))


def test_ranks_ordered_by_descending_score():
    _r, _rep, _s, ranking = _rank()
    scores = [c.total_score for c in ranking.ranked_candidates]
    assert scores == sorted(scores, reverse=True)


def test_monotonic_higher_better():
    assert normalize_higher_better(0.5, 0, 1) <= normalize_higher_better(0.6, 0, 1)
    assert normalize_higher_better(1.0, 0, 1) == 10000
    assert normalize_higher_better(0.0, 0, 1) == 0


def test_monotonic_lower_better_penalty():
    # higher cost/latency must not yield a better (higher) normalized value
    assert normalize_lower_better(100, 0, 1000) >= normalize_lower_better(200, 0, 1000)
    assert normalize_lower_better(0, 0, 1000) == 10000


def test_deterministic_tie_break_total_order():
    _r, _rep, _s, ranking = _rank()
    keys = [c.tie_break_values for c in ranking.ranked_candidates]
    assert len(keys) == len(set(keys))  # unique total order via identity tail


def test_zero_and_one_eligible_candidate():
    # security threat-analysis role: exactly one eligible (cyber analyst)
    role, rep, snap = role_report("security", "sec_threat_analysis")
    ranking = rank_eligible_candidates(role, rep, snap, fixtures.ranking_policy(), fixtures.LOGICAL_TIME)
    assert ranking.eligible_candidate_count == 1
    assert len(ranking.ranked_candidates) == 1 and ranking.ranked_candidates[0].rank == 1
    # evidence-collection role: zero eligible → empty ranking
    role0, rep0, snap0 = role_report("security", "sec_evidence_collection")
    r0 = rank_eligible_candidates(role0, rep0, snap0, fixtures.ranking_policy(), fixtures.LOGICAL_TIME)
    assert r0.eligible_candidate_count == 0 and r0.ranked_candidates == ()
