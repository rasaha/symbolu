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
assert g.__version__ == "0.3.1", g.__version__
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

# Equal bindings canonicalize identically: aware instants are normalized to UTC
# before serialization, so the offset they were written with cannot fork the
# digest. Naive instants stay rejected; a different instant stays distinct.
_utc = _bind(effective_from=_dtc(2026, 8, 17, 10, 0, tzinfo=_tz.utc))
_ist = _bind(effective_from=_dtc(2026, 8, 17, 15, 30, tzinfo=_tz(_td(hours=5, minutes=30))))
_edt = _bind(effective_from=_dtc(2026, 8, 17, 6, 0, tzinfo=_tz(_td(hours=-4))))
assert _utc == _ist == _edt
assert _utc.canonical_bytes() == _ist.canonical_bytes() == _edt.canonical_bytes()
assert _utc.canonical_digest() == _ist.canonical_digest() == _edt.canonical_digest()
assert _hl.sha256(_utc.canonical_bytes()).hexdigest() == _utc.canonical_digest()
assert _bind(effective_from=_dtc(2026, 8, 17, 10, 0, 1, tzinfo=_tz.utc)).canonical_digest() \
    != _utc.canonical_digest()
try:
    _bind(effective_from=_dtc(2026, 8, 17, 10, 0))
    raise SystemExit("a naive datetime was accepted")
except SystemIdentityContractError:
    pass
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


#: The single generated directory ``python -m build`` leaves inside this package.
#: Named as a literal so the removal target can never widen: it is joined onto
#: the already-resolved package root, never onto a caller string, an environment
#: variable or a repository-root walk.
_BUILD_DIRNAME = "build"


def stale_build_tree() -> Path:
    """The exact package-local generated ``build/`` directory.

    ``PKG`` is ``Path(__file__).resolve().parent`` — this file's own directory,
    already resolved — so the target is pinned to *this* distribution and
    nothing above it. The join itself is deliberately **not** re-resolved: a
    symlink at ``build`` must stay visible as a symlink so it can be refused
    rather than silently followed to whatever it points at.
    """

    return PKG / _BUILD_DIRNAME


def remove_stale_build_tree() -> bool:
    """Delete the package-local ``build/`` tree; return whether one was there.

    ``python -m build`` reuses ``build/lib`` across runs, so a module deleted
    from the source tree — the ADR §20 move of ``AssessedSystemBinding`` is the
    live example — survives there and is silently copied back into the next
    wheel. The freshly built wheel would then carry a module that no longer
    exists in source, or a **second** definition of a contract this package is
    the single canonical owner of.

    Three guards keep the deletion narrow, so this can never become a broad or
    recursive removal:

    * the target is ``<resolved package root>/build`` and is recomputed here,
      never taken from an argument, an environment variable or ``cwd``;
    * it must still be *inside* the package root after resolution, which a
      symlink pointing elsewhere would fail;
    * only a real directory is removed — a symlink is refused rather than
      followed, and a stray file of that name is left alone.

    Source, tests, fixtures and user files are never touched: only the one
    generated directory ``build`` is a candidate, and only when it exists.
    """

    target = stale_build_tree()
    if not target.exists() and not target.is_symlink():
        return False

    if target.parent != PKG or target.name != _BUILD_DIRNAME:
        raise AssertionError(f"refusing to remove a path outside the package: {target}")
    if target.is_symlink():
        raise AssertionError(f"refusing to follow a symlinked build tree: {target}")
    if not target.is_dir():
        raise AssertionError(f"refusing to remove a non-directory build path: {target}")
    if target.resolve().parent != PKG:
        raise AssertionError(f"refusing to remove a path outside the package: {target}")

    shutil.rmtree(target)
    return True


def main() -> int:
    findlinks = PKG / "_dist_wheels"
    if findlinks.exists():
        shutil.rmtree(findlinks)
    findlinks.mkdir()

    print("[1/4] build the single governance-contracts wheel")
    # Immediately before building: a stale package-local ``build/lib`` tree
    # resurrects deleted modules into the wheel, so every wheel is built from
    # the source tree alone.
    if remove_stale_build_tree():
        print(f"      removed stale build tree {stale_build_tree()}")
    assert not stale_build_tree().exists(), "stale build tree survived removal"
    _run([sys.executable, "-m", "build", "--wheel", str(PKG), "-o", str(findlinks)])
    wheel = _latest(findlinks, "ugence_governance_contracts-*.whl")
    print(f"      built {wheel.name}")

    print("[2/4] assert the wheel bundles no foreign top-level package + ships py.typed")
    foreign = _foreign_members(wheel)
    assert not foreign, f"wheel bundles foreign packages: {sorted(foreign)}"
    with zipfile.ZipFile(wheel) as z:
        names = set(z.namelist())
    assert "ugence_governance_contracts/py.typed" in names, "wheel is missing py.typed"

    # The completed wheel is inspected, never the source tree: exactly one
    # module may define the assessed-system identity contracts this package
    # owns, and no module deleted from source may reappear.
    definitions = {"AssessedSystemBinding": [], "SystemBindingAuthenticityStatus": []}
    with zipfile.ZipFile(wheel) as z:
        for member in sorted(names):
            if not member.endswith(".py"):
                continue
            source = z.read(member).decode("utf-8")
            for symbol, sites in definitions.items():
                if f"class {symbol}" in source:
                    sites.append(member)
    for symbol, sites in definitions.items():
        assert sites == ["ugence_governance_contracts/contracts/system_identity.py"], (
            f"the governance wheel defines {symbol} in {sites} — expected exactly one "
            "definition, in contracts/system_identity.py"
        )
    assert "ugence_governance_contracts/contracts/binding.py" not in names, (
        "the governance wheel ships a stale binding module that is not in source"
    )
    print("      wheel contains only ugence_governance_contracts/ (+ py.typed) + dist-info")
    print("      and defines AssessedSystemBinding exactly once, in system_identity.py")

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
