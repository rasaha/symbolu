"""Gate-removal probes: proof that each check is load-bearing, not decorative.

A passing adversarial test proves the *current* code rejects a bad input. It does not
prove the rejection came from the gate you think it did — a test can pass because some
unrelated validation happened to fire first, leaving the intended gate dead code that
nobody would notice removing.

Each probe below **disables one gate** (monkeypatching it to a no-op or an always-accept)
and asserts that the corresponding attack **now succeeds**. If a probe fails, the gate it
targets is not what was stopping the attack, and the adversarial test guarding it is
weaker than it appears.

This is mutation testing scoped to the security-relevant gates, run as ordinary tests so
it executes on every CI run rather than in a separate tool nobody invokes.
"""

from __future__ import annotations

import pytest

from conftest import INSIDE_WINDOW, RecordingSeam, fixed_clock, reference_seam
from ugence_cloud_scaling_risk_integration import (
    AdapterOutcomeStatus,
    CloudScalingRiskAdapter,
    authenticity as authenticity_module,
    projection as projection_module,
)
from ugence_cloud_scaling_risk_integration import adapter as adapter_module


# --- probe 1: the recommendation-authenticity digest comparison ---------------------------


def test_removing_the_digest_comparison_lets_tampering_through(monkeypatch, recommendation):
    """Disable only the equality check inside ``_reconcile``."""

    tampered = dict(recommendation.to_canonical_dict())
    tampered["recommendation_id"] = "rec-TAMPERED"

    seam = RecordingSeam(decision=None)
    adapter = CloudScalingRiskAdapter(seam=seam, clock=fixed_clock(INSIDE_WINDOW))

    # Baseline: the gate is doing the work.
    assert (
        adapter.evaluate(tampered).status is AdapterOutcomeStatus.PROJECTION_REJECTED
    )
    assert not seam.reached

    # Now remove the gate — and only the gate.
    def _permissive(recomputed, *, carried, expected, artifact):
        return "gate-removed"

    monkeypatch.setattr(authenticity_module, "_reconcile", _permissive)

    live_seam = reference_seam()
    permissive_adapter = CloudScalingRiskAdapter(
        seam=live_seam, clock=fixed_clock(INSIDE_WINDOW)
    )
    outcome = permissive_adapter.evaluate(tampered)
    assert outcome.status is AdapterOutcomeStatus.RISK_DECISION, (
        "with the digest comparison removed the tampered payload should sail through — "
        "it did not, so the comparison is NOT what was rejecting it"
    )


def test_removing_the_expectation_requirement_permits_the_self_referential_check(
    monkeypatch, recommendation
):
    """Disable the 'at least one independent expectation' requirement."""

    adapter = CloudScalingRiskAdapter(
        seam=reference_seam(), clock=fixed_clock(INSIDE_WINDOW)
    )
    # Baseline: a live object with no expectation is refused.
    assert (
        adapter.evaluate(recommendation).status
        is AdapterOutcomeStatus.PROJECTION_REJECTED
    )

    original = authenticity_module._reconcile

    def _no_expectation_required(recomputed, *, carried, expected, artifact):
        if carried is None and expected is None:
            return "gate-removed"
        return original(recomputed, carried=carried, expected=expected, artifact=artifact)

    monkeypatch.setattr(authenticity_module, "_reconcile", _no_expectation_required)
    outcome = adapter.evaluate(recommendation)
    assert outcome.status is AdapterOutcomeStatus.RISK_DECISION, (
        "with the requirement removed the unverified object should be accepted — it was "
        "not, so the requirement is NOT what was rejecting it"
    )


# --- probe 2: the validity gate --------------------------------------------------------


def test_removing_the_validity_gate_lets_an_expired_recommendation_through(
    monkeypatch, recommendation
):
    from datetime import timedelta

    expired_at = INSIDE_WINDOW + timedelta(days=1)
    seam = reference_seam(now=INSIDE_WINDOW)  # a seam whose own clock is still inside
    adapter = CloudScalingRiskAdapter(seam=seam, clock=fixed_clock(expired_at))

    assert (
        adapter.evaluate(recommendation.to_canonical_dict()).status
        is AdapterOutcomeStatus.PROJECTION_REJECTED
    )

    monkeypatch.setattr(
        adapter_module, "_require_within_validity", lambda now, projection: None
    )
    outcome = adapter.evaluate(recommendation.to_canonical_dict())
    assert outcome.status is AdapterOutcomeStatus.RISK_DECISION, (
        "with the validity gate removed the expired recommendation should reach the seam "
        "— it did not, so the gate is NOT what was rejecting it"
    )


# --- probe 3: the local binding reconciliation --------------------------------------------


def test_removing_local_reconciliation_lets_a_broken_chain_be_built(
    monkeypatch, recommendation
):
    """Hand the projection record a chain that does not reconcile.

    The mutation targets the reconciliation step itself rather than the digest
    primitive: corrupting ``SubjectContext.digest`` globally would corrupt the
    re-derivation too, leaving everything self-consistent and proving nothing.
    """

    from ugence_cloud_scaling_risk_integration import (
        CapacityRiskSubjectProjection,
        ProjectionError,
        authenticate_controller_output,
        project_recommendation,
    )

    sound = project_recommendation(
        authenticate_controller_output(recommendation.to_canonical_dict())
    )
    corrupt = "sha256:" + "c" * 64
    assert corrupt != sound.context_digest

    def build_broken():
        return CapacityRiskSubjectProjection(
            recommendation_digest=sound.recommendation_digest,
            tenant_id=sound.tenant_id,
            subject_id=sound.subject_id,
            context=sound.context,
            # A context digest that does not match the carried context.
            context_digest=corrupt,
            binding=sound.binding,
            subject_digest=sound.subject_digest,
            request=sound.request,
            request_digest=sound.request_digest,
            idempotency_key=sound.idempotency_key,
            evidence_references=sound.evidence_references,
            valid_from=sound.valid_from,
            valid_until=sound.valid_until,
            asserted_at=sound.asserted_at,
        )

    # Baseline: the reconciliation in __post_init__ refuses it.
    with pytest.raises(ProjectionError, match="context_digest"):
        build_broken()

    # Remove that reconciliation, and the broken chain becomes constructible.
    monkeypatch.setattr(
        projection_module.CapacityRiskSubjectProjection, "__post_init__", lambda self: None
    )
    broken = build_broken()
    assert broken.context_digest == corrupt, (
        "with local reconciliation removed the mismatched digest should survive into the "
        "projection — it did not, so reconciliation is NOT what was catching it"
    )
    # ...and Risk Authority's own Phase 4B validation remains the independent backstop.
    from risk_authority.integrations import validate_subject_binding

    assert validate_subject_binding(broken.request).context_digest != corrupt


# --- probe 4: the no-execution assertion ---------------------------------------------------


def test_removing_the_forged_flag_check_lets_an_executable_decision_through(
    monkeypatch, recommendation
):
    from risk_authority.integrations import SubjectRiskDecision

    from ugence_cloud_scaling_risk_integration import (
        NonExecutableInvariantError,
        outcomes as outcomes_module,
    )

    real = reference_seam().evaluate(
        CloudScalingRiskAdapter(seam=reference_seam(), clock=fixed_clock(INSIDE_WINDOW))
        .project(recommendation.to_canonical_dict())
        .request
    )
    forged = object.__new__(SubjectRiskDecision)
    for field, value in real.__dict__.items():
        object.__setattr__(forged, field, value)
    object.__setattr__(forged, "executable", True)

    class ForgingSeam:
        def evaluate(self, request):
            return forged

    adapter = CloudScalingRiskAdapter(seam=ForgingSeam(), clock=fixed_clock(INSIDE_WINDOW))

    # Baseline: rejected, not normalized.
    with pytest.raises(NonExecutableInvariantError):
        adapter.evaluate(recommendation.to_canonical_dict())

    # Remove the decision-flag re-assertion.
    monkeypatch.setattr(outcomes_module, "_DECISION_FLAGS", ())
    outcome = adapter.evaluate(recommendation.to_canonical_dict())
    assert outcome.decision.executable is True, (
        "with the re-assertion removed the forged flag should survive — it did not, so "
        "the re-assertion is NOT what was catching it"
    )


# --- probe 5: the abstention short-circuit ---------------------------------------------------


def test_removing_the_abstention_short_circuit_would_reach_the_seam(monkeypatch):
    """The abstention branch is what keeps a non-recommendation out of the seam."""

    from conftest import build_abstention

    from ugence_cloud_scaling_risk_integration.authenticity import AuthenticatedAbstention

    seam = RecordingSeam()
    adapter = CloudScalingRiskAdapter(seam=seam, clock=fixed_clock(INSIDE_WINDOW))
    abstention = build_abstention().to_canonical_dict()

    # Baseline: the seam is never reached.
    assert (
        adapter.evaluate(abstention).status
        is AdapterOutcomeStatus.PROJECTION_ABSTAINED_UPSTREAM
    )
    assert not seam.reached

    # Remove the short-circuit by making the isinstance test never match.
    class _NeverMatches:
        def __instancecheck__(self, instance):
            return False

    class _Shadow(metaclass=type("_Meta", (type,), {"__instancecheck__": lambda s, i: False})):
        pass

    monkeypatch.setattr(adapter_module, "AuthenticatedAbstention", _Shadow)
    outcome = adapter.evaluate(abstention)
    # It now falls through to projection, which refuses on its own type boundary —
    # a genuine defence in depth, so the outcome is a rejection rather than a seam call.
    assert outcome.status is AdapterOutcomeStatus.PROJECTION_REJECTED
    assert not seam.reached, (
        "even with the short-circuit removed the seam must not be reached; the "
        "projection type boundary is the second, independent guard"
    )
