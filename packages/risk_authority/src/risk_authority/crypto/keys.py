"""Key material and a verification-key ring.

Authority signing keys are referenced by ``kid`` and rotated (spec §27). The
issuer holds a :class:`SigningKeyRecord`; the runtime hot path holds only a
:class:`KeyRing` of public verification keys so it can verify offline
(spec §5 hot path, §32 "Signature/key unknown -> DENY").

Key validity windows (issue #1398 / F-G item 2)
-----------------------------------------------
A key's validity window is a **half-open interval** ``[not_before, not_after)``:

===============================  ==========
condition                        verdict
===============================  ==========
``not_before`` absent            no lower bound
``not_after`` absent             no upper bound
``now < not_before``             invalid — not yet valid
``now == not_before``            **valid**
``now >= not_after``             invalid — expired
===============================  ==========

Both bounds absent therefore means unbounded-valid, which is what every existing
``SigningKeyRecord`` in the repository relies on and what the Policy Authority key
window (``ugence_policy_authority.core.signing``) already does.

**The envelope now shares this shape.** ``RiskAuthorizationEnvelope.is_temporally_valid``
is ``not_before <= now < expires_at``, so at exactly ``expires_at`` an envelope is expired,
exactly as a key is at ``not_after``. One rule covers both: *authority begins at the lower
bound and ends immediately upon reaching the upper bound.*

.. note:: **Superseded wording, retained for traceability.**

   This module previously said the two conventions "deliberately differ … and must not be
   conflated", on the reasoning that a key is a *credential* whose interval must be
   half-open so two adjacent rotation windows cannot both be valid at the instant they
   meet, while an envelope is a *grant* whose inclusive boundary was separately ratified.

   That argument was retired on review. It is sound about *overlap* — envelopes are never
   chained, since issuance always sets ``not_before`` to its own issuance instant, so no
   two envelope windows ever meet — but the absence of overlap never explained why a
   security validity artifact should remain usable at its own stated expiry. The practical
   evidence was that nothing downstream would honor it: at ``now == expires_at`` the
   credential broker derived a zero-width window and refused, and
   ``governance_contracts.Validity`` cannot construct ``issued_at == expires_at`` at all.
   The envelope was the last artifact still saying yes at an instant no consumer could act
   on. Changing it altered no signed field, canonical byte, digest or signature.

Before this, ``not_before`` / ``not_after`` were declared on ``SigningKeyRecord`` and read
nowhere: ``KeyRing.from_records`` discarded them, so no verification path could see a
window even in principle. :class:`VerificationKeyRecord` is what carries them through.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping, Optional, Union

from .signing import SigningKey, VerifyKey

__all__ = [
    "SigningKeyRecord",
    "VerificationKeyRecord",
    "KeyRing",
    "KeyWindowError",
    "key_window_valid_at",
    "validate_key_window",
]


class KeyWindowError(ValueError):
    """A key declares a structurally invalid validity window.

    Raised at construction, so a malformed window can never reach a signing or
    verification decision. A window with ``not_before >= not_after`` names an empty
    interval: no instant satisfies it, and silently treating that as "always invalid"
    would hide a configuration error behind a plausible-looking refusal.
    """


def validate_key_window(
    not_before: Optional[datetime], not_after: Optional[datetime], *, owner: str
) -> None:
    """Structural validation. Fails closed before signing or verification (ruling 1)."""

    for name, value in (("not_before", not_before), ("not_after", not_after)):
        if value is not None and not isinstance(value, datetime):
            raise KeyWindowError(f"{owner}.{name} must be a datetime or None")
    if not_before is not None and not_after is not None and not_before >= not_after:
        raise KeyWindowError(
            f"{owner} declares an empty validity window: not_before {not_before!r} "
            f"is not before not_after {not_after!r}")


def key_window_valid_at(
    now: datetime, *, not_before: Optional[datetime], not_after: Optional[datetime]
) -> bool:
    """The half-open key-validity predicate: ``[not_before, not_after)``.

    The single definition both the issuer and the verifier use, so the two paths cannot
    drift apart on the boundary.
    """

    if not_before is not None and now < not_before:
        return False
    if not_after is not None and now >= not_after:
        return False
    return True


@dataclass(frozen=True)
class SigningKeyRecord:
    """A named signing key held by the authority (issuance side)."""

    key_id: str
    signing_key: SigningKey
    not_before: Optional[datetime] = None
    not_after: Optional[datetime] = None

    def __post_init__(self) -> None:
        validate_key_window(self.not_before, self.not_after, owner="SigningKeyRecord")

    @property
    def verify_key(self) -> VerifyKey:
        return self.signing_key.verify_key

    def is_valid_at(self, now: datetime) -> bool:
        return key_window_valid_at(
            now, not_before=self.not_before, not_after=self.not_after)

    def verification_record(self) -> "VerificationKeyRecord":
        """The public half, window included — what belongs on the runtime hot path."""

        return VerificationKeyRecord(
            verify_key=self.verify_key,
            not_before=self.not_before,
            not_after=self.not_after,
        )


@dataclass(frozen=True)
class VerificationKeyRecord:
    """A public verification key together with its validity window.

    What a :class:`KeyRing` holds. Immutable, and validated at construction so a
    malformed window cannot reach :meth:`KeyRing.resolve_record`.
    """

    verify_key: VerifyKey
    not_before: Optional[datetime] = None
    not_after: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not isinstance(self.verify_key, VerifyKey):
            raise KeyWindowError("VerificationKeyRecord.verify_key must be a VerifyKey")
        validate_key_window(self.not_before, self.not_after, owner="VerificationKeyRecord")

    @property
    def bounded(self) -> bool:
        return self.not_before is not None or self.not_after is not None

    def is_valid_at(self, now: datetime) -> bool:
        return key_window_valid_at(
            now, not_before=self.not_before, not_after=self.not_after)


_KeyEntry = Union[VerifyKey, VerificationKeyRecord]


def _as_record(value: _KeyEntry) -> VerificationKeyRecord:
    """Normalize a ring entry. A bare ``VerifyKey`` is an unbounded key (ruling 1)."""

    if isinstance(value, VerificationKeyRecord):
        return value
    if isinstance(value, VerifyKey):
        return VerificationKeyRecord(verify_key=value)
    raise KeyWindowError(
        "KeyRing entries must be a VerifyKey or a VerificationKeyRecord, "
        f"got {type(value).__name__}")


@dataclass(frozen=True)
class KeyRing:
    """A ring of public verification keys and their windows, indexed by ``kid``.

    The runtime resolves a key by ``kid`` before verifying an envelope signature; an
    unknown ``kid`` yields ``None`` and the caller denies.

    Entries are normalized to :class:`VerificationKeyRecord` at construction, so a ring
    built from bare ``VerifyKey`` values keeps working and its keys are unbounded.
    """

    keys: Mapping[str, _KeyEntry] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "keys", {k: _as_record(v) for k, v in dict(self.keys).items()})

    def resolve(self, key_id: str) -> Optional[VerifyKey]:
        """Raw, **non-validating** lookup: the bare key, with no window check.

        Retained for compatibility. It cannot enforce a window — it takes no instant —
        so nothing that makes a trust decision may use it. Signature verification must
        go through :meth:`resolve_record` and check
        :meth:`VerificationKeyRecord.is_valid_at`. See
        ``tests/unit/test_key_windows.py`` for the boundary test that pins this.
        """

        record = self.keys.get(key_id)
        return record.verify_key if record is not None else None

    def resolve_record(self, key_id: str) -> Optional[VerificationKeyRecord]:
        """Resolve the key **with** its validity window. The verification-side entry point."""

        return self.keys.get(key_id)

    def with_key(
        self, key_id: str, verify_key: _KeyEntry,
        *, not_before: Optional[datetime] = None, not_after: Optional[datetime] = None,
    ) -> "KeyRing":
        """Add a key. A bare ``VerifyKey`` with no bounds stays unbounded-valid."""

        if isinstance(verify_key, VerifyKey) and (not_before is not None or not_after is not None):
            entry: _KeyEntry = VerificationKeyRecord(
                verify_key=verify_key, not_before=not_before, not_after=not_after)
        else:
            entry = verify_key
        merged = dict(self.keys)
        merged[key_id] = _as_record(entry)
        return KeyRing(merged)

    @classmethod
    def from_records(cls, records: "list[SigningKeyRecord]") -> "KeyRing":
        """Build a ring from signing records, **retaining** each key's window.

        Previously this dropped ``not_before`` / ``not_after``, which is why no
        verification path could enforce them (issue #1398).
        """

        return cls({r.key_id: r.verification_record() for r in records})
