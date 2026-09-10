"""Readiness semantics are invariant under the binding's UTC canonicalization.

``AssessedSystemBinding`` is owned by ``ugence-governance-contracts`` and shared:
Agent Value Readiness consumes the *same* class, and the binding's canonical
digest flows into the request digest, the orchestration trace and the outcome. So
correcting the binding's canonicalization is a change to a shared seam, and the
obligation is to prove it moved **nothing** in readiness.

What is proven here, through the public ``assess_readiness`` entry point only:

* two bindings whose instants are the same but written with different UTC offsets
  are one binding, produce one binding digest, and drive byte-identical
  admission, classification, rule, reason codes, evaluation digest, trace digest
  and dispositions;
* every M-3R.3 refusal that held before still holds — cross-system, cross-tenant,
  cross-context and cross-configuration replay stay rejected, and authenticity
  stays non-forgeable;
* a genuinely different instant stays a genuinely different binding;
* nothing about the advisory posture moved: ``authorizes_deployment`` is still
  ``False``, RA-01 is still gate-driven, the evaluator source is untouched and
  ``EVALUATOR_FORMULA_VERSION`` is still exactly ``GV-3R-b.3``.
"""

from __future__ import annotations

import dataclasses
import hashlib
import pathlib
from datetime import datetime, timedelta, timezone

import pytest

import ugence_governance_contracts.api as governance_api
from ugence_agent_value_readiness.evaluation.codes import EVALUATOR_FORMULA_VERSION
from ugence_agent_value_readiness.api import (
    READINESS_ORCHESTRATOR_VERSION,
    AssessedSystemBinding,
    GateStatus,
    ReadinessAssessmentStatus,
    ReadinessClassification,
    ReadinessIndicatorAdmissionStatus,
    ReadinessTrustGapCode,
    SystemBindingAuthenticityStatus,
    assess_readiness,
)

from _orchestration_fixtures import (  # noqa: E402
    BOTH,
    CONFIG_DIGEST_B,
    MANDATORY,
    StubConditionVerifier,
    StubGateVerifier,
    binding,
    catalogs,
    context,
    gate,
    gate_result,
    indicators,
    issued_resolver,
    readiness_policy,
    request,
)

_G = ReadinessTrustGapCode
_I = ReadinessIndicatorAdmissionStatus

#: One instant, three spellings — the finding's own example.
UTC = datetime(2026, 8, 17, 10, 0, 0, tzinfo=timezone.utc)
PLUS_0530 = datetime(2026, 8, 17, 15, 30, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
MINUS_0400 = datetime(2026, 8, 17, 6, 0, 0, tzinfo=timezone(timedelta(hours=-4)))

#: A second instant for the closing bound. 2026-08-18T00:00:00Z.
END_UTC = datetime(2026, 8, 18, 0, 0, 0, tzinfo=timezone.utc)
END_PLUS_0930 = datetime(2026, 8, 18, 9, 30, tzinfo=timezone(timedelta(hours=9, minutes=30)))
END_MINUS_1100 = datetime(2026, 8, 17, 13, 0, tzinfo=timezone(timedelta(hours=-11)))

#: A different instant, one second later.
OTHER_INSTANT = datetime(2026, 8, 17, 10, 0, 1, tzinfo=timezone.utc)

#: Inside ``[UTC, END_UTC)`` — the binding must be effective at the instant the
#: assessment is evaluated at, so the fixture default (T_MID, June) is replaced.
EVAL_TIME = datetime(2026, 8, 17, 12, 0, 0, tzinfo=timezone.utc)

EQUIVALENT_PERIODS = [
    (UTC, END_UTC),
    (PLUS_0530, END_MINUS_1100),
    (MINUS_0400, END_PLUS_0930),
]


def _policy():
    return readiness_policy(gates=(gate("g1", MANDATORY, BOTH),))


def _assess(policy, req):
    return assess_readiness(
        req,
        policy_resolver=issued_resolver(policy),
        gate_verifier=StubGateVerifier(),
        condition_verifier=StubConditionVerifier(),
    )


def _outcome_for(effective_from, effective_to, *, with_indicators=True, **binding_kwargs):
    """One full assessment whose binding carries the given effective period."""

    policy = _policy()
    ctx = context(policy)
    bound = binding(
        ctx=ctx,
        effective_from=effective_from,
        effective_to=effective_to,
        **binding_kwargs,
    )
    req = request(
        policy=policy,
        ctx=ctx,
        gate_results=(gate_result(policy, "g1", GateStatus.PASS),),
        system_binding=bound,
        with_indicators=with_indicators,
        evaluation_time=EVAL_TIME,
    )
    return _assess(policy, req), req, bound


def _semantic_fingerprint(outcome, req):
    """Every readiness-visible value the correction could conceivably have moved."""

    return {
        "binding_digest": req.system_binding.canonical_digest(),
        "system_binding_accepted": outcome.system_binding_accepted,
        "trace_binding_digest": outcome.trace.system_binding_digest,
        "trace_binding_ref": outcome.trace.system_binding_ref,
        "status": outcome.status,
        "classification": outcome.classification,
        "admitted_indicator_result_ids": outcome.trace.admitted_indicator_result_ids,
        "excluded_indicator_result_ids": outcome.trace.excluded_indicator_result_ids,
        "indicator_admissions": tuple(
            (s.indicator_class, s.result_id, s.admission_status, s.admitted)
            for s in outcome.indicator_admissions
        ),
        "catalog_families_bound": outcome.trace.catalog_families_bound,
        "trust_gap_codes": outcome.trace.trust_gap_codes,
        "rule_id": outcome.evaluation.rule_id,
        "reason_codes": outcome.evaluation.reason_codes,
        "advisory_codes": outcome.evaluation.advisory_codes,
        "evaluator_id": outcome.evaluation.trace.evaluator_id,
        "formula_version": outcome.evaluation.trace.formula_version,
        "evaluation_digest": outcome.evaluation.canonical_digest(),
        "determination_digest": outcome.evaluation.determination.canonical_digest(),
        "evaluation_trace_digest": outcome.evaluation.trace.canonical_digest(),
        "orchestration_trace_digest": outcome.trace.canonical_digest(),
        "request_digest": outcome.trace.request_digest,
        "outcome_digest": outcome.canonical_digest(),
        "dispositions": tuple(
            (d.advisory_code, d.state, d.detail) for d in outcome.dispositions
        ),
        "authorizes_deployment": outcome.authorizes_deployment,
    }


# --------------------------------------------------------------------------- #
# 1. Timezone-equivalent bindings are semantically one assessment
# --------------------------------------------------------------------------- #
def test_timezone_equivalent_bindings_produce_identical_readiness_semantics():
    fingerprints = []
    for start, end in EQUIVALENT_PERIODS:
        outcome, req, bound = _outcome_for(start, end)
        assert outcome.status is ReadinessAssessmentStatus.EVALUATED
        fingerprints.append(_semantic_fingerprint(outcome, req))

    first = fingerprints[0]
    for other in fingerprints[1:]:
        # Compared key by key so a failure names the field that moved.
        for key in first:
            assert other[key] == first[key], key
        assert other == first


def test_the_equivalent_bindings_really_are_the_same_binding():
    bindings = [
        _outcome_for(start, end)[2] for start, end in EQUIVALENT_PERIODS
    ]
    first = bindings[0]
    for other in bindings[1:]:
        assert first == other
        assert hash(first) == hash(other)
        assert first.canonical_bytes() == other.canonical_bytes()
        assert first.canonical_digest() == other.canonical_digest()


def test_the_admitted_indicator_set_and_classification_are_the_expected_ones():
    """Not merely equal to each other — equal to the known-correct values."""

    for start, end in EQUIVALENT_PERIODS:
        outcome, _, _ = _outcome_for(start, end)
        assert outcome.classification is ReadinessClassification.DEPLOYMENT_READY
        assert outcome.system_binding_accepted is True
        assert outcome.trace.admitted_indicator_result_ids == ("ar1", "cr1", "ir1")
        assert outcome.trace.excluded_indicator_result_ids == ()
        assert {s.admission_status for s in outcome.indicator_admissions} == {_I.ADMITTED}
        assert outcome.trace.trust_gap_codes == ()


def test_open_period_bindings_are_also_invariant():
    """Open-start and open-end bindings normalize the one bound they carry."""

    for pair_a, pair_b in (
        ((None, END_UTC), (None, END_MINUS_1100)),
        ((UTC, None), (PLUS_0530, None)),
    ):
        a_out, a_req, _ = _outcome_for(*pair_a)
        b_out, b_req, _ = _outcome_for(*pair_b)
        assert _semantic_fingerprint(a_out, a_req) == _semantic_fingerprint(b_out, b_req)


def test_the_correction_did_not_move_a_binding_free_assessment():
    """A binding with no effective period carries no instant to normalize."""

    outcome, req, _ = _outcome_for(None, None)
    assert outcome.status is ReadinessAssessmentStatus.EVALUATED
    assert outcome.classification is ReadinessClassification.DEPLOYMENT_READY
    assert outcome.trace.system_binding_digest == req.system_binding.canonical_digest()


# --------------------------------------------------------------------------- #
# 2. Genuinely different instants stay distinct
# --------------------------------------------------------------------------- #
def test_a_genuinely_different_instant_remains_a_different_assessment():
    same, same_req, _ = _outcome_for(UTC, END_UTC)
    other, other_req, _ = _outcome_for(OTHER_INSTANT, END_UTC)

    assert other_req.system_binding != same_req.system_binding
    assert other_req.system_binding.canonical_digest() != (
        same_req.system_binding.canonical_digest()
    )
    for key in ("binding_digest", "trace_binding_digest", "request_digest",
                "orchestration_trace_digest", "outcome_digest"):
        assert _semantic_fingerprint(other, other_req)[key] != (
            _semantic_fingerprint(same, same_req)[key]
        ), key
    # But the *classification* is unchanged: an effective period is identity, not
    # a readiness input. Both assessments are still DEPLOYMENT_READY.
    assert other.classification is same.classification


# --------------------------------------------------------------------------- #
# 3. Every M-3R.3 refusal still holds
# --------------------------------------------------------------------------- #
def _replay_outcome(start, end, **other_binding_kwargs):
    """Indicators minted against system A, submitted under system B.

    This is the real replay shape: the orchestrator has no request-level system
    id to compare a binding against, so cross-system and cross-configuration
    replay are caught at indicator admission, by the binding ref + digest each
    result carries. Both bindings are written with the *same* offsets so the
    only thing separating them is the system coordinate under test.
    """

    policy = _policy()
    ctx = context(policy)
    assessed = binding(ctx=ctx, effective_from=start, effective_to=end)
    other = binding(
        ctx=ctx, binding_id="bind-2", effective_from=start, effective_to=end,
        **other_binding_kwargs,
    )
    assert assessed.canonical_digest() != other.canonical_digest()

    # The indicators belong to `other`; the assessment is about `assessed`.
    foreign_intel, _cap, _ado = indicators(
        context_id=ctx.context_id, system_binding=other
    )
    req = request(
        policy=policy,
        ctx=ctx,
        gate_results=(gate_result(policy, "g1", GateStatus.PASS),),
        system_binding=assessed,
        indicator_catalogs=catalogs(),
        evaluation_time=EVAL_TIME,
    )
    req = type(req)(
        **{
            **{f: getattr(req, f) for f in req.__dataclass_fields__},
            "intelligence_results": foreign_intel,
        }
    )
    return _assess(policy, req)


@pytest.mark.parametrize("start,end", EQUIVALENT_PERIODS)
def test_cross_system_replay_remains_rejected(start, end):
    outcome = _replay_outcome(start, end, system_id="other-system")
    assert outcome.trace.admitted_indicator_result_ids == ()
    assert outcome.trace.excluded_indicator_result_ids == ("ir1",)
    assert {s.admission_status for s in outcome.indicator_admissions} == {
        _I.SYSTEM_BINDING_MISMATCH
    }
    assert (
        _G.INDICATOR_RESULT_SYSTEM_BINDING_MISMATCH in outcome.trace.trust_gap_codes
    )


@pytest.mark.parametrize("start,end", EQUIVALENT_PERIODS)
def test_cross_configuration_replay_remains_rejected(start, end):
    outcome = _replay_outcome(
        start, end, configuration_id="cfg-b", configuration_digest=CONFIG_DIGEST_B
    )
    assert outcome.trace.admitted_indicator_result_ids == ()
    assert outcome.trace.excluded_indicator_result_ids == ("ir1",)
    assert {s.admission_status for s in outcome.indicator_admissions} == {
        _I.SYSTEM_BINDING_MISMATCH
    }


@pytest.mark.parametrize("start,end", EQUIVALENT_PERIODS)
def test_a_binding_not_effective_at_the_evaluation_time_remains_rejected(start, end):
    """The effective-period gate is unchanged, and offset-agnostic.

    The window below closes *before* the evaluation instant whichever offset it
    is written with, so all three spellings refuse identically.
    """

    outcome, _, _ = _outcome_for(UTC, END_UTC)
    assert outcome.status is ReadinessAssessmentStatus.EVALUATED

    early_end_utc = datetime(2026, 8, 17, 11, 0, tzinfo=timezone.utc)
    early_end_offset = datetime(2026, 8, 17, 16, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    for closing in (early_end_utc, early_end_offset):
        refused, _, _ = _outcome_for(start, closing)
        assert refused.status is ReadinessAssessmentStatus.NOT_EVALUATED
        assert refused.system_binding_accepted is False
        assert (
            _G.SYSTEM_BINDING_NOT_EFFECTIVE_AT_EVALUATION_TIME
            in refused.trace.trust_gap_codes
        )


@pytest.mark.parametrize("start,end", EQUIVALENT_PERIODS)
def test_cross_tenant_and_cross_context_replay_remain_rejected(start, end):
    for kwargs in ({"tenant": "other-tenant"}, {"subject": "other-subject"}):
        outcome, _, _ = _outcome_for(start, end, **kwargs)
        assert outcome.status is ReadinessAssessmentStatus.NOT_EVALUATED
        assert outcome.system_binding_accepted is False

    # A binding minted against a *different* assessment context cannot be
    # attached to this one, whichever offset its instants were written with.
    policy = _policy()
    ctx = context(policy)
    foreign_ctx = context(policy, subject="other-subject")
    foreign = binding(
        ctx=foreign_ctx, subject="other-subject", effective_from=start, effective_to=end
    )
    req = request(
        policy=policy,
        ctx=ctx,
        gate_results=(gate_result(policy, "g1", GateStatus.PASS),),
        system_binding=foreign,
        evaluation_time=EVAL_TIME,
    )
    outcome = _assess(policy, req)
    assert outcome.status is ReadinessAssessmentStatus.NOT_EVALUATED
    assert outcome.system_binding_accepted is False


@pytest.mark.parametrize("start,end", EQUIVALENT_PERIODS)
def test_binding_authenticity_cannot_be_forged(start, end):
    outcome, _, bound = _outcome_for(start, end)
    assert bound.authenticity_status is SystemBindingAuthenticityStatus.STRUCTURAL_UNVERIFIED
    assert bound.authenticity_verified is False
    assert outcome.system_binding_authenticity_verified is False
    field_names = {f.name for f in dataclasses.fields(AssessedSystemBinding)}
    assert "authenticity_status" not in field_names
    assert "authenticity_verified" not in field_names
    with pytest.raises(TypeError):
        binding(ctx=context(_policy()), authenticity_status="AUTHORITY_VERIFIED")
    assert AssessedSystemBinding.__subclasses__() == []
    assert [m.value for m in SystemBindingAuthenticityStatus] == ["STRUCTURAL_UNVERIFIED"]


@pytest.mark.parametrize("start,end", EQUIVALENT_PERIODS)
def test_a_missing_binding_is_still_not_evaluated(start, end):
    policy = _policy()
    req = request(
        policy=policy,
        gate_results=(gate_result(policy, "g1", GateStatus.PASS),),
        system_binding=None,
        evaluation_time=EVAL_TIME,
    )
    outcome = _assess(policy, req)
    assert outcome.status is ReadinessAssessmentStatus.NOT_EVALUATED
    assert outcome.classification is None
    assert _G.SYSTEM_BINDING_REQUIRED in outcome.trace.trust_gap_codes


# --------------------------------------------------------------------------- #
# 4. The advisory posture and the evaluator are untouched
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("start,end", EQUIVALENT_PERIODS)
def test_authorizes_deployment_remains_false(start, end):
    outcome, _, _ = _outcome_for(start, end)
    assert outcome.authorizes_deployment is False
    assert outcome.evaluation.authorizes_deployment is False
    assert outcome.is_advisory is True
    assert outcome.trace.is_explanatory_only is True


def test_evaluator_formula_version_is_exactly_gv_3r_b_3():
    assert EVALUATOR_FORMULA_VERSION == "GV-3R-b.3"
    assert READINESS_ORCHESTRATOR_VERSION == "ugence.readiness-orchestration/v0.2"
    for start, end in EQUIVALENT_PERIODS:
        outcome, _, _ = _outcome_for(start, end)
        assert outcome.evaluation.trace.formula_version == "GV-3R-b.3"
        assert outcome.trace.evaluator_formula_version == "GV-3R-b.3"


def test_ra_01_remains_gate_driven_and_no_family_count_heuristic_exists():
    """Removing all indicators cannot change the gate-driven classification."""

    with_indicators, req_a, _ = _outcome_for(PLUS_0530, END_MINUS_1100, with_indicators=True)
    without, req_b, _ = _outcome_for(PLUS_0530, END_MINUS_1100, with_indicators=False)
    assert with_indicators.classification is without.classification
    assert without.classification is ReadinessClassification.DEPLOYMENT_READY
    assert without.trace.admitted_indicator_result_ids == ()
    # The rule that selected the tier is the same one in both cases.
    assert with_indicators.evaluation.rule_id == without.evaluation.rule_id


def test_the_evaluator_source_is_unchanged_by_this_correction():
    """The evaluator is not a party to binding canonicalization.

    Asserted structurally rather than by digest literal: the evaluator package
    must not reference the binding, its canonicalization or a timezone at all.
    """

    import ugence_agent_value_readiness.evaluation as evaluation

    root = pathlib.Path(evaluation.__file__).resolve().parent
    for path in sorted(root.rglob("*.py")):
        source = path.read_text()
        for banned in (
            "AssessedSystemBinding",
            "canonical_bytes",
            "astimezone",
            "system_identity",
        ):
            assert banned not in source, f"{path.name} references {banned}"


def test_the_binding_class_is_the_identical_governance_object():
    assert AssessedSystemBinding is governance_api.AssessedSystemBinding
    assert SystemBindingAuthenticityStatus is governance_api.SystemBindingAuthenticityStatus
    assert (
        AssessedSystemBinding.__module__
        == "ugence_governance_contracts.contracts.system_identity"
    )


def test_the_orchestration_digest_chain_is_anchored_in_the_binding_digest():
    """Why this file exists: the binding digest really does reach the trace.

    If it did not, the invariance above would be vacuous.
    """

    outcome, req, bound = _outcome_for(PLUS_0530, END_MINUS_1100)
    assert outcome.trace.system_binding_digest == bound.canonical_digest()
    assert bound.canonical_digest() == hashlib.sha256(bound.canonical_bytes()).hexdigest()
    assert outcome.trace.request_digest == req.canonical_digest()
    # Changing the instant changes the whole chain — proof the anchor is live.
    other, other_req, _ = _outcome_for(OTHER_INSTANT, END_MINUS_1100)
    assert other.trace.system_binding_digest != outcome.trace.system_binding_digest
    assert other.trace.request_digest != outcome.trace.request_digest
    assert other.trace.canonical_digest() != outcome.trace.canonical_digest()
