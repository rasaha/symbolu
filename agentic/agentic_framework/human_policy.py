"""
Human-Curated Policy Layer — deterministic, author-controlled governance verdicts.

WHY THIS EXISTS
    The ActionGate decision core (``governance_service.GovernanceService``)
    derives its ALLOW / DENY / DEFER verdict from *LLM-produced* signals —
    quality/coherence/consistency/alignment scores fed through the
    ConfidenceGate, SafetyContract preconditions, and the JEPA latent-state
    assessment.  Those signals are probabilistic and model-authored.

    Many deployments need governance decisions that come from an explicit,
    *human-curated* policy instead: "an agent may never delete the last
    replica of a database", "any destructive action requires dual-control
    approval", "actor X may read-only in namespace Y".  These are rules a
    security owner writes and signs, not judgements an LLM makes.

    This module adds that path.  It is a pure, deterministic, stdlib-only
    rule engine (same spirit as ``safety.governance_patterns.policy_engine``
    and the frozen ``action_gate_ref.policy`` ruleset) that evaluates a
    proposed action against a curated ``HumanPolicyBook`` and returns a
    verdict.

AUTHORITY MODEL — "human sets the baseline, the LLM can only tighten"
    When a human rule matches a request, its verdict becomes the *baseline*
    governance decision.  Every downstream layer in GovernanceService
    (ConfidenceGate, JEPA, domain policy, shadow AI, generation gate, agent
    policy engine) is already **stricter-only**: it can escalate or deny, but
    never loosen.  So the composed decision is::

        final = stricter_of( human_baseline , llm_and_signal_tightening )

    Consequences:
      * An explicit human ``DENY`` is dispositive — nothing downstream can
        loosen it.
      * A human ``REQUIRE_APPROVAL`` forces at least ``DEFER`` (human
        confirmation) even if the LLM was fully confident.
      * A human ``ALLOW`` is a *ceiling of permissiveness*: the action may
        still be denied/deferred by the LLM/JEPA/domain overlays if they are
        stricter, but a low-confidence LLM signal can never turn a
        human-forbidden action into an allowed one.
      * When **no** rule matches, this layer is silent and the existing
        LLM-derived baseline is used unchanged (fully backward-compatible).

FAIL-CLOSED
    A configured-but-failing policy book resolves to ``DENY`` with a
    ``HUMAN_POLICY_ERROR`` reason code rather than silently falling back to
    the LLM.  An *absent* book is not an error — it resolves to "no match"
    (no effect).

DETERMINISM
    Evaluation is a pure function of (request attributes, classified risk,
    declared facts, book).  No wall-clock, no randomness.  The book has a
    stable content hash / ``policy_version`` so decisions are auditable and
    reproducible, mirroring ``action_gate_ref.policy``.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

SCHEMA_VERSION = "1.0.0"


# =============================================================================
# Verdict
# =============================================================================


class HumanPolicyVerdict(str, Enum):
    """Verdict a curated rule can assign to a matching action.

    Ordered by restrictiveness (see ``_VERDICT_SEVERITY``): DENY is the most
    restrictive, ALLOW the least.
    """

    ALLOW = "ALLOW"
    ALLOW_WITH_CONSTRAINTS = "ALLOW_WITH_CONSTRAINTS"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    DENY = "DENY"


class HumanPolicyMode(str, Enum):
    """How a matched human verdict relates to the LLM/model-derived decision.

    BASELINE
        "Human sets the baseline, the LLM can only tighten."  A matched human
        verdict is the baseline; the LLM/JEPA/domain/shadow overlays are
        stricter-only, so the composed decision is the MORE RESTRICTIVE of the
        human baseline and the model decision.  A human ALLOW is therefore a
        permissiveness ceiling the model may still tighten to DEFER/DENY.

    SOURCE_OF_TRUTH
        "Humans are the source of truth."  A matched human verdict is
        DISPOSITIVE: the LLM/model-derived governance layers are advisory and
        cannot change it — a human ALLOW stays ALLOW even if the model would
        have deferred/denied.  It remains subject only to the independent
        fail-closed hard blocks that are themselves human-configured, not LLM
        judgements (forbidden capability, agent PolicyEngine hard-deny, and the
        generation gate).  When no human rule matches, the normal model
        pipeline decides (identical to BASELINE on a no-match).
    """

    BASELINE = "baseline"
    SOURCE_OF_TRUTH = "source_of_truth"


# Higher number == more restrictive.  Used for "most-restrictive-rule-wins".
_VERDICT_SEVERITY: Dict[HumanPolicyVerdict, int] = {
    HumanPolicyVerdict.ALLOW: 0,
    HumanPolicyVerdict.ALLOW_WITH_CONSTRAINTS: 1,
    HumanPolicyVerdict.REQUIRE_APPROVAL: 2,
    HumanPolicyVerdict.DENY: 3,
}

# Verdict -> top-level governance decision string (matches APIGovernanceDecision).
_VERDICT_TO_DECISION: Dict[HumanPolicyVerdict, str] = {
    HumanPolicyVerdict.ALLOW: "ALLOW",
    HumanPolicyVerdict.ALLOW_WITH_CONSTRAINTS: "ALLOW",
    HumanPolicyVerdict.REQUIRE_APPROVAL: "DEFER",
    HumanPolicyVerdict.DENY: "DENY",
}


def verdict_severity(verdict: HumanPolicyVerdict) -> int:
    """Return the restrictiveness rank of *verdict* (higher == stricter)."""
    return _VERDICT_SEVERITY[verdict]


# =============================================================================
# Action-criticality classification (human-authored)
# =============================================================================


class CriticalityClass(str, Enum):
    """Human-authored criticality of an action class.

    CRITICAL      → decisions default to SOURCE_OF_TRUTH (human dispositive).
    NON_CRITICAL  → decisions default to BASELINE (model may tighten).
    UNKNOWN       → not classified; handled conservatively per the registry's
                    ``uncertain_disposition``.
    """

    CRITICAL = "critical"
    NON_CRITICAL = "non_critical"
    UNKNOWN = "unknown"


class UncertainDisposition(str, Enum):
    """How to handle an action whose criticality the registry cannot classify.

    REQUIRE_APPROVAL
        Conservative default — force at least DEFER (human confirmation) and
        resolve the authority mode to SOURCE_OF_TRUTH so the model cannot loosen
        that floor.  Safe regardless of what the matched verdict says (a broad
        ALLOW does not silently pass on an unclassified action).

    TREAT_AS_CRITICAL
        Treat the action as CRITICAL — resolve to SOURCE_OF_TRUTH and let the
        matched human verdict stand (no forced approval floor).
    """

    REQUIRE_APPROVAL = "require_approval"
    TREAT_AS_CRITICAL = "treat_as_critical"


@dataclass(frozen=True)
class ActionCriticalityRegistry:
    """Human-authored classification of action classes into criticality.

    Classification is **deterministic** and derived only from human-configured
    class membership plus caller-declared deterministic impact facts.  The LLM
    that produces the governance verdict has NO input here, so it can never
    downgrade an action's criticality; deterministic impact facts may only
    PROMOTE an action to CRITICAL.

    Membership is checked in this order (promotion wins):
      1. any ``critical_promoting_facts`` truthy in the request facts → CRITICAL;
      2. ``critical_*`` class membership (risk level / action type / tool) → CRITICAL;
      3. otherwise ``non_critical_*`` membership → NON_CRITICAL;
      4. otherwise → UNKNOWN (handled per ``uncertain_disposition``).
    """

    critical_risk_levels: Tuple[str, ...] = ("destructive", "privileged")
    non_critical_risk_levels: Tuple[str, ...] = ("read_only",)
    critical_action_types: Tuple[str, ...] = ()
    non_critical_action_types: Tuple[str, ...] = ()
    critical_tools: Tuple[str, ...] = ()
    non_critical_tools: Tuple[str, ...] = ()
    # Deterministic impact facts that PROMOTE an action to critical (never demote).
    critical_promoting_facts: Tuple[str, ...] = (
        "last_replica", "irreversible", "bulk", "public_sensitive",
    )
    uncertain_disposition: UncertainDisposition = UncertainDisposition.REQUIRE_APPROVAL

    def classify(self, ctx: "RequestContext") -> Tuple[CriticalityClass, Tuple[str, ...]]:
        """Return ``(criticality, basis)`` for *ctx* (deterministic)."""
        basis: List[str] = []

        # 1. Deterministic impact promotion (facts) — always wins.
        promoted = False
        for fact in self.critical_promoting_facts:
            if _fact_truthy(ctx.facts, fact):
                promoted = True
                basis.append(f"promoted:fact:{fact}")

        # 2. Critical class membership.
        if ctx.risk_level in self.critical_risk_levels:
            promoted = True
            basis.append(f"critical:risk_level:{ctx.risk_level}")
        if ctx.action_type in self.critical_action_types:
            promoted = True
            basis.append(f"critical:action_type:{ctx.action_type}")
        if ctx.tool_name and ctx.tool_name in self.critical_tools:
            promoted = True
            basis.append(f"critical:tool:{ctx.tool_name}")
        if promoted:
            return CriticalityClass.CRITICAL, tuple(basis)

        # 3. Non-critical class membership.
        noncrit = False
        if ctx.risk_level in self.non_critical_risk_levels:
            noncrit = True
            basis.append(f"non_critical:risk_level:{ctx.risk_level}")
        if ctx.action_type in self.non_critical_action_types:
            noncrit = True
            basis.append(f"non_critical:action_type:{ctx.action_type}")
        if ctx.tool_name and ctx.tool_name in self.non_critical_tools:
            noncrit = True
            basis.append(f"non_critical:tool:{ctx.tool_name}")
        if noncrit:
            return CriticalityClass.NON_CRITICAL, tuple(basis)

        # 4. Unclassified.
        return CriticalityClass.UNKNOWN, ("unclassified",)

    def default_mode(self, criticality: CriticalityClass) -> HumanPolicyMode:
        """Authority mode a criticality class maps to (audit/transparency)."""
        if criticality == CriticalityClass.NON_CRITICAL:
            return HumanPolicyMode.BASELINE
        # CRITICAL and UNKNOWN both resolve to SOURCE_OF_TRUTH (conservative).
        return HumanPolicyMode.SOURCE_OF_TRUTH


@dataclass(frozen=True)
class AuthorityModeResolution:
    """Result of resolving the per-decision authority mode."""

    effective_mode: HumanPolicyMode
    source: str  # rule_explicit | criticality_registry | uncertain_conservative | engine_default
    criticality: CriticalityClass
    criticality_basis: Tuple[str, ...]
    criticality_mode: Optional[HumanPolicyMode]  # mode implied by criticality (pre-override)
    rule_authority_mode: Optional[HumanPolicyMode]
    conservative_floor: Optional[str]  # e.g. "DEFER" when uncertain forces approval


def resolve_authority_mode(
    *,
    rule: "HumanPolicyRule",
    registry: Optional[ActionCriticalityRegistry],
    engine_default: HumanPolicyMode,
    ctx: "RequestContext",
) -> AuthorityModeResolution:
    """Resolve the authority mode for a matched rule, by precedence:

    1. explicit ``authority_mode`` on the matched rule;
    2. human-authored criticality registry default;
    3. engine/service default (backward compatibility).

    Unknown/uncertain criticality is handled conservatively per the registry's
    ``uncertain_disposition``.
    """
    criticality = CriticalityClass.UNKNOWN
    basis: Tuple[str, ...] = ()
    criticality_mode: Optional[HumanPolicyMode] = None
    if registry is not None:
        criticality, basis = registry.classify(ctx)
        criticality_mode = registry.default_mode(criticality)

    # Precedence 1: explicit per-rule mode.
    if rule.authority_mode is not None:
        return AuthorityModeResolution(
            effective_mode=rule.authority_mode,
            source="rule_explicit",
            criticality=criticality,
            criticality_basis=basis,
            criticality_mode=criticality_mode,
            rule_authority_mode=rule.authority_mode,
            conservative_floor=None,
        )

    # Precedence 2: criticality registry.
    if registry is not None:
        if criticality == CriticalityClass.CRITICAL:
            return AuthorityModeResolution(
                effective_mode=HumanPolicyMode.SOURCE_OF_TRUTH,
                source="criticality_registry", criticality=criticality,
                criticality_basis=basis, criticality_mode=criticality_mode,
                rule_authority_mode=None, conservative_floor=None)
        if criticality == CriticalityClass.NON_CRITICAL:
            return AuthorityModeResolution(
                effective_mode=HumanPolicyMode.BASELINE,
                source="criticality_registry", criticality=criticality,
                criticality_basis=basis, criticality_mode=criticality_mode,
                rule_authority_mode=None, conservative_floor=None)
        # UNKNOWN → conservative.
        floor = (
            "DEFER"
            if registry.uncertain_disposition == UncertainDisposition.REQUIRE_APPROVAL
            else None
        )
        return AuthorityModeResolution(
            effective_mode=HumanPolicyMode.SOURCE_OF_TRUTH,
            source="uncertain_conservative", criticality=criticality,
            criticality_basis=basis, criticality_mode=criticality_mode,
            rule_authority_mode=None, conservative_floor=floor)

    # Precedence 3: engine/service default.
    return AuthorityModeResolution(
        effective_mode=engine_default, source="engine_default",
        criticality=criticality, criticality_basis=basis,
        criticality_mode=criticality_mode, rule_authority_mode=None,
        conservative_floor=None)


# =============================================================================
# Rule
# =============================================================================


@dataclass(frozen=True)
class HumanPolicyRule:
    """One human-authored governance rule.

    A rule *matches* a request when **every** non-empty criterion below is
    satisfied.  An empty criterion is a wildcard (matches anything).  This is
    intentionally conjunctive so that broad rules are explicit and narrow
    rules stay predictable.

    Match criteria
    --------------
    action_types      : request.action_type must equal one of these.
    tool_names        : request.tool_name must equal one of these.
    risk_levels       : the classified risk level must be one of these
                        (read_only / write / execute / destructive / privileged).
    actor_ids         : request.actor_id must equal one of these.
    agency_levels     : request.agency_level must be one of these.
    capabilities_any  : request.capabilities must intersect this set.
    target_patterns   : at least one regex must search-match the request's
                        target haystack (tool/action/target/params).
    when_facts        : every named fact must be truthy in the request facts.
    unless_facts      : no named fact may be truthy in the request facts.

    Outputs
    -------
    verdict           : the decision this rule asserts on a match.
    constraints       : conditions attached to an ALLOW_WITH_CONSTRAINTS
                        verdict (recorded, surfaced to the caller/audit).
    approver_policy   : e.g. "dual_control" / "single" for REQUIRE_APPROVAL.
    priority          : higher priority rules win selection ties and can
                        override a more-restrictive lower-priority rule
                        (this is how an ALLOW *exception* to a broad DENY is
                        expressed).  Default 0.
    description       : human-readable rationale for audit.
    """

    rule_id: str
    verdict: HumanPolicyVerdict

    action_types: Tuple[str, ...] = ()
    tool_names: Tuple[str, ...] = ()
    risk_levels: Tuple[str, ...] = ()
    actor_ids: Tuple[str, ...] = ()
    agency_levels: Tuple[str, ...] = ()
    capabilities_any: Tuple[str, ...] = ()
    target_patterns: Tuple[str, ...] = ()
    when_facts: Tuple[str, ...] = ()
    unless_facts: Tuple[str, ...] = ()

    constraints: Mapping[str, Any] = field(default_factory=dict)
    approver_policy: str = ""
    priority: int = 0
    description: str = ""
    # Optional explicit authority mode for this rule — precedence #1 in
    # per-decision mode resolution (a human's deliberate per-rule override,
    # e.g. promoting an otherwise non-critical action to SOURCE_OF_TRUTH).
    authority_mode: Optional[HumanPolicyMode] = None

    def matches(self, ctx: "RequestContext") -> bool:
        """Return True if this rule applies to *ctx* (conjunctive match)."""
        if self.action_types and ctx.action_type not in self.action_types:
            return False
        if self.tool_names and (ctx.tool_name or "") not in self.tool_names:
            return False
        if self.risk_levels and ctx.risk_level not in self.risk_levels:
            return False
        if self.actor_ids and ctx.actor_id not in self.actor_ids:
            return False
        if self.agency_levels and ctx.agency_level not in self.agency_levels:
            return False
        if self.capabilities_any and not (
            set(self.capabilities_any) & set(ctx.capabilities)
        ):
            return False
        if self.target_patterns and not any(
            re.search(pat, ctx.target_haystack) for pat in self.target_patterns
        ):
            return False
        if self.when_facts and not all(
            _fact_truthy(ctx.facts, name) for name in self.when_facts
        ):
            return False
        if self.unless_facts and any(
            _fact_truthy(ctx.facts, name) for name in self.unless_facts
        ):
            return False
        return True

    def to_canonical(self) -> Dict[str, Any]:
        """Deterministic dict used for hashing / auditing the book."""
        return {
            "rule_id": self.rule_id,
            "verdict": self.verdict.value,
            "action_types": list(self.action_types),
            "tool_names": list(self.tool_names),
            "risk_levels": list(self.risk_levels),
            "actor_ids": list(self.actor_ids),
            "agency_levels": list(self.agency_levels),
            "capabilities_any": list(self.capabilities_any),
            "target_patterns": list(self.target_patterns),
            "when_facts": list(self.when_facts),
            "unless_facts": list(self.unless_facts),
            "constraints": _canonical_constraints(self.constraints),
            "approver_policy": self.approver_policy,
            "priority": self.priority,
            "description": self.description,
            "authority_mode": (
                self.authority_mode.value if self.authority_mode is not None else None
            ),
        }


def _fact_truthy(facts: Mapping[str, Any], name: str) -> bool:
    """Interpret a named declared fact as a boolean.

    Missing facts are False (fail-closed for ``when_facts`` guards).  String
    values "false"/"0"/"no"/"" are treated as False; everything else uses
    normal Python truthiness.
    """
    if name not in facts:
        return False
    value = facts[name]
    if isinstance(value, str):
        return value.strip().lower() not in ("", "false", "0", "no", "off")
    return bool(value)


def _canonical_constraints(constraints: Mapping[str, Any]) -> Dict[str, Any]:
    """Sort constraint keys for stable hashing."""
    return {k: constraints[k] for k in sorted(constraints)}


# =============================================================================
# Book (bundle of rules)
# =============================================================================


@dataclass(frozen=True)
class HumanPolicyBook:
    """An ordered, versioned collection of human-authored rules.

    Selection semantics ("most-restrictive-rule-wins, priority overrides"):
        Among all rules that match a request, the winner is the rule with the
        greatest ``(priority, verdict_severity)`` — ties broken by ``rule_id``
        for determinism.  Thus, at equal priority, a DENY beats a
        REQUIRE_APPROVAL beats an ALLOW.  A higher-priority ALLOW can override
        a lower-priority DENY (this is how narrow allow-exceptions are
        written).  When no rule matches, the book is silent.
    """

    rules: Tuple[HumanPolicyRule, ...]
    name: str = "human-curated"
    version: str = "1.0.0"

    def select(self, ctx: "RequestContext") -> Optional[HumanPolicyRule]:
        """Return the winning matched rule, or None when nothing matches."""
        matched = [r for r in self.rules if r.matches(ctx)]
        if not matched:
            return None
        # Highest (priority, severity) wins; rule_id keeps it deterministic.
        return max(
            matched,
            key=lambda r: (r.priority, verdict_severity(r.verdict), r.rule_id),
        )

    def content_hash(self) -> str:
        """Stable sha256 over the canonical book content."""
        canon = json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "name": self.name,
                "version": self.version,
                "rules": [r.to_canonical() for r in self.rules],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canon.encode("utf-8")).hexdigest()

    def policy_version(self) -> str:
        """Human/audit-friendly version string bound to content."""
        return f"{self.name}@{self.version}+sha256:{self.content_hash()[:16]}"


# =============================================================================
# Request context (dependency-light view of an authorization request)
# =============================================================================


@dataclass(frozen=True)
class RequestContext:
    """Normalized, framework-agnostic view of a request the engine evaluates.

    Kept free of any Pydantic / GovernanceService import so this module has
    no dependency cycle and can be unit-tested in isolation.
    """

    action_type: str
    tool_name: Optional[str]
    risk_level: str
    actor_id: str
    agency_level: str
    capabilities: Tuple[str, ...]
    facts: Mapping[str, Any]
    target_haystack: str


# =============================================================================
# Resolution (engine output)
# =============================================================================


@dataclass(frozen=True)
class HumanPolicyResolution:
    """Outcome of evaluating a request against a human policy book."""

    available: bool  # an engine/book was configured
    matched: bool  # a curated rule matched the request
    verdict: Optional[HumanPolicyVerdict] = None
    matched_rule_id: str = ""
    matched_rule_priority: int = 0
    constraints: Mapping[str, Any] = field(default_factory=dict)
    approver_policy: str = ""
    reason_codes: Tuple[str, ...] = ()
    policy_version: str = ""
    description: str = ""
    fail_closed_error: bool = False
    # ``mode`` is the engine/service DEFAULT mode (configured at construction).
    mode: str = HumanPolicyMode.BASELINE.value
    # Per-decision authority-mode resolution (populated by the engine).
    effective_mode: str = HumanPolicyMode.BASELINE.value
    mode_resolution_source: str = "engine_default"
    criticality: str = ""  # "", "critical", "non_critical", "unknown"
    criticality_basis: Tuple[str, ...] = ()
    criticality_mode: Optional[str] = None
    rule_authority_mode: Optional[str] = None
    conservative_floor: Optional[str] = None  # e.g. "DEFER"

    def governance_decision(self) -> Optional[str]:
        """Map the verdict to a top-level decision string, or None if silent."""
        if self.verdict is None:
            return None
        return _VERDICT_TO_DECISION[self.verdict]

    @property
    def requires_human(self) -> bool:
        """Whether this verdict demands human confirmation."""
        return self.verdict == HumanPolicyVerdict.REQUIRE_APPROVAL

    @property
    def is_dispositive_deny(self) -> bool:
        """Whether this is a hard human DENY."""
        return self.verdict == HumanPolicyVerdict.DENY

    def to_audit_dict(self) -> Dict[str, Any]:
        return {
            "available": self.available,
            "matched": self.matched,
            "verdict": self.verdict.value if self.verdict is not None else None,
            "matched_rule_id": self.matched_rule_id,
            "matched_rule_priority": self.matched_rule_priority,
            "governance_decision": self.governance_decision(),
            "requires_human": self.requires_human,
            "constraints": dict(self.constraints),
            "approver_policy": self.approver_policy,
            "reason_codes": list(self.reason_codes),
            "policy_version": self.policy_version,
            "description": self.description,
            "fail_closed_error": self.fail_closed_error,
            "default_mode": self.mode,
            "effective_mode": self.effective_mode,
            "mode_resolution_source": self.mode_resolution_source,
            "criticality": self.criticality,
            "criticality_basis": list(self.criticality_basis),
            "criticality_mode": self.criticality_mode,
            "rule_authority_mode": self.rule_authority_mode,
            "conservative_floor": self.conservative_floor,
            # Back-compat alias: previously ``mode`` meant the engine default.
            "mode": self.mode,
        }


# Canonical "no engine configured" resolution — silent, no effect.
_UNAVAILABLE = HumanPolicyResolution(available=False, matched=False)


# =============================================================================
# Engine
# =============================================================================


class HumanPolicyEngine:
    """Evaluates a request against a curated ``HumanPolicyBook``.

    Deterministic and fail-closed: any internal error during evaluation
    resolves to a hard ``DENY`` (``fail_closed_error=True``) rather than
    silently degrading to the LLM baseline.
    """

    def __init__(
        self,
        book: HumanPolicyBook,
        mode: HumanPolicyMode = HumanPolicyMode.BASELINE,
        criticality_registry: Optional[ActionCriticalityRegistry] = None,
    ) -> None:
        self.book = book
        # ``mode`` is the DEFAULT authority mode — the lowest-precedence source
        # in per-decision resolution (backward-compatible when no per-rule or
        # per-action-class configuration exists).
        self.mode = mode
        self.criticality_registry = criticality_registry
        self._policy_version = book.policy_version()

    def evaluate(self, ctx: RequestContext) -> HumanPolicyResolution:
        default_mode_value = self.mode.value
        try:
            rule = self.book.select(ctx)
            if rule is None:
                # Configured but nothing matched — silent, LLM baseline stands.
                # Criticality is still classified for audit transparency, but no
                # authority mode is applied (there is no human verdict to make
                # dispositive).
                crit = CriticalityClass.UNKNOWN
                crit_basis: Tuple[str, ...] = ()
                if self.criticality_registry is not None:
                    crit, crit_basis = self.criticality_registry.classify(ctx)
                return HumanPolicyResolution(
                    available=True,
                    matched=False,
                    reason_codes=("HUMAN_POLICY:NO_MATCH",),
                    policy_version=self._policy_version,
                    mode=default_mode_value,
                    effective_mode=default_mode_value,
                    mode_resolution_source="no_match",
                    criticality=crit.value,
                    criticality_basis=crit_basis,
                )

            amr = resolve_authority_mode(
                rule=rule,
                registry=self.criticality_registry,
                engine_default=self.mode,
                ctx=ctx,
            )
            reason_codes = [
                f"HUMAN_POLICY:{rule.verdict.value}",
                f"HUMAN_POLICY_RULE:{rule.rule_id}",
                f"HUMAN_POLICY_MODE:{amr.effective_mode.value}",
                f"HUMAN_POLICY_MODE_SOURCE:{amr.source}",
            ]
            if amr.criticality != CriticalityClass.UNKNOWN or self.criticality_registry is not None:
                reason_codes.append(f"HUMAN_POLICY_CRITICALITY:{amr.criticality.value}")
            if amr.conservative_floor:
                reason_codes.append(
                    f"HUMAN_POLICY_CONSERVATIVE_FLOOR:{amr.conservative_floor}"
                )
            return HumanPolicyResolution(
                available=True,
                matched=True,
                verdict=rule.verdict,
                matched_rule_id=rule.rule_id,
                matched_rule_priority=rule.priority,
                constraints=dict(rule.constraints),
                approver_policy=rule.approver_policy,
                reason_codes=tuple(reason_codes),
                policy_version=self._policy_version,
                description=rule.description,
                mode=default_mode_value,
                effective_mode=amr.effective_mode.value,
                mode_resolution_source=amr.source,
                criticality=amr.criticality.value,
                criticality_basis=amr.criticality_basis,
                criticality_mode=(
                    amr.criticality_mode.value
                    if amr.criticality_mode is not None else None
                ),
                rule_authority_mode=(
                    amr.rule_authority_mode.value
                    if amr.rule_authority_mode is not None else None
                ),
                conservative_floor=amr.conservative_floor,
            )
        except Exception as exc:  # fail-closed: a broken book must not open the gate
            # Fail closed to a dispositive DENY.
            return HumanPolicyResolution(
                available=True,
                matched=True,
                verdict=HumanPolicyVerdict.DENY,
                matched_rule_id="",
                reason_codes=(f"HUMAN_POLICY_ERROR:{type(exc).__name__}",),
                policy_version=self._policy_version,
                fail_closed_error=True,
                mode=default_mode_value,
                effective_mode=HumanPolicyMode.SOURCE_OF_TRUTH.value,
                mode_resolution_source="fail_closed",
            )


# =============================================================================
# Adapter: extract a RequestContext from a GovernanceService request
# =============================================================================


def build_request_context(request: Any, risk_level: str) -> RequestContext:
    """Build a :class:`RequestContext` from an ``AuthorizationRequest``.

    Duck-typed — reads attributes via ``getattr`` so this module never has to
    import the Pydantic model.  ``risk_level`` is the string value classified
    upstream by ``ToolRiskClassifier``.

    Facts are read from ``request.metadata["facts"]`` (a mapping of named
    boolean-ish conditions the caller declares, e.g. ``{"last_replica": True}``).
    The target haystack is assembled from the tool/action/target/params so
    ``target_patterns`` regexes have something meaningful to search.
    """
    metadata = getattr(request, "metadata", None) or {}
    facts = metadata.get("facts") if isinstance(metadata, dict) else None
    if not isinstance(facts, dict):
        facts = {}

    action_type = getattr(request, "action_type", "") or ""
    tool_name = getattr(request, "tool_name", None)
    actor_id = getattr(request, "actor_id", "") or ""
    agency_level = getattr(request, "agency_level", "") or ""
    capabilities = tuple(getattr(request, "capabilities", None) or ())

    haystack_parts: List[str] = [action_type, tool_name or ""]
    if isinstance(metadata, dict):
        for key in ("target", "target_resource", "resource"):
            val = metadata.get(key)
            if val:
                haystack_parts.append(str(val))
    params_summary = getattr(request, "parameters_summary", None)
    if params_summary:
        try:
            haystack_parts.append(json.dumps(params_summary, sort_keys=True, default=str))
        except (TypeError, ValueError):
            haystack_parts.append(str(params_summary))
    target_haystack = " ".join(p for p in haystack_parts if p)

    return RequestContext(
        action_type=action_type,
        tool_name=tool_name,
        risk_level=risk_level,
        actor_id=actor_id,
        agency_level=agency_level,
        capabilities=capabilities,
        facts=facts,
        target_haystack=target_haystack,
    )


def resolve_human_policy(
    engine: Optional[HumanPolicyEngine],
    request: Any,
    risk_level: str,
) -> HumanPolicyResolution:
    """Resolve the human-curated policy verdict for a request.

    Fail-safe: ``engine is None`` → unavailable/no-effect resolution (the
    LLM-derived baseline stands, fully backward-compatible).  A configured
    engine that errors resolves to a fail-closed DENY inside
    :meth:`HumanPolicyEngine.evaluate`.
    """
    if engine is None:
        return _UNAVAILABLE
    try:
        ctx = build_request_context(request, risk_level)
    except Exception as exc:
        # Context extraction failed on a configured engine → fail closed.
        return HumanPolicyResolution(
            available=True,
            matched=True,
            verdict=HumanPolicyVerdict.DENY,
            reason_codes=(f"HUMAN_POLICY_ERROR:{type(exc).__name__}",),
            fail_closed_error=True,
            mode=engine.mode.value,
            effective_mode=HumanPolicyMode.SOURCE_OF_TRUTH.value,
            mode_resolution_source="fail_closed",
        )
    return engine.evaluate(ctx)


# =============================================================================
# Composition helper: "human sets baseline, LLM can only tighten"
# =============================================================================


_DECISION_SEVERITY: Dict[str, int] = {"ALLOW": 0, "DEFER": 1, "DENY": 2}


def stricter_decision(a: str, b: str) -> str:
    """Return the more restrictive of two decision strings (DENY > DEFER > ALLOW)."""
    return a if _DECISION_SEVERITY.get(a, 0) >= _DECISION_SEVERITY.get(b, 0) else b


# =============================================================================
# Example / default book
# =============================================================================


def build_default_criticality_registry() -> ActionCriticalityRegistry:
    """A small, illustrative human-authored criticality registry.

    Destructive/privileged actions (and known impact facts) are CRITICAL →
    SOURCE_OF_TRUTH; read-only actions are NON_CRITICAL → BASELINE; anything
    else is UNKNOWN and handled conservatively (force REQUIRE_APPROVAL).
    Security owners replace this with their own class map.
    """
    return ActionCriticalityRegistry(
        critical_risk_levels=("destructive", "privileged"),
        non_critical_risk_levels=("read_only",),
        critical_promoting_facts=(
            "last_replica", "irreversible", "bulk", "public_sensitive",
        ),
        uncertain_disposition=UncertainDisposition.REQUIRE_APPROVAL,
    )


def build_default_book() -> HumanPolicyBook:
    """A small, illustrative human-curated book.

    Mirrors a few of the hard invariants from the frozen reference ruleset
    (``action_gate_ref.policy.DEFAULT_RULES``) but expressed against the
    agentic authorization request.  Intended as a starting template that
    security owners replace with their own rules — not a production policy.
    """
    return HumanPolicyBook(
        name="human-curated-default",
        version="1.0.0",
        rules=(
            # Never delete the last replica of a datastore.
            HumanPolicyRule(
                rule_id="HP-DB-LAST-REPLICA",
                verdict=HumanPolicyVerdict.DENY,
                risk_levels=("destructive",),
                when_facts=("last_replica",),
                description="Deleting the last replica is irreversible; hard deny.",
            ),
            # Any destructive action requires dual-control human approval.
            HumanPolicyRule(
                rule_id="HP-DESTRUCTIVE-APPROVAL",
                verdict=HumanPolicyVerdict.REQUIRE_APPROVAL,
                risk_levels=("destructive",),
                approver_policy="dual_control",
                description="Destructive actions require dual-control approval.",
            ),
            # Privileged actions require human approval.
            HumanPolicyRule(
                rule_id="HP-PRIVILEGED-APPROVAL",
                verdict=HumanPolicyVerdict.REQUIRE_APPROVAL,
                risk_levels=("privileged",),
                approver_policy="single",
                description="Privileged actions require human approval.",
            ),
            # Free-text external communications are denied; templated allowed.
            HumanPolicyRule(
                rule_id="HP-EXTERNAL-COMMS-FREETEXT",
                verdict=HumanPolicyVerdict.DENY,
                action_types=("send_email", "external_comms", "post_message"),
                when_facts=("free_text",),
                description="Unstructured outbound comms are denied.",
            ),
            # Read-only actions are explicitly allowed at the human layer.
            HumanPolicyRule(
                rule_id="HP-READONLY-ALLOW",
                verdict=HumanPolicyVerdict.ALLOW,
                risk_levels=("read_only",),
                description="Read-only actions are permitted by human policy.",
            ),
        ),
    )
