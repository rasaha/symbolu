"""RELEASE GATE — the vNext lattice is non-compensatory and fails closed.

Two properties carry the safety of the whole evaluator:

* **non-compensatory aggregation** — no number of satisfied conditions offsets a
  single dispositive restriction (ported from the reference evaluator's
  ``_SEVERITY`` minimum);
* **fail-closed defaults** — uncertainty, an unmapped tier, and an expired
  authorization never reach an authorizing outcome.
"""

from __future__ import annotations

import pytest

from ugence_actiongate_provider.vnext import (
    DEFAULT_TIER,
    NEUTRAL_OUTCOME_STAGED,
    NEUTRAL_OUTCOME_V2,
    NON_SOFTENABLE,
    TIER_PRECEDENCE,
    ActionGatePolicy,
    ActionGateReasonCode as RC,
    ActionGateTier as Tier,
    ParameterBound,
    VNextAuthorizationRequest as Req,
    combine_tiers,
    evaluate,
)

ACT = "TRANSFER"
_AUTHORIZING = {"AUTHORIZED", "AUTHORIZED_WITH_CONSTRAINTS"}


def _policy(**kw) -> ActionGatePolicy:
    return ActionGatePolicy(policy_id="test", policy_version="1", **kw)


# --- precedence ------------------------------------------------------------

def test_precedence_is_a_total_order_over_the_tiers():
    assert set(TIER_PRECEDENCE) == set(Tier)
    assert len(set(TIER_PRECEDENCE.values())) == len(Tier), "tiers must not tie"


def test_expired_outranks_denied_outranks_everything_else():
    order = sorted(Tier, key=lambda t: TIER_PRECEDENCE[t])
    assert order[0] is Tier.EXPIRED
    assert order[1] is Tier.DENIED
    assert order[-1] is Tier.AUTHORIZED


def test_one_restriction_is_not_offset_by_many_satisfactions():
    """The defining property of a non-compensatory gate."""
    p = _policy(
        principal_allowlist=frozenset({"alice"}),
        accepted_authority_contexts={ACT: ("delegated:treasurer",)},
        permitted_resource_prefixes={ACT: ("ledger:",)},
        minimum_evidence_refs={ACT: 1},
        risk_deny_scores=frozenset({"critical"}))
    # everything satisfied except one denial
    d = evaluate(Req(ACT, principal="alice", authority="delegated:treasurer",
                     resource="ledger:1", evidence_refs=("e1", "e2", "e3"),
                     risk_context={"score": "critical"}), p)
    assert d.tier is Tier.DENIED
    assert not d.authorizes


def test_hardest_contribution_wins_regardless_of_order():
    mixed = [Tier.AUTHORIZED, Tier.EVIDENCE_REQUIRED, Tier.DENIED, Tier.AUTHORIZED]
    assert combine_tiers(mixed) is Tier.DENIED
    assert combine_tiers(list(reversed(mixed))) is Tier.DENIED


def test_no_contributions_authorizes():
    assert combine_tiers([]) is Tier.AUTHORIZED


# --- fail-closed -----------------------------------------------------------

@pytest.mark.parametrize("tier", list(Tier))
def test_every_tier_has_a_neutral_mapping_in_both_tables(tier):
    assert tier in NEUTRAL_OUTCOME_STAGED
    assert tier in NEUTRAL_OUTCOME_V2


def test_only_the_two_authorizing_tiers_map_to_authorizing_outcomes():
    for table in (NEUTRAL_OUTCOME_STAGED, NEUTRAL_OUTCOME_V2):
        for tier, outcome in table.items():
            authorizing = outcome in _AUTHORIZING
            expected = tier in (Tier.AUTHORIZED, Tier.AUTHORIZED_WITH_CONSTRAINTS)
            assert authorizing is expected, f"{tier} -> {outcome}"


def test_expiry_is_non_authorizing_in_both_staged_and_v2():
    d = evaluate(Req(ACT, authorization_expired=True), _policy())
    assert d.tier is Tier.EXPIRED
    assert d.neutral_outcome() == "INDETERMINATE"                       # staged
    assert d.neutral_outcome(expired_outcome_available=True) == "EXPIRED"  # after MAJOR
    assert not d.authorizes


def test_expiry_short_circuits_before_policy_is_consulted():
    """An expired authorization is not a policy question and must not be one."""
    permissive = _policy()
    d = evaluate(Req(ACT, principal="alice", authorization_expired=True), permissive)
    assert d.reason_codes == (RC.AUTHORIZATION_EXPIRED.value,)
    assert d.constraints == ()


def test_constraints_never_ride_on_a_non_authorizing_outcome():
    p = _policy(
        parameter_bounds=(ParameterBound("amount", deny_above=1000, constrain_above=100),),
        risk_deny_scores=frozenset({"critical"}))
    d = evaluate(Req(ACT, parameters={"amount": "500"},
                     risk_context={"score": "critical"}), p)
    assert d.tier is Tier.DENIED
    assert d.constraints == (), "a denied action must not carry actionable constraints"


# --- policy override safety ------------------------------------------------

def test_policy_may_elevate_a_soft_finding():
    p = _policy(minimum_evidence_refs={ACT: 1},
                tier_overrides={RC.EVIDENCE_INSUFFICIENT.value: Tier.DENIED})
    d = evaluate(Req(ACT, evidence_refs=()), p)
    assert d.tier is Tier.DENIED


@pytest.mark.parametrize("code", sorted(NON_SOFTENABLE, key=lambda c: c.value))
def test_policy_may_never_soften_a_boundary_violation(code):
    """A policy able to downgrade these could authorize around the boundary."""
    p = _policy(
        authority_required_action_types=frozenset({ACT}),
        principal_required_action_types=frozenset({ACT}),
        decision_ref_required_action_types=frozenset({ACT}),
        tier_overrides={code.value: Tier.AUTHORIZED})
    d = evaluate(Req(ACT), p)
    assert not d.authorizes
    assert DEFAULT_TIER[code] is Tier.DENIED or code is RC.AUTHORIZATION_EXPIRED


def test_softening_attempt_leaves_the_default_tier_intact():
    p = _policy(authority_required_action_types=frozenset({ACT}),
                tier_overrides={RC.AUTHORITY_ABSENT.value: Tier.AUTHORIZED})
    assert evaluate(Req(ACT, authority=""), p).tier is Tier.DENIED


@pytest.mark.parametrize("code", sorted(RC, key=lambda c: c.value))
@pytest.mark.parametrize("softer", sorted(Tier, key=lambda t: TIER_PRECEDENCE[t]))
def test_no_policy_override_softens_any_code_in_the_catalogue(code, softer):
    """The refusal that carries the safety is the precedence comparison.

    ``test_policy_may_never_soften_a_boundary_violation`` is parametrized over
    ``NON_SOFTENABLE``, so it reads as though membership of that set is what
    stops a policy downgrading a finding. It is not: ``_Accumulator._tier_for``
    accepts an override only when it is strictly more restrictive than the
    default, and that clause runs for every code. A test that exercises only
    the six members would still pass if the clause were deleted, which is the
    same shape of vacuity — asserting a property against a surface that is not
    what makes it true — this evaluator exists to remove.

    So assert it where it actually lives: over the whole catalogue, every tier
    strictly more permissive than a code's default is refused, leaving the
    default intact.
    """
    base = DEFAULT_TIER[code]
    if TIER_PRECEDENCE[softer] <= TIER_PRECEDENCE[base]:
        pytest.skip("not a softening of this code's default tier")
    p = _policy(
        denied_action_types=frozenset({ACT}),
        unknown_action_types=frozenset({ACT}),
        authority_required_action_types=frozenset({ACT}),
        principal_required_action_types=frozenset({ACT}),
        decision_ref_required_action_types=frozenset({ACT}),
        resource_required_action_types=frozenset({ACT}),
        permitted_resource_prefixes={ACT: ("allowed/",)},
        parameter_bounds=(ParameterBound("amount", deny_above=10, constrain_above=1),),
        risk_required_action_types=frozenset({ACT}),
        minimum_evidence_refs={ACT: 1},
        policy_ref_required_action_types=frozenset({ACT}),
        tier_overrides={code.value: softer})
    acc = evaluate.__globals__["_Accumulator"](p)
    assert acc._tier_for(code) is base, (
        f"policy softened {code.value} from {base.value} to {softer.value}")


# --- determinism -----------------------------------------------------------

def test_repeated_evaluation_is_byte_identical():
    p = _policy(risk_constrain_scores=frozenset({"medium"}),
                parameter_bounds=(ParameterBound("amount", deny_above=10, constrain_above=1),))
    r = Req(ACT, parameters={"amount": "5"}, risk_context={"score": "medium"})
    assert evaluate(r, p) == evaluate(r, p)


def test_reason_codes_are_canonically_ordered():
    p = _policy(principal_allowlist=frozenset({"alice"}),
                accepted_authority_contexts={ACT: ("x",)},
                permitted_resource_prefixes={ACT: ("ledger:",)})
    d = evaluate(Req(ACT, principal="mallory", authority="y", resource="payroll:1"), p)
    assert list(d.reason_codes) == sorted(d.reason_codes)
    assert len(set(d.reason_codes)) == len(d.reason_codes), "codes must be deduped"


def test_evaluator_reads_no_clock_and_touches_no_io():
    """Purity by construction: the module imports nothing that could do either."""
    import ast
    import pathlib

    import ugence_actiongate_provider.vnext.evaluator as mod

    tree = ast.parse(pathlib.Path(mod.__file__).read_text())
    banned = {"datetime", "time", "random", "os", "socket", "pathlib", "urllib"}
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level:
            imported.add((node.module or "").split(".")[0])
    assert not (imported & banned), f"evaluator imports {imported & banned}"
