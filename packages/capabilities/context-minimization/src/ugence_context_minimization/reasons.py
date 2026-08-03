"""Deterministic reason codes recorded on every :class:`MinimizationResult`.

Reason codes are a stable, curated vocabulary explaining *why* a run produced the
result it did. They are part of the public contract; add codes, never repurpose
one. Every fail-closed path emits a code so an auditor can see exactly which
guard fired.
"""

from __future__ import annotations

# --- structural ---------------------------------------------------------------
STRUCTURAL_DEDUP_APPLIED = "STRUCTURAL_DEDUP_APPLIED"
NO_REDUCTION_POSSIBLE = "NO_REDUCTION_POSSIBLE"

# --- extractive selection -----------------------------------------------------
EXTRACTIVE_REMOVAL_APPLIED = "EXTRACTIVE_REMOVAL_APPLIED"
TARGET_REDUCTION_MET = "TARGET_REDUCTION_MET"
TARGET_REDUCTION_UNMET = "TARGET_REDUCTION_UNMET"
BUDGET_UNREACHABLE_WITHOUT_PROTECTED = "BUDGET_UNREACHABLE_WITHOUT_PROTECTED"

# --- oracle equivalence -------------------------------------------------------
EQUIVALENCE_VERIFIED = "EQUIVALENCE_VERIFIED"
SPANS_RESTORED = "SPANS_RESTORED"

# --- fail-closed reasons (each raises retained context, never removal) ---------
ORACLE_REQUIRED_FOR_MODE = "ORACLE_REQUIRED_FOR_MODE"
ORACLE_RAISED = "ORACLE_RAISED"
ORACLE_RESULT_MALFORMED = "ORACLE_RESULT_MALFORMED"
ORACLE_CONTRACT_MISMATCH = "ORACLE_CONTRACT_MISMATCH"
ORACLE_EVALUATION_EXPIRED = "ORACLE_EVALUATION_EXPIRED"
#: valid_until was supplied but no evaluation_time was given — the core will not
#: assume "unexpired" and will not read a wall clock; it fails closed (v0.1.1).
ORACLE_EVALUATION_TIME_REQUIRED = "ORACLE_EVALUATION_TIME_REQUIRED"
#: context carries a correlation id but the oracle evaluation omitted one (v0.1.1).
ORACLE_CORRELATION_MISSING = "ORACLE_CORRELATION_MISSING"
#: context correlation id and the oracle evaluation's correlation id differ (v0.1.1).
ORACLE_CORRELATION_MISMATCH = "ORACLE_CORRELATION_MISMATCH"
#: DEPRECATED (v0.1.1): superseded by the two specific codes above. Retained as a
#: defined constant so existing imports do not break; it is no longer emitted and is
#: not part of the curated ALL_REASON_CODES vocabulary.
CORRELATION_MISMATCH = "CORRELATION_MISMATCH"
EQUIVALENCE_NOT_ESTABLISHED = "EQUIVALENCE_NOT_ESTABLISHED"
JOINT_EFFECT_FALLBACK = "JOINT_EFFECT_FALLBACK"
PROTECTION_PROVIDER_FAILED = "PROTECTION_PROVIDER_FAILED"
PROTECTION_EMPTY = "PROTECTION_EMPTY"

# Curated, ordered public set (used by the generated reason_codes.json artifact and
# the public-API test). The deprecated ``CORRELATION_MISMATCH`` alias is intentionally
# excluded — the emitted vocabulary uses the two specific correlation codes.
ALL_REASON_CODES: tuple[str, ...] = (
    STRUCTURAL_DEDUP_APPLIED,
    NO_REDUCTION_POSSIBLE,
    EXTRACTIVE_REMOVAL_APPLIED,
    TARGET_REDUCTION_MET,
    TARGET_REDUCTION_UNMET,
    BUDGET_UNREACHABLE_WITHOUT_PROTECTED,
    EQUIVALENCE_VERIFIED,
    SPANS_RESTORED,
    ORACLE_REQUIRED_FOR_MODE,
    ORACLE_RAISED,
    ORACLE_RESULT_MALFORMED,
    ORACLE_CONTRACT_MISMATCH,
    ORACLE_EVALUATION_EXPIRED,
    ORACLE_EVALUATION_TIME_REQUIRED,
    ORACLE_CORRELATION_MISSING,
    ORACLE_CORRELATION_MISMATCH,
    EQUIVALENCE_NOT_ESTABLISHED,
    JOINT_EFFECT_FALLBACK,
    PROTECTION_PROVIDER_FAILED,
    PROTECTION_EMPTY,
)
