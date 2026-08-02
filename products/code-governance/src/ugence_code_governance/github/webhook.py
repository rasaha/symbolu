"""Pure GitHub webhook HMAC verification helper.

Read-only and side-effect free. This helper NEVER stores the secret and NEVER
makes a network call — it only computes and constant-time-compares an HMAC-SHA256
signature the way GitHub's ``X-Hub-Signature-256`` header is produced.

Secrets are the caller's responsibility; they are not placed on any product
model. Callers pass the raw request body and the header value.
"""
from __future__ import annotations

import hashlib
import hmac

_PREFIX = "sha256="


def compute_signature(secret: str, payload: bytes) -> str:
    """Return the ``sha256=<hex>`` signature GitHub would send for ``payload``."""
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return _PREFIX + digest


def verify_signature(secret: str, payload: bytes, signature_header: str) -> bool:
    """Constant-time verify a GitHub ``X-Hub-Signature-256`` header.

    Returns ``True`` only when the header matches the HMAC of ``payload`` under
    ``secret``. A missing/blank header returns ``False`` (fail closed).
    """
    if not signature_header:
        return False
    expected = compute_signature(secret, payload)
    return hmac.compare_digest(expected, signature_header.strip())


__all__ = ["compute_signature", "verify_signature"]
