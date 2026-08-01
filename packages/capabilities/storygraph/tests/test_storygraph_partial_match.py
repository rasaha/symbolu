"""Corrected partial-match semantics (Run 2, matcher/2.0.0).

Regression + behavior tests for the fix to the Run-1 defect: a non-evaluable edge
is never treated as satisfied, dimensions never default to 1.0 on a zero
denominator, and a partial story requires positive discriminating evidence before
escalation — while exact completion, non-compensatory gates, verified-context
safety, determinism, and non-mutation are preserved.
"""

from __future__ import annotations

import pytest

from ugence_storygraph import (
    ACCOUNT_RECOVERY_STORY, ACCOUNT_TAKEOVER_TRANSFER as ATO, Authorization,
    MATCHER_SEMANTICS_VERSION, ObservedEvent, evaluate_proposed_action,
    story_match, storyverdict,
)
from ugence_storygraph import financial as F
from ugence_storygraph.storygraph import (
    DIM_FAILED, DIM_NOT_APPLICABLE, DIM_NOT_EVALUABLE, DIM_SATISFIED,
    EDGE_AMBIGUOUS, EDGE_FAILED, EDGE_NOT_EVALUABLE, EDGE_SATISFIED,
    PARTIAL_ESCALATION_POLICY_VERSION, StoryGraph, StoryNode, order, same_entity,
    within,
)

V = storyverdict


def oe(frag, eid, pos, **ent):
    return ObservedEvent(fragment_id=frag, event_id=eid, position=pos, epoch=None,
                         actor="u1", entities=dict(ent))


def _assembly():
    return [oe(F.CRED_RESET, "reset", 1, account="a1"),
            oe(F.DEVICE_NEW, "device", 2, account="a1", device="d1"),
            oe(F.BENEFICIARY_ADD, "benef", 3, account="a1", beneficiary="bob")]


def _transfer(pos=99, **over):
    ent = {"account": "a1", "beneficiary": "bob", "device": "d1", "amount": "9000"}
    ent.update(over)
    return oe(F.TRANSFER, "xfer", pos, **ent)


def _full(**over):
    return _assembly() + [_transfer(pos=4, **over)]


# ===========================================================================
# §3/§4  explicit edge states
# ===========================================================================
def test_edge_states_are_explicit_and_reported():
    m = story_match(ATO, _full())
    states = {r["state"] for r in m.edge_results}
    assert EDGE_SATISFIED in states
    # every edge record carries the §4 fields
    for r in m.edge_results:
        for k in ("edge_id", "kind", "state", "mandatory", "is_discriminating",
                  "detail"):
            assert k in r


def test_absent_completion_makes_discriminators_not_evaluable():
    # the Run-1 defect scenario: reset+device only, no transfer.
    m = story_match(ATO, [oe(F.CRED_RESET, "reset", 1, account="a1"),
                          oe(F.DEVICE_NEW, "device", 2, account="a1", device="d1")])
    # edges that reference the absent xfer node are NOT_EVALUABLE, never SATISFIED
    ne = [r for r in m.not_evaluable_edges]
    assert ne, "discriminating edges to the absent completion must be NOT_EVALUABLE"
    assert all(r["state"] == EDGE_NOT_EVALUABLE for r in ne)


def test_wrong_beneficiary_edge_is_failed_not_absent():
    m = story_match(ATO, _full(beneficiary="eve"))
    benef = next(r for r in m.edge_results
                 if r["kind"] == "SAME_ENTITY" and r["dim"] == "beneficiary")
    assert benef["state"] == EDGE_FAILED
    assert benef["detail"]["expected"] == "bob" and benef["detail"]["observed"] == "eve"


def test_equal_coordinates_are_ambiguous_not_satisfied():
    ev = [oe(F.CRED_RESET, "reset", 5, account="a1"),
          oe(F.DEVICE_NEW, "device", 5, account="a1", device="d1"),
          oe(F.BENEFICIARY_ADD, "benef", 5, account="a1", beneficiary="bob"),
          oe(F.TRANSFER, "xfer", 5, account="a1", beneficiary="bob", device="d1",
             amount="9000")]
    m = story_match(ATO, ev)
    assert any(r["state"] == EDGE_AMBIGUOUS for r in m.edge_results)
    assert m.ordering_ambiguous and not m.is_complete()


# ===========================================================================
# §5  dimension results — NEVER a bare 1.0 on a zero denominator
# ===========================================================================
def test_non_evaluable_dimension_is_not_1_0():
    # THE core regression: entity/ordering/timing over the absent completion must
    # report NOT_EVALUABLE with a None ratio and a 0.0 scalar — not 1.0.
    m = story_match(ATO, [oe(F.CRED_RESET, "reset", 1, account="a1"),
                          oe(F.DEVICE_NEW, "device", 2, account="a1", device="d1")])
    ent = m.dimension_results["entity_consistency"]
    assert ent["status"] == DIM_NOT_EVALUABLE
    assert ent["evaluable_ratio"] is None
    assert m.risk.entity_consistency == 0.0            # NOT 1.0
    assert m.risk.harmful_score < ATO.threat_threshold  # cannot clear the threshold


def test_dimension_counts_present():
    m = story_match(ATO, _full())
    ent = m.dimension_results["entity_consistency"]
    for k in ("satisfied_count", "failed_count", "not_evaluable_count",
              "ambiguous_count", "applicable_count", "status", "evaluable_ratio"):
        assert k in ent
    assert ent["status"] == DIM_SATISFIED
    assert m.dimension_results["corroboration"]["status"] == DIM_NOT_APPLICABLE


def test_failed_dimension_status():
    m = story_match(ATO, _full(beneficiary="eve"))
    assert m.dimension_results["entity_consistency"]["status"] == DIM_FAILED


# ===========================================================================
# §7  positive-evidence partial-escalation gate (the defect fix)
# ===========================================================================
def test_partial_benign_does_not_escalate_without_discriminating_evidence():
    # reset+device+ (proposed limit), no completion, no verified context.
    r = evaluate_proposed_action(
        [oe(F.CRED_RESET, "reset", 1, account="a1"),
         oe(F.DEVICE_NEW, "device", 2, account="a1", device="d1")],
        oe(F.LIMIT_UP, "limit", 3, account="a1"), ATO)
    assert r.category != V.THREAT_CONSISTENT_WITH_INSUFFICIENT_CONTEXT
    assert r.signal != "ESCALATE"


def test_escalation_eligible_requires_positive_evidence():
    m = story_match(ATO, [oe(F.CRED_RESET, "reset", 1, account="a1"),
                          oe(F.DEVICE_NEW, "device", 2, account="a1", device="d1")])
    assert m.escalation_eligible is False
    assert m.escalation_reasons                       # explains why
    assert m.discriminating_satisfied == 0


def test_complete_true_story_is_escalation_eligible():
    m = story_match(ATO, _full())
    assert m.escalation_eligible is True
    assert m.discriminating_satisfied >= 1


# ===========================================================================
# §6  mandatory non-compensatory gates (required proofs)
# ===========================================================================
def test_full_coverage_cannot_compensate_wrong_account():
    m = story_match(ATO, _full(account="a2"))
    assert m.risk.coverage == 1.0
    assert not m.is_complete()


def test_correct_timing_cannot_compensate_wrong_beneficiary():
    m = story_match(ATO, _full(beneficiary="eve"))   # in-window, wrong beneficiary
    assert m.dimension_results["timing_consistency"]["status"] == DIM_SATISFIED
    assert not m.is_complete()


def test_optional_abundance_cannot_compensate_missing_required():
    # device (required) missing; limit (optional) present and proposed transfer.
    r = evaluate_proposed_action(
        [oe(F.CRED_RESET, "reset", 1, account="a1"),
         oe(F.BENEFICIARY_ADD, "benef", 2, account="a1", beneficiary="bob"),
         oe(F.LIMIT_UP, "limit", 3, account="a1")],
        _transfer(), ATO)
    assert r.category != V.WOULD_COMPLETE_PROHIBITED_CAPABILITY
    assert r.completion_witness is None


def test_correct_entity_cannot_compensate_invalid_ordering():
    ev = _assembly() + [oe(F.TRANSFER, "xfer", 0, account="a1", beneficiary="bob",
                           device="d1", amount="9000")]   # transfer before setup
    m = story_match(ATO, ev)
    assert m.dimension_results["entity_consistency"]["status"] == DIM_SATISFIED
    assert m.risk.gate_triggered and not m.is_complete()


def test_non_evaluable_completion_edge_cannot_count_as_satisfied():
    # transfer present but its beneficiary entity is ABSENT => SAME_ENTITY(benef) is
    # NOT_EVALUABLE => the mandatory edge is unsatisfied => no completion.
    ev = _assembly() + [oe(F.TRANSFER, "xfer", 4, account="a1", device="d1",
                           amount="9000")]              # no beneficiary entity
    m = story_match(ATO, ev)
    benef = next(r for r in m.edge_results
                 if r["kind"] == "SAME_ENTITY" and r["dim"] == "beneficiary")
    assert benef["state"] == EDGE_NOT_EVALUABLE
    assert m.mandatory_unsatisfied and not m.is_complete()


def test_legit_coverage_cannot_override_hard_policy_violation():
    r = evaluate_proposed_action(
        _assembly(), _transfer(), ATO,
        legitimate_stories=[ACCOUNT_RECOVERY_STORY],
        authorizations=[Authorization("customer_account_recovery", True,
                                      frozenset({"PASSWORD_RESET", "DEVICE_REGISTER",
                                                 "TRANSFER"}), account="a1")],
        facts={"confirmed_violation": True})
    assert r.category == V.HARD_POLICY_VIOLATION


# ===========================================================================
# §9  exact completion preserved
# ===========================================================================
def test_exact_completion_unchanged():
    r = evaluate_proposed_action(_assembly(), _transfer(), ATO)
    assert r.category == V.WOULD_COMPLETE_PROHIBITED_CAPABILITY
    assert r.completion_witness["minimality_verified"] is True


# ===========================================================================
# §10  verified-context: "not verified" is not "positively harmful"
# ===========================================================================
def test_missing_authorization_does_not_strengthen_harmful():
    with_auth = story_match(ATO, _full())
    # coverage/entity consistency are identical whether or not a benign auth exists;
    # absence of an authorization must not raise the harmful structural dimensions.
    r_no = evaluate_proposed_action(_assembly(), _transfer(), ATO)
    r_yes = evaluate_proposed_action(
        _assembly(), _transfer(), ATO, legitimate_stories=[ACCOUNT_RECOVERY_STORY],
        authorizations=[Authorization("customer_account_recovery", True,
                                      frozenset({"PASSWORD_RESET", "DEVICE_REGISTER"}),
                                      account="a1")])
    assert r_no.structural_vector["entity_binding_consistency"] == \
        r_yes.structural_vector["entity_binding_consistency"]


# ===========================================================================
# versioning + prior-run preservation
# ===========================================================================
def test_versions_are_bumped_and_reported():
    m = story_match(ATO, _full())
    assert m.matcher_semantics_version == MATCHER_SEMANTICS_VERSION
    assert MATCHER_SEMANTICS_VERSION == "ctd.storygraph.matcher/2.0.0"
    assert PARTIAL_ESCALATION_POLICY_VERSION == "ctd.partial_escalation/1.0.0"


def test_prior_run_preserved():
    from ugence_storygraph.evaluation.prior_runs import RUN_1
    assert RUN_1["status"] == "SUPERSEDED"
    assert RUN_1["commit"] == "78911a9f"
    assert RUN_1["metrics"]["benign_escalate_advisory_rate"] == 0.75
    assert RUN_1["corrected_verdict"] == \
        "CONTINUE — StoryGraph adversarial validation incomplete"


def test_freeze_binds_new_semantics_and_corpus():
    from ugence_storygraph.evaluation import freeze
    cfg = freeze.current_config()
    assert cfg["matcher_semantics"] == MATCHER_SEMANTICS_VERSION
    assert cfg["partial_escalation_policy_version"] == PARTIAL_ESCALATION_POLICY_VERSION
    assert "final" in cfg["story_corpus_v2_hashes"]
