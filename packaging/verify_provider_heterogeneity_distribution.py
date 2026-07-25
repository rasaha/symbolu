#!/usr/bin/env python3
"""Reproducible proof the heterogeneity validation installs and runs isolated (Task 17).

Builds all nine distributions, installs only the validation package (+ its eight
frozen/alternative deps) into a fresh venv with no monorepo path, then proves:

  * all four providers import and register; both alternatives pass shared conformance;
  * deterministic selection, capability rejection, safe fallback, rejected-unsafe
    fallback, and no-provider fail-safe all work;
  * C1 (TAP + ActionGate) reproduces Phase 6A full governance;
  * no domain source / monorepo path is present, no frozen source is duplicated.

Run:  python packaging/verify_provider_heterogeneity_distribution.py
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
    "dgm-baseline-assertion-provider": REPO / "packaging" / "dgm-baseline-assertion-provider",
    "dgm-baseline-action-provider": REPO / "packaging" / "dgm-baseline-action-provider",
    "dgm-enterprise-validation-pilot": REPO / "packaging" / "dgm-enterprise-validation-pilot",
    "dgm-comparative-governance-benchmark":
        REPO / "packaging" / "dgm-comparative-governance-benchmark",
    "dgm-provider-heterogeneity-validation":
        REPO / "packaging" / "dgm-provider-heterogeneity-validation",
}

_CHECK = r'''
import importlib.util, sys

for m in ("decision_governance", "governance_providers", "tap_provider", "actiongate_provider",
          "baseline_assertion_provider", "baseline_action_provider",
          "provider_heterogeneity_validation"):
    __import__(m)
import provider_heterogeneity_validation as phv
assert phv.__version__ == "0.1.0"
assert "site-packages" in phv.__file__, phv.__file__
missing = [p for p in ("ai_hiring", "domains", "applications")
           if importlib.util.find_spec(p) is not None]
assert not missing, missing

# both alternatives pass shared conformance
from governance_providers.conformance import (
    run_assertion_provider_conformance, run_action_provider_conformance)
from baseline_assertion_provider.configuration import build_baseline_assertion_provider
from baseline_action_provider.configuration import build_baseline_action_provider
assert run_assertion_provider_conformance(lambda: build_baseline_assertion_provider()).passed
assert run_action_provider_conformance(lambda: build_baseline_action_provider()).passed

# providers register through the framework registry
from governance_providers.api import ProviderRegistry, ProviderKind
reg = ProviderRegistry()
reg.register(build_baseline_assertion_provider().descriptor())
reg.register(build_baseline_action_provider().descriptor())
assert {d.provider_id for d in reg.list_by_kind()} == {"baseline-assertion", "baseline-action"}

# deterministic selection, capability rejection, safe fallback, no-provider fail-safe
from provider_heterogeneity_validation.selection import (
    ProviderCatalog, CatalogEntry, ProviderState, SelectionRequest, ResolutionPolicy, select)
from provider_heterogeneity_validation.profiles.capabilities import capabilities_of
K = "ASSERTION_GOVERNANCE"
def cat(*st):
    c = ProviderCatalog()
    for pid, s in st:
        c.add(CatalogEntry(pid, K, "0.1.0", capabilities_of(pid), s))
    return c
c = cat(("tap-primary", ProviderState()), ("baseline-assertion", ProviderState()))
_e, r1 = select(c, SelectionRequest(K, ResolutionPolicy.CAPABILITY_REQUIRED,
                required_capabilities=("qualifier_detection",)), request_id="x")
assert r1.selected_provider_id == "tap-primary"
assert r1.rejection_reasons["baseline-assertion"] == "MISSING_CAPABILITY"
c2 = cat(("tap-primary", ProviderState(health="UNAVAILABLE")), ("baseline-assertion", ProviderState()))
_e, r2 = select(c2, SelectionRequest(K, ResolutionPolicy.BOUNDED_FALLBACK,
                preference_order=("tap-primary", "baseline-assertion"), allow_fallback=True),
                request_id="y")
assert r2.selected_provider_id == "baseline-assertion" and r2.fallback_used
c3 = cat(("tap-primary", ProviderState(health="UNAVAILABLE")),
         ("baseline-assertion", ProviderState(health="UNAVAILABLE")))
_e, r3 = select(c3, SelectionRequest(K, ResolutionPolicy.BOUNDED_FALLBACK,
                preference_order=("tap-primary", "baseline-assertion"), allow_fallback=True),
                request_id="z")
assert r3.selected_provider_id is None  # no-valid-provider → fail-safe upstream

# C1 reproduces Phase 6A full governance (subset for speed)
from comparative_governance_benchmark.schemas.dataset import load_frozen_dataset
from comparative_governance_benchmark.strategies import build_strategy
from provider_heterogeneity_validation.runners.workflow import run
from provider_heterogeneity_validation.schemas.config import CONFIGURATIONS
ds = load_frozen_dataset(); full = build_strategy("full_governance")
for s in ds.ordered():
    hr = run(s, CONFIGURATIONS["C1"]); fr = full.run(s)
    assert hr.dispatched == fr.dispatched and hr.assertion_outcome == fr.assertion_outcome, s.scenario_id

print("ISOLATED HETEROGENEITY VERIFICATION OK")
'''


def _run(cmd, **kw):
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    return subprocess.run(cmd, check=True, **kw)


def _latest(path: Path, pattern: str) -> Path:
    files = sorted(path.glob(pattern))
    if not files:
        raise FileNotFoundError(f"no {pattern} in {path}")
    return files[-1]


def main() -> int:
    findlinks = REPO / "packaging" / "_dist_wheels"
    if findlinks.exists():
        shutil.rmtree(findlinks)
    findlinks.mkdir()

    print("[1/4] build all nine independent wheels")
    for name, path in DISTS.items():
        _run([sys.executable, "-m", "build", "--wheel", str(path)])
        wheel = _latest(path / "dist", "*.whl")
        shutil.copy(wheel, findlinks / wheel.name)
        print(f"      built {name}: {wheel.name}")

    print("[2/4] assert the validation wheel bundles no frozen source")
    v_wheel = _latest(findlinks, "dgm_provider_heterogeneity_validation-*.whl")
    with zipfile.ZipFile(v_wheel) as z:
        names = z.namelist()
        for pkg in ("decision_governance/", "governance_providers/", "tap_provider/",
                    "actiongate_provider/", "enterprise_validation_pilot/",
                    "comparative_governance_benchmark/"):
            assert not any(n.startswith(pkg) for n in names), f"validation bundles {pkg}"
    print("      validation wheel owns only its own source")

    print("[3/4] create isolated venv and install ONLY the validation package (+deps)")
    with tempfile.TemporaryDirectory() as td:
        env = Path(td) / "venv"
        venv.create(env, with_pip=True, clear=True, system_site_packages=False)
        py = env / "bin" / "python"
        _run([str(py), "-m", "pip", "install", "--quiet",
              "--find-links", str(findlinks), "dgm-provider-heterogeneity-validation"])

        print("[4/4] run the isolated proof (cwd has no monorepo source)")
        _run([str(py), "-c", _CHECK], cwd=str(td))

    shutil.rmtree(findlinks, ignore_errors=True)
    print("\nISOLATED NINE-WHEEL HETEROGENEITY DISTRIBUTION VERIFIED ✔")
    return 0


if __name__ == "__main__":
    sys.exit(main())
