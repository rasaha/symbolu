"""Signed admission — the research composition root for the first signed workflow-fit study.

Owner rulings SR-0 to SR-5 (2026-09-06, recorded in
``docs/architecture/ADR_UGENCE_SIGNED_COMPARISON_RESULT_SCOPING.md`` §7) under
SCR-1. This module is the one place that composes the pilot runner, the
comparison-result attestation package and the advisor together. It is a
**research harness**, not a governed package: no capability package may hold
this composition (SR-1), and nothing here is production signing infrastructure.

    run_phase_4c_pilot(...)                         -> ReadinessComparisonResult
        (the ratified Phase 4C gate over run_pilot: F3 refuses a v1 manifest, F4
        revalidates the role; the pilot's tripwire forbids the ungated runner here)
    sign_result(result, signer)                     -> SignedComparisonResult
    verify_and_admit(signed, result, resolver, ...) -> SignedAdmissionEnvelope
        Ed25519ComparisonResultVerifier.verify      -> ComparisonResultVerificationResult
        VerifiedResultSignature(...)                -> the advisor's typed fact
        admit(..., verified=..., require_signature=True)

**Custody (SR-0).** The experiment operator controls both keys used here, and
they are two distinct seeds: the engine-signing seed lives in this module; the
trust-anchor-set publication seed lives only in
``publish_research_trust_anchor_set.py``. Both are experiment-scoped reference
material. No production key is generated or introduced; no KMS, HSM, vault,
cloud signer, Credential Broker or network signer is used (SR-2).

**Trust chain (SR-3).** The engine's anchor is resolved through a
``SignedSnapshotTrustAnchorResolver`` over the committed research snapshot
``research_trust_anchor_set_v1.json``, authenticated by the publication root
pinned below by its public key. The composition root supplies the snapshot
bytes, the root, ``max_snapshot_age`` and ``last_accepted_set_version``
explicitly; nothing is discovered from the environment or the network.

**What a signed admission establishes (SR-5).** Digest binding, signer and key
attribution, and successful verification through this pinned research trust
chain — nothing more. The party that runs the engine, requests the comparison
and signs the result is the same operator, so every result here is
**RESEARCH EVIDENCE / CRYPTOGRAPHICALLY VERIFIABLE SELF-ATTESTATION**: not
independent verification, not separation of duties, not organisational
approval, not production authority, not experimental correctness, and not
production authenticity. Every envelope and every rendering says so.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

from ugence_readiness_comparison import ENGINE_IDENTITY
from ugence_reasoning_method_advisor.api import (
    ReasoningMethodAdvisory,
    ReasoningMethodAdvisoryAdmission,
    ReasoningMethodAdvisoryRequest,
    VerifiedResultSignature,
    admit,
)
from ugence_reasoning_method_advisor.proposer_bridge import PROPOSER_DIGEST_PREFIX
from ugence_reasoning_method_governance.api import ReadinessComparisonResult
from ugence_reasoning_method_result_attestation import (
    ComparisonResultAttesterRole,
    ComparisonResultSignerPort,
    ComparisonResultVerificationOutcome,
    ComparisonResultVerificationResult,
    Ed25519ComparisonResultVerifier,
    ReferenceEd25519ComparisonResultSigner,
    SignedComparisonResult,
    TrustAnchorCapability,
    TrustAnchorRecord,
    TrustAnchorResolverPort,
    sign_comparison_result,
    verification_result_digest,
)
from ugence_trusted_evidence_authority import (
    TRUSTED_EVIDENCE_SIGNATURE_ENCODING_V1,
    TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1,
    SignedSnapshotTrustAnchorResolver,
)
from ugence_workflow_fit_pilot.api import PilotRunResult, PilotStudyManifest, run_phase_4c_pilot

__all__ = [
    "RESEARCH_EVIDENCE_CLASSIFICATION",
    "SELF_ATTESTATION_NOTE",
    "RESEARCH_ENGINE_KEY_ID",
    "RESEARCH_ENGINE_SEED",
    "RESEARCH_SET_ID",
    "RESEARCH_SET_VERSION",
    "RESEARCH_PUBLICATION_ROOT",
    "RESEARCH_SNAPSHOT_PATH",
    "MAX_SNAPSHOT_AGE",
    "LAST_ACCEPTED_SET_VERSION",
    "ENGINE_KEY_EFFECTIVE_FROM",
    "ENGINE_KEY_EFFECTIVE_TO",
    "VERIFIER_IDENTITY",
    "SignedAdmissionRefused",
    "SignedAdmissionRefusedNoResult",
    "SignedAdmissionEnvelope",
    "research_engine_signer",
    "research_engine_anchor",
    "read_committed_snapshot",
    "research_resolver",
    "sign_result",
    "verified_fact",
    "verify_and_admit",
    "run_signed_study",
    "render_envelope",
]

# --------------------------------------------------------------------------- #
# SR-5: the evidence classification, stated once and carried on everything
# --------------------------------------------------------------------------- #
RESEARCH_EVIDENCE_CLASSIFICATION = "RESEARCH_EVIDENCE / CRYPTOGRAPHICALLY_VERIFIABLE_SELF_ATTESTATION"
SELF_ATTESTATION_NOTE = (
    "The engine operator, the comparison requester and the result signer are the same "
    "party. The signature establishes digest binding, signer and key attribution, and "
    "verification through the pinned research trust chain. It establishes no independent "
    "verification, no separation of duties, no organisational approval, no production "
    "authority, no experimental correctness and no production authenticity."
)

# --------------------------------------------------------------------------- #
# SR-0 / SR-2 / SR-4: the research engine key — reference material, generation 1
# --------------------------------------------------------------------------- #
#: Versioned research key identifier (SR-4). A later study generation issues new
#: material under ``.../2``; this key is never treated as indefinitely valid.
RESEARCH_ENGINE_KEY_ID = "workflow-fit-research-engine/1"
#: Experiment-scoped reference seed. RESEARCH ONLY: it is committed, deterministic
#: and public, and therefore proves attribution to this harness and nothing else.
RESEARCH_ENGINE_SEED = bytes.fromhex(
    "d2d38473923cc32a8b05d7e3635a4c01932d09b8ef52bf199dae01748abbf907"
)
#: The engine anchor's bounded window (SR-4): twenty-five days, inside the
#: snapshot's thirty-day window and shorter than it, so a key can expire while
#: the set that carries it is still fresh.
ENGINE_KEY_EFFECTIVE_FROM = datetime(2026, 9, 1, tzinfo=timezone.utc)
ENGINE_KEY_EFFECTIVE_TO = datetime(2026, 9, 26, tzinfo=timezone.utc)

# --------------------------------------------------------------------------- #
# SR-3: the committed research snapshot and the pinned publication root
# --------------------------------------------------------------------------- #
RESEARCH_SET_ID = "workflow-fit-research-anchors"
RESEARCH_SET_VERSION = 1
RESEARCH_SNAPSHOT_PATH = Path(__file__).resolve().with_name("research_trust_anchor_set_v1.json")
MAX_SNAPSHOT_AGE = timedelta(days=30)
#: No set was accepted before generation 1; ``0`` names that explicitly, so a
#: document at version 0 or below is a rollback.
LAST_ACCEPTED_SET_VERSION = 0

#: The publication root, pinned by its **public** key. Its private seed lives only
#: in ``publish_research_trust_anchor_set.py`` and is distinct from the engine seed.
#: The snapshot itself never carries this record (TR-2), and nothing here reads it
#: from the snapshot, the environment or the network.
RESEARCH_PUBLICATION_ROOT = TrustAnchorRecord(
    authority_id="workflow-fit-research-trust-operations",
    key_id="workflow-fit-research-publication/1",
    capability=TrustAnchorCapability.TRUST_ANCHOR_SET_PUBLICATION,
    public_key="5f9e1bdf69c3eac5386039e42824f1d159b08da744af7406d1ae92bcb1f86c17",
    trust_anchor_set_id="workflow-fit-research-bootstrap",
    trust_anchor_set_version="1",
    signature_profile=TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1,
    signature_encoding=TRUSTED_EVIDENCE_SIGNATURE_ENCODING_V1,
    effective_from=datetime(2026, 9, 1, tzinfo=timezone.utc),
    effective_to=datetime(2027, 9, 1, tzinfo=timezone.utc),
)

VERIFIER_IDENTITY = "ugence-reasoning-method-result-attestation"


class SignedAdmissionRefused(Exception):
    """The verifier refused the signed result, so nothing was admitted.

    Carries the verifier's typed reason and its complete result record; the
    refusal is the study's finding, not an error to be retried."""

    def __init__(self, verification: ComparisonResultVerificationResult) -> None:
        self.verification = verification
        self.reason = verification.refusal_reason
        super().__init__(f"{verification.refusal_reason.value}: {verification.detail}")


@dataclass(frozen=True)
class SignedAdmissionEnvelope:
    """Everything one signed admission produced, under one classification.

    ``evidence_classification`` is fixed at construction and cannot be set to
    anything else: an envelope claiming stronger assurance is unconstructible."""

    pilot: Optional[PilotRunResult]
    result: ReadinessComparisonResult
    signed_result: SignedComparisonResult
    verification: ComparisonResultVerificationResult
    verified: VerifiedResultSignature
    admission: ReasoningMethodAdvisoryAdmission
    evidence_classification: str = RESEARCH_EVIDENCE_CLASSIFICATION
    self_attestation_note: str = SELF_ATTESTATION_NOTE

    def __post_init__(self) -> None:
        if self.evidence_classification != RESEARCH_EVIDENCE_CLASSIFICATION:
            raise ValueError("a signed admission is research evidence; no other classification exists")
        if self.self_attestation_note != SELF_ATTESTATION_NOTE:
            raise ValueError("the self-attestation note is fixed")
        if self.verification.outcome is not ComparisonResultVerificationOutcome.VERIFIED:
            raise ValueError("an envelope exists only for a VERIFIED signature")
        if self.admission.result_signature_receipt_digest != self.verified.verification_receipt_digest:
            raise ValueError("the admission must cite the verification record in this envelope")
        if self.verified.result_digest != self.result.result_digest != self.signed_result.result_digest:
            raise ValueError("the envelope's result, signed result and verified fact must agree")


# --------------------------------------------------------------------------- #
# the signer, the anchor, the resolver
# --------------------------------------------------------------------------- #
def research_engine_signer() -> ReferenceEd25519ComparisonResultSigner:
    """The reference signer for the comparison engine identity (SR-2). Refused by
    the attestation package under ``production_mode=True``, which this harness
    never sets when signing."""

    return ReferenceEd25519ComparisonResultSigner(
        RESEARCH_ENGINE_SEED,
        signer_identity=ENGINE_IDENTITY,
        signer_key_id=RESEARCH_ENGINE_KEY_ID,
        signer_role=ComparisonResultAttesterRole.COMPARISON_ENGINE,
    )


def research_engine_anchor() -> TrustAnchorRecord:
    """The engine's **public** half as the anchor the snapshot carries (SR-4)."""

    return research_engine_signer().trust_anchor(
        trust_anchor_set_id=RESEARCH_SET_ID,
        trust_anchor_set_version=str(RESEARCH_SET_VERSION),
        effective_from=ENGINE_KEY_EFFECTIVE_FROM,
        effective_to=ENGINE_KEY_EFFECTIVE_TO,
    )


def read_committed_snapshot(path: Path = RESEARCH_SNAPSHOT_PATH) -> Optional[bytes]:
    """The complete committed document, or ``None`` when it cannot be read — which
    the resolver turns into a typed load failure rather than a crash."""

    try:
        return Path(path).read_bytes()
    except OSError:
        return None


def research_resolver(
    document: Optional[bytes],
    *,
    publication_root: TrustAnchorRecord = RESEARCH_PUBLICATION_ROOT,
    max_snapshot_age: timedelta = MAX_SNAPSHOT_AGE,
    last_accepted_set_version: Optional[int] = LAST_ACCEPTED_SET_VERSION,
) -> SignedSnapshotTrustAnchorResolver:
    """The resolver over one explicitly supplied document under one explicitly
    pinned root (SR-3). Every argument is the composition root's; none is
    discovered."""

    return SignedSnapshotTrustAnchorResolver.from_document(
        document,
        publication_root=publication_root,
        max_snapshot_age=max_snapshot_age,
        last_accepted_set_version=last_accepted_set_version,
    )


# --------------------------------------------------------------------------- #
# the three steps
# --------------------------------------------------------------------------- #
def sign_result(
    result: ReadinessComparisonResult,
    *,
    signer: ComparisonResultSignerPort,
    signed_at: datetime,
) -> SignedComparisonResult:
    """Step 2: wrap and sign the engine result behind the signer port. Never in
    production mode: the reference signer is all this study is authorised to use."""

    return sign_comparison_result(result, signer=signer, signed_at=signed_at, production_mode=False)


def verified_fact(verification: ComparisonResultVerificationResult) -> VerifiedResultSignature:
    """Step 4: the advisor's typed fact, built from the verifier's own record.

    The receipt digest is the attestation package's ``verification_result_digest``
    with the repository's one digest-prefix translation applied — the same
    ``sha256:`` prefix the advisor's bridge adds back for the proposer. No second
    digest algorithm and no other representation exist."""

    if verification.outcome is not ComparisonResultVerificationOutcome.VERIFIED:
        raise SignedAdmissionRefused(verification)
    receipt = verification_result_digest(verification)
    if not receipt.startswith(PROPOSER_DIGEST_PREFIX):
        raise ValueError("the verification record digest is not in the repository's sha256: spelling")
    return VerifiedResultSignature(
        result_digest=verification.result_digest,
        signer_identity=verification.signer_identity,
        signer_key_id=verification.signer_key_id,
        verification_receipt_digest=receipt[len(PROPOSER_DIGEST_PREFIX):],
        verifier_identity=VERIFIER_IDENTITY,
        verified_at=verification.evaluated_at,
    )


def verify_and_admit(
    signed_result: SignedComparisonResult,
    result: ReadinessComparisonResult,
    *,
    advisory: ReasoningMethodAdvisory,
    request: ReasoningMethodAdvisoryRequest,
    resolver: TrustAnchorResolverPort,
    as_of: datetime,
    admitted_at: Optional[datetime] = None,
    expected_engine_identity: str = ENGINE_IDENTITY,
    pilot: Optional[PilotRunResult] = None,
) -> SignedAdmissionEnvelope:
    """Steps 3 to 5: verify against the caller's own result through the pinned
    trust chain, build the typed fact, and admit with the signature required.

    ``production_mode=True`` on the verifier: the reference **resolver** is
    refused, and the signed-snapshot resolver must declare it can serve. A
    refused verification raises :class:`SignedAdmissionRefused`; an advisor
    refusal propagates as the advisor's own error."""

    verifier = Ed25519ComparisonResultVerifier(trust_anchor_resolver=resolver, production_mode=True)
    verification = verifier.verify(
        signed_result=signed_result,
        expected_role=ComparisonResultAttesterRole.COMPARISON_ENGINE,
        expected_engine_identity=expected_engine_identity,
        expected_result=result,
        as_of=as_of,
    )
    fact = verified_fact(verification)
    admission = admit(
        advisory, request, result,
        admitted_at=admitted_at if admitted_at is not None else as_of,
        verified=fact, require_signature=True,
    )
    return SignedAdmissionEnvelope(
        pilot=pilot, result=result, signed_result=signed_result,
        verification=verification, verified=fact, admission=admission,
    )


def run_signed_study(
    manifest: PilotStudyManifest,
    *,
    advisory: ReasoningMethodAdvisory,
    request: ReasoningMethodAdvisoryRequest,
    now: Callable[[], datetime],
    signer: Optional[ComparisonResultSignerPort] = None,
    snapshot_document: Optional[bytes] = None,
    publication_root: TrustAnchorRecord = RESEARCH_PUBLICATION_ROOT,
    max_snapshot_age: timedelta = MAX_SNAPSHOT_AGE,
    last_accepted_set_version: Optional[int] = LAST_ACCEPTED_SET_VERSION,
    **run_pilot_kwargs,
) -> SignedAdmissionEnvelope:
    """The whole path, steps 1 to 5. ``now`` is the caller's clock, as for the
    pilot; the snapshot bytes default to the committed document, read here and
    nowhere else.

    Step 1 goes through ``run_phase_4c_pilot``, the ratified Phase 4C entry point
    (F3, F4; revision 20), which delegates to ``run_pilot`` after refusing a v1
    manifest and revalidating the run role. The pilot's own tripwire
    (``test_the_phase_4c_study_never_calls_the_ungated_runner``) forbids this
    harness from calling the ungated runner, so a signed study needs a v2
    manifest with a committed role."""

    pilot = run_phase_4c_pilot(manifest, advisory=advisory, now=now, **run_pilot_kwargs)
    if pilot.result is None:
        raise SignedAdmissionRefusedNoResult("the pilot produced no comparison result; there is nothing to sign")
    signed = sign_result(pilot.result, signer=signer if signer is not None else research_engine_signer(), signed_at=now())
    resolver = research_resolver(
        snapshot_document if snapshot_document is not None else read_committed_snapshot(),
        publication_root=publication_root,
        max_snapshot_age=max_snapshot_age,
        last_accepted_set_version=last_accepted_set_version,
    )
    return verify_and_admit(
        signed, pilot.result, advisory=advisory, request=request, resolver=resolver, as_of=now(), pilot=pilot,
    )


class SignedAdmissionRefusedNoResult(Exception):
    """The pilot run ended without a comparison result (a calibration run, or an
    incomplete one), so signing never started."""


def render_envelope(envelope: SignedAdmissionEnvelope) -> str:
    """Deterministic text. The classification heads and closes it; every block
    that could read as assurance carries the note."""

    e = envelope
    lines = [
        f"# Signed workflow-fit admission — {e.evidence_classification}",
        "",
        f"- classification: {e.evidence_classification}",
        f"- note: {e.self_attestation_note}",
        f"- engine: {e.result.engine_identity} {e.result.engine_version}",
        f"- result_digest: {e.result.result_digest}",
        f"- signer: {e.signed_result.signer_identity} key={e.signed_result.signer_key_id} role={e.signed_result.signer_role.value}",
        f"- signature verified: {e.verification.outcome.value} at {e.verification.evaluated_at.isoformat()} "
        f"(establishes {e.verification.establishes}; factual_correctness_established={e.verification.factual_correctness_established})",
        f"- anchor revision: {e.verification.anchor_record_digest}",
        f"- verification record: {PROPOSER_DIGEST_PREFIX}{e.verified.verification_receipt_digest}",
        f"- admission: {e.admission.schema_version} digest={e.admission.admission_digest} "
        f"qualifying={[m.method_id for m in e.admission.qualifying]} "
        f"evidence_status={e.admission.evidence_status} usage_scope={e.admission.usage_scope}",
        f"- study conclusion: {e.evidence_classification}; the admission is research evidence about the rule set, not a product claim",
        "",
        f"{e.evidence_classification}",
    ]
    return "\n".join(lines) + "\n"
