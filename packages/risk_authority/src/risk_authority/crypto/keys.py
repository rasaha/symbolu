"""Key material and a verification-key ring.

Authority signing keys are referenced by ``kid`` and rotated (spec §27). The
issuer holds a :class:`SigningKeyRecord`; the runtime hot path holds only a
:class:`KeyRing` of public verification keys so it can verify offline
(spec §5 hot path, §32 "Signature/key unknown -> DENY").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping, Optional

from .signing import SigningKey, VerifyKey

__all__ = ["SigningKeyRecord", "KeyRing"]


@dataclass(frozen=True)
class SigningKeyRecord:
    """A named signing key held by the authority (issuance side)."""

    key_id: str
    signing_key: SigningKey
    not_before: Optional[datetime] = None
    not_after: Optional[datetime] = None

    @property
    def verify_key(self) -> VerifyKey:
        return self.signing_key.verify_key


@dataclass(frozen=True)
class KeyRing:
    """A ring of public verification keys, indexed by ``kid``.

    The runtime resolves a key by ``kid`` before verifying an envelope
    signature; an unknown ``kid`` yields ``None`` and the caller denies.
    """

    keys: Mapping[str, VerifyKey] = field(default_factory=dict)

    def resolve(self, key_id: str) -> Optional[VerifyKey]:
        return self.keys.get(key_id)

    def with_key(self, key_id: str, verify_key: VerifyKey) -> "KeyRing":
        merged = dict(self.keys)
        merged[key_id] = verify_key
        return KeyRing(merged)

    @classmethod
    def from_records(cls, records: "list[SigningKeyRecord]") -> "KeyRing":
        return cls({r.key_id: r.verify_key for r in records})
