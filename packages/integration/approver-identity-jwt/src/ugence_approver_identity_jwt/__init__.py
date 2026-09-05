"""Ugence Approver Identity JWT — the first real ``ApproverIdentityPort`` adapter:
a locally validated RFC 9068 access token as proof of who decided (AI-C, owner rulings
IA-1 to IA-5, ``docs/architecture/ADR_UGENCE_APPROVER_IDENTITY_ADAPTER_SCOPING.md``).

    THIS PACKAGE VALIDATES A PROOF IT DID NOT ISSUE. IT MINTS NO IDENTITY, HOLDS NO
    CREDENTIAL BEYOND PUBLIC KEYS, AND NEVER LOGS, STORES OR RETURNS A TOKEN.

Maturity ``REFERENCE_GRADE_SHADOW_ONLY``: validated against this package's in-process
test issuer only; validation against a real enterprise issuer remains unproven.
"""

from __future__ import annotations

from .adapter import (
    ACCESS_TOKEN_TYPES,
    ALGORITHMS,
    REQUIRED_CLAIMS,
    JwtApproverIdentity,
    JwtApproverIdentityAdapter,
    Refusal,
)
from .config import LOOPBACK_HOSTS, AdapterConfig
from .errors import AdapterConfigurationError, KeyRetrievalFailed
from .keys import MAX_JWKS_BYTES, JwksKeyCache
from .version import ENFORCEMENT_ENABLED, ISSUER_VALIDATION, MATURITY, __version__

__all__ = [
    "__version__", "MATURITY", "ISSUER_VALIDATION", "ENFORCEMENT_ENABLED",
    "JwtApproverIdentityAdapter", "JwtApproverIdentity", "Refusal",
    "ALGORITHMS", "ACCESS_TOKEN_TYPES", "REQUIRED_CLAIMS",
    "AdapterConfig", "LOOPBACK_HOSTS",
    "JwksKeyCache", "MAX_JWKS_BYTES",
    "KeyRetrievalFailed", "AdapterConfigurationError",
]
