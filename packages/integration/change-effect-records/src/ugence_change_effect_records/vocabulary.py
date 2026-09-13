"""Closed vocabularies. Every one is a name the rule fixes; none is a decision.

Nothing here classifies, routes, measures or admits. These are the words the
records are written in.
"""

from __future__ import annotations

from enum import Enum


class EvaluationStatus(str, Enum):
    """Whether a registry's effect was measured at all."""

    MEASURED = "MEASURED"
    NO_EFFECT = "NO_EFFECT"
    UNEVALUATED = "UNEVALUATED"


class EffectClass(str, Enum):
    """What a measured effect is. Set only when the status is ``MEASURED``."""

    DESCRIPTIVE_STATE = "DESCRIPTIVE_STATE"
    POLICY_ENFORCEMENT = "POLICY_ENFORCEMENT"
    AUTHORITY = "AUTHORITY"
    IDENTITY = "IDENTITY"


class JurisdictionalRoute(str, Enum):
    """Which governance process has jurisdiction. A route is never a permission."""

    GERL_BASE = "GERL_BASE"
    GERL_DELEGATED = "GERL_DELEGATED"
    POLICY_GOVERNANCE = "POLICY_GOVERNANCE"
    UNDETERMINED_PENDING_EVALUATION = "UNDETERMINED_PENDING_EVALUATION"


class ObligationKind(str, Enum):
    """The blocking obligations the rule can emit."""

    UNEVALUABLE_REGISTRY = "UNEVALUABLE_REGISTRY"
    UNDERSIZED_CELL = "UNDERSIZED_CELL"
    ZERO_DENOMINATOR = "ZERO_DENOMINATOR"
    MISSING_BASELINE = "MISSING_BASELINE"
    MIXED_DIRECTION = "MIXED_DIRECTION"
    D1_BOUND_ADMITS_WORSENING = "D1_BOUND_ADMITS_WORSENING"
    CUSTODY_UNVERIFIED = "CUSTODY_UNVERIFIED"
    NO_ANCHOR = "NO_ANCHOR"
    CONFIRMATION_PENDING = "CONFIRMATION_PENDING"
    INSUFFICIENT_EVALUATION = "INSUFFICIENT_EVALUATION"
    INSUFFICIENT_ARCHIVE = "INSUFFICIENT_ARCHIVE"


class ClosureOutcome(str, Enum):
    """How an investigation ended. Only ``COMPLETED`` can feed a final resolution."""

    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"
    CLOSED_INSUFFICIENT_EVIDENCE = "CLOSED_INSUFFICIENT_EVIDENCE"


class PrimitiveEffectKind(str, Enum):
    """The six writable primitives. **None of them writes a derived value.**

    A registry status, an effect class, a direction, a magnitude, a D1 bound and
    every routing input are recomputed by the Stage 3 projection, never supplied.
    """

    SET_SAMPLE = "SET_SAMPLE"
    SET_CELL_MEASUREMENT = "SET_CELL_MEASUREMENT"
    SET_REGISTRY_OBSERVATION = "SET_REGISTRY_OBSERVATION"
    SET_BASELINE = "SET_BASELINE"
    SET_EVIDENCE_CUSTODY = "SET_EVIDENCE_CUSTODY"
    SET_CONFIRMATION_RESULT = "SET_CONFIRMATION_RESULT"


class AdmissionState(str, Enum):
    """States an admission record carries. No record ever changes its own state."""

    RESERVED = "RESERVED"
    APPLIED = "APPLIED"
    FAILED = "FAILED"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"


class ClaimKind(str, Enum):
    """APPLY is the execution commitment; CANCEL is documentary and load-bearing for nothing."""

    APPLY = "APPLY"
    CANCEL = "CANCEL"


class ControlRegisterState(str, Enum):
    """The resolution's control register. ``REVOKED`` is terminal absolutely."""

    ACTIVE = "ACTIVE"
    APPLY_COMMITTED = "APPLY_COMMITTED"
    APPLIED = "APPLIED"
    REVOKED = "REVOKED"


class RevocationOrdering(str, Enum):
    """Fixed by the control register's own transition sequence, never by a clock."""

    REVOKE_THEN_APPLY = "REVOKE_THEN_APPLY"
    APPLY_THEN_REVOKE = "APPLY_THEN_REVOKE"


class CompletionAbsence(str, Enum):
    """Why no completion exists. Admissible in exactly one case.

    A stalled executor is **never** absence: a completion always arrives, because
    the recovery rule produces one. Only "no APPLY claim was ever made" is
    structural, and a verifier confirms it from an empty or CANCEL claim slot.
    """

    NO_APPLY_CLAIM = "NO_APPLY_CLAIM"


class RemediationRequirement(str, Enum):
    """Owner decision 6b, taken 2026-09-13, as two separate obligations.

    A revoked applied delta always requires state repair. Downstream-exposure
    remediation is a different obligation, required where at least one read was
    served; until archive custody exists the presumption is that it was.
    """

    NONE = "NONE"
    STATE_REPAIR_REQUIRED = "STATE_REPAIR_REQUIRED"
    STATE_REPAIR_AND_EXPOSURE_REMEDIATION_REQUIRED = (
        "STATE_REPAIR_AND_EXPOSURE_REMEDIATION_REQUIRED"
    )


class ReviewOutcome(str, Enum):
    """The four outcomes the reviewer returns."""

    SUPPORTED = "SUPPORTED"
    REPLAY_MISMATCH = "REPLAY_MISMATCH"
    INSUFFICIENT_EVALUATION = "INSUFFICIENT_EVALUATION"
    MISCLASSIFIED = "MISCLASSIFIED"
