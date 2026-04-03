"""
Policy Externalization Layer — Versioned policy bundles with scoped overrides.

ARCHITECTURAL POSITION:
    Built governance layers (JEPA, Domain, Shadow, Core) → consume policy
    Policy Control Plane (THIS MODULE) → produce resolved policy

DESIGN PRINCIPLES:
    1. Declarative-first: policy is data structures, not code
    2. Versioned: every bundle has an immutable version identifier
    3. Scoped: global < tenant < domain < environment override precedence
    4. Validated: malformed bundles rejected early with clear errors
    5. Fail-closed: resolution failure produces a restrictive fallback policy
    6. Auditable: resolved policy carries provenance for replay

WHAT THIS MODULE DOES:
    - Defines the PolicyBundle model and its sections
    - Validates bundles against known invariants
    - Resolves scoped overrides into a single effective policy
    - Provides a fail-closed fallback when resolution fails
    - Carries policy version metadata for audit persistence

WHAT THIS MODULE DOES NOT DO:
    - Hot-reload from disk (future: Layer 6 productization)
    - Policy-as-code DSL (out of scope)
    - Persist policy bundles to durable storage (future)
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Tuple

_logger = logging.getLogger(__name__)


# =========================================================================
# Policy Scope
# =========================================================================


class PolicyScopeLevel(Enum):
    """Scope level for policy override precedence.

    Precedence: GLOBAL < TENANT < DOMAIN < ENVIRONMENT.
    Higher-precedence scopes override lower ones field-by-field.
    """
    GLOBAL = "global"
    TENANT = "tenant"
    DOMAIN = "domain"
    ENVIRONMENT = "environment"

    @property
    def precedence(self) -> int:
        return _SCOPE_PRECEDENCE[self]


_SCOPE_PRECEDENCE = {
    PolicyScopeLevel.GLOBAL: 0,
    PolicyScopeLevel.TENANT: 1,
    PolicyScopeLevel.DOMAIN: 2,
    PolicyScopeLevel.ENVIRONMENT: 3,
}


@dataclass(frozen=True)
class PolicyScope:
    """Targeting scope for a policy bundle.

    A bundle applies when ALL non-None fields match the runtime context.
    A None field means "match any" for that dimension.
    """
    level: PolicyScopeLevel = PolicyScopeLevel.GLOBAL
    tenant_id: Optional[str] = None
    domain_id: Optional[str] = None
    environment: Optional[str] = None

    def matches(
        self,
        tenant_id: Optional[str] = None,
        domain_id: Optional[str] = None,
        environment: Optional[str] = None,
    ) -> bool:
        """Check if this scope matches the given runtime context."""
        if self.tenant_id is not None and self.tenant_id != tenant_id:
            return False
        if self.domain_id is not None and self.domain_id != domain_id:
            return False
        if self.environment is not None and self.environment != environment:
            return False
        return True


# =========================================================================
# Policy Sections
# =========================================================================


@dataclass(frozen=True)
class JEPAPolicy:
    """Externalized JEPA governance policy.

    Maps governance regimes to recommended actions, confidence adjustments,
    execution mode overrides, and escalation overrides.
    """
    # Regime → recommended action: "ALLOW", "DEGRADE", "CONFIRM", "DENY", "HALT"
    regime_actions: Dict[str, str] = field(default_factory=lambda: {
        "NORMAL": "ALLOW",
        "PROCESS_DRIFT": "DEGRADE",
        "SEMANTIC_SHIFT": "CONFIRM",
        "DUAL_ANOMALY": "DENY",
        "UNKNOWN": "HALT",
    })
    # Regime → execution mode override (None = no override)
    regime_execution_modes: Dict[str, Optional[str]] = field(default_factory=lambda: {
        "NORMAL": None,
        "PROCESS_DRIFT": "CAUTIOUS",
        "SEMANTIC_SHIFT": "CONFIRM_REQUIRED",
        "DUAL_ANOMALY": "BLOCKED",
        "UNKNOWN": "BLOCKED",
    })
    # Regime → escalation override (None = no override)
    regime_escalations: Dict[str, Optional[str]] = field(default_factory=lambda: {
        "NORMAL": None,
        "PROCESS_DRIFT": "NOTIFY",
        "SEMANTIC_SHIFT": "CONFIRM",
        "DUAL_ANOMALY": "HALT",
        "UNKNOWN": "HALT",
    })
    # Regime → confidence adjustment
    regime_confidence_adjustments: Dict[str, float] = field(default_factory=lambda: {
        "NORMAL": 0.0,
        "PROCESS_DRIFT": -0.15,
        "SEMANTIC_SHIFT": -0.20,
        "DUAL_ANOMALY": -0.30,
        "UNKNOWN": -0.25,
    })


@dataclass(frozen=True)
class ConfidencePolicy:
    """Externalized confidence gate thresholds."""
    # Aggregation weights
    quality_weight: float = 0.30
    coherence_weight: float = 0.25
    stability_weight: float = 0.25
    action_weight: float = 0.20

    # Escalation thresholds
    escalation_halt_threshold: float = 0.35
    escalation_confirm_threshold: float = 0.55
    escalation_notify_threshold: float = 0.75

    # Execution mode thresholds
    execution_full_threshold: float = 0.75
    execution_cautious_threshold: float = 0.55
    execution_confirm_threshold: float = 0.35


@dataclass(frozen=True)
class SafetyPolicy:
    """Externalized safety contract thresholds and forbidden capabilities."""
    internal_consistency_threshold: float = 0.60
    goal_alignment_threshold: float = 0.60
    reversal_risk_threshold: float = 0.40
    identity_stability_threshold: float = 0.60

    forbidden_capabilities: Tuple[str, ...] = (
        "destructive_file_operations",
        "network_attacks",
        "credential_access",
        "privilege_escalation",
        "system_modification",
        "data_exfiltration",
        "malware_execution",
    )


@dataclass(frozen=True)
class RiskPolicy:
    """Externalized risk classification mappings."""
    # Risk level → action complexity score
    complexity_map: Dict[str, float] = field(default_factory=lambda: {
        "read_only": 0.1,
        "write": 0.4,
        "execute": 0.7,
        "destructive": 0.9,
        "privileged": 0.95,
    })
    # Risk level → reversibility score
    reversibility_map: Dict[str, float] = field(default_factory=lambda: {
        "read_only": 1.0,
        "write": 0.7,
        "execute": 0.5,
        "destructive": 0.0,
        "privileged": 0.2,
    })


@dataclass(frozen=True)
class ShadowPolicy:
    """Externalized shadow AI control policy.

    References the declarative rule and registry structures from shadow_ai.py.
    The rules themselves remain ShadowPolicyRule instances; this section
    carries the policy-level configuration that scoped overrides may change.
    """
    # Provenance → fail-closed containment for mutating actions
    provenance_fail_closed_mutating: Dict[str, str] = field(default_factory=lambda: {
        "shadow": "blocked",
        "revoked": "blocked",
        "quarantined": "blocked",
        "unverified": "require_confirmation",
    })
    # Provenance → fail-closed containment for read-only actions
    provenance_fail_closed_read: Dict[str, str] = field(default_factory=lambda: {
        "shadow": "read_only",
        "revoked": "blocked",
        "quarantined": "quarantined",
        "unverified": "allow",
    })
    # Whether to enable shadow AI evaluation
    enabled: bool = True
    # Max risk level enforcement enabled
    max_risk_enforcement_enabled: bool = True
    # Blocked capabilities enforcement enabled
    blocked_capabilities_enforcement_enabled: bool = True


@dataclass(frozen=True)
class DomainPolicyConfig:
    """Policy-level configuration for Domain Semantic Policy Layer.

    Does NOT duplicate DomainProfile data. Instead, carries policy-level
    controls that affect how domain profiles are applied.
    """
    # Whether domain policy evaluation is enabled
    enabled: bool = True
    # Default domain_id when none is specified at runtime
    default_domain_id: Optional[str] = None
    # Domain IDs that are blocked entirely (override profiles)
    blocked_domains: Tuple[str, ...] = ()


# =========================================================================
# Policy Metadata
# =========================================================================


@dataclass(frozen=True)
class PolicyMetadata:
    """Immutable metadata for a policy bundle."""
    policy_id: str
    version: str
    description: str = ""
    created_at: str = ""
    schema_version: str = "1.0.0"
    active: bool = True

    def fingerprint(self) -> str:
        """Compute a short deterministic fingerprint for audit."""
        raw = f"{self.policy_id}:{self.version}:{self.schema_version}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


# =========================================================================
# Policy Bundle
# =========================================================================


@dataclass(frozen=True)
class PolicyBundle:
    """A versioned, scoped governance policy bundle.

    Contains all externalized policy sections plus metadata and scope.
    Bundles are immutable after construction (frozen dataclass).
    """
    metadata: PolicyMetadata
    scope: PolicyScope = field(default_factory=PolicyScope)

    # Policy sections
    jepa: JEPAPolicy = field(default_factory=JEPAPolicy)
    confidence: ConfidencePolicy = field(default_factory=ConfidencePolicy)
    safety: SafetyPolicy = field(default_factory=SafetyPolicy)
    risk: RiskPolicy = field(default_factory=RiskPolicy)
    shadow: ShadowPolicy = field(default_factory=ShadowPolicy)
    domain: DomainPolicyConfig = field(default_factory=DomainPolicyConfig)

    def to_audit_dict(self) -> Dict[str, Any]:
        """Minimal audit-friendly representation for embedding in events."""
        return {
            "policy_id": self.metadata.policy_id,
            "version": self.metadata.version,
            "schema_version": self.metadata.schema_version,
            "fingerprint": self.metadata.fingerprint(),
            "scope_level": self.scope.level.value,
            "scope_tenant": self.scope.tenant_id,
            "scope_domain": self.scope.domain_id,
            "scope_environment": self.scope.environment,
        }


# =========================================================================
# Fail-closed fallback
# =========================================================================


FAIL_CLOSED_POLICY = PolicyBundle(
    metadata=PolicyMetadata(
        policy_id="__fail_closed__",
        version="0.0.0",
        description="Fail-closed fallback policy. Used when resolution fails.",
        schema_version="1.0.0",
        active=True,
    ),
    scope=PolicyScope(level=PolicyScopeLevel.GLOBAL),
    jepa=JEPAPolicy(
        regime_actions={
            "NORMAL": "CONFIRM",
            "PROCESS_DRIFT": "DENY",
            "SEMANTIC_SHIFT": "DENY",
            "DUAL_ANOMALY": "DENY",
            "UNKNOWN": "HALT",
        },
        regime_execution_modes={
            "NORMAL": "CONFIRM_REQUIRED",
            "PROCESS_DRIFT": "BLOCKED",
            "SEMANTIC_SHIFT": "BLOCKED",
            "DUAL_ANOMALY": "BLOCKED",
            "UNKNOWN": "BLOCKED",
        },
        regime_escalations={
            "NORMAL": "CONFIRM",
            "PROCESS_DRIFT": "HALT",
            "SEMANTIC_SHIFT": "HALT",
            "DUAL_ANOMALY": "HALT",
            "UNKNOWN": "HALT",
        },
        regime_confidence_adjustments={
            "NORMAL": -0.10,
            "PROCESS_DRIFT": -0.30,
            "SEMANTIC_SHIFT": -0.30,
            "DUAL_ANOMALY": -0.30,
            "UNKNOWN": -0.30,
        },
    ),
    confidence=ConfidencePolicy(
        escalation_halt_threshold=0.50,
        escalation_confirm_threshold=0.70,
        escalation_notify_threshold=0.90,
        execution_full_threshold=0.90,
        execution_cautious_threshold=0.70,
        execution_confirm_threshold=0.50,
    ),
    safety=SafetyPolicy(
        internal_consistency_threshold=0.70,
        goal_alignment_threshold=0.70,
        reversal_risk_threshold=0.30,
        identity_stability_threshold=0.70,
    ),
    shadow=ShadowPolicy(enabled=True),
    domain=DomainPolicyConfig(enabled=True),
)


# =========================================================================
# Default global policy (matches current hardcoded values)
# =========================================================================


DEFAULT_GLOBAL_POLICY = PolicyBundle(
    metadata=PolicyMetadata(
        policy_id="default-global",
        version="1.0.0",
        description="Default global governance policy matching hardcoded values.",
        created_at=datetime.now(timezone.utc).isoformat(),
        schema_version="1.0.0",
        active=True,
    ),
    scope=PolicyScope(level=PolicyScopeLevel.GLOBAL),
    jepa=JEPAPolicy(),
    confidence=ConfidencePolicy(),
    safety=SafetyPolicy(),
    risk=RiskPolicy(),
    shadow=ShadowPolicy(),
    domain=DomainPolicyConfig(),
)


# =========================================================================
# Example scoped overrides
# =========================================================================


FINANCE_TENANT_OVERRIDE = PolicyBundle(
    metadata=PolicyMetadata(
        policy_id="finance-tenant-strict",
        version="1.0.0",
        description="Strict override for finance tenant.",
        schema_version="1.0.0",
        active=True,
    ),
    scope=PolicyScope(
        level=PolicyScopeLevel.TENANT,
        tenant_id="finance-corp",
    ),
    confidence=ConfidencePolicy(
        escalation_halt_threshold=0.45,
        escalation_confirm_threshold=0.65,
        escalation_notify_threshold=0.85,
        execution_full_threshold=0.85,
        execution_cautious_threshold=0.65,
        execution_confirm_threshold=0.45,
    ),
    safety=SafetyPolicy(
        internal_consistency_threshold=0.70,
        goal_alignment_threshold=0.70,
        reversal_risk_threshold=0.30,
        identity_stability_threshold=0.70,
    ),
)

STAGING_ENV_OVERRIDE = PolicyBundle(
    metadata=PolicyMetadata(
        policy_id="staging-permissive",
        version="1.0.0",
        description="Permissive override for staging environment.",
        schema_version="1.0.0",
        active=True,
    ),
    scope=PolicyScope(
        level=PolicyScopeLevel.ENVIRONMENT,
        environment="staging",
    ),
    confidence=ConfidencePolicy(
        escalation_halt_threshold=0.20,
        escalation_confirm_threshold=0.40,
        escalation_notify_threshold=0.60,
        execution_full_threshold=0.60,
        execution_cautious_threshold=0.40,
        execution_confirm_threshold=0.20,
    ),
)


# =========================================================================
# Validation
# =========================================================================


class PolicyValidationError(Exception):
    """Raised when a policy bundle fails validation."""
    pass


_VALID_REGIME_KEYS = frozenset({
    "NORMAL", "PROCESS_DRIFT", "SEMANTIC_SHIFT", "DUAL_ANOMALY", "UNKNOWN",
})

_VALID_ACTIONS = frozenset({
    "ALLOW", "DEGRADE", "CONFIRM", "DENY", "HALT",
})

_VALID_EXECUTION_MODES = frozenset({
    None, "CAUTIOUS", "CONFIRM_REQUIRED", "BLOCKED",
})

_VALID_ESCALATIONS = frozenset({
    None, "NOTIFY", "CONFIRM", "HALT",
})

_VALID_CONTAINMENT_MODES = frozenset({
    "allow", "observe_only", "read_only", "draft_only", "sandbox_only",
    "memory_write_denied", "require_confirmation", "quarantined", "blocked",
})


def validate_policy_bundle(bundle: PolicyBundle) -> List[str]:
    """Validate a policy bundle. Returns list of error messages (empty = valid).

    Checks:
    - Required metadata fields
    - JEPA regime keys completeness and value validity
    - Threshold ranges [0.0, 1.0]
    - Confidence adjustment ranges [-1.0, 0.0]
    - Weight positivity and sum
    - Shadow containment mode validity
    - Forbidden capabilities non-empty in safety
    """
    errors: List[str] = []

    # Metadata
    if not bundle.metadata.policy_id:
        errors.append("metadata.policy_id is required")
    if not bundle.metadata.version:
        errors.append("metadata.version is required")

    # JEPA section
    jepa = bundle.jepa
    for name, mapping, valid_vals in [
        ("regime_actions", jepa.regime_actions, _VALID_ACTIONS),
        ("regime_execution_modes", jepa.regime_execution_modes, _VALID_EXECUTION_MODES),
        ("regime_escalations", jepa.regime_escalations, _VALID_ESCALATIONS),
    ]:
        missing_keys = _VALID_REGIME_KEYS - set(mapping.keys())
        if missing_keys:
            errors.append(f"jepa.{name} missing regimes: {sorted(missing_keys)}")
        for k, v in mapping.items():
            if k not in _VALID_REGIME_KEYS:
                errors.append(f"jepa.{name} unknown regime: {k}")
            if v not in valid_vals:
                errors.append(f"jepa.{name}[{k}] invalid value: {v}")

    for k, v in jepa.regime_confidence_adjustments.items():
        if k not in _VALID_REGIME_KEYS:
            errors.append(f"jepa.regime_confidence_adjustments unknown regime: {k}")
        if not (-1.0 <= v <= 0.0):
            errors.append(
                f"jepa.regime_confidence_adjustments[{k}]={v} "
                f"outside [-1.0, 0.0]"
            )
    missing_adj = _VALID_REGIME_KEYS - set(jepa.regime_confidence_adjustments.keys())
    if missing_adj:
        errors.append(
            f"jepa.regime_confidence_adjustments missing regimes: "
            f"{sorted(missing_adj)}"
        )

    # Confidence section
    conf = bundle.confidence
    for attr in (
        "quality_weight", "coherence_weight", "stability_weight", "action_weight",
    ):
        v = getattr(conf, attr)
        if v < 0.0:
            errors.append(f"confidence.{attr}={v} must be >= 0.0")

    weight_sum = (
        conf.quality_weight + conf.coherence_weight
        + conf.stability_weight + conf.action_weight
    )
    if abs(weight_sum - 1.0) > 0.01:
        errors.append(f"confidence weights sum to {weight_sum:.3f}, expected ~1.0")

    for attr in (
        "escalation_halt_threshold", "escalation_confirm_threshold",
        "escalation_notify_threshold",
        "execution_full_threshold", "execution_cautious_threshold",
        "execution_confirm_threshold",
    ):
        v = getattr(conf, attr)
        if not (0.0 <= v <= 1.0):
            errors.append(f"confidence.{attr}={v} outside [0.0, 1.0]")

    # Escalation thresholds must be ordered: halt < confirm < notify
    if conf.escalation_halt_threshold >= conf.escalation_confirm_threshold:
        errors.append(
            "confidence.escalation_halt_threshold must be < confirm_threshold"
        )
    if conf.escalation_confirm_threshold >= conf.escalation_notify_threshold:
        errors.append(
            "confidence.escalation_confirm_threshold must be < notify_threshold"
        )

    # Execution thresholds must be ordered: confirm < cautious < full
    if conf.execution_confirm_threshold >= conf.execution_cautious_threshold:
        errors.append(
            "confidence.execution_confirm_threshold must be < cautious_threshold"
        )
    if conf.execution_cautious_threshold >= conf.execution_full_threshold:
        errors.append(
            "confidence.execution_cautious_threshold must be < full_threshold"
        )

    # Safety section
    safety = bundle.safety
    for attr in (
        "internal_consistency_threshold", "goal_alignment_threshold",
        "identity_stability_threshold",
    ):
        v = getattr(safety, attr)
        if not (0.0 <= v <= 1.0):
            errors.append(f"safety.{attr}={v} outside [0.0, 1.0]")

    if not (0.0 <= safety.reversal_risk_threshold <= 1.0):
        errors.append(
            f"safety.reversal_risk_threshold={safety.reversal_risk_threshold} "
            f"outside [0.0, 1.0]"
        )

    if not safety.forbidden_capabilities:
        errors.append("safety.forbidden_capabilities must not be empty")

    # Shadow section
    shadow = bundle.shadow
    for name, mapping in [
        ("provenance_fail_closed_mutating", shadow.provenance_fail_closed_mutating),
        ("provenance_fail_closed_read", shadow.provenance_fail_closed_read),
    ]:
        for k, v in mapping.items():
            if v not in _VALID_CONTAINMENT_MODES:
                errors.append(f"shadow.{name}[{k}] invalid mode: {v}")

    return errors


def validate_or_raise(bundle: PolicyBundle) -> None:
    """Validate and raise PolicyValidationError if invalid."""
    errors = validate_policy_bundle(bundle)
    if errors:
        raise PolicyValidationError(
            f"Policy bundle '{bundle.metadata.policy_id}' v{bundle.metadata.version} "
            f"has {len(errors)} validation error(s):\n"
            + "\n".join(f"  - {e}" for e in errors)
        )


# =========================================================================
# Policy Loader
# =========================================================================


def policy_bundle_from_dict(data: Dict[str, Any]) -> PolicyBundle:
    """Construct a PolicyBundle from a plain dict (e.g. parsed JSON/YAML).

    Validates the bundle after construction. Raises PolicyValidationError
    on invalid data, KeyError/TypeError on malformed structure.
    """
    meta_d = data.get("metadata", {})
    scope_d = data.get("scope", {})

    metadata = PolicyMetadata(
        policy_id=meta_d["policy_id"],
        version=meta_d["version"],
        description=meta_d.get("description", ""),
        created_at=meta_d.get("created_at", ""),
        schema_version=meta_d.get("schema_version", "1.0.0"),
        active=meta_d.get("active", True),
    )

    scope = PolicyScope(
        level=PolicyScopeLevel(scope_d.get("level", "global")),
        tenant_id=scope_d.get("tenant_id"),
        domain_id=scope_d.get("domain_id"),
        environment=scope_d.get("environment"),
    )

    jepa_d = data.get("jepa", {})
    jepa = JEPAPolicy(
        regime_actions=jepa_d.get("regime_actions", JEPAPolicy().regime_actions),
        regime_execution_modes=jepa_d.get(
            "regime_execution_modes", JEPAPolicy().regime_execution_modes,
        ),
        regime_escalations=jepa_d.get(
            "regime_escalations", JEPAPolicy().regime_escalations,
        ),
        regime_confidence_adjustments=jepa_d.get(
            "regime_confidence_adjustments",
            JEPAPolicy().regime_confidence_adjustments,
        ),
    )

    conf_d = data.get("confidence", {})
    confidence = ConfidencePolicy(**{
        k: conf_d[k] for k in conf_d
        if hasattr(ConfidencePolicy, k)
    }) if conf_d else ConfidencePolicy()

    safety_d = data.get("safety", {})
    safety_kwargs: Dict[str, Any] = {}
    if safety_d:
        for k in ("internal_consistency_threshold", "goal_alignment_threshold",
                   "reversal_risk_threshold", "identity_stability_threshold"):
            if k in safety_d:
                safety_kwargs[k] = safety_d[k]
        if "forbidden_capabilities" in safety_d:
            safety_kwargs["forbidden_capabilities"] = tuple(
                safety_d["forbidden_capabilities"]
            )
    safety = SafetyPolicy(**safety_kwargs) if safety_kwargs else SafetyPolicy()

    risk_d = data.get("risk", {})
    risk = RiskPolicy(
        complexity_map=risk_d.get("complexity_map", RiskPolicy().complexity_map),
        reversibility_map=risk_d.get(
            "reversibility_map", RiskPolicy().reversibility_map,
        ),
    ) if risk_d else RiskPolicy()

    shadow_d = data.get("shadow", {})
    shadow_kwargs: Dict[str, Any] = {}
    if shadow_d:
        for k in ("enabled", "max_risk_enforcement_enabled",
                   "blocked_capabilities_enforcement_enabled"):
            if k in shadow_d:
                shadow_kwargs[k] = shadow_d[k]
        for k in ("provenance_fail_closed_mutating", "provenance_fail_closed_read"):
            if k in shadow_d:
                shadow_kwargs[k] = shadow_d[k]
    shadow = ShadowPolicy(**shadow_kwargs) if shadow_kwargs else ShadowPolicy()

    domain_d = data.get("domain", {})
    domain_kwargs: Dict[str, Any] = {}
    if domain_d:
        if "enabled" in domain_d:
            domain_kwargs["enabled"] = domain_d["enabled"]
        if "default_domain_id" in domain_d:
            domain_kwargs["default_domain_id"] = domain_d["default_domain_id"]
        if "blocked_domains" in domain_d:
            domain_kwargs["blocked_domains"] = tuple(domain_d["blocked_domains"])
    domain_cfg = DomainPolicyConfig(**domain_kwargs) if domain_kwargs else DomainPolicyConfig()

    bundle = PolicyBundle(
        metadata=metadata,
        scope=scope,
        jepa=jepa,
        confidence=confidence,
        safety=safety,
        risk=risk,
        shadow=shadow,
        domain=domain_cfg,
    )

    validate_or_raise(bundle)
    return bundle


def policy_bundle_from_json(json_str: str) -> PolicyBundle:
    """Parse a JSON string into a validated PolicyBundle."""
    data = json.loads(json_str)
    return policy_bundle_from_dict(data)


# =========================================================================
# Policy Resolver
# =========================================================================


@dataclass(frozen=True)
class PolicyResolution:
    """Result of resolving scoped policy overrides.

    Carries the effective policy plus provenance for audit.
    """
    effective_policy: PolicyBundle
    base_policy_id: str
    base_version: str
    applied_overrides: Tuple[str, ...] = ()
    resolution_timestamp: str = ""
    failed: bool = False
    failure_reason: str = ""

    def to_audit_dict(self) -> Dict[str, Any]:
        """Audit-friendly representation."""
        return {
            "effective_policy_id": self.effective_policy.metadata.policy_id,
            "effective_version": self.effective_policy.metadata.version,
            "effective_fingerprint": self.effective_policy.metadata.fingerprint(),
            "base_policy_id": self.base_policy_id,
            "base_version": self.base_version,
            "applied_overrides": list(self.applied_overrides),
            "failed": self.failed,
            "failure_reason": self.failure_reason,
        }


def _merge_dict(base: Dict, override: Dict) -> Dict:
    """Shallow merge: override values replace base values."""
    merged = dict(base)
    merged.update(override)
    return merged


def _merge_section(base: Any, override: Any) -> Any:
    """Merge two frozen dataclass sections. Override fields replace base.

    For dict fields, does a shallow merge. For scalar fields, override wins
    if it differs from the section's default.
    """
    if type(base) is not type(override):
        return override

    # Get default values for comparison
    default_instance = type(base)()
    merged_kwargs = {}

    for f in base.__dataclass_fields__:
        base_val = getattr(base, f)
        override_val = getattr(override, f)
        default_val = getattr(default_instance, f)

        if isinstance(base_val, dict) and isinstance(override_val, dict):
            # Dict fields: merge
            merged_kwargs[f] = _merge_dict(base_val, override_val)
        elif override_val != default_val:
            # Override has a non-default value: use it
            merged_kwargs[f] = override_val
        else:
            # Override is at default: keep base
            merged_kwargs[f] = base_val

    return type(base)(**merged_kwargs)


def resolve_effective_policy(
    base: PolicyBundle,
    overrides: Sequence[PolicyBundle] = (),
    *,
    tenant_id: Optional[str] = None,
    domain_id: Optional[str] = None,
    environment: Optional[str] = None,
) -> PolicyResolution:
    """Resolve scoped overrides into a single effective policy.

    Algorithm:
    1. Start with the base policy
    2. Filter overrides to those matching the runtime context
    3. Sort matching overrides by scope precedence (global < tenant < domain < env)
    4. Apply each override section-by-section (field-by-field merge)
    5. Construct a new PolicyBundle with merged metadata

    If resolution fails for any reason, returns FAIL_CLOSED_POLICY.
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    try:
        # Filter to matching, active overrides
        matching = [
            o for o in overrides
            if o.metadata.active
            and o.scope.matches(tenant_id, domain_id, environment)
        ]

        # Sort by scope precedence
        matching.sort(key=lambda o: o.scope.level.precedence)

        # Apply overrides
        effective_jepa = base.jepa
        effective_confidence = base.confidence
        effective_safety = base.safety
        effective_risk = base.risk
        effective_shadow = base.shadow
        effective_domain = base.domain
        applied_ids: List[str] = []

        for override in matching:
            effective_jepa = _merge_section(effective_jepa, override.jepa)
            effective_confidence = _merge_section(
                effective_confidence, override.confidence,
            )
            effective_safety = _merge_section(effective_safety, override.safety)
            effective_risk = _merge_section(effective_risk, override.risk)
            effective_shadow = _merge_section(effective_shadow, override.shadow)
            effective_domain = _merge_section(effective_domain, override.domain)
            applied_ids.append(
                f"{override.metadata.policy_id}:v{override.metadata.version}"
            )

        # Build resolved metadata
        if applied_ids:
            resolved_id = f"{base.metadata.policy_id}+{'+'.join(applied_ids)}"
            resolved_version = f"{base.metadata.version}+resolved"
        else:
            resolved_id = base.metadata.policy_id
            resolved_version = base.metadata.version

        resolved_meta = PolicyMetadata(
            policy_id=resolved_id,
            version=resolved_version,
            description=f"Resolved from {base.metadata.policy_id} with {len(applied_ids)} override(s)",
            created_at=timestamp,
            schema_version=base.metadata.schema_version,
            active=True,
        )

        effective = PolicyBundle(
            metadata=resolved_meta,
            scope=base.scope,
            jepa=effective_jepa,
            confidence=effective_confidence,
            safety=effective_safety,
            risk=effective_risk,
            shadow=effective_shadow,
            domain=effective_domain,
        )

        # Validate resolved policy
        validate_or_raise(effective)

        return PolicyResolution(
            effective_policy=effective,
            base_policy_id=base.metadata.policy_id,
            base_version=base.metadata.version,
            applied_overrides=tuple(applied_ids),
            resolution_timestamp=timestamp,
        )

    except Exception as exc:
        _logger.error(
            "POLICY RESOLUTION FAILED — using fail-closed policy: %s",
            exc,
            exc_info=True,
        )
        return PolicyResolution(
            effective_policy=FAIL_CLOSED_POLICY,
            base_policy_id=base.metadata.policy_id,
            base_version=base.metadata.version,
            applied_overrides=(),
            resolution_timestamp=timestamp,
            failed=True,
            failure_reason=f"{type(exc).__name__}: {exc}",
        )
