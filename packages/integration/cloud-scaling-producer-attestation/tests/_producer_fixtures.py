"""Shared builders for the Phase 5B-0A producer-authenticity suite.

Nothing here stubs the artifact under test. The chain is genuine end to end:

* the recommendation comes from the controller's **real** Phase-3 pipeline;
* the projection comes from the **real** Phase 4C ``project_recommendation``;
* the ``SubjectRiskDecision`` comes from the **real** ``RiskEvaluationSeam.reference(...)``;
* the Phase 5A ``CapacityAuthorizationCandidate`` is built by Phase 5A's **own** public
  builder, from Phase 5A's **own** frozen fixture module — imported, never re-implemented,
  so the forgery-laundering proof runs against the real Phase 5A artifact;
* the v2 producer attestation carries a **real Ed25519 signature** over the real canonical
  signing payload, produced through this package's one minting route.

Two structurally different keys exist here, and the difference is the whole proof:
:data:`TRUSTED_PRODUCER_SEED` is registered as a trust anchor, and
:data:`UNTRUSTED_PRODUCER_SEED` is not. The forgery arm varies **only** the key.

:class:`ForbiddenCollaborator` and :class:`CountingSigner` are sentinels, not substitutes:
reaching the former fails the test, and the latter proves that verification calls no signer.
"""

from __future__ import annotations

import importlib.util
import os
import pathlib
import sys
from datetime import datetime, timedelta, timezone
from typing import Any


from ugence_trusted_evidence_authority import (
    TrustedEvidenceSigningKey,
    encode_public_key,
)

from ugence_cloud_scaling_producer_attestation import (
    PRODUCER_ATTESTATION_CAPABILITY,
    Ed25519ProducerSignatureVerifier,
    ProducerAttestationV2,
    ProducerAttestationVerifier,
    ReferenceEd25519ProducerAttestationSigner,
    StaticTrustAnchorDirectory,
    TrustAnchorRecord,
    canonical_digest,
    mint_producer_attestation,
)

# --------------------------------------------------------------------------------------- #
# Phase 5A's own fixture module, imported rather than re-implemented.
# --------------------------------------------------------------------------------------- #

def repo_root() -> pathlib.Path:
    """Locate the monorepo root without counting directory levels.

    Deliberately self-contained rather than imported from the package-root ``conftest``:
    ``tests/`` is on ``sys.path`` ahead of the package root, so ``import conftest`` here
    resolves to *this* directory's ``conftest``, which imports this module — a circular
    import. Twelve duplicated lines are cheaper than that, and than a shared helper module
    that would itself need to be importable before the path is set up.

    Counting ``parents[n]`` breaks the moment this tree is copied elsewhere — which the
    guard sweep does on every mutation, into a disposable directory outside the repository.
    ``UGENCE_REPO_ROOT`` is how the sweep tells a copy where the real checkout is;
    otherwise the search walks upward for the marker directories.
    """

    injected = os.environ.get("UGENCE_REPO_ROOT")
    if injected:
        return pathlib.Path(injected).resolve()
    here = pathlib.Path(__file__).resolve().parent
    for candidate in (here, *here.parents):
        if (candidate / "packages" / "risk_authority").is_dir() and (
            candidate / "packages" / "trusted-evidence-authority"
        ).is_dir():
            return candidate
    raise RuntimeError(
        f"could not locate the monorepo root from {here}; set UGENCE_REPO_ROOT"
    )


REPO = repo_root()
_PHASE_5A_TESTS = (
    REPO / "packages" / "integration" / "cloud-scaling-authorization-contracts" / "tests"
)


def _load_phase5a_fixtures():
    """Load Phase 5A's ``tests/conftest.py`` under a distinct module name.

    Imported under ``phase5a_fixtures`` so it cannot collide with this suite's own
    ``conftest``. Everything the laundering proof needs — the genuine recommendation,
    projection, decision, target scope, policy binding and v1 attestation builders — comes
    from there, so the proof runs against Phase 5A's real frozen fixture and not a copy of
    it that could drift.
    """

    if str(_PHASE_5A_TESTS) not in sys.path:
        sys.path.insert(0, str(_PHASE_5A_TESTS))
    spec = importlib.util.spec_from_file_location(
        "phase5a_fixtures", _PHASE_5A_TESTS / "conftest.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["phase5a_fixtures"] = module
    spec.loader.exec_module(module)
    return module


P5A = _load_phase5a_fixtures()

# --------------------------------------------------------------------------------------- #
# Deterministic, non-secret test key material. No production key exists in this repository.
# --------------------------------------------------------------------------------------- #

#: The seed whose public half IS registered as a trust anchor.
TRUSTED_PRODUCER_SEED = bytes(range(96, 128))
#: A structurally identical seed whose public half is NOT registered. The forgery arm.
UNTRUSTED_PRODUCER_SEED = bytes(range(128, 160))
#: A third key registered under the RECEIPT_ISSUANCE capability, for the capability probe.
WRONG_CAPABILITY_SEED = bytes(range(160, 192))

PRODUCER_ID = "ugence.cloud-scaling-controller"
ISSUER_ID = "ugence.cloud-scaling-producer-authority"
FOREIGN_ISSUER_ID = "attacker.rogue-producer-authority"
PRODUCER_KEY_ID = "producer-attestation-v2-key-1"
UNTRUSTED_KEY_ID = "producer-attestation-v2-key-forged"
ANCHOR_SET_ID = "cloud-scaling-producer-anchors"
ANCHOR_SET_VERSION = "1"

#: The injected verification instant. Inside every anchor window the fixtures build.
AS_OF = datetime(2026, 1, 1, 0, 5, 0, tzinfo=timezone.utc)
#: Anchor window bounds, half-open ``[effective_from, effective_to)``.
WINDOW_FROM = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
WINDOW_TO = datetime(2026, 1, 2, 0, 0, 0, tzinfo=timezone.utc)


def signing_key(seed: bytes = TRUSTED_PRODUCER_SEED) -> TrustedEvidenceSigningKey:
    return TrustedEvidenceSigningKey(seed)


def build_signer(
    *,
    seed: bytes = TRUSTED_PRODUCER_SEED,
    producer_id: str = PRODUCER_ID,
    issuer: str = ISSUER_ID,
    producer_key_id: str = PRODUCER_KEY_ID,
) -> ReferenceEd25519ProducerAttestationSigner:
    """The reference signer. Marked ``is_reference_signer=True`` and refused in production."""

    return ReferenceEd25519ProducerAttestationSigner(
        producer_id=producer_id,
        issuer=issuer,
        producer_key_id=producer_key_id,
        signing_key=signing_key(seed),
    )


def build_anchor(
    *,
    seed: bytes = TRUSTED_PRODUCER_SEED,
    issuer: str = ISSUER_ID,
    key_id: str = PRODUCER_KEY_ID,
    capability=PRODUCER_ATTESTATION_CAPABILITY,
    effective_from: "datetime | None" = WINDOW_FROM,
    effective_to: "datetime | None" = WINDOW_TO,
    disabled: bool = False,
    revocation=None,
) -> TrustAnchorRecord:
    """A trust anchor carrying only the PUBLIC half of a key. No seed reaches a record."""

    return TrustAnchorRecord(
        authority_id=issuer,
        key_id=key_id,
        capability=capability,
        public_key=encode_public_key(
            TrustedEvidenceSigningKey(seed).verification_key.public_key_bytes
        ),
        trust_anchor_set_id=ANCHOR_SET_ID,
        trust_anchor_set_version=ANCHOR_SET_VERSION,
        effective_from=effective_from,
        effective_to=effective_to,
        disabled=disabled,
        revocation=revocation,
    )


def build_directory(*anchors: TrustAnchorRecord) -> StaticTrustAnchorDirectory:
    """The reference directory holding exactly the anchors it is given, and no others."""

    records = anchors or (build_anchor(),)
    return StaticTrustAnchorDirectory(
        records,
        trust_anchor_set_id=ANCHOR_SET_ID,
        trust_anchor_set_version=ANCHOR_SET_VERSION,
    )


def build_verifier(
    *, directory=None, signature_verifier=None, production_mode: bool = False
) -> ProducerAttestationVerifier:
    """The authoritative verifier. Both collaborators are required and have no defaults."""

    return ProducerAttestationVerifier(
        trust_anchor_resolver=directory if directory is not None else build_directory(),
        signature_verifier=(
            signature_verifier
            if signature_verifier is not None
            else Ed25519ProducerSignatureVerifier()
        ),
        production_mode=production_mode,
    )


_DEFAULT_CANDIDATE = None


def build_candidate(**overrides: Any):
    """A genuine Phase 5A candidate, from Phase 5A's own public builder and fixtures.

    The default (no-override) candidate is built once and shared. It is a frozen dataclass
    over frozen dataclasses, so sharing it is safe, and building the real Phase-3 →
    Phase 4C → Risk Authority → Phase 5A chain costs about a second each time. Any
    override builds a fresh chain, so no test that varies an input ever sees the cache.
    """

    global _DEFAULT_CANDIDATE
    if overrides:
        return P5A.build_candidate(**overrides)
    if _DEFAULT_CANDIDATE is None:
        _DEFAULT_CANDIDATE = P5A.build_candidate()
    return _DEFAULT_CANDIDATE


def build_attestation(
    candidate,
    *,
    seed: bytes = TRUSTED_PRODUCER_SEED,
    producer_id: str = PRODUCER_ID,
    issuer: str = ISSUER_ID,
    producer_key_id: str = PRODUCER_KEY_ID,
    tenant_id: "str | None" = None,
    subject_id: "str | None" = None,
    recommendation_id: "str | None" = None,
    recommendation_digest: "str | None" = None,
    issued_at: datetime = P5A.REC_TIME,
    signer=None,
) -> ProducerAttestationV2:
    """Mint a genuine v2 attestation bound to ``candidate``, through the one minting route."""

    return mint_producer_attestation(
        signer=signer
        if signer is not None
        else build_signer(
            seed=seed,
            producer_id=producer_id,
            issuer=issuer,
            producer_key_id=producer_key_id,
        ),
        tenant_id=tenant_id if tenant_id is not None else candidate.tenant_id,
        subject_id=subject_id if subject_id is not None else candidate.subject_id,
        recommendation_id=(
            recommendation_id
            if recommendation_id is not None
            else candidate.recommendation_id
        ),
        recommendation_digest=(
            recommendation_digest
            if recommendation_digest is not None
            else candidate.recommendation_digest
        ),
        issued_at=issued_at,
    )


def replace_attestation(attestation: ProducerAttestationV2, **overrides: Any):
    """Rebuild an attestation with fields overridden, re-deriving its payload digest.

    Used to construct *structurally valid* attestations that carry a lie — the shape a real
    attacker produces. It re-derives ``signing_payload_digest`` deliberately: an attacker
    who changes a field also recomputes the digest, and a proof that only catches attackers
    who forget to would prove nothing.
    """

    fields = {
        "producer_id": attestation.producer_id,
        "issuer": attestation.issuer,
        "producer_key_id": attestation.producer_key_id,
        "tenant_id": attestation.tenant_id,
        "subject_id": attestation.subject_id,
        "subject_type": attestation.subject_type,
        "recommendation_id": attestation.recommendation_id,
        "recommendation_digest": attestation.recommendation_digest,
        "issued_at": attestation.issued_at,
        "signing_purpose": attestation.signing_purpose,
        "signature_algorithm": attestation.signature_algorithm,
        "signature_profile": attestation.signature_profile,
        "signature_encoding": attestation.signature_encoding,
        "signature": attestation.signature,
        "schema_version": attestation.schema_version,
    }
    fields.update(overrides)
    body = {k: v for k, v in fields.items() if k not in ("signature",)}
    from ugence_cloud_scaling_producer_attestation import (
        producer_attestation_signing_payload,
    )

    payload = producer_attestation_signing_payload(
        producer_id=body["producer_id"],
        issuer=body["issuer"],
        producer_key_id=body["producer_key_id"],
        tenant_id=body["tenant_id"],
        subject_id=body["subject_id"],
        subject_type=body["subject_type"],
        recommendation_id=body["recommendation_id"],
        recommendation_digest=body["recommendation_digest"],
        issued_at=body["issued_at"],
        signing_purpose=body["signing_purpose"],
        signature_algorithm=body["signature_algorithm"],
        signature_profile=body["signature_profile"],
        signature_encoding=body["signature_encoding"],
    )
    return ProducerAttestationV2(
        **fields, signing_payload_digest=canonical_digest(payload)
    )


class ForbiddenCollaborator:
    """Fails the test if it is reached at all. A sentinel, not a mock."""

    def __init__(self, name: str = "collaborator") -> None:
        self.name = name
        self.calls: list = []

    def __getattr__(self, item: str):
        def _fail(*args: Any, **kwargs: Any):  # pragma: no cover - reaching this IS failure
            raise AssertionError(
                f"the Phase 5B-0A boundary reached {self.name}.{item} — no envelope "
                "issuer, ActionGate, credential broker or executor may be invoked while "
                "verifying producer authenticity"
            )

        return _fail


class CountingSigner:
    """A signer that counts calls and refuses to sign. Verification must never call one."""

    is_reference_signer = True

    def __init__(self) -> None:
        self.calls = 0

    @property
    def producer_id(self) -> str:
        return PRODUCER_ID

    @property
    def issuer(self) -> str:
        return ISSUER_ID

    @property
    def producer_key_id(self) -> str:
        return PRODUCER_KEY_ID

    @property
    def signature_profile(self) -> str:
        from ugence_cloud_scaling_producer_attestation import (
            PRODUCER_ATTESTATION_SIGNATURE_PROFILE,
        )

        return PRODUCER_ATTESTATION_SIGNATURE_PROFILE

    def sign_producer_attestation(self, signing_input) -> str:  # pragma: no cover
        self.calls += 1
        raise AssertionError(
            "a signer was called during verification; verification signs nothing"
        )


class CountingSignatureVerifier:
    """Wraps the real verifier and counts how many signature checks actually happened."""

    is_production_authoritative = True

    def __init__(self, inner=None) -> None:
        self.inner = inner if inner is not None else Ed25519ProducerSignatureVerifier()
        self.calls = 0

    def verify_producer_signature(self, *, anchor, signed_input, signature) -> bool:
        self.calls += 1
        return self.inner.verify_producer_signature(
            anchor=anchor, signed_input=signed_input, signature=signature
        )
