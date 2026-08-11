"""``CapacityDecisionEvidence`` — immutable, versioned, provider-neutral recommendation
evidence that accompanies a ``ScalingRecommendation``.

This is **not** a second decision engine. It records what the controller saw, what it
used, how values were normalized, and which recommendation the controller produced —
distinguishing, at every step:

    observed  !=  normalized  !=  decision-used  !=  recommendation

Evidence is produced only through the controlled service path
(:func:`recommend_with_evidence` / :func:`build_capacity_decision_evidence`): the service
runs the *real* projection and the *real* controller, so a caller cannot forge evidence
by supplying a different recommendation. The evidence carries a deterministic
``sha256:`` content digest (:meth:`CapacityDecisionEvidence.digest`) suitable for a
future, separately governed Risk Authority integration package to reference as a stable
identity. That digest is an *identity*, never a signature, authorization, risk verdict,
control-satisfaction claim, or execution permission.

Determinism of the digest: it covers all decision-relevant fields but EXCLUDES
``evidence_produced_at`` (a production timestamp isolated from the deterministic decision
path), ``controller_explanation`` (a human-readable rendering that embeds the controller's
*disclosed* nondeterministic ``identity_deviation`` "Identity Drift" line), and the digest
field itself. The controller's ``identity_deviation`` diagnostic is never carried here at
all. The structured decision fields that ARE digested (recommendation, replica_delta,
recommended_replicas, action_score, pressure, component_breakdown, projected/normalized
signals, determinism disclosure) fully determine the decision. For identical
``(CanonicalCapacityState, NormalizationPolicy, ControllerConfig, controller history)``
the digest is reproducible.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from ..config import InfraControllerConfig
from ..contracts import ScalingRecommendation
from ..version import __version__ as CONTROLLER_PACKAGE_VERSION
from .identity import CapacitySubject
from .normalization import NormalizationPolicy, NormalizedSignal
from .projection import ControllerProjection, project_to_scaling_observation
from .provenance import ObservationProvenance
from .serialization import content_digest
from .state import CanonicalCapacityState

EVIDENCE_SCHEMA_VERSION = "capacity-evidence-1"
# Documented controller input schema (see module_manifest.json input_schema_version).
CONTROLLER_OBSERVATION_SCHEMA_VERSION = "1.0"

AUTHORITY_CLASS_ADVISORY = "ADVISORY"
EXECUTION_CAPABILITY_NONE = "NONE"

# Fields deliberately excluded from the identity digest (documented above):
#   evidence_digest        — the digest cannot cover itself
#   evidence_produced_at   — production timestamp isolated from the decision path
#   controller_explanation — human rendering embedding the disclosed nondeterministic
#                            identity_deviation ("Identity Drift") diagnostic line
DIGEST_EXCLUDED_FIELDS = ("evidence_digest", "evidence_produced_at", "controller_explanation")


class EvidenceError(ValueError):
    """Raised when evidence would be internally inconsistent (fail closed)."""


def _config_digest(config: InfraControllerConfig) -> str:
    return content_digest("controller_config", "infra-controller-config-1", asdict(config))


@dataclass(frozen=True)
class CapacityDecisionEvidence:
    """Immutable evidence artifact for one advisory scaling recommendation."""

    evidence_schema_version: str
    canonical_state_schema_version: str
    controller_observation_schema_version: str
    controller_recommendation_schema_version: str
    controller_package_version: str
    controller_config_digest: str
    normalization_policy_id: str
    normalization_policy_digest: str
    canonical_state_digest: str

    subject: CapacitySubject
    correlation_id: Optional[str]
    observed_at: datetime
    evidence_produced_at: datetime

    # Projection disclosure (observed -> normalized -> decision-used).
    projected_signals: Dict[str, float]
    normalized_signals: Tuple[NormalizedSignal, ...]
    signals_delivered_to_controller: Dict[str, float]
    ignored_canonical_fields: Tuple[str, ...]
    used_canonical_fields: Tuple[str, ...]
    missing_controller_signals: Tuple[str, ...]
    projection_warnings: Tuple[str, ...]

    # Recommendation (the real controller output; identity_deviation intentionally omitted).
    recommendation: str
    current_replicas: int
    recommended_replicas: int
    replica_delta: int
    action_score: float
    pressure: float
    component_breakdown: Dict[str, Any]
    controller_explanation: str
    controller_step: int
    determinism: Dict[str, Any]

    provenance: Optional[ObservationProvenance]

    # Authority classification — fixed, advisory-only.
    authority_class: str = AUTHORITY_CLASS_ADVISORY
    execution_capability: str = EXECUTION_CAPABILITY_NONE
    advisory_only: bool = True
    actuation_performed: bool = False

    def __post_init__(self) -> None:
        if self.advisory_only is not True:
            raise EvidenceError("advisory_only must be True")
        if self.actuation_performed is not False:
            raise EvidenceError("actuation_performed must be False")
        if self.authority_class != AUTHORITY_CLASS_ADVISORY:
            raise EvidenceError("authority_class must be ADVISORY")
        if self.execution_capability != EXECUTION_CAPABILITY_NONE:
            raise EvidenceError("execution_capability must be NONE")

    def to_canonical_dict(self, *, include_digest: bool = True) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "evidence_schema_version": self.evidence_schema_version,
            "canonical_state_schema_version": self.canonical_state_schema_version,
            "controller_observation_schema_version": self.controller_observation_schema_version,
            "controller_recommendation_schema_version": self.controller_recommendation_schema_version,
            "controller_package_version": self.controller_package_version,
            "controller_config_digest": self.controller_config_digest,
            "normalization_policy_id": self.normalization_policy_id,
            "normalization_policy_digest": self.normalization_policy_digest,
            "canonical_state_digest": self.canonical_state_digest,
            "subject": self.subject.to_canonical_dict(),
            "correlation_id": self.correlation_id,
            "observed_at": self.observed_at,
            "evidence_produced_at": self.evidence_produced_at,
            "projected_signals": dict(self.projected_signals),
            "normalized_signals": [s.to_canonical_dict() for s in self.normalized_signals],
            "signals_delivered_to_controller": dict(self.signals_delivered_to_controller),
            "ignored_canonical_fields": list(self.ignored_canonical_fields),
            "used_canonical_fields": list(self.used_canonical_fields),
            "missing_controller_signals": list(self.missing_controller_signals),
            "projection_warnings": list(self.projection_warnings),
            "recommendation": self.recommendation,
            "current_replicas": self.current_replicas,
            "recommended_replicas": self.recommended_replicas,
            "replica_delta": self.replica_delta,
            "action_score": self.action_score,
            "pressure": self.pressure,
            "component_breakdown": self.component_breakdown,
            "controller_explanation": self.controller_explanation,
            "controller_step": self.controller_step,
            "determinism": self.determinism,
            "provenance": self.provenance.to_canonical_dict() if self.provenance else None,
            "authority_class": self.authority_class,
            "execution_capability": self.execution_capability,
            "advisory_only": self.advisory_only,
            "actuation_performed": self.actuation_performed,
        }
        if include_digest:
            data["evidence_digest"] = self.digest()
        return data

    def _digest_payload(self) -> Dict[str, Any]:
        data = self.to_canonical_dict(include_digest=False)
        for excluded in DIGEST_EXCLUDED_FIELDS:
            data.pop(excluded, None)
        return data

    def digest(self) -> str:
        """Deterministic ``sha256:`` identity over decision-relevant fields."""
        return content_digest(
            "capacity_decision_evidence", self.evidence_schema_version, self._digest_payload()
        )

    def to_json(self, *, indent: Optional[int] = None) -> str:
        from .serialization import canonical_json
        import json

        payload = self.to_canonical_dict(include_digest=True)
        # canonical_json normalizes/validates; re-emit with optional indent.
        return json.dumps(json.loads(canonical_json(payload)), sort_keys=True, indent=indent)


def build_capacity_decision_evidence(
    state: CanonicalCapacityState,
    normalization_policy: NormalizationPolicy,
    projection: ControllerProjection,
    recommendation: ScalingRecommendation,
    config: InfraControllerConfig,
    *,
    evidence_produced_at: datetime,
) -> CapacityDecisionEvidence:
    """Assemble evidence from an already-computed real projection + real recommendation.

    This binds evidence to the actual controller output — the ``recommendation`` here is
    the object the controller returned, not a caller-supplied claim.
    """
    if not isinstance(recommendation, ScalingRecommendation):
        raise EvidenceError("recommendation must be a real ScalingRecommendation")
    if recommendation.advisory_only is not True or recommendation.actuation_performed is not False:
        raise EvidenceError("recommendation must be advisory-only with no actuation")
    if not isinstance(evidence_produced_at, datetime):
        raise EvidenceError("evidence_produced_at must be a datetime")

    return CapacityDecisionEvidence(
        evidence_schema_version=EVIDENCE_SCHEMA_VERSION,
        canonical_state_schema_version=state.schema_version,
        controller_observation_schema_version=CONTROLLER_OBSERVATION_SCHEMA_VERSION,
        controller_recommendation_schema_version=recommendation.schema_version,
        controller_package_version=CONTROLLER_PACKAGE_VERSION,
        controller_config_digest=_config_digest(config),
        normalization_policy_id=normalization_policy.policy_id,
        normalization_policy_digest=normalization_policy.digest(),
        canonical_state_digest=state.digest(),
        subject=state.subject,
        correlation_id=recommendation.correlation_id,
        observed_at=state.observed_at,
        evidence_produced_at=evidence_produced_at,
        projected_signals=dict(projection.projected_signals),
        normalized_signals=projection.normalized_signals,
        signals_delivered_to_controller=dict(recommendation.metrics_snapshot),
        ignored_canonical_fields=projection.ignored_canonical_fields,
        used_canonical_fields=projection.used_canonical_fields,
        missing_controller_signals=projection.missing_controller_signals,
        projection_warnings=projection.warnings,
        recommendation=recommendation.recommendation,
        current_replicas=recommendation.current_replicas,
        recommended_replicas=recommendation.recommended_replicas,
        replica_delta=recommendation.replica_delta,
        action_score=recommendation.action_score,
        pressure=recommendation.pressure,
        component_breakdown=recommendation.component_breakdown,
        controller_explanation=recommendation.explanation,
        controller_step=recommendation.controller_step,
        determinism=recommendation.determinism,
        provenance=state.provenance,
    )


def recommend_with_evidence(
    state: CanonicalCapacityState,
    normalization_policy: NormalizationPolicy,
    controller: Any = None,
    *,
    evidence_produced_at: Optional[datetime] = None,
):
    """Controlled service path: project → recommend → build evidence.

    Runs the *unmodified* ``CloudScalingController`` on the projected observation and
    returns ``(ScalingRecommendation, CapacityDecisionEvidence)``. Evidence is bound to
    the real recommendation, preventing forgery.

    ``evidence_produced_at`` must be a caller-supplied trusted timestamp (never generated
    inside this deterministic path); it defaults to ``state.observed_at`` so the call
    stays clock-free and deterministic. It is excluded from the evidence identity digest.
    """
    from ..api import CloudScalingController

    if controller is None:
        controller = CloudScalingController()
    projection = project_to_scaling_observation(state, normalization_policy)
    recommendation = controller.recommend(projection.observation)
    produced_at = evidence_produced_at if evidence_produced_at is not None else state.observed_at
    evidence = build_capacity_decision_evidence(
        state,
        normalization_policy,
        projection,
        recommendation,
        controller.config,
        evidence_produced_at=produced_at,
    )
    return recommendation, evidence


__all__ = [
    "EVIDENCE_SCHEMA_VERSION",
    "CONTROLLER_OBSERVATION_SCHEMA_VERSION",
    "AUTHORITY_CLASS_ADVISORY",
    "EXECUTION_CAPABILITY_NONE",
    "DIGEST_EXCLUDED_FIELDS",
    "EvidenceError",
    "CapacityDecisionEvidence",
    "build_capacity_decision_evidence",
    "recommend_with_evidence",
]
