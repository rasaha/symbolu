"""Deterministic, offline signing for the HiringWorkflowIR.

Consistent with this package's "deterministic, offline, in-memory adapters
only" boundary: the default signer is a keyed HMAC-SHA256 over the IR content
digest. It is reproducible (same digest + same key → same signature) and needs
no network, HSM, or key-management service. Production deployments inject a real
signer implementing the :class:`Signer` protocol; the core never requires one.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Protocol, runtime_checkable

from ..domain.base import DomainModel
from ..errors import DomainValidationError
from .errors import SignatureError


class IRSignature(DomainModel):
    """A detached signature over an IR content digest."""

    alg: str
    key_id: str
    value: str

    def _validate_fields(self) -> None:
        for field in ("alg", "key_id", "value"):
            if not getattr(self, field).strip():
                raise DomainValidationError(f"signature.{field} is required")


@runtime_checkable
class Signer(Protocol):
    """Produces and verifies detached signatures over an IR content digest."""

    @property
    def alg(self) -> str: ...

    @property
    def key_id(self) -> str: ...

    def sign(self, content_digest: str) -> IRSignature: ...

    def verify(self, content_digest: str, signature: IRSignature) -> bool: ...


class DeterministicHMACSigner:
    """Offline HMAC-SHA256 signer. Reproducible and dependency-free."""

    def __init__(self, *, key_id: str = "dev-hmac-key", secret: bytes = b"ugence-ai-hiring-dev") -> None:
        if not key_id.strip():
            raise DomainValidationError("key_id is required")
        self._key_id = key_id
        self._secret = secret

    @property
    def alg(self) -> str:
        return "hmac-sha256"

    @property
    def key_id(self) -> str:
        return self._key_id

    def _mac(self, content_digest: str) -> str:
        if not content_digest.strip():
            raise SignatureError("cannot sign an empty content digest")
        return hmac.new(self._secret, content_digest.encode("utf-8"), hashlib.sha256).hexdigest()

    def sign(self, content_digest: str) -> IRSignature:
        return IRSignature(alg=self.alg, key_id=self._key_id, value=self._mac(content_digest))

    def verify(self, content_digest: str, signature: IRSignature) -> bool:
        if signature.key_id != self._key_id or signature.alg != self.alg:
            return False
        return hmac.compare_digest(signature.value, self._mac(content_digest))
