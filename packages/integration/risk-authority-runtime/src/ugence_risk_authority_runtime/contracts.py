"""Composition contracts for RA-4.5 fail-closed governance composition.

These value objects are the **integration-layer** vocabulary. They describe
*additive governance inputs* folded onto a Risk Authority machine-authority
result, and the single governed decision that results. They are deliberately
constrained so the corrected authority model holds *by construction*:

* A :class:`GovernanceVetoResult` can express ``NO_VETO``, ``HOLD``, ``DENY`` or
  ``ERROR`` — **never** an ``ALLOW`` and never a scope. Governance can only
  subtract authority; it can never manufacture it.
* :class:`EffectiveConstraints` is computed as ``RA scope ∩ governance
  restrictions`` and can only *preserve or reduce* the Risk Authority scope.
* :class:`GovernedExecutionDecision` **wraps** (never re-mints) the signed
  ``RiskAuthorizationEnvelope``. It is a composition/audit artifact that
  explains *why* execution is eligible or blocked — it is **not** a second
  machine-authorization envelope.

Every object here is immutable and JSON-serializable (``to_dict``). No object in
this module carries a signature or can be mistaken for machine authority.

See ``docs/architecture/RISK_AUTHORITY_RA45_GOVERNANCE_COMPOSITION_PLAN.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Mapping, Optional

__all__ = [
    "VetoDisposition",
    "FinalDisposition",
    "RiskAuthorityDisposition",
    "ReasonCode",
    "GovernanceRestrictions",
    "GovernanceVetoResult",
    "RiskAuthorityMachineResult",
    "EffectiveConstraints",
    "GovernedExecutionDecision",
]


# --------------------------------------------------------------------------
# Bounded vocabularies (closed, small, branched-on — never free text).
# --------------------------------------------------------------------------


class RiskAuthorityDisposition(str, Enum):
    """The Risk Authority machine-authority verdict for an exact action.

    ``ALLOW`` means the signed envelope verified (signature / time / revocation
    / epoch / tenant / actor / model) **and** the exact canonical action matched
    the signed scope. ``DENY`` means Risk Authority refused for any
    authority-critical reason. ``ERROR`` means the Risk Authority enforcement
    path could not be evaluated at all (fail closed — never an authorization).
    """

    ALLOW = "ALLOW"
    DENY = "DENY"
    ERROR = "ERROR"


class VetoDisposition(str, Enum):
    """What an additive governance input contributes to the composition.

    Deliberately has **no ALLOW and no scope**. The strongest positive a
    governance input can express is ``NO_VETO`` ("this source does not object").
    It can never upgrade a Risk Authority ``DENY`` or widen scope.
    """

    NO_VETO = "NO_VETO"
    HOLD = "HOLD"
    DENY = "DENY"
    ERROR = "ERROR"


class FinalDisposition(str, Enum):
    """The composed, fail-closed execution-eligibility disposition."""

    GRANT = "GRANT"
    DENY = "DENY"
    HOLD_NON_EXECUTABLE = "HOLD_NON_EXECUTABLE"
    ERROR_NON_EXECUTABLE = "ERROR_NON_EXECUTABLE"

    @property
    def executable(self) -> bool:
        return self is FinalDisposition.GRANT


class ReasonCode(str, Enum):
    """Structured, per-source reason codes.

    These are *composition-layer* codes. They never assert equality with any
    kernel's native reason vocabulary (the vocabularies are unrelated); the
    per-source raw codes are preserved separately on each result.
    """

    # Risk Authority (machine authority) — absorbing failures.
    RA_DENY = "RA_DENY"
    RA_ENVELOPE_INVALID = "RA_ENVELOPE_INVALID"
    RA_EXPIRED = "RA_EXPIRED"
    RA_REVOKED = "RA_REVOKED"
    RA_STALE_EPOCH = "RA_STALE_EPOCH"
    RA_ACTION_MISMATCH = "RA_ACTION_MISMATCH"
    RA_UNAVAILABLE = "RA_UNAVAILABLE"
    RA_ALLOW = "RA_ALLOW"

    # Decision Authority (organizational governance veto).
    DA_ADVANCE_NO_VETO = "DA_ADVANCE_NO_VETO"
    DA_REJECT = "DA_REJECT"
    DA_HOLD = "DA_HOLD"
    DA_DEFER = "DA_DEFER"
    DA_UNKNOWN_OUTCOME = "DA_UNKNOWN_OUTCOME"
    DA_UNAVAILABLE = "DA_UNAVAILABLE"
    DA_MALFORMED = "DA_MALFORMED"

    # ActionGate (supplementary action-policy veto / restriction).
    AG_ALLOW_NO_VETO = "AG_ALLOW_NO_VETO"
    AG_ALLOW_WITH_CONSTRAINTS = "AG_ALLOW_WITH_CONSTRAINTS"
    AG_DENY = "AG_DENY"
    AG_UNKNOWN = "AG_UNKNOWN"
    AG_UNAVAILABLE = "AG_UNAVAILABLE"
    AG_MALFORMED = "AG_MALFORMED"

    # Restriction algebra.
    EFFECTIVE_SCOPE_EMPTY = "EFFECTIVE_SCOPE_EMPTY"
    RESTRICTIONS_APPLIED = "RESTRICTIONS_APPLIED"

    # All-clear.
    GRANTED = "GRANTED"


# --------------------------------------------------------------------------
# Governance restriction inputs (tightening-only).
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class GovernanceRestrictions:
    """Tightening-only restrictions a governance source contributes.

    Every field can only *narrow* the effective authority relative to the Risk
    Authority scope. There is intentionally no field that could widen an allow
    set, raise a ceiling, or extend an expiry. The restriction algebra
    (:mod:`ugence_risk_authority_runtime.restrictions`) enforces the direction.
    """

    #: Upper bound on transaction amount (minor units); combined with RA via min().
    max_amount_minor_units: Optional[int] = None
    #: Absolute expiry instant; combined with RA via earliest().
    expires_at: Optional[datetime] = None
    #: Allow-set intersections keyed by scope dimension (e.g. "tools_allow").
    #: Each intersects with the corresponding RA allow set (can only shrink it).
    allow_intersections: Mapping[str, frozenset[str]] = field(default_factory=dict)
    #: Deny-set additions keyed by scope dimension (e.g. "tools_deny").
    #: Each unions into the corresponding RA deny set (can only grow denial).
    deny_unions: Mapping[str, frozenset[str]] = field(default_factory=dict)
    #: Additional required approvals (union → strengthens the obligation).
    required_approvals: frozenset[str] = frozenset()
    #: Recorded governance obligations (audit only; never treated as RA
    #: enforcement — e.g. an AG ``allowed_region`` is recorded here, NOT mapped
    #: onto RA jurisdiction enforcement, which remains F-D / #1397).
    obligations: tuple[tuple[str, str], ...] = ()

    def to_dict(self) -> dict:
        return {
            "max_amount_minor_units": self.max_amount_minor_units,
            "expires_at": _iso(self.expires_at),
            "allow_intersections": {
                k: sorted(v) for k, v in self.allow_intersections.items()
            },
            "deny_unions": {k: sorted(v) for k, v in self.deny_unions.items()},
            "required_approvals": sorted(self.required_approvals),
            "obligations": [list(o) for o in self.obligations],
        }


EMPTY_RESTRICTIONS = GovernanceRestrictions()


# --------------------------------------------------------------------------
# Per-source results.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class GovernanceVetoResult:
    """A single governance source's contribution to the composition.

    This is the only shape a Decision Authority or ActionGate adapter may
    produce. It can veto, hold, error, or stand aside — it can **never** grant,
    and it carries **no** authorization scope of its own.
    """

    source: str  # "decision_authority" | "actiongate"
    disposition: VetoDisposition
    reason_codes: tuple[str, ...] = ()
    restrictions: GovernanceRestrictions = EMPTY_RESTRICTIONS
    source_version: str = ""
    raw_outcome: str = ""
    raw_reason_codes: tuple[str, ...] = ()

    @property
    def vetoes(self) -> bool:
        return self.disposition in (VetoDisposition.HOLD, VetoDisposition.DENY)

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "disposition": self.disposition.value,
            "reason_codes": list(self.reason_codes),
            "restrictions": self.restrictions.to_dict(),
            "source_version": self.source_version,
            "raw_outcome": self.raw_outcome,
            "raw_reason_codes": list(self.raw_reason_codes),
        }


@dataclass(frozen=True)
class RiskAuthorityMachineResult:
    """The Risk Authority machine-authority verdict for an exact action.

    Produced by reusing the canonical RA enforcement path (envelope verifier +
    exact-action matcher). This object references — but never re-mints — the
    signed ``RiskAuthorizationEnvelope``. Its ``scope`` is the RA-issued scope
    that bounds every effective constraint (``FinalScope ⊆ RiskAuthorityScope``).
    """

    disposition: RiskAuthorityDisposition
    reason_codes: tuple[str, ...] = ()
    envelope_id: str = ""
    action_digest: str = ""
    # The RA-issued authority scope (source of truth for restriction algebra).
    # Kept as an opaque object to avoid importing RA domain types here; the
    # engine and restriction algebra read its documented attributes.
    scope: object = None
    expires_at: Optional[datetime] = None
    source_version: str = ""
    raw_reason_codes: tuple[str, ...] = ()

    @property
    def authorized(self) -> bool:
        return self.disposition is RiskAuthorityDisposition.ALLOW

    @property
    def errored(self) -> bool:
        return self.disposition is RiskAuthorityDisposition.ERROR

    def to_dict(self) -> dict:
        return {
            "disposition": self.disposition.value,
            "reason_codes": list(self.reason_codes),
            "envelope_id": self.envelope_id,
            "action_digest": self.action_digest,
            "expires_at": _iso(self.expires_at),
            "source_version": self.source_version,
            "raw_reason_codes": list(self.raw_reason_codes),
        }


# --------------------------------------------------------------------------
# Effective constraints (FinalScope ⊆ RiskAuthorityScope).
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class EffectiveConstraints:
    """The computed effective authority: ``RA scope ∩ governance restrictions``.

    Constructed from the RA scope, then tightened. Never wider than RA on any
    dimension. ``is_empty()`` is true when a dimension RA authorized has been
    intersected to nothing, or an amount ceiling has been driven to zero — in
    which case the composition denies (no residual authority to execute).
    """

    purposes: tuple[str, ...] = ()
    tools_allow: tuple[str, ...] = ()
    tools_deny: tuple[str, ...] = ()
    data_allow: tuple[str, ...] = ()
    data_deny: tuple[str, ...] = ()
    destinations: tuple[str, ...] = ()
    jurisdictions: tuple[str, ...] = ()
    max_autonomy_level: int = 0
    max_amount_minor_units: Optional[int] = None
    expires_at: Optional[datetime] = None
    required_approvals: frozenset[str] = frozenset()
    obligations: tuple[tuple[str, str], ...] = ()
    #: Names of allow dimensions RA authorized (non-empty) that governance
    #: intersected to empty. Non-empty ⇒ the effective scope is empty.
    emptied_dimensions: tuple[str, ...] = ()

    def is_empty(self) -> bool:
        if self.emptied_dimensions:
            return True
        if (
            self.max_amount_minor_units is not None
            and self.max_amount_minor_units <= 0
        ):
            return True
        return False

    def to_dict(self) -> dict:
        return {
            "purposes": list(self.purposes),
            "tools_allow": list(self.tools_allow),
            "tools_deny": list(self.tools_deny),
            "data_allow": list(self.data_allow),
            "data_deny": list(self.data_deny),
            "destinations": list(self.destinations),
            "jurisdictions": list(self.jurisdictions),
            "max_autonomy_level": self.max_autonomy_level,
            "max_amount_minor_units": self.max_amount_minor_units,
            "expires_at": _iso(self.expires_at),
            "required_approvals": sorted(self.required_approvals),
            "obligations": [list(o) for o in self.obligations],
            "emptied_dimensions": list(self.emptied_dimensions),
        }


# --------------------------------------------------------------------------
# The governed decision (composition/audit artifact — NOT machine authority).
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class GovernedExecutionDecision:
    """The single governed decision produced by the composition engine.

    Wraps (never re-mints) the signed RA envelope with governance evidence and
    the computed effective constraints. It explains *why* execution is eligible
    or blocked. It is **not** an authorization envelope and carries no signature.
    """

    final_disposition: FinalDisposition
    risk_authority_result: RiskAuthorityMachineResult
    decision_authority_result: GovernanceVetoResult
    actiongate_result: GovernanceVetoResult
    effective_constraints: EffectiveConstraints
    reason_codes: tuple[str, ...] = ()
    non_executable_reason: str = ""
    source_versions: Mapping[str, str] = field(default_factory=dict)
    correlation_id: str = ""

    @property
    def executable(self) -> bool:
        return self.final_disposition.executable

    def to_dict(self) -> dict:
        return {
            "final_disposition": self.final_disposition.value,
            "executable": self.executable,
            "risk_authority_result": self.risk_authority_result.to_dict(),
            "decision_authority_result": self.decision_authority_result.to_dict(),
            "actiongate_result": self.actiongate_result.to_dict(),
            "effective_constraints": self.effective_constraints.to_dict(),
            "reason_codes": list(self.reason_codes),
            "non_executable_reason": self.non_executable_reason,
            "source_versions": dict(self.source_versions),
            "correlation_id": self.correlation_id,
        }


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value is not None else None
