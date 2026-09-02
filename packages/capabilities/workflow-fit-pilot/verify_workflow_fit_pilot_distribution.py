#!/usr/bin/env python3
"""Reproducible proof that ugence-workflow-fit-pilot installs from a built wheel with ONLY
its declared first-party dependencies, starts a real boundary process from the installed
distribution, captures and attests a run, and cannot import the runtime, Context
Minimization or any LLM SDK.

Run:  python packages/capabilities/workflow-fit-pilot/verify_workflow_fit_pilot_distribution.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PACKAGES = [
    REPO / "packages" / "jcs",
    REPO / "packages" / "governance-contracts",
    REPO / "packages" / "uvi-policy-contracts",
    REPO / "packages" / "capabilities" / "reasoning-method-governance",
    REPO / "packages" / "capabilities" / "readiness-comparison",
    REPO / "packages" / "capabilities" / "reasoning-method-advisor",
    REPO / "packages" / "capabilities" / "workflow-fit-pilot",
]
TESTS = REPO / "packages" / "capabilities" / "workflow-fit-pilot" / "tests"
SLICE1_TESTS = REPO / "packages" / "capabilities" / "reasoning-method-governance" / "tests"
SLICE2_TESTS = REPO / "packages" / "capabilities" / "reasoning-method-advisor" / "tests"

PROBE = r'''
import importlib, os, pathlib, sys
m = importlib.import_module("ugence_workflow_fit_pilot")
assert "site-packages" in m.__file__ and (pathlib.Path(m.__file__).parent / "py.typed").exists()
from ugence_workflow_fit_pilot import api
for n in api.__all__: assert hasattr(api, n), n
sys.path[:0] = [%r, %r, %r]
import pilot_fixtures as pf
m = pf.manifest(); adv = pf.advisory(m.plan.task_class)
env = os.environ.copy(); env["PYTHONPATH"] = os.pathsep.join(sys.path[:3]); env["WFP_STUB_MODE"] = "ok"
res = api.run_pilot(m, catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=adv, cases=pf.cases(), executor=pf.FakeExecutor(pf.DEFAULT_CALLS), scorer=pf.KeywordScorer(),
                    identity=pf.IDENTITY, provider_factory="stub_provider:make_provider", now=pf.clock(), boundary_env=env)
assert all(r.complete for r in res.runs) and all(r.attestation is not None for r in res.runs)
assert res.result.authority_resolution_basis == "REQUESTER_ASSERTED" and all(v.verification_status.value == "UNVERIFIED" for v in res.result.evidence_status)
api.validate_lineage(res.states, [m], [res.result])
for forbidden in ("agentic", "ugence_context_minimization", "ugence_agent_value_readiness", "governed_value", "ugence_trusted_evidence_authority", "numpy", "openai", "anthropic"):
    try:
        importlib.import_module(forbidden)
    except ImportError:
        continue
    raise SystemExit(f"{forbidden} is importable in the verification env")
print("VERIFIED: pilot installs from wheels with declared dependencies only, runs a separate boundary process, captures and attests deterministically")
''' % (str(TESTS), str(SLICE1_TESTS), str(SLICE2_TESTS))


def run(cmd, **kw):
    print("+", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True, **kw)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        wheels = tmp / "wheels"
        wheels.mkdir()
        run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "-w", wheels, *PACKAGES])
        env_dir = tmp / "venv"
        venv.create(env_dir, with_pip=True, system_site_packages=False)
        py = env_dir / ("Scripts" if os.name == "nt" else "bin") / "python"
        run([py, "-m", "pip", "install", "--no-index", "--find-links", wheels, "ugence-workflow-fit-pilot"])
        run([py, "-c", PROBE], cwd=tmp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
