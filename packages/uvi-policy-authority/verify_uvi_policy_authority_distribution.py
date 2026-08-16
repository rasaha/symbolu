#!/usr/bin/env python3
"""Reproducible proof that the UVI Policy Authority installs and operates from a
built wheel, with ONLY the two neutral contract leaves as cross-package
dependencies and NO readiness, governed-value, risk-authority or other foreign
package on the path.

Builds ``ugence-uvi-policy-authority`` and its two dependencies
(``ugence-uvi-policy-contracts``, ``ugence-governance-contracts``) into a local
find-links directory, installs the former (pip resolves the latter two) into a
fresh venv with no system site packages and no monorepo path (``--no-index`` —
all wheels are local, zero third-party deps), then proves inside that env:

  * ``ugence_uvi_policy_authority`` imports from site-packages, ships py.typed;
  * the curated API resolves and reports version 0.1.0;
  * the content digest is a single-pass fixed relation with no circularity, and
    an arbitrary well-formed 64-hex value is refused;
  * all five merged policy families issue, resolve, and verify end to end;
  * the shipped default approval verifier denies, a self-approving authority is
    refused, and no signature is produced when approval fails;
  * signature tampering, an unknown key and a revoked key each fail closed with
    a distinct typed reason;
  * effective-period boundaries are half-open and cross-tenant access fails;
  * policy-version revocation denies at and after its instant;
  * no system clock is reachable in the installed source;
  * NO ``ugence_agent_value_readiness`` / ``governed_value`` / ``risk_authority``
    / capability / product / third-party package is importable.

Run:  python packages/uvi-policy-authority/verify_uvi_policy_authority_distribution.py
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
REPO = PKG.parents[1]  # packages/uvi-policy-authority -> packages -> repo

SOURCES = {
    "ugence_uvi_policy_authority": PKG,
    "ugence_uvi_policy_contracts": REPO / "packages" / "uvi-policy-contracts",
    "ugence_governance_contracts": REPO / "packages" / "governance-contracts",
}

_CHECK = r'''
import ast, dataclasses, hashlib, importlib.util, pathlib, sys
from datetime import datetime, timedelta, timezone

import ugence_uvi_policy_authority as pa
assert pa.__version__ == "0.1.0", pa.__version__
assert "site-packages" in pa.__file__, pa.__file__
assert not any("/symbolu" in p for p in sys.path), sys.path
ROOT = pathlib.Path(pa.__file__).resolve().parent
assert (ROOT / "py.typed").is_file(), "py.typed not installed"

from ugence_uvi_policy_contracts.api import (
    ComponentEvidenceRequirement, DomainPolicy, GeographyPolicy, IntendedOutcomePolicy,
    PolicyArtifactMetadata, PolicyFamily, PolicyLifecycleState, PolicyReference,
    PolicyScope, ReadinessPolicy, ValuationPolicy, ValueComponent,
)
from ugence_uvi_policy_authority.api import (
    ApprovalEvidenceRef, ApprovalVerification, ApprovalVerificationStatus,
    DenyAllApprovalVerifier, DenyAllSignatureVerifier, Ed25519PolicySigner,
    HistoricalResolutionRule, InMemoryPolicyRegistry, IssuedPolicyRecord,
    PolicyApprovalError, PolicyDigestMismatchError, PolicyKeyRing,
    PolicyRegistryConflictError, PolicyResolutionReason, PolicyResolutionStatus,
    PolicyRevocationReasonCode, SigningKey, UnsupportedPolicyFamilyError,
    canonical_policy_body_digest, issue_policy, resolve_policy, revoke_policy,
)

T_FROM = datetime(2026, 1, 1, tzinfo=timezone.utc)
T_MID  = datetime(2026, 6, 1, tzinfo=timezone.utc)
T_TO   = datetime(2027, 1, 1, tzinfo=timezone.utc)
SEC = timedelta(seconds=1)

BODIES = {
    PolicyFamily.GEOGRAPHY: (GeographyPolicy, dict(jurisdiction="US-CA", reporting_currency="USD", functional_currency="USD")),
    PolicyFamily.DOMAIN: (DomainPolicy, dict(governed_outcome_unit="resolved_ticket")),
    PolicyFamily.INTENDED_OUTCOME: (IntendedOutcomePolicy, dict(target_outcome="o", task_definition="t")),
    PolicyFamily.VALUATION: (ValuationPolicy, dict(required_components=(ComponentEvidenceRequirement(component=ValueComponent.GROSS_BENEFIT),))),
    PolicyFamily.READINESS: (ReadinessPolicy, dict()),
}

def meta(family, digest, **kw):
    base = dict(policy_id="pol-1", policy_family=family, version="1.0.0", content_digest=digest,
                lifecycle_state=PolicyLifecycleState.APPROVED_ACTIVE, effective_from=T_FROM, effective_to=T_TO)
    base.update(kw)
    return PolicyArtifactMetadata(**base)

def build(family, **kw):
    cls, body = BODIES[family]
    draft = cls(metadata=meta(family, "0" * 64, **kw), **body)
    return cls(metadata=meta(family, canonical_policy_body_digest(draft), **kw), **body)

class Verifier:
    def __init__(self, status=ApprovalVerificationStatus.APPROVED, approver="ugence.governance.policy-approval-board"):
        self.status, self.approver, self.calls = status, approver, 0
    def verify_approval(self, *, policy_reference, policy_body_digest, approval, as_of):
        self.calls += 1
        return ApprovalVerification(
            verified=self.status is ApprovalVerificationStatus.APPROVED, status=self.status,
            policy_reference=policy_reference, policy_body_digest=policy_body_digest,
            approving_authority_id=self.approver, approval_ref=approval.approval_ref,
            approval_digest=approval.approval_digest, verified_at=as_of)

class CountingSigner:
    def __init__(self, inner): self.inner, self.calls = inner, 0
    authority_id = property(lambda s: s.inner.authority_id)
    key_id = property(lambda s: s.inner.key_id)
    signature_alg = property(lambda s: s.inner.signature_alg)
    def sign(self, payload):
        self.calls += 1
        return self.inner.sign(payload)

EV = ApprovalEvidenceRef(approval_ref="APPROVAL-1", approval_digest=hashlib.sha256(b"a").hexdigest(),
                         approving_authority_id="ugence.governance.policy-approval-board")

def fresh():
    signer = Ed25519PolicySigner(authority_id="ugence.uvi.policy-authority", key_id="k1",
                                 signing_key=SigningKey.from_seed(b"\x01" * 32))
    return signer, PolicyKeyRing().with_key(signer.verification_key()), InMemoryPolicyRegistry(), Verifier()

# 1. digest is a single-pass fixed relation, no circularity
for fam in BODIES:
    p = build(fam)
    assert canonical_policy_body_digest(p) == p.metadata.content_digest, fam
    fields = {f.name for f in dataclasses.fields(p)} | {f.name for f in dataclasses.fields(p.metadata)}
    assert not [n for n in fields if "signature" in n], fam
print("  [ok] content digest binds the body in one pass, with no signature field anywhere")

# 2. every family issues, resolves, and returns by value with its proof
for fam in BODIES:
    p = build(fam)
    signer, ring, reg, ver = fresh()
    rec = issue_policy(policy=p, record_id="r", approval=EV, approval_verifier=ver,
                       signer=signer, registry=reg, issued_at=T_MID)
    assert isinstance(rec, IssuedPolicyRecord) and len(rec.signature) == 64
    res = resolve_policy(reference=p.reference, expected_tenant_id="", as_of=T_MID,
                         registry=reg, signature_verifier=ring)
    assert res.status is PolicyResolutionStatus.RESOLVED and res.policy == p, (fam, res.reason)
print("  [ok] all five merged policy families issue, resolve, and verify")

# 3. approval fails closed and no signature is produced
signer, ring, reg, ver = fresh()
counting = CountingSigner(signer)
p = build(PolicyFamily.DOMAIN)
try:
    issue_policy(policy=p, record_id="r", approval=EV, approval_verifier=DenyAllApprovalVerifier(),
                 signer=counting, registry=reg, issued_at=T_MID)
    raise SystemExit("FAIL: the deny-all verifier permitted issuance")
except PolicyApprovalError:
    pass
assert counting.calls == 0, "FAIL: the signer ran despite an approval failure"
assert reg.get_issued(p.reference) is None, "FAIL: the registry mutated on a failed issuance"

self_approve = Verifier(approver="ugence.uvi.policy-authority")
try:
    issue_policy(policy=p, record_id="r", approval=ApprovalEvidenceRef(
        approval_ref="A", approval_digest=hashlib.sha256(b"a").hexdigest(),
        approving_authority_id="ugence.uvi.policy-authority"),
        approval_verifier=self_approve, signer=counting, registry=reg, issued_at=T_MID)
    raise SystemExit("FAIL: the authority approved its own policy")
except PolicyApprovalError:
    pass
assert counting.calls == 0
print("  [ok] approval fails closed; no signature, no registry mutation, no self-approval")

# 4. an arbitrary well-formed digest and an unsupported type are refused
forged = dataclasses.replace(p, metadata=dataclasses.replace(p.metadata, content_digest="a" * 64))
try:
    issue_policy(policy=forged, record_id="r", approval=EV, approval_verifier=ver,
                 signer=signer, registry=reg, issued_at=T_MID)
    raise SystemExit("FAIL: an arbitrary 64-hex digest was accepted")
except PolicyDigestMismatchError:
    pass
try:
    issue_policy(policy=object(), record_id="r", approval=EV, approval_verifier=ver,
                 signer=signer, registry=reg, issued_at=T_MID)
    raise SystemExit("FAIL: an unsupported artifact was issued")
except UnsupportedPolicyFamilyError:
    pass
print("  [ok] arbitrary digests and unsupported artifacts are refused")

# 5. signature / key failures each fail closed with a distinct reason
signer, ring, reg, ver = fresh()
rec = issue_policy(policy=p, record_id="r", approval=EV, approval_verifier=ver,
                   signer=signer, registry=reg, issued_at=T_MID)
object.__setattr__(rec, "signature", b"\x00" * 64)
assert resolve_policy(reference=p.reference, expected_tenant_id="", as_of=T_MID, registry=reg,
                      signature_verifier=ring).reason is PolicyResolutionReason.SIGNATURE_INVALID
object.__setattr__(rec, "signature", signer.sign(rec.signing_payload()))
assert resolve_policy(reference=p.reference, expected_tenant_id="", as_of=T_MID, registry=reg,
                      signature_verifier=PolicyKeyRing()).reason is PolicyResolutionReason.KEY_UNKNOWN
revoked_ring = ring.with_key(ring.resolve("k1").revoke())
assert resolve_policy(reference=p.reference, expected_tenant_id="", as_of=T_MID, registry=reg,
                      signature_verifier=revoked_ring).reason is PolicyResolutionReason.KEY_REVOKED
assert resolve_policy(reference=p.reference, expected_tenant_id="", as_of=T_MID, registry=reg,
                      signature_verifier=DenyAllSignatureVerifier()).reason is PolicyResolutionReason.KEY_UNKNOWN
print("  [ok] tampered signature, unknown key, revoked key and no-verifier all fail closed")

# 6. effective-period boundaries and tenant isolation
def reason_at(moment, tenant=""):
    return resolve_policy(reference=p.reference, expected_tenant_id=tenant, as_of=moment,
                          registry=reg, signature_verifier=ring).reason
assert reason_at(T_FROM) is PolicyResolutionReason.RESOLVED
assert reason_at(T_FROM - SEC) is PolicyResolutionReason.NOT_YET_EFFECTIVE
assert reason_at(T_TO - SEC) is PolicyResolutionReason.RESOLVED
assert reason_at(T_TO) is PolicyResolutionReason.EXPIRED
assert reason_at(T_MID, "other-tenant") is PolicyResolutionReason.TENANT_SCOPE_MISMATCH
print("  [ok] effective_from inclusive, effective_to exclusive, cross-tenant denied")

# 7. append-only registry and policy-version revocation
try:
    issue_policy(policy=build(PolicyFamily.DOMAIN, version="1.0.0",
                              **{}) if False else p, record_id="other",
                 approval=EV, approval_verifier=ver, signer=signer, registry=reg, issued_at=T_MID)
    raise SystemExit("FAIL: a stored version was overwritten")
except PolicyRegistryConflictError:
    pass
revoke_policy(reference=p.reference, revocation_id="rv-1",
              reason_code=PolicyRevocationReasonCode.CONTENT_DEFECT,
              registry=reg, revoked_at=T_MID, signer=signer)
assert reason_at(T_MID) is PolicyResolutionReason.REVOKED
assert reason_at(T_MID - SEC) is PolicyResolutionReason.REVOKED  # DENY_ALWAYS default
assert resolve_policy(reference=p.reference, expected_tenant_id="", as_of=T_MID - SEC,
                      registry=reg, signature_verifier=ring,
                      historical_resolution=HistoricalResolutionRule.ALLOW_BEFORE_REVOCATION
                      ).status is PolicyResolutionStatus.RESOLVED
print("  [ok] registry is append-only; revocation denies at/after its instant")

# 8. no system clock in the installed source
banned = ("datetime.now(", "datetime.utcnow(", "time.time(", ".utcnow()")
for path in ROOT.rglob("*.py"):
    src = path.read_text()
    for token in banned:
        assert token not in src, (path.name, token)
print("  [ok] no system clock is reachable in the installed package")

# 9. dependency isolation
for forbidden in ("ugence_agent_value_readiness", "governed_value", "ugence_governed_value",
                  "risk_authority", "ugence_decision_authority", "agent_runtime",
                  "governance_providers", "ai_hiring", "pydantic", "numpy", "fastapi",
                  "cryptography", "nacl"):
    assert importlib.util.find_spec(forbidden) is None, f"{forbidden} is importable"
print("  [ok] no readiness, governed-value, authority, runtime or third-party package is importable")

print("ALL DISTRIBUTION CHECKS PASSED")
'''


def run(cmd, **kw):
    result = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if result.returncode != 0:
        sys.stderr.write(result.stdout + result.stderr)
        raise SystemExit(f"FAILED: {' '.join(str(c) for c in cmd)}")
    return result


def main() -> int:
    print(f"UVI Policy Authority distribution verification ({PKG.name})")
    workdir = Path(tempfile.mkdtemp(prefix="uvi-policy-authority-verify-"))
    try:
        links = workdir / "wheels"
        links.mkdir()

        print("[1/4] Building wheels")
        for name, source in SOURCES.items():
            out = workdir / f"build-{name}"
            run([sys.executable, "-m", "build", "--wheel", "--outdir", str(out), str(source)])
            for wheel in out.glob("*.whl"):
                shutil.copy(wheel, links / wheel.name)
                print(f"      built {wheel.name}")

        authority_wheel = next(links.glob("ugence_uvi_policy_authority-*.whl"))
        with zipfile.ZipFile(authority_wheel) as zf:
            names = zf.namelist()
        assert any(n.endswith("ugence_uvi_policy_authority/py.typed") for n in names), (
            "py.typed missing from the wheel"
        )
        print(f"      wheel ships py.typed ({len(names)} entries)")

        print("[2/4] Creating an isolated venv (no system site packages)")
        env_dir = workdir / "venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(env_dir)
        py = env_dir / "bin" / "python"
        if not py.exists():  # pragma: no cover - Windows
            py = env_dir / "Scripts" / "python.exe"

        print("[3/4] Installing --no-index from local wheels only")
        run(
            [
                str(py), "-m", "pip", "install", "--no-index",
                "--find-links", str(links), "ugence-uvi-policy-authority",
            ]
        )

        print("[4/4] Running in-environment conformance checks")
        # Run from the temp dir, never the repo root: with ``-c`` the current
        # directory joins sys.path, which would otherwise make top-level
        # monorepo directories importable and hide a real isolation failure.
        result = run([str(py), "-c", _CHECK], cwd=str(workdir))
        print(result.stdout.rstrip())
        return 0
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
