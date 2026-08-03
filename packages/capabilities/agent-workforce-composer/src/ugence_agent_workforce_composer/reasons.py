"""Append-only elimination-reason taxonomy.

Every hard-constraint failure normalizes into one of these typed codes. The
taxonomy is append-only: existing codes never change meaning. Unknown raw codes
normalize deterministically to :data:`EliminationReason.UNKNOWN_REQUIRED_EVIDENCE`
(a safe fail-closed value) rather than being silently dropped.
"""
from __future__ import annotations

from enum import Enum


class EliminationReason(str, Enum):
    # -- capability / evidence --------------------------------------------------
    MISSING_REQUIRED_CAPABILITY = "MISSING_REQUIRED_CAPABILITY"
    CAPABILITY_EVIDENCE_INSUFFICIENT = "CAPABILITY_EVIDENCE_INSUFFICIENT"
    CAPABILITY_EVIDENCE_EXPIRED = "CAPABILITY_EVIDENCE_EXPIRED"
    CAPABILITY_EVIDENCE_VERSION_MISMATCH = "CAPABILITY_EVIDENCE_VERSION_MISMATCH"
    DECLARED_ONLY_WHEN_MEASURED_REQUIRED = "DECLARED_ONLY_WHEN_MEASURED_REQUIRED"
    UNKNOWN_REQUIRED_EVIDENCE = "UNKNOWN_REQUIRED_EVIDENCE"
    # -- interface / contract ---------------------------------------------------
    INPUT_CONTRACT_INCOMPATIBLE = "INPUT_CONTRACT_INCOMPATIBLE"
    OUTPUT_CONTRACT_INCOMPATIBLE = "OUTPUT_CONTRACT_INCOMPATIBLE"
    # -- tools ------------------------------------------------------------------
    REQUIRED_TOOL_UNAVAILABLE = "REQUIRED_TOOL_UNAVAILABLE"
    PROHIBITED_TOOL_REQUIRED = "PROHIBITED_TOOL_REQUIRED"
    # -- provider / residency / deployment --------------------------------------
    PROVIDER_FORBIDDEN = "PROVIDER_FORBIDDEN"
    PROVIDER_NOT_APPROVED = "PROVIDER_NOT_APPROVED"
    RESIDENCY_MISMATCH = "RESIDENCY_MISMATCH"
    DEPLOYMENT_ENVIRONMENT_MISMATCH = "DEPLOYMENT_ENVIRONMENT_MISMATCH"
    # -- security / audit -------------------------------------------------------
    SECURITY_CLASSIFICATION_INSUFFICIENT = "SECURITY_CLASSIFICATION_INSUFFICIENT"
    AUDIT_CAPABILITY_INSUFFICIENT = "AUDIT_CAPABILITY_INSUFFICIENT"
    # -- permission / authority -------------------------------------------------
    PERMISSION_REQUIREMENT_EXCEEDS_POLICY = "PERMISSION_REQUIREMENT_EXCEEDS_POLICY"
    AUTHORITY_REQUIREMENT_EXCEEDS_CEILING = "AUTHORITY_REQUIREMENT_EXCEEDS_CEILING"
    # -- hard operational limits ------------------------------------------------
    COST_HARD_LIMIT_EXCEEDED = "COST_HARD_LIMIT_EXCEEDED"
    LATENCY_HARD_LIMIT_EXCEEDED = "LATENCY_HARD_LIMIT_EXCEEDED"
    QUALITY_FLOOR_NOT_MET = "QUALITY_FLOOR_NOT_MET"
    # -- agent version / status -------------------------------------------------
    AGENT_VERSION_NOT_APPROVED = "AGENT_VERSION_NOT_APPROVED"
    AGENT_VERSION_REVOKED = "AGENT_VERSION_REVOKED"
    AGENT_INACTIVE = "AGENT_INACTIVE"
    PROFILE_EXPIRED = "PROFILE_EXPIRED"
    # -- integrity --------------------------------------------------------------
    MALFORMED_PROFILE = "MALFORMED_PROFILE"
    MALFORMED_ROLE = "MALFORMED_ROLE"
    MALFORMED_POLICY = "MALFORMED_POLICY"
    SNAPSHOT_INTEGRITY_FAILURE = "SNAPSHOT_INTEGRITY_FAILURE"


#: Codes that are safe fail-closed defaults for unknown/normalized input.
_SAFE_UNKNOWN = EliminationReason.UNKNOWN_REQUIRED_EVIDENCE

_BY_VALUE = {r.value: r for r in EliminationReason}


def normalize_reason(raw: object) -> EliminationReason:
    """Normalize a raw reason (str/enum/None) to a typed :class:`EliminationReason`.

    Unknown or unparsable codes map deterministically to
    :data:`EliminationReason.UNKNOWN_REQUIRED_EVIDENCE`. A raw code is never
    silently discarded.
    """
    if isinstance(raw, EliminationReason):
        return raw
    if raw is None:
        return _SAFE_UNKNOWN
    key = str(raw).strip().upper()
    return _BY_VALUE.get(key, _SAFE_UNKNOWN)


__all__ = ["EliminationReason", "normalize_reason"]
