"""Ugence Approver Identity JWT — the first real ``ApproverIdentityPort`` adapter:
a locally validated RFC 9068 access token as proof of who decided (AI-C, owner rulings
IA-1 to IA-5, ``docs/architecture/ADR_UGENCE_APPROVER_IDENTITY_ADAPTER_SCOPING.md``).

    THIS PACKAGE VALIDATES A PROOF IT DID NOT ISSUE. IT MINTS NO IDENTITY, HOLDS NO
    CREDENTIAL BEYOND PUBLIC KEYS, AND NEVER LOGS, STORES OR RETURNS A TOKEN.

Maturity ``REFERENCE_GRADE_SHADOW_ONLY``: validated against this package's in-process
test issuer only; validation against a real enterprise issuer remains unproven.

Since 0.1.2 the adapter carries one narrowly scoped issuer profile beyond the RFC 9068
default: ``cloudflare-access`` (owner rulings AP3-D1 as amended 2026-09-11, AP3-D2,
AP3-D3), selected only by explicit configuration and changing nothing for any other
issuer. 0.1.3 applies the AP3-D1 amendment: an absent ``typ`` is admitted under that
profile, a present one must be ``JWT``, and ``alg`` must be ``RS256``.
"""

from __future__ import annotations

from .adapter import (
    ACCESS_TOKEN_TYPES,
    ALGORITHMS,
    CLOUDFLARE_ACCESS_TOKEN_TYPE,
    CLOUDFLARE_ALGORITHMS,
    CLOUDFLARE_REQUIRED_CLAIMS,
    REQUIRED_CLAIMS,
    JwtApproverIdentity,
    JwtApproverIdentityAdapter,
    Refusal,
)
from .config import (
    CLOUDFLARE_ACCESS_PROFILE,
    ISSUER_PROFILES,
    LOOPBACK_HOSTS,
    RFC9068_PROFILE,
    AdapterConfig,
)
from .errors import AdapterConfigurationError, KeyRetrievalFailed
from .keys import MAX_JWKS_BYTES, JwksKeyCache
from .version import ENFORCEMENT_ENABLED, ISSUER_VALIDATION, MATURITY, __version__

__all__ = [
    "__version__", "MATURITY", "ISSUER_VALIDATION", "ENFORCEMENT_ENABLED",
    "JwtApproverIdentityAdapter", "JwtApproverIdentity", "Refusal",
    "ALGORITHMS", "ACCESS_TOKEN_TYPES", "REQUIRED_CLAIMS",
    "CLOUDFLARE_ACCESS_TOKEN_TYPE", "CLOUDFLARE_ALGORITHMS", "CLOUDFLARE_REQUIRED_CLAIMS",
    "AdapterConfig", "LOOPBACK_HOSTS", "ISSUER_PROFILES", "RFC9068_PROFILE",
    "CLOUDFLARE_ACCESS_PROFILE",
    "JwksKeyCache", "MAX_JWKS_BYTES",
    "KeyRetrievalFailed", "AdapterConfigurationError",
]
