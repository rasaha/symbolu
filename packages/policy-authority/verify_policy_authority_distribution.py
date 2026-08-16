#!/usr/bin/env python3
"""Reproducible proof that the shared Ugence Policy Authority installs and operates
from a built wheel, with only the UVI policy-contracts leaf as a cross-package
dependency and no readiness, governed-value, risk-authority or other foreign
package on the path.

Builds ``ugence-policy-authority`` and its dependency chain
(``ugence-uvi-policy-contracts`` → ``ugence-governance-contracts``) into a local
find-links directory, installs the first (pip resolves the rest) into a fresh
venv with no system site packages and no monorepo path (``--no-index`` — all
wheels are local, zero third-party deps), then proves inside that env:

  * ``ugence_policy_authority`` imports from site-packages and ships py.typed;
  * the **old** ``ugence_uvi_policy_authority`` namespace is NOT importable, and
    exactly one top-level namespace shipped;
  * the version, authority protocol id and canonicalization version are exact;
  * the generic core imports no policy family and branches on none;
  * a second, synthetic policy family works with no core change;
  * all five merged UVI families issue, resolve and verify end to end;
  * the shipped default approval verifier denies; no signature is produced and
    no registry mutation occurs when approval fails; self-approval is refused;
  * a non-empty unstructured ``supersedes_ref`` is rejected before any
    collaborator runs, while empty/whitespace-only issues normally;
  * NFD input is rejected and naive datetimes are refused at the helper;
  * revocation is mandatory-signed, entitlement-authorized, and re-verified at
    resolution — a tampered revocation fails closed as an integrity error;
  * trust anchors are immutable against caller-map mutation;
  * historical resolution is disclosed and never implies current validity;
  * no wall clock, and no tests/fixtures/probes/private keys ship in the wheel.

Run:  python packages/policy-authority/verify_policy_authority_distribution.py
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
REPO = PKG.parents[1]

SOURCES = {
    "ugence_policy_authority": PKG,
    "ugence_uvi_policy_contracts": REPO / "packages" / "uvi-policy-contracts",
    "ugence_governance_contracts": REPO / "packages" / "governance-contracts",
}

_CHECK = r'''
import ast, dataclasses, hashlib, importlib.util, pathlib, sys, unicodedata
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Optional

import ugence_policy_authority as pa
assert pa.__version__ == "0.1.0", pa.__version__
assert "site-packages" in pa.__file__, pa.__file__
assert not any("/symbolu" in p for p in sys.path), sys.path
ROOT = pathlib.Path(pa.__file__).resolve().parent
assert (ROOT / "py.typed").is_file(), "py.typed not installed"

# The retired namespace must be gone, and only one namespace shipped.
assert importlib.util.find_spec("ugence_uvi_policy_authority") is None, "old namespace importable"
site = ROOT.parent
shipped = {p.name for p in site.iterdir() if p.is_dir() and p.name.startswith("ugence_")}
assert "ugence_uvi_policy_authority" not in shipped, shipped
print("  [ok] one namespace ships; the retired UVI-owned namespace is absent")

from ugence_policy_authority.api import (
    AUTHORITY_PROTOCOL, AUTHORITY_PROTOCOL_ID, AUTHORITY_PROTOCOL_VERSION,
    CANONICALIZATION_VERSION, SUPERSESSION_REFERENCE_UNSUPPORTED,
    AdapterRegistry, ApprovalEvidenceRef, ApprovalVerification, ApprovalVerificationStatus,
    DenyAllApprovalVerifier, DenyAllSignatureVerifier, Ed25519PolicySigner,
    HistoricalResolutionRule, InMemoryPolicyRegistry, IssuedPolicyRecord, KeyEntitlement,
    PolicyApprovalError, PolicyArtifactDescriptor, PolicyAuthorityError,
    PolicyCanonicalizationError, PolicyCoordinate, PolicyDigestMismatchError, PolicyKeyRing,
    PolicyRegistryConflictError, PolicyResolutionReason, PolicyResolutionStatus,
    PolicyRevocationError, PolicyRevocationReasonCode, SigningKey,
    UnsupportedPolicyArtifactError, UnsupportedSupersessionError, canonical_bytes,
    default_uvi_adapters, issue_policy, resolve_policy, revoke_policy, uvi_coordinate,
)
assert AUTHORITY_PROTOCOL == "ugence.policy-authority"
assert AUTHORITY_PROTOCOL_VERSION == "v0.1"
assert AUTHORITY_PROTOCOL_ID == "ugence.policy-authority/v0.1"
assert CANONICALIZATION_VERSION == "ugence.policy-authority/canonicalization/v1"
print("  [ok] version 0.1.0, protocol ugence.policy-authority/v0.1, canonicalization v1")

from ugence_uvi_policy_contracts.api import (
    ComponentEvidenceRequirement, DomainPolicy, GeographyPolicy, IntendedOutcomePolicy,
    PolicyArtifactMetadata, PolicyFamily, PolicyLifecycleState, PolicyScope,
    ReadinessPolicy, ValuationPolicy, ValueComponent,
)

T_FROM = datetime(2026, 1, 1, tzinfo=timezone.utc)
T_MID  = datetime(2026, 6, 1, tzinfo=timezone.utc)
T_TO   = datetime(2027, 1, 1, tzinfo=timezone.utc)
SEC = timedelta(seconds=1)
ISSUER, REVOKER, APPROVER = "ugence.policy-authority", "ugence.pa.revocation", "ugence.gov.board"
ADAPTERS = default_uvi_adapters()

BODIES = {
    PolicyFamily.GEOGRAPHY: (GeographyPolicy, dict(jurisdiction="US-CA", reporting_currency="USD", functional_currency="USD")),
    PolicyFamily.DOMAIN: (DomainPolicy, dict(governed_outcome_unit="resolved_ticket")),
    PolicyFamily.INTENDED_OUTCOME: (IntendedOutcomePolicy, dict(target_outcome="o", task_definition="t")),
    PolicyFamily.VALUATION: (ValuationPolicy, dict(required_components=(ComponentEvidenceRequirement(component=ValueComponent.GROSS_BENEFIT),))),
    PolicyFamily.READINESS: (ReadinessPolicy, dict()),
}

def build(family=PolicyFamily.DOMAIN, **kw):
    cls, body = BODIES[family]
    def meta(d):
        base = dict(policy_id="pol-1", policy_family=family, version="1.0.0", content_digest=d,
                    lifecycle_state=PolicyLifecycleState.APPROVED_ACTIVE,
                    effective_from=T_FROM, effective_to=T_TO)
        base.update(kw)
        return PolicyArtifactMetadata(**base)
    draft = cls(metadata=meta("0" * 64), **body)
    return cls(metadata=meta(ADAPTERS.describe(draft).body_digest()), **body)

class V:
    def __init__(self, status=ApprovalVerificationStatus.APPROVED, approver=APPROVER):
        self.status, self.approver, self.calls = status, approver, 0
    def verify_approval(self, *, coordinate, policy_body_digest, approval, as_of):
        self.calls += 1
        return ApprovalVerification(
            verified=self.status is ApprovalVerificationStatus.APPROVED, status=self.status,
            coordinate=coordinate, policy_body_digest=policy_body_digest,
            approving_authority_id=self.approver, approval_ref=approval.approval_ref,
            approval_digest=approval.approval_digest, verified_at=as_of)

class CountingSigner:
    def __init__(self, inner): self.inner, self.calls = inner, 0
    authority_id = property(lambda s: s.inner.authority_id)
    key_id = property(lambda s: s.inner.key_id)
    signature_alg = property(lambda s: s.inner.signature_alg)
    def sign(self, p):
        self.calls += 1
        return self.inner.sign(p)

EV = ApprovalEvidenceRef(approval_ref="A-1", approval_digest=hashlib.sha256(b"a").hexdigest(),
                         approving_authority_id=APPROVER)

def wiring():
    s = Ed25519PolicySigner(authority_id=ISSUER, key_id="k-i", signing_key=SigningKey.from_seed(b"\x01" * 32))
    r = Ed25519PolicySigner(authority_id=REVOKER, key_id="k-r", signing_key=SigningKey.from_seed(b"\x07" * 32))
    ring = PolicyKeyRing([s.verification_key(entitlements=(KeyEntitlement.ISSUE_POLICY,)),
                          r.verification_key(entitlements=(KeyEntitlement.REVOKE_POLICY,))])
    return s, r, ring, InMemoryPolicyRegistry()

def issue(policy, s, reg, v=None, **kw):
    return issue_policy(policy=policy, record_id=kw.pop("record_id", "r"), approval=kw.pop("approval", EV),
                        approval_verifier=v or V(), signer=s, registry=reg,
                        adapters=kw.pop("adapters", ADAPTERS), issued_at=kw.pop("issued_at", T_MID), **kw)

def resolve(ref, reg, ring, **kw):
    return resolve_policy(reference=ref, expected_reference_tenant_id=kw.pop("tenant", ""),
                          as_of=kw.pop("as_of", T_MID), registry=reg, signature_verifier=ring,
                          adapters=kw.pop("adapters", ADAPTERS), **kw)

# 1. core/adapter boundary
BANNED = {"GeographyPolicy","DomainPolicy","IntendedOutcomePolicy","ValuationPolicy","ReadinessPolicy","PolicyFamily","PolicyReference"}
for path in (ROOT / "core").rglob("*.py"):
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "uvi_policy_contracts" not in node.module, path
        if isinstance(node, ast.Name):
            assert node.id not in BANNED, (path, node.id)
        if isinstance(node, ast.Attribute):
            assert node.attr not in BANNED, (path, node.attr)
importers = {p.name for p in ROOT.rglob("*.py") if "ugence_uvi_policy_contracts" in p.read_text()}
assert importers == {"uvi.py"}, importers
print("  [ok] the generic core imports no policy family and branches on none")

# 2. all five UVI families
for fam in BODIES:
    p = build(fam)
    s, r, ring, reg = wiring()
    rec = issue(p, s, reg)
    assert len(rec.signature) == 64
    res = resolve(p.reference, reg, ring)
    assert res.status is PolicyResolutionStatus.RESOLVED and res.policy == p, (fam, res.reason)
print("  [ok] all five merged UVI families issue, resolve and verify")

# 3. a second synthetic family, with no core change
@dataclass(frozen=True)
class RosterPolicy:
    rid: str; rev: str; declared: str; state: str = "LIVE"; opens: Optional[datetime] = None
class RosterAdapter:
    adapter_id = "example.roster/v1"
    def recognizes(self, a): return type(a) is RosterPolicy
    def coordinate_for(self, r): return None
    def describe(self, a):
        from ugence_policy_authority.core.canonical import to_canonical_obj
        proj = {k: v for k, v in to_canonical_obj(a).items() if k != "declared"}
        return PolicyArtifactDescriptor(
            adapter_id=self.adapter_id, policy_type="RosterPolicy",
            coordinate=PolicyCoordinate(policy_family="ROSTER", policy_id=a.rid, version=a.rev,
                                        content_digest=a.declared, scope="GLOBAL"),
            declared_content_digest=a.declared, canonical_projection=proj,
            lifecycle_label=a.state, lifecycle_is_active=a.state == "LIVE", effective_from=a.opens)
_ra = RosterAdapter()
_draft = RosterPolicy(rid="x", rev="1", declared="0" * 64, opens=T_FROM)
roster = RosterPolicy(rid="x", rev="1", declared=_ra.describe(_draft).body_digest(), opens=T_FROM)
s, r, ring, reg = wiring()
both = AdapterRegistry((ADAPTERS.adapters[0], _ra))
rec = issue(roster, s, reg, adapters=both)
assert rec.adapter_id == "example.roster/v1"
coord = _ra.describe(roster).coordinate
assert resolve(coord, reg, ring, adapters=both).status is PolicyResolutionStatus.RESOLVED
print("  [ok] a second synthetic policy family works with no core change")

# 4. approval fails closed; no signature, no mutation, no self-approval
s, r, ring, reg = wiring()
counting = CountingSigner(s)
p = build()
try:
    issue_policy(policy=p, record_id="r", approval=EV, approval_verifier=DenyAllApprovalVerifier(),
                 signer=counting, registry=reg, adapters=ADAPTERS, issued_at=T_MID)
    raise SystemExit("FAIL: the deny-all verifier permitted issuance")
except PolicyApprovalError: pass
assert counting.calls == 0 and len(reg._issued) == 0
try:
    issue(p, counting, reg, v=V(approver=ISSUER),
          approval=ApprovalEvidenceRef(approval_ref="A", approval_digest=hashlib.sha256(b"a").hexdigest(),
                                       approving_authority_id=ISSUER))
    raise SystemExit("FAIL: the authority approved its own policy")
except PolicyApprovalError: pass
assert counting.calls == 0
print("  [ok] approval fails closed; no signature, no mutation, no self-approval")

# 5. supersession
s, r, ring, reg = wiring()
v, counting = V(), CountingSigner(s)
for ref in ("p@1", "prior", "  padded  ", "latest"):
    try:
        issue_policy(policy=build(supersedes_ref=ref), record_id="r", approval=EV,
                     approval_verifier=v, signer=counting, registry=reg, adapters=ADAPTERS, issued_at=T_MID)
        raise SystemExit(f"FAIL: supersedes_ref {ref!r} was accepted")
    except UnsupportedSupersessionError as e:
        assert SUPERSESSION_REFERENCE_UNSUPPORTED in str(e)
assert v.calls == 0 and counting.calls == 0 and len(reg._issued) == 0
for ref in ("", "   ", "\t\n"):
    s2, _, ring2, reg2 = wiring()
    p2 = build(supersedes_ref=ref)
    issue(p2, s2, reg2)
    assert resolve(p2.reference, reg2, ring2).resolved, repr(ref)
print("  [ok] non-empty unstructured supersession rejected before any collaborator; empty issues")

# 6. digest, Unicode, naive datetime
s, r, ring, reg = wiring()
p = build()
forged = replace(p, metadata=replace(p.metadata, content_digest="a" * 64))
try:
    issue(forged, s, reg); raise SystemExit("FAIL: arbitrary digest accepted")
except PolicyDigestMismatchError: pass
try:
    issue(object(), s, reg); raise SystemExit("FAIL: unsupported artifact issued")
except UnsupportedPolicyArtifactError: pass
nfd = unicodedata.normalize("NFD", "café")
for payload in ({"j": nfd}, {"a": [nfd]}, {nfd: "v"}):
    try:
        canonical_bytes(payload); raise SystemExit("FAIL: NFD accepted")
    except PolicyCanonicalizationError: pass
assert canonical_bytes({"j": "café"})
for bad in (datetime(2026, 6, 1), {"w": datetime(2026, 6, 1)}):
    try:
        canonical_bytes(bad); raise SystemExit("FAIL: naive datetime accepted")
    except PolicyCanonicalizationError: pass
print("  [ok] arbitrary digests, unsupported artifacts, NFD and naive datetimes are refused")

# 7. signature / key failures
s, r, ring, reg = wiring()
rec = issue(p, s, reg)
object.__setattr__(rec, "signature", b"\x00" * 64)
assert resolve(p.reference, reg, ring).reason is PolicyResolutionReason.SIGNATURE_INVALID
object.__setattr__(rec, "signature", s.sign(rec.signing_payload()))
assert resolve(p.reference, reg, PolicyKeyRing()).reason is PolicyResolutionReason.KEY_UNKNOWN
assert resolve(p.reference, reg, ring.with_key(ring.resolve("k-i").revoke())).reason is PolicyResolutionReason.KEY_REVOKED
assert resolve(p.reference, reg, DenyAllSignatureVerifier()).reason is PolicyResolutionReason.KEY_UNKNOWN
print("  [ok] tampered signature, unknown key, revoked key and no-verifier all fail closed")

# 8. effective period, tenancy
def reason(as_of, tenant=""):
    return resolve(p.reference, reg, ring, as_of=as_of, tenant=tenant).reason
assert reason(T_FROM) is PolicyResolutionReason.RESOLVED
assert reason(T_FROM - SEC) is PolicyResolutionReason.NOT_YET_EFFECTIVE
assert reason(T_TO - SEC) is PolicyResolutionReason.RESOLVED
assert reason(T_TO) is PolicyResolutionReason.EXPIRED
assert reason(T_MID, "other") is PolicyResolutionReason.TENANT_SCOPE_MISMATCH
print("  [ok] effective_from inclusive, effective_to exclusive, cross-tenant denied")

# 9. append-only registry, signed+authorized revocation, historical disclosure
try:
    issue(p, s, reg, record_id="other"); raise SystemExit("FAIL: a stored version was overwritten")
except PolicyRegistryConflictError: pass
s2, r2, ring2, reg2 = wiring()
p2 = build(effective_to=None)
issue(p2, s2, reg2)
def revoke(**kw):
    params = dict(reference=p2.reference, revocation_id="rv-1",
                  reason_code=PolicyRevocationReasonCode.CONTENT_DEFECT, registry=reg2,
                  adapters=ADAPTERS, signer=r2, signature_verifier=ring2, revoked_at=T_MID)
    params.update(kw); return revoke_policy(**params)
for bad in (dict(signer=None), dict(signature_verifier=None), dict(signer=s2)):
    try:
        revoke(**bad); raise SystemExit(f"FAIL: an invalid revocation was accepted: {bad}")
    except (PolicyAuthorityError,): pass
assert reg2.revocations_for(uvi_coordinate(p2.reference)) == ()
revocation = revoke()
assert resolve(p2.reference, reg2, ring2).reason is PolicyResolutionReason.REVOKED
assert resolve(p2.reference, reg2, ring2, as_of=T_MID - SEC).reason is PolicyResolutionReason.REVOKED
hist = resolve(p2.reference, reg2, ring2, as_of=T_MID - SEC,
               historical_resolution=HistoricalResolutionRule.ALLOW_BEFORE_REVOCATION)
assert hist.status is PolicyResolutionStatus.RESOLVED and hist.historical is True
assert hist.implies_current_validity is False and hist.as_of == T_MID - SEC
reg2._revocations[uvi_coordinate(p2.reference)] = replace(revocation, signature=b"\x00" * 64)
bad = resolve(p2.reference, reg2, ring2, as_of=T_FROM)
assert bad.reason is PolicyResolutionReason.REVOCATION_INTEGRITY_INVALID and bad.policy is None
print("  [ok] append-only registry; revocation signed, authorized, re-verified; history disclosed")

# 10. immutable trust anchors
caller = {"k-i": s.verification_key()}
ring3 = PolicyKeyRing(caller)
attacker = Ed25519PolicySigner(authority_id="x", key_id="atk", signing_key=SigningKey.from_seed(b"\x41" * 32))
caller["atk"] = attacker.verification_key(); caller.clear()
assert ring3.resolve("atk") is None and ring3.resolve("k-i") is not None
for attempt in (lambda: ring3.keys.__setitem__("atk", attacker.verification_key()),
                lambda: setattr(ring3, "_keys", {})):
    try:
        attempt(); raise SystemExit("FAIL: a trust-anchor mutation succeeded")
    except (TypeError, AttributeError): pass
print("  [ok] trust anchors are immutable against caller-map mutation")

# 11. no wall clock, no test material shipped
for path in ROOT.rglob("*.py"):
    src = path.read_text()
    for token in ("datetime.now(", "datetime.utcnow(", "time.time(", ".utcnow()", "uuid4(", "os.environ"):
        assert token not in src, (path.name, token)
assert not list(ROOT.rglob("test_*.py")) and not list(ROOT.rglob("*_fixtures.py"))
assert not list(ROOT.rglob("adversarial_probes.py")) and not list(ROOT.rglob("conftest.py"))
print("  [ok] no wall clock, and no tests/fixtures/probes ship in the wheel")

# 12. dependency isolation
for forbidden in ("ugence_agent_value_readiness", "governed_value", "ugence_governed_value",
                  "risk_authority", "ugence_decision_authority", "agent_runtime",
                  "governance_providers", "ai_hiring", "pydantic", "numpy", "fastapi",
                  "cryptography", "nacl"):
    assert importlib.util.find_spec(forbidden) is None, f"{forbidden} is importable"
print("  [ok] no readiness, governed-value, authority, runtime or third-party package importable")

print("ALL DISTRIBUTION CHECKS PASSED")
'''


def run(cmd, **kw):
    result = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if result.returncode != 0:
        sys.stderr.write(result.stdout + result.stderr)
        raise SystemExit(f"FAILED: {' '.join(str(c) for c in cmd)}")
    return result


def main() -> int:
    print(f"Shared Ugence Policy Authority distribution verification ({PKG.name})")
    workdir = Path(tempfile.mkdtemp(prefix="policy-authority-verify-"))
    try:
        links = workdir / "wheels"
        links.mkdir()

        print("[1/4] Building wheels")
        # Stale in-tree build state (notably a *.egg-info left by an earlier,
        # differently-named build) can leak retired paths into a fresh wheel.
        # Clear it first so what is verified is what a clean checkout produces.
        for source in SOURCES.values():
            for stale in list((source / "src").glob("*.egg-info")) + [
                source / "build",
                source / "dist",
            ]:
                shutil.rmtree(stale, ignore_errors=True)

        for name, source in SOURCES.items():
            out = workdir / f"build-{name}"
            run([sys.executable, "-m", "build", "--wheel", "--outdir", str(out), str(source)])
            for wheel in out.glob("*.whl"):
                shutil.copy(wheel, links / wheel.name)
                print(f"      built {wheel.name}")

        authority_wheel = next(links.glob("ugence_policy_authority-*.whl"))
        with zipfile.ZipFile(authority_wheel) as zf:
            names = zf.namelist()
        assert any(n.endswith("ugence_policy_authority/py.typed") for n in names), (
            "py.typed missing from the wheel"
        )
        assert not any("ugence_uvi_policy_authority" in n for n in names), (
            "the retired namespace is present in the wheel"
        )
        top_level = {n.split("/")[0] for n in names if not n.endswith(".dist-info") and "/" in n}
        top_level = {t for t in top_level if not t.endswith(".dist-info")}
        assert top_level == {"ugence_policy_authority"}, top_level
        for banned in ("test_", "conftest", "_fixtures", "adversarial_probes"):
            assert not any(banned in n for n in names), (banned, [n for n in names if banned in n])
        print(f"      wheel ships one namespace + py.typed, no test material ({len(names)} entries)")

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
                "--find-links", str(links), "ugence-policy-authority",
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
