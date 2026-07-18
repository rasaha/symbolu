"""Frozen constants: versions, hash algorithms, and the ten domain tags.

Mirrors ACTION_CANONICALIZATION_AND_HASHING_SPEC.md §9, §17, §20.
"""

from __future__ import annotations

CANONICALIZATION_VERSION = "1"
ENVELOPE_SCHEMA_VERSION = "1.0.0"
# Identity-profile v2 (CER V0.1): identical canonicalization + hashing, but the
# action-identity projection excludes the decision-inert provenance fields
# (runtime, model_provider, objective). A distinct envelope_schema_version keeps
# a v1 and a v2 action_hash of the same envelope domain-separated (never
# confusable) even before their projected payloads differ. See projection.py.
ENVELOPE_SCHEMA_VERSION_V2 = "2.0.0"
DEFAULT_IDENTITY_PROFILE = "v1"
IDENTITY_PROFILES = frozenset({"v1", "v2"})
POLICY_SCHEMA_VERSION = "1.0.0"
SIGNATURE_FORMAT_VERSION = "ref-hmac-1"  # reference-only signing scheme (see signing.py)

DEFAULT_HASH_ALGORITHM_ID = "sha-256"

# hash_algorithm_id -> hashlib name
HASH_ALGORITHMS = {
    "sha-256": "sha256",
    "sha-512-256": "sha512_256",
}

# spec §9 — ten domains, versioned tags
_DOMAIN_PREFIX = "SYMBOLU/ACTIONGATE"
_DOMAIN_VER = "v1"
DOMAINS = (
    "ACTION",
    "APPROVAL",
    "POLICY",
    "EVIDENCE",
    "SIMULATION",
    "AUDIT_RECORD",
    "AUDIT_CHAIN",
    "DELEGATION",
    "EXECUTION_RESULT",
    "EXECUTION_TOKEN",
)


def domain_tag(domain: str) -> str:
    if domain not in DOMAINS:
        raise ValueError(f"unknown domain {domain!r}")
    return f"{_DOMAIN_PREFIX}/{domain}/{_DOMAIN_VER}"
