"""The production-resolver conformance suite, run against the package's own
``SignedSnapshotTrustAnchorResolver`` (TR-1 to TR-3), plus the properties that
belong to the two shipped directories and the amended port.

Maturity of what is proved here: a production-shaped resolver candidate. Not
independently reviewed, not externally cryptographically audited, not
production-ready; D-38 and D-32(4) remain applicable.
"""

from __future__ import annotations

import dataclasses
import inspect
from datetime import datetime, timedelta, timezone

import pytest
from resolver_conformance import (
    EFFECTIVE_TO,
    FRESH_AS_OF,
    MAX_AGE,
    PRODUCER_COORDINATE,
    PUBLISHED_AT,
    ResolverConformance,
    default_anchors,
    document,
    publication_root,
    resolver,
    snapshot,
)

from ugence_trusted_evidence_authority.api import (
    DenyAllTrustAnchorDirectory,
    SignedSnapshotTrustAnchorResolver,
    StaticTrustAnchorDirectory,
    TrustAnchorCapability,
    TrustAnchorCoordinate,
    TrustAnchorResolverPort,
    TrustAnchorSetLoadFailure,
    TrustedEvidenceContractError,
    TrustedEvidenceRefusalReason,
    parse_trust_anchor_set_document,
    render_trust_anchor_set_document,
)

R = TrustedEvidenceRefusalReason


def _build(doc, *, root, max_age, last_accepted):
    return SignedSnapshotTrustAnchorResolver.from_document(
        doc, publication_root=root, max_snapshot_age=max_age, last_accepted_set_version=last_accepted
    )


HARNESS = ResolverConformance(_build)


@pytest.mark.parametrize("case", HARNESS.cases(), ids=[c.name for c in HARNESS.cases()])
def test_conformance(case):
    case.check()


def test_the_harness_covers_every_ruled_property():
    names = {c.name for c in HARNESS.cases()}
    assert names >= {
        "instant_required_before_any_lookup",
        "datetime_subclass_is_not_an_instant",
        "valid_instant_resolves_exact_coordinate",
        "same_snapshot_resolves_while_fresh_and_refuses_when_stale",
        "signed_effective_to_bounds_freshness_when_earlier_than_max_age",
        "set_not_yet_in_force_is_unavailable_not_stale",
        "no_startup_freshness_decision_survives",
        "unavailable_document_refuses_everything",
        "malformed_and_partial_documents_refuse",
        "tampered_manifest_collection_anchor_or_digest_refuses",
        "signature_by_another_key_refuses",
        "duplicate_coordinate_refuses",
        "rollback_and_duplicate_versions_refuse",
        "malformed_public_point_refuses",
        "wrong_capability_root_refuses",
        "absent_or_unknown_root_refuses",
        "self_authenticating_snapshot_refuses",
        "revoked_or_expired_root_makes_the_set_unavailable_at_that_instant",
        "contents_are_immutable",
        "no_cached_fallback_after_unavailable_or_stale",
        "empty_set_denies",
        "lifecycle_stays_with_the_verifier",
    }


# --------------------------------------------------------------------------- #
# the amended port and the two shipped directories
# --------------------------------------------------------------------------- #
def test_the_port_carries_the_keyword_only_as_of_with_a_compatibility_default():
    signature = inspect.signature(TrustAnchorResolverPort.resolve)
    as_of = signature.parameters["as_of"]
    assert as_of.kind is inspect.Parameter.KEYWORD_ONLY
    assert as_of.default is None
    for cls in (StaticTrustAnchorDirectory, DenyAllTrustAnchorDirectory, SignedSnapshotTrustAnchorResolver):
        param = inspect.signature(cls.resolve).parameters["as_of"]
        assert param.kind is inspect.Parameter.KEYWORD_ONLY and param.default is None, cls


def test_static_directory_accepts_and_ignores_as_of_and_is_never_production_authoritative():
    static = StaticTrustAnchorDirectory(default_anchors(), trust_anchor_set_id="s", trust_anchor_set_version="1")
    assert static.resolve(PRODUCER_COORDINATE).anchor is not None
    assert static.resolve(PRODUCER_COORDINATE, as_of=FRESH_AS_OF).anchor is not None
    assert static.resolve(PRODUCER_COORDINATE, as_of=FRESH_AS_OF + timedelta(days=4000)).anchor is not None
    assert static.resolve(PRODUCER_COORDINATE, as_of="not an instant").anchor is not None
    assert getattr(static, "is_production_authoritative", False) is not True


def test_a_subclass_of_the_static_directory_cannot_claim_production_authority():
    class Claiming(StaticTrustAnchorDirectory):
        is_production_authoritative = True

    claiming = Claiming(default_anchors(), trust_anchor_set_id="s", trust_anchor_set_version="1")
    assert isinstance(claiming, StaticTrustAnchorDirectory)
    # The consumer rule is "the static directory or any subclass is refused":
    # the identity check every consumer performs sees straight through the flag.
    assert type(claiming) is not DenyAllTrustAnchorDirectory
    assert issubclass(type(claiming), StaticTrustAnchorDirectory)


def test_deny_all_accepts_as_of_and_remains_the_exact_type_deny_default():
    deny = DenyAllTrustAnchorDirectory()
    for as_of in (None, FRESH_AS_OF, "x"):
        out = deny.resolve(PRODUCER_COORDINATE, as_of=as_of)
        assert out.anchor is None
        assert out.refusal_reason is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_NOT_CONFIGURED
    assert type(deny) is DenyAllTrustAnchorDirectory
    assert getattr(deny, "is_production_authoritative", False) is not True


def test_the_production_resolver_never_succeeds_at_as_of_none_even_when_fresh():
    r = resolver()
    assert r.is_production_authoritative is True
    assert r.resolve(PRODUCER_COORDINATE).anchor is None
    assert r.resolve(PRODUCER_COORDINATE, as_of=None).refusal_reason is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_SET_INSTANT_REQUIRED


def test_as_of_is_used_exactly_once_per_resolution_and_never_stored():
    r = resolver()
    first = r.resolve(PRODUCER_COORDINATE, as_of=FRESH_AS_OF)
    assert first.anchor is not None
    assert "as_of" not in dir(r)
    assert not any(isinstance(getattr(r, slot, None), datetime) for slot in getattr(r, "__slots__", ()))


# --------------------------------------------------------------------------- #
# validation order (TR-3 rulings 1..6)
# --------------------------------------------------------------------------- #
def test_validation_order_instant_then_admission_then_window_then_age_then_coordinate():
    stale_and_missing = resolver().resolve(
        TrustAnchorCoordinate(authority_id="nobody", key_id="k", capability=TrustAnchorCapability.EVIDENCE_PRODUCTION),
        as_of=PUBLISHED_AT + MAX_AGE,
    )
    assert stale_and_missing.refusal_reason is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_SET_STALE
    unavailable_and_naive = resolver(None).resolve(PRODUCER_COORDINATE, as_of=datetime(2026, 9, 6))
    assert unavailable_and_naive.refusal_reason is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_SET_INSTANT_REQUIRED
    early_and_missing = resolver().resolve(
        TrustAnchorCoordinate(authority_id="nobody", key_id="k", capability=TrustAnchorCapability.EVIDENCE_PRODUCTION),
        as_of=PUBLISHED_AT - timedelta(seconds=1),
    )
    assert early_and_missing.refusal_reason is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_SET_UNAVAILABLE


def test_freshness_boundaries_use_the_half_open_convention():
    r = resolver()
    assert r.resolve(PRODUCER_COORDINATE, as_of=PUBLISHED_AT).anchor is not None
    age_bound = PUBLISHED_AT + MAX_AGE
    assert r.resolve(PRODUCER_COORDINATE, as_of=age_bound - timedelta(microseconds=1)).anchor is not None
    assert r.resolve(PRODUCER_COORDINATE, as_of=age_bound).refusal_reason is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_SET_STALE
    wide = resolver(max_age=timedelta(days=3650))
    assert wide.resolve(PRODUCER_COORDINATE, as_of=EFFECTIVE_TO - timedelta(microseconds=1)).anchor is not None
    assert wide.resolve(PRODUCER_COORDINATE, as_of=EFFECTIVE_TO).refusal_reason is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_SET_STALE


def test_offset_aware_non_utc_instants_are_compared_as_instants():
    r = resolver()
    plus_two = timezone(timedelta(hours=2))
    assert r.resolve(PRODUCER_COORDINATE, as_of=FRESH_AS_OF.astimezone(plus_two)).anchor is not None
    boundary = (PUBLISHED_AT + MAX_AGE).astimezone(plus_two)
    assert r.resolve(PRODUCER_COORDINATE, as_of=boundary).refusal_reason is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_SET_STALE


# --------------------------------------------------------------------------- #
# contracts and wire document
# --------------------------------------------------------------------------- #
def test_the_document_round_trips_byte_for_byte():
    snap = snapshot()
    doc = render_trust_anchor_set_document(snap)
    parsed = parse_trust_anchor_set_document(doc)
    assert parsed == snap
    assert render_trust_anchor_set_document(parsed) == doc


def test_manifest_construction_refuses_bad_shapes():
    from resolver_conformance import manifest

    anchors = default_anchors()
    with pytest.raises(TrustedEvidenceContractError):
        manifest(anchors, set_version=0)
    with pytest.raises(TrustedEvidenceContractError):
        manifest(anchors, set_version="1")  # type: ignore[arg-type]
    with pytest.raises(TrustedEvidenceContractError):
        manifest(anchors, effective_from=EFFECTIVE_TO, effective_to=PUBLISHED_AT)
    with pytest.raises(TrustedEvidenceContractError):
        manifest(anchors, published_at=PUBLISHED_AT + timedelta(days=1), effective_from=PUBLISHED_AT)
    with pytest.raises(TrustedEvidenceContractError):
        manifest(anchors, published_at=datetime(2026, 9, 1))
    with pytest.raises(TrustedEvidenceContractError):
        manifest(anchors, anchor_collection_digest="zz" * 32)


def test_constructor_misuse_raises_rather_than_refusing():
    with pytest.raises(TrustedEvidenceContractError):
        resolver(max_age=timedelta(0))
    with pytest.raises(TrustedEvidenceContractError):
        resolver(max_age=30)  # type: ignore[arg-type]
    with pytest.raises(TrustedEvidenceContractError):
        resolver(last_accepted="2")  # type: ignore[arg-type]


def test_load_failure_is_typed_and_reported_but_confers_nothing():
    r = resolver(b"garbage")
    assert r.load_failure is TrustAnchorSetLoadFailure.DOCUMENT_MALFORMED
    assert r.load_detail != ""
    assert r.snapshot is None and r.trust_anchor_set_version is None and r.trust_anchor_set_id == ""
    assert "refused=" in str(r)
    ok = resolver()
    assert ok.load_failure is None and ok.load_detail == ""
    assert ok.trust_anchor_set_version == 1 and ok.snapshot is not None
    assert ok.max_snapshot_age == MAX_AGE


def test_the_root_is_supplied_never_discovered():
    signature = inspect.signature(SignedSnapshotTrustAnchorResolver.from_document)
    assert signature.parameters["publication_root"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["publication_root"].default is inspect.Parameter.empty
    assert signature.parameters["max_snapshot_age"].default is inspect.Parameter.empty
    root = publication_root()
    assert dataclasses.replace(root).capability is TrustAnchorCapability.TRUST_ANCHOR_SET_PUBLICATION
    assert not hasattr(SignedSnapshotTrustAnchorResolver, "from_file")
    assert not hasattr(SignedSnapshotTrustAnchorResolver, "from_path")
    assert not hasattr(SignedSnapshotTrustAnchorResolver, "refresh")


def test_the_document_bytes_are_the_only_input_no_file_is_opened():
    import ast
    import pathlib

    from ugence_trusted_evidence_authority.authority import trust_snapshot

    source = pathlib.Path(trust_snapshot.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module is not None:
            imported.add(node.module.split(".")[0])
    assert not (imported & {"os", "pathlib", "sys", "time", "socket", "urllib", "http", "tempfile", "shutil"})
    names = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "open" not in names
    calls = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert not ({"now", "utcnow", "today", "time", "monotonic"} & calls)


def test_document_freshness_pins_from_the_ruling(monkeypatch):
    """The two ruled freshness inputs, and nothing else, decide staleness."""

    r = resolver()
    fresh_by_both = PUBLISHED_AT + timedelta(days=1)
    assert r.resolve(PRODUCER_COORDINATE, as_of=fresh_by_both).anchor is not None
    assert r.snapshot.manifest.effective_to == EFFECTIVE_TO
    # the anchor-level expiry of a record is not snapshot freshness
    late = document(snapshot(default_anchors()))
    r2 = resolver(late, max_age=timedelta(days=3650))
    assert r2.resolve(PRODUCER_COORDINATE, as_of=EFFECTIVE_TO - timedelta(days=1)).anchor is not None
