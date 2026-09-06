"""Reusable production-resolver conformance harness (TR-1 to TR-3).

Any :class:`TrustAnchorResolverPort` implementation that claims
``is_production_authoritative = True`` can be driven through
:class:`ResolverConformance`; ``test_signed_snapshot_resolver_conformance.py``
runs it against the package's own :class:`SignedSnapshotTrustAnchorResolver`.

The harness holds only **test** key material derived from fixed seeds. It is a
test module, imported by tests, and ships in no wheel. It signs snapshots with
the package's reference signing key because a signed document must exist to be
verified; nothing here is publication tooling.
"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional, Sequence, Tuple

from ugence_trusted_evidence_authority.api import (
    TRUST_ANCHOR_SET_MANIFEST_SCHEMA_V1,
    KeyRevocation,
    SignedSnapshotTrustAnchorResolver,
    TrustAnchorCapability,
    TrustAnchorCoordinate,
    TrustAnchorRecord,
    TrustAnchorSetLoadFailure,
    TrustAnchorSetManifest,
    TrustAnchorSetSnapshot,
    TrustedEvidenceRefusalReason,
    TrustedEvidenceSigningKey,
    encode_public_key,
    encode_signature,
    render_trust_anchor_set_document,
    trust_anchor_collection_digest,
    trust_anchor_set_signing_bytes,
)

R = TrustedEvidenceRefusalReason

PUBLISHED_AT = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
EFFECTIVE_FROM = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
EFFECTIVE_TO = datetime(2026, 12, 1, 0, 0, tzinfo=timezone.utc)
MAX_AGE = timedelta(days=30)
FRESH_AS_OF = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)
SET_ID = "production-anchors"

PUBLISHER_SEED = b"\x11" * 32
ROOT_SEED = b"\x22" * 32
PRODUCER_SEED = b"\x33" * 32
ISSUER_SEED = b"\x44" * 32


def signing_key(seed: bytes) -> TrustedEvidenceSigningKey:
    return TrustedEvidenceSigningKey(seed)


def public_hex(seed: bytes) -> str:
    return encode_public_key(signing_key(seed).verification_key.public_key_bytes)


def publication_root(
    seed: bytes = PUBLISHER_SEED,
    *,
    authority_id: str = "trust-operations",
    key_id: str = "publication-key-1",
    capability: TrustAnchorCapability = TrustAnchorCapability.TRUST_ANCHOR_SET_PUBLICATION,
    **overrides,
) -> TrustAnchorRecord:
    fields = dict(
        authority_id=authority_id,
        key_id=key_id,
        capability=capability,
        public_key=public_hex(seed),
        trust_anchor_set_id="bootstrap",
        trust_anchor_set_version="1",
        effective_from=EFFECTIVE_FROM - timedelta(days=365),
        effective_to=EFFECTIVE_TO + timedelta(days=365),
    )
    fields.update(overrides)
    return TrustAnchorRecord(**fields)


def anchor(
    seed: bytes,
    *,
    authority_id: str,
    key_id: str,
    capability: TrustAnchorCapability,
    set_version: int = 1,
    **overrides,
) -> TrustAnchorRecord:
    fields = dict(
        authority_id=authority_id,
        key_id=key_id,
        capability=capability,
        public_key=public_hex(seed),
        trust_anchor_set_id=SET_ID,
        trust_anchor_set_version=str(set_version),
        effective_from=EFFECTIVE_FROM - timedelta(days=30),
        effective_to=EFFECTIVE_TO + timedelta(days=30),
    )
    fields.update(overrides)
    return TrustAnchorRecord(**fields)


def default_anchors(set_version: int = 1) -> Tuple[TrustAnchorRecord, ...]:
    return ordered(
        anchor(PRODUCER_SEED, authority_id="producer-a", key_id="pk-1",
               capability=TrustAnchorCapability.EVIDENCE_PRODUCTION, set_version=set_version),
        anchor(ISSUER_SEED, authority_id="verifier-1", key_id="vk-1",
               capability=TrustAnchorCapability.RECEIPT_ISSUANCE, set_version=set_version),
        anchor(PRODUCER_SEED, authority_id="observer-omega", key_id="ok-1",
               capability=TrustAnchorCapability.EFFECT_ATTESTATION_INDEPENDENT_OBSERVER,
               set_version=set_version),
    )


def ordered(*anchors: TrustAnchorRecord) -> Tuple[TrustAnchorRecord, ...]:
    return tuple(sorted(anchors, key=lambda a: (a.authority_id, a.key_id, a.capability.value)))


def manifest(
    anchors: Sequence[TrustAnchorRecord],
    *,
    set_version: int = 1,
    published_at: datetime = PUBLISHED_AT,
    effective_from: datetime = EFFECTIVE_FROM,
    effective_to: datetime = EFFECTIVE_TO,
    publisher: Optional[TrustAnchorRecord] = None,
    **overrides,
) -> TrustAnchorSetManifest:
    root = publisher if publisher is not None else publication_root()
    fields = dict(
        schema_version=TRUST_ANCHOR_SET_MANIFEST_SCHEMA_V1,
        trust_anchor_set_id=SET_ID,
        trust_anchor_set_version=set_version,
        publisher_authority_id=root.authority_id,
        publisher_key_id=root.key_id,
        published_at=published_at,
        effective_from=effective_from,
        effective_to=effective_to,
        anchor_count=len(anchors),
        anchor_collection_digest=trust_anchor_collection_digest(tuple(anchors)),
    )
    fields.update(overrides)
    return TrustAnchorSetManifest(**fields)


def sign(m: TrustAnchorSetManifest, seed: bytes = PUBLISHER_SEED) -> str:
    return encode_signature(signing_key(seed).sign(trust_anchor_set_signing_bytes(m)))


def snapshot(
    anchors: Optional[Sequence[TrustAnchorRecord]] = None,
    *,
    set_version: int = 1,
    seed: bytes = PUBLISHER_SEED,
    **manifest_overrides,
) -> TrustAnchorSetSnapshot:
    records = tuple(anchors) if anchors is not None else default_anchors(set_version)
    m = manifest(records, set_version=set_version, **manifest_overrides)
    return TrustAnchorSetSnapshot(manifest=m, anchors=records, signature=sign(m, seed))


def document(snap: Optional[TrustAnchorSetSnapshot] = None, **kw) -> bytes:
    return render_trust_anchor_set_document(snap if snap is not None else snapshot(**kw))


_DEFAULT = object()


def resolver(
    doc=_DEFAULT,
    *,
    root: Optional[TrustAnchorRecord] = None,
    max_age: timedelta = MAX_AGE,
    last_accepted: Optional[int] = None,
    **kw,
) -> SignedSnapshotTrustAnchorResolver:
    """``doc`` defaults to a freshly signed good document; pass ``None`` for an unavailable one."""

    return SignedSnapshotTrustAnchorResolver.from_document(
        document(**kw) if doc is _DEFAULT else doc,
        publication_root=root if root is not None else publication_root(),
        max_snapshot_age=max_age,
        last_accepted_set_version=last_accepted,
    )


def publisher_signed_document(
    anchors: Sequence[TrustAnchorRecord],
    *,
    seed: bytes = PUBLISHER_SEED,
    anchor_count: Optional[int] = None,
    set_version: int = 1,
) -> bytes:
    """A document a *malicious or careless publisher* could sign: the manifest is
    genuinely signed over whatever records are listed, in the order given, with
    the count as given. It bypasses ``TrustAnchorSetSnapshot`` so the resolver's
    own admission checks are what must refuse it."""

    from ugence_trusted_evidence_authority.authority import trust_snapshot as _mod

    records = tuple(anchors)
    m = manifest(records, set_version=set_version,
                 anchor_count=len(records) if anchor_count is None else anchor_count)
    payload = {
        "document_schema": _mod.TRUST_ANCHOR_SET_DOCUMENT_SCHEMA_V1,
        "manifest": {
            "schema_version": m.schema_version,
            "trust_anchor_set_id": m.trust_anchor_set_id,
            "trust_anchor_set_version": m.trust_anchor_set_version,
            "publisher_authority_id": m.publisher_authority_id,
            "publisher_key_id": m.publisher_key_id,
            "published_at": _mod._format_instant(m.published_at),
            "effective_from": _mod._format_instant(m.effective_from),
            "effective_to": _mod._format_instant(m.effective_to),
            "anchor_count": m.anchor_count,
            "anchor_collection_digest": m.anchor_collection_digest,
            "signature_profile": m.signature_profile,
            "signature_encoding": m.signature_encoding,
        },
        "anchors": [_mod._render_anchor(a) for a in records],
        "signature": sign(m, seed),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def edit_document(doc: bytes, mutate: Callable[[dict], None]) -> bytes:
    """Parse, mutate in place, re-render without re-signing: a tamper."""

    loaded = json.loads(doc.decode("utf-8"))
    mutate(loaded)
    return json.dumps(loaded, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


PRODUCER_COORDINATE = TrustAnchorCoordinate(
    authority_id="producer-a", key_id="pk-1", capability=TrustAnchorCapability.EVIDENCE_PRODUCTION
)
OBSERVER_COORDINATE = TrustAnchorCoordinate(
    authority_id="observer-omega", key_id="ok-1",
    capability=TrustAnchorCapability.EFFECT_ATTESTATION_INDEPENDENT_OBSERVER,
)
ABSENT_COORDINATE = TrustAnchorCoordinate(
    authority_id="nobody", key_id="nk-1", capability=TrustAnchorCapability.EVIDENCE_PRODUCTION
)


# --------------------------------------------------------------------------- #
# The reusable harness
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ConformanceCase:
    name: str
    check: Callable[[], None]


class ResolverConformance:
    """Drive a production-resolver factory through every TR-1..TR-3 property.

    ``build(document, *, root, max_age, last_accepted)`` must return a resolver.
    Every case is independent; :meth:`cases` returns them for parametrization.
    """

    def __init__(self, build: Callable[..., object]) -> None:
        self._build = build

    def _r(self, doc=_DEFAULT, **kw):
        root = kw.pop("root", publication_root())
        max_age = kw.pop("max_age", MAX_AGE)
        last_accepted = kw.pop("last_accepted", None)
        return self._build(document(**kw) if doc is _DEFAULT else doc, root=root,
                           max_age=max_age, last_accepted=last_accepted)

    # -- instant --------------------------------------------------------------
    def instant_required_before_any_lookup(self) -> None:
        r = self._r()
        assert r.is_production_authoritative is True
        for bad in (None, datetime(2026, 9, 6, 12, 0), "2026-09-06T12:00:00Z", 1_757_160_000, object()):
            out = r.resolve(PRODUCER_COORDINATE, as_of=bad)
            assert out.anchor is None
            assert out.refusal_reason is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_SET_INSTANT_REQUIRED, bad
        # positional-only omission is the same refusal
        assert r.resolve(PRODUCER_COORDINATE).refusal_reason is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_SET_INSTANT_REQUIRED

    def datetime_subclass_is_not_an_instant(self) -> None:
        class Sub(datetime):
            pass

        r = self._r()
        sub = Sub(2026, 9, 6, 12, 0, tzinfo=timezone.utc)
        assert r.resolve(PRODUCER_COORDINATE, as_of=sub).refusal_reason is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_SET_INSTANT_REQUIRED

    def valid_instant_resolves_exact_coordinate(self) -> None:
        r = self._r()
        out = r.resolve(PRODUCER_COORDINATE, as_of=FRESH_AS_OF)
        assert out.refusal_reason is None
        assert out.anchor is not None and out.anchor.coordinate == PRODUCER_COORDINATE
        assert out.coordinate == PRODUCER_COORDINATE
        assert r.resolve(OBSERVER_COORDINATE, as_of=FRESH_AS_OF).anchor is not None
        # a near miss is a miss
        near = dataclasses.replace(PRODUCER_COORDINATE, capability=TrustAnchorCapability.RECEIPT_ISSUANCE)
        assert r.resolve(near, as_of=FRESH_AS_OF).refusal_reason is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_MISSING
        assert r.resolve(ABSENT_COORDINATE, as_of=FRESH_AS_OF).refusal_reason is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_MISSING

    # -- freshness ------------------------------------------------------------
    def same_snapshot_resolves_while_fresh_and_refuses_when_stale(self) -> None:
        r = self._r()
        assert r.resolve(PRODUCER_COORDINATE, as_of=FRESH_AS_OF).anchor is not None
        boundary = PUBLISHED_AT + MAX_AGE
        assert r.resolve(PRODUCER_COORDINATE, as_of=boundary - timedelta(microseconds=1)).anchor is not None
        assert r.resolve(PRODUCER_COORDINATE, as_of=boundary).refusal_reason is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_SET_STALE
        assert r.resolve(PRODUCER_COORDINATE, as_of=boundary + timedelta(days=400)).refusal_reason is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_SET_STALE
        # and fresh again for an earlier instant: nothing was cached by the stale call
        assert r.resolve(PRODUCER_COORDINATE, as_of=FRESH_AS_OF).anchor is not None

    def signed_effective_to_bounds_freshness_when_earlier_than_max_age(self) -> None:
        r = self._r(max_age=timedelta(days=3650))
        assert r.resolve(PRODUCER_COORDINATE, as_of=EFFECTIVE_TO - timedelta(seconds=1)).anchor is not None
        assert r.resolve(PRODUCER_COORDINATE, as_of=EFFECTIVE_TO).refusal_reason is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_SET_STALE

    def set_not_yet_in_force_is_unavailable_not_stale(self) -> None:
        r = self._r()
        assert r.resolve(PRODUCER_COORDINATE, as_of=EFFECTIVE_FROM - timedelta(seconds=1)).refusal_reason is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_SET_UNAVAILABLE
        assert r.resolve(PRODUCER_COORDINATE, as_of=EFFECTIVE_FROM).anchor is not None
        later = self._r(effective_from=EFFECTIVE_FROM + timedelta(days=2))
        assert later.resolve(PRODUCER_COORDINATE, as_of=EFFECTIVE_FROM + timedelta(days=1)).refusal_reason is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_SET_UNAVAILABLE

    def no_startup_freshness_decision_survives(self) -> None:
        """Freshness is decided per resolution, never once at construction."""

        r = self._r()
        assert r.is_production_authoritative is True
        stale_first = r.resolve(PRODUCER_COORDINATE, as_of=PUBLISHED_AT + MAX_AGE + timedelta(days=1))
        assert stale_first.refusal_reason is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_SET_STALE
        assert r.is_production_authoritative is True  # posture is about admission, not freshness
        assert r.resolve(PRODUCER_COORDINATE, as_of=FRESH_AS_OF).anchor is not None

    # -- admission ------------------------------------------------------------
    def unavailable_document_refuses_everything(self) -> None:
        r = self._r(None)
        assert r.is_production_authoritative is False
        assert r.load_failure is TrustAnchorSetLoadFailure.DOCUMENT_UNAVAILABLE
        assert r.resolve(PRODUCER_COORDINATE, as_of=FRESH_AS_OF).refusal_reason is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_SET_UNAVAILABLE
        # the instant is still checked first, even with nothing loaded
        assert r.resolve(PRODUCER_COORDINATE).refusal_reason is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_SET_INSTANT_REQUIRED

    def malformed_and_partial_documents_refuse(self) -> None:
        good = document()
        for bad in (b"", b"{", good[: len(good) // 2], b"\xff\xfe", b"[]", b'{"document_schema": 1}',
                    good + b" ", b" " + good, good.replace(b'"anchors"', b'"anchor_list"'),
                    good.replace(b",", b", ", 1)):
            r = self._r(bad)
            assert r.is_production_authoritative is False, bad[:20]
            assert r.load_failure is TrustAnchorSetLoadFailure.DOCUMENT_MALFORMED, bad[:20]
            assert r.resolve(PRODUCER_COORDINATE, as_of=FRESH_AS_OF).refusal_reason is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_SET_UNAVAILABLE

    def tampered_manifest_collection_anchor_or_digest_refuses(self) -> None:
        good = document()

        def bump_version(d): d["manifest"]["trust_anchor_set_version"] += 1
        def extend_window(d): d["manifest"]["effective_to"] = "2030-01-01T00:00:00.000000Z"
        def swap_key(d): d["anchors"][0]["public_key"] = public_hex(b"\x99" * 32)
        def undisable(d): d["anchors"][0]["disabled"] = True
        def digest(d): d["manifest"]["anchor_collection_digest"] = "0" * 64
        def signature(d): d["signature"] = "0" * 128
        def remove(d):
            d["anchors"].pop(); d["manifest"]["anchor_count"] -= 1
        def append(d):
            extra = json.loads(json.dumps(d["anchors"][0])); extra["key_id"] = "pk-9"
            d["anchors"].append(extra); d["manifest"]["anchor_count"] += 1
        def reorder(d): d["anchors"].reverse()

        for label, mutate in (("version", bump_version), ("window", extend_window), ("key", swap_key),
                              ("disabled", undisable), ("digest", digest), ("signature", signature),
                              ("removed", remove), ("appended", append), ("reordered", reorder)):
            r = self._r(edit_document(good, mutate))
            assert r.is_production_authoritative is False, label
            assert r.load_failure in (TrustAnchorSetLoadFailure.DOCUMENT_MALFORMED,
                                      TrustAnchorSetLoadFailure.SIGNATURE_INVALID), label
            assert r.resolve(PRODUCER_COORDINATE, as_of=FRESH_AS_OF).refusal_reason is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_SET_UNAVAILABLE, label

    def signature_by_another_key_refuses(self) -> None:
        r = self._r(document(seed=b"\x77" * 32))
        assert r.load_failure is TrustAnchorSetLoadFailure.SIGNATURE_INVALID
        assert r.is_production_authoritative is False

    def duplicate_coordinate_refuses(self) -> None:
        a = default_anchors()
        good = document()

        def duplicate(d):
            d["anchors"].append(json.loads(json.dumps(d["anchors"][-1])))
            d["manifest"]["anchor_count"] += 1

        r = self._r(edit_document(good, duplicate))
        assert r.load_failure is TrustAnchorSetLoadFailure.DOCUMENT_MALFORMED
        # and a publisher who genuinely signs a duplicate is refused all the same
        dup = a + (dataclasses.replace(a[-1], public_key=public_hex(b"\x66" * 32)),)
        r = self._r(publisher_signed_document(dup))
        assert r.is_production_authoritative is False
        assert r.load_failure is TrustAnchorSetLoadFailure.DOCUMENT_MALFORMED
        assert r.resolve(PRODUCER_COORDINATE, as_of=FRESH_AS_OF).refusal_reason is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_SET_UNAVAILABLE

    def publisher_signed_structural_defects_refuse(self) -> None:
        """A valid signature does not launder a malformed set (TR-2)."""

        a = default_anchors()
        # out of canonical order
        r = self._r(publisher_signed_document(tuple(reversed(a))))
        assert r.load_failure is TrustAnchorSetLoadFailure.DOCUMENT_MALFORMED
        # count that does not match the records
        r = self._r(publisher_signed_document(a, anchor_count=len(a) - 1))
        assert r.load_failure is TrustAnchorSetLoadFailure.DOCUMENT_MALFORMED
        # a record naming another set version
        mixed = ordered(*(a[:-1] + (dataclasses.replace(a[-1], trust_anchor_set_version="2"),)))
        r = self._r(publisher_signed_document(mixed))
        assert r.load_failure is TrustAnchorSetLoadFailure.DOCUMENT_MALFORMED
        # a record naming another set
        mixed = ordered(*(a[:-1] + (dataclasses.replace(a[-1], trust_anchor_set_id="other-set"),)))
        r = self._r(publisher_signed_document(mixed))
        assert r.load_failure is TrustAnchorSetLoadFailure.DOCUMENT_MALFORMED
        for defect in (tuple(reversed(a)),):
            assert self._r(publisher_signed_document(defect)).is_production_authoritative is False

    def publisher_signing_bytes_are_domain_separated_and_pinned(self) -> None:
        """The publication domain is element 0 of the frame, so a signature over a
        bare manifest, or over another artifact's frame, never verifies here."""

        from ugence_trusted_evidence_authority.api import (
            SIGNED_INPUT_LENGTH_PREFIX_BYTES,
            TRUST_ANCHOR_SET_PUBLICATION_SIGNING_DOMAIN,
        )

        m = manifest(default_anchors())
        frame = trust_anchor_set_signing_bytes(m)
        width = SIGNED_INPUT_LENGTH_PREFIX_BYTES
        domain = TRUST_ANCHOR_SET_PUBLICATION_SIGNING_DOMAIN.encode("utf-8")
        assert frame[:width] == (2).to_bytes(width, "big")
        assert frame[width:2 * width] == len(domain).to_bytes(width, "big")
        assert frame[2 * width:2 * width + len(domain)] == domain
        assert frame.endswith(m.canonical_bytes())
        assert len(frame) == 3 * width + len(domain) + len(m.canonical_bytes())

    def rollback_and_duplicate_versions_refuse(self) -> None:
        assert self._r(set_version=3, last_accepted=2).is_production_authoritative is True
        for version in (2, 1):
            r = self._r(set_version=version, last_accepted=2)
            assert r.is_production_authoritative is False, version
            assert r.load_failure is TrustAnchorSetLoadFailure.VERSION_ROLLBACK, version
            assert r.resolve(PRODUCER_COORDINATE, as_of=FRESH_AS_OF).refusal_reason is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_SET_UNAVAILABLE

    def malformed_public_point_refuses(self) -> None:
        good = document()
        for label, key in (("identity", "01" + "00" * 31), ("all-zero", "00" * 32),
                           ("non-canonical-identity", "01" + "00" * 30 + "80"), ("short", "ab" * 31),
                           ("uppercase", public_hex(PRODUCER_SEED).upper())):
            def swap(d, key=key): d["anchors"][0]["public_key"] = key
            r = self._r(edit_document(good, swap))
            assert r.is_production_authoritative is False, label
            assert r.load_failure is TrustAnchorSetLoadFailure.DOCUMENT_MALFORMED, label

    # -- publication root -----------------------------------------------------
    def wrong_capability_root_refuses(self) -> None:
        for capability in TrustAnchorCapability:
            if capability is TrustAnchorCapability.TRUST_ANCHOR_SET_PUBLICATION:
                continue
            r = self._r(root=publication_root(capability=capability))
            assert r.is_production_authoritative is False, capability
            assert r.load_failure is TrustAnchorSetLoadFailure.PUBLICATION_ROOT_WRONG_CAPABILITY, capability

    def absent_or_unknown_root_refuses(self) -> None:
        r = self._r(root=None)
        assert r.load_failure is TrustAnchorSetLoadFailure.PUBLICATION_ROOT_ABSENT
        other = publication_root(ROOT_SEED, key_id="publication-key-2")
        r = self._r(root=other)
        assert r.load_failure is TrustAnchorSetLoadFailure.PUBLISHER_UNKNOWN
        assert r.resolve(PRODUCER_COORDINATE, as_of=FRESH_AS_OF).refusal_reason is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_SET_UNAVAILABLE

    def self_authenticating_snapshot_refuses(self) -> None:
        """The root is never drawn from the snapshot it is asked to authenticate."""

        root = publication_root()
        # (a) the publisher's own key under another capability inside the set
        inside = default_anchors() + (anchor(PUBLISHER_SEED, authority_id=root.authority_id, key_id=root.key_id,
                                             capability=TrustAnchorCapability.EVIDENCE_PRODUCTION),)
        r = self._r(document(snapshot(ordered(*inside))))
        assert r.load_failure is TrustAnchorSetLoadFailure.SELF_AUTHENTICATING
        # (a') the publisher's coordinate inside the set even with a rotated key
        rotated = default_anchors() + (anchor(ROOT_SEED, authority_id=root.authority_id, key_id=root.key_id,
                                              capability=TrustAnchorCapability.EVIDENCE_PRODUCTION),)
        r = self._r(document(snapshot(ordered(*rotated))))
        assert r.load_failure is TrustAnchorSetLoadFailure.SELF_AUTHENTICATING
        # (b) the same public key under a different coordinate
        inside = default_anchors() + (anchor(PUBLISHER_SEED, authority_id="someone-else", key_id="k",
                                             capability=TrustAnchorCapability.EVIDENCE_PRODUCTION),)
        r = self._r(document(snapshot(ordered(*inside))))
        assert r.load_failure is TrustAnchorSetLoadFailure.SELF_AUTHENTICATING
        # (c) a publication-capability anchor inside a snapshot is refused at the contract
        try:
            snapshot(ordered(*(default_anchors() + (anchor(ROOT_SEED, authority_id="x", key_id="y",
                     capability=TrustAnchorCapability.TRUST_ANCHOR_SET_PUBLICATION),))))
        except Exception as exc:  # noqa: BLE001
            assert "TRUST_ANCHOR_SET_PUBLICATION" in str(exc)
        else:
            raise AssertionError("a snapshot carried a publication-capability anchor")

    def revoked_or_expired_root_makes_the_set_unavailable_at_that_instant(self) -> None:
        revoked = publication_root(revocation=KeyRevocation(effective_at=FRESH_AS_OF + timedelta(days=1)))
        r = self._r(root=revoked)
        assert r.is_production_authoritative is True
        assert r.resolve(PRODUCER_COORDINATE, as_of=FRESH_AS_OF).anchor is not None
        assert r.resolve(PRODUCER_COORDINATE, as_of=FRESH_AS_OF + timedelta(days=1)).refusal_reason is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_SET_UNAVAILABLE

    # -- immutability, no cache -----------------------------------------------
    def contents_are_immutable(self) -> None:
        r = self._r()
        for name in ("_snapshot", "_anchors", "_max_snapshot_age", "is_production_authoritative", "extra"):
            try:
                setattr(r, name, None)
            except AttributeError:
                continue
            raise AssertionError(name)
        assert not hasattr(r, "with_anchor") and not hasattr(r, "add") and not hasattr(r, "refresh")

    def no_cached_fallback_after_unavailable_or_stale(self) -> None:
        r = self._r()
        fresh = r.resolve(PRODUCER_COORDINATE, as_of=FRESH_AS_OF)
        assert fresh.anchor is not None
        stale = r.resolve(PRODUCER_COORDINATE, as_of=PUBLISHED_AT + MAX_AGE)
        assert stale.anchor is None and stale.refusal_reason is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_SET_STALE
        again = r.resolve(PRODUCER_COORDINATE, as_of=PUBLISHED_AT + MAX_AGE)
        assert again.anchor is None
        broken = self._r(None)
        assert broken.resolve(PRODUCER_COORDINATE, as_of=FRESH_AS_OF).anchor is None
        assert broken.resolve(PRODUCER_COORDINATE, as_of=FRESH_AS_OF).anchor is None

    def empty_set_denies(self) -> None:
        r = self._r(document(snapshot(())))
        assert r.is_production_authoritative is True
        assert r.resolve(PRODUCER_COORDINATE, as_of=FRESH_AS_OF).refusal_reason is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_MISSING

    def lifecycle_stays_with_the_verifier(self) -> None:
        """A resolved record is returned as it stands; the resolver evaluates no anchor lifecycle."""

        revoked = anchor(PRODUCER_SEED, authority_id="producer-a", key_id="pk-1",
                         capability=TrustAnchorCapability.EVIDENCE_PRODUCTION,
                         revocation=KeyRevocation(effective_at=EFFECTIVE_FROM - timedelta(days=1)))
        others = tuple(a for a in default_anchors() if a.coordinate != PRODUCER_COORDINATE)
        r = self._r(document(snapshot(ordered(revoked, *others))))
        out = r.resolve(PRODUCER_COORDINATE, as_of=FRESH_AS_OF)
        assert out.anchor is not None
        assert out.anchor.lifecycle_refusal_at(FRESH_AS_OF) is R.TRUSTED_EVIDENCE_KEY_REVOKED

    def cases(self) -> Tuple[ConformanceCase, ...]:
        names = [n for n in dir(self) if not n.startswith("_") and n != "cases"]
        return tuple(ConformanceCase(n, getattr(self, n)) for n in sorted(names))
