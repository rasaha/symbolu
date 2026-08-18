#!/usr/bin/env python3
"""Reproducible proof that the Trusted Evidence Authority contracts install and
operate from a built wheel, with **no** cross-package dependency and no monorepo
source on the path.

Builds ``ugence-trusted-evidence-authority`` into a local find-links directory,
installs it into a fresh virtualenv with no system site packages and no monorepo
path (``--no-index`` — the wheel is local and declares zero dependencies), then
proves inside that env:

  * ``ugence_trusted_evidence_authority`` imports from site-packages;
  * the curated public API resolves and ships ``py.typed``;
  * the installed surface equals the committed ``public_api.json`` exactly —
    every symbol, kind, enum member **and order**, dataclass field **and
    order**, and pinned constant value;
  * representative contracts construct, canonicalize and digest, and the pinned
    canonical bytes and digest reproduce byte-for-byte — including the four
    TEV-1 vectors, unchanged;
  * the TEV-2 verification authority, signer and independent re-verifier work
    end to end inside the installed wheel: an evidence submission is verified,
    a receipt is signed, and the envelope re-verifies against a resolved trust
    anchor, with pinned signature bytes and pinned digests;
  * the RFC 8032 §7.1 published Ed25519 vectors reproduce exactly, proving the
    installed signer implements the standard algorithm;
  * the principal TEV-2 refusal classes fire from the installed wheel —
    revoked, expired and not-yet-valid keys, an unconfigured trust anchor, an
    invalid signature, a swapped payload, and a replayed coordinate;
  * the structural invariants fire (blank/padded identifier, malformed digest,
    naive datetime, reversed interval, duplicate custody link, applicability
    XOR, co-required binding pair, closed lifecycle relation);
  * no caller can reach a verified state (frozen assignment, enum lookup,
    subclass, property override, duck-typed lookalike, cross-scope replay);
  * the independent ``adversarial_probes.py`` harness passes against the
    installed wheel, importing only the curated API;
  * **no** Ugence package, capability, product, console, platform tool or
    third-party package is importable.

Run:  python packages/trusted-evidence-authority/verify_trusted_evidence_authority_distribution.py
Exit code 0 on success; non-zero on the first failed step.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import venv
import zipfile
from pathlib import Path

PKG = Path(__file__).resolve().parent
REPO = PKG.parents[1]  # packages/trusted-evidence-authority -> packages -> repo root
NAMESPACE = "ugence_trusted_evidence_authority"
DISTRIBUTION = "ugence-trusted-evidence-authority"

_CHECK = r'''
import dataclasses, enum, hashlib, importlib.util, json, pathlib, sys
from datetime import datetime, timedelta, timezone

import ugence_trusted_evidence_authority as u
assert u.__version__ == "0.2.0", u.__version__
assert "site-packages" in u.__file__, u.__file__
assert not any("/symbolu" in p for p in sys.path), sys.path
assert (pathlib.Path(u.__file__).resolve().parent / "py.typed").is_file(), "py.typed not installed"
assert not hasattr(u, "CONTRACT_VERSION"), "no CONTRACT_VERSION is minted"

from ugence_trusted_evidence_authority.api import (
    EVIDENCE_IDENTITY_DIGEST_DOMAIN, EVIDENCE_LIFECYCLE_TRANSITIONS,
    EVIDENCE_TRUST_STAGE_ORDER,
    EVIDENCE_VERIFICATION_RECEIPT_PAYLOAD_DIGEST_DOMAIN,
    RECEIPT_REPORTABLE_TRUST_STAGES,
    TRUSTED_EVIDENCE_CANONICALIZATION_VERSION,
    TRUSTED_EVIDENCE_REFUSAL_REASONS,
    TEV1_TRUSTED_EVIDENCE_REFUSAL_REASONS,
    TEV2_TRUSTED_EVIDENCE_REFUSAL_REASONS,
    SIGNED_EVIDENCE_SUBMISSION_SCHEMA_V1,
    SIGNED_RECEIPT_ENVELOPE_SCHEMA_V1,
    TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1,
    TRUSTED_EVIDENCE_SIGNATURE_ENCODING_V1,
    TRUSTED_EVIDENCE_SIGNED_EVIDENCE_INPUT_DOMAIN,
    TRUSTED_EVIDENCE_SIGNED_RECEIPT_INPUT_DOMAIN,
    DenyAllTrustAnchorDirectory, Ed25519EvidenceAuthenticityProtocol,
    Ed25519ReceiptSigner, EvidenceAdmissionOutcome,
    EvidenceVerificationAuthority, KeyRevocation, ReceiptIssuer,
    ReceiptVerificationOutcome, SignedEvidenceSubmission,
    SignedEvidenceVerificationReceipt, SignedReceiptVerifier,
    StaticTrustAnchorDirectory, TrustAnchorCapability, TrustAnchorCoordinate,
    TrustAnchorRecord, TrustedEvidenceSigningKey,
    TrustedEvidenceVerificationKey, audit_record_for_determination,
    encode_public_key, encode_signature, signed_evidence_input_bytes,
    signed_receipt_input_bytes,
    ApplicabilityCoordinate,
    ApplicabilityDeclaration, CanonicalEvidenceIdentity,
    DeclaredVerificationOutcome, EvidenceClaimBinding, EvidenceLifecycleState,
    EvidenceObservation, EvidenceProvenanceChain, EvidenceSchemaRef,
    EvidenceScopeBinding, EvidenceStructuralStatus, EvidenceTrustStage,
    EvidenceVerificationReceiptPayload,
    EvidenceVerificationRequest, TrustedEvidenceCanonicalizationError,
    TrustedEvidenceContractError, TrustedEvidenceLifecycleError,
    TrustedEvidenceRefusalReason, canonical_bytes, canonical_digest,
    is_valid_lifecycle_transition, require_valid_lifecycle_transition)
from ugence_trusted_evidence_authority import api

UTC = timezone.utc
R = TrustedEvidenceRefusalReason
C = hashlib.sha256(b"evidence-content").hexdigest()
X = hashlib.sha256(b"assessment-context").hexdigest()
B = hashlib.sha256(b"system-binding").hexdigest()
OTHER = hashlib.sha256(b"something-else").hexdigest()
T_OBS = datetime(2026, 3, 1, 10, 0, 0, 250000, tzinfo=UTC)
T_COL = datetime(2026, 3, 1, 12, 0, 0, 500000, tzinfo=UTC)
T_TO_OBS = datetime(2026, 3, 1, 11, 0, 0, tzinfo=UTC)
V0 = datetime(2026, 3, 1, tzinfo=UTC)
V1 = datetime(2026, 9, 1, tzinfo=UTC)

def obs(**kw):
    base = dict(producer_id="prod-a", collected_at=T_COL, observed_from=T_OBS,
                observed_to=T_TO_OBS, issuer_id="issuer-b"); base.update(kw)
    return EvidenceObservation(**base)

def sc(**kw):
    base = dict(tenant_id="tenant-1", assessment_context_ref="ctx-1",
                assessment_context_digest=X, subject_ref="subject-1",
                assessment_purpose_ref="purpose-readiness", usage_scope_ref="scope-general",
                assessed_system_applicability=ApplicabilityDeclaration.APPLICABLE,
                assessed_system_binding_ref="bind-1", assessed_system_binding_digest=B)
    base.update(kw); return EvidenceScopeBinding(**base)

def ident(**kw):
    base = dict(evidence_id="ev-1", evidence_type="CONTROL_TEST_RESULT",
                schema=EvidenceSchemaRef(schema_id="ugence.evidence.control-test", schema_version="1"),
                content_digest=C, observation=obs(), scope=sc(),
                claim=EvidenceClaimBinding.applicable(
                    claim_ref="claim-1", metric_ref="metric-resolution-rate",
                    unit="ratio", measurement_semantics_ref="semantics-1"),
                provenance=EvidenceProvenanceChain(chain_ref="chain-1",
                                                   custody_refs=("custody-1", "custody-2")),
                lifecycle_state=EvidenceLifecycleState.SUBMITTED,
                geography=ApplicabilityCoordinate.applicable("US"),
                domain=ApplicabilityCoordinate.not_applicable(),
                intended_outcome=ApplicabilityCoordinate.applicable("ticket-resolution"),
                valid_from=V0, valid_to=V1)
    base.update(kw); return CanonicalEvidenceIdentity(**base)

def req(**kw):
    base = dict(evidence=ident(), expected_content_digest=C, expected_tenant_id="tenant-1",
                expected_assessment_context_ref="ctx-1", expected_assessment_context_digest=X,
                expected_subject_ref="subject-1", expected_assessment_purpose_ref="purpose-readiness",
                expected_usage_scope_ref="scope-general",
                expected_assessed_system_binding_ref="bind-1",
                expected_assessed_system_binding_digest=B, as_of=datetime(2026, 6, 1, tzinfo=UTC),
                requested_trust_stages=(EvidenceTrustStage.CRYPTOGRAPHICALLY_AUTHENTIC,))
    base.update(kw); return EvidenceVerificationRequest(**base)

def refuses(fn, *types):
    types = types or (TrustedEvidenceContractError,)
    try:
        fn()
    except types:
        return
    raise SystemExit("expected a refusal: " + getattr(fn, "__doc__", "") or repr(fn))

# ---- pinned canonical bytes and digest, recomputed with hashlib alone -------
LITERAL = (b'{"body":{"schema_id":"ugence.evidence.control-test","schema_version":"1"},'
           b'"canonicalization":"ugence.trusted-evidence-authority/canonicalization/v1",'
           b'"domain":"ugence.trusted-evidence-authority/evidence-identity/v1",'
           b'"type":"EvidenceSchemaRef"}')
s = EvidenceSchemaRef(schema_id="ugence.evidence.control-test", schema_version="1")
assert canonical_bytes(s) == LITERAL, canonical_bytes(s)
assert canonical_digest(s) == hashlib.sha256(LITERAL).hexdigest()
assert ident().canonical_digest() == "26ee959e4c87cc0660895a269c2805af1065ba4f634c9c73070848de7bf51029", ident().canonical_digest()
assert hashlib.sha256(ident().canonical_bytes()).hexdigest() == ident().canonical_digest()

framed = json.loads(canonical_bytes(ident()).decode("utf-8"))
assert framed["canonicalization"] == TRUSTED_EVIDENCE_CANONICALIZATION_VERSION
assert framed["domain"] == EVIDENCE_IDENTITY_DIGEST_DOMAIN
assert framed["type"] == "CanonicalEvidenceIdentity"

# ---- determinism ------------------------------------------------------------
ist = T_OBS.astimezone(timezone(timedelta(hours=5, minutes=30)))
assert ident(observation=obs(observed_from=ist)).canonical_digest() == ident().canonical_digest()
assert b"10:00:00.250000Z" in ident().canonical_bytes()
assert ident(observation=obs(observed_from=T_OBS.replace(microsecond=250001))).canonical_digest() \
    != ident().canonical_digest()
assert json.loads(canonical_bytes(ident(valid_to=None)))["body"]["valid_to"] is None

# ---- structural invariants fire --------------------------------------------
for bad in ("", "  ", " ev-1", "ev-1 ", None, 1, True):
    refuses(lambda b=bad: ident(evidence_id=b))
for bad in ("", "nope", C.upper(), C[:-1], "sha256:" + C):
    refuses(lambda b=bad: ident(content_digest=b))
refuses(lambda: ident(valid_from=datetime(2026, 3, 1)))
refuses(lambda: ident(valid_from=V1, valid_to=V0))
refuses(lambda: ident(valid_from=V0, valid_to=V0))
refuses(lambda: obs(observed_from=T_TO_OBS, observed_to=T_OBS))
refuses(lambda: obs(collected_at=T_OBS - timedelta(seconds=1)))
refuses(lambda: obs(producer_id="p", issuer_id="p"))
refuses(lambda: EvidenceProvenanceChain(chain_ref="c", custody_refs=("a", "a")))
refuses(lambda: EvidenceProvenanceChain(chain_ref="c", custody_refs="abc"))
refuses(lambda: ApplicabilityCoordinate(declaration=ApplicabilityDeclaration.APPLICABLE, value=""))
refuses(lambda: ApplicabilityCoordinate(declaration=ApplicabilityDeclaration.NOT_APPLICABLE, value="US"))
refuses(lambda: sc(assessed_system_binding_digest=""))
refuses(lambda: sc(assessed_system_applicability=ApplicabilityDeclaration.NOT_APPLICABLE))
refuses(lambda: req(as_of=datetime(2026, 6, 1)))
refuses(lambda: req(requested_trust_stages=()))
refuses(lambda: req(requested_trust_stages=(EvidenceTrustStage.POLICY_SUFFICIENT,)))
refuses(lambda: canonical_bytes("not a contract"), TrustedEvidenceCanonicalizationError)

# ---- half-open boundaries ---------------------------------------------------
tick = timedelta(microseconds=1)
assert ident().is_valid_at(V0) is True
assert ident().temporal_refusal_at(V0 - tick) is R.TRUSTED_EVIDENCE_NOT_YET_VALID
assert ident().is_valid_at(V1) is False
assert ident().temporal_refusal_at(V1) is R.TRUSTED_EVIDENCE_STALE

# ---- lifecycle relation is closed ------------------------------------------
S = EvidenceLifecycleState
admissible = {(S.PRODUCED, S.SUBMITTED), (S.PRODUCED, S.EXPIRED), (S.PRODUCED, S.REVOKED),
              (S.SUBMITTED, S.RETAINED), (S.SUBMITTED, S.EXPIRED), (S.SUBMITTED, S.REVOKED),
              (S.RETAINED, S.EXPIRED), (S.RETAINED, S.REVOKED)}
for a in S:
    for b in S:
        assert is_valid_lifecycle_transition(a, b) is ((a, b) in admissible), (a, b)
refuses(lambda: require_valid_lifecycle_transition(S.REVOKED, S.RETAINED),
        TrustedEvidenceLifecycleError)
assert {s.value for s in S} == {"PRODUCED", "SUBMITTED", "RETAINED", "EXPIRED", "REVOKED"}

# ---- anti-forgery -----------------------------------------------------------
assert list(EvidenceStructuralStatus) == [EvidenceStructuralStatus.STRUCTURAL_UNVERIFIED]
assert ident().authenticity_verified is False
assert len(ident().unestablished_trust_stages) == 5
refuses(lambda: ident(verified=True), TypeError)
refuses(lambda: setattr(ident(), "authenticity_verified", True), dataclasses.FrozenInstanceError)
for attempt in ("VERIFIED", "AUTHENTIC", "TRUSTED"):
    refuses(lambda a=attempt: EvidenceStructuralStatus(a), ValueError)

class Forged(CanonicalEvidenceIdentity):
    @property
    def authenticity_verified(self): return True
base = ident()
forged = Forged(**{f.name: getattr(base, f.name) for f in dataclasses.fields(base)})
refuses(lambda: req(evidence=forged))
assert canonical_digest(forged) != base.canonical_digest()

class Lookalike: pass
fake = Lookalike()
for f in dataclasses.fields(base): setattr(fake, f.name, getattr(base, f.name))
fake.authenticity_verified = True
refuses(lambda: req(evidence=fake))

assert req().structural_scope_mismatches() == ()
assert req().unperformed_verification_reason is R.TRUSTED_EVIDENCE_VERIFICATION_NOT_PERFORMED
for field, code in (("tenant_id", R.TRUSTED_EVIDENCE_TENANT_MISMATCH),
                    ("subject_ref", R.TRUSTED_EVIDENCE_SUBJECT_MISMATCH),
                    ("assessment_purpose_ref", R.TRUSTED_EVIDENCE_PURPOSE_SCOPE_MISMATCH),
                    ("usage_scope_ref", R.TRUSTED_EVIDENCE_PURPOSE_SCOPE_MISMATCH),
                    ("assessed_system_binding_ref", R.TRUSTED_EVIDENCE_SYSTEM_BINDING_MISMATCH)):
    replayed = ident(scope=sc(**{field: "replayed-value"}))
    assert replayed.canonical_digest() != base.canonical_digest(), field
    assert code in req(evidence=replayed).structural_scope_mismatches(), field

assert set(R) == set(TRUSTED_EVIDENCE_REFUSAL_REASONS)
assert len(list(R)) == 40
assert R.TRUSTED_EVIDENCE_INDETERMINATE in TRUSTED_EVIDENCE_REFUSAL_REASONS
# TEV-1's nineteen keep their exact ordinal positions; TEV-2 appended 21.
assert list(R)[18] is R.TRUSTED_EVIDENCE_INDETERMINATE
assert list(R)[19] is R.TRUSTED_EVIDENCE_ENVELOPE_MALFORMED
assert list(R)[-1] is R.TRUSTED_EVIDENCE_RECEIPT_EXPIRED
for name in api.__all__:
    low = name.lower().replace("_", "")
    # No *later* milestone leaked in. TEV-2's own verifier, signer, trust
    # anchors and signed receipt are expected and asserted present below.
    for banned in ("benchmark", "readiness", "roi", "forecast", "attribution",
                   "valuation", "actiongate", "deployment", "credential",
                   "kms", "hsm", "certificate", "riskauthority",
                   "cloudscaling", "governedvalue", "policyapplicability"):
        assert banned not in low, name
    # §13.3 — an unsigned artifact is not a receipt, and is not named as one.
    if name.endswith("Receipt") and not name.isupper() and "_" not in name:
        assert name.startswith("Signed"), name
assert "EvidenceVerificationReceiptPayload" in api.__all__
assert "EvidenceVerificationReceipt" not in api.__all__
for required in ("EvidenceVerificationAuthority", "SignedReceiptVerifier",
                 "SignedEvidenceVerificationReceipt", "TrustAnchorRecord",
                 "ReceiptIssuer", "Ed25519ReceiptSigner"):
    assert required in api.__all__, required

# ---- A-02: claim/metric/units co-requirement --------------------------------
for kw in (dict(claim_ref="c", unit="u", measurement_semantics_ref="s"),
           dict(metric_ref="m", unit="u", measurement_semantics_ref="s")):
    EvidenceClaimBinding(applicability=ApplicabilityDeclaration.APPLICABLE, **kw)
for kw in (dict(unit="u", measurement_semantics_ref="s"), dict(claim_ref="c", unit="u"),
           dict(claim_ref="c", measurement_semantics_ref="s"), dict(claim_ref="c"), {}):
    refuses(lambda k=kw: EvidenceClaimBinding(
        applicability=ApplicabilityDeclaration.APPLICABLE, **k))
for f in ("claim_ref", "metric_ref", "unit", "measurement_semantics_ref"):
    refuses(lambda f=f: EvidenceClaimBinding(
        applicability=ApplicabilityDeclaration.NOT_APPLICABLE, **{f: "x"}))
refuses(lambda: EvidenceClaimBinding(), TypeError)
_base_claim = ident().canonical_digest()
for variant in (EvidenceClaimBinding.applicable(claim_ref="other", unit="ratio",
                                                measurement_semantics_ref="semantics-1"),
                EvidenceClaimBinding.applicable(claim_ref="claim-1", unit="percent",
                                                measurement_semantics_ref="semantics-1"),
                EvidenceClaimBinding.applicable(claim_ref="claim-1", unit="ratio",
                                                measurement_semantics_ref="other"),
                EvidenceClaimBinding.not_applicable()):
    assert ident(claim=variant).canonical_digest() != _base_claim

# ---- A-03: NFC refused at construction, and again at canonicalization -------
import unicodedata
NFD = "caf\u0065\u0301-id"
NFC = "caf\u00e9-id"
assert unicodedata.normalize("NFC", NFD) == NFC != NFD, "fixture is already NFC"
refuses(lambda: EvidenceSchemaRef(schema_id=NFD, schema_version="1"))
refuses(lambda: ident(evidence_id=NFD))
refuses(lambda: EvidenceProvenanceChain(chain_ref="c", custody_refs=("ok", NFD)))
refuses(lambda: ApplicabilityCoordinate.applicable(NFD))
refuses(lambda: EvidenceClaimBinding.applicable(claim_ref=NFD, unit="u",
                                                measurement_semantics_ref="s"))
assert EvidenceSchemaRef(schema_id=NFC, schema_version="1").schema_id == NFC
_bypass = EvidenceSchemaRef(schema_id="ok", schema_version="1")
object.__setattr__(_bypass, "schema_id", NFD)
refuses(lambda: canonical_bytes(_bypass), TrustedEvidenceCanonicalizationError)

# ---- A-01: the structural receipt payload -----------------------------------
RT = datetime(2026, 6, 1, 8, 0, 0, 750000, tzinfo=UTC)
def rcpt(**kw):
    base = dict(
        receipt_id="receipt-1",
        schema=EvidenceSchemaRef(schema_id="ugence.receipt.evidence-verification",
                                 schema_version="1"),
        source_evidence_identity_digest=ident().canonical_digest(),
        evidence_content_digest=C,
        verification_request_digest=req().canonical_digest(),
        scope=sc(), verified_at=RT,
        verifier_authority_id="Ugence Root Trust Authority",
        verifier_key_id="root-signing-key",
        verification_protocol_id="ugence.tap.verification",
        verification_protocol_version="1",
        declared_outcome=DeclaredVerificationOutcome.DECLARED_ADMITTED,
        declared_cleared_stages=tuple(RECEIPT_REPORTABLE_TRUST_STAGES),
        declared_unattempted_stages=(), declared_refusal_reasons=(),
        evidence_valid_from=V0, evidence_valid_to=V1,
        receipt_valid_from=datetime(2026, 6, 1, tzinfo=UTC),
        receipt_valid_to=datetime(2026, 12, 1, tzinfo=UTC))
    base.update(kw); return EvidenceVerificationReceiptPayload(**base)

_r = rcpt()
# A second, independent receipt vector: this fixture deliberately differs from
# the test suite's (an authoritative-sounding verifier and key), so it pins its
# own digest rather than reusing the suite's.
assert _r.canonical_digest() == "53b4c28caf7fec4b9c739a0b408b9830980b032073ccf9b887f43d979c8cd4c0", _r.canonical_digest()
assert hashlib.sha256(_r.canonical_bytes()).hexdigest() == _r.canonical_digest()
_rf = json.loads(_r.canonical_bytes())
assert _rf["domain"] == EVIDENCE_VERIFICATION_RECEIPT_PAYLOAD_DIGEST_DOMAIN
assert _rf["domain"] != EVIDENCE_IDENTITY_DIGEST_DOMAIN
assert _rf["type"] == "EvidenceVerificationReceiptPayload"
for other in (ident(), sc(), obs(), req(), ident().claim, ident().provenance,
              EvidenceSchemaRef(schema_id="x", schema_version="1")):
    assert canonical_bytes(other) != _r.canonical_bytes()
    assert canonical_digest(other) != _r.canonical_digest()
    assert json.loads(canonical_bytes(other))["domain"] != _rf["domain"]

# declared != established, even at maximum declared favourability
assert _r.declares_admission is True
assert set(_r.declared_cleared_stages) == set(RECEIPT_REPORTABLE_TRUST_STAGES)
assert _r.structural_status is EvidenceStructuralStatus.STRUCTURAL_UNVERIFIED
assert _r.authenticity_verified is False
assert _r.established_trust_stages == (EvidenceTrustStage.STRUCTURALLY_CONSTRUCTIBLE,)
assert EvidenceTrustStage.CRYPTOGRAPHICALLY_AUTHENTIC in _r.unestablished_trust_stages
assert EvidenceTrustStage.POLICY_SUFFICIENT in _r.unestablished_trust_stages
assert _r.envelope_verification_reason is R.TRUSTED_EVIDENCE_VERIFICATION_NOT_PERFORMED

# no signature field, anywhere
_rnames = {f.name for f in dataclasses.fields(EvidenceVerificationReceiptPayload)}
for banned in ("signature", "signed", "signer", "envelope", "trust_anchor",
               "public_key", "algorithm", "certificate"):
    assert banned not in _rnames, banned
assert not any("sign" in k.lower() for k in _rf["body"])
for banned in ("signature", "signed", "trust_anchor", "verified"):
    refuses(lambda b=banned: rcpt(**{b: b"x"}), TypeError)

# forgery routes
refuses(lambda: setattr(_r, "authenticity_verified", True), dataclasses.FrozenInstanceError)
refuses(lambda: object.__setattr__(_r, "authenticity_verified", True), AttributeError)
_r.__dict__["authenticity_verified"] = True
assert _r.authenticity_verified is False
for attempt in ("DECLARED_VERIFIED", "AUTHORITY_VERIFIED", "OK"):
    refuses(lambda a=attempt: DeclaredVerificationOutcome(a), ValueError)

# stage/outcome coherence
for f in ("declared_cleared_stages", "declared_unattempted_stages"):
    refuses(lambda f=f: rcpt(**{f: (EvidenceTrustStage.POLICY_SUFFICIENT,)}))
refuses(lambda: rcpt(declared_cleared_stages=(EvidenceTrustStage.CURRENTLY_VALID,),
                     declared_unattempted_stages=(EvidenceTrustStage.CURRENTLY_VALID,)))
refuses(lambda: rcpt(declared_refusal_reasons=(R.TRUSTED_EVIDENCE_STALE,)))
refuses(lambda: rcpt(declared_cleared_stages=()))
refuses(lambda: rcpt(declared_outcome=DeclaredVerificationOutcome.DECLARED_REFUSED,
                     declared_refusal_reasons=()))
refuses(lambda: rcpt(declared_outcome=DeclaredVerificationOutcome.DECLARED_INDETERMINATE,
                     declared_cleared_stages=(EvidenceTrustStage.STRUCTURALLY_CONSTRUCTIBLE,),
                     declared_refusal_reasons=(R.TRUSTED_EVIDENCE_STALE,)))
refuses(lambda: rcpt(verified_at=datetime(2026, 6, 1)))

# reordered order-irrelevant sets are equivalent
_a = rcpt(declared_cleared_stages=(EvidenceTrustStage.STRUCTURALLY_CONSTRUCTIBLE,
                                   EvidenceTrustStage.CURRENTLY_VALID))
_b = rcpt(declared_cleared_stages=(EvidenceTrustStage.CURRENTLY_VALID,
                                   EvidenceTrustStage.STRUCTURALLY_CONSTRUCTIBLE))
assert _a.canonical_bytes() == _b.canonical_bytes()

# the two validity intervals are distinct and half-open
_v = rcpt(evidence_valid_from=datetime(2026, 1, 1, tzinfo=UTC),
          evidence_valid_to=datetime(2026, 2, 1, tzinfo=UTC),
          receipt_valid_from=datetime(2026, 6, 1, tzinfo=UTC),
          receipt_valid_to=datetime(2026, 12, 1, tzinfo=UTC))
assert _v.receipt_is_valid_at(datetime(2026, 7, 1, tzinfo=UTC)) is True
assert _v.evidence_is_valid_at(datetime(2026, 7, 1, tzinfo=UTC)) is False
assert _v.receipt_is_valid_at(datetime(2026, 12, 1, tzinfo=UTC)) is False
assert _v.receipt_is_valid_at(datetime(2026, 6, 1, tzinfo=UTC)) is True
refuses(lambda: rcpt(receipt_valid_from=V1, receipt_valid_to=V0))
refuses(lambda: rcpt(evidence_valid_from=V1, evidence_valid_to=V0))

# ---- TEV-2: the verification authority, end to end inside the wheel ---------
#
# NOT PRODUCTION KEYS. Fixed, published or trivially-patterned byte ranges,
# committed to a public source tree purely so this proof is deterministic.
NON_PRODUCTION_VERIFY_PRODUCER_SEED = bytes(range(192, 224))
NON_PRODUCTION_VERIFY_AUTHORITY_SEED = bytes(range(224, 256))

_prod_key = TrustedEvidenceSigningKey(NON_PRODUCTION_VERIFY_PRODUCER_SEED)
_auth_key = TrustedEvidenceSigningKey(NON_PRODUCTION_VERIFY_AUTHORITY_SEED)
_PA, _PK = "dist-producer-authority-nonprod", "dist-producer-key-nonprod"
_VA, _VK = "dist-verifier-authority-nonprod", "dist-verifier-key-nonprod"
_KF = datetime(2026, 1, 1, tzinfo=UTC)
_KT = datetime(2027, 1, 1, tzinfo=UTC)
_VT = datetime(2026, 6, 1, 8, 0, 0, 750000, tzinfo=UTC)
_AT = datetime(2026, 6, 1, tzinfo=UTC)

# RFC 8032 §7.1 TEST 1 — the installed signer implements the standard algorithm.
_rfc = TrustedEvidenceSigningKey(bytes.fromhex(
    "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"))
assert encode_public_key(_rfc.verification_key.public_key_bytes) == (
    "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
assert encode_signature(_rfc.sign(b"")) == (
    "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8"
    "821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b")

def _anchor(**kw):
    base = dict(authority_id=_VA, key_id=_VK,
                capability=TrustAnchorCapability.RECEIPT_ISSUANCE,
                public_key=encode_public_key(
                    _auth_key.verification_key.public_key_bytes),
                trust_anchor_set_id="dist-set", trust_anchor_set_version="1",
                effective_from=_KF, effective_to=_KT)
    base.update(kw); return TrustAnchorRecord(**base)

_producer_anchor = _anchor(
    authority_id=_PA, key_id=_PK,
    capability=TrustAnchorCapability.EVIDENCE_PRODUCTION,
    public_key=encode_public_key(_prod_key.verification_key.public_key_bytes))

def _directory(*anchors):
    return StaticTrustAnchorDirectory(
        anchors or (_producer_anchor, _anchor()),
        trust_anchor_set_id="dist-set", trust_anchor_set_version="1")

_evidence = ident()
_submission = SignedEvidenceSubmission(
    envelope_schema=SIGNED_EVIDENCE_SUBMISSION_SCHEMA_V1,
    evidence=_evidence,
    evidence_identity_digest=_evidence.canonical_digest(),
    producer_authority_id=_PA, producer_key_id=_PK,
    signature_profile=TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1,
    signed_input_domain=TRUSTED_EVIDENCE_SIGNED_EVIDENCE_INPUT_DOMAIN,
    signature=encode_signature(_prod_key.sign(signed_evidence_input_bytes(
        evidence=_evidence, producer_authority_id=_PA, producer_key_id=_PK))))

_signer = Ed25519ReceiptSigner(
    signer_authority_id=_VA, signing_key_id=_VK, signing_key=_auth_key)
_authority = EvidenceVerificationAuthority(
    authority_id=_VA, trust_anchors=_directory(),
    protocol=Ed25519EvidenceAuthenticityProtocol(),
    receipt_schema=EvidenceSchemaRef(
        schema_id="ugence.receipt.evidence-verification", schema_version="1"))

_det = _authority.verify(_submission, req(), verified_at=_VT, verifier_key_id=_VK)
assert _det.outcome is EvidenceAdmissionOutcome.ADMITTED, _det.refusal_reasons
assert _det.admitted is True and _det.refusal_reasons == ()

_env = ReceiptIssuer(signer=_signer).issue(_det)
assert isinstance(_env, SignedEvidenceVerificationReceipt)
assert _env.envelope_schema == SIGNED_RECEIPT_ENVELOPE_SCHEMA_V1
assert _env.signed_input_domain == TRUSTED_EVIDENCE_SIGNED_RECEIPT_INPUT_DOMAIN
assert _env.signature_encoding == TRUSTED_EVIDENCE_SIGNATURE_ENCODING_V1

# Pinned TEV-2 vectors, reproduced from the installed wheel.
assert _env.payload.receipt_id == "receipt-90f644a29950267a8af2a836ff8ed67288f8ed91611239a62b1aa593997a8479", _env.payload.receipt_id
assert _env.payload_canonical_digest == "70f5bcc7edd8a5c396a4afba5c0787955f1440b11d797afb763a50df35bf47b0", _env.payload_canonical_digest
assert _env.envelope_digest() == "9dc4b08950abaa96a0bea65c313afd101ee18143c63e13bae10fc6574d2bea57", _env.envelope_digest()
assert _env.signature == ("2f322fbae9cbb2d0d11ebbd244bb33762c4d1d02442cbfdccea4d3ddeb641df6" "e31f6718e9ed3fb0db8d4d40b7de9a5749cb976c1bd3ea15b7011eae31d1b001"), _env.signature
assert _submission.signature == ("1573c4f355ffe9cd970c0718e6b603e9d12a032af9dc8c314eac722d461e9e47" "8127e264d02223b6e1551b27ee8b003f8d1cadf426fa30505dec68da54e24f0c"), _submission.signature
assert hashlib.sha256(_env.signed_input_bytes()).hexdigest() == "f009f27699306664e74dfec7ff1d5fbaa052f28487db8044c42486486ac9aebe"

# The signed input is reconstructible from the documented rules alone.
_w = 8
_elements = (
    TRUSTED_EVIDENCE_SIGNED_RECEIPT_INPUT_DOMAIN.encode("utf-8"),
    SIGNED_RECEIPT_ENVELOPE_SCHEMA_V1.encode("utf-8"),
    TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1.encode("utf-8"),
    TRUSTED_EVIDENCE_CANONICALIZATION_VERSION.encode("utf-8"),
    EVIDENCE_VERIFICATION_RECEIPT_PAYLOAD_DIGEST_DOMAIN.encode("utf-8"),
    _VA.encode("utf-8"), _VK.encode("utf-8"),
    _env.payload.verification_protocol_id.encode("utf-8"),
    _env.payload.verification_protocol_version.encode("utf-8"),
    _env.payload.canonical_digest().encode("utf-8"),
    canonical_bytes(_env.payload))
_hand = b"".join([len(_elements).to_bytes(_w, "big")] + [
    piece for e in _elements for piece in (len(e).to_bytes(_w, "big"), e)])
assert _env.signed_input_bytes() == _hand

# Independent re-verification, and a key rebuilt from the published hex.
_verified = SignedReceiptVerifier(trust_anchors=_directory()).verify(
    _env, evaluated_at=_AT, expected_tenant_id=_env.payload.scope.tenant_id)
assert _verified.outcome is ReceiptVerificationOutcome.VERIFIED
assert _verified.verified is True and _verified.refusal_reason is None
assert TrustedEvidenceVerificationKey(
    bytes.fromhex(_anchor().public_key)).verify(
        _env.signed_input_bytes(), _env.signature_bytes())

# The principal refusal classes fire from the installed wheel.
def _refuses_with(reason, *, anchors=None, at=None, envelope=None, **expected):
    result = SignedReceiptVerifier(
        trust_anchors=anchors or _directory()).verify(
            envelope or _env, evaluated_at=at or _AT, **expected)
    assert result.outcome is ReceiptVerificationOutcome.REFUSED, reason
    assert result.verified is False
    assert result.refusal_reason is reason, (reason, result.refusal_reason)

_refuses_with(R.TRUSTED_EVIDENCE_TRUST_ANCHOR_NOT_CONFIGURED,
              anchors=DenyAllTrustAnchorDirectory())
_refuses_with(R.TRUSTED_EVIDENCE_TRUST_ANCHOR_MISSING,
              anchors=_directory(_producer_anchor))
_refuses_with(R.TRUSTED_EVIDENCE_KEY_REVOKED, anchors=_directory(
    _producer_anchor, _anchor(revocation=KeyRevocation(effective_at=_KF))))
_refuses_with(R.TRUSTED_EVIDENCE_KEY_EXPIRED, anchors=_directory(
    _producer_anchor, _anchor(effective_to=datetime(2026, 2, 1, tzinfo=UTC))))
_refuses_with(R.TRUSTED_EVIDENCE_KEY_NOT_YET_VALID, anchors=_directory(
    _producer_anchor, _anchor(effective_from=datetime(2026, 12, 1, tzinfo=UTC))))
_refuses_with(R.TRUSTED_EVIDENCE_KEY_DISABLED, anchors=_directory(
    _producer_anchor, _anchor(disabled=True)))
_refuses_with(R.TRUSTED_EVIDENCE_SIGNATURE_INVALID, anchors=_directory(
    _producer_anchor, _anchor(public_key=encode_public_key(
        _prod_key.verification_key.public_key_bytes))))
_refuses_with(R.TRUSTED_EVIDENCE_TENANT_MISMATCH,
              expected_tenant_id="a-different-tenant")
_refuses_with(R.TRUSTED_EVIDENCE_CONTENT_DIGEST_MISMATCH,
              expected_evidence_content_digest=OTHER)

# A tampered signature, and a swapped payload.
_flipped = bytearray(_env.signature_bytes()); _flipped[0] ^= 0x01
_refuses_with(R.TRUSTED_EVIDENCE_SIGNATURE_INVALID, envelope=dataclasses.replace(
    _env, signature=encode_signature(bytes(_flipped))))
_other_payload = rcpt(receipt_id="a-different-receipt")
_refuses_with(R.TRUSTED_EVIDENCE_SIGNATURE_INVALID, envelope=dataclasses.replace(
    _env, payload=_other_payload,
    payload_canonical_digest=_other_payload.canonical_digest()))
refuses(lambda: dataclasses.replace(_env, payload=_other_payload),
        TrustedEvidenceContractError)

# No arbitrary-signing route, and no manufactured success, from the wheel.
refuses(lambda: ReceiptIssuer(signer=_signer).issue(_authority.verify(
    _submission, req(expected_tenant_id="other"), verified_at=_VT,
    verifier_key_id=_VK)), TrustedEvidenceContractError)
for _bad in (b"bytes", "string", None, 42):
    refuses(lambda b=_bad: _signer.sign_receipt(b), TrustedEvidenceContractError)

# The wrapped TEV-1 payload is untouched by all of this.
assert _env.payload.structural_status is EvidenceStructuralStatus.STRUCTURAL_UNVERIFIED
assert _env.payload.authenticity_verified is False
assert EvidenceTrustStage.POLICY_SUFFICIENT not in _env.payload.declared_cleared_stages

# Private key material reaches nothing that leaves the process.
_hex = NON_PRODUCTION_VERIFY_AUTHORITY_SEED.hex()
_record = audit_record_for_determination(_det, tenant_id="tenant-1", envelope=_env)
for _rendering in (repr(_auth_key), str(_auth_key), repr(_signer),
                   canonical_bytes(_env).decode("utf-8"),
                   canonical_bytes(_record).decode("utf-8"),
                   canonical_bytes(_anchor()).decode("utf-8")):
    assert _hex not in _rendering
assert repr(_auth_key) == "TrustedEvidenceSigningKey(<redacted>)"

# The refusal vocabulary is one namespace: TEV-1's nineteen, plus TEV-2's.
assert len(TEV1_TRUSTED_EVIDENCE_REFUSAL_REASONS) == 19
assert TEV1_TRUSTED_EVIDENCE_REFUSAL_REASONS.isdisjoint(
    TEV2_TRUSTED_EVIDENCE_REFUSAL_REASONS)
assert (TEV1_TRUSTED_EVIDENCE_REFUSAL_REASONS
        | TEV2_TRUSTED_EVIDENCE_REFUSAL_REASONS) == TRUSTED_EVIDENCE_REFUSAL_REASONS
assert set(list(TrustedEvidenceRefusalReason)[:19]) == (
    TEV1_TRUSTED_EVIDENCE_REFUSAL_REASONS)

# ---- installed surface == committed public_api.json ------------------------
def kind(o):
    if isinstance(o, type):
        if issubclass(o, enum.Enum): return "enum"
        if issubclass(o, Exception): return "exception"
        if dataclasses.is_dataclass(o): return "dataclass"
        return "class"
    return "function" if callable(o) else "constant"

def const_value(o):
    if isinstance(o, str): return o
    if isinstance(o, (tuple, list)): return [getattr(v, "value", v) for v in o]
    if isinstance(o, frozenset): return sorted(getattr(v, "value", v) for v in o)
    if hasattr(o, "items"):
        return {getattr(k, "value", k): sorted(getattr(v, "value", v) for v in val)
                for k, val in o.items()}
    return repr(o)

symbols = {}
for name in sorted(api.__all__):
    if name == "__version__": continue
    o = getattr(api, name)
    e = {"kind": kind(o)}
    if isinstance(o, type) and issubclass(o, enum.Enum): e["values"] = [m.value for m in o]
    elif isinstance(o, type) and dataclasses.is_dataclass(o):
        e["fields"] = [f.name for f in dataclasses.fields(o)]
    elif e["kind"] == "constant": e["value"] = const_value(o)
    symbols[name] = e

documented = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
assert documented["distribution"] == "ugence-trusted-evidence-authority"
assert documented["namespace"] == "ugence_trusted_evidence_authority"
assert documented["package_version"] == u.__version__
assert documented["curated_api_module"] == "ugence_trusted_evidence_authority.api"
assert documented["symbols"] == symbols, {
    k: (documented["symbols"].get(k), symbols.get(k))
    for k in set(documented["symbols"]) | set(symbols)
    if documented["symbols"].get(k) != symbols.get(k)}
assert set(u.__all__) - {"api"} == set(api.__all__)

# ---- no foreign package importable in this clean env ------------------------
for mod in ("ugence_governance_contracts", "ugence_uvi_policy_contracts",
            "ugence_policy_authority", "ugence_governed_value", "governed_value",
            "agent_value_readiness", "ugence_agent_value_readiness", "risk_authority",
            "governance_providers", "decision_governance", "actiongate_provider",
            "tap_provider", "ugence_tap_provider", "truth_assurance_pipeline",
            "ai_hiring", "ugence_console_api", "platform_freeze", "pydantic"):
    assert importlib.util.find_spec(mod) is None, ("unrelated package present: " + mod)

print("ISOLATED TRUSTED-EVIDENCE-AUTHORITY VERIFICATION OK")
'''


def _run(cmd, **kw):
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    return subprocess.run(cmd, check=True, **kw)


def _latest(path: Path, pattern: str) -> Path:
    files = sorted(path.glob(pattern))
    if not files:
        raise FileNotFoundError(f"no {pattern} in {path}")
    return files[-1]


def _safe_rmtree(target: Path, *, label: str) -> None:
    """Remove a package-local build artifact, refusing anything unsafe.

    Cleaning ``build/`` before packaging matters: a stale build tree can leave
    a previous module in the wheel. Doing it safely matters more, so the target
    must be a real directory (never a symlink, at any level of its path) and
    must live strictly inside this package.
    """

    if not target.exists() and not target.is_symlink():
        return
    if target.is_symlink():
        raise SystemExit(f"refusing to remove symlinked {label}: {target}")
    resolved = target.resolve()
    package_root = PKG.resolve()
    if not resolved.is_relative_to(package_root) or resolved == package_root:
        raise SystemExit(f"refusing to remove {label} outside the package: {resolved}")
    if not resolved.is_dir():
        raise SystemExit(f"refusing to remove non-directory {label}: {resolved}")
    for entry in resolved.rglob("*"):
        if entry.is_symlink():
            raise SystemExit(
                f"refusing to remove {label}: it contains a symlink ({entry})"
            )
    print(f"      cleaned {label}: {resolved.relative_to(package_root)}")
    shutil.rmtree(resolved)


def _wheel_members(wheel: Path):
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
    tops = {n.split("/", 1)[0] for n in names if "/" in n}
    foreign = {t for t in tops if not (t == NAMESPACE or t.endswith(".dist-info"))}
    return names, tops, foreign


def main() -> int:
    findlinks = PKG / "_dist_wheels"
    _safe_rmtree(findlinks, label="find-links directory")
    _safe_rmtree(PKG / "build", label="build tree")
    findlinks.mkdir()

    print(f"[1/5] build the {DISTRIBUTION} wheel (zero declared dependencies)")
    _run([sys.executable, "-m", "build", "--wheel", str(PKG), "-o", str(findlinks)])
    wheel = _latest(findlinks, f"{NAMESPACE}-*.whl")
    print(f"      built {wheel.name}")

    print("[2/5] assert the wheel ships exactly one namespace + dist-info + py.typed")
    names, tops, foreign = _wheel_members(wheel)
    assert not foreign, f"wheel bundles foreign top-level packages: {sorted(foreign)}"
    assert f"{NAMESPACE}/py.typed" in names, "wheel is missing py.typed"
    for name in names:
        lowered = name.lower()
        for banned in ("test", "conftest", "probe", "fixture", "_builders",
                       "build/", "public_api.json"):
            assert banned not in lowered, f"wheel contains {name} (matched {banned!r})"
    # No duplicate class definition: exactly one module file per module name.
    modules = [n for n in names if n.endswith(".py")]
    assert len(modules) == len(set(modules)), "duplicate module entries in the wheel"
    print(f"      {len(modules)} modules, top-level: {sorted(tops)}")

    print("[3/5] create an isolated venv and install ONLY this local wheel (--no-index)")
    with tempfile.TemporaryDirectory() as td:
        env = Path(td) / "venv"
        venv.create(env, with_pip=True, clear=True, system_site_packages=False)
        python = env / "bin" / "python"
        _run([str(python), "-m", "pip", "install", "--quiet", "--no-index",
              "--find-links", str(findlinks), DISTRIBUTION])

        print("[4/5] run the isolated proof (cwd has no monorepo source)")
        _run([str(python), "-c", _CHECK, str(PKG / "public_api.json")], cwd=str(td))

        print("[5/5] run the independent adversarial probes against the installed wheel")
        _run([str(python), str(PKG / "adversarial_probes.py")], cwd=str(td))

    _safe_rmtree(findlinks, label="find-links directory")
    _safe_rmtree(PKG / "build", label="build tree")
    print("\nISOLATED TRUSTED-EVIDENCE-AUTHORITY DISTRIBUTION VERIFIED ✔")
    return 0


if __name__ == "__main__":
    sys.exit(main())
