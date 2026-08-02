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
CORRELATION_MISMATCH = "CORRELATION_MISMATCH"
EQUIVALENCE_NOT_ESTABLISHED = "EQUIVALENCE_NOT_ESTABLISHED"
JOINT_EFFECT_FALLBACK = "JOINT_EFFECT_FALLBACK"
PROTECTION_PROVIDER_FAILED = "PROTECTION_PROVIDER_FAILED"
PROTECTION_EMPTY = "PROTECTION_EMPTY"

# Curated, ordered public set (used by the generated reason_codes.json artifact and
# the public-API test).
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
    CORRELATION_MISMATCH,
    EQUIVALENCE_NOT_ESTABLISHED,
    JOINT_EFFECT_FALLBACK,
    PROTECTION_PROVIDER_FAILED,
    PROTECTION_EMPTY,
)
