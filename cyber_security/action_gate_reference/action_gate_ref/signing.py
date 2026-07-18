"""Reference-only signing scheme.

The harness signs digests with HMAC-SHA256 over a named test key. This is a
**stand-in** for the production scheme (asymmetric signatures — Ed25519/ECDSA —
via an audited crypto library, with real key custody). Production key custody
and asymmetric signing are OUT OF SCOPE for this reference harness (see README).
"""

from __future__ import annotations

import hashlib
import hmac

# Deterministic reference keyring (test keys only — NOT secret, NOT production).
_TEST_KEYRING = {
    "gate": b"REF-TEST-KEY/gate",
    "audit": b"REF-TEST-KEY/audit",
    "root_of_trust": b"REF-TEST-KEY/root",
    "approver:security-lead": b"REF-TEST-KEY/approver/security-lead",
    "approver:sre-lead": b"REF-TEST-KEY/approver/sre-lead",
    "approver:budget-owner": b"REF-TEST-KEY/approver/budget-owner",
    "approver:comms-owner": b"REF-TEST-KEY/approver/comms-owner",
}


def _key(key_id: str) -> bytes:
    if key_id not in _TEST_KEYRING:
        raise KeyError(f"unknown reference key_id {key_id!r}")
    return _TEST_KEYRING[key_id]


def sign(key_id: str, digest_hex: str) -> str:
    """Reference signature over a hex digest (HMAC-SHA256)."""
    return hmac.new(_key(key_id), digest_hex.encode("ascii"), hashlib.sha256).hexdigest()


def verify(key_id: str, digest_hex: str, signature_hex: str) -> bool:
    try:
        expected = sign(key_id, digest_hex)
    except KeyError:
        return False
    return hmac.compare_digest(expected, signature_hex)
