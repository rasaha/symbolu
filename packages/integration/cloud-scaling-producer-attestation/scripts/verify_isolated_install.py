#!/usr/bin/env python3
"""Reproducible proof that ``ugence-cloud-scaling-producer-attestation`` installs and
operates from its DECLARED dependencies alone, in a fresh virtualenv with no monorepo path.

Follows the proven Phase 4C/5A pattern exactly, including its honesty about what is offline.

**Scope of the claim, stated precisely.** This script's run is *not* offline as a whole, and
does not claim to be. It has four phases:

  * **Phase A (online)** — build the first-party wheels and download the full dependency
    closure into a local wheelhouse. Reaching an index here is what collecting a closure
    *means*; pretending otherwise would be the over-claim.
  * **Phase B (genuinely offline)** — the isolated-installation stage under test: install
    into a throwaway virtualenv from that wheelhouse alone, with no index reachable.
  * **Phase C (offline)** — negative controls that prove the phase-B guarantee.
  * **Phase D (offline)** — behaviour probes inside the isolated environment.

Only **phase B** is the guarantee, and the closing banner names exactly that.

Within phase B, ``--no-index`` and ``PIP_NO_INDEX=1`` are the *actual* index prohibition.
The unroutable ``OFFLINE_SENTINEL_INDEX`` is **defence in depth** and provides no protection
of its own: it exists so that if a future edit dropped one of those flags, resolution fails
loudly against an unroutable host rather than quietly succeeding against the real PyPI. No
editable install is used anywhere, and pip is never upgraded (that would be a network fetch,
and would make "offline installation" false).

It then proves, inside that clean environment:

  * the package imports from site-packages, not the repo checkout;
  * the exact public API matches the source tree and ``public_api.json``, symbol for symbol;
  * every frozen Phase 5B-0A digest reproduces byte for byte — the source digests are passed
    in as expected values, so any divergence fails here;
  * the positive control still verifies, and every refusal route still refuses;
  * the verified artifact still grants nothing and still revalidates;
  * NO envelope, ActionGate, credential, executor, Policy Authority, Decision Authority,
    Cloud Scaling Operations or controller symbol is importable, imported or exported;
  * NO clock source is reachable;
  * NO test, fixture or ``conftest.py`` leaked into the wheel.

Run:  python packages/integration/cloud-scaling-producer-attestation/scripts/verify_isolated_install.py
Exit code 0 on success; non-zero on the first failed step.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path
from typing import Sequence

PKG = Path(__file__).resolve().parents[1]
REPO = PKG.parents[2]

FIRST_PARTY = [
    REPO / "packages" / "risk_authority",
    REPO / "packages" / "trusted-evidence-authority",
    REPO / "packages" / "capabilities" / "cloud-scaling-controller",
    REPO / "packages" / "integration" / "cloud-scaling-risk-integration",
    REPO / "packages" / "integration" / "cloud-scaling-authorization-contracts",
    PKG,
]

REQUIRED_DISTRIBUTIONS = (
    "ugence_cloud_scaling_producer_attestation-",
    "ugence_cloud_scaling_authorization_contracts-",
    "ugence_trusted_evidence_authority-",
    "ugence_risk_authority-",
    "cryptography-",
    "PyNaCl-",
)

OFFLINE_SENTINEL_INDEX = "http://offline.invalid/simple"
EXPECTED_STEPS = 8

_PROBE = r'''
import dataclasses, importlib, json, pathlib, sys
from datetime import datetime, timedelta, timezone

EXPECTED = json.loads(sys.argv[1])

# Timestamps cross the process boundary in the CANONICAL spelling the packages themselves
# use — "%Y-%m-%dT%H:%M:%S.%fZ". ``datetime.isoformat`` renders "+00:00" instead, which the
# Phase 5A deserializer rightly refuses: two spellings of one instant is exactly what
# canonicalization exists to prevent.
def _ts(value):
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)

# --- 1. every package under test resolves to site-packages, not the repo checkout -------
import ugence_cloud_scaling_producer_attestation as p5b
import ugence_cloud_scaling_authorization_contracts as p5a
import ugence_trusted_evidence_authority as tev
import risk_authority as ra

for name, mod in (("p5b", p5b), ("p5a", p5a), ("tev", tev), ("ra", ra)):
    location = pathlib.Path(mod.__file__).resolve()
    if "site-packages" not in location.parts:
        raise AssertionError(f"{name} did not come from site-packages: {location}")

if p5b.__version__ != EXPECTED["version"]:
    raise AssertionError(f"version {p5b.__version__} != {EXPECTED['version']}")
if p5a.__version__ != "0.1.0":
    raise AssertionError(f"Phase 5A moved off 0.1.0: {p5a.__version__}")
if len(p5a.__all__) != 37:
    raise AssertionError(f"Phase 5A export count moved: {len(p5a.__all__)}")

# --- 2. exact public API parity with the source tree and with public_api.json -----------
installed_api = sorted(p5b.__all__)
if installed_api != sorted(EXPECTED["public_api"]):
    missing = set(EXPECTED["public_api"]) - set(installed_api)
    extra = set(installed_api) - set(EXPECTED["public_api"])
    raise AssertionError(f"public API drift: missing={sorted(missing)} extra={sorted(extra)}")
for symbol in installed_api:
    if not hasattr(p5b, symbol):
        raise AssertionError(f"{symbol} is exported but absent")

# --- 3. the identifiers are the ratified strings -----------------------------------------
assert p5b.PRODUCER_ATTESTATION_V2_SCHEMA_VERSION == EXPECTED["schema_version"]
assert p5b.PRODUCER_ATTESTATION_V2_SIGNING_PURPOSE == EXPECTED["signing_purpose"]
assert p5b.PRODUCER_ATTESTATION_V2_SCHEMA_VERSION != p5a.PRODUCER_ATTESTATION_SCHEMA_VERSION
assert p5b.PRODUCER_ATTESTATION_V2_SIGNING_PURPOSE != p5a.PRODUCER_SIGNING_PURPOSE
assert p5b.PRODUCER_ATTESTATION_V2_SIGNING_PURPOSE != p5a.PURPOSE_CAPACITY_ACTION
assert p5b.PRODUCER_ATTESTATION_CAPABILITY is (
    tev.TrustAnchorCapability.CLOUD_SCALING_RECOMMENDATION_ATTESTATION
)
assert p5b.PRODUCER_ATTESTATION_CAPABILITY is not tev.TrustAnchorCapability.EVIDENCE_PRODUCTION
assert p5b.PRODUCER_ATTESTATION_CAPABILITY is not tev.TrustAnchorCapability.RECEIPT_ISSUANCE

# --- 4. every trust contract is the IDENTICAL TEV object (no second anchor store) --------
for name in ("TrustAnchorCoordinate", "TrustAnchorRecord", "TrustAnchorCapability",
             "TrustAnchorResolution", "TrustAnchorResolverPort", "KeyRevocation",
             "StaticTrustAnchorDirectory", "DenyAllTrustAnchorDirectory"):
    if getattr(p5b, name) is not getattr(tev, name):
        raise AssertionError(f"{name} is not the identical TEV object inside the wheel")

# --- 5. the frozen digests reproduce byte for byte ---------------------------------------
TRUSTED_SEED = bytes(range(96, 128))
UNTRUSTED_SEED = bytes(range(128, 160))
ISSUER = "ugence.cloud-scaling-producer-authority"
PRODUCER = "ugence.cloud-scaling-controller"
KEY_ID = "producer-attestation-v2-key-1"
AS_OF = datetime(2026, 1, 1, 0, 5, 0, tzinfo=timezone.utc)
WINDOW_FROM = datetime(2026, 1, 1, tzinfo=timezone.utc)
WINDOW_TO = datetime(2026, 1, 2, tzinfo=timezone.utc)
ISSUED_AT = _ts(EXPECTED["issued_at"])

def signer(seed=TRUSTED_SEED, key_id=KEY_ID):
    return p5b.ReferenceEd25519ProducerAttestationSigner(
        producer_id=PRODUCER, issuer=ISSUER, producer_key_id=key_id,
        signing_key=tev.TrustedEvidenceSigningKey(seed))

def anchor(seed=TRUSTED_SEED, key_id=KEY_ID, capability=None, **kw):
    return p5b.TrustAnchorRecord(
        authority_id=ISSUER, key_id=key_id,
        capability=capability or p5b.PRODUCER_ATTESTATION_CAPABILITY,
        public_key=tev.encode_public_key(
            tev.TrustedEvidenceSigningKey(seed).verification_key.public_key_bytes),
        trust_anchor_set_id="cloud-scaling-producer-anchors",
        trust_anchor_set_version="1",
        effective_from=kw.pop("effective_from", WINDOW_FROM),
        effective_to=kw.pop("effective_to", WINDOW_TO), **kw)

def directory(*anchors):
    return p5b.StaticTrustAnchorDirectory(
        anchors or (anchor(),), trust_anchor_set_id="cloud-scaling-producer-anchors",
        trust_anchor_set_version="1")

def verifier(d=None, sv=None, production_mode=False):
    return p5b.ProducerAttestationVerifier(
        trust_anchor_resolver=d if d is not None else directory(),
        signature_verifier=sv if sv is not None else p5b.Ed25519ProducerSignatureVerifier(),
        production_mode=production_mode)

def mint(seed=TRUSTED_SEED, key_id=KEY_ID, **kw):
    return p5b.mint_producer_attestation(
        signer=signer(seed, key_id),
        tenant_id=kw.pop("tenant_id", EXPECTED["tenant_id"]),
        subject_id=kw.pop("subject_id", EXPECTED["subject_id"]),
        recommendation_id=kw.pop("recommendation_id", EXPECTED["recommendation_id"]),
        recommendation_digest=kw.pop("recommendation_digest",
                                     EXPECTED["recommendation_digest"]),
        issued_at=ISSUED_AT, **kw)

attestation = mint()
if attestation.signature != EXPECTED["v2_signature"]:
    raise AssertionError("the v2 signature is not byte-identical to the source tree's")
if attestation.signing_payload_digest != EXPECTED["v2_signing_payload_digest"]:
    raise AssertionError("the v2 signing-payload digest moved inside the wheel")
if attestation.digest() != EXPECTED["v2_attestation_digest"]:
    raise AssertionError("the v2 attestation digest moved inside the wheel")

coordinate = p5b.producer_anchor_coordinate(issuer=ISSUER, producer_key_id=KEY_ID)
if p5b.anchor_coordinate_digest(coordinate) != EXPECTED["anchor_coordinate_digest"]:
    raise AssertionError("the anchor coordinate digest moved inside the wheel")
if p5b.anchor_record_digest(anchor()) != EXPECTED["anchor_record_digest"]:
    raise AssertionError("the anchor record digest moved inside the wheel")

forged = mint(seed=UNTRUSTED_SEED)
if forged.digest() != EXPECTED["refused_attestation_digest"]:
    raise AssertionError("the refused-attestation fixture digest moved inside the wheel")

# --- 6. the positive control still verifies, against a candidate built in the wheel -------
# The candidate arrives as its canonical field values from the source tree, rebuilt here
# through Phase 5A's own exact type, so the verification runs against the real contract.
candidate = p5a.CapacityAuthorizationCandidate(**{
    **{k: v for k, v in EXPECTED["candidate_fields"].items()},
    "target_scope": p5a.ExecutionTargetScope(**EXPECTED["target_scope_fields"]),
    "policy_binding": p5a.PolicyTargetBindingReference(**EXPECTED["policy_fields"]),
    "producer_attestation": p5a.ProducerAttestationEvidence.from_dict(
        EXPECTED["v1_attestation"]),
    **{k: _ts(v) for k, v in EXPECTED["candidate_datetimes"].items()},
})
if candidate.candidate_digest != EXPECTED["candidate_digest"]:
    raise AssertionError("the Phase 5A candidate digest moved inside the wheel")

result = verifier().verify(candidate=candidate, attestation=attestation, as_of=AS_OF)
if result.refusal is not None:
    raise AssertionError(f"the positive control refused inside the wheel: {result.refusal}")
artifact = result.verified_attestation
if artifact.artifact_digest != EXPECTED["verified_artifact_digest"]:
    raise AssertionError("the verified-artifact digest moved inside the wheel")
if artifact.grants_authority is not False:
    raise AssertionError("the verified artifact claims authority inside the wheel")
if p5b.require_verified_producer_attestation(artifact) is not artifact:
    raise AssertionError("revalidation failed inside the wheel")

# --- 7. every refusal route still refuses, and mints nothing ------------------------------
O = p5b.ProducerAuthenticityOutcome
def refuses(label, attestation_arg, d=None, expected=None):
    r = verifier(d).verify(candidate=candidate, attestation=attestation_arg, as_of=AS_OF)
    if r.verified_attestation is not None:
        raise AssertionError(f"{label} minted an artifact inside the wheel")
    if r.refusal is None or r.refusal.outcome is O.VERIFIED:
        raise AssertionError(f"{label} produced no typed refusal inside the wheel")
    if expected is not None and r.refusal.outcome is not expected:
        raise AssertionError(f"{label}: {r.refusal.outcome} != {expected}")

refuses("absent", None, expected=O.ATTESTATION_ABSENT)
refuses("wrong exact type", object(), expected=O.UNSUPPORTED_EXACT_TYPE)
refuses("v1 attestation", candidate.producer_attestation, expected=O.UNSUPPORTED_EXACT_TYPE)
refuses("impostor key", mint(seed=UNTRUSTED_SEED), expected=O.SIGNATURE_INVALID)
refuses("unknown key", mint(seed=UNTRUSTED_SEED, key_id="not-registered"),
        expected=O.ANCHOR_UNKNOWN)
refuses("cross tenant", mint(tenant_id="tenant-2"), expected=O.WRONG_TENANT)
refuses("cross subject", mint(subject_id="billing-api"), expected=O.WRONG_SUBJECT)
refuses("wrong recommendation", mint(recommendation_digest="sha256:" + "b" * 64),
        expected=O.RECOMMENDATION_DIGEST_MISMATCH)
refuses("deny-all", attestation, p5b.DenyAllTrustAnchorDirectory(), O.ANCHOR_UNKNOWN)
refuses("revoked", attestation,
        directory(anchor(revocation=p5b.KeyRevocation(effective_at=WINDOW_FROM))),
        O.ANCHOR_REVOKED)
refuses("disabled", attestation, directory(anchor(disabled=True)), O.ANCHOR_DISABLED)
refuses("expired", attestation,
        directory(anchor(effective_to=WINDOW_FROM + timedelta(minutes=1))),
        O.ANCHOR_EXPIRED)
refuses("receipt-issuance key", attestation,
        directory(anchor(capability=tev.TrustAnchorCapability.RECEIPT_ISSUANCE)),
        O.ANCHOR_UNKNOWN)
# The cross-domain reuse an independent closure audit found, asserted against the
# INSTALLED wheel rather than the source tree: a key provisioned purely to sign Trusted
# Evidence must not attest a capacity recommendation. Everything but the anchor's
# capability is identical to the positive control above, which verified.
refuses("evidence-production key", attestation,
        directory(anchor(capability=tev.TrustAnchorCapability.EVIDENCE_PRODUCTION)),
        O.ANCHOR_UNKNOWN)

# the reference resolver is refused in production, inside the wheel too — and so is every
# SUBTYPE of it (closure-audit L-E). Exact-type matching used to let a subclass inherit the
# reference implementation, fail the identity test, and then satisfy an opt-in it declared
# for itself. These probes run the same cases against site-packages, not only against source.
class _PlainSubclass(p5b.StaticTrustAnchorDirectory):
    pass

class _OptedInSubclass(p5b.StaticTrustAnchorDirectory):
    is_production_authoritative = True

class _DeeperSubclass(_OptedInSubclass):
    pass

class _UnrelatedMixin:
    pass

class _MultipleInheritance(_UnrelatedMixin, p5b.StaticTrustAnchorDirectory):
    is_production_authoritative = True

for label, factory in (
    ("exact reference directory", lambda: directory()),
    ("plain subclass", lambda: _PlainSubclass(())),
    ("subclass declaring is_production_authoritative", lambda: _OptedInSubclass(())),
    ("deeper subclass", lambda: _DeeperSubclass(())),
    ("multiple inheritance", lambda: _MultipleInheritance(())),
):
    try:
        verifier(factory(), production_mode=True)
    except p5b.ProducerAttestationConfigurationError:
        pass
    else:
        raise AssertionError(
            f"{label} was admitted in production inside the wheel — the reference-grade "
            "denial is not subclass-aware in the installed distribution"
        )

# ...and the denial is not widened: an independently implemented resolver that opts in is
# still admissible, and so is the ratified deny-all posture.
class _IndependentProductionResolver:
    is_production_authoritative = True

    def resolve(self, coordinate):
        return p5b.TrustAnchorResolution.refused(
            coordinate,
            tev.TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_TRUST_ANCHOR_MISSING,
        )

verifier(_IndependentProductionResolver(), production_mode=True)
verifier(p5b.DenyAllTrustAnchorDirectory(), production_mode=True)

# a wrapper that merely HOLDS a reference directory is refused for not opting in, which is a
# different reason — proving the denial keys on what the object is, not what it contains.
class _WrappingResolver:
    def __init__(self):
        self._inner = directory()

    def resolve(self, coordinate):
        return self._inner.resolve(coordinate)

try:
    verifier(_WrappingResolver(), production_mode=True)
except p5b.ProducerAttestationConfigurationError as exc:
    if "REFERENCE" in str(exc):
        raise AssertionError(
            "a non-subclass wrapper was refused as reference grade inside the wheel; the "
            "denial has been widened beyond actual subtypes"
        )
else:
    raise AssertionError("a resolver that declared nothing was admitted inside the wheel")

# the reference signer is refused in production minting — and so is every SUBTYPE of it
# (post-merge audit M-1). The exact counterpart of the resolver matrix above, and open for
# the same reason: a subclass inherits the reference signer's whole implementation — the
# same in-memory TrustedEvidenceSigningKey, built from the same caller-supplied seed — so
# matching the denial by exact type let a one-line relabelling walk straight through.
class _PlainSignerSubclass(p5b.ReferenceEd25519ProducerAttestationSigner):
    pass

class _RelabelledSigner(p5b.ReferenceEd25519ProducerAttestationSigner):
    is_reference_signer = False

class _TwoLevelSigner(_RelabelledSigner):
    pass

class _MultipleInheritanceSigner(_UnrelatedMixin,
                                 p5b.ReferenceEd25519ProducerAttestationSigner):
    is_reference_signer = False

def _sub_signer(cls):
    return cls(producer_id=PRODUCER, issuer=ISSUER, producer_key_id=KEY_ID,
               signing_key=tev.TrustedEvidenceSigningKey(TRUSTED_SEED))

def _mint_in_production(s):
    return p5b.mint_producer_attestation(
        signer=s, tenant_id="t", subject_id="s", recommendation_id="r",
        recommendation_digest="sha256:" + "a" * 64, issued_at=ISSUED_AT,
        production_mode=True)

for label, factory in (
    ("the reference signer", lambda: signer()),
    ("plain signer subclass", lambda: _sub_signer(_PlainSignerSubclass)),
    ("subclass with is_reference_signer = False", lambda: _sub_signer(_RelabelledSigner)),
    ("two-level signer subclass", lambda: _sub_signer(_TwoLevelSigner)),
    ("multiple inheritance", lambda: _sub_signer(_MultipleInheritanceSigner)),
):
    try:
        _mint_in_production(factory())
    except p5b.ProducerAttestationConfigurationError as exc:
        if "REFERENCE" not in str(exc):
            raise AssertionError(
                f"{label} was refused inside the wheel, but not as reference grade: {exc}")
    else:
        raise AssertionError(
            f"{label} was admitted in production minting inside the wheel — the "
            "reference-grade signer denial is not subclass-aware in the installed "
            "distribution")

# ...and the denial is not widened: a custodian that COMPOSES a reference signer rather
# than inheriting from one is still admissible.
class _ComposingCustodian:
    is_reference_signer = False
    producer_id = PRODUCER
    issuer = ISSUER
    producer_key_id = KEY_ID
    signature_profile = p5b.PRODUCER_ATTESTATION_SIGNATURE_PROFILE

    def __init__(self):
        self._inner = signer()

    def sign_producer_attestation(self, signing_input):
        return self._inner.sign_producer_attestation(signing_input)

if _mint_in_production(_ComposingCustodian()).producer_key_id != KEY_ID:
    raise AssertionError(
        "a composing production custodian was refused inside the wheel; the reference-grade "
        "signer denial has been widened beyond actual subtypes")

# a fabricated verified artifact is refused at consumption
try:
    p5b.require_verified_producer_attestation(
        object.__new__(p5b.VerifiedProducerAttestation))
except p5b.VerifiedArtifactIntegrityError:
    pass
else:
    raise AssertionError("a fabricated verification artifact was admitted inside the wheel")

# --- 8. no authority, execution or clock symbol exists in the installed package -----------
import ast

pkg_dir = pathlib.Path(p5b.__file__).resolve().parent
for source_file in sorted(pkg_dir.rglob("*.py")):
    tree = ast.parse(source_file.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in {
                    "boto3", "kubernetes", "azure", "requests", "socket", "subprocess",
                    "time", "os", "pathlib", "secrets"}:
                    raise AssertionError(f"{source_file.name} imports {alias.name}")
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            if node.module.split(".")[0] in {
                "ugence_decision_authority", "ugence_actiongate_provider",
                "ugence_cloud_scaling_operations", "ugence_policy_authority",
                "ugence_cloud_scaling_controller"}:
                raise AssertionError(f"{source_file.name} imports {node.module}")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in {"now", "utcnow", "monotonic", "issue_envelope",
                                  "authorize_action", "issue_credential"}:
                raise AssertionError(f"{source_file.name} calls .{node.func.attr}()")

for symbol in p5b.__all__:
    lowered = symbol.lower()
    for fragment in ("envelope", "actiongate", "credential", "executor", "clock"):
        if fragment in lowered:
            raise AssertionError(f"public export {symbol} names {fragment}")

# --- 9. no test, fixture or conftest leaked into the wheel --------------------------------
for leaked in pkg_dir.rglob("*"):
    name = leaked.name
    if name in {"conftest.py", "_producer_fixtures.py"} or name.startswith("test_"):
        raise AssertionError(f"test material leaked into the wheel: {leaked}")
    if leaked.is_dir() and name in {"tests", "fixtures"}:
        raise AssertionError(f"test directory leaked into the wheel: {leaked}")
if not (pkg_dir / "py.typed").exists():
    raise AssertionError("py.typed is missing from the installed package")

# --- 10. no out-of-scope monorepo package is importable -----------------------------------
for module in ("symbolu", "agentic", "cloud_scaling_operations",
               "ugence_decision_authority", "ugence_actiongate_provider",
               "ugence_policy_authority"):
    try:
        importlib.import_module(module)
    except ImportError:
        pass
    else:
        raise AssertionError(f"out-of-scope package is importable: {module}")

print("INSTALLED-WHEEL PHASE 5B-0A PRODUCER-AUTHENTICITY VERIFICATION OK")
'''


def run(cmd, **kwargs):
    print("$", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run(cmd, check=True, **kwargs)


def source_expectations() -> dict:
    """Compute the expected values from the SOURCE tree, to compare the wheel against."""

    import dataclasses
    from datetime import timezone

    def _canonical_ts(value):
        """Render an instant the way the packages canonicalize it: UTC, microseconds, Z."""

        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    for path in (
        PKG / "src",
        REPO / "packages" / "integration" / "cloud-scaling-authorization-contracts" / "src",
        REPO / "packages" / "risk_authority" / "src",
        REPO / "packages" / "trusted-evidence-authority" / "src",
        REPO / "packages" / "capabilities" / "cloud-scaling-controller" / "src",
        REPO / "packages" / "integration" / "cloud-scaling-risk-integration" / "src",
        REPO / "packages" / "capabilities" / "cloud-scaling-controller" / "tests",
        REPO / "packages" / "capabilities" / "cloud-scaling-controller" / "tests" / "planning",
        PKG / "tests",
    ):
        sys.path.insert(0, str(path))

    import _producer_fixtures as F  # type: ignore[import-not-found]

    import ugence_cloud_scaling_producer_attestation as p5b

    candidate = F.build_candidate()
    attestation = F.build_attestation(candidate)
    anchor = F.build_anchor()
    coordinate = p5b.producer_anchor_coordinate(
        issuer=F.ISSUER_ID, producer_key_id=F.PRODUCER_KEY_ID
    )
    artifact = F.build_verifier(directory=F.build_directory(anchor)).verify(
        candidate=candidate, attestation=attestation, as_of=F.AS_OF
    ).verified_attestation
    forged = F.build_attestation(
        candidate, seed=F.UNTRUSTED_PRODUCER_SEED, producer_key_id=F.PRODUCER_KEY_ID
    )

    scalar_fields, datetime_fields = {}, {}
    for field in dataclasses.fields(candidate):
        value = getattr(candidate, field.name)
        if field.name in ("target_scope", "policy_binding", "producer_attestation"):
            continue
        if hasattr(value, "isoformat"):
            datetime_fields[field.name] = _canonical_ts(value)
        else:
            scalar_fields[field.name] = value

    return {
        "version": p5b.__version__,
        "public_api": list(p5b.__all__),
        "schema_version": p5b.PRODUCER_ATTESTATION_V2_SCHEMA_VERSION,
        "signing_purpose": p5b.PRODUCER_ATTESTATION_V2_SIGNING_PURPOSE,
        "tenant_id": candidate.tenant_id,
        "subject_id": candidate.subject_id,
        "recommendation_id": candidate.recommendation_id,
        "recommendation_digest": candidate.recommendation_digest,
        "candidate_digest": candidate.candidate_digest,
        "issued_at": _canonical_ts(attestation.issued_at),
        "v2_signature": attestation.signature,
        "v2_signing_payload_digest": attestation.signing_payload_digest,
        "v2_attestation_digest": attestation.digest(),
        "anchor_coordinate_digest": p5b.anchor_coordinate_digest(coordinate),
        "anchor_record_digest": p5b.anchor_record_digest(anchor),
        "verified_artifact_digest": artifact.artifact_digest,
        "refused_attestation_digest": forged.digest(),
        "candidate_fields": scalar_fields,
        "candidate_datetimes": datetime_fields,
        "target_scope_fields": {
            f.name: getattr(candidate.target_scope, f.name)
            for f in dataclasses.fields(candidate.target_scope)
        },
        "policy_fields": {
            f.name: getattr(candidate.policy_binding, f.name)
            for f in dataclasses.fields(candidate.policy_binding)
        },
        "v1_attestation": {
            key: (_canonical_ts(value) if hasattr(value, "isoformat") else value)
            for key, value in candidate.producer_attestation.to_canonical_dict().items()
            if key != "trust_state"
        },
    }


def make_python(env_dir: Path) -> Path:
    """A clean virtualenv. pip comes from the local ``ensurepip`` bundle and is not upgraded."""

    venv.EnvBuilder(with_pip=True).create(env_dir)
    python = env_dir / "bin" / "python"
    if not python.exists():  # pragma: no cover - Windows layout
        python = env_dir / "Scripts" / "python.exe"
    return python


def offline_install(
    python: Path, wheelhouse: Path, requirement: str, *, extra_args: Sequence[str] = ()
) -> subprocess.CompletedProcess:
    """Install with index access structurally disabled. Three independent belts."""

    env = dict(os.environ)
    env.update(
        {
            "PIP_NO_INDEX": "1",
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_NO_PYTHON_VERSION_WARNING": "1",
            "PIP_INDEX_URL": OFFLINE_SENTINEL_INDEX,
            "PIP_EXTRA_INDEX_URL": OFFLINE_SENTINEL_INDEX,
            "PIP_NO_CACHE_DIR": "1",
        }
    )
    cmd = [
        str(python), "-m", "pip", "install", "--quiet",
        "--no-index", "--no-cache-dir",
        "--find-links", str(wheelhouse),
        *extra_args,
        requirement,
    ]
    print("$", " ".join(cmd), flush=True)
    return subprocess.run(cmd, check=True, env=env)


def expect_offline_install_failure(
    python: Path, wheelhouse: Path, requirement: str, *, why: str
) -> None:
    """Assert that an offline install *fails*. A negative control for the positive path."""

    try:
        offline_install(python, wheelhouse, requirement)
    except subprocess.CalledProcessError:
        print(f"  [ok] install failed as required — {why}", flush=True)
        return
    raise SystemExit(
        f"NEGATIVE PROBE FAILED: the install unexpectedly SUCCEEDED — {why}. "
        "The offline guarantee is not being enforced."
    )


def main() -> int:
    steps: list[str] = []

    def done(step: str) -> None:
        steps.append(step)
        print(f"  [step complete] {step}", flush=True)

    expected = source_expectations()
    print("source expectations:")
    for key in (
        "version", "candidate_digest", "v2_signing_payload_digest",
        "v2_attestation_digest", "anchor_coordinate_digest", "anchor_record_digest",
        "verified_artifact_digest", "refused_attestation_digest",
    ):
        print(f"  {key} = {expected[key]}")
    print(f"  public_api = {len(expected['public_api'])} symbols")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        wheelhouse = tmp_path / "wheelhouse"
        wheelhouse.mkdir()

        # === PHASE A — collection. ONLINE by design, and the only phase that is. ========
        print("\n=== PHASE A (online): build + collect every required wheel ===", flush=True)
        for project in FIRST_PARTY:
            run([sys.executable, "-m", "build", "--wheel", "--outdir", str(wheelhouse),
                 str(project)])
        done("first-party wheels built")

        run([
            sys.executable, "-m", "pip", "download", "--quiet",
            "--only-binary=:all:",
            "--dest", str(wheelhouse),
            "--find-links", str(wheelhouse),
            "ugence-cloud-scaling-producer-attestation",
        ])
        collected = sorted(p.name for p in wheelhouse.glob("*.whl"))
        print(f"  wheelhouse now holds {len(collected)} wheel(s):", flush=True)
        for name in collected:
            print(f"    - {name}", flush=True)
        for required in REQUIRED_DISTRIBUTIONS:
            if not any(name.lower().startswith(required.lower()) for name in collected):
                raise SystemExit(
                    f"required distribution {required!r} is absent from the wheelhouse; "
                    "refusing to enter the offline phase with an incomplete wheelhouse"
                )
        done("dependency closure collected into the wheelhouse")

        # === PHASE B — the genuinely offline stage this verifier exists to prove. =======
        print("\n=== PHASE B (offline): install with the index structurally disabled ===",
              flush=True)
        env_dir = tmp_path / "env"
        python = make_python(env_dir)
        done("clean virtualenv created (pip from local ensurepip, never upgraded)")

        offline_install(python, wheelhouse, "ugence-cloud-scaling-producer-attestation")
        done("package installed offline from the local wheelhouse only")

        # === PHASE C — negative controls. An "offline" claim nobody tested is a guess. ==
        print("\n=== PHASE C: negative controls on the offline guarantee ===", flush=True)

        crippled = tmp_path / "crippled-wheelhouse"
        crippled.mkdir()
        removed = None
        for wheel in wheelhouse.glob("*.whl"):
            if wheel.name.startswith("ugence_trusted_evidence_authority-"):
                removed = wheel.name
                continue
            shutil.copy2(wheel, crippled / wheel.name)
        if removed is None:
            raise SystemExit("could not identify the TEV wheel to remove")
        print(f"  removed {removed} from a copy of the wheelhouse", flush=True)
        crippled_env = make_python(tmp_path / "env-crippled")
        expect_offline_install_failure(
            crippled_env, crippled, "ugence-cloud-scaling-producer-attestation",
            why="a required wheel was absent from the wheelhouse",
        )
        done("negative control: missing wheel causes failure, not an index fetch")

        bogus_env = make_python(tmp_path / "env-bogus")
        try:
            subprocess.run(
                [
                    str(bogus_env), "-m", "pip", "install", "--quiet", "--no-cache-dir",
                    "--index-url", OFFLINE_SENTINEL_INDEX,
                    "--find-links", str(crippled),
                    "ugence-cloud-scaling-producer-attestation",
                ],
                check=True,
                env={**os.environ, "PIP_NO_CACHE_DIR": "1",
                     "PIP_DISABLE_PIP_VERSION_CHECK": "1"},
                timeout=300,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            print("  [ok] a bogus index could not supply the missing distribution", flush=True)
        else:
            raise SystemExit(
                "NEGATIVE PROBE FAILED: the install succeeded against a bogus index — "
                "something other than the wheelhouse supplied the distribution"
            )
        done("negative control: a bogus index cannot rescue an incomplete wheelhouse")

        probe = subprocess.run(
            [str(crippled_env), "-c", "import ugence_cloud_scaling_producer_attestation"],
            capture_output=True,
        )
        if probe.returncode == 0:
            raise SystemExit(
                "NEGATIVE PROBE FAILED: the package is importable in an environment whose "
                "installation failed — a failed install left a usable package"
            )
        print("  [ok] the failed installation left nothing importable", flush=True)
        done("negative control: a failed install cannot yield a working package")

        # === PHASE D — behaviour probes inside the isolated environment. ================
        print("\n=== PHASE D: behaviour probes in the isolated environment ===", flush=True)
        probe_dir = tmp_path / "probe"
        probe_dir.mkdir()
        probe_file = probe_dir / "probe.py"
        probe_file.write_text(_PROBE, encoding="utf-8")

        probe_env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        run([str(python), str(probe_file), json.dumps(expected)],
            cwd=str(probe_dir), env=probe_env)
        done("import, API-parity, digest-parity, refusal and non-authority probes passed")

    if len(steps) != EXPECTED_STEPS:
        raise SystemExit(
            f"refusing to report success: {len(steps)} of {EXPECTED_STEPS} steps "
            f"completed ({steps})"
        )
    print(f"\nall {EXPECTED_STEPS} verification steps completed:", flush=True)
    for step in steps:
        print(f"  - {step}")
    print("\nOFFLINE ISOLATED INSTALLATION STAGE VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
