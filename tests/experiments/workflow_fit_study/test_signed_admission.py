"""The signed workflow-fit admission composition root (SR-0 to SR-5, SCR-1).

Runs the fixture pilot once through the real boundary process, signs the engine's
result with the research reference signer, verifies it through the committed
research snapshot under the pinned publication root, and admits it with the
signature required. Every refusal the rulings name is then proved against that
one genuine run. Skipped where the attestation stack is not installed.

Every result here is RESEARCH EVIDENCE / CRYPTOGRAPHICALLY VERIFIABLE
SELF-ATTESTATION: the operator, requester and signer are the same party.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from datetime import timedelta
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PILOT_TESTS = _REPO_ROOT / "packages" / "capabilities" / "workflow-fit-pilot" / "tests"
for _p in (_PILOT_TESTS, _PILOT_TESTS / "contracts",
           _REPO_ROOT / "packages" / "capabilities" / "reasoning-method-governance" / "tests",
           _REPO_ROOT / "packages" / "capabilities" / "reasoning-method-advisor" / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

ra = pytest.importorskip("ugence_reasoning_method_result_attestation")
tea = pytest.importorskip("ugence_trusted_evidence_authority")
pytest.importorskip("ugence_workflow_fit_pilot")

import pilot_fixtures as pf  # noqa: E402
import test_run_role_and_calibration as slice2  # noqa: E402
from experiments.workflow_fit_study import publish_research_trust_anchor_set as pub  # noqa: E402
from experiments.workflow_fit_study import signed_admission as sa  # noqa: E402
from ugence_reasoning_method_advisor.api import (  # noqa: E402
    ADVISORY_REQUEST_SCHEMA_VERSION,
    AdvisorError,
    AdvisorErrorCode,
    ReasoningMethodAdvisoryRequest,
    admit,
    to_proposer_input,
    validate_admission,
)
from ugence_reasoning_method_governance.api import USAGE_SCOPE_RESEARCH_ONLY  # noqa: E402

R = ra.ComparisonResultRefusalReason
CAP = tea.TrustAnchorCapability
NOW = pf.NOW  # 2026-09-02T12:00Z: inside the engine key's window and the snapshot's


def _pilot_kwargs():
    return dict(catalog=pf.catalog(), rule_set=pf.rule_set(), cases=pf.cases(), executor=pf.FakeExecutor(pf.DEFAULT_CALLS),
                scorer=pf.KeywordScorer(), identity=pf.IDENTITY, provider_factory="stub_provider:make_provider",
                boundary_env=pf.boundary_env())


@pytest.fixture(scope="module")
def study():
    """One genuine run through the whole path: gated pilot, sign, verify, admit.

    A v2 CONFIRMATORY manifest: the Phase 4C gate refuses the v1 fixture, and the
    pilot's tripwire forbids the ungated runner from this harness."""

    m = slice2._confirmatory_manifest()
    adv = pf.advisory(m.plan.task_class)
    req = ReasoningMethodAdvisoryRequest(ADVISORY_REQUEST_SCHEMA_VERSION, "pilot.advice", pf.profile(), m.plan.task_class,
                                         pf.catalog(), pf.rule_set(), "requester:pilot")
    env = sa.run_signed_study(m, advisory=adv, request=req, now=pf.clock(), **_pilot_kwargs())
    return m, adv, req, env


def _verify(env, *, signed=None, result=None, document=None, as_of=NOW, **resolver_kw):
    _, adv, req, e = env
    resolver = sa.research_resolver(document if document is not None else sa.read_committed_snapshot(), **resolver_kw)
    return sa.verify_and_admit(signed if signed is not None else e.signed_result, result if result is not None else e.result,
                               advisory=adv, request=req, resolver=resolver, as_of=as_of)


def _refused(reason, thunk):
    with pytest.raises(sa.SignedAdmissionRefused) as info:
        thunk()
    assert info.value.reason is reason, (info.value.reason, info.value.verification.detail)
    return info.value


# --------------------------------------------------------------------------- #
# 1. valid signed admission
# --------------------------------------------------------------------------- #
def test_a_valid_signed_admission_binds_the_result_the_signature_and_the_receipt(study):
    m, adv, req, env = study
    assert env.pilot is not None and env.pilot.result is env.result
    assert m.is_v2 and m.run_role.name == "CONFIRMATORY"
    assert env.verification.outcome is ra.ComparisonResultVerificationOutcome.VERIFIED
    assert env.verification.signer_identity == env.result.engine_identity == "ugence-readiness-comparison"
    assert env.verification.signer_key_id == sa.RESEARCH_ENGINE_KEY_ID == "workflow-fit-research-engine/1"
    assert env.verification.anchor_record_digest == ra.anchor_record_digest(sa.research_engine_anchor())
    assert env.verified.result_digest == env.result.result_digest == env.signed_result.result_digest
    receipt = ra.verification_result_digest(env.verification)
    assert receipt == "sha256:" + env.verified.verification_receipt_digest
    assert env.admission.result_signature_receipt_digest == env.verified.verification_receipt_digest
    assert env.admission.comparison_result_digest == env.result.result_digest
    assert [q.method_id for q in env.admission.qualifying] == ["iterative_refinement", "map_reduce", "tree_of_thought"]
    validate_admission(env.admission, adv, env.result, verified=env.verified, require_signature=True)
    assert to_proposer_input(env.admission)["result_signature_receipt_digest"] == receipt


# --------------------------------------------------------------------------- #
# 2. result mutation after signing
# --------------------------------------------------------------------------- #
def test_a_result_mutated_after_signing_is_refused(study):
    _, _, _, env = study
    moved = dataclasses.replace(env.result, produced_at=env.result.produced_at + timedelta(seconds=1))
    _refused(R.RESULT_MISMATCH, lambda: _verify(study, result=moved))
    forged = dataclasses.replace(env.result, request_id="cmp.forged", result_digest="")
    _refused(R.RESULT_MISMATCH, lambda: _verify(study, result=forged))
    tampered = dataclasses.replace(env.signed_result, result=forged)
    _refused(R.SIGNATURE_INVALID, lambda: _verify(study, signed=tampered, result=forged))


# --------------------------------------------------------------------------- #
# 3. wrong engine signer — right identity and key id, different key material
# --------------------------------------------------------------------------- #
def test_a_different_key_under_the_engines_identity_and_key_id_is_refused(study):
    _, _, _, env = study
    impostor = ra.ReferenceEd25519ComparisonResultSigner(
        b"\x07" * 32, signer_identity=env.result.engine_identity, signer_key_id=sa.RESEARCH_ENGINE_KEY_ID,
        signer_role=ra.ComparisonResultAttesterRole.COMPARISON_ENGINE)
    signed = sa.sign_result(env.result, signer=impostor, signed_at=NOW)
    _refused(R.SIGNATURE_INVALID, lambda: _verify(study, signed=signed))


# --------------------------------------------------------------------------- #
# 4. wrong key id
# --------------------------------------------------------------------------- #
def test_the_genuine_key_under_an_unpublished_key_id_is_refused(study):
    _, _, _, env = study
    generation_2 = ra.ReferenceEd25519ComparisonResultSigner(
        sa.RESEARCH_ENGINE_SEED, signer_identity=env.result.engine_identity, signer_key_id="workflow-fit-research-engine/2",
        signer_role=ra.ComparisonResultAttesterRole.COMPARISON_ENGINE)
    signed = sa.sign_result(env.result, signer=generation_2, signed_at=NOW)
    refusal = _refused(R.ANCHOR_UNKNOWN, lambda: _verify(study, signed=signed))
    assert refusal.verification.anchor_record_digest is None


# --------------------------------------------------------------------------- #
# 5. untrusted engine key — a snapshot that does not carry it
# --------------------------------------------------------------------------- #
def test_a_snapshot_without_the_engine_anchor_refuses_the_genuine_signature(study):
    other = ra.ReferenceEd25519ComparisonResultSigner(
        b"\x08" * 32, signer_identity="another-engine", signer_key_id="k", signer_role=ra.ComparisonResultAttesterRole.COMPARISON_ENGINE)
    other_anchor = other.trust_anchor(trust_anchor_set_id=sa.RESEARCH_SET_ID, trust_anchor_set_version="1",
                                      effective_from=sa.ENGINE_KEY_EFFECTIVE_FROM, effective_to=sa.ENGINE_KEY_EFFECTIVE_TO)
    document = pub.render_document(anchors=(other_anchor,))
    _refused(R.ANCHOR_UNKNOWN, lambda: _verify(study, document=document))


# --------------------------------------------------------------------------- #
# 6. invalid snapshot publication signature
# --------------------------------------------------------------------------- #
def test_a_snapshot_whose_publication_signature_does_not_verify_is_refused(study):
    doc = json.loads(sa.read_committed_snapshot())
    sig = doc["signature"]
    doc["signature"] = ("0" if sig[0] != "0" else "1") + sig[1:]
    forged = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()
    refusal = _refused(R.ANCHOR_SET_UNAVAILABLE, lambda: _verify(study, document=forged))
    assert "cannot serve" in refusal.verification.detail
    # A document signed by the engine seed instead of the publication root is equally refused.
    engine_signed = pub.render_document(seed=sa.RESEARCH_ENGINE_SEED)
    _refused(R.ANCHOR_SET_UNAVAILABLE, lambda: _verify(study, document=engine_signed))
    # And so is one that cannot be read at all.
    _refused(R.ANCHOR_SET_UNAVAILABLE, lambda: _verify(study, document=b""))
    assert sa.read_committed_snapshot(Path("/nonexistent/snapshot.json")) is None


# --------------------------------------------------------------------------- #
# 7. stale snapshot
# --------------------------------------------------------------------------- #
def test_a_snapshot_older_than_thirty_days_is_stale(study):
    assert sa.MAX_SNAPSHOT_AGE == timedelta(days=30)
    _refused(R.ANCHOR_SET_STALE, lambda: _verify(study, as_of=pub.PUBLISHED_AT + sa.MAX_SNAPSHOT_AGE))
    _refused(R.ANCHOR_SET_STALE, lambda: _verify(study, as_of=pub.PUBLISHED_AT + timedelta(days=10), max_snapshot_age=timedelta(days=9)))


# --------------------------------------------------------------------------- #
# 8. trust-set rollback
# --------------------------------------------------------------------------- #
def test_a_document_at_or_below_the_last_accepted_version_is_a_rollback(study):
    assert sa.LAST_ACCEPTED_SET_VERSION == 0
    _refused(R.ANCHOR_SET_UNAVAILABLE, lambda: _verify(study, last_accepted_set_version=1))
    _refused(R.ANCHOR_SET_UNAVAILABLE, lambda: _verify(study, last_accepted_set_version=7))
    assert _verify(study, last_accepted_set_version=0).verification.outcome.value == "VERIFIED"


# --------------------------------------------------------------------------- #
# 9. engine key outside its effective window
# --------------------------------------------------------------------------- #
def test_the_engine_key_expires_before_the_set_it_lives_in(study):
    assert sa.ENGINE_KEY_EFFECTIVE_TO - sa.ENGINE_KEY_EFFECTIVE_FROM <= timedelta(days=30)
    assert sa.ENGINE_KEY_EFFECTIVE_TO < pub.SET_EFFECTIVE_TO
    _refused(R.ANCHOR_EXPIRED, lambda: _verify(study, as_of=sa.ENGINE_KEY_EFFECTIVE_TO))
    # The set is still fresh at that instant: the refusal is the key's, not the set's.
    assert _verify(study, as_of=sa.ENGINE_KEY_EFFECTIVE_TO - timedelta(seconds=1)).verification.outcome.value == "VERIFIED"


# --------------------------------------------------------------------------- #
# 10. signer / result engine_identity mismatch
# --------------------------------------------------------------------------- #
def test_a_signer_for_another_identity_cannot_sign_the_engines_result(study):
    _, _, _, env = study
    stranger = ra.ReferenceEd25519ComparisonResultSigner(
        sa.RESEARCH_ENGINE_SEED, signer_identity="someone-else", signer_key_id=sa.RESEARCH_ENGINE_KEY_ID,
        signer_role=ra.ComparisonResultAttesterRole.COMPARISON_ENGINE)
    with pytest.raises(ra.ComparisonResultAttestationSigningBoundaryError, match="engine_identity"):
        sa.sign_result(env.result, signer=stranger, signed_at=NOW)
    # And a caller expecting another engine refuses the genuine signed result.
    _, adv, req, e = study
    resolver = sa.research_resolver(sa.read_committed_snapshot())
    _refused(R.WRONG_ENGINE_IDENTITY, lambda: sa.verify_and_admit(
        e.signed_result, e.result, advisory=adv, request=req, resolver=resolver, as_of=NOW, expected_engine_identity="someone-else"))


# --------------------------------------------------------------------------- #
# 11. missing verified signature with require_signature=True
# --------------------------------------------------------------------------- #
def test_an_unsigned_result_admits_nothing_under_the_signed_posture(study):
    _, adv, req, env = study
    with pytest.raises(AdvisorError) as info:
        admit(adv, req, env.result, admitted_at=NOW, require_signature=True)
    assert info.value.code is AdvisorErrorCode.COMPARISON_RESULT_UNSIGNED
    refused = ra.Ed25519ComparisonResultVerifier(trust_anchor_resolver=ra.DenyAllTrustAnchorDirectory(), production_mode=True).verify(
        signed_result=env.signed_result, expected_role=ra.ComparisonResultAttesterRole.COMPARISON_ENGINE,
        expected_engine_identity=env.result.engine_identity, expected_result=env.result, as_of=NOW)
    with pytest.raises(sa.SignedAdmissionRefused):
        sa.verified_fact(refused)


# --------------------------------------------------------------------------- #
# 12. the engine-signing key and the publication-root key are distinct
# --------------------------------------------------------------------------- #
def test_the_engine_key_and_the_publication_root_are_two_keys_under_two_capabilities(study):
    engine = sa.research_engine_anchor()
    root = sa.RESEARCH_PUBLICATION_ROOT
    assert sa.RESEARCH_ENGINE_SEED != pub.RESEARCH_PUBLICATION_SEED
    assert engine.public_key != root.public_key
    assert engine.capability is CAP.COMPARISON_RESULT_ATTESTATION and root.capability is CAP.TRUST_ANCHOR_SET_PUBLICATION
    assert (engine.authority_id, engine.key_id) != (root.authority_id, root.key_id)
    # The pinned root is the publication seed's public half, pinned by literal, not derived at runtime.
    derived = tea.encode_public_key(pub.publication_signing_key().verification_key.public_key_bytes)
    assert derived == root.public_key
    # The snapshot never carries the root, and the root's key cannot sign a result.
    doc = json.loads(sa.read_committed_snapshot())
    assert [a["capability"] for a in doc["anchors"]] == ["COMPARISON_RESULT_ATTESTATION"]
    root_as_engine = ra.ReferenceEd25519ComparisonResultSigner(
        pub.RESEARCH_PUBLICATION_SEED, signer_identity="ugence-readiness-comparison", signer_key_id=sa.RESEARCH_ENGINE_KEY_ID,
        signer_role=ra.ComparisonResultAttesterRole.COMPARISON_ENGINE)
    _, _, _, env = study
    _refused(R.SIGNATURE_INVALID, lambda: _verify(study, signed=sa.sign_result(env.result, signer=root_as_engine, signed_at=NOW)))


# --------------------------------------------------------------------------- #
# 13. research-only evidence classification survives a successful admission
# --------------------------------------------------------------------------- #
def test_a_successful_signed_admission_stays_research_evidence(study):
    _, _, _, env = study
    assert env.evidence_classification == sa.RESEARCH_EVIDENCE_CLASSIFICATION
    assert "RESEARCH_EVIDENCE" in env.evidence_classification and "SELF_ATTESTATION" in env.evidence_classification
    assert env.verification.factual_correctness_established is False
    assert env.verification.establishes == "PROVENANCE_AND_INTEGRITY_ONLY"
    assert all(a.usage_scope == USAGE_SCOPE_RESEARCH_ONLY for a in env.result.assessments)
    with pytest.raises(ValueError):
        dataclasses.replace(env, evidence_classification="PRODUCTION_VERIFIED")
    with pytest.raises(ValueError):
        dataclasses.replace(env, self_attestation_note="independently verified")
    text = sa.render_envelope(env)
    assert text.startswith("# Signed workflow-fit admission — RESEARCH_EVIDENCE")
    assert text.rstrip().endswith(sa.RESEARCH_EVIDENCE_CLASSIFICATION)
    assert "same party" in text and "not a product claim" in text and "factual_correctness_established=False" in text
    for word in ("independently verified", "production-ready", "approved"):
        assert word not in text.lower()


# --------------------------------------------------------------------------- #
# the committed snapshot is the deterministic rendering, and the harness reads no clock
# --------------------------------------------------------------------------- #
def test_the_committed_snapshot_equals_a_fresh_deterministic_rendering():
    assert sa.RESEARCH_SNAPSHOT_PATH.read_bytes() == pub.render_document()
    assert pub.main(["--check"]) == 0
    snap = tea.parse_trust_anchor_set_document(sa.read_committed_snapshot())
    assert snap.manifest.trust_anchor_set_version == 1 and snap.manifest.anchor_count == 1
    assert snap.manifest.publisher_coordinate == sa.RESEARCH_PUBLICATION_ROOT.coordinate


def test_the_composition_root_reads_no_clock_and_no_environment():
    import ast

    for path in (sa.__file__, pub.__file__):
        for node in ast.walk(ast.parse(Path(path).read_text(encoding="utf-8"))):
            # A bare ``now()`` is the caller-supplied clock, as for the pilot; a clock
            # *read* is an attribute call on a datetime or time object.
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in ("now", "utcnow", "today", "time", "getenv", "urlopen"), (path, node.func.attr)
            if isinstance(node, ast.Attribute):
                assert node.attr != "environ", path
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                assert not {n.split(".")[0] for n in names} & {"os", "socket", "urllib", "http", "requests", "secrets", "random"}, (path, names)


def test_a_run_without_a_comparison_result_never_starts_signing():
    m = slice2._calibration_manifest()
    adv = None
    with pytest.raises(sa.SignedAdmissionRefusedNoResult):
        sa.run_signed_study(m, advisory=adv, request=None, now=pf.clock(), **_pilot_kwargs())


def test_a_historical_v1_manifest_is_refused_at_the_gate_before_anything_is_signed():
    """F3 through the composition root: the v1 fixture is mechanism validation and is
    not eligible for a Phase 4C run, so no boundary starts and no signature is made."""
    from ugence_workflow_fit_pilot.api import PilotError, PilotErrorCode

    m = pf.manifest()
    adv = pf.advisory(m.plan.task_class)
    with pytest.raises(PilotError) as info:
        sa.run_signed_study(m, advisory=adv, request=None, now=pf.clock(), **_pilot_kwargs())
    assert info.value.code is PilotErrorCode.RUN_ROLE_INVALID

