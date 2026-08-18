"""Shared fixtures for the Phase 4C adapter suite.

Every recommendation here is a **genuine** ``CapacityActionRecommendation`` produced by
the controller's real Phase-3 pipeline (``recommend_capacity_action``) over real forecast
evidence, a real canonical state, a real cost book and real constraints. Nothing is
stubbed: an adapter validated against a hand-built look-alike would prove nothing about
the contract it actually consumes, and the recommendation's own ``__post_init__`` is a
large part of what makes the authenticity check meaningful.

The seams here are equally deliberate:

* :class:`RecordingSeam` is a **sentinel**, not a mock of Risk Authority. Its entire job
  is to record whether it was reached and what it was handed, so the suite can assert
  that a failed adapter gate means the seam observed nothing at all.
* :class:`ReferenceSeamHarness` composes the **real**
  ``RiskEvaluationSeam.reference(...)`` so the end-to-end path exercises genuine v2
  admission, genuine binding revalidation and a genuine ``SubjectRiskDecision``.

No fixture here constructs a *production* seam: doing so would require minting a real
authority grant and signing key inside a test, and the adapter's contract is that the
composition root supplies an already-constructed production seam.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import pytest

import ph_helpers as H  # controller Phase-3 test builders (see the package conftest)
from ugence_cloud_scaling_controller.planning import recommend_capacity_action
from ugence_cloud_scaling_controller.planning.candidates import ActionKind
from ugence_cloud_scaling_controller.planning.recommendation import (
    CapacityActionRecommendation,
    RecommendationAbstention,
)

from ugence_cloud_scaling_risk_integration import CloudScalingRiskAdapter

# The controller fixtures are anchored at 2026-01-01T00:00:00Z; the recommendation is
# stamped at +190s with a 300s validity window, so "inside the window" is [190s, 490s].
REC_TIME = H.at(190.0)
VALIDITY_SECONDS = 300.0
INSIDE_WINDOW = H.at(300.0)


def build_recommendation(
    *,
    predicted: int = 9,
    current: int = 6,
    subject=None,
    topology=None,
    cost_book=None,
    constraints=None,
    policy=None,
    recommendation_time: datetime = REC_TIME,
    validity_seconds: float = VALIDITY_SECONDS,
    recommendation_id: str = "rec-phase4c-1",
) -> CapacityActionRecommendation:
    """Produce a genuine recommendation through the real Phase-3 pipeline."""

    subject = subject if subject is not None else H.subject()
    forecast = H.build_forecast_evidence(predicted, subj=subject)
    state = H.replicas_state(H.at(180.0), current, subj=subject)
    outcome = recommend_capacity_action(
        forecast,
        state,
        cost_book if cost_book is not None else H.cost_book(subj=subject),
        constraints if constraints is not None else H.constraints(),
        policy if policy is not None else H.policy(),
        recommendation_time=recommendation_time,
        validity_seconds=validity_seconds,
        topology=topology,
        recommendation_id=recommendation_id,
    )
    if not isinstance(outcome, CapacityActionRecommendation):
        raise AssertionError(
            f"fixture produced an abstention rather than a recommendation: {outcome!r}"
        )
    return outcome


def build_coordinated_recommendation() -> CapacityActionRecommendation:
    """A genuine COORDINATED recommendation (primary scale-up + dependency change)."""

    subject = H.subject()
    dependency = H.subject(workload_id="db")
    return build_recommendation(
        predicted=9,
        current=6,
        subject=subject,
        topology=H.topology(subj=subject, dependency=dependency),
        cost_book=H.cost_book(subj=subject, dependency=dependency),
        recommendation_id="rec-coordinated",
    )


def build_abstention() -> RecommendationAbstention:
    """A genuine typed controller abstention (the forecast itself abstained)."""

    subject = H.subject()
    outcome = recommend_capacity_action(
        H.build_abstained_forecast(subj=subject),
        H.replicas_state(H.at(180.0), 6, subj=subject),
        H.cost_book(subj=subject),
        H.constraints(),
        H.policy(),
        recommendation_time=REC_TIME,
        validity_seconds=VALIDITY_SECONDS,
    )
    if not isinstance(outcome, RecommendationAbstention):
        raise AssertionError(f"fixture produced {type(outcome).__name__}, not an abstention")
    return outcome


def recommendation_for(kind: ActionKind) -> CapacityActionRecommendation:
    """A genuine recommendation whose selected plan has the requested ``ActionKind``."""

    if kind is ActionKind.NO_CHANGE:
        rec = build_recommendation(predicted=6, current=6, recommendation_id="rec-no-change")
    elif kind is ActionKind.SCALE_UP:
        rec = build_recommendation(predicted=9, current=6, recommendation_id="rec-scale-up")
    elif kind is ActionKind.SCALE_DOWN:
        # A safe scale-down only wins under a cost-eager policy; the controller's default
        # hold-bias otherwise (correctly) prefers NO_CHANGE.
        rec = build_recommendation(
            predicted=3,
            current=6,
            policy=H.policy(
                w_change_magnitude=0.0, w_uncertainty=0.0, w_hold_bias=0.0, w_cost=2.0
            ),
            recommendation_id="rec-scale-down",
        )
    elif kind is ActionKind.COORDINATED:
        rec = build_coordinated_recommendation()
    else:  # pragma: no cover - the ratified set is closed
        raise AssertionError(f"unhandled ActionKind: {kind!r}")
    if rec.selected_plan.action_kind is not kind:
        raise AssertionError(
            f"fixture for {kind.value} selected {rec.selected_plan.action_kind.value}"
        )
    return rec


def fixed_clock(now: datetime = INSIDE_WINDOW):
    """An injected trusted clock returning a fixed, timezone-aware instant."""

    def _clock() -> datetime:
        return now

    return _clock


@dataclass
class RecordingSeam:
    """A sentinel seam: records what it was handed, or proves it was never reached.

    It is not a Risk Authority substitute — it deliberately performs no evaluation. Its
    purpose is the negative assertion: after a failed adapter gate, ``calls`` must be
    empty, meaning no resolver, no evidence source and no authority ever observed the
    request.
    """

    decision: Optional[Any] = None
    calls: list = field(default_factory=list)

    def evaluate(self, request):
        self.calls.append(request)
        if self.decision is None:
            raise AssertionError(
                "RecordingSeam was reached but no decision was configured — the test "
                "expected this seam never to be called"
            )
        return self.decision

    @property
    def reached(self) -> bool:
        return bool(self.calls)


class ForbiddenSeam:
    """A seam that fails the test if it is reached at all."""

    def evaluate(self, request):  # pragma: no cover - reaching this IS the failure
        raise AssertionError(
            "the evaluation seam was reached even though an adapter gate should have "
            "failed closed before it"
        )


@pytest.fixture
def forbidden_seam() -> ForbiddenSeam:
    return ForbiddenSeam()


@pytest.fixture
def recording_seam() -> RecordingSeam:
    return RecordingSeam()


@pytest.fixture
def recommendation() -> CapacityActionRecommendation:
    return build_recommendation()


@pytest.fixture
def serialized(recommendation) -> dict:
    """The canonical serialized form, carrying its independent ``evidence_digest``."""

    return recommendation.to_canonical_dict()


@pytest.fixture
def adapter(forbidden_seam) -> CloudScalingRiskAdapter:
    """An adapter whose seam must never be reached (the fail-closed default)."""

    return CloudScalingRiskAdapter(seam=forbidden_seam, clock=fixed_clock())


def reference_seam(now: datetime = INSIDE_WINDOW):
    """The REAL ``RiskEvaluationSeam.reference(...)``, subject-context aware.

    Used only where the suite needs a genuine end-to-end path through v2 admission,
    binding revalidation and decision construction. It is visibly labelled reference —
    the production factory can never yield it — and the adapter treats it identically to
    any other injected seam, which is exactly the point: the adapter adds no grade of its
    own.
    """

    from risk_authority.api.evaluation_seam import RiskEvaluationSeam
    from risk_authority.crypto import SigningKey, SigningKeyRecord
    from risk_authority.domain import (
        Predicate,
        PredicateOp,
        RuleEffect,
        WorkflowIR,
        WorkflowRule,
        WorkflowStatus,
    )
    from risk_authority.integrations import (
        InMemoryWorkflowIRSource,
        ReferenceSubjectAwarePolicyResolver,
    )

    from ugence_cloud_scaling_risk_integration import (
        DOMAIN_CLOUD_SCALING,
        PURPOSE_CAPACITY_ACTION,
    )

    workflow = WorkflowIR(
        workflow_ir_id="cloud-scaling-risk",
        version="1.0.0",
        status=WorkflowStatus.ACTIVE,
        rules=(
            WorkflowRule(
                rule_id="CS-1",
                conditions=(Predicate("domain", PredicateOp.EQ, DOMAIN_CLOUD_SCALING),),
                required_controls=(),
                effect=RuleEffect.ALLOW_IF_ALL,
            ),
        ),
        source_refs=("ADR-CLOUD-SCALING-P4",),
        effective_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    ).with_digest()
    source = InMemoryWorkflowIRSource()
    source.register(workflow)
    return RiskEvaluationSeam.reference(
        workflow_source=source,
        key_record=SigningKeyRecord("cs-key", SigningKey.from_seed(bytes(range(32)))),
        clock=lambda: now,
        policy_resolver=ReferenceSubjectAwarePolicyResolver(
            by_purpose_domain={(PURPOSE_CAPACITY_ACTION, DOMAIN_CLOUD_SCALING): workflow}
        ),
    )
