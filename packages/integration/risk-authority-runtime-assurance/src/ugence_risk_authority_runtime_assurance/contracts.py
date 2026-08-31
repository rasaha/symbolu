"""RA-7 neutral runtime-assurance contracts (spec §11–§13, §20, §23).

These are the minimum ratified neutral types. Every one is **evidence /
observation**, not authority: none carries an ``ALLOW``, a scope grant, a
signature, or any machine-authority token. The absence is structural (there is
simply no such field), not merely validated — a packaging property test asserts
it (invariant I9).

    TrajectoryObservation   one admitted runtime-behavior fact, fully bound to a
                            (tenant, workflow-instance, envelope) authority domain
    RuntimeRiskLevel        NORMAL / ESCALATED / UNKNOWN  (spec §13)
    ReasonCode              structured cause for a signal (spec §9)
    AssessmentOutcome       the fail-safe outcome vocabulary (spec §20)
    TrajectoryAssessment    the neutral verdict the evaluator produces (spec §12)
    TrajectoryPolicyRef     an authority-bound *reference* to a policy (spec §5)

Nothing here imports Risk Authority, the Agent Runtime, persistence, or any
third-party package: these are stdlib-only value objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping, Optional

__all__ = [
    "RUNTIME_ASSURANCE_SCHEMA_VERSION",
    "SUPPORTED_OBSERVATION_SCHEMA_VERSIONS",
    "RuntimeRiskLevel",
    "ReasonCode",
    "AssessmentOutcome",
    "TrajectoryPolicyRef",
    "TrajectoryObservation",
    "TrajectoryAssessment",
]

#: Current observation wire-schema version. An observation declaring an
#: unsupported version is rejected fail-closed at ingress (never assessed).
RUNTIME_ASSURANCE_SCHEMA_VERSION = "1"
SUPPORTED_OBSERVATION_SCHEMA_VERSIONS = frozenset({RUNTIME_ASSURANCE_SCHEMA_VERSION})


class RuntimeRiskLevel(str, Enum):
    """The three-value runtime risk level (spec §13).

    Intentionally minimal: severity tiers (``ELEVATED``/``CRITICAL``) are rejected
    because RA-6's consequence for any material escalation is identical, so tiers
    would duplicate Risk Authority's own classification without changing behavior.
    A risk level is an **observation, not authority** (invariant I9).
    """

    NORMAL = "NORMAL"
    ESCALATED = "ESCALATED"
    UNKNOWN = "UNKNOWN"


class ReasonCode(str, Enum):
    """Structured cause codes carried on an assessment / signal (spec §9/D6).

    A single signal category (``RUNTIME_RISK_ESCALATED``) plus these structured
    reasons preserves audit granularity without a taxonomy-for-its-own-sake
    proliferation of top-level categories. RA-8's effect-mismatch reason is
    deliberately absent (invariant I13, N7).
    """

    CUMULATIVE_EXPOSURE = "CUMULATIVE_EXPOSURE"
    NEAR_BOUNDARY_REPEAT = "NEAR_BOUNDARY_REPEAT"
    RETRY_LOOP = "RETRY_LOOP"
    DATA_CLASS_PROGRESSION = "DATA_CLASS_PROGRESSION"
    CONTEXT_EXPANSION = "CONTEXT_EXPANSION"
    TRAJECTORY_POLICY_DEVIATION = "TRAJECTORY_POLICY_DEVIATION"
    MODEL_BEHAVIOR_CHANGED = "MODEL_BEHAVIOR_CHANGED"


class AssessmentOutcome(str, Enum):
    """The fail-safe outcome vocabulary (spec §20).

    No outcome ever widens authority. ``SIGNAL_REASSESS`` is the only outcome that
    causes a consequence, and it does so exclusively by handing a neutral signal to
    the RA-6 intake — never by mutating authority directly.
    """

    IGNORE_EVENT = "IGNORE_EVENT"
    UNKNOWN_ASSESSMENT = "UNKNOWN_ASSESSMENT"
    NO_SIGNAL = "NO_SIGNAL"
    SIGNAL_REASSESS = "SIGNAL_REASSESS"
    ERROR_NON_EXECUTABLE = "ERROR_NON_EXECUTABLE"
    CONTINUE_UNDER_RA6 = "CONTINUE_UNDER_RA6"
    DENY_IF_ASSURANCE_REQUIRED = "DENY_IF_ASSURANCE_REQUIRED"


@dataclass(frozen=True)
class TrajectoryPolicyRef:
    """An authority-bound *reference* to a trajectory policy (spec §5/D2).

    This is a reference, **not** the policy content. ``policy_id`` is the signed
    ``EnvelopeConditions.trajectory_policy_id``; ``version`` is the threaded
    ``trajectory_version``. ``digest`` pins content integrity when the deferred,
    additive ``trajectory_policy_digest`` binding lands (D2) — until then it is
    ``None`` and content-integrity cannot be asserted (⇒ ``UNKNOWN`` where it
    matters). WorkflowIR owns the content; Risk Authority binds the reference; RA-7
    only *reads* it.
    """

    policy_id: str
    version: Optional[str] = None
    digest: Optional[str] = None

    def is_empty(self) -> bool:
        return not self.policy_id


def _freeze_detail(detail: Optional[Mapping[str, Any]]) -> Mapping[str, Any]:
    """Return an immutable shallow copy of a neutral detail mapping.

    Detail carries only neutral, risk-relevant coordination facts (cumulative
    exposure totals, retry counts, a data-access class, context size, a tool /
    destination label). It never carries credentials, raw prompts, secret tool
    arguments, or provider responses (mirroring the Agent Runtime event contract).
    """

    if not detail:
        return {}
    return dict(detail)


@dataclass(frozen=True)
class TrajectoryObservation:
    """One admitted runtime-behavior fact, bound to an authority domain (spec §10–§12).

    Every binding field has a stated trust/audit purpose (spec §12 table). An
    observation is transient evidence; it carries no authority. ``detail`` holds
    the neutral risk-relevant facts the evaluator risk-types (never authoritative
    accounting — RA-7 reads the numbers, Agent Runtime owns them, D3/§6).
    """

    schema_version: str
    event_id: str
    tenant_id: str
    workflow_instance_id: str
    envelope_id: str
    runtime_event_type: str
    observed_at: datetime
    source: str
    source_version: str
    action_id: str = ""
    sequence_number: Optional[int] = None
    policy_ref: Optional[TrajectoryPolicyRef] = None
    payload_digest: Optional[str] = None
    detail: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "detail", _freeze_detail(self.detail))

    def binding_errors(self) -> tuple[str, ...]:
        """Return fail-closed reasons this observation cannot be trusted/bound.

        Empty tuple == structurally acceptable for ingress (trust + dedupe +
        ordering still decide the disposition). A non-empty result means the
        observation MUST be ignored (``IGNORE_EVENT``) and can never influence an
        assessment (invariants I6/I7). Wrong-tenant / wrong-workflow / wrong-envelope
        mismatches are checked by the ingress against the expected binding; this
        method only validates the observation is internally well-formed.
        """

        reasons: list[str] = []
        if self.schema_version not in SUPPORTED_OBSERVATION_SCHEMA_VERSIONS:
            reasons.append(
                f"unsupported observation schema_version {self.schema_version!r}"
            )
        if not self.event_id:
            reasons.append("missing event_id")
        if not self.tenant_id:
            reasons.append("missing tenant_id")
        if not self.workflow_instance_id:
            reasons.append("missing workflow_instance_id")
        if not self.envelope_id:
            reasons.append("missing envelope_id")
        if not self.runtime_event_type:
            reasons.append("missing runtime_event_type")
        if not isinstance(self.observed_at, datetime):
            reasons.append("missing/invalid observed_at")
        if not self.source:
            reasons.append("missing source")
        if not self.source_version:
            reasons.append("missing source_version")
        if self.sequence_number is not None and (
            isinstance(self.sequence_number, bool)
            or not isinstance(self.sequence_number, int)
        ):
            reasons.append("sequence_number must be an int when set")
        return tuple(reasons)

    @property
    def trajectory_key(self) -> tuple[str, str]:
        """The canonical trajectory key ``(tenant_id, workflow_instance_id)`` (spec §11)."""

        return (self.tenant_id, self.workflow_instance_id)


@dataclass(frozen=True)
class TrajectoryAssessment:
    """The neutral verdict RA-7 produces (spec §12).

    **Evidence / verdict, NOT machine authority.** It uses the neutral vocabulary
    ``NORMAL`` / ``ESCALATED`` / ``UNKNOWN`` (never ALLOW/DENY). Only a *material*
    (``ESCALATED``) assessment causes a downstream consequence, and only via the
    neutral RA-6 signal — the assessment itself can never be used as standalone
    execution authority (invariant I9).
    """

    assessment_id: str
    tenant_id: str
    workflow_instance_id: str
    envelope_id: str
    risk_level: RuntimeRiskLevel
    outcome: AssessmentOutcome
    produced_at: datetime
    evaluator_identity: str
    evaluator_version: str
    policy_ref: Optional[TrajectoryPolicyRef] = None
    reason_codes: tuple[ReasonCode, ...] = ()
    reasons: tuple[str, ...] = ()
    supporting_event_refs: tuple[str, ...] = ()
    observed_window: tuple[str, ...] = ()

    @property
    def is_material(self) -> bool:
        """A material assessment is exactly an ``ESCALATED`` one (spec §12/§18).

        ``NORMAL`` and ``UNKNOWN`` never emit a signal — an ``UNKNOWN`` verdict is a
        blind window, never a fabricated escalation, and never widens authority.
        """

        return self.risk_level is RuntimeRiskLevel.ESCALATED
