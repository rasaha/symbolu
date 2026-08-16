"""Injected signing / verification interfaces and the key ring (GV-2C-b §7).

The authority never signs directly: it talks only to the
:class:`PolicySigner` and :class:`PolicySignatureVerifier` protocols, so a
deployment can substitute an HSM- or KMS-backed implementation without any
caller change — the same seam the repository's existing authority uses.

Three rules are enforced structurally here rather than by convention:

* **no private key in a contract object** — a signer holds its
  :class:`~ugence_uvi_policy_authority.ed25519.SigningKey`; no record, result,
  or registry entry has a field capable of carrying one;
* **a caller cannot supply signature bytes** — the issuance and revocation
  entry points take no signature parameter; the signature is produced inside
  the service from the signer it was given;
* **keys resolve by exact ``key_id``** — an unknown, revoked, out-of-window,
  wrong-authority or wrong-tenant key fails closed with a distinct typed
  status, and the verifier reports the reason rather than a bare boolean.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping, Optional, Protocol, runtime_checkable

from .ed25519 import SIGNATURE_ALG, SigningKey, VerifyKey
from .errors import PolicyAuthorityRequestError, PolicySigningError
from .statuses import KeyVerificationStatus

__all__ = [
    "SIGNATURE_ALG",
    "PolicySigner",
    "PolicySignatureVerifier",
    "KeyVerification",
    "PolicyVerificationKey",
    "PolicyKeyRing",
    "Ed25519PolicySigner",
    "DenyAllSignatureVerifier",
]


@dataclass(frozen=True)
class KeyVerification:
    """The structured outcome of resolving a key and checking a signature."""

    status: KeyVerificationStatus
    key_id: str
    authority_id: str = ""
    detail: str = ""

    @property
    def valid(self) -> bool:
        return self.status is KeyVerificationStatus.VALID


@runtime_checkable
class PolicySigner(Protocol):
    """Produce an authority signature over an exact byte payload."""

    @property
    def authority_id(self) -> str:
        """Identity of the issuing authority this signer speaks for."""
        ...

    @property
    def key_id(self) -> str:
        """Exact key identifier a verifier will resolve to check the result."""
        ...

    @property
    def signature_alg(self) -> str:
        """Signature algorithm identifier bound into the signed payload."""
        ...

    def sign(self, payload: bytes) -> bytes:
        """Return the signature over ``payload``."""
        ...


@runtime_checkable
class PolicySignatureVerifier(Protocol):
    """Resolve a key by exact ``key_id`` and verify a signature under it."""

    def verify(
        self,
        *,
        key_id: str,
        payload: bytes,
        signature: bytes,
        expected_authority_id: str,
        expected_tenant_id: str,
        as_of: datetime,
    ) -> KeyVerification:
        """Return a structured verification, never raising for a plain refusal."""
        ...


@dataclass(frozen=True)
class PolicyVerificationKey:
    """A registered public verification key.

    A key is bound to exactly one issuing authority and, optionally, to one
    tenant. A tenant-bound key can never verify another tenant's issuance, so a
    compromised tenant key cannot mint global policy.
    """

    key_id: str
    verify_key: VerifyKey
    authority_id: str
    tenant_id: str = ""
    not_before: Optional[datetime] = None
    not_after: Optional[datetime] = None
    revoked: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.key_id, str) or not self.key_id.strip():
            raise PolicyAuthorityRequestError("PolicyVerificationKey.key_id must be non-empty")
        if not isinstance(self.verify_key, VerifyKey):
            raise PolicyAuthorityRequestError(
                "PolicyVerificationKey.verify_key must be a VerifyKey"
            )
        if not isinstance(self.authority_id, str) or not self.authority_id.strip():
            raise PolicyAuthorityRequestError(
                "PolicyVerificationKey.authority_id must be non-empty"
            )
        for name in ("not_before", "not_after"):
            value = getattr(self, name)
            if value is not None and (
                not isinstance(value, datetime)
                or value.tzinfo is None
                or value.tzinfo.utcoffset(value) is None
            ):
                raise PolicyAuthorityRequestError(
                    f"PolicyVerificationKey.{name} must be timezone-aware"
                )

    def revoke(self) -> "PolicyVerificationKey":
        """Return a revoked copy. Key revocation is distinct from policy revocation."""

        from dataclasses import replace

        return replace(self, revoked=True)


@dataclass(frozen=True)
class PolicyKeyRing:
    """An immutable ring of verification keys, indexed by exact ``key_id``.

    Implements :class:`PolicySignatureVerifier`. Resolution is by exact key id
    only — there is no "current key", no newest-key fallback, and no algorithm
    negotiation, so a signature can never be checked against a key other than
    the one it names.
    """

    keys: Mapping[str, PolicyVerificationKey] = field(default_factory=dict)

    def with_key(self, key: PolicyVerificationKey) -> "PolicyKeyRing":
        merged = dict(self.keys)
        merged[key.key_id] = key
        return PolicyKeyRing(merged)

    def resolve(self, key_id: str) -> Optional[PolicyVerificationKey]:
        return self.keys.get(key_id)

    def verify(
        self,
        *,
        key_id: str,
        payload: bytes,
        signature: bytes,
        expected_authority_id: str,
        expected_tenant_id: str,
        as_of: datetime,
    ) -> KeyVerification:
        key = self.keys.get(key_id)
        if key is None:
            return KeyVerification(
                status=KeyVerificationStatus.UNKNOWN_KEY,
                key_id=key_id,
                detail="no key registered under this key_id",
            )
        if key.revoked:
            return KeyVerification(
                status=KeyVerificationStatus.REVOKED_KEY,
                key_id=key_id,
                authority_id=key.authority_id,
                detail="signing key revoked",
            )
        if key.authority_id != expected_authority_id:
            return KeyVerification(
                status=KeyVerificationStatus.WRONG_AUTHORITY,
                key_id=key_id,
                authority_id=key.authority_id,
                detail=(
                    f"key belongs to {key.authority_id!r}, artifact names "
                    f"{expected_authority_id!r}"
                ),
            )
        # A key bound to a tenant may only verify that tenant's artifacts. An
        # unbound (global) key may verify any tenant's.
        if key.tenant_id and key.tenant_id != expected_tenant_id:
            return KeyVerification(
                status=KeyVerificationStatus.WRONG_TENANT,
                key_id=key_id,
                authority_id=key.authority_id,
                detail=f"key is bound to tenant {key.tenant_id!r}",
            )
        if key.not_before is not None and as_of < key.not_before:
            return KeyVerification(
                status=KeyVerificationStatus.KEY_NOT_IN_WINDOW,
                key_id=key_id,
                authority_id=key.authority_id,
                detail="key not yet valid",
            )
        if key.not_after is not None and as_of >= key.not_after:
            return KeyVerification(
                status=KeyVerificationStatus.KEY_NOT_IN_WINDOW,
                key_id=key_id,
                authority_id=key.authority_id,
                detail="key expired",
            )
        if not key.verify_key.verify(payload, signature):
            return KeyVerification(
                status=KeyVerificationStatus.INVALID_SIGNATURE,
                key_id=key_id,
                authority_id=key.authority_id,
                detail="signature did not verify under the named key",
            )
        return KeyVerification(
            status=KeyVerificationStatus.VALID,
            key_id=key_id,
            authority_id=key.authority_id,
        )


@dataclass(frozen=True)
class Ed25519PolicySigner:
    """Reference :class:`PolicySigner` over the RFC 8032 implementation.

    Holds the private seed and nothing else; the seed is reachable only through
    this object and never lands in a record. Swap for an HSM/KMS-backed signer
    in production — the protocol is identical.
    """

    _authority_id: str
    _key_id: str
    _signing_key: SigningKey

    def __init__(self, *, authority_id: str, key_id: str, signing_key: SigningKey) -> None:
        if not isinstance(authority_id, str) or not authority_id.strip():
            raise PolicyAuthorityRequestError("Ed25519PolicySigner.authority_id must be non-empty")
        if not isinstance(key_id, str) or not key_id.strip():
            raise PolicyAuthorityRequestError("Ed25519PolicySigner.key_id must be non-empty")
        if not isinstance(signing_key, SigningKey):
            raise PolicyAuthorityRequestError(
                "Ed25519PolicySigner.signing_key must be a SigningKey"
            )
        object.__setattr__(self, "_authority_id", authority_id)
        object.__setattr__(self, "_key_id", key_id)
        object.__setattr__(self, "_signing_key", signing_key)

    @property
    def authority_id(self) -> str:
        return self._authority_id

    @property
    def key_id(self) -> str:
        return self._key_id

    @property
    def signature_alg(self) -> str:
        return SIGNATURE_ALG

    def sign(self, payload: bytes) -> bytes:
        if not isinstance(payload, (bytes, bytearray)):
            raise PolicySigningError("signing payload must be bytes")
        return self._signing_key.sign(bytes(payload))

    def verification_key(
        self,
        *,
        tenant_id: str = "",
        not_before: Optional[datetime] = None,
        not_after: Optional[datetime] = None,
    ) -> PolicyVerificationKey:
        """Publish this signer's public half for registration in a key ring."""

        return PolicyVerificationKey(
            key_id=self._key_id,
            verify_key=self._signing_key.verify_key,
            authority_id=self._authority_id,
            tenant_id=tenant_id,
            not_before=not_before,
            not_after=not_after,
        )

    def __repr__(self) -> str:  # pragma: no cover - defensive
        return f"Ed25519PolicySigner(authority_id={self._authority_id!r}, key_id={self._key_id!r})"


class DenyAllSignatureVerifier:
    """The deny-by-default :class:`PolicySignatureVerifier`.

    Used when no key ring is configured: every resolution fails closed rather
    than accepting an unverifiable issuance.
    """

    def verify(
        self,
        *,
        key_id: str,
        payload: bytes,
        signature: bytes,
        expected_authority_id: str,
        expected_tenant_id: str,
        as_of: datetime,
    ) -> KeyVerification:
        return KeyVerification(
            status=KeyVerificationStatus.NO_VERIFIER_CONFIGURED,
            key_id=key_id,
            detail="no signature verifier configured; resolution denied by default",
        )
