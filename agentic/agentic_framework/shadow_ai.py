"""
Shadow AI Control Layer — Provenance, sanctionedness, and containment
for unsanctioned or untrusted AI/agent/model/tool/workflow usage.

ARCHITECTURAL PLACEMENT:
    3. Domain Semantic Policy Layer
    3.5. Shadow AI Control Layer  <-- THIS MODULE
    4. Execution / Runtime Enforcement Layer

DESIGN PRINCIPLES:
    1. Shadow AI is a governance condition, not just discovery/inventory
    2. Both provenance problems AND semantic mismatch detect shadow AI
    3. Domain-aware containment (shadow posture depends on domain context)
    4. Stricter-only: shadow policy can restrict, never relax governance
    5. Audit-first: all shadow decisions are durably visible
    6. Declarative-first: registry + rules before ML detection
    7. Fail-closed: unknown/untrusted assets blocked in sensitive contexts

SHADOW AI DEFINITION:
    - AI model/agent/MCP server/plugin/tool/workflow operating outside
      approved governance visibility or approval
    - OR an otherwise approved intelligence path behaving outside its
      sanctioned semantic-governance boundary
"""

from __future__ import annotations

import enum
import fnmatch
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Tuple

_logger = logging.getLogger(__name__)


# =========================================================================
# Enums
# =========================================================================


class ProvenanceStatus(enum.Enum):
    """Sanctionedness state of an AI asset."""
    APPROVED = "approved"
    UNVERIFIED = "unverified"
    SHADOW = "shadow"
    QUARANTINED = "quarantined"
    REVOKED = "revoked"


class ShadowAssetType(enum.Enum):
    """Type of AI/intelligence asset."""
    MODEL_ENDPOINT = "model_endpoint"
    AGENT = "agent"
    MCP_SERVER = "mcp_server"
    TOOL = "tool"
    PLUGIN = "plugin"
    WORKFLOW = "workflow"
    BROWSER_AI = "browser_ai"
    EXTERNAL_API = "external_api"
    MEMORY_SOURCE = "memory_source"
    UNKNOWN = "unknown"


class ShadowTrustLevel(enum.Enum):
    """Trust level for an AI asset."""
    TRUSTED = "trusted"
    LIMITED = "limited"
    UNTRUSTED = "untrusted"
    BLOCKED = "blocked"

    @property
    def severity(self) -> int:
        return _TRUST_SEVERITY[self]


_TRUST_SEVERITY: Dict[ShadowTrustLevel, int] = {
    ShadowTrustLevel.TRUSTED: 0,
    ShadowTrustLevel.LIMITED: 1,
    ShadowTrustLevel.UNTRUSTED: 2,
    ShadowTrustLevel.BLOCKED: 3,
}


class ShadowContainmentMode(enum.Enum):
    """Containment / response mode from shadow AI assessment.

    Ordered from most permissive to most restrictive.
    Maps to DomainActionMode where applicable, but preserves
    the semantic distinction that posture came from shadow-AI control.
    """
    ALLOW = "allow"
    OBSERVE_ONLY = "observe_only"
    READ_ONLY = "read_only"
    DRAFT_ONLY = "draft_only"
    SANDBOX_ONLY = "sandbox_only"
    MEMORY_WRITE_DENIED = "memory_write_denied"
    REQUIRE_CONFIRMATION = "require_confirmation"
    QUARANTINED = "quarantined"
    BLOCKED = "blocked"

    @property
    def severity(self) -> int:
        return _CONTAINMENT_SEVERITY[self]

    def is_stricter_than(self, other: "ShadowContainmentMode") -> bool:
        return self.severity > other.severity


_CONTAINMENT_SEVERITY: Dict[ShadowContainmentMode, int] = {
    ShadowContainmentMode.ALLOW: 0,
    ShadowContainmentMode.OBSERVE_ONLY: 1,
    ShadowContainmentMode.READ_ONLY: 2,
    ShadowContainmentMode.DRAFT_ONLY: 3,
    ShadowContainmentMode.SANDBOX_ONLY: 4,
    ShadowContainmentMode.MEMORY_WRITE_DENIED: 5,
    ShadowContainmentMode.REQUIRE_CONFIRMATION: 6,
    ShadowContainmentMode.QUARANTINED: 7,
    ShadowContainmentMode.BLOCKED: 8,
}


def _stricter_containment(
    a: ShadowContainmentMode, b: ShadowContainmentMode,
) -> ShadowContainmentMode:
    """Return the stricter of two containment modes."""
    return a if a.severity >= b.severity else b


# =========================================================================
# Data Models
# =========================================================================


@dataclass(frozen=True)
class ShadowRegistryEntry:
    """A sanctioned AI asset in the shadow registry.

    Attributes:
        asset_id: Unique identifier for the asset.
        asset_type: Type of AI asset.
        provenance: Sanctionedness status.
        trust_level: Trust classification.
        provider: Provider/vendor name (e.g. "anthropic", "openai").
        allowed_domains: Domains where this asset is sanctioned (empty=all).
        allowed_capabilities: Capabilities this asset is sanctioned for.
        blocked_capabilities: Capabilities explicitly denied.
        max_risk_level: Maximum tool risk level this asset may use.
        active: Whether this entry is currently active.
        metadata: Additional metadata for audit.
    """
    asset_id: str
    asset_type: ShadowAssetType
    provenance: ProvenanceStatus = ProvenanceStatus.APPROVED
    trust_level: ShadowTrustLevel = ShadowTrustLevel.TRUSTED
    provider: str = ""
    allowed_domains: FrozenSet[str] = field(default_factory=frozenset)
    allowed_capabilities: FrozenSet[str] = field(default_factory=frozenset)
    blocked_capabilities: FrozenSet[str] = field(default_factory=frozenset)
    max_risk_level: Optional[str] = None
    active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ShadowRiskFactors:
    """Structured risk factors for shadow AI assessment.

    Each factor is visible individually for audit, not collapsed
    into an opaque scalar.
    """
    provenance_risk: float = 0.0        # from sanctionedness state
    identity_confidence: float = 1.0     # how sure we are about asset identity
    domain_mismatch: float = 0.0         # asset outside allowed domain
    action_risk: float = 0.0             # risk from action category
    tool_risk: float = 0.0              # risk from tool classification
    data_sensitivity: float = 0.0        # sensitivity of data involved
    semantic_governance_mismatch: float = 0.0  # JEPA/vritti incoherence
    domain_policy_mismatch: float = 0.0  # domain policy disagreement
    hidden_intelligence_path: float = 0.0  # external AI path detection
    memory_write_risk: float = 0.0       # untrusted AI writing memory
    external_side_effects: float = 0.0   # external mutation risk
    execution_privilege: float = 0.0     # privilege level of execution
    unexpected_usage: float = 0.0        # asset used outside sanctioned scope

    @property
    def composite_score(self) -> float:
        """Weighted composite risk score [0, 1].

        Exposed for convenience but individual factors are authoritative.
        """
        weights = {
            "provenance_risk": 2.0,
            "identity_confidence_inv": 1.5,
            "domain_mismatch": 1.5,
            "action_risk": 1.0,
            "tool_risk": 1.0,
            "semantic_governance_mismatch": 2.0,
            "domain_policy_mismatch": 1.5,
            "hidden_intelligence_path": 2.0,
            "memory_write_risk": 1.5,
            "external_side_effects": 1.0,
            "execution_privilege": 1.0,
            "unexpected_usage": 1.5,
        }
        total_weight = sum(weights.values())
        score = (
            weights["provenance_risk"] * self.provenance_risk
            + weights["identity_confidence_inv"] * (1.0 - self.identity_confidence)
            + weights["domain_mismatch"] * self.domain_mismatch
            + weights["action_risk"] * self.action_risk
            + weights["tool_risk"] * self.tool_risk
            + weights["semantic_governance_mismatch"] * self.semantic_governance_mismatch
            + weights["domain_policy_mismatch"] * self.domain_policy_mismatch
            + weights["hidden_intelligence_path"] * self.hidden_intelligence_path
            + weights["memory_write_risk"] * self.memory_write_risk
            + weights["external_side_effects"] * self.external_side_effects
            + weights["execution_privilege"] * self.execution_privilege
            + weights["unexpected_usage"] * self.unexpected_usage
        )
        return min(1.0, max(0.0, score / total_weight))

    def to_dict(self) -> Dict[str, float]:
        """Serialize all factors to a flat dict for audit."""
        return {
            "provenance_risk": self.provenance_risk,
            "identity_confidence": self.identity_confidence,
            "domain_mismatch": self.domain_mismatch,
            "action_risk": self.action_risk,
            "tool_risk": self.tool_risk,
            "data_sensitivity": self.data_sensitivity,
            "semantic_governance_mismatch": self.semantic_governance_mismatch,
            "domain_policy_mismatch": self.domain_policy_mismatch,
            "hidden_intelligence_path": self.hidden_intelligence_path,
            "memory_write_risk": self.memory_write_risk,
            "external_side_effects": self.external_side_effects,
            "execution_privilege": self.execution_privilege,
            "unexpected_usage": self.unexpected_usage,
            "composite_score": self.composite_score,
        }


@dataclass(frozen=True)
class ShadowAssessment:
    """Full shadow AI assessment for a single request/action.

    This is the primary output of the shadow policy resolver.
    """
    provenance_status: ProvenanceStatus
    asset_type: ShadowAssetType
    trust_level: ShadowTrustLevel
    containment_mode: ShadowContainmentMode
    risk_factors: ShadowRiskFactors
    reason_codes: Tuple[str, ...] = ()
    rationale: str = ""
    registry_entry_id: Optional[str] = None
    shadow_overrode_baseline: bool = False
    asset_identity_summary: str = ""

    def to_audit_dict(self) -> Dict[str, Any]:
        """Serialize to audit-friendly dict."""
        return {
            "provenance_status": self.provenance_status.value,
            "asset_type": self.asset_type.value,
            "trust_level": self.trust_level.value,
            "containment_mode": self.containment_mode.value,
            "risk_factors": self.risk_factors.to_dict(),
            "reason_codes": list(self.reason_codes),
            "rationale": self.rationale,
            "registry_entry_id": self.registry_entry_id,
            "shadow_overrode_baseline": self.shadow_overrode_baseline,
            "asset_identity_summary": self.asset_identity_summary,
        }


# =========================================================================
# Shadow Asset Registry
# =========================================================================


class ShadowRegistry:
    """Registry of sanctioned AI assets.

    Supports registration, lookup by various keys, and fallback
    handling for unknown assets. First version is in-memory +
    config-backed (matches repo style).

    Unknown assets return None from lookup, triggering fail-closed
    handling in the policy resolver.
    """

    def __init__(
        self,
        entries: Optional[Sequence[ShadowRegistryEntry]] = None,
    ) -> None:
        self._by_id: Dict[str, ShadowRegistryEntry] = {}
        self._by_pattern: List[Tuple[str, ShadowRegistryEntry]] = []
        if entries:
            for e in entries:
                self.register(e)

    def register(self, entry: ShadowRegistryEntry) -> None:
        """Register a sanctioned AI asset."""
        self._by_id[entry.asset_id] = entry
        # Also index as a pattern for glob-style lookup
        self._by_pattern.append((entry.asset_id, entry))

    def lookup(self, asset_id: str) -> Optional[ShadowRegistryEntry]:
        """Look up by exact asset ID."""
        entry = self._by_id.get(asset_id)
        if entry is not None and entry.active:
            return entry
        return None

    def lookup_by_pattern(self, name: str) -> Optional[ShadowRegistryEntry]:
        """Look up by pattern matching (glob).

        Tries exact match first, then glob patterns. Returns the first
        active match, or None.
        """
        # Exact match first
        exact = self.lookup(name)
        if exact is not None:
            return exact
        # Glob pattern match
        for pattern, entry in self._by_pattern:
            if entry.active and fnmatch.fnmatch(name, pattern):
                return entry
        return None

    def lookup_by_provider(self, provider: str) -> List[ShadowRegistryEntry]:
        """Find all active entries for a provider."""
        return [
            e for e in self._by_id.values()
            if e.active and e.provider == provider
        ]

    def is_sanctioned(self, asset_id: str) -> bool:
        """Check if an asset is registered and approved."""
        entry = self.lookup(asset_id)
        return (
            entry is not None
            and entry.provenance == ProvenanceStatus.APPROVED
            and entry.active
        )

    def all_entries(self) -> List[ShadowRegistryEntry]:
        """Return all registered entries."""
        return list(self._by_id.values())


# =========================================================================
# Shadow Policy Rules
# =========================================================================


@dataclass(frozen=True)
class ShadowPolicyRule:
    """Declarative shadow AI policy rule.

    When all specified conditions match, the rule imposes its
    result_mode. Conditions left as None/empty are wildcards.

    Attributes:
        name: Human-readable rule name for audit.
        provenance_states: Provenance states this rule applies to.
        asset_types: Asset types this rule applies to.
        trust_levels: Trust levels this rule applies to.
        domain_ids: Domains where this rule applies (empty=any).
        action_categories: Action categories this rule targets.
        requires_memory_write: If True, rule fires only on memory writes.
        requires_mutation: If True, rule fires only on mutating actions.
        min_semantic_mismatch: Min JEPA mismatch to trigger (0.0=always).
        result_mode: Containment mode to impose.
        reason: Human-readable reason for audit.
    """
    name: str
    provenance_states: FrozenSet[ProvenanceStatus] = field(
        default_factory=frozenset,
    )
    asset_types: FrozenSet[ShadowAssetType] = field(
        default_factory=frozenset,
    )
    trust_levels: FrozenSet[ShadowTrustLevel] = field(
        default_factory=frozenset,
    )
    domain_ids: FrozenSet[str] = field(default_factory=frozenset)
    action_categories: FrozenSet[str] = field(default_factory=frozenset)
    requires_memory_write: bool = False
    requires_mutation: bool = False
    min_semantic_mismatch: float = 0.0
    result_mode: ShadowContainmentMode = ShadowContainmentMode.BLOCKED
    reason: str = ""


# =========================================================================
# Built-in Shadow Policy Rules
# =========================================================================


DEFAULT_SHADOW_RULES: Tuple[ShadowPolicyRule, ...] = (
    # Rule 1: Unknown / unverified external AI + privileged action -> BLOCKED
    ShadowPolicyRule(
        name="unverified_privileged_block",
        provenance_states=frozenset({
            ProvenanceStatus.UNVERIFIED, ProvenanceStatus.SHADOW,
        }),
        action_categories=frozenset({"privileged", "destructive"}),
        result_mode=ShadowContainmentMode.BLOCKED,
        reason="Unverified AI asset attempting privileged/destructive action",
    ),
    # Rule 2: Unapproved MCP server / tool provider -> QUARANTINED
    ShadowPolicyRule(
        name="unapproved_mcp_quarantine",
        provenance_states=frozenset({
            ProvenanceStatus.UNVERIFIED, ProvenanceStatus.SHADOW,
        }),
        asset_types=frozenset({
            ShadowAssetType.MCP_SERVER, ShadowAssetType.TOOL,
        }),
        result_mode=ShadowContainmentMode.QUARANTINED,
        reason="Unapproved MCP server or tool provider",
    ),
    # Rule 3: Memory write from untrusted AI -> MEMORY_WRITE_DENIED
    ShadowPolicyRule(
        name="untrusted_memory_write_denied",
        trust_levels=frozenset({
            ShadowTrustLevel.UNTRUSTED, ShadowTrustLevel.BLOCKED,
        }),
        requires_memory_write=True,
        result_mode=ShadowContainmentMode.MEMORY_WRITE_DENIED,
        reason="Untrusted AI attempting memory write",
    ),
    # Rule 4: Unverified AI + mutating action -> REQUIRE_CONFIRMATION
    ShadowPolicyRule(
        name="unverified_mutation_confirm",
        provenance_states=frozenset({ProvenanceStatus.UNVERIFIED}),
        requires_mutation=True,
        result_mode=ShadowContainmentMode.REQUIRE_CONFIRMATION,
        reason="Unverified AI attempting mutating action",
    ),
    # Rule 5: Shadow browser AI + finance domain + mutating -> BLOCKED
    ShadowPolicyRule(
        name="shadow_browser_finance_block",
        provenance_states=frozenset({ProvenanceStatus.SHADOW}),
        asset_types=frozenset({ShadowAssetType.BROWSER_AI}),
        domain_ids=frozenset({"finance"}),
        requires_mutation=True,
        result_mode=ShadowContainmentMode.BLOCKED,
        reason="Shadow browser AI attempting mutation in finance domain",
    ),
    # Rule 6: Revoked asset -> always BLOCKED
    ShadowPolicyRule(
        name="revoked_asset_block",
        provenance_states=frozenset({ProvenanceStatus.REVOKED}),
        result_mode=ShadowContainmentMode.BLOCKED,
        reason="Revoked AI asset",
    ),
    # Rule 7: High semantic-governance mismatch from approved asset
    ShadowPolicyRule(
        name="approved_semantic_mismatch_quarantine",
        provenance_states=frozenset({ProvenanceStatus.APPROVED}),
        min_semantic_mismatch=0.6,
        result_mode=ShadowContainmentMode.QUARANTINED,
        reason="Approved asset with high semantic-governance mismatch (possible drift)",
    ),
    # Rule 8: Unverified external model in research -> READ_ONLY
    ShadowPolicyRule(
        name="unverified_research_read_only",
        provenance_states=frozenset({ProvenanceStatus.UNVERIFIED}),
        domain_ids=frozenset({"research"}),
        result_mode=ShadowContainmentMode.READ_ONLY,
        reason="Unverified external model in research domain — read-only",
    ),
    # Rule 9: Shadow AI + finance domain -> BLOCKED
    ShadowPolicyRule(
        name="shadow_finance_block",
        provenance_states=frozenset({
            ProvenanceStatus.SHADOW, ProvenanceStatus.UNVERIFIED,
        }),
        domain_ids=frozenset({"finance", "healthcare", "legal"}),
        requires_mutation=True,
        result_mode=ShadowContainmentMode.BLOCKED,
        reason="Shadow/unverified AI mutating in sensitive domain",
    ),
    # Rule 10: Blocked trust level -> always BLOCKED
    ShadowPolicyRule(
        name="blocked_trust_block",
        trust_levels=frozenset({ShadowTrustLevel.BLOCKED}),
        result_mode=ShadowContainmentMode.BLOCKED,
        reason="Blocked trust level",
    ),
)


# =========================================================================
# Shadow Policy Resolver — helpers
# =========================================================================


def _provenance_risk(status: ProvenanceStatus) -> float:
    """Map provenance status to risk score."""
    return {
        ProvenanceStatus.APPROVED: 0.0,
        ProvenanceStatus.UNVERIFIED: 0.5,
        ProvenanceStatus.SHADOW: 0.8,
        ProvenanceStatus.QUARANTINED: 0.9,
        ProvenanceStatus.REVOKED: 1.0,
    }.get(status, 1.0)


def _trust_risk(level: ShadowTrustLevel) -> float:
    """Map trust level to identity confidence."""
    return {
        ShadowTrustLevel.TRUSTED: 1.0,
        ShadowTrustLevel.LIMITED: 0.6,
        ShadowTrustLevel.UNTRUSTED: 0.2,
        ShadowTrustLevel.BLOCKED: 0.0,
    }.get(level, 0.0)


def _action_risk(action_category: str) -> float:
    """Map action category to risk score."""
    return {
        "read_only": 0.0,
        "mutating": 0.4,
        "destructive": 0.8,
        "privileged": 1.0,
        "unknown": 0.5,
    }.get(action_category, 0.5)


def _tool_risk_score(risk_level: str) -> float:
    """Map tool risk level string to risk score."""
    return {
        "read_only": 0.0,
        "write": 0.3,
        "execute": 0.6,
        "destructive": 0.9,
        "privileged": 1.0,
    }.get(risk_level, 0.5)


def _classify_unknown_asset(
    asset_id: str,
    tool_name: str,
    provider: str,
) -> Tuple[ShadowAssetType, ProvenanceStatus, ShadowTrustLevel]:
    """Classify an unknown asset that is not in the registry.

    Fail-closed: unknown assets are classified as SHADOW/UNTRUSTED.
    """
    # Heuristic: MCP server patterns
    if "mcp" in asset_id.lower() or "mcp" in tool_name.lower():
        return ShadowAssetType.MCP_SERVER, ProvenanceStatus.SHADOW, ShadowTrustLevel.UNTRUSTED
    if "browser" in asset_id.lower():
        return ShadowAssetType.BROWSER_AI, ProvenanceStatus.SHADOW, ShadowTrustLevel.UNTRUSTED
    if "agent" in asset_id.lower():
        return ShadowAssetType.AGENT, ProvenanceStatus.SHADOW, ShadowTrustLevel.UNTRUSTED
    if "model" in asset_id.lower() or "endpoint" in asset_id.lower():
        return ShadowAssetType.MODEL_ENDPOINT, ProvenanceStatus.SHADOW, ShadowTrustLevel.UNTRUSTED
    if tool_name:
        return ShadowAssetType.TOOL, ProvenanceStatus.UNVERIFIED, ShadowTrustLevel.UNTRUSTED
    return ShadowAssetType.UNKNOWN, ProvenanceStatus.SHADOW, ShadowTrustLevel.UNTRUSTED


def _rule_matches(
    rule: ShadowPolicyRule,
    provenance: ProvenanceStatus,
    asset_type: ShadowAssetType,
    trust_level: ShadowTrustLevel,
    domain_id: str,
    action_category: str,
    memory_write_intent: bool,
    mutation_intent: bool,
    semantic_mismatch: float,
) -> bool:
    """Check if a shadow policy rule matches the current context."""
    if rule.provenance_states and provenance not in rule.provenance_states:
        return False
    if rule.asset_types and asset_type not in rule.asset_types:
        return False
    if rule.trust_levels and trust_level not in rule.trust_levels:
        return False
    if rule.domain_ids and domain_id not in rule.domain_ids:
        return False
    if rule.action_categories and action_category not in rule.action_categories:
        return False
    if rule.requires_memory_write and not memory_write_intent:
        return False
    if rule.requires_mutation and not mutation_intent:
        return False
    if rule.min_semantic_mismatch > 0 and semantic_mismatch < rule.min_semantic_mismatch:
        return False
    return True


# =========================================================================
# Shadow Policy Resolver — top-level entry point
# =========================================================================


def resolve_shadow_policy(
    *,
    # Asset identity
    asset_id: str = "",
    tool_name: str = "",
    provider: str = "",
    # Registry
    registry: Optional[ShadowRegistry] = None,
    # Runtime context
    action_category: str = "unknown",
    risk_level: str = "write",
    domain_id: str = "",
    memory_write_intent: bool = False,
    mutation_intent: bool = False,
    # Semantic-governance signals
    jepa_regime: str = "normal",
    semantic_mismatch: float = 0.0,
    domain_policy_mismatch: float = 0.0,
    confidence: float = 0.5,
    # Policy rules
    rules: Optional[Sequence[ShadowPolicyRule]] = None,
) -> ShadowAssessment:
    """Top-level shadow AI policy resolver.

    Classifies provenance, computes risk, evaluates rules, and returns
    a containment posture. NEVER weakens baseline governance (stricter-only).

    Args:
        asset_id: Identity of the AI asset (tool/agent/model/endpoint).
        tool_name: Tool being invoked.
        provider: Provider/vendor name.
        registry: Shadow asset registry for sanctioned lookup.
        action_category: Runtime action category (read_only/mutating/etc).
        risk_level: Tool risk level string.
        domain_id: Current domain context.
        memory_write_intent: Whether the action intends to write memory.
        mutation_intent: Whether the action is mutating.
        jepa_regime: Current JEPA governance regime.
        semantic_mismatch: Semantic-governance mismatch score [0,1].
        domain_policy_mismatch: Domain policy mismatch score [0,1].
        confidence: Current confidence score [0,1].
        rules: Policy rules to evaluate (default: DEFAULT_SHADOW_RULES).

    Returns:
        ShadowAssessment with full provenance, risk, containment, and audit.
    """
    if rules is None:
        rules = DEFAULT_SHADOW_RULES

    reason_codes: List[str] = []
    fired_rules: List[str] = []

    # --- Step 1: Registry lookup ---
    registry_entry: Optional[ShadowRegistryEntry] = None
    lookup_key = asset_id or tool_name
    if registry is not None and lookup_key:
        registry_entry = registry.lookup_by_pattern(lookup_key)

    # --- Step 2: Determine provenance, asset type, trust level ---
    if registry_entry is not None:
        provenance = registry_entry.provenance
        asset_type = registry_entry.asset_type
        trust_level = registry_entry.trust_level
        reason_codes.append(f"REGISTRY:{registry_entry.asset_id}:{provenance.value}")

        # Check domain restrictions
        if (registry_entry.allowed_domains
                and domain_id
                and domain_id not in registry_entry.allowed_domains):
            # Approved asset used outside allowed domain
            provenance = ProvenanceStatus.SHADOW
            trust_level = ShadowTrustLevel.LIMITED
            reason_codes.append(
                f"DOMAIN_RESTRICTION:{domain_id} not in "
                f"{sorted(registry_entry.allowed_domains)}"
            )

        # Check capability restrictions
        if registry_entry.blocked_capabilities:
            if any(cap in registry_entry.blocked_capabilities
                   for cap in (action_category,)):
                reason_codes.append(
                    f"BLOCKED_CAPABILITY:{action_category}"
                )

        # Check max risk level — record for enforcement after containment init
        _max_risk_escalation: Optional[ShadowContainmentMode] = None
        if registry_entry.max_risk_level is not None:
            _RISK_ORDER = {
                "read_only": 0, "write": 1, "execute": 2,
                "destructive": 3, "privileged": 4,
            }
            if (_RISK_ORDER.get(risk_level, 5)
                    > _RISK_ORDER.get(registry_entry.max_risk_level, 0)):
                reason_codes.append(
                    f"EXCEEDS_MAX_RISK:{risk_level}>{registry_entry.max_risk_level}"
                )
                # Escalate: destructive/privileged beyond max → BLOCKED,
                # otherwise → REQUIRE_CONFIRMATION (stricter-only)
                if risk_level in ("destructive", "privileged"):
                    _max_risk_escalation = ShadowContainmentMode.BLOCKED
                else:
                    _max_risk_escalation = ShadowContainmentMode.REQUIRE_CONFIRMATION
    else:
        # Unknown asset — fail-closed classification
        asset_type, provenance, trust_level = _classify_unknown_asset(
            asset_id, tool_name, provider,
        )
        reason_codes.append(f"UNKNOWN_ASSET:{lookup_key or 'empty'}")
        _max_risk_escalation = None

    # --- Step 3: Compute risk factors ---
    risk_factors = ShadowRiskFactors(
        provenance_risk=_provenance_risk(provenance),
        identity_confidence=_trust_risk(trust_level),
        domain_mismatch=(
            1.0 if (registry_entry and registry_entry.allowed_domains
                     and domain_id
                     and domain_id not in registry_entry.allowed_domains)
            else 0.0
        ),
        action_risk=_action_risk(action_category),
        tool_risk=_tool_risk_score(risk_level),
        semantic_governance_mismatch=semantic_mismatch,
        domain_policy_mismatch=domain_policy_mismatch,
        hidden_intelligence_path=(
            0.8 if provenance == ProvenanceStatus.SHADOW else 0.0
        ),
        memory_write_risk=(
            0.9 if memory_write_intent and trust_level != ShadowTrustLevel.TRUSTED
            else 0.0
        ),
        external_side_effects=(
            0.6 if mutation_intent and provenance != ProvenanceStatus.APPROVED
            else 0.0
        ),
        execution_privilege=_tool_risk_score(risk_level),
        unexpected_usage=(
            semantic_mismatch if provenance == ProvenanceStatus.APPROVED else 0.0
        ),
    )

    # --- Step 4: Evaluate policy rules ---
    containment = ShadowContainmentMode.ALLOW
    for rule in rules:
        if _rule_matches(
            rule, provenance, asset_type, trust_level,
            domain_id, action_category,
            memory_write_intent, mutation_intent, semantic_mismatch,
        ):
            fired_rules.append(rule.name)
            reason_codes.append(f"RULE:{rule.name}:{rule.result_mode.value}")
            containment = _stricter_containment(containment, rule.result_mode)

    # --- Step 4b: Apply max_risk_level escalation (deferred from Step 2) ---
    if _max_risk_escalation is not None:
        containment = _stricter_containment(containment, _max_risk_escalation)
        fired_rules.append("_max_risk_level_enforcement")

    # --- Step 5: Semantic-governance mismatch escalation ---
    # An approved asset behaving incoherently may be shadow AI
    if (provenance == ProvenanceStatus.APPROVED
            and semantic_mismatch >= 0.4
            and containment.severity < ShadowContainmentMode.REQUIRE_CONFIRMATION.severity):
        containment = ShadowContainmentMode.REQUIRE_CONFIRMATION
        reason_codes.append(
            f"SEMANTIC_MISMATCH_ESCALATION:mismatch={semantic_mismatch:.2f}"
        )
        fired_rules.append("_semantic_mismatch_escalation")

    # --- Step 6: JEPA regime escalation ---
    if jepa_regime in ("dual_anomaly", "unknown"):
        if containment.severity < ShadowContainmentMode.QUARANTINED.severity:
            containment = ShadowContainmentMode.QUARANTINED
            reason_codes.append(f"JEPA_REGIME_ESCALATION:{jepa_regime}")
            fired_rules.append("_jepa_regime_escalation")

    # --- Step 7: Fail-closed defaults for unknown/untrusted ---
    if (provenance in (ProvenanceStatus.SHADOW, ProvenanceStatus.REVOKED)
            and containment == ShadowContainmentMode.ALLOW):
        # Shadow/revoked asset that passed all rules — still restrict
        if action_category in ("mutating", "destructive", "privileged"):
            containment = ShadowContainmentMode.BLOCKED
            reason_codes.append("FAIL_CLOSED:shadow_mutating")
        else:
            containment = ShadowContainmentMode.READ_ONLY
            reason_codes.append("FAIL_CLOSED:shadow_default_read_only")

    if (provenance == ProvenanceStatus.UNVERIFIED
            and containment == ShadowContainmentMode.ALLOW):
        if action_category in ("destructive", "privileged"):
            containment = ShadowContainmentMode.BLOCKED
            reason_codes.append("FAIL_CLOSED:unverified_dangerous")
        elif mutation_intent:
            containment = ShadowContainmentMode.REQUIRE_CONFIRMATION
            reason_codes.append("FAIL_CLOSED:unverified_mutation")

    # --- Step 8: Build rationale ---
    rationale_parts = [
        f"Asset '{lookup_key}': provenance={provenance.value}, "
        f"trust={trust_level.value}, type={asset_type.value}.",
    ]
    if fired_rules:
        rationale_parts.append(f"Rules fired: {', '.join(fired_rules)}.")
    rationale_parts.append(f"Containment: {containment.value}.")
    if risk_factors.composite_score > 0.5:
        rationale_parts.append(
            f"Risk composite: {risk_factors.composite_score:.2f} (elevated)."
        )

    shadow_overrode = containment != ShadowContainmentMode.ALLOW

    return ShadowAssessment(
        provenance_status=provenance,
        asset_type=asset_type,
        trust_level=trust_level,
        containment_mode=containment,
        risk_factors=risk_factors,
        reason_codes=tuple(reason_codes),
        rationale=" ".join(rationale_parts),
        registry_entry_id=(
            registry_entry.asset_id if registry_entry is not None else None
        ),
        shadow_overrode_baseline=shadow_overrode,
        asset_identity_summary=lookup_key or "(unknown)",
    )


# =========================================================================
# Containment → Governance Decision mapping
# =========================================================================


def resolve_shadow_asset_id(
    tool_name: str = "",
    actor_id: str = "",
) -> str:
    """Resolve the canonical asset ID for shadow registry lookup.

    Prefers tool_name (specific) over actor_id (general) to ensure
    consistent identity resolution across GovernanceService and MCP.
    """
    return tool_name.strip() or actor_id.strip() or ""


def is_memory_write_intent(
    action_type: str = "",
    tool_name: str = "",
) -> bool:
    """Detect memory-write intent from action type or tool name.

    Shared heuristic used by both GovernanceService and MCP gateway
    to ensure consistent shadow AI classification.
    """
    combined = f"{action_type} {tool_name}".lower()
    return "memory" in combined


@dataclass(frozen=True)
class ShadowGovernanceMapping:
    """Result of mapping shadow containment to a governance decision.

    Preserves the original containment mode so downstream consumers
    can differentiate between intermediate DEFER modes (e.g.,
    OBSERVE_ONLY vs REQUIRE_CONFIRMATION have different operational
    implications even though both map to DEFER).
    """
    decision: str  # "ALLOW", "DENY", or "DEFER"
    containment_mode: ShadowContainmentMode
    containment_severity: int
    constraint_hint: str  # Human-readable operational hint


_CONTAINMENT_HINTS: Dict[ShadowContainmentMode, str] = {
    ShadowContainmentMode.ALLOW: "No shadow restrictions",
    ShadowContainmentMode.OBSERVE_ONLY: "Allow but log all outputs for review",
    ShadowContainmentMode.READ_ONLY: "Permit read operations only",
    ShadowContainmentMode.DRAFT_ONLY: "Output treated as draft, not committed",
    ShadowContainmentMode.SANDBOX_ONLY: "Execute in isolated sandbox environment",
    ShadowContainmentMode.MEMORY_WRITE_DENIED: "Block all memory/state persistence",
    ShadowContainmentMode.REQUIRE_CONFIRMATION: "Require human confirmation before proceeding",
    ShadowContainmentMode.QUARANTINED: "Asset quarantined — block all actions",
    ShadowContainmentMode.BLOCKED: "Asset blocked — deny all actions",
}


def shadow_containment_to_governance(
    containment: ShadowContainmentMode,
) -> str:
    """Map shadow containment mode to APIGovernanceDecision value.

    Returns "ALLOW", "DENY", or "DEFER".
    For richer metadata, use shadow_containment_to_governance_mapping().
    """
    if containment == ShadowContainmentMode.ALLOW:
        return "ALLOW"
    if containment in (
        ShadowContainmentMode.BLOCKED,
        ShadowContainmentMode.QUARANTINED,
    ):
        return "DENY"
    # All intermediate modes map to DEFER (require human / escalate)
    return "DEFER"


def shadow_containment_to_governance_mapping(
    containment: ShadowContainmentMode,
) -> ShadowGovernanceMapping:
    """Map shadow containment to governance decision with full metadata.

    Unlike shadow_containment_to_governance() which only returns the
    decision string, this returns the original containment mode and
    operational constraint hint so callers can differentiate between
    the 6 intermediate DEFER modes.
    """
    decision = shadow_containment_to_governance(containment)
    return ShadowGovernanceMapping(
        decision=decision,
        containment_mode=containment,
        containment_severity=containment.severity,
        constraint_hint=_CONTAINMENT_HINTS.get(containment, "Unknown containment mode"),
    )
