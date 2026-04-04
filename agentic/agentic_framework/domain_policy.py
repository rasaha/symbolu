"""
Domain Semantic Policy Layer — Translates general semantic-governance
signals into domain-specific allowed behavior.

ARCHITECTURE:
    Semantic Governance Layer (ontology, vritti, JEPA composite, residual regime)
        |
        v
    Domain Semantic Policy Layer  <-- THIS MODULE
        |  - DomainProfile (declarative domain definition)
        |  - DomainActionCoherenceMatrix (regime x action_category -> mode)
        |  - DomainPolicyInterpreter (runtime translation)
        |
        v
    Execution / Runtime Enforcement Layer (GovernanceService, SafeMCPGateway)

This layer does NOT replace the semantic governor. It TRANSLATES the general
semantic-cognitive governance signals into domain-specific allowed behavior.

DESIGN PRINCIPLES:
    1. Declarative: domain profiles are data, not code
    2. Fail-closed: missing domain or missing rule -> most restrictive mode
    3. Auditable: every translation decision is traceable
    4. Domain-adaptive: same code, different behavior per domain
    5. Stricter-only: domain policy can restrict, never relax governance
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Tuple

from agentic.agentic_framework.jepa_governance import (
    GovernanceRegime,
    JEPAGovernanceAssessment,
    RuntimeActionCategory,
)

_logger = logging.getLogger(__name__)


# =========================================================================
# Enums
# =========================================================================


class DomainActionMode(enum.Enum):
    """Domain-specific allowed action modes.

    Ordered from most permissive to most restrictive.
    The integer value encodes severity for comparison.

    ENFORCEMENT TIERS — the 7 semantic modes collapse into 3 distinct
    enforcement behaviors at the execution layer:

    Tier A (ALLOW):
        ALLOW              → proceed without restriction

    Tier B (DEFER / ESCALATE):
        READ_ONLY          → block non-read tools, escalate reads
        DRAFT_ONLY         → block non-read tools, escalate reads
        CONFIRM_REQUIRED   → escalate (require human confirmation)
        SANDBOX_ONLY       → escalate (require human confirmation)
        MEMORY_WRITE_DENIED→ escalate (require human confirmation)

    Tier C (BLOCK):
        BLOCKED            → hard block, no execution

    Within Tier B, READ_ONLY and DRAFT_ONLY additionally gate on the
    tool's risk level (only READ_ONLY tools may proceed); the other
    three unconditionally escalate.  Despite the semantic distinction,
    CONFIRM_REQUIRED / SANDBOX_ONLY / MEMORY_WRITE_DENIED produce
    identical enforcement (escalate).  The semantic labels exist to
    communicate *intent* to human reviewers and audit consumers.
    """
    ALLOW = "allow"                       # 0 - proceed without restriction
    READ_ONLY = "read_only"               # 1 - only reads permitted
    DRAFT_ONLY = "draft_only"             # 2 - writes go to draft/staging
    CONFIRM_REQUIRED = "confirm_required" # 3 - human must approve
    SANDBOX_ONLY = "sandbox_only"         # 4 - execute in sandbox only
    MEMORY_WRITE_DENIED = "memory_write_denied"  # 5 - no memory persistence
    BLOCKED = "blocked"                   # 6 - hard block

    @property
    def severity(self) -> int:
        """Numeric severity for stricter-only comparison."""
        return _MODE_SEVERITY[self]

    def is_stricter_than(self, other: "DomainActionMode") -> bool:
        return self.severity > other.severity


_MODE_SEVERITY: Dict[DomainActionMode, int] = {
    DomainActionMode.ALLOW: 0,
    DomainActionMode.READ_ONLY: 1,
    DomainActionMode.DRAFT_ONLY: 2,
    DomainActionMode.CONFIRM_REQUIRED: 3,
    DomainActionMode.SANDBOX_ONLY: 4,
    DomainActionMode.MEMORY_WRITE_DENIED: 5,
    DomainActionMode.BLOCKED: 6,
}


# =========================================================================
# Domain Profile (declarative domain definition)
# =========================================================================


@dataclass(frozen=True)
class DomainToolPermission:
    """Per-tool permission override within a domain.

    Attributes:
        tool_pattern: Tool name or glob pattern (e.g. "db_*", "file_read").
        max_mode: Maximum permissive mode for this tool.
            The interpreter will never allow a mode less restrictive than this.
        requires_regime: If set, tool is only allowed in these regimes.
        blocked_in_regimes: Regimes where tool is unconditionally blocked.
    """
    tool_pattern: str
    max_mode: DomainActionMode = DomainActionMode.ALLOW
    requires_regime: FrozenSet[GovernanceRegime] = field(
        default_factory=lambda: frozenset(GovernanceRegime),
    )
    blocked_in_regimes: FrozenSet[GovernanceRegime] = field(
        default_factory=frozenset,
    )


@dataclass(frozen=True)
class DomainCoherenceRule:
    """Domain-specific coherence rule.

    Translates a combination of vritti mode + ontology position + regime
    into a domain-specific action mode.

    Attributes:
        name: Human-readable rule name for audit trail.
        vritti_modes: Vritti modes this rule applies to (empty = any).
        ontology_layers: Ontology layers this rule applies to (empty = any).
        regimes: Governance regimes this rule applies to (empty = any).
        action_categories: Runtime action categories (empty = any).
        min_confidence: Minimum confidence for rule to fire (0.0 = always).
        result_mode: The DomainActionMode to impose when rule matches.
        reason: Human-readable reason for audit.
    """
    name: str
    vritti_modes: FrozenSet[str] = field(default_factory=frozenset)
    ontology_layers: FrozenSet[str] = field(default_factory=frozenset)
    regimes: FrozenSet[GovernanceRegime] = field(default_factory=frozenset)
    action_categories: FrozenSet[RuntimeActionCategory] = field(
        default_factory=frozenset,
    )
    min_confidence: float = 0.0
    result_mode: DomainActionMode = DomainActionMode.BLOCKED
    reason: str = ""


@dataclass(frozen=True)
class DomainThresholdOverrides:
    """Domain-specific threshold overrides.

    Allows domains to set stricter (never looser) thresholds than the
    global semantic governor defaults.

    Attributes:
        alignment_critical: Override for _ALIGNMENT_CRITICAL (global=0.60).
        alignment_low: Override for _ALIGNMENT_LOW (global=0.70).
        min_confidence_for_mutating: Min confidence for mutating actions.
        min_confidence_for_destructive: Min confidence for destructive actions.
        max_residual_for_allow: Max residual magnitude to allow execution.
    """
    alignment_critical: Optional[float] = None
    alignment_low: Optional[float] = None
    min_confidence_for_mutating: Optional[float] = None
    min_confidence_for_destructive: Optional[float] = None
    max_residual_for_allow: Optional[float] = None

    def effective_alignment_critical(self, default: float = 0.60) -> float:
        if self.alignment_critical is not None:
            return max(self.alignment_critical, default)
        return default

    def effective_alignment_low(self, default: float = 0.70) -> float:
        if self.alignment_low is not None:
            return max(self.alignment_low, default)
        return default


@dataclass(frozen=True)
class DomainProfile:
    """Declarative domain profile.

    A domain profile defines how semantic-governance signals translate
    into domain-specific behavior. It is pure data — no code.

    Attributes:
        domain_id: Unique domain identifier (e.g. "finance", "devops").
        display_name: Human-readable name.
        description: What this domain covers.
        action_coherence_matrix: Regime x ActionCategory -> DomainActionMode.
        coherence_rules: Ordered list of domain coherence rules.
        tool_permissions: Per-tool permission overrides.
        thresholds: Domain-specific threshold overrides.
        default_mode: Default mode when no rule matches (fail-closed).
        blocked_action_categories: Categories always blocked in this domain.
        allowed_vritti_for_execution: Vritti modes that permit execution.
        metadata: Additional domain metadata for audit.
    """
    domain_id: str
    display_name: str
    description: str = ""
    action_coherence_matrix: Dict[
        Tuple[GovernanceRegime, RuntimeActionCategory], DomainActionMode
    ] = field(default_factory=dict)
    coherence_rules: Tuple[DomainCoherenceRule, ...] = ()
    tool_permissions: Tuple[DomainToolPermission, ...] = ()
    thresholds: DomainThresholdOverrides = field(
        default_factory=DomainThresholdOverrides,
    )
    default_mode: DomainActionMode = DomainActionMode.BLOCKED
    blocked_action_categories: FrozenSet[RuntimeActionCategory] = field(
        default_factory=frozenset,
    )
    allowed_vritti_for_execution: FrozenSet[str] = field(
        default_factory=lambda: frozenset({"pramana", "smrti"}),
    )
    metadata: Dict[str, Any] = field(default_factory=dict)


# =========================================================================
# Domain Policy Translation Result
# =========================================================================


@dataclass(frozen=True)
class DomainPolicyResult:
    """Result of domain policy translation.

    Captures the full audit trail of how semantic-governance signals
    were translated into a domain-specific action mode.

    Attributes:
        domain_id: Which domain profile was used.
        mode: The resulting domain action mode.
        matrix_mode: Mode from action coherence matrix (or None).
        rule_modes: Modes from coherence rules that fired.
        tool_mode: Mode from tool permission (or None).
        threshold_mode: Mode from threshold checks (or None).
        effective_mode: Final mode after merging all sources.
        fired_rules: Names of coherence rules that fired.
        reason_codes: Machine-readable audit codes.
        rationale: Human-readable explanation.
    """
    domain_id: str
    mode: DomainActionMode
    matrix_mode: Optional[DomainActionMode] = None
    rule_modes: Tuple[Tuple[str, DomainActionMode], ...] = ()
    tool_mode: Optional[DomainActionMode] = None
    threshold_mode: Optional[DomainActionMode] = None
    effective_mode: Optional[DomainActionMode] = None
    fired_rules: Tuple[str, ...] = ()
    reason_codes: Tuple[str, ...] = ()
    rationale: str = ""

    def to_audit_dict(self) -> Dict[str, Any]:
        """Serialize to audit-friendly dict."""
        return {
            "domain_id": self.domain_id,
            "mode": self.mode.value,
            "matrix_mode": self.matrix_mode.value if self.matrix_mode else None,
            "rule_modes": [
                {"rule": name, "mode": m.value} for name, m in self.rule_modes
            ],
            "tool_mode": self.tool_mode.value if self.tool_mode else None,
            "threshold_mode": (
                self.threshold_mode.value if self.threshold_mode else None
            ),
            "fired_rules": list(self.fired_rules),
            "reason_codes": list(self.reason_codes),
            "rationale": self.rationale,
        }


# =========================================================================
# Tool pattern matching
# =========================================================================


def _tool_matches(pattern: str, tool_name: str) -> bool:
    """Match a tool name against a pattern.

    Supports:
    - Exact match: "file_read" matches "file_read"
    - Prefix glob: "db_*" matches "db_query", "db_write"
    - Suffix glob: "*_read" matches "file_read", "db_read"
    - Universal glob: "*" matches everything
    """
    if pattern == "*":
        return True
    if pattern == tool_name:
        return True
    if pattern.endswith("*") and tool_name.startswith(pattern[:-1]):
        return True
    if pattern.startswith("*") and tool_name.endswith(pattern[1:]):
        return True
    return False


# =========================================================================
# Domain Policy Interpreter
# =========================================================================


def _stricter(a: DomainActionMode, b: DomainActionMode) -> DomainActionMode:
    """Return the stricter of two modes."""
    return a if a.severity >= b.severity else b


class DomainPolicyInterpreter:
    """Runtime interpreter that translates semantic-governance signals
    into domain-specific action modes using a DomainProfile.

    The interpreter is stateless — all state comes from the profile and
    the governance signals passed to interpret().

    Usage:
        profile = FINANCE_PROFILE
        interpreter = DomainPolicyInterpreter(profile)
        result = interpreter.interpret(jepa_assessment)
        # result.mode is the domain-specific DomainActionMode
    """

    def __init__(self, profile: DomainProfile) -> None:
        self._profile = profile
        # Pre-index tool permissions for fast lookup
        self._tool_perms: Tuple[DomainToolPermission, ...] = profile.tool_permissions

    @property
    def profile(self) -> DomainProfile:
        return self._profile

    @property
    def domain_id(self) -> str:
        return self._profile.domain_id

    def interpret(
        self,
        assessment: JEPAGovernanceAssessment,
        *,
        tool_name: str = "",
    ) -> DomainPolicyResult:
        """Translate a JEPA governance assessment into a domain-specific mode.

        Evaluation order (each can only make the result STRICTER):
        1. Action coherence matrix lookup (regime x action_category)
        2. Blocked action category check
        3. Coherence rules (ordered, all matching rules fire)
        4. Tool permission check
        5. Threshold checks (alignment, confidence, residual)
        6. Vritti execution guard
        7. Merge all modes (strictest wins)
        8. Apply domain default (fail-closed) if nothing matched

        Args:
            assessment: Full JEPA governance assessment.
            tool_name: Specific tool being invoked (for tool permissions).

        Returns:
            DomainPolicyResult with full audit trail.
        """
        regime = assessment.regime
        action_cat = assessment.runtime_state.action_category
        vritti = assessment.jepa_composite.vritti.primary_vritti
        ontology = assessment.jepa_composite.ontology.primary_layer
        confidence = assessment.jepa_composite.integrated_confidence
        alignment = assessment.jepa_composite.ontology_vritti_alignment
        residual_mag = assessment.residual.residual_magnitude

        reason_codes: List[str] = []
        fired_rules: List[str] = []
        rule_modes_list: List[Tuple[str, DomainActionMode]] = []

        # --- 1. Action coherence matrix ---
        matrix_key = (regime, action_cat)
        matrix_mode = self._profile.action_coherence_matrix.get(matrix_key)
        if matrix_mode is not None:
            reason_codes.append(
                f"MATRIX:{regime.value}:{action_cat.value}:{matrix_mode.value}"
            )

        # --- 2. Blocked action categories ---
        if action_cat in self._profile.blocked_action_categories:
            cat_mode = DomainActionMode.BLOCKED
            reason_codes.append(f"BLOCKED_CATEGORY:{action_cat.value}")
            if matrix_mode is None:
                matrix_mode = cat_mode
            else:
                matrix_mode = _stricter(matrix_mode, cat_mode)

        # --- 3. Coherence rules ---
        for rule in self._profile.coherence_rules:
            if self._rule_matches(rule, regime, action_cat, vritti,
                                   ontology, confidence):
                fired_rules.append(rule.name)
                rule_modes_list.append((rule.name, rule.result_mode))
                reason_codes.append(
                    f"RULE:{rule.name}:{rule.result_mode.value}"
                )

        # --- 4. Tool permission ---
        tool_mode = self._resolve_tool_permission(tool_name, regime)
        if tool_mode is not None:
            reason_codes.append(f"TOOL:{tool_name}:{tool_mode.value}")

        # --- 5. Threshold checks ---
        threshold_mode = self._check_thresholds(
            alignment, confidence, residual_mag, action_cat,
        )
        if threshold_mode is not None:
            reason_codes.append(f"THRESHOLD:{threshold_mode.value}")

        # --- 6. Vritti execution guard ---
        vritti_mode: Optional[DomainActionMode] = None
        if action_cat in (RuntimeActionCategory.MUTATING,
                          RuntimeActionCategory.DESTRUCTIVE,
                          RuntimeActionCategory.PRIVILEGED):
            if vritti not in self._profile.allowed_vritti_for_execution:
                vritti_mode = DomainActionMode.BLOCKED
                reason_codes.append(
                    f"VRITTI_GUARD:{vritti}:{action_cat.value}"
                )

        # --- 7. Merge all modes (strictest wins) ---
        candidates: List[DomainActionMode] = []
        if matrix_mode is not None:
            candidates.append(matrix_mode)
        for _, rm in rule_modes_list:
            candidates.append(rm)
        if tool_mode is not None:
            candidates.append(tool_mode)
        if threshold_mode is not None:
            candidates.append(threshold_mode)
        if vritti_mode is not None:
            candidates.append(vritti_mode)

        if candidates:
            effective = candidates[0]
            for c in candidates[1:]:
                effective = _stricter(effective, c)
        else:
            # --- 8. Fail-closed default ---
            effective = self._profile.default_mode
            reason_codes.append(f"DEFAULT:{effective.value}")

        # Phase S1: Nexus routing context (informational — does not change mode)
        from agentic.sovereign_constants import (
            ONTOLOGY_TO_NEXUS, NEXUS_MODE_DESCRIPTIONS,
        )
        nexus_pos = ONTOLOGY_TO_NEXUS.get(ontology, 6)
        nexus_desc = NEXUS_MODE_DESCRIPTIONS.get(nexus_pos, "unknown")
        reason_codes.append(f"NEXUS:{nexus_pos}:{nexus_desc}")

        rationale = (
            f"Domain '{self._profile.domain_id}': "
            f"regime={regime.value}, action={action_cat.value}, "
            f"vritti={vritti}, ontology={ontology}, nexus={nexus_desc} -> "
            f"mode={effective.value}. "
            f"Rules fired: {fired_rules or 'none'}."
        )

        return DomainPolicyResult(
            domain_id=self._profile.domain_id,
            mode=effective,
            matrix_mode=matrix_mode,
            rule_modes=tuple(rule_modes_list),
            tool_mode=tool_mode,
            threshold_mode=threshold_mode,
            effective_mode=effective,
            fired_rules=tuple(fired_rules),
            reason_codes=tuple(reason_codes),
            rationale=rationale,
        )

    def _rule_matches(
        self,
        rule: DomainCoherenceRule,
        regime: GovernanceRegime,
        action_cat: RuntimeActionCategory,
        vritti: str,
        ontology: str,
        confidence: float,
    ) -> bool:
        """Check if a coherence rule matches the current state."""
        if rule.regimes and regime not in rule.regimes:
            return False
        if rule.action_categories and action_cat not in rule.action_categories:
            return False
        if rule.vritti_modes and vritti not in rule.vritti_modes:
            return False
        if rule.ontology_layers and ontology not in rule.ontology_layers:
            return False
        if confidence < rule.min_confidence:
            return False
        return True

    def _resolve_tool_permission(
        self,
        tool_name: str,
        regime: GovernanceRegime,
    ) -> Optional[DomainActionMode]:
        """Resolve tool permission for the given tool and regime.

        Uses most-restrictive-match semantics: ALL matching patterns are
        evaluated and the strictest result wins.  This prevents broad
        patterns (e.g. ``file_*`` ALLOW) from shadowing narrow block
        patterns (e.g. ``file_delete`` BLOCKED).
        """
        if not tool_name:
            return None
        result: Optional[DomainActionMode] = None
        for perm in self._tool_perms:
            if _tool_matches(perm.tool_pattern, tool_name):
                # Determine mode for this matching permission
                if regime in perm.blocked_in_regimes:
                    mode = DomainActionMode.BLOCKED
                elif perm.requires_regime and regime not in perm.requires_regime:
                    mode = DomainActionMode.BLOCKED
                else:
                    mode = perm.max_mode
                # Merge: strictest wins
                result = _stricter(result, mode) if result is not None else mode
        return result

    def _check_thresholds(
        self,
        alignment: float,
        confidence: float,
        residual_magnitude: float,
        action_cat: RuntimeActionCategory,
    ) -> Optional[DomainActionMode]:
        """Check domain threshold overrides."""
        t = self._profile.thresholds
        modes: List[DomainActionMode] = []

        # Alignment critical check
        crit = t.effective_alignment_critical()
        if alignment < crit:
            modes.append(DomainActionMode.BLOCKED)

        # Alignment low check
        low = t.effective_alignment_low()
        if alignment < low and not modes:
            modes.append(DomainActionMode.CONFIRM_REQUIRED)

        # Confidence for mutating
        if (action_cat == RuntimeActionCategory.MUTATING
                and t.min_confidence_for_mutating is not None
                and confidence < t.min_confidence_for_mutating):
            modes.append(DomainActionMode.CONFIRM_REQUIRED)

        # Confidence for destructive
        if (action_cat == RuntimeActionCategory.DESTRUCTIVE
                and t.min_confidence_for_destructive is not None
                and confidence < t.min_confidence_for_destructive):
            modes.append(DomainActionMode.BLOCKED)

        # Max residual for allow
        if (t.max_residual_for_allow is not None
                and residual_magnitude > t.max_residual_for_allow):
            modes.append(DomainActionMode.CONFIRM_REQUIRED)

        if not modes:
            return None
        result = modes[0]
        for m in modes[1:]:
            result = _stricter(result, m)
        return result


# =========================================================================
# Domain Registry
# =========================================================================


class DomainRegistry:
    """Registry of available domain profiles.

    Thread-safe for read access after initial registration.
    The registry enforces that domain_id is unique.
    """

    def __init__(self) -> None:
        self._profiles: Dict[str, DomainProfile] = {}

    def register(self, profile: DomainProfile) -> None:
        """Register a domain profile. Raises ValueError on duplicate."""
        if profile.domain_id in self._profiles:
            raise ValueError(
                f"Domain '{profile.domain_id}' is already registered"
            )
        self._profiles[profile.domain_id] = profile

    def get(self, domain_id: str) -> Optional[DomainProfile]:
        """Get a profile by domain_id, or None if not found."""
        return self._profiles.get(domain_id)

    def get_or_raise(self, domain_id: str) -> DomainProfile:
        """Get a profile or raise KeyError."""
        profile = self._profiles.get(domain_id)
        if profile is None:
            raise KeyError(f"Domain '{domain_id}' not registered")
        return profile

    def list_domains(self) -> List[str]:
        """Return sorted list of registered domain IDs."""
        return sorted(self._profiles.keys())

    def interpreter_for(self, domain_id: str) -> DomainPolicyInterpreter:
        """Create an interpreter for the given domain."""
        return DomainPolicyInterpreter(self.get_or_raise(domain_id))

    def __contains__(self, domain_id: str) -> bool:
        return domain_id in self._profiles

    def __len__(self) -> int:
        return len(self._profiles)


# =========================================================================
# Fail-closed helper
# =========================================================================


def fail_closed_result(
    domain_id: str = "__unknown__",
    reason: str = "No domain profile available",
) -> DomainPolicyResult:
    """Return a fail-closed BLOCKED result when no domain is available."""
    return DomainPolicyResult(
        domain_id=domain_id,
        mode=DomainActionMode.BLOCKED,
        reason_codes=("DOMAIN_UNAVAILABLE",),
        rationale=f"Fail-closed: {reason}",
    )


# =========================================================================
# Governance integration helper
# =========================================================================


def resolve_domain_policy(
    assessment: JEPAGovernanceAssessment,
    registry: DomainRegistry,
    domain_id: str,
    *,
    tool_name: str = "",
) -> DomainPolicyResult:
    """Top-level entry point for domain policy resolution.

    Used by GovernanceService and SafeMCPGateway to translate
    a JEPA assessment into a domain-specific action mode.

    Fail-closed: if domain_id is not registered or interpretation
    fails, returns BLOCKED.

    Args:
        assessment: Full JEPA governance assessment.
        registry: Domain registry to look up the profile.
        domain_id: Which domain to use.
        tool_name: Tool being invoked (for tool permissions).

    Returns:
        DomainPolicyResult — always. Never raises.
    """
    try:
        profile = registry.get(domain_id)
        if profile is None:
            return fail_closed_result(
                domain_id, f"Domain '{domain_id}' not registered"
            )
        interpreter = DomainPolicyInterpreter(profile)
        return interpreter.interpret(assessment, tool_name=tool_name)
    except Exception as e:
        _logger.error(
            "Domain policy resolution failed for '%s': %s",
            domain_id, e,
        )
        return fail_closed_result(domain_id, str(e))


# =========================================================================
# Example Domain Profiles
# =========================================================================

# Shorthand aliases for readability
_N = GovernanceRegime.NORMAL
_PD = GovernanceRegime.PROCESS_DRIFT
_SS = GovernanceRegime.SEMANTIC_SHIFT
_DA = GovernanceRegime.DUAL_ANOMALY
_UK = GovernanceRegime.UNKNOWN
_RO = RuntimeActionCategory.READ_ONLY
_MU = RuntimeActionCategory.MUTATING
_DE = RuntimeActionCategory.DESTRUCTIVE
_PR = RuntimeActionCategory.PRIVILEGED
_UNK = RuntimeActionCategory.UNKNOWN

_AM = DomainActionMode


# --- Finance Domain Profile ---

FINANCE_PROFILE = DomainProfile(
    domain_id="finance",
    display_name="Financial Services",
    description=(
        "High-security domain for financial operations. "
        "Destructive/privileged actions always require confirmation. "
        "Process drift blocks all writes. Semantic shift blocks everything."
    ),
    action_coherence_matrix={
        # NORMAL: reads OK, mutating needs confirmation, destructive blocked
        (_N, _RO): _AM.ALLOW,
        (_N, _MU): _AM.CONFIRM_REQUIRED,
        (_N, _DE): _AM.BLOCKED,
        (_N, _PR): _AM.BLOCKED,
        (_N, _UNK): _AM.BLOCKED,
        # PROCESS_DRIFT: reads only, everything else blocked
        (_PD, _RO): _AM.READ_ONLY,
        (_PD, _MU): _AM.BLOCKED,
        (_PD, _DE): _AM.BLOCKED,
        (_PD, _PR): _AM.BLOCKED,
        (_PD, _UNK): _AM.BLOCKED,
        # SEMANTIC_SHIFT / DUAL_ANOMALY / UNKNOWN: all blocked
        (_SS, _RO): _AM.BLOCKED,
        (_SS, _MU): _AM.BLOCKED,
        (_SS, _DE): _AM.BLOCKED,
        (_SS, _PR): _AM.BLOCKED,
        (_SS, _UNK): _AM.BLOCKED,
        (_DA, _RO): _AM.BLOCKED,
        (_DA, _MU): _AM.BLOCKED,
        (_DA, _DE): _AM.BLOCKED,
        (_DA, _PR): _AM.BLOCKED,
        (_DA, _UNK): _AM.BLOCKED,
        (_UK, _RO): _AM.BLOCKED,
        (_UK, _MU): _AM.BLOCKED,
        (_UK, _DE): _AM.BLOCKED,
        (_UK, _PR): _AM.BLOCKED,
        (_UK, _UNK): _AM.BLOCKED,
    },
    coherence_rules=(
        DomainCoherenceRule(
            name="finance_misperception_guard",
            vritti_modes=frozenset({"viparyaya"}),
            result_mode=_AM.BLOCKED,
            reason="Misperception (viparyaya) in financial domain -> block all",
        ),
        DomainCoherenceRule(
            name="finance_dormancy_guard",
            vritti_modes=frozenset({"nidra"}),
            action_categories=frozenset({_MU, _DE, _PR}),
            result_mode=_AM.BLOCKED,
            reason="Dormancy (nidra) with write action in finance -> block",
        ),
        DomainCoherenceRule(
            name="finance_low_confidence_write",
            action_categories=frozenset({_MU}),
            min_confidence=0.7,
            result_mode=_AM.ALLOW,  # Only fires at high confidence
            reason="Mutating allowed only above 0.7 confidence in finance",
        ),
    ),
    tool_permissions=(
        DomainToolPermission(
            tool_pattern="ledger_*",
            max_mode=_AM.CONFIRM_REQUIRED,
            blocked_in_regimes=frozenset({_PD, _SS, _DA, _UK}),
        ),
        DomainToolPermission(
            tool_pattern="payment_*",
            max_mode=_AM.CONFIRM_REQUIRED,
            blocked_in_regimes=frozenset({_PD, _SS, _DA, _UK}),
        ),
        DomainToolPermission(
            tool_pattern="audit_*",
            max_mode=_AM.READ_ONLY,
        ),
    ),
    thresholds=DomainThresholdOverrides(
        alignment_critical=0.70,
        alignment_low=0.80,
        min_confidence_for_mutating=0.70,
        min_confidence_for_destructive=0.95,
        max_residual_for_allow=0.30,
    ),
    default_mode=_AM.BLOCKED,
    blocked_action_categories=frozenset({_DE, _PR}),
    allowed_vritti_for_execution=frozenset({"pramana"}),
)


# --- Coding / DevOps Domain Profile ---

DEVOPS_PROFILE = DomainProfile(
    domain_id="devops",
    display_name="Coding & DevOps",
    description=(
        "Development domain. More permissive for reads and code writes. "
        "Destructive actions (delete repo, drop DB) need confirmation. "
        "Privileged actions (deploy, infra changes) need confirmation."
    ),
    action_coherence_matrix={
        # NORMAL: reads and writes OK, destructive/privileged need confirm
        (_N, _RO): _AM.ALLOW,
        (_N, _MU): _AM.ALLOW,
        (_N, _DE): _AM.CONFIRM_REQUIRED,
        (_N, _PR): _AM.CONFIRM_REQUIRED,
        (_N, _UNK): _AM.CONFIRM_REQUIRED,
        # PROCESS_DRIFT: reads OK, writes draft-only, rest blocked
        (_PD, _RO): _AM.ALLOW,
        (_PD, _MU): _AM.DRAFT_ONLY,
        (_PD, _DE): _AM.BLOCKED,
        (_PD, _PR): _AM.BLOCKED,
        (_PD, _UNK): _AM.BLOCKED,
        # SEMANTIC_SHIFT: read-only
        (_SS, _RO): _AM.READ_ONLY,
        (_SS, _MU): _AM.CONFIRM_REQUIRED,
        (_SS, _DE): _AM.BLOCKED,
        (_SS, _PR): _AM.BLOCKED,
        (_SS, _UNK): _AM.BLOCKED,
        # DUAL_ANOMALY / UNKNOWN: blocked
        (_DA, _RO): _AM.CONFIRM_REQUIRED,
        (_DA, _MU): _AM.BLOCKED,
        (_DA, _DE): _AM.BLOCKED,
        (_DA, _PR): _AM.BLOCKED,
        (_DA, _UNK): _AM.BLOCKED,
        (_UK, _RO): _AM.CONFIRM_REQUIRED,
        (_UK, _MU): _AM.BLOCKED,
        (_UK, _DE): _AM.BLOCKED,
        (_UK, _PR): _AM.BLOCKED,
        (_UK, _UNK): _AM.BLOCKED,
    },
    coherence_rules=(
        DomainCoherenceRule(
            name="devops_sandbox_destructive",
            action_categories=frozenset({_DE}),
            regimes=frozenset({_N}),
            result_mode=_AM.SANDBOX_ONLY,
            reason="Destructive actions in devops go to sandbox first",
        ),
        DomainCoherenceRule(
            name="devops_dormancy_guard",
            vritti_modes=frozenset({"nidra"}),
            action_categories=frozenset({_MU, _DE, _PR}),
            result_mode=_AM.CONFIRM_REQUIRED,
            reason="Dormancy in devops needs human confirmation for writes",
        ),
    ),
    tool_permissions=(
        DomainToolPermission(
            tool_pattern="git_*",
            max_mode=_AM.ALLOW,
            blocked_in_regimes=frozenset({_DA, _UK}),
        ),
        DomainToolPermission(
            tool_pattern="deploy_*",
            max_mode=_AM.CONFIRM_REQUIRED,
            blocked_in_regimes=frozenset({_PD, _SS, _DA, _UK}),
        ),
        DomainToolPermission(
            tool_pattern="file_*",
            max_mode=_AM.ALLOW,
        ),
        DomainToolPermission(
            tool_pattern="db_drop*",
            max_mode=_AM.BLOCKED,
        ),
    ),
    thresholds=DomainThresholdOverrides(
        min_confidence_for_destructive=0.80,
        max_residual_for_allow=0.50,
    ),
    default_mode=_AM.CONFIRM_REQUIRED,
    allowed_vritti_for_execution=frozenset({"pramana", "smrti"}),
)


# --- Research / Customer Support Domain Profile ---

RESEARCH_PROFILE = DomainProfile(
    domain_id="research",
    display_name="Research & Customer Support",
    description=(
        "Read-heavy domain for research, analysis, and customer support. "
        "Very permissive for reads. Writes go to draft. "
        "No destructive or privileged operations."
    ),
    action_coherence_matrix={
        # NORMAL: reads OK, writes draft-only
        (_N, _RO): _AM.ALLOW,
        (_N, _MU): _AM.DRAFT_ONLY,
        (_N, _DE): _AM.BLOCKED,
        (_N, _PR): _AM.BLOCKED,
        (_N, _UNK): _AM.CONFIRM_REQUIRED,
        # PROCESS_DRIFT: reads OK, writes need confirmation
        (_PD, _RO): _AM.ALLOW,
        (_PD, _MU): _AM.CONFIRM_REQUIRED,
        (_PD, _DE): _AM.BLOCKED,
        (_PD, _PR): _AM.BLOCKED,
        (_PD, _UNK): _AM.BLOCKED,
        # SEMANTIC_SHIFT: reads escalated, rest blocked
        (_SS, _RO): _AM.CONFIRM_REQUIRED,
        (_SS, _MU): _AM.BLOCKED,
        (_SS, _DE): _AM.BLOCKED,
        (_SS, _PR): _AM.BLOCKED,
        (_SS, _UNK): _AM.BLOCKED,
        # DUAL_ANOMALY / UNKNOWN: all blocked
        (_DA, _RO): _AM.BLOCKED,
        (_DA, _MU): _AM.BLOCKED,
        (_DA, _DE): _AM.BLOCKED,
        (_DA, _PR): _AM.BLOCKED,
        (_DA, _UNK): _AM.BLOCKED,
        (_UK, _RO): _AM.BLOCKED,
        (_UK, _MU): _AM.BLOCKED,
        (_UK, _DE): _AM.BLOCKED,
        (_UK, _PR): _AM.BLOCKED,
        (_UK, _UNK): _AM.BLOCKED,
    },
    coherence_rules=(
        DomainCoherenceRule(
            name="research_vikalpa_creative",
            vritti_modes=frozenset({"vikalpa"}),
            action_categories=frozenset({_RO}),
            regimes=frozenset({_N}),
            result_mode=_AM.ALLOW,
            reason="Conceptual mode (vikalpa) is fine for research reads",
        ),
        DomainCoherenceRule(
            name="research_memory_deny_on_drift",
            regimes=frozenset({_PD, _SS}),
            result_mode=_AM.MEMORY_WRITE_DENIED,
            reason="No memory writes during drift/shift in research domain",
        ),
    ),
    tool_permissions=(
        DomainToolPermission(
            tool_pattern="search_*",
            max_mode=_AM.ALLOW,
        ),
        DomainToolPermission(
            tool_pattern="knowledge_*",
            max_mode=_AM.ALLOW,
        ),
        DomainToolPermission(
            tool_pattern="ticket_*",
            max_mode=_AM.DRAFT_ONLY,
            blocked_in_regimes=frozenset({_DA, _UK}),
        ),
    ),
    thresholds=DomainThresholdOverrides(
        max_residual_for_allow=0.40,
    ),
    default_mode=_AM.CONFIRM_REQUIRED,
    blocked_action_categories=frozenset({_DE, _PR}),
    allowed_vritti_for_execution=frozenset({"pramana", "smrti", "vikalpa"}),
)


# =========================================================================
# Default registry with built-in profiles
# =========================================================================


def create_default_registry() -> DomainRegistry:
    """Create a registry pre-loaded with the built-in domain profiles."""
    reg = DomainRegistry()
    reg.register(FINANCE_PROFILE)
    reg.register(DEVOPS_PROFILE)
    reg.register(RESEARCH_PROFILE)
    return reg


# =========================================================================
# Exports
# =========================================================================

__all__ = [
    # Enums
    "DomainActionMode",
    # Data structures
    "DomainToolPermission",
    "DomainCoherenceRule",
    "DomainThresholdOverrides",
    "DomainProfile",
    "DomainPolicyResult",
    # Interpreter
    "DomainPolicyInterpreter",
    # Registry
    "DomainRegistry",
    # Top-level entry points
    "resolve_domain_policy",
    "fail_closed_result",
    "create_default_registry",
    # Built-in profiles
    "FINANCE_PROFILE",
    "DEVOPS_PROFILE",
    "RESEARCH_PROFILE",
    # Helpers
    "_tool_matches",
    "_stricter",
]
