#!/usr/bin/env python3
"""Reproducible proof that the Governance Contracts install and operate as a
single, self-contained leaf wheel with NO other Ugence package on the path.

Builds ``ugence-governance-contracts`` only, installs it into a fresh virtualenv
with no system site packages and no monorepo path (``--no-index`` — the package
declares zero third-party dependencies), then proves inside that env:

  * ``ugence_governance_contracts`` imports from site-packages;
  * the curated public API resolves;
  * representative request/result contracts construct, serialize, and round-trip;
  * enum values and error failure-classes are intact;
  * NO capability / framework / product / console / research package is importable
    (the contracts layer is a leaf that pulls nothing else in).

Run:  python packages/governance-contracts/verify_governance_contracts_distribution.py
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

_CHECK = r'''
import dataclasses, importlib.util, json, sys

import ugence_governance_contracts as g
assert g.__version__ == "0.3.0", g.__version__
assert g.CONTRACT_VERSION == "1.0.0", g.CONTRACT_VERSION
assert "site-packages" in g.__file__, g.__file__
assert not any("/symbolu" in p or "governance_providers" in p for p in sys.path), sys.path

# PEP 561: the installed leaf advertises typing support to consumers.
import pathlib as _pl
assert (_pl.Path(g.__file__).resolve().parent / "py.typed").is_file(), "py.typed not installed"

# curated API resolves
from ugence_governance_contracts.api import (
    ActionGovernanceRequest, ActionGovernanceResult, ActionGovernanceOutcome,
    AssertionGovernanceRequest, AssertionGovernanceResult, AssertionCoverage,
    ExecutionDispatchRequest, ExecutionObservation, ExecutionBusinessOutcome,
    ProviderKind, ProviderLifecycleState, Provider, FailureClass)

# construct + serialize + round-trip
req = ActionGovernanceRequest(action_type="deploy", actor="a", policy_refs=("p",))
d = dataclasses.asdict(req)
assert d["action_type"] == "deploy" and d["policy_refs"] == ("p",)
rebuilt = ActionGovernanceRequest(action_type=d["action_type"], actor=d["actor"],
                                  policy_refs=tuple(d["policy_refs"]))
assert rebuilt == req
res = AssertionGovernanceResult(coverage=AssertionCoverage.SUPPORTED)
assert res.is_supported is True

# enum / error integrity
assert [m.value for m in ActionGovernanceOutcome] == [
    "AUTHORIZED", "AUTHORIZED_WITH_CONSTRAINTS", "DENIED", "INDETERMINATE", "EXPIRED"]
assert FailureClass.RETRYABLE.value == "RETRYABLE"

# GV-2E-a neutral evidence contracts ship and enforce structure
from ugence_governance_contracts.api import (
    SourceBasis, TransformationMethod, AttestationStatus, AttributionStatus,
    VerificationStatus, EvidenceUsageScope, EvidenceContractError,
    MetricClaim, MetricObservation, EvidenceReference, AssessmentWindow)
from datetime import datetime as _dt, timezone as _tz, timedelta as _td
assert [m.value for m in SourceBasis] == ["REPORTED", "OBSERVED", "SYNTHETIC", "MIXED"]
_c = MetricClaim(claim_id="c", tenant_id="t", subject_id="s", metric_id="m",
                 value="1", governed_unit="u", source_basis=SourceBasis.REPORTED,
                 transformation_method=TransformationMethod.DIRECT)
assert len(_c.canonical_digest()) == 64
# caller label alone cannot elevate: VERIFIED without references is rejected
try:
    MetricClaim(claim_id="c", tenant_id="t", subject_id="s", metric_id="m",
                value="1", governed_unit="u", source_basis=SourceBasis.REPORTED,
                transformation_method=TransformationMethod.DIRECT,
                verification_status=VerificationStatus.VERIFIED)
    raise SystemExit("evidence structural guard did not fire")
except EvidenceContractError:
    pass

# M-3R.3 neutral assessed-system identity ships and enforces structure
from ugence_governance_contracts.api import (
    AssessedSystemBinding, SystemBindingAuthenticityStatus, SystemIdentityContractError)
import dataclasses as _dc, hashlib as _hl
_d = _hl.sha256(b"cfg").hexdigest()
def _bind(**kw):
    base = dict(binding_id="b", tenant_id="t", subject_id="s", context_id="c",
                context_digest=_d, system_id="sys", system_version="1",
                configuration_id="cfg", configuration_digest=_d)
    base.update(kw)
    return AssessedSystemBinding(**base)

# The binding is OWNED here — this is the single canonical definition site.
assert AssessedSystemBinding.__module__ == "ugence_governance_contracts.contracts.system_identity"
assert AssessedSystemBinding.__subclasses__() == [], AssessedSystemBinding.__subclasses__()
assert len(_bind().canonical_digest()) == 64
# Replay across system version / configuration / tenant / subject is detectable.
for _kw in ({"system_version": "2"}, {"configuration_id": "other"},
            {"tenant_id": "other"}, {"subject_id": "other"}):
    assert _bind().canonical_digest() != _bind(**_kw).canonical_digest(), _kw
# Authenticity is a permanently structural PROPERTY, never a settable field.
assert [m.value for m in SystemBindingAuthenticityStatus] == ["STRUCTURAL_UNVERIFIED"]
assert _bind().authenticity_status is SystemBindingAuthenticityStatus.STRUCTURAL_UNVERIFIED
assert _bind().authenticity_verified is False
_names = {f.name for f in _dc.fields(AssessedSystemBinding)}
assert "authenticity_status" not in _names and "authenticity_verified" not in _names
try:
    _bind(authenticity_status="AUTHORITY_VERIFIED")
    raise SystemExit("authenticity is settable from the wheel")
except TypeError:
    pass
# Structural guard fires as the governance-owned error.
try:
    _bind(system_manifest_ref="m")
    raise SystemExit("system-identity structural guard did not fire")
except SystemIdentityContractError:
    pass
# Every field is a platform-neutral primitive -> no cycle is representable.
from datetime import datetime as _dtc
for _f in _dc.fields(AssessedSystemBinding):
    _v = getattr(_bind(), _f.name)
    assert _v is None or isinstance(_v, (str, _dtc)), _f.name
# No SystemManifest was minted.
from ugence_governance_contracts import api as _api
assert not any("systemmanifest" in _n.lower().replace("_", "") for _n in _api.__all__)

# NO unrelated Ugence package importable in this clean env
for mod in ("governance_providers", "decision_governance", "actiongate_provider",
            "tap_provider", "ai_hiring", "ugence_console_api", "platform_freeze",
            "pydantic",
            # The neutral leaf must never require a UVI / readiness / authority
            # / risk package to operate: that absence IS the cycle proof.
            "ugence_agent_value_readiness", "ugence_uvi_policy_contracts",
            "ugence_policy_authority", "risk_authority"):
    assert importlib.util.find_spec(mod) is None, ("unrelated package present: " + mod)

print("ISOLATED SINGLE-WHEEL GOVERNANCE-CONTRACTS VERIFICATION OK")
'''


def _run(cmd, **kw):
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    return subprocess.run(cmd, check=True, **kw)


def _latest(path: Path, pattern: str) -> Path:
    files = sorted(path.glob(pattern))
    if not files:
        raise FileNotFoundError(f"no {pattern} in {path}")
    return files[-1]


def _foreign_members(wheel: Path) -> set[str]:
    with zipfile.ZipFile(wheel) as z:
        tops = {n.split("/", 1)[0] for n in z.namelist() if "/" in n}
    return {t for t in tops if not (t == "ugence_governance_contracts" or t.endswith(".dist-info"))}


def main() -> int:
    findlinks = PKG / "_dist_wheels"
    if findlinks.exists():
        shutil.rmtree(findlinks)
    findlinks.mkdir()

    print("[1/4] build the single governance-contracts wheel")
    _run([sys.executable, "-m", "build", "--wheel", str(PKG), "-o", str(findlinks)])
    wheel = _latest(findlinks, "ugence_governance_contracts-*.whl")
    print(f"      built {wheel.name}")

    print("[2/4] assert the wheel bundles no foreign top-level package + ships py.typed")
    foreign = _foreign_members(wheel)
    assert not foreign, f"wheel bundles foreign packages: {sorted(foreign)}"
    with zipfile.ZipFile(wheel) as z:
        names = set(z.namelist())
    assert "ugence_governance_contracts/py.typed" in names, "wheel is missing py.typed"
    print("      wheel contains only ugence_governance_contracts/ (+ py.typed) + dist-info")

    print("[3/4] create an isolated venv and install ONLY this wheel (--no-index)")
    with tempfile.TemporaryDirectory() as td:
        env = Path(td) / "venv"
        venv.create(env, with_pip=True, clear=True, system_site_packages=False)
        py = env / "bin" / "python"
        _run([str(py), "-m", "pip", "install", "--quiet", "--no-index",
              "--find-links", str(findlinks), "ugence-governance-contracts"])

        print("[4/4] run the isolated proof (cwd has no monorepo source)")
        _run([str(py), "-c", _CHECK], cwd=str(td))

    shutil.rmtree(findlinks, ignore_errors=True)
    print("\nISOLATED SINGLE-WHEEL GOVERNANCE-CONTRACTS DISTRIBUTION VERIFIED ✔")
    return 0


if __name__ == "__main__":
    sys.exit(main())
