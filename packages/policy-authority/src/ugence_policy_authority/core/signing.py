"""Injected signing interfaces and immutable trust anchors (ADR §14, §15).

The authority never signs directly: it talks only to the :class:`PolicySigner`
and :class:`PolicySignatureVerifier` protocols, so a deployment can substitute
an HSM- or KMS-backed implementation without any caller change.

Three rules are structural rather than conventional:

* **no private key in a contract object** — a signer holds its
  :class:`~ugence_policy_authority.core.ed25519.SigningKey`; no record, result
  or registry entry has a field able to carry one, and no ``repr`` discloses
  one;
* **a caller cannot supply signature bytes** — the issuance and revocation
  entry points take no signature parameter;
* **trust anchors are immutable** — :class:`PolicyKeyRing` defensively copies
  every caller mapping and exposes only a ``MappingProxyType`` view, so a
  caller that mutates the dict it passed in cannot alter the authority's trust
  state afterwards.

Keys resolve by **exact ``key_id``** and carry an **entitlement** set, so a key
authorized to issue is not thereby authorized to revoke.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from types import MappingProxyType
from typing import Iterable, Mapping, Optional, Protocol, runtime_checkable

from .canonical import require_tzaware
from .ed25519 import SIGNATURE_ALG, SigningKey, VerifyKey
from .errors import PolicyAuthorityRequestError, PolicySigningError
from .statuses import KeyEntitlement, KeyVerificationStatus

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
    """The structured outcome of resolving a trust anchor and checking a signature."""

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
        """Identity of the authority this signer speaks for."""
        ...

    @property
    def key_id(self) -> str:
        """Exact key identifier a verifier resolves to check the result."""
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
    """Resolve a trust anchor by exact ``key_id`` and verify a signature under it."""

    def verify(
        self,
        *,
        key_id: str,
        payload: bytes,
        signature: bytes,
        expected_authority_id: str,
        expected_tenant_id: str,
        required_entitlement: KeyEntitlement,
        as_of: datetime,
    ) -> KeyVerification:
        """Return a structured verification, never raising for a plain refusal."""
        ...


@dataclass(frozen=True)
class PolicyVerificationKey:
    """A registered trust anchor.

    Bound to exactly one authority and, optionally, one tenant, with an explicit
    validity window, algorithm, key id and entitlement set. A tenant-bound key
    can never verify another tenant's artifact, and an issue-only key can never
    authorize a revocation.
    """

    key_id: str
    verify_key: VerifyKey
    authority_id: str
    tenant_id: str = ""
    not_before: Optional[datetime] = None
    not_after: Optional[datetime] = None
    revoked: bool = False
    signature_alg: str = SIGNATURE_ALG
    entitlements: frozenset = frozenset({KeyEntitlement.ISSUE_POLICY})

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
        if not isinstance(self.tenant_id, str):
            raise PolicyAuthorityRequestError("PolicyVerificationKey.tenant_id must be a string")
        for name in ("not_before", "not_after"):
            value = getattr(self, name)
            if value is not None:
                require_tzaware(value, path=f"PolicyVerificationKey.{name}")
        # Defensive copy into an immutable frozenset, validated member by member.
        entitlements = frozenset(self.entitlements)
        for entitlement in entitlements:
            if not isinstance(entitlement, KeyEntitlement):
                raise PolicyAuthorityRequestError(
                    "PolicyVerificationKey.entitlements entries must be KeyEntitlement"
                )
        if not entitlements:
            raise PolicyAuthorityRequestError(
                "PolicyVerificationKey.entitlements must grant at least one capability"
            )
        object.__setattr__(self, "entitlements", entitlements)

    def revoke(self) -> "PolicyVerificationKey":
        """Return a revoked copy. Key revocation is not policy-version revocation."""

        return replace(self, revoked=True)


class PolicyKeyRing:
    """An immutable ring of trust anchors, indexed by exact ``key_id``.

    Implements :class:`PolicySignatureVerifier`. Resolution is by exact key id
    only — no "current key", no newest-key fallback, no algorithm negotiation.

    The constructor **copies** whatever mapping or iterable it is given; the
    internal store is a ``MappingProxyType`` over that private copy, and
    :attr:`keys` returns that read-only view. Mutating the mapping you passed
    in, or the view you got back, cannot change the authority's trust state.
    """

    __slots__ = ("_keys",)

    def __init__(
        self,
        keys: "Mapping[str, PolicyVerificationKey] | Iterable[PolicyVerificationKey] | None" = None,
    ) -> None:
        collected: dict[str, PolicyVerificationKey] = {}
        if keys is None:
            pass
        elif isinstance(keys, Mapping):
            for key_id, key in keys.items():
                self._validate(key_id, key)
                collected[key_id] = key
        else:
            for key in keys:
                self._validate(getattr(key, "key_id", None), key)
                collected[key.key_id] = key
        object.__setattr__(self, "_keys", MappingProxyType(collected))

    def __setattr__(self, name: str, value: object) -> None:
        # The trust store is not rebindable after construction: replacing
        # ``_keys`` wholesale would be exactly the attacker-key injection the
        # defensive copy and the read-only view exist to prevent.
        raise AttributeError(
            f"PolicyKeyRing is immutable; cannot set {name!r}. Build a new ring with "
            "with_key() instead."
        )

    def __delattr__(self, name: str) -> None:
        raise AttributeError(f"PolicyKeyRing is immutable; cannot delete {name!r}")

    @staticmethod
    def _validate(key_id: object, key: object) -> None:
        if not isinstance(key, PolicyVerificationKey):
            raise PolicyAuthorityRequestError(
                "PolicyKeyRing entries must be PolicyVerificationKey instances"
            )
        if key_id != key.key_id:
            raise PolicyAuthorityRequestError(
                f"PolicyKeyRing mapping key {key_id!r} does not match the anchor's "
                f"key_id {key.key_id!r}"
            )

    @property
    def keys(self) -> "Mapping[str, PolicyVerificationKey]":
        """A read-only view. Mutating it raises; it never exposes internal state."""

        return self._keys

    def with_key(self, key: PolicyVerificationKey) -> "PolicyKeyRing":
        """Return a *new* ring with ``key`` added or replaced. This ring is unchanged."""

        merged = dict(self._keys)
        self._validate(getattr(key, "key_id", None), key)
        merged[key.key_id] = key
        return PolicyKeyRing(merged)

    def resolve(self, key_id: str) -> Optional[PolicyVerificationKey]:
        return self._keys.get(key_id)

    def __repr__(self) -> str:  # pragma: no cover - defensive
        return f"PolicyKeyRing({sorted(self._keys)!r})"

    def verify(
        self,
        *,
        key_id: str,
        payload: bytes,
        signature: bytes,
        expected_authority_id: str,
        expected_tenant_id: str,
        required_entitlement: KeyEntitlement = KeyEntitlement.ISSUE_POLICY,
        as_of: datetime,
    ) -> KeyVerification:
        key = self._keys.get(key_id)
        if key is None:
            return KeyVerification(
                status=KeyVerificationStatus.UNKNOWN_KEY,
                key_id=key_id if isinstance(key_id, str) else "",
                detail="no trust anchor registered under this key_id",
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
        # A tenant-bound key may only serve that tenant. An unbound (global) key
        # may serve any tenant of its authority.
        if key.tenant_id and key.tenant_id != expected_tenant_id:
            return KeyVerification(
                status=KeyVerificationStatus.WRONG_TENANT,
                key_id=key_id,
                authority_id=key.authority_id,
                detail=f"key is bound to a different tenant",
            )
        if required_entitlement not in key.entitlements:
            return KeyVerification(
                status=KeyVerificationStatus.NOT_ENTITLED,
                key_id=key_id,
                authority_id=key.authority_id,
                detail=f"key is not entitled to {required_entitlement.value}",
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
            status=KeyVerificationStatus.VALID, key_id=key_id, authority_id=key.authority_id
        )


class Ed25519PolicySigner:
    """Reference :class:`PolicySigner` over the RFC 8032 implementation.

    Holds the private seed and nothing else; the seed is reachable only through
    this object, never lands in a record, and never appears in a ``repr``. Swap
    for an HSM/KMS-backed signer in production — the protocol is identical.
    """

    __slots__ = ("_authority_id", "_key_id", "_signing_key")

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
        entitlements: Iterable[KeyEntitlement] = (KeyEntitlement.ISSUE_POLICY,),
    ) -> PolicyVerificationKey:
        """Publish this signer's public half for registration as a trust anchor."""

        return PolicyVerificationKey(
            key_id=self._key_id,
            verify_key=self._signing_key.verify_key,
            authority_id=self._authority_id,
            tenant_id=tenant_id,
            not_before=not_before,
            not_after=not_after,
            entitlements=frozenset(entitlements),
        )

    def __repr__(self) -> str:  # pragma: no cover - defensive
        return f"Ed25519PolicySigner(authority_id={self._authority_id!r}, key_id={self._key_id!r})"


class DenyAllSignatureVerifier:
    """The deny-by-default :class:`PolicySignatureVerifier`.

    Used when no trust anchors are configured: every resolution fails closed
    rather than accepting an unverifiable issuance or revocation.
    """

    def verify(
        self,
        *,
        key_id: str,
        payload: bytes,
        signature: bytes,
        expected_authority_id: str,
        expected_tenant_id: str,
        required_entitlement: KeyEntitlement = KeyEntitlement.ISSUE_POLICY,
        as_of: datetime,
    ) -> KeyVerification:
        return KeyVerification(
            status=KeyVerificationStatus.NO_VERIFIER_CONFIGURED,
            key_id=key_id if isinstance(key_id, str) else "",
            detail="no signature verifier configured; denied by default",
        )
