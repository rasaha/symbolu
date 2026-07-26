#!/usr/bin/env python3
"""Reproducible proof the pilot installs and runs in an isolated five-wheel env (Task 118).

Builds all five distributions, installs only the pilot (+ its four frozen deps and
declared third-party deps) into a fresh venv with no monorepo path, then proves:

  * the pilot imports and all providers register;
  * the compatibility manifest validates;
  * the packaged dataset loads (90 scenarios);
  * the deterministic pilot executes and all safety invariants pass;
  * failure injection is fail-safe and providers stay independent;
  * reports are generated;
  * no domain source tree / monorepo path is present, no duplicate DGM/framework/
    provider source is bundled.

Run:  python packaging/verify_enterprise_pilot_distribution.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import venv
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DISTS = {
    "decision-governance": REPO / "packaging" / "decision-governance",
    "dgm-provider-framework": REPO / "packaging" / "dgm-provider-framework",
    "dgm-actiongate-provider": REPO / "packaging" / "dgm-actiongate-provider",
    "dgm-tap-provider": REPO / "packaging" / "dgm-tap-provider",
    "dgm-enterprise-validation-pilot": REPO / "packaging" / "dgm-enterprise-validation-pilot",
}

_CHECK = r'''
import importlib.util, pathlib, sys, tempfile
import decision_governance, governance_providers, actiongate_provider, tap_provider
import enterprise_validation_pilot as pilot
assert pilot.__version__ == "0.1.0", pilot.__version__
assert "site-packages" in pilot.__file__, pilot.__file__
missing = [p for p in ("ai_hiring", "domains", "applications")
           if importlib.util.find_spec(p) is not None]
assert not missing, missing

from enterprise_validation_pilot.composition.manifest import validate_manifest
assert validate_manifest().ok

from enterprise_validation_pilot.schemas.dataset import Dataset
dspath = pathlib.Path(pilot.__file__).parent / "datasets" / "enterprise_pilot_v1.json"
ds = Dataset.from_json(dspath.read_text())
assert len(ds.scenarios) == 90, len(ds.scenarios)

from enterprise_validation_pilot.pilot import run_pilot
res = run_pilot(ds)
assert res.overall_pass, "pilot did not pass overall"
assert res.scenarios_passed == 90, res.scenarios_passed
assert res.invariants_passed, "invariants failed"
assert res.failure_injection_passed, "failure injection not fail-safe"
assert res.independence_passed, "provider independence violated"

from enterprise_validation_pilot.reports.generate import write_all
written = write_all(res, pathlib.Path(tempfile.mkdtemp()))
assert len(written) == 6, written
print("ISOLATED PILOT VERIFICATION OK digest=" + res.substantive_digest[:16])
'''


def _run(cmd, **kw):
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    return subprocess.run(cmd, check=True, **kw)


def _latest(path: Path, pattern: str) -> Path:
    files = sorted(path.glob(pattern))
    if not files:
        raise FileNotFoundError(f"no {pattern} in {path}")
    return files[-1]


def _kernel_members(wheel: Path) -> set[str]:
    with zipfile.ZipFile(wheel) as z:
        return {n for n in z.namelist()
                if n.startswith("decision_governance/") and n.endswith(".py")}


def main() -> int:
    findlinks = REPO / "packaging" / "_dist_wheels"
    if findlinks.exists():
        shutil.rmtree(findlinks)
    findlinks.mkdir()

    print("[1/4] build all five independent wheels")
    for name, path in DISTS.items():
        _run([sys.executable, "-m", "build", "--wheel", str(path)])
        wheel = _latest(path / "dist", "*.whl")
        shutil.copy(wheel, findlinks / wheel.name)
        print(f"      built {name}: {wheel.name}")

    print("[2/4] assert the pilot wheel bundles no frozen source")
    pilot_wheel = _latest(findlinks, "dgm_enterprise_validation_pilot-*.whl")
    assert not _kernel_members(pilot_wheel), "pilot wheel bundles kernel source!"
    with zipfile.ZipFile(pilot_wheel) as z:
        names = z.namelist()
        assert any(n.endswith("enterprise_pilot_v1.json") for n in names), "dataset not packaged"
        for pkg in ("governance_providers/", "tap_provider/", "actiongate_provider/"):
            assert not any(n.startswith(pkg) for n in names), f"pilot bundles {pkg}"
    print("      pilot wheel owns only its own source + dataset")

    print("[3/4] create isolated venv and install ONLY the pilot (+deps via find-links)")
    with tempfile.TemporaryDirectory() as td:
        env = Path(td) / "venv"
        venv.create(env, with_pip=True, clear=True, system_site_packages=False)
        py = env / "bin" / "python"
        _run([str(py), "-m", "pip", "install", "--quiet",
              "--find-links", str(findlinks), "dgm-enterprise-validation-pilot"])

        print("[4/4] run the isolated pilot proof (cwd has no monorepo source)")
        _run([str(py), "-c", _CHECK], cwd=str(td))

    shutil.rmtree(findlinks, ignore_errors=True)
    print("\nISOLATED FIVE-WHEEL PILOT DISTRIBUTION VERIFIED ✔")
    return 0


if __name__ == "__main__":
    sys.exit(main())
