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
assert g.__version__ == "0.1.0", g.__version__
assert g.CONTRACT_VERSION == "1.0.0", g.CONTRACT_VERSION
assert "site-packages" in g.__file__, g.__file__
assert not any("/symbolu" in p or "governance_providers" in p for p in sys.path), sys.path

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

# NO unrelated Ugence package importable in this clean env
for mod in ("governance_providers", "decision_governance", "actiongate_provider",
            "tap_provider", "ai_hiring", "ugence_console_api", "platform_freeze",
            "pydantic"):
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

    print("[2/4] assert the wheel bundles no foreign top-level package")
    foreign = _foreign_members(wheel)
    assert not foreign, f"wheel bundles foreign packages: {sorted(foreign)}"
    print("      wheel contains only ugence_governance_contracts/ + dist-info")

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
