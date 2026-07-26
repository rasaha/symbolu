#!/usr/bin/env python3
"""Reproducible proof the benchmark installs and runs in an isolated six-wheel env (Task 18).

Builds all six distributions, installs only the benchmark (+ its five frozen deps
and declared third-party deps) into a fresh venv with no monorepo path, then proves:

  * the benchmark imports and the frozen dataset loads (90 scenarios, expected hash);
  * all four strategies run; Strategy D matches the Phase 5I pilot;
  * benchmark invariants and fairness controls pass;
  * all seven reports generate;
  * no domain source / monorepo path is present, no frozen source is duplicated;
  * simpler strategies do not import prohibited providers.

Run:  python packaging/verify_comparative_benchmark_distribution.py
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
    "dgm-comparative-governance-benchmark":
        REPO / "packaging" / "dgm-comparative-governance-benchmark",
}

_CHECK = r'''
import ast, importlib.util, pathlib, sys, tempfile

import comparative_governance_benchmark as cgb
assert cgb.__version__ == "0.1.0", cgb.__version__
assert "site-packages" in cgb.__file__, cgb.__file__
missing = [p for p in ("ai_hiring", "domains", "applications")
           if importlib.util.find_spec(p) is not None]
assert not missing, missing

from comparative_governance_benchmark.schemas.dataset import load_frozen_dataset, verify_identity
ds = load_frozen_dataset()
ident = verify_identity(ds)
assert ident.ok and ident.scenario_count == 90, ident

from comparative_governance_benchmark.benchmark import run_benchmark
res = run_benchmark(ds)
assert res.overall_pass, "benchmark did not pass overall"
assert res.invariants_passed, "invariants failed"
assert res.fairness_passed, "fairness failed"

from comparative_governance_benchmark.schemas.safety import UNSAFE_OUTCOMES
unsafe = {s: sum(1 for j in res.judgements[s] if j.safety_outcome in UNSAFE_OUTCOMES)
          for s in res.strategy_ids}
assert unsafe["full_governance"] == 0, unsafe
assert unsafe["no_governance"] > unsafe["full_governance"], unsafe

# Strategy D matches the pilot
from enterprise_validation_pilot.runners.workflow import run_scenario as pilot_run
from comparative_governance_benchmark.strategies import build_strategy
full = build_strategy("full_governance")
for s in ds.ordered():
    r, run = full.run(s), pilot_run(s)
    assert r.dispatched == run.dispatched and r.assertion_outcome == run.tap_outcome, s.scenario_id

from comparative_governance_benchmark.reporting.generate import write_all
written = write_all(res, pathlib.Path(tempfile.mkdtemp()))
assert len(written) == 7, written

# simpler strategies do not import prohibited providers (static, on installed source)
sd = pathlib.Path(cgb.__file__).parent / "strategies"
def imports(path):
    mods = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            mods.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            mods.add(node.module)
    return mods
ng = imports(sd / "no_governance.py")
assert not any(m.split(".")[0] in ("tap_provider", "actiongate_provider") for m in ng)
assert not any(m.split(".")[0] == "tap_provider" for m in imports(sd / "action_only.py"))
assert not any(m.split(".")[0] == "actiongate_provider" for m in imports(sd / "assertion_only.py"))

print("ISOLATED BENCHMARK VERIFICATION OK digest=" + res.substantive_digest[:16])
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

    print("[1/4] build all six independent wheels")
    for name, path in DISTS.items():
        _run([sys.executable, "-m", "build", "--wheel", str(path)])
        wheel = _latest(path / "dist", "*.whl")
        shutil.copy(wheel, findlinks / wheel.name)
        print(f"      built {name}: {wheel.name}")

    print("[2/4] assert the benchmark wheel bundles no frozen source")
    bench_wheel = _latest(findlinks, "dgm_comparative_governance_benchmark-*.whl")
    with zipfile.ZipFile(bench_wheel) as z:
        names = z.namelist()
        for pkg in ("decision_governance/", "governance_providers/", "tap_provider/",
                    "actiongate_provider/", "enterprise_validation_pilot/"):
            assert not any(n.startswith(pkg) for n in names), f"benchmark bundles {pkg}"
    print("      benchmark wheel owns only its own source")

    print("[3/4] create isolated venv and install ONLY the benchmark (+deps via find-links)")
    with tempfile.TemporaryDirectory() as td:
        env = Path(td) / "venv"
        venv.create(env, with_pip=True, clear=True, system_site_packages=False)
        py = env / "bin" / "python"
        _run([str(py), "-m", "pip", "install", "--quiet",
              "--find-links", str(findlinks), "dgm-comparative-governance-benchmark"])

        print("[4/4] run the isolated benchmark proof (cwd has no monorepo source)")
        _run([str(py), "-c", _CHECK], cwd=str(td))

    shutil.rmtree(findlinks, ignore_errors=True)
    print("\nISOLATED SIX-WHEEL BENCHMARK DISTRIBUTION VERIFIED ✔")
    return 0


if __name__ == "__main__":
    sys.exit(main())
