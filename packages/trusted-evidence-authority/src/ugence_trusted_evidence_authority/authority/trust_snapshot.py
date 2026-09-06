"""The signed trust-anchor-set snapshot and its production-shaped resolver (TR-1 to TR-5).

``ADR_UGENCE_TEA_PRODUCTION_TRUST_ANCHOR_RESOLVER`` ratifies one production
resolver shape: an **immutable, manifest-signed snapshot** of a complete
trust-anchor set, authenticated by a **pinned bootstrap publication root** that
the composition root provisions independently, and resolved only against an
**explicit timezone-aware instant** supplied to every resolution (TR-3-PROTOCOL).

What this module does
---------------------
* defines the manifest and snapshot contracts and their wire document, with
  deterministic canonicalization and a complete-collection digest;
* parses a complete document **handed to it as bytes** and admits nothing until
  every check passes — a truncated, tampered, reordered, duplicated, rolled-back
  or self-authenticating document leaves the resolver in a typed refused state;
* resolves an exact coordinate only after the instant, the load state, the
  publication root's lifecycle, the set's validity window and the maximum
  snapshot age have all been checked, in that order, for **that** resolution.

What it deliberately does not do
--------------------------------
It reads no file, clock, environment or network: this package bans ``open``,
``os``, ``pathlib`` and every clock call structurally
(``tests/packaging/test_no_clock_or_environment.py``), so the composition root
performs the file read and hands over the bytes. It signs nothing, holds no
private material, refreshes nothing in the background and offers no widening
method: a new snapshot means a new resolver. The publication, rotation and
revocation *process* is specified by the ADR (TR-4) and implemented nowhere.

A resolved anchor is an input to verification, never an authorization. Anchor
lifecycle (revoked, disabled, not yet valid, expired) stays with the verifier,
as the BR-2C precedent requires, so the four states remain distinguishable.

Maturity: a **production-shaped resolver candidate**. It is not independently
reviewed, not externally cryptographically audited and not production-ready;
D-38 and D-32(4) remain applicable.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from types import MappingProxyType
from typing import Optional, Tuple

from ..contracts._validation import (
    require_aware_datetime,
    require_canonical_str,
    require_exact_type,
    require_identifier,
    require_strictly_before,
)
from ..contracts.canonical import canonical_bytes
from ..contracts.errors import TrustedEvidenceContractError
from ..contracts.reasons import TrustedEvidenceRefusalReason
from .profile import (
    TRUSTED_EVIDENCE_SIGNATURE_ENCODING_V1,
    TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1,
    decode_signature,
    framed_signed_input,
)
from .trust import (
    KeyRevocation,
    TrustAnchorCapability,
    TrustAnchorCoordinate,
    TrustAnchorRecord,
    TrustAnchorResolution,
)

__all__ = [
    "TRUST_ANCHOR_SET_MANIFEST_SCHEMA_V1",
    "TRUST_ANCHOR_SET_DOCUMENT_SCHEMA_V1",
    "TRUST_ANCHOR_SET_PUBLICATION_SIGNING_DOMAIN",
    "TRUST_ANCHOR_SET_COLLECTION_DIGEST_DOMAIN",
    "TrustAnchorSetManifest",
    "TrustAnchorSetSnapshot",
    "TrustAnchorSetLoadFailure",
    "SignedSnapshotTrustAnchorResolver",
    "trust_anchor_collection_digest",
    "trust_anchor_set_signing_bytes",
    "parse_trust_anchor_set_document",
    "render_trust_anchor_set_document",
]

_R = TrustedEvidenceRefusalReason

#: Schema of the signed manifest. Bound into the signed bytes.
TRUST_ANCHOR_SET_MANIFEST_SCHEMA_V1 = (
    "ugence.trusted-evidence-authority/trust-anchor-set-manifest/v1"
)
#: Schema of the wire document that carries manifest, anchors and signature.
TRUST_ANCHOR_SET_DOCUMENT_SCHEMA_V1 = (
    "ugence.trusted-evidence-authority/trust-anchor-set-document/v1"
)
#: Domain tag bound as element 0 of a publication signature (TR-2).
TRUST_ANCHOR_SET_PUBLICATION_SIGNING_DOMAIN = (
    "ugence.trusted-evidence-authority/trust-anchor-set-publication/v1"
)
#: Domain tag bound as element 0 of the complete-collection digest.
TRUST_ANCHOR_SET_COLLECTION_DIGEST_DOMAIN = (
    "ugence.trusted-evidence-authority/trust-anchor-set-collection/v1"
)

_INSTANT_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
_HEX_DIGITS = frozenset("0123456789abcdef")


def _fail(message: str, reason: TrustedEvidenceRefusalReason):
    error = TrustedEvidenceContractError(message)
    error.reason = reason
    return error


def _malformed(message: str):
    return _fail(message, _R.TRUSTED_EVIDENCE_MALFORMED_CONTRACT)


# --------------------------------------------------------------------------- #
# The manifest
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class TrustAnchorSetManifest:
    """What the publisher signs: the identity, version, window and complete
    content digest of one trust-anchor set (TR-2).

    ``trust_anchor_set_version`` is an integer so monotonicity is a comparison,
    not a string convention. ``anchor_collection_digest`` binds the complete,
    ordered anchor collection, so no record can be added, removed or reordered
    under a valid signature. The publisher coordinate names the bootstrap root
    the composition root must have pinned independently; the manifest can name
    it but can never supply it.
    """

    schema_version: str
    trust_anchor_set_id: str
    trust_anchor_set_version: int
    publisher_authority_id: str
    publisher_key_id: str
    published_at: datetime
    effective_from: datetime
    effective_to: datetime
    anchor_count: int
    anchor_collection_digest: str
    signature_profile: str = TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1
    signature_encoding: str = TRUSTED_EVIDENCE_SIGNATURE_ENCODING_V1

    def __post_init__(self) -> None:
        require_identifier(self.schema_version, "TrustAnchorSetManifest.schema_version")
        if self.schema_version != TRUST_ANCHOR_SET_MANIFEST_SCHEMA_V1:
            raise _fail(
                "TrustAnchorSetManifest.schema_version must be exactly "
                f"{TRUST_ANCHOR_SET_MANIFEST_SCHEMA_V1!r}",
                _R.TRUSTED_EVIDENCE_SCHEMA_UNSUPPORTED,
            )
        require_identifier(self.trust_anchor_set_id, "TrustAnchorSetManifest.trust_anchor_set_id")
        if type(self.trust_anchor_set_version) is not int or self.trust_anchor_set_version < 1:
            raise _malformed(
                "TrustAnchorSetManifest.trust_anchor_set_version must be an int >= 1; "
                "monotonic ordering is a comparison, never a string convention"
            )
        require_identifier(
            self.publisher_authority_id, "TrustAnchorSetManifest.publisher_authority_id"
        )
        require_identifier(self.publisher_key_id, "TrustAnchorSetManifest.publisher_key_id")
        require_aware_datetime(self.published_at, "TrustAnchorSetManifest.published_at")
        require_aware_datetime(self.effective_from, "TrustAnchorSetManifest.effective_from")
        require_aware_datetime(self.effective_to, "TrustAnchorSetManifest.effective_to")
        require_strictly_before(
            self.effective_from,
            self.effective_to,
            "TrustAnchorSetManifest.effective_from",
            "TrustAnchorSetManifest.effective_to",
            "set validity is half-open [effective_from, effective_to) per ADR §17.9",
        )
        if self.published_at > self.effective_from:
            raise _malformed(
                "TrustAnchorSetManifest.published_at must not be after effective_from; a "
                "set cannot come into force before it was published"
            )
        if type(self.anchor_count) is not int or self.anchor_count < 0:
            raise _malformed("TrustAnchorSetManifest.anchor_count must be an int >= 0")
        _require_hex_digest(self.anchor_collection_digest, "TrustAnchorSetManifest.anchor_collection_digest")
        if self.signature_profile != TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1:
            raise _fail(
                "TrustAnchorSetManifest.signature_profile must be exactly "
                f"{TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1!r}",
                _R.TRUSTED_EVIDENCE_SIGNATURE_PROFILE_UNSUPPORTED,
            )
        if self.signature_encoding != TRUSTED_EVIDENCE_SIGNATURE_ENCODING_V1:
            raise _fail(
                "TrustAnchorSetManifest.signature_encoding must be exactly "
                f"{TRUSTED_EVIDENCE_SIGNATURE_ENCODING_V1!r}",
                _R.TRUSTED_EVIDENCE_SIGNATURE_ENCODING_INVALID,
            )

    @property
    def publisher_coordinate(self) -> TrustAnchorCoordinate:
        """The exact coordinate the pinned publication root must answer to."""

        return TrustAnchorCoordinate(
            authority_id=self.publisher_authority_id,
            key_id=self.publisher_key_id,
            capability=TrustAnchorCapability.TRUST_ANCHOR_SET_PUBLICATION,
        )

    def canonical_bytes(self) -> bytes:
        return canonical_bytes(self)


def _require_hex_digest(value: object, name: str) -> str:
    require_canonical_str(value, name, allow_empty=False)
    if type(value) is not str or len(value) != 64 or not set(value) <= _HEX_DIGITS:
        raise _malformed(f"{name} must be exactly 64 lowercase hex characters")
    return value


def trust_anchor_collection_digest(anchors: Tuple[TrustAnchorRecord, ...]) -> str:
    """The sha-256 over the framed, ordered canonical bytes of every anchor.

    Element 0 is the collection domain, then each record's complete canonical
    bytes in order. The frame binds the count and every boundary, so adding,
    removing, reordering or editing a record changes the digest.
    """

    if type(anchors) is not tuple:
        raise _malformed("trust_anchor_collection_digest expects a tuple of TrustAnchorRecord")
    elements = [TRUST_ANCHOR_SET_COLLECTION_DIGEST_DOMAIN.encode("utf-8")]
    for index, anchor in enumerate(anchors):
        require_exact_type(anchor, TrustAnchorRecord, f"trust_anchor_collection_digest.anchors[{index}]")
        elements.append(anchor.canonical_bytes())
    return hashlib.sha256(framed_signed_input(tuple(elements))).hexdigest()


def trust_anchor_set_signing_bytes(manifest: TrustAnchorSetManifest) -> bytes:
    """The exact bytes a publication root signs: domain, then the canonical manifest.

    This package emits the bytes and verifies signatures over them. It signs
    nothing: the publication signer is held outside the repository (TR-4).
    """

    require_exact_type(manifest, TrustAnchorSetManifest, "trust_anchor_set_signing_bytes.manifest")
    return framed_signed_input(
        (
            TRUST_ANCHOR_SET_PUBLICATION_SIGNING_DOMAIN.encode("utf-8"),
            manifest.canonical_bytes(),
        )
    )


def _coordinate_sort_key(anchor: TrustAnchorRecord) -> Tuple[str, str, str]:
    return (anchor.authority_id, anchor.key_id, anchor.capability.value)


# --------------------------------------------------------------------------- #
# The snapshot
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class TrustAnchorSetSnapshot:
    """One complete, ordered, manifest-bound trust-anchor set with its signature.

    Construction proves internal consistency only: the count matches, the
    collection digest matches, the records are in canonical order with no
    duplicate coordinate, every record names this set at this version, and no
    record carries the publication capability (a snapshot may never carry the
    key that authenticates it — TR-2). Whether the **signature** verifies under
    a pinned root is the resolver's question, because only the composition root
    holds that root.
    """

    manifest: TrustAnchorSetManifest
    anchors: Tuple[TrustAnchorRecord, ...]
    signature: str

    def __post_init__(self) -> None:
        require_exact_type(self.manifest, TrustAnchorSetManifest, "TrustAnchorSetSnapshot.manifest")
        if type(self.anchors) is not tuple:
            raise _malformed("TrustAnchorSetSnapshot.anchors must be a tuple")
        seen: dict = {}
        previous_key: Optional[Tuple[str, str, str]] = None
        for index, anchor in enumerate(self.anchors):
            require_exact_type(anchor, TrustAnchorRecord, f"TrustAnchorSetSnapshot.anchors[{index}]")
            if anchor.capability is TrustAnchorCapability.TRUST_ANCHOR_SET_PUBLICATION:
                raise _fail(
                    "TrustAnchorSetSnapshot refuses an anchor under "
                    "TRUST_ANCHOR_SET_PUBLICATION: a snapshot may never carry the key "
                    "that authenticates it; the publication root is pinned at the "
                    "composition boundary (TR-2)",
                    _R.TRUSTED_EVIDENCE_KEY_CAPABILITY_MISMATCH,
                )
            if anchor.trust_anchor_set_id != self.manifest.trust_anchor_set_id:
                raise _malformed(
                    f"TrustAnchorSetSnapshot.anchors[{index}] names set "
                    f"{anchor.trust_anchor_set_id!r}, not the manifest's "
                    f"{self.manifest.trust_anchor_set_id!r}"
                )
            if anchor.trust_anchor_set_version != str(self.manifest.trust_anchor_set_version):
                raise _malformed(
                    f"TrustAnchorSetSnapshot.anchors[{index}] names set version "
                    f"{anchor.trust_anchor_set_version!r}, not the manifest's "
                    f"{self.manifest.trust_anchor_set_version}"
                )
            key = _coordinate_sort_key(anchor)
            if anchor.coordinate in seen:
                raise _fail(
                    "TrustAnchorSetSnapshot refuses a duplicate trust-anchor coordinate "
                    f"(authority {anchor.authority_id!r}, key {anchor.key_id!r}, "
                    f"capability {anchor.capability.value}); two anchors at one "
                    "coordinate would force a first-key-wins choice (ADR §26.9)",
                    _R.TRUSTED_EVIDENCE_TRUST_ANCHOR_AMBIGUOUS,
                )
            if previous_key is not None and key < previous_key:
                raise _malformed(
                    f"TrustAnchorSetSnapshot.anchors[{index}] is out of canonical order; "
                    "records are ordered by (authority_id, key_id, capability) so the "
                    "collection digest is a function of the set, not of a listing"
                )
            seen[anchor.coordinate] = anchor
            previous_key = key
        if self.manifest.anchor_count != len(self.anchors):
            raise _malformed(
                f"TrustAnchorSetManifest.anchor_count is {self.manifest.anchor_count} but the "
                f"snapshot carries {len(self.anchors)} anchors"
            )
        digest = trust_anchor_collection_digest(self.anchors)
        if digest != self.manifest.anchor_collection_digest:
            raise _fail(
                "TrustAnchorSetSnapshot.anchors do not match the manifest's "
                "anchor_collection_digest; a record was added, removed, reordered or "
                "edited after the manifest was signed",
                _R.TRUSTED_EVIDENCE_PAYLOAD_DIGEST_MISMATCH,
            )
        require_canonical_str(self.signature, "TrustAnchorSetSnapshot.signature", allow_empty=False)
        if type(self.signature) is not str or len(self.signature) != 128 or not set(self.signature) <= _HEX_DIGITS:
            raise _fail(
                "TrustAnchorSetSnapshot.signature must be exactly 128 lowercase hex characters",
                _R.TRUSTED_EVIDENCE_SIGNATURE_ENCODING_INVALID,
            )

    def signing_bytes(self) -> bytes:
        return trust_anchor_set_signing_bytes(self.manifest)

    @property
    def anchors_by_coordinate(self):
        """A read-only view keyed by exact coordinate."""

        return MappingProxyType({anchor.coordinate: anchor for anchor in self.anchors})


# --------------------------------------------------------------------------- #
# Wire document
# --------------------------------------------------------------------------- #
_MANIFEST_KEYS = (
    "schema_version",
    "trust_anchor_set_id",
    "trust_anchor_set_version",
    "publisher_authority_id",
    "publisher_key_id",
    "published_at",
    "effective_from",
    "effective_to",
    "anchor_count",
    "anchor_collection_digest",
    "signature_profile",
    "signature_encoding",
)
_ANCHOR_KEYS = (
    "authority_id",
    "key_id",
    "capability",
    "public_key",
    "trust_anchor_set_id",
    "trust_anchor_set_version",
    "signature_profile",
    "signature_encoding",
    "effective_from",
    "effective_to",
    "disabled",
    "revocation",
)
_DOCUMENT_KEYS = ("document_schema", "manifest", "anchors", "signature")


def _format_instant(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime(_INSTANT_FORMAT)


def _parse_instant(value: object, path: str) -> datetime:
    if type(value) is not str:
        raise _malformed(f"{path} must be a string instant")
    try:
        parsed = datetime.strptime(value, _INSTANT_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError:
        raise _malformed(f"{path} is not a canonical UTC instant") from None
    if _format_instant(parsed) != value:
        raise _malformed(f"{path} is not in canonical form")
    return parsed


def _require_object(value: object, path: str, keys: Tuple[str, ...]) -> dict:
    if type(value) is not dict:
        raise _malformed(f"{path} must be a JSON object")
    if tuple(sorted(value)) != tuple(sorted(keys)):
        raise _malformed(f"{path} must carry exactly the keys {sorted(keys)}")
    return value


def _require_str(value: object, path: str) -> str:
    if type(value) is not str:
        raise _malformed(f"{path} must be a string")
    return value


def _require_int(value: object, path: str) -> int:
    if type(value) is not int:
        raise _malformed(f"{path} must be an integer")
    return value


def _parse_anchor(value: object, path: str) -> TrustAnchorRecord:
    obj = _require_object(value, path, _ANCHOR_KEYS)
    capability_value = _require_str(obj["capability"], f"{path}.capability")
    capability = None
    for member in TrustAnchorCapability:
        if member.value == capability_value:
            capability = member
    if capability is None:
        raise _malformed(f"{path}.capability names no TrustAnchorCapability member")
    if type(obj["disabled"]) is not bool:
        raise _malformed(f"{path}.disabled must be a boolean")
    revocation = None
    if obj["revocation"] is not None:
        rev = _require_object(obj["revocation"], f"{path}.revocation", ("effective_at", "reason_ref"))
        revocation = KeyRevocation(
            effective_at=_parse_instant(rev["effective_at"], f"{path}.revocation.effective_at"),
            reason_ref=_require_str(rev["reason_ref"], f"{path}.revocation.reason_ref"),
        )
    effective_from = None
    if obj["effective_from"] is not None:
        effective_from = _parse_instant(obj["effective_from"], f"{path}.effective_from")
    effective_to = None
    if obj["effective_to"] is not None:
        effective_to = _parse_instant(obj["effective_to"], f"{path}.effective_to")
    return TrustAnchorRecord(
        authority_id=_require_str(obj["authority_id"], f"{path}.authority_id"),
        key_id=_require_str(obj["key_id"], f"{path}.key_id"),
        capability=capability,
        public_key=_require_str(obj["public_key"], f"{path}.public_key"),
        trust_anchor_set_id=_require_str(obj["trust_anchor_set_id"], f"{path}.trust_anchor_set_id"),
        trust_anchor_set_version=_require_str(
            obj["trust_anchor_set_version"], f"{path}.trust_anchor_set_version"
        ),
        signature_profile=_require_str(obj["signature_profile"], f"{path}.signature_profile"),
        signature_encoding=_require_str(obj["signature_encoding"], f"{path}.signature_encoding"),
        effective_from=effective_from,
        effective_to=effective_to,
        disabled=obj["disabled"],
        revocation=revocation,
    )


def parse_trust_anchor_set_document(document: bytes) -> TrustAnchorSetSnapshot:
    """Parse one complete wire document into a structurally verified snapshot.

    Strict: exact JSON types, exactly the documented keys, canonical instants,
    canonical hex, and the one canonical rendering byte for byte. A document
    that is not ``bytes``, not UTF-8, not JSON, not an object, not complete or
    not canonical refuses with ``TRUSTED_EVIDENCE_MALFORMED_CONTRACT``. The
    signature is **not** checked here; see the resolver.
    """

    if type(document) is not bytes:
        raise _malformed("parse_trust_anchor_set_document expects the complete document as bytes")
    try:
        text = document.decode("utf-8")
    except UnicodeDecodeError:
        raise _malformed("the trust-anchor-set document is not UTF-8") from None
    try:
        loaded = json.loads(text)
    except ValueError:
        raise _malformed("the trust-anchor-set document is not JSON") from None
    root = _require_object(loaded, "document", _DOCUMENT_KEYS)
    if root["document_schema"] != TRUST_ANCHOR_SET_DOCUMENT_SCHEMA_V1:
        raise _fail(
            "document.document_schema must be exactly "
            f"{TRUST_ANCHOR_SET_DOCUMENT_SCHEMA_V1!r}",
            _R.TRUSTED_EVIDENCE_SCHEMA_UNSUPPORTED,
        )
    m = _require_object(root["manifest"], "document.manifest", _MANIFEST_KEYS)
    manifest = TrustAnchorSetManifest(
        schema_version=_require_str(m["schema_version"], "document.manifest.schema_version"),
        trust_anchor_set_id=_require_str(m["trust_anchor_set_id"], "document.manifest.trust_anchor_set_id"),
        trust_anchor_set_version=_require_int(
            m["trust_anchor_set_version"], "document.manifest.trust_anchor_set_version"
        ),
        publisher_authority_id=_require_str(
            m["publisher_authority_id"], "document.manifest.publisher_authority_id"
        ),
        publisher_key_id=_require_str(m["publisher_key_id"], "document.manifest.publisher_key_id"),
        published_at=_parse_instant(m["published_at"], "document.manifest.published_at"),
        effective_from=_parse_instant(m["effective_from"], "document.manifest.effective_from"),
        effective_to=_parse_instant(m["effective_to"], "document.manifest.effective_to"),
        anchor_count=_require_int(m["anchor_count"], "document.manifest.anchor_count"),
        anchor_collection_digest=_require_str(
            m["anchor_collection_digest"], "document.manifest.anchor_collection_digest"
        ),
        signature_profile=_require_str(m["signature_profile"], "document.manifest.signature_profile"),
        signature_encoding=_require_str(m["signature_encoding"], "document.manifest.signature_encoding"),
    )
    if type(root["anchors"]) is not list:
        raise _malformed("document.anchors must be a JSON array")
    anchors = tuple(
        _parse_anchor(item, f"document.anchors[{index}]") for index, item in enumerate(root["anchors"])
    )
    signature = _require_str(root["signature"], "document.signature")
    snapshot = TrustAnchorSetSnapshot(manifest=manifest, anchors=anchors, signature=signature)
    # The document must be in its one canonical rendering: a byte appended,
    # removed or reflowed anywhere is refused, so a partial read and a
    # non-canonical re-serialization are both malformed rather than tolerated.
    if render_trust_anchor_set_document(snapshot) != document:
        raise _malformed(
            "the trust-anchor-set document is not in canonical rendering; only the exact "
            "bytes render_trust_anchor_set_document produces are admitted"
        )
    return snapshot


def _render_anchor(anchor: TrustAnchorRecord) -> dict:
    revocation = None
    if anchor.revocation is not None:
        revocation = {
            "effective_at": _format_instant(anchor.revocation.effective_at),
            "reason_ref": anchor.revocation.reason_ref,
        }
    return {
        "authority_id": anchor.authority_id,
        "key_id": anchor.key_id,
        "capability": anchor.capability.value,
        "public_key": anchor.public_key,
        "trust_anchor_set_id": anchor.trust_anchor_set_id,
        "trust_anchor_set_version": anchor.trust_anchor_set_version,
        "signature_profile": anchor.signature_profile,
        "signature_encoding": anchor.signature_encoding,
        "effective_from": None if anchor.effective_from is None else _format_instant(anchor.effective_from),
        "effective_to": None if anchor.effective_to is None else _format_instant(anchor.effective_to),
        "disabled": anchor.disabled,
        "revocation": revocation,
    }


def render_trust_anchor_set_document(snapshot: TrustAnchorSetSnapshot) -> bytes:
    """Serialize a snapshot to its wire document. Deterministic; the inverse of parse.

    Serialization only: it signs nothing and is not publication tooling. The
    publisher role (TR-4) obtains the signature from an externally held signer
    over :func:`trust_anchor_set_signing_bytes` and then renders.
    """

    require_exact_type(snapshot, TrustAnchorSetSnapshot, "render_trust_anchor_set_document.snapshot")
    m = snapshot.manifest
    document = {
        "document_schema": TRUST_ANCHOR_SET_DOCUMENT_SCHEMA_V1,
        "manifest": {
            "schema_version": m.schema_version,
            "trust_anchor_set_id": m.trust_anchor_set_id,
            "trust_anchor_set_version": m.trust_anchor_set_version,
            "publisher_authority_id": m.publisher_authority_id,
            "publisher_key_id": m.publisher_key_id,
            "published_at": _format_instant(m.published_at),
            "effective_from": _format_instant(m.effective_from),
            "effective_to": _format_instant(m.effective_to),
            "anchor_count": m.anchor_count,
            "anchor_collection_digest": m.anchor_collection_digest,
            "signature_profile": m.signature_profile,
            "signature_encoding": m.signature_encoding,
        },
        "anchors": [_render_anchor(anchor) for anchor in snapshot.anchors],
        "signature": snapshot.signature,
    }
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


# --------------------------------------------------------------------------- #
# The resolver
# --------------------------------------------------------------------------- #
class TrustAnchorSetLoadFailure(str, Enum):
    """Why a snapshot was not admitted. Every value leaves the resolver refusing
    every resolution with ``TRUSTED_EVIDENCE_TRUST_ANCHOR_SET_UNAVAILABLE``; the
    member records which check failed, for the operator, and confers nothing."""

    DOCUMENT_UNAVAILABLE = "DOCUMENT_UNAVAILABLE"
    DOCUMENT_MALFORMED = "DOCUMENT_MALFORMED"
    PUBLICATION_ROOT_ABSENT = "PUBLICATION_ROOT_ABSENT"
    PUBLICATION_ROOT_WRONG_CAPABILITY = "PUBLICATION_ROOT_WRONG_CAPABILITY"
    PUBLISHER_UNKNOWN = "PUBLISHER_UNKNOWN"
    SELF_AUTHENTICATING = "SELF_AUTHENTICATING"
    SIGNATURE_INVALID = "SIGNATURE_INVALID"
    VERSION_ROLLBACK = "VERSION_ROLLBACK"


class SignedSnapshotTrustAnchorResolver:
    """The production-shaped :class:`~.trust.TrustAnchorResolverPort` over one
    verified snapshot (TR-1 to TR-3).

    Build it with :meth:`from_document`. The composition root reads the snapshot
    file and passes the **complete** bytes, the **pinned publication root**, the
    **maximum snapshot age** and the **last accepted set version**; the resolver
    admits nothing until every check passes, and a resolver that admitted
    nothing is still a resolver — one whose every resolution is the typed
    refusal ``TRUSTED_EVIDENCE_TRUST_ANCHOR_SET_UNAVAILABLE``.

    Resolution order, fixed (TR-3-PROTOCOL):

    1. ``as_of`` must be exactly a timezone-aware ``datetime`` — anything else
       is ``TRUSTED_EVIDENCE_TRUST_ANCHOR_SET_INSTANT_REQUIRED`` before any
       snapshot content is consulted;
    2. the snapshot must have been completely admitted;
    3. the publication root must be usable at ``as_of`` and the set must be
       published and in force at ``as_of``;
    4. the snapshot must be fresh: ``as_of`` before the signed ``effective_to``
       and before ``published_at + max_snapshot_age`` (half-open, ADR §17.9);
    5. the exact coordinate is looked up;
    6. the ordinary typed resolution is returned.

    ``is_production_authoritative`` is ``True`` only after step 2's admission
    succeeded at construction. Nothing is cached across resolutions: every call
    re-evaluates 1–4 against its own ``as_of``.
    """

    __slots__ = (
        "_snapshot",
        "_publication_root",
        "_max_snapshot_age",
        "_load_failure",
        "_load_detail",
        "_anchors",
    )

    def __init__(
        self,
        *,
        snapshot: Optional[TrustAnchorSetSnapshot],
        publication_root: Optional[TrustAnchorRecord],
        max_snapshot_age: timedelta,
        load_failure: Optional[TrustAnchorSetLoadFailure],
        load_detail: str,
    ) -> None:
        _require_max_age(max_snapshot_age)
        if load_failure is not None:
            require_exact_type(load_failure, TrustAnchorSetLoadFailure, "load_failure")
            snapshot = None
        else:
            require_exact_type(snapshot, TrustAnchorSetSnapshot, "snapshot")
            require_exact_type(publication_root, TrustAnchorRecord, "publication_root")
        require_canonical_str(load_detail, "load_detail", allow_empty=True)
        anchors: dict = {}
        if snapshot is not None:
            anchors = dict(snapshot.anchors_by_coordinate)
        object.__setattr__(self, "_snapshot", snapshot)
        object.__setattr__(self, "_publication_root", publication_root)
        object.__setattr__(self, "_max_snapshot_age", max_snapshot_age)
        object.__setattr__(self, "_load_failure", load_failure)
        object.__setattr__(self, "_load_detail", load_detail)
        object.__setattr__(self, "_anchors", MappingProxyType(anchors))

    # ------------------------------------------------------------------ build
    @classmethod
    def from_document(
        cls,
        document: Optional[bytes],
        *,
        publication_root: Optional[TrustAnchorRecord],
        max_snapshot_age: timedelta,
        last_accepted_set_version: Optional[int] = None,
    ) -> "SignedSnapshotTrustAnchorResolver":
        """Verify one complete document under a pinned root; never partially admit.

        ``document`` is the complete file content as read by the composition
        root, or ``None`` when the file could not be read. ``last_accepted_set_version``
        is the version the composition root's audit record names as previously
        accepted; a document at or below it is a rollback and is refused.
        """

        _require_max_age(max_snapshot_age)
        if last_accepted_set_version is not None and type(last_accepted_set_version) is not int:
            raise TrustedEvidenceContractError(
                "last_accepted_set_version must be an int or None"
            )

        def refused(failure: TrustAnchorSetLoadFailure, detail: str):
            return cls(
                snapshot=None,
                publication_root=None,
                max_snapshot_age=max_snapshot_age,
                load_failure=failure,
                load_detail=detail,
            )

        # The root is validated first: a snapshot may never be consulted for it.
        if publication_root is None:
            return refused(
                TrustAnchorSetLoadFailure.PUBLICATION_ROOT_ABSENT,
                "no pinned publication root was supplied; the root is never taken from the snapshot",
            )
        if type(publication_root) is not TrustAnchorRecord:
            return refused(
                TrustAnchorSetLoadFailure.PUBLICATION_ROOT_ABSENT,
                "the publication root must be exactly a TrustAnchorRecord",
            )
        if publication_root.capability is not TrustAnchorCapability.TRUST_ANCHOR_SET_PUBLICATION:
            return refused(
                TrustAnchorSetLoadFailure.PUBLICATION_ROOT_WRONG_CAPABILITY,
                "the pinned root does not hold TRUST_ANCHOR_SET_PUBLICATION; an anchor for "
                "another purpose never authenticates a trust-anchor set",
            )
        if document is None:
            return refused(
                TrustAnchorSetLoadFailure.DOCUMENT_UNAVAILABLE,
                "the snapshot document could not be read",
            )
        try:
            snapshot = parse_trust_anchor_set_document(document)
        except TrustedEvidenceContractError as exc:
            return refused(TrustAnchorSetLoadFailure.DOCUMENT_MALFORMED, str(exc))
        manifest = snapshot.manifest
        if manifest.publisher_coordinate != publication_root.coordinate:
            return refused(
                TrustAnchorSetLoadFailure.PUBLISHER_UNKNOWN,
                "the manifest names a publisher coordinate other than the pinned root",
            )
        for anchor in snapshot.anchors:
            if anchor.authority_id == publication_root.authority_id and anchor.key_id == publication_root.key_id:
                return refused(
                    TrustAnchorSetLoadFailure.SELF_AUTHENTICATING,
                    "the snapshot carries the publisher's own key; a snapshot may not "
                    "authenticate itself",
                )
            if anchor.public_key == publication_root.public_key:
                return refused(
                    TrustAnchorSetLoadFailure.SELF_AUTHENTICATING,
                    "the snapshot carries the publication root's public key under another "
                    "coordinate; a snapshot may not authenticate itself",
                )
        try:
            signature = decode_signature(snapshot.signature, "TrustAnchorSetSnapshot.signature")
            verified = publication_root.verification_key().verify(snapshot.signing_bytes(), signature)
        except TrustedEvidenceContractError as exc:
            return refused(TrustAnchorSetLoadFailure.SIGNATURE_INVALID, str(exc))
        if verified is not True:
            return refused(
                TrustAnchorSetLoadFailure.SIGNATURE_INVALID,
                "the manifest signature did not verify under the pinned publication root",
            )
        if last_accepted_set_version is not None and manifest.trust_anchor_set_version <= last_accepted_set_version:
            return refused(
                TrustAnchorSetLoadFailure.VERSION_ROLLBACK,
                f"set version {manifest.trust_anchor_set_version} is not above the last "
                f"accepted version {last_accepted_set_version}; a rollback or a re-published "
                "version is refused",
            )
        return cls(
            snapshot=snapshot,
            publication_root=publication_root,
            max_snapshot_age=max_snapshot_age,
            load_failure=None,
            load_detail="",
        )

    # ------------------------------------------------------------ immutability
    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(
            f"SignedSnapshotTrustAnchorResolver is immutable; cannot set {name!r}. "
            "A new snapshot means a new resolver (TR-1)."
        )

    def __delattr__(self, name: str) -> None:
        raise AttributeError(f"SignedSnapshotTrustAnchorResolver is immutable; cannot delete {name!r}")

    # ---------------------------------------------------------------- posture
    @property
    def is_production_authoritative(self) -> bool:
        """``True`` only when the complete snapshot was admitted at construction."""

        return self._load_failure is None

    @property
    def load_failure(self) -> Optional[TrustAnchorSetLoadFailure]:
        return self._load_failure

    @property
    def load_detail(self) -> str:
        return self._load_detail

    @property
    def snapshot(self) -> Optional[TrustAnchorSetSnapshot]:
        return self._snapshot

    @property
    def max_snapshot_age(self) -> timedelta:
        return self._max_snapshot_age

    @property
    def trust_anchor_set_id(self) -> str:
        if self._snapshot is None:
            return ""
        return self._snapshot.manifest.trust_anchor_set_id

    @property
    def trust_anchor_set_version(self) -> Optional[int]:
        if self._snapshot is None:
            return None
        return self._snapshot.manifest.trust_anchor_set_version

    # ---------------------------------------------------------------- resolve
    def resolve(
        self,
        coordinate: TrustAnchorCoordinate,
        *,
        as_of: Optional[datetime] = None,
    ) -> TrustAnchorResolution:
        """Resolve one exact coordinate at ``as_of``, in the fixed order above."""

        require_exact_type(
            coordinate, TrustAnchorCoordinate, "SignedSnapshotTrustAnchorResolver.resolve.coordinate"
        )
        # 1. the instant, before anything else is consulted
        if type(as_of) is not datetime or as_of.tzinfo is None or as_of.utcoffset() is None:
            return TrustAnchorResolution.refused(
                coordinate, _R.TRUSTED_EVIDENCE_TRUST_ANCHOR_SET_INSTANT_REQUIRED
            )
        # 2. complete admission
        snapshot = self._snapshot
        root = self._publication_root
        if self._load_failure is not None or snapshot is None or root is None:
            return TrustAnchorResolution.refused(
                coordinate, _R.TRUSTED_EVIDENCE_TRUST_ANCHOR_SET_UNAVAILABLE
            )
        # 3. publication root usable at as_of; set published and in force at as_of
        if root.lifecycle_refusal_at(as_of) is not None:
            return TrustAnchorResolution.refused(
                coordinate, _R.TRUSTED_EVIDENCE_TRUST_ANCHOR_SET_UNAVAILABLE
            )
        manifest = snapshot.manifest
        if as_of < manifest.published_at or as_of < manifest.effective_from:
            return TrustAnchorResolution.refused(
                coordinate, _R.TRUSTED_EVIDENCE_TRUST_ANCHOR_SET_UNAVAILABLE
            )
        # 4. freshness: the earlier of the signed effective_to and published_at + max age
        if as_of >= manifest.effective_to:
            return TrustAnchorResolution.refused(
                coordinate, _R.TRUSTED_EVIDENCE_TRUST_ANCHOR_SET_STALE
            )
        if as_of >= manifest.published_at + self._max_snapshot_age:
            return TrustAnchorResolution.refused(
                coordinate, _R.TRUSTED_EVIDENCE_TRUST_ANCHOR_SET_STALE
            )
        # 5. exact coordinate
        anchor = self._anchors.get(coordinate)
        if anchor is None:
            return TrustAnchorResolution.refused(coordinate, _R.TRUSTED_EVIDENCE_TRUST_ANCHOR_MISSING)
        # 6. the ordinary typed resolution
        return TrustAnchorResolution.resolved(coordinate, anchor)

    def __repr__(self) -> str:
        if self._load_failure is not None:
            return f"SignedSnapshotTrustAnchorResolver(refused={self._load_failure.value})"
        return (
            "SignedSnapshotTrustAnchorResolver("
            f"set={self.trust_anchor_set_id!r}@{self.trust_anchor_set_version}, "
            f"{len(self._anchors)} anchors)"
        )


def _require_max_age(value: object) -> timedelta:
    if type(value) is not timedelta or value <= timedelta(0):
        raise TrustedEvidenceContractError(
            "max_snapshot_age must be a positive timedelta; the owner configures it and "
            "there is no default"
        )
    return value

