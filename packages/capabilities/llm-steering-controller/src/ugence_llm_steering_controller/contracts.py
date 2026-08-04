"""Stable, typed public contracts for the advisory LLM Steering Controller.

These are the ONLY data shapes callers should depend on. Everything is a plain
``dataclass`` or ``str``-valued ``Enum`` built from the Python standard library, with
explicit ``to_dict`` / ``from_dict`` for deterministic JSON serialization (sorted keys,
no timestamps, no randomness).

Authority boundary (see ``docs/AUTHORITY_BOUNDARY.md``): every value produced here is a
*recommendation*. A :class:`RoutingRecommendation` carries ``execution_status =
NOT_EXECUTED`` and ``recommendation_only = True``. Nothing in this module can call a
provider, load a credential, open a socket, or execute a model request.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# --------------------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------------------
class SteeringError(Exception):
    """Base class for every error raised by the steering controller."""


class ContractError(SteeringError, ValueError):
    """A contract object was constructed from malformed / invalid input."""


class RegistryError(SteeringError, ValueError):
    """The candidate registry is invalid (bad metadata, duplicate ids, secrets)."""


class PolicyViolation(SteeringError, ValueError):
    """A routing policy is internally inconsistent (e.g. invalid weights, contradiction)."""


class NoEligibleCandidate(SteeringError):
    """No candidate survived hard-constraint filtering.

    Raised only by the strict API; the default :class:`SteeringResult` flow returns a
    typed *outcome* (``status = NO_ELIGIBLE_CANDIDATE``) rather than raising, so callers
    always receive an inspectable decision trace instead of an arbitrary fallback.
    """


# --------------------------------------------------------------------------------------
# Enums
# --------------------------------------------------------------------------------------
class QualityPreference(str, Enum):
    """Soft optimization posture. Selects a documented weight preset; it can never
    override a hard constraint (see ``ROUTING_POLICY_MODEL.md``)."""

    QUALITY_FIRST = "quality_first"
    BALANCED = "balanced"
    COST_FIRST = "cost_first"
    LATENCY_FIRST = "latency_first"


class PrivacyClass(str, Enum):
    """Data-sensitivity classification of the request payload. ``CONFIDENTIAL`` and
    ``RESTRICTED`` are fail-closed: a candidate with unknown / insufficient privacy
    metadata is disqualified rather than admitted."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class ExecutionStatus(str, Enum):
    """Execution disposition. This package only ever emits ``NOT_EXECUTED``."""

    NOT_EXECUTED = "NOT_EXECUTED"


class SteeringStatus(str, Enum):
    """Outcome of a steering evaluation."""

    RECOMMENDED = "RECOMMENDED"
    NO_ELIGIBLE_CANDIDATE = "NO_ELIGIBLE_CANDIDATE"


class Disposition(str, Enum):
    """Per-candidate disposition after hard-constraint filtering."""

    ELIGIBLE = "eligible"
    REJECTED = "rejected"


class DeprecationState(str, Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


# Ordered, documented cost / latency / quality / reliability / availability tiers.
# These are *configured priors*, never measured production values (see
# ``SCORING_AND_EXPLANATION.md``). Callers may instead supply exact numeric estimates.
COST_CLASS_ORDER = ("very_low", "low", "medium", "high", "very_high")
LATENCY_CLASS_ORDER = ("very_fast", "fast", "medium", "slow", "very_slow")
QUALITY_TIER_ORDER = ("economy", "standard", "advanced", "premium", "frontier")
RELIABILITY_CLASS_ORDER = ("low", "medium", "high", "very_high")
AVAILABILITY_CLASS_ORDER = ("limited", "regional", "broad", "global")


def _require(condition: bool, message: str, exc=ContractError) -> None:
    if not condition:
        raise exc(message)


def _as_str_set(value: Any, name: str) -> Tuple[str, ...]:
    if value is None:
        return ()
    _require(isinstance(value, (list, tuple, set)), f"{name} must be a list/set of strings")
    out = tuple(sorted({str(v) for v in value}))
    return out


# --------------------------------------------------------------------------------------
# Registry candidate metadata (metadata ONLY — never credentials or live clients)
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ProviderCandidate:
    """Immutable metadata describing a routable provider. Contains NO credentials,
    tokens, secrets, or live SDK clients — only descriptive facts used for filtering
    and scoring."""

    provider_id: str
    display_name: str = ""
    regions: Tuple[str, ...] = ()
    deployment_mode: str = "cloud"  # "cloud" | "on_prem" | "vpc" | "hybrid"
    trains_on_data: bool = False
    policy_tags: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require(isinstance(self.provider_id, str) and self.provider_id, "provider_id required")
        object.__setattr__(self, "regions", _as_str_set(self.regions, "regions"))
        object.__setattr__(self, "policy_tags", _as_str_set(self.policy_tags, "policy_tags"))

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ProviderCandidate":
        _require(isinstance(d, dict), "provider candidate must be an object")
        return cls(
            provider_id=str(d["provider_id"]),
            display_name=str(d.get("display_name", "")),
            regions=_as_str_set(d.get("regions"), "regions"),
            deployment_mode=str(d.get("deployment_mode", "cloud")),
            trains_on_data=bool(d.get("trains_on_data", False)),
            policy_tags=_as_str_set(d.get("policy_tags"), "policy_tags"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "display_name": self.display_name,
            "regions": list(self.regions),
            "deployment_mode": self.deployment_mode,
            "trains_on_data": self.trains_on_data,
            "policy_tags": list(self.policy_tags),
        }


@dataclass(frozen=True)
class ModelCandidate:
    """Immutable metadata describing a routable model. Contains NO credentials.

    Unknown capability metadata is never treated as supported: booleans default to
    ``False`` and unset regions/modalities/capabilities are empty, so a missing fact
    fails closed during constraint evaluation.
    """

    model_id: str
    provider_id: str
    modalities_in: Tuple[str, ...] = ()
    modalities_out: Tuple[str, ...] = ()
    context_limit: int = 0
    structured_output: bool = False
    tool_use: bool = False
    regions: Tuple[str, ...] = ()
    privacy_tier: str = "standard"  # "standard" | "high"
    cost_class: str = "medium"
    latency_class: str = "medium"
    quality_tier: str = "standard"
    reliability_class: str = "medium"
    availability_class: str = "broad"
    deprecation_state: str = DeprecationState.ACTIVE.value
    capabilities: Tuple[str, ...] = ()
    policy_tags: Tuple[str, ...] = ()
    # Optional exact numeric estimates; when present they override the class prior.
    est_cost_per_ktok: Optional[float] = None
    est_latency_ms: Optional[float] = None

    def __post_init__(self) -> None:
        _require(isinstance(self.model_id, str) and self.model_id, "model_id required")
        _require(isinstance(self.provider_id, str) and self.provider_id, "provider_id required")
        _require(isinstance(self.context_limit, int) and self.context_limit >= 0,
                 "context_limit must be a non-negative int")
        _require(self.privacy_tier in ("standard", "high"), "privacy_tier must be 'standard'|'high'")
        _require(self.cost_class in COST_CLASS_ORDER, f"cost_class must be one of {COST_CLASS_ORDER}")
        _require(self.latency_class in LATENCY_CLASS_ORDER,
                 f"latency_class must be one of {LATENCY_CLASS_ORDER}")
        _require(self.quality_tier in QUALITY_TIER_ORDER,
                 f"quality_tier must be one of {QUALITY_TIER_ORDER}")
        _require(self.reliability_class in RELIABILITY_CLASS_ORDER,
                 f"reliability_class must be one of {RELIABILITY_CLASS_ORDER}")
        _require(self.availability_class in AVAILABILITY_CLASS_ORDER,
                 f"availability_class must be one of {AVAILABILITY_CLASS_ORDER}")
        _require(self.deprecation_state in tuple(s.value for s in DeprecationState),
                 "deprecation_state invalid")
        for f_name in ("modalities_in", "modalities_out", "regions", "capabilities", "policy_tags"):
            object.__setattr__(self, f_name, _as_str_set(getattr(self, f_name), f_name))
        if self.est_cost_per_ktok is not None:
            _require(float(self.est_cost_per_ktok) >= 0, "est_cost_per_ktok must be >= 0")
        if self.est_latency_ms is not None:
            _require(float(self.est_latency_ms) >= 0, "est_latency_ms must be >= 0")

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ModelCandidate":
        _require(isinstance(d, dict), "model candidate must be an object")
        ecpt = d.get("est_cost_per_ktok")
        elm = d.get("est_latency_ms")
        return cls(
            model_id=str(d["model_id"]),
            provider_id=str(d["provider_id"]),
            modalities_in=_as_str_set(d.get("modalities_in"), "modalities_in"),
            modalities_out=_as_str_set(d.get("modalities_out"), "modalities_out"),
            context_limit=int(d.get("context_limit", 0)),
            structured_output=bool(d.get("structured_output", False)),
            tool_use=bool(d.get("tool_use", False)),
            regions=_as_str_set(d.get("regions"), "regions"),
            privacy_tier=str(d.get("privacy_tier", "standard")),
            cost_class=str(d.get("cost_class", "medium")),
            latency_class=str(d.get("latency_class", "medium")),
            quality_tier=str(d.get("quality_tier", "standard")),
            reliability_class=str(d.get("reliability_class", "medium")),
            availability_class=str(d.get("availability_class", "broad")),
            deprecation_state=str(d.get("deprecation_state", DeprecationState.ACTIVE.value)),
            capabilities=_as_str_set(d.get("capabilities"), "capabilities"),
            policy_tags=_as_str_set(d.get("policy_tags"), "policy_tags"),
            est_cost_per_ktok=None if ecpt is None else float(ecpt),
            est_latency_ms=None if elm is None else float(elm),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "provider_id": self.provider_id,
            "modalities_in": list(self.modalities_in),
            "modalities_out": list(self.modalities_out),
            "context_limit": self.context_limit,
            "structured_output": self.structured_output,
            "tool_use": self.tool_use,
            "regions": list(self.regions),
            "privacy_tier": self.privacy_tier,
            "cost_class": self.cost_class,
            "latency_class": self.latency_class,
            "quality_tier": self.quality_tier,
            "reliability_class": self.reliability_class,
            "availability_class": self.availability_class,
            "deprecation_state": self.deprecation_state,
            "capabilities": list(self.capabilities),
            "policy_tags": list(self.policy_tags),
            "est_cost_per_ktok": self.est_cost_per_ktok,
            "est_latency_ms": self.est_latency_ms,
        }


# --------------------------------------------------------------------------------------
# Request
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class TaskRequirements:
    """Hard capability requirements a candidate must satisfy to be eligible."""

    required_modalities: Tuple[str, ...] = ()
    min_context_window: int = 0
    estimated_input_tokens: int = 0
    structured_output_required: bool = False
    tool_use_required: bool = False
    required_capabilities: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require(self.min_context_window >= 0, "min_context_window must be >= 0")
        _require(self.estimated_input_tokens >= 0, "estimated_input_tokens must be >= 0")
        for f_name in ("required_modalities", "required_capabilities"):
            object.__setattr__(self, f_name, _as_str_set(getattr(self, f_name), f_name))

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TaskRequirements":
        d = d or {}
        return cls(
            required_modalities=_as_str_set(d.get("required_modalities"), "required_modalities"),
            min_context_window=int(d.get("min_context_window", 0)),
            estimated_input_tokens=int(d.get("estimated_input_tokens", 0)),
            structured_output_required=bool(d.get("structured_output_required", False)),
            tool_use_required=bool(d.get("tool_use_required", False)),
            required_capabilities=_as_str_set(d.get("required_capabilities"), "required_capabilities"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "required_modalities": list(self.required_modalities),
            "min_context_window": self.min_context_window,
            "estimated_input_tokens": self.estimated_input_tokens,
            "structured_output_required": self.structured_output_required,
            "tool_use_required": self.tool_use_required,
            "required_capabilities": list(self.required_capabilities),
        }


@dataclass(frozen=True)
class SteeringRequest:
    """A routing request. Every field is data supplied by the caller; the controller
    never reads ambient state (clock, env, network) to fill any of it."""

    task_category: str = "general"
    requirements: TaskRequirements = field(default_factory=TaskRequirements)
    tenant: Optional[str] = None
    policy_domain: str = "default"
    latency_budget_ms: Optional[float] = None
    cost_budget: Optional[float] = None
    quality_preference: QualityPreference = QualityPreference.BALANCED
    privacy_classification: PrivacyClass = PrivacyClass.INTERNAL
    data_residency: Tuple[str, ...] = ()
    approved_providers: Tuple[str, ...] = ()
    prohibited_providers: Tuple[str, ...] = ()
    approved_models: Tuple[str, ...] = ()
    prohibited_models: Tuple[str, ...] = ()
    fallback_permitted: bool = True
    escalation_permitted: bool = True
    determinism_required: bool = False
    request_timestamp: Optional[str] = None  # caller-supplied; never used in a decision
    policy_version: Optional[str] = None  # defaults to the package POLICY_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.quality_preference, QualityPreference):
            object.__setattr__(self, "quality_preference", QualityPreference(str(self.quality_preference)))
        if not isinstance(self.privacy_classification, PrivacyClass):
            object.__setattr__(self, "privacy_classification", PrivacyClass(str(self.privacy_classification)))
        if not isinstance(self.requirements, TaskRequirements):
            object.__setattr__(self, "requirements", TaskRequirements.from_dict(self.requirements or {}))
        for f_name in ("data_residency", "approved_providers", "prohibited_providers",
                       "approved_models", "prohibited_models"):
            object.__setattr__(self, f_name, _as_str_set(getattr(self, f_name), f_name))
        if self.latency_budget_ms is not None:
            _require(float(self.latency_budget_ms) >= 0, "latency_budget_ms must be >= 0")
        if self.cost_budget is not None:
            _require(float(self.cost_budget) >= 0, "cost_budget must be >= 0 (negative budget is invalid)")

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SteeringRequest":
        _require(isinstance(d, dict), "steering request must be an object")
        return cls(
            task_category=str(d.get("task_category", "general")),
            requirements=TaskRequirements.from_dict(d.get("requirements") or {}),
            tenant=(None if d.get("tenant") is None else str(d.get("tenant"))),
            policy_domain=str(d.get("policy_domain", "default")),
            latency_budget_ms=(None if d.get("latency_budget_ms") is None else float(d["latency_budget_ms"])),
            cost_budget=(None if d.get("cost_budget") is None else float(d["cost_budget"])),
            quality_preference=QualityPreference(str(d.get("quality_preference", "balanced"))),
            privacy_classification=PrivacyClass(str(d.get("privacy_classification", "internal"))),
            data_residency=_as_str_set(d.get("data_residency"), "data_residency"),
            approved_providers=_as_str_set(d.get("approved_providers"), "approved_providers"),
            prohibited_providers=_as_str_set(d.get("prohibited_providers"), "prohibited_providers"),
            approved_models=_as_str_set(d.get("approved_models"), "approved_models"),
            prohibited_models=_as_str_set(d.get("prohibited_models"), "prohibited_models"),
            fallback_permitted=bool(d.get("fallback_permitted", True)),
            escalation_permitted=bool(d.get("escalation_permitted", True)),
            determinism_required=bool(d.get("determinism_required", False)),
            request_timestamp=(None if d.get("request_timestamp") is None else str(d["request_timestamp"])),
            policy_version=(None if d.get("policy_version") is None else str(d["policy_version"])),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_category": self.task_category,
            "requirements": self.requirements.to_dict(),
            "tenant": self.tenant,
            "policy_domain": self.policy_domain,
            "latency_budget_ms": self.latency_budget_ms,
            "cost_budget": self.cost_budget,
            "quality_preference": self.quality_preference.value,
            "privacy_classification": self.privacy_classification.value,
            "data_residency": list(self.data_residency),
            "approved_providers": list(self.approved_providers),
            "prohibited_providers": list(self.prohibited_providers),
            "approved_models": list(self.approved_models),
            "prohibited_models": list(self.prohibited_models),
            "fallback_permitted": self.fallback_permitted,
            "escalation_permitted": self.escalation_permitted,
            "determinism_required": self.determinism_required,
            "request_timestamp": self.request_timestamp,
            "policy_version": self.policy_version,
        }


# --------------------------------------------------------------------------------------
# Constraint / scoring / recommendation records
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class RoutingConstraint:
    """The outcome of evaluating one hard constraint against one candidate."""

    name: str
    satisfied: bool
    provenance: str  # e.g. "policy-hard", "verified-provider-fact", "request-budget"
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "satisfied": self.satisfied,
                "provenance": self.provenance, "detail": self.detail}


@dataclass(frozen=True)
class CandidateScore:
    """Decomposable score for one eligible candidate. ``components`` are the raw
    per-dimension fit scores in [0, 1]; ``total`` is the policy-weighted aggregate in
    [0, 1]. ``measurement_basis`` states the evidence class for the whole score."""

    model_id: str
    provider_id: str
    total: float
    components: Dict[str, float]
    weighted: Dict[str, float]
    measurement_basis: str = "estimated_from_declared_metadata"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "provider_id": self.provider_id,
            "total": self.total,
            "components": dict(sorted(self.components.items())),
            "weighted": dict(sorted(self.weighted.items())),
            "measurement_basis": self.measurement_basis,
        }


@dataclass(frozen=True)
class RoutingExplanation:
    """Human-readable + structured explanation of a routing recommendation."""

    summary: str
    reasons: Tuple[str, ...]
    weight_preset: str
    tie_break_rule: str

    def to_dict(self) -> Dict[str, Any]:
        return {"summary": self.summary, "reasons": list(self.reasons),
                "weight_preset": self.weight_preset, "tie_break_rule": self.tie_break_rule}


@dataclass(frozen=True)
class RoutingEvidence:
    """Everything needed to reproduce candidate filtering and ranking."""

    registry_fingerprint: str
    request_fingerprint: str
    policy_fingerprint: str
    candidates_considered: int
    eligible_count: int
    rejected: Tuple[Dict[str, Any], ...]
    scores: Tuple[Dict[str, Any], ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "registry_fingerprint": self.registry_fingerprint,
            "request_fingerprint": self.request_fingerprint,
            "policy_fingerprint": self.policy_fingerprint,
            "candidates_considered": self.candidates_considered,
            "eligible_count": self.eligible_count,
            "rejected": list(self.rejected),
            "scores": list(self.scores),
        }


@dataclass(frozen=True)
class RoutingDecisionTrace:
    """Ordered record of the deterministic pipeline stages that produced the decision."""

    stages: Tuple[str, ...]
    eligible_order: Tuple[str, ...]
    rejected_order: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {"stages": list(self.stages), "eligible_order": list(self.eligible_order),
                "rejected_order": list(self.rejected_order)}


@dataclass(frozen=True)
class FallbackRecommendation:
    """Ordered fallback candidates plus the conditions under which fallback / escalation
    is *recommended*. The controller never executes any of it."""

    permitted: bool
    ordered_candidates: Tuple[str, ...]
    conditions: Tuple[str, ...]
    escalation_recommended: bool
    escalation_conditions: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "permitted": self.permitted,
            "ordered_candidates": list(self.ordered_candidates),
            "conditions": list(self.conditions),
            "escalation_recommended": self.escalation_recommended,
            "escalation_conditions": list(self.escalation_conditions),
        }


@dataclass(frozen=True)
class RoutingRecommendation:
    """The advisory routing recommendation. ``execution_status`` is always
    ``NOT_EXECUTED`` and ``recommendation_only`` is always ``True``."""

    decision_id: str
    recommended_model: str
    recommended_provider: str
    ranked_alternatives: Tuple[str, ...]
    score: CandidateScore
    ranked_scores: Tuple[Dict[str, Any], ...]
    constraints_evaluated: Tuple[Dict[str, Any], ...]
    constraints_satisfied: Tuple[str, ...]
    constraints_rejected: Tuple[str, ...]
    policy_version: str
    confidence: float
    confidence_basis: str
    explanation: RoutingExplanation
    fallback: FallbackRecommendation
    evidence: RoutingEvidence
    trace: RoutingDecisionTrace
    execution_status: str = ExecutionStatus.NOT_EXECUTED.value
    recommendation_only: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "recommended_model": self.recommended_model,
            "recommended_provider": self.recommended_provider,
            "ranked_alternatives": list(self.ranked_alternatives),
            "score": self.score.to_dict(),
            "ranked_scores": list(self.ranked_scores),
            "constraints_evaluated": list(self.constraints_evaluated),
            "constraints_satisfied": list(self.constraints_satisfied),
            "constraints_rejected": list(self.constraints_rejected),
            "policy_version": self.policy_version,
            "confidence": self.confidence,
            "confidence_basis": self.confidence_basis,
            "explanation": self.explanation.to_dict(),
            "fallback": self.fallback.to_dict(),
            "evidence": self.evidence.to_dict(),
            "trace": self.trace.to_dict(),
            "execution_status": self.execution_status,
            "recommendation_only": self.recommendation_only,
        }


@dataclass(frozen=True)
class SteeringResult:
    """Top-level outcome. On success ``recommendation`` is populated and ``status`` is
    ``RECOMMENDED``. When nothing is eligible, ``status`` is ``NO_ELIGIBLE_CANDIDATE``,
    ``recommendation`` is ``None``, and ``evidence`` still explains every rejection."""

    status: str
    policy_version: str
    decision_id: str
    recommendation: Optional[RoutingRecommendation]
    evidence: RoutingEvidence
    trace: RoutingDecisionTrace
    reason: str = ""
    execution_status: str = ExecutionStatus.NOT_EXECUTED.value
    recommendation_only: bool = True

    @property
    def is_recommended(self) -> bool:
        return self.status == SteeringStatus.RECOMMENDED.value

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "policy_version": self.policy_version,
            "decision_id": self.decision_id,
            "recommendation": None if self.recommendation is None else self.recommendation.to_dict(),
            "evidence": self.evidence.to_dict(),
            "trace": self.trace.to_dict(),
            "reason": self.reason,
            "execution_status": self.execution_status,
            "recommendation_only": self.recommendation_only,
        }


__all__ = [
    "SteeringError", "ContractError", "RegistryError", "PolicyViolation", "NoEligibleCandidate",
    "QualityPreference", "PrivacyClass", "ExecutionStatus", "SteeringStatus", "Disposition",
    "DeprecationState",
    "ProviderCandidate", "ModelCandidate", "TaskRequirements", "SteeringRequest",
    "RoutingConstraint", "CandidateScore", "RoutingExplanation", "RoutingEvidence",
    "RoutingDecisionTrace", "FallbackRecommendation", "RoutingRecommendation", "SteeringResult",
    "COST_CLASS_ORDER", "LATENCY_CLASS_ORDER", "QUALITY_TIER_ORDER",
    "RELIABILITY_CLASS_ORDER", "AVAILABILITY_CLASS_ORDER",
]
