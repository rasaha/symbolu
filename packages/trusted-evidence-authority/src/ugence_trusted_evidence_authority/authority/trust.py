"""Trust anchors, key lifecycle, revocation, and exact-coordinate resolution.

ADR §30 assigns "trust anchors, key trust/revocation" to TEV-2. E-5 fixes where
they come from: "trust anchors and verifier entitlements are configured at the
**composition root**, never supplied by the caller of verification and never
self-declared inside the artifact". E-8 fixes what happens when there are none:
"the production default is **deny**".

Resolution is exact-coordinate only
-----------------------------------
A trust anchor is found by the exact triple
``(authority_id, key_id, capability)`` and nothing else. There is deliberately:

* no ``latest()`` and no "current key";
* no implicit default key and no ambient fallback anchor;
* no partial-match, prefix-match or fuzzy lookup;
* no acceptance on an authority **name** alone — ADR §10.3 lists "a string
  naming a verifier" among the enumerated non-proofs;
* no first-key-wins behaviour, because duplicate coordinates never enter a
  directory in the first place;
* no algorithm negotiation — a resolved anchor whose profile is not the one the
  artifact names is a refusal, not a re-try under another profile.

ADR §26.9 is the rule underneath all of these: "guessing is prohibited … a
guessed supersession is an unsigned authority decision". Guessing *which key*
is the same species of unsigned decision.

Resolution authorizes nothing
-----------------------------
:meth:`TrustAnchorResolverPort.resolve` answers "is there a configured,
currently-valid, unrevoked anchor at this exact coordinate?" and stops. It
performs no signature check, admits no evidence, and issues no receipt. A
resolved anchor is an input to verification, never a substitute for it — ADR
§8.1.3, "possession is not validity", applied to key material.

Private key material never appears here
---------------------------------------
:class:`TrustAnchorRecord` carries a **public** key as canonical hex and nothing
else. There is no field that can hold a seed, and the canonical encoder rejects
``bytes`` outright, so no private material can reach a record, a digest, a
canonical byte sequence, a ``repr`` or an audit trail even by mistake. Signing
keys live only behind :class:`~.signing.ReceiptSignerPort`, at the composition
root (DD-10).

Two capabilities, never one key
-------------------------------
:class:`TrustAnchorCapability` splits producing evidence from issuing receipts.
This is ADR E-3 and §8.1.1 — "an evidence producer cannot verify its own
evidence" — made structural rather than conventional: an anchor entitled to
``EVIDENCE_PRODUCTION`` can never satisfy a receipt-issuance resolution, and the
reverse, so one key physically cannot occupy both roles. A record naming both is
not representable: the field holds exactly one member.

Time and revocation are explicit inputs
---------------------------------------
No method here reads a clock (§22.9). Every lifecycle question takes an explicit
timezone-aware instant (§22.10). Key validity is the half-open interval
``[effective_from, effective_to)`` of §17.9, and revocation carries its own
effective instant so "revoked" is always "revoked *as of when*".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Iterable, Optional, Protocol, runtime_checkable

from ..contracts._validation import (
    require_aware_datetime,
    require_canonical_str,
    require_exact_type,
    require_identifier,
    require_optional_aware_datetime,
    require_strictly_before,
)
from ..contracts.canonical import (
    TRUST_ANCHOR_RECORD_DIGEST_DOMAIN,
    canonical_bytes,
    canonical_digest,
)
from ..contracts.errors import TrustedEvidenceContractError
from ..contracts.reasons import TrustedEvidenceRefusalReason
from .ed25519 import TrustedEvidenceVerificationKey
from .profile import (
    TRUSTED_EVIDENCE_SIGNATURE_ENCODING_V1,
    TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1,
    decode_public_key,
)

__all__ = [
    "TRUST_ANCHOR_RECORD_DIGEST_DOMAIN",
    "TrustAnchorCapability",
    "TrustAnchorCoordinate",
    "KeyRevocation",
    "TrustAnchorRecord",
    "TrustAnchorResolution",
    "TrustAnchorResolverPort",
    "StaticTrustAnchorDirectory",
    "DenyAllTrustAnchorDirectory",
]

_R = TrustedEvidenceRefusalReason

# The trust-anchor digest domain lives in :mod:`..contracts.canonical` with every
# other domain tag — one module owns domain selection, so a second definition
# here could drift from the one the encoder actually frames. It is re-exported
# for the curated API's convenience and is the identical object.


class TrustAnchorCapability(str, Enum):
    """What one trust anchor is entitled to do. Exactly one per anchor.

    ADR §8.1.1 and E-3 rule that an evidence producer cannot verify its own
    evidence, and §8's role matrix keeps "evidence producer / source" (row 1)
    and "evidence-verification receipt issuer" (row 4) as separate rows that
    "no row may absorb". Holding the capability as a single-valued field rather
    than a set makes the separation unrepresentable to violate: there is no way
    to spell an anchor that both produces evidence and issues receipts.
    """

    #: The anchor's key signs **evidence** on behalf of a producer. Verifying
    #: such a signature establishes ADR §12 stage 2 for that evidence, and
    #: nothing else — §12 stage 2 "establishes nothing about where the content
    #: came from" beyond the key that signed it.
    EVIDENCE_PRODUCTION = "EVIDENCE_PRODUCTION"
    #: The anchor's key signs **receipts** on behalf of the verifying authority
    #: (ADR §8 role 4, E-11). It may never sign evidence.
    RECEIPT_ISSUANCE = "RECEIPT_ISSUANCE"


@dataclass(frozen=True)
class TrustAnchorCoordinate:
    """The exact triple a trust anchor is looked up by. No other lookup exists.

    Immutable, hashable and canonicalizable. Two coordinates are equal only when
    all three components are equal — there is no normalization, no case folding
    and no wildcard, so a near-miss is a miss.
    """

    authority_id: str
    key_id: str
    capability: TrustAnchorCapability

    def __post_init__(self) -> None:
        require_identifier(self.authority_id, "TrustAnchorCoordinate.authority_id")
        require_identifier(self.key_id, "TrustAnchorCoordinate.key_id")
        require_exact_type(
            self.capability,
            TrustAnchorCapability,
            "TrustAnchorCoordinate.capability",
        )

    def canonical_bytes(self) -> bytes:
        """The exact bytes :meth:`canonical_digest` is computed over."""

        return canonical_bytes(self)

    def canonical_digest(self) -> str:
        """Deterministic sha-256 over the coordinate."""

        return canonical_digest(self)


@dataclass(frozen=True)
class KeyRevocation:
    """A dated key revocation (§13.3, §26.8).

    Revocation is **dated**, not a bare flag, because ADR §13.3 requires key
    revocation to be "checked at verification time" — a check that needs an
    instant to compare against. ``effective_at`` is the instant from which the
    key is revoked; a key is revoked at an evaluation instant ``t`` exactly when
    ``t >= effective_at``, which is the same half-open convention §17.9 fixes
    for every other interval bound in this package.

    §26.8 keeps three revocations distinct and never conflated: **key**
    revocation (this type), **evidence** revocation
    (``TRUSTED_EVIDENCE_REVOKED`` on the evidence lifecycle), and
    benchmark-version revocation (BR-2, not TEV-2's). Policy-version revocation
    and Risk Authority envelope revocation are separate again, and belong to
    other authorities entirely.
    """

    effective_at: datetime
    reason_ref: str = ""

    def __post_init__(self) -> None:
        require_aware_datetime(self.effective_at, "KeyRevocation.effective_at")
        require_canonical_str(
            self.reason_ref, "KeyRevocation.reason_ref", allow_empty=True
        )

    def is_revoked_at(self, instant: datetime) -> bool:
        """Whether the key is revoked at ``instant`` — explicit input, no clock."""

        require_aware_datetime(instant, "KeyRevocation.is_revoked_at.instant")
        return instant >= self.effective_at


@dataclass(frozen=True)
class TrustAnchorRecord:
    """One configured trust anchor. Public material and lifecycle only.

    Everything a verifier needs in order to decide whether a named key may be
    trusted *right now*, and nothing a signer needs in order to use it.

    ============================  =========================================
    ``authority_id``              §9 row 14 — whose key this is
    ``key_id``                    §9 row 14 — the exact key coordinate
    ``capability``                §8 rows 1/4, E-3 — produce **or** issue
    ``signature_profile``         DD-9 — the one ratified profile
    ``signature_encoding``        DD-9 — the one ratified encoding
    ``public_key``                canonical lowercase hex; never a seed
    ``effective_from``/``_to``    §17.9 half-open validity interval
    ``disabled``                  administrative, undated, reversible
    ``revocation``                §13.3 dated, terminal, or ``None``
    ``trust_anchor_set_id``       which configured set this came from
    ``trust_anchor_set_version``  and at which version — both auditable
    ============================  =========================================

    ``trust_anchor_set_id`` and ``trust_anchor_set_version`` are recorded so an
    audit record can name the exact trust configuration a determination was
    reached under. They identify the configuration; they confer nothing.

    Tenant, system and domain restrictions are deliberately **not** fields. ADR
    §9 binds tenant, context, subject and assessed system to the *evidence and
    the receipt*, where §26.5 makes cross-tenant replay mechanically detectable.
    No ratified clause additionally scopes a **key** to a tenant, and inventing
    one would mint an entitlement model the ADR has not ratified — DD-3's
    neighbouring question about entitlement is explicitly still open.
    """

    authority_id: str
    key_id: str
    capability: TrustAnchorCapability
    public_key: str
    trust_anchor_set_id: str
    trust_anchor_set_version: str
    signature_profile: str = TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1
    signature_encoding: str = TRUSTED_EVIDENCE_SIGNATURE_ENCODING_V1
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None
    disabled: bool = False
    revocation: Optional[KeyRevocation] = None

    def __post_init__(self) -> None:
        for name in (
            "authority_id",
            "key_id",
            "trust_anchor_set_id",
            "trust_anchor_set_version",
        ):
            require_identifier(getattr(self, name), f"TrustAnchorRecord.{name}")
        require_exact_type(
            self.capability, TrustAnchorCapability, "TrustAnchorRecord.capability"
        )
        # Validates the encoding *and* proves the material decodes to a real
        # 32-byte Ed25519 public key, so a malformed anchor cannot be configured
        # and then fail obscurely at verification time.
        decode_public_key(self.public_key, "TrustAnchorRecord.public_key")
        if self.signature_profile != TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1:
            raise _fail(
                "TrustAnchorRecord.signature_profile must be exactly "
                f"{TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1!r}; TEV-2 ships one "
                "strict profile with no negotiation, no alias and no fallback",
                _R.TRUSTED_EVIDENCE_SIGNATURE_PROFILE_UNSUPPORTED,
            )
        if self.signature_encoding != TRUSTED_EVIDENCE_SIGNATURE_ENCODING_V1:
            raise _fail(
                "TrustAnchorRecord.signature_encoding must be exactly "
                f"{TRUSTED_EVIDENCE_SIGNATURE_ENCODING_V1!r}",
                _R.TRUSTED_EVIDENCE_SIGNATURE_ENCODING_INVALID,
            )
        if type(self.disabled) is not bool:
            raise _fail(
                "TrustAnchorRecord.disabled must be exactly a bool "
                f"(got {type(self.disabled).__name__}); a truthy substitute is "
                "refused because a trust decision may not rest on coercion",
                _R.TRUSTED_EVIDENCE_MALFORMED_CONTRACT,
            )
        require_optional_aware_datetime(
            self.effective_from, "TrustAnchorRecord.effective_from"
        )
        require_optional_aware_datetime(
            self.effective_to, "TrustAnchorRecord.effective_to"
        )
        if self.effective_from is not None and self.effective_to is not None:
            require_strictly_before(
                self.effective_from,
                self.effective_to,
                "TrustAnchorRecord.effective_from",
                "TrustAnchorRecord.effective_to",
                "key validity is half-open [effective_from, effective_to) per "
                "ADR §17.9",
            )
        if self.revocation is not None:
            require_exact_type(
                self.revocation, KeyRevocation, "TrustAnchorRecord.revocation"
            )

    @property
    def coordinate(self) -> TrustAnchorCoordinate:
        """The exact triple this anchor answers to."""

        return TrustAnchorCoordinate(
            authority_id=self.authority_id,
            key_id=self.key_id,
            capability=self.capability,
        )

    def verification_key(self) -> TrustedEvidenceVerificationKey:
        """Decode the public half for signature checking. Public material only."""

        return TrustedEvidenceVerificationKey(
            decode_public_key(self.public_key, "TrustAnchorRecord.public_key")
        )

    def lifecycle_refusal_at(self, instant: datetime):
        """The typed refusal this anchor's lifecycle produces at ``instant``.

        Returns ``None`` when the anchor is usable at that instant, and exactly
        one :class:`~..contracts.reasons.TrustedEvidenceRefusalReason` when it
        is not. Checked in a fixed order — revoked, disabled, not yet valid,
        expired — so identical inputs always yield the identical reason (ADR
        §22.13).

        Revocation is checked **first and hardest**. ADR §13.3: "a receipt
        signed by a key that was later revoked is **not** silently honoured."
        A revoked key therefore cannot establish trust at any instant at or
        after its revocation, whatever its validity window says and whatever
        instant the signature was produced at.
        """

        require_aware_datetime(instant, "TrustAnchorRecord.lifecycle_refusal_at.instant")
        if self.revocation is not None and self.revocation.is_revoked_at(instant):
            return _R.TRUSTED_EVIDENCE_KEY_REVOKED
        if self.disabled:
            return _R.TRUSTED_EVIDENCE_KEY_DISABLED
        if self.effective_from is not None and instant < self.effective_from:
            return _R.TRUSTED_EVIDENCE_KEY_NOT_YET_VALID
        if self.effective_to is not None and instant >= self.effective_to:
            return _R.TRUSTED_EVIDENCE_KEY_EXPIRED
        return None

    def canonical_bytes(self) -> bytes:
        """The exact bytes :meth:`canonical_digest` is computed over."""

        return canonical_bytes(self)

    def canonical_digest(self) -> str:
        """Deterministic sha-256 over the complete anchor record.

        An auditable identity for "which configured anchor was consulted". It is
        not a signature, not an entitlement, and not a trust decision.
        """

        return canonical_digest(self)


@dataclass(frozen=True)
class TrustAnchorResolution:
    """The typed outcome of one exact-coordinate trust-anchor lookup.

    Exactly one of :attr:`anchor` and :attr:`refusal_reason` is set — enforced
    at construction, so there is no "resolved but also refused" state and no
    "neither" state to read optimistically. There is no boolean success flag:
    a caller must branch on which of the two is present, and the presence of an
    anchor is decided by this module, never supplied by a caller.
    """

    coordinate: TrustAnchorCoordinate
    anchor: Optional[TrustAnchorRecord] = None
    refusal_reason: Optional[TrustedEvidenceRefusalReason] = None

    def __post_init__(self) -> None:
        require_exact_type(
            self.coordinate, TrustAnchorCoordinate, "TrustAnchorResolution.coordinate"
        )
        if self.anchor is not None:
            require_exact_type(
                self.anchor, TrustAnchorRecord, "TrustAnchorResolution.anchor"
            )
        if self.refusal_reason is not None:
            require_exact_type(
                self.refusal_reason,
                TrustedEvidenceRefusalReason,
                "TrustAnchorResolution.refusal_reason",
            )
        if (self.anchor is None) == (self.refusal_reason is None):
            raise _fail(
                "TrustAnchorResolution must carry exactly one of an anchor or a "
                "typed refusal reason; carrying both would be a resolved refusal "
                "and carrying neither would be an untyped silence, and ADR E-9 "
                "admits no outcome that is not one or the other",
                _R.TRUSTED_EVIDENCE_MALFORMED_CONTRACT,
            )
        if self.anchor is not None and self.anchor.coordinate != self.coordinate:
            raise _fail(
                "TrustAnchorResolution carries an anchor at a different "
                "coordinate than the one resolved; a resolver may not answer a "
                "question it was not asked",
                _R.TRUSTED_EVIDENCE_KEY_ID_MISMATCH,
            )

    @classmethod
    def resolved(
        cls, coordinate: TrustAnchorCoordinate, anchor: TrustAnchorRecord
    ) -> "TrustAnchorResolution":
        """An anchor was found at exactly this coordinate."""

        return cls(coordinate=coordinate, anchor=anchor)

    @classmethod
    def refused(
        cls, coordinate: TrustAnchorCoordinate, reason: TrustedEvidenceRefusalReason
    ) -> "TrustAnchorResolution":
        """No usable anchor, with the typed reason why."""

        return cls(coordinate=coordinate, refusal_reason=reason)


@runtime_checkable
class TrustAnchorResolverPort(Protocol):
    """Resolve a trust anchor at an exact coordinate. The only lookup shape.

    A deployment substitutes its own implementation — a configuration loader, a
    managed key service, an HSM directory — without any caller change (DD-10).
    Whatever the backing store, the contract is the same: an **exact** triple in,
    a typed :class:`TrustAnchorResolution` out, no clock read, and no
    authorization performed.

    TEV-2 adds **no network retrieval**. An implementation that fetches over a
    network is a deployment's own concern and is outside this milestone; the
    reference implementation reads nothing but the records it was constructed
    with.
    """

    def resolve(self, coordinate: TrustAnchorCoordinate) -> TrustAnchorResolution:
        """Return the typed resolution for this exact coordinate."""
        ...


class StaticTrustAnchorDirectory:
    """The deterministic reference :class:`TrustAnchorResolverPort`.

    Suitable for tests, for local use, and as the shape a production resolver
    should present. It holds exactly the records it was constructed with, in an
    immutable private mapping exposed only through a read-only view.

    Three properties are structural rather than conventional:

    * **duplicate coordinates are refused at construction** — two records
      answering one triple would force a first-key-wins choice, and choosing
      between trust anchors is an unsigned authority decision (§26.9);
    * **the directory is immutable after construction** — the internal mapping
      is defensively copied and rebinding any attribute raises, so a caller who
      mutates the iterable it passed in cannot alter trust state afterwards
      (the same discipline §17.7 requires of trust-anchor views);
    * **there is no widening method** — no ``add``, no ``latest``, no
      ``default``, no ``any``, no ``first``. :meth:`with_anchor` returns a
      *new* directory and re-runs the duplicate check.
    """

    __slots__ = ("_anchors", "_set_id", "_set_version")

    def __init__(
        self,
        anchors: "Iterable[TrustAnchorRecord]" = (),
        *,
        trust_anchor_set_id: str = "",
        trust_anchor_set_version: str = "",
    ) -> None:
        if isinstance(anchors, (str, bytes, bytearray)):
            raise _fail(
                "StaticTrustAnchorDirectory expects an iterable of "
                f"TrustAnchorRecord, not a {type(anchors).__name__}",
                _R.TRUSTED_EVIDENCE_MALFORMED_CONTRACT,
            )
        collected: dict = {}
        for index, anchor in enumerate(anchors):
            require_exact_type(
                anchor, TrustAnchorRecord, f"StaticTrustAnchorDirectory.anchors[{index}]"
            )
            coordinate = anchor.coordinate
            if coordinate in collected:
                raise _fail(
                    "StaticTrustAnchorDirectory refuses a duplicate trust-anchor "
                    f"coordinate (authority {anchor.authority_id!r}, key "
                    f"{anchor.key_id!r}, capability {anchor.capability.value}); "
                    "two anchors at one coordinate would force a first-key-wins "
                    "choice, and choosing between trust anchors is an unsigned "
                    "authority decision (ADR §26.9)",
                    _R.TRUSTED_EVIDENCE_TRUST_ANCHOR_AMBIGUOUS,
                )
            collected[coordinate] = anchor
        set_id = require_canonical_str(
            trust_anchor_set_id,
            "StaticTrustAnchorDirectory.trust_anchor_set_id",
            allow_empty=True,
        )
        set_version = require_canonical_str(
            trust_anchor_set_version,
            "StaticTrustAnchorDirectory.trust_anchor_set_version",
            allow_empty=True,
        )
        object.__setattr__(self, "_anchors", MappingProxyType(collected))
        object.__setattr__(self, "_set_id", set_id)
        object.__setattr__(self, "_set_version", set_version)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(
            f"StaticTrustAnchorDirectory is immutable; cannot set {name!r}. "
            "Rebinding the anchor store wholesale is exactly the attacker-key "
            "injection the defensive copy exists to prevent — build a new "
            "directory with with_anchor() instead."
        )

    def __delattr__(self, name: str) -> None:
        raise AttributeError(
            f"StaticTrustAnchorDirectory is immutable; cannot delete {name!r}"
        )

    @property
    def anchors(self):
        """A read-only view of the configured anchors, keyed by coordinate."""

        return self._anchors

    @property
    def trust_anchor_set_id(self) -> str:
        """Identity of the configured anchor set, for audit. Confers nothing."""

        return self._set_id

    @property
    def trust_anchor_set_version(self) -> str:
        """Version of the configured anchor set, for audit. Confers nothing."""

        return self._set_version

    def with_anchor(self, anchor: TrustAnchorRecord) -> "StaticTrustAnchorDirectory":
        """Return a **new** directory with ``anchor`` added. This one is unchanged.

        Re-runs the duplicate-coordinate check, so an anchor cannot be swapped
        in over an existing coordinate: replacing a trust anchor is a
        configuration act performed at the composition root by constructing a
        different directory, not an in-flight mutation (E-5).
        """

        return StaticTrustAnchorDirectory(
            tuple(self._anchors.values()) + (anchor,),
            trust_anchor_set_id=self._set_id,
            trust_anchor_set_version=self._set_version,
        )

    def resolve(self, coordinate: TrustAnchorCoordinate) -> TrustAnchorResolution:
        """Exact-triple lookup. A near miss is a miss."""

        require_exact_type(
            coordinate,
            TrustAnchorCoordinate,
            "StaticTrustAnchorDirectory.resolve.coordinate",
        )
        if not self._anchors:
            # E-8 — nothing configured is not "nothing to check"; it is deny.
            return TrustAnchorResolution.refused(
                coordinate, _R.TRUSTED_EVIDENCE_TRUST_ANCHOR_NOT_CONFIGURED
            )
        anchor = self._anchors.get(coordinate)
        if anchor is None:
            return TrustAnchorResolution.refused(
                coordinate, _R.TRUSTED_EVIDENCE_TRUST_ANCHOR_MISSING
            )
        return TrustAnchorResolution.resolved(coordinate, anchor)

    def __repr__(self) -> str:
        return (
            "StaticTrustAnchorDirectory("
            f"{len(self._anchors)} anchors, set={self._set_id!r}@{self._set_version!r})"
        )


class DenyAllTrustAnchorDirectory:
    """The deny-by-default resolver required by ADR E-8.

    "When no trusted verifier or trust anchor is configured, the production
    default is **deny**." This is that default made explicit and constructible,
    so a composition root that has not yet configured trust denies loudly and
    typed rather than silently accepting.

    It is **not** a permissive stub, a fake verifier or a test double: it refuses
    every coordinate, unconditionally, in production and in tests alike. ADR E-8
    prohibits the opposite — "no production allow-all verifier may ship" — and
    this package contains none.
    """

    __slots__ = ()

    def resolve(self, coordinate: TrustAnchorCoordinate) -> TrustAnchorResolution:
        require_exact_type(
            coordinate,
            TrustAnchorCoordinate,
            "DenyAllTrustAnchorDirectory.resolve.coordinate",
        )
        return TrustAnchorResolution.refused(
            coordinate, _R.TRUSTED_EVIDENCE_TRUST_ANCHOR_NOT_CONFIGURED
        )

    def __repr__(self) -> str:
        return "DenyAllTrustAnchorDirectory()"


def _fail(message: str, reason: TrustedEvidenceRefusalReason):
    error = TrustedEvidenceContractError(message)
    error.reason = reason
    return error
