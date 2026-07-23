"""Stable, machine-readable reason-code taxonomy (see REASON_CODE_TAXONOMY.md).

Append-only: existing codes never change meaning. Raw provider error strings are
NORMALIZED into these codes; the raw string is kept in Evidence, never used as a code.
"""
from __future__ import annotations

from enum import Enum


class ReasonCode(str, Enum):
    OK = "OK"
    # network / transport
    NETWORK_BLOCKED = "NETWORK_BLOCKED"
    DNS_FAILURE = "DNS_FAILURE"
    TLS_FAILURE = "TLS_FAILURE"
    # auth / credential
    AUTH_MISSING = "AUTH_MISSING"
    AUTH_INVALID = "AUTH_INVALID"
    AUTH_EXPIRED = "AUTH_EXPIRED"
    # billing / quota
    BILLING_INACTIVE = "BILLING_INACTIVE"
    FREE_TIER_ONLY = "FREE_TIER_ONLY"
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    RATE_LIMITED = "RATE_LIMITED"
    # model availability
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
    MODEL_DISABLED = "MODEL_DISABLED"
    # region / residency / governance
    REGION_UNAVAILABLE = "REGION_UNAVAILABLE"
    DATA_RESIDENCY_VIOLATION = "DATA_RESIDENCY_VIOLATION"
    PROVIDER_NOT_APPROVED = "PROVIDER_NOT_APPROVED"
    # capability / features
    FEATURE_UNSUPPORTED = "FEATURE_UNSUPPORTED"
    CONTEXT_TOO_SMALL = "CONTEXT_TOO_SMALL"
    # operational limits
    COST_LIMIT_EXCEEDED = "COST_LIMIT_EXCEEDED"
    LATENCY_LIMIT_EXCEEDED = "LATENCY_LIMIT_EXCEEDED"
    RELIABILITY_BELOW_THRESHOLD = "RELIABILITY_BELOW_THRESHOLD"
    PROVIDER_DEGRADED = "PROVIDER_DEGRADED"
    # evidence quality
    POLICY_STATE_UNKNOWN = "POLICY_STATE_UNKNOWN"
    TELEMETRY_STALE = "TELEMETRY_STALE"


# normalization of raw provider signals -> codes (raw strings kept only in Evidence)
def normalize_raw(signal: str) -> ReasonCode:
    s = (signal or "").lower()
    if "403" in s and "connect" in s or "tunnel connection failed" in s:
        return ReasonCode.NETWORK_BLOCKED
    if "invalidclienttokenid" in s or "invalid_token" in s or "401" in s or "unauthor" in s:
        return ReasonCode.AUTH_INVALID
    if "freetier" in s or "free_tier" in s or "free-tier" in s:
        return ReasonCode.FREE_TIER_ONLY
    if "resource_exhausted" in s or "quota" in s or "429" in s:
        return ReasonCode.QUOTA_EXHAUSTED
    if "model_not_found" in s or ("404" in s and "model" in s) or "not_found" in s:
        return ReasonCode.MODEL_NOT_FOUND
    if "nxdomain" in s or "name or service not known" in s:
        return ReasonCode.DNS_FAILURE
    if "certificate" in s or "ssl" in s or "tls" in s:
        return ReasonCode.TLS_FAILURE
    return ReasonCode.POLICY_STATE_UNKNOWN
