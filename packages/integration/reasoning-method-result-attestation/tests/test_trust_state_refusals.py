"""TW-1 to TW-3 — trust-state refusals stay distinguishable, and a resolver that
cannot serve is admitted at composition and refuses every verification.

Every case here runs against the real ``SignedSnapshotTrustAnchorResolver`` from
the Trusted Evidence Authority, so the mapping is proved end to end rather than
against a double. That resolver remains a **production-shaped candidate**: not
independently reviewed, not externally cryptographically audited, not
production-ready. Nothing here wires a deployment, and no snapshot file is read.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import ugence_reasoning_method_result_attestation as ra
from ugence_trusted_evidence_authority import (
    TrustAnchorResolution,
    TrustedEvidenceRefusalReason,
)

from _fixtures import ENGINE, ENGINE_ID, engine_signer, result

# The TEA conformance harness already builds signed snapshots; reusing it keeps
# this suite honest about what a real snapshot is, rather than re-deriving one.
# The repo root comes from conftest's own resolution (``UGENCE_REPO_ROOT`` when
# injected), so this works from a copied tree — the mutation sweep runs one.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from conftest import REPO as _REPO  # noqa: E402

if _REPO is None:  # pragma: no cover - the harness is required, never optional
    raise RuntimeError("the repository root is required to load the TEA resolver harness")
_TEA_TESTS = _REPO / "packages" / "trusted-evidence-authority" / "tests" / "authority"
if str(_TEA_TESTS) not in sys.path:
    sys.path.insert(0, str(_TEA_TESTS))
import resolver_conformance as rc  # noqa: E402

R = ra.ComparisonResultRefusalReason
SIGNED_AT = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)
FRESH = rc.FRESH_AS_OF
STALE = rc.PUBLISHED_AT + rc.MAX_AGE
BEFORE_WINDOW = rc.PUBLISHED_AT - timedelta(seconds=1)


def _signed():
    return ra.sign_comparison_result(result(), signer=engine_signer(), signed_at=SIGNED_AT)


def _snapshot_document():
    """A signed snapshot carrying the engine's anchor at its comparison-result coordinate."""

    anchor = engine_signer().trust_anchor(
        trust_anchor_set_id=rc.SET_ID,
        trust_anchor_set_version="1",
        effective_from=rc.EFFECTIVE_FROM - timedelta(days=30),
        effective_to=rc.EFFECTIVE_TO + timedelta(days=30),
    )
    return rc.document(rc.snapshot(rc.ordered(anchor)))


def _resolver(document=None, **kw):
    """A signed-snapshot resolver over the engine's anchor unless given a document."""

    return rc.resolver(_snapshot_document() if document is None else document, **kw)


def _verify(resolver, *, as_of=FRESH, production_mode=True):
    verifier = ra.Ed25519ComparisonResultVerifier(
        trust_anchor_resolver=resolver, production_mode=production_mode
    )
    return verifier.verify(
        signed_result=_signed(),
        expected_role=ENGINE,
        expected_engine_identity=ENGINE_ID,
        expected_result=result(),
        as_of=as_of,
    )


# --------------------------------------------------------------------------- #
# TW-1: four distinguishable outcomes, end to end
# --------------------------------------------------------------------------- #
def test_a_fresh_snapshot_still_verifies_under_production_mode():
    result = _verify(_resolver())
    assert result.outcome is ra.ComparisonResultVerificationOutcome.VERIFIED
    assert result.refusal_reason is None
    assert result.factual_correctness_established is False


def test_stale_unavailable_unknown_and_resolver_fault_are_four_distinct_reasons():
    fresh = _resolver()
    reasons = {
        "stale": _verify(fresh, as_of=STALE).refusal_reason,
        "set-unavailable": _verify(fresh, as_of=BEFORE_WINDOW).refusal_reason,
        "unknown": _verify(_resolver(rc.document(rc.snapshot(()))), as_of=FRESH).refusal_reason,
        "resolver-fault": _verify(_Raises(), as_of=FRESH).refusal_reason,
    }
    assert reasons["stale"] is R.ANCHOR_SET_STALE
    assert reasons["set-unavailable"] is R.ANCHOR_SET_UNAVAILABLE
    assert reasons["unknown"] is R.ANCHOR_UNKNOWN
    assert reasons["resolver-fault"] is R.ANCHOR_UNAVAILABLE
    assert len(set(reasons.values())) == 4, reasons


def test_the_set_reason_map_is_one_to_one_and_omits_instant_required():
    assert ra.TRUST_ANCHOR_SET_REASONS == {
        TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_TRUST_ANCHOR_SET_UNAVAILABLE:
            R.ANCHOR_SET_UNAVAILABLE,
        TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_TRUST_ANCHOR_SET_STALE:
            R.ANCHOR_SET_STALE,
    }
    values = list(ra.TRUST_ANCHOR_SET_REASONS.values())
    assert len(set(values)) == len(values)
    assert (TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_TRUST_ANCHOR_SET_INSTANT_REQUIRED
            not in ra.TRUST_ANCHOR_SET_REASONS)


def test_no_cached_answer_follows_a_stale_one():
    resolver = _resolver()
    assert _verify(resolver, as_of=FRESH).outcome is ra.ComparisonResultVerificationOutcome.VERIFIED
    assert _verify(resolver, as_of=STALE).refusal_reason is R.ANCHOR_SET_STALE
    assert _verify(resolver, as_of=STALE).refusal_reason is R.ANCHOR_SET_STALE
    # and fresh again afterwards: the stale answer was not remembered either way
    assert _verify(resolver, as_of=FRESH).outcome is ra.ComparisonResultVerificationOutcome.VERIFIED


# --------------------------------------------------------------------------- #
# TW-2: instant-required is a caller contract error, never a member
# --------------------------------------------------------------------------- #
def test_a_bad_instant_raises_at_the_caller_seam_rather_than_minting_a_reason():
    verifier = ra.Ed25519ComparisonResultVerifier(trust_anchor_resolver=_resolver(), production_mode=True)
    for bad in (None, datetime(2026, 9, 6, 12, 0), "2026-09-06T12:00:00Z", 1_757_160_000):
        with pytest.raises(ra.ComparisonResultAttestationContractError):
            verifier.verify(signed_result=_signed(), expected_role=ENGINE,
                            expected_engine_identity=ENGINE_ID, expected_result=result(), as_of=bad)
    assert not any(m.name.endswith("INSTANT_REQUIRED") for m in R)


def test_a_resolver_that_answers_instant_required_anyway_is_a_resolver_fault():
    """This package always hands over a validated aware instant, so a resolver
    returning that reason is non-conforming rather than reporting trust state."""

    class _AnswersInstantRequired:
        is_production_authoritative = True

        def resolve(self, coordinate, *, as_of=None):
            assert as_of is not None and as_of.tzinfo is not None  # it was handed one
            return TrustAnchorResolution.refused(
                coordinate,
                TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_TRUST_ANCHOR_SET_INSTANT_REQUIRED,
            )

    result = _verify(_AnswersInstantRequired())
    assert result.refusal_reason is R.ANCHOR_UNAVAILABLE
    assert "INSTANT_REQUIRED" in result.detail


# --------------------------------------------------------------------------- #
# TW-3: a failed load is admitted at composition and refuses every verification
# --------------------------------------------------------------------------- #
def test_a_resolver_whose_snapshot_failed_to_load_is_admitted_and_refuses_everything():
    broken = rc.resolver(None)  # the composition root could not read the file
    assert broken.is_production_authoritative is False
    assert broken.load_failure is not None
    verifier = ra.Ed25519ComparisonResultVerifier(trust_anchor_resolver=broken, production_mode=True)
    assert verifier.production_mode is True
    result = _verify(broken)
    assert result.refusal_reason is R.ANCHOR_SET_UNAVAILABLE
    assert result.anchor_record_digest is None
    assert "cannot serve production trust state" in result.detail


def test_the_gate_refuses_before_the_resolver_is_consulted():
    """Admitting a non-serving resolver never yields an anchor, because it is
    never asked. A resolver that would answer generously proves the ordering."""

    class _GenerousButNotServing:
        is_production_authoritative = False

        def __init__(self):
            self.calls = []

        def resolve(self, coordinate, *, as_of=None):  # pragma: no cover - must not run
            self.calls.append(coordinate)
            raise AssertionError("a non-serving resolver was consulted")

    generous = _GenerousButNotServing()
    assert _verify(generous).refusal_reason is R.ANCHOR_SET_UNAVAILABLE
    assert generous.calls == []


def test_a_resolver_declaring_no_posture_is_still_refused_at_composition():
    class _Silent:
        def resolve(self, coordinate, *, as_of=None):  # pragma: no cover - never reached
            raise AssertionError

    class _Truthy:
        is_production_authoritative = 1  # not an exact bool

        def resolve(self, coordinate, *, as_of=None):  # pragma: no cover - never reached
            raise AssertionError

    for resolver in (_Silent(), _Truthy()):
        with pytest.raises(ra.ComparisonResultAttestationConfigurationError, match="exact bool"):
            ra.Ed25519ComparisonResultVerifier(trust_anchor_resolver=resolver, production_mode=True)
    assert ra.declares_production_posture(_Silent()) is False
    assert ra.declares_production_posture(_Truthy()) is False
    assert ra.declares_production_posture(rc.resolver(None)) is True
    assert ra.resolver_serves_production(rc.resolver(None)) is False
    assert ra.resolver_serves_production(_resolver()) is True


def test_the_reference_directory_is_still_refused_in_production():
    static = ra.StaticTrustAnchorDirectory(
        [engine_signer().trust_anchor(trust_anchor_set_id="s", trust_anchor_set_version="1")],
        trust_anchor_set_id="s", trust_anchor_set_version="1",
    )
    with pytest.raises(ra.ComparisonResultAttestationConfigurationError, match="REFERENCE"):
        ra.Ed25519ComparisonResultVerifier(trust_anchor_resolver=static, production_mode=True)

    class _Claiming(ra.StaticTrustAnchorDirectory):
        is_production_authoritative = True

    claiming = _Claiming([], trust_anchor_set_id="s", trust_anchor_set_version="1")
    with pytest.raises(ra.ComparisonResultAttestationConfigurationError, match="REFERENCE"):
        ra.Ed25519ComparisonResultVerifier(trust_anchor_resolver=claiming, production_mode=True)


def test_deny_all_keeps_its_ratified_reason_and_is_exempt_from_the_gate():
    """E-8's deny-all declares no posture and is admitted by exact type, so the
    TW-3 gate leaves it alone and its refusal stays ANCHOR_UNKNOWN."""

    deny = ra.DenyAllTrustAnchorDirectory()
    assert ra.declares_production_posture(deny) is False
    assert _verify(deny).refusal_reason is R.ANCHOR_UNKNOWN


def test_the_reference_grade_path_is_unchanged_by_the_gate():
    """Outside production the gate does not apply, so nothing about the
    reference posture moved."""

    broken = rc.resolver(None)
    assert _verify(broken, production_mode=False).refusal_reason is R.ANCHOR_SET_UNAVAILABLE
    static_ok = ra.Ed25519ComparisonResultVerifier(
        trust_anchor_resolver=ra.StaticTrustAnchorDirectory(
            [engine_signer().trust_anchor(trust_anchor_set_id="s", trust_anchor_set_version="1")],
            trust_anchor_set_id="s", trust_anchor_set_version="1"),
        production_mode=False,
    )
    assert static_ok.production_mode is False


class _Raises:
    is_production_authoritative = True

    def resolve(self, coordinate, *, as_of=None):
        raise RuntimeError("directory down")


# --------------------------------------------------------------------------- #
# the vocabulary itself
# --------------------------------------------------------------------------- #
def test_the_vocabulary_is_appended_in_the_verifier_order_and_closed():
    names = [m.name for m in R]
    assert names[:11] == [
        "ATTESTATION_ABSENT", "UNSUPPORTED_EXACT_TYPE", "UNSUPPORTED_SCHEMA_VERSION",
        "UNSUPPORTED_SIGNING_DOMAIN", "UNSUPPORTED_ALGORITHM", "UNSUPPORTED_PROFILE",
        "UNSUPPORTED_ENCODING", "ROLE_MISMATCH", "WRONG_ENGINE_IDENTITY", "RESULT_MISMATCH",
        "ANCHOR_UNKNOWN",
    ]
    assert "ANCHOR_SET_UNAVAILABLE" in names and "ANCHOR_SET_STALE" in names
    assert names[-1] == "VERIFICATION_UNAVAILABLE"
    assert len(names) == 26 and len(set(names)) == 26
    for member in R:
        words = set(member.name.split("_"))
        assert not (words & {"OK", "PASS", "VERIFIED", "ADMITTED", "SUCCESS", "GRANTED"}), member


def test_no_verified_result_is_reachable_through_a_trust_state_reason():
    for reason in (R.ANCHOR_SET_STALE, R.ANCHOR_SET_UNAVAILABLE):
        outcome = ra.ComparisonResultVerificationResult(
            outcome=ra.ComparisonResultVerificationOutcome.REFUSED,
            refusal_reason=reason,
            signer_role=ENGINE,
            signer_identity=ENGINE_ID,
            signer_key_id="engine-key-1",
            engine_identity=ENGINE_ID,
            result_digest=result().result_digest,
            signing_payload_digest=None,
            anchor_coordinate_digest=ra.anchor_coordinate_digest(
                ra.comparison_result_signer_coordinate(role=ENGINE, signer_identity=ENGINE_ID,
                                              signer_key_id="engine-key-1")),
            anchor_record_digest=None,
            evaluated_at=FRESH,
        )
        assert outcome.factual_correctness_established is False
        assert outcome.outcome is ra.ComparisonResultVerificationOutcome.REFUSED
