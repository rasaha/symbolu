#!/usr/bin/env python3
"""Reproducible proof that the slice 1 distributions install from built wheels
with ONLY their declared first-party dependencies and no runtime import of the
experimental reasoning runtime or any capability package.

Builds ugence-jcs, ugence-governance-contracts, ugence-uvi-policy-contracts,
ugence-reasoning-method-governance and ugence-readiness-comparison into a local
find-links directory, installs the last two (pip resolves the rest) into a fresh
venv with no system site packages and no monorepo path (--no-index), then proves
inside that env:

  * both packages import from site-packages and ship py.typed;
  * the curated API resolves and the §11 code vocabularies are complete;
  * a record's evidence axes are class constants a producer cannot set;
  * a two-method request compares to the expected outcomes and its result digest
    is independent of input order;
  * neither agentic, agentic_framework, ugence_context_minimization,
    ugence_agent_value_readiness nor governed_value is importable.

Run:  python packages/capabilities/reasoning-method-governance/verify_reasoning_method_governance_distribution.py
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
]

PROBE = r'''
import importlib, sys
for name in ("ugence_reasoning_method_governance", "ugence_readiness_comparison"):
    m = importlib.import_module(name)
    assert "site-packages" in m.__file__, m.__file__
    assert (__import__("pathlib").Path(m.__file__).parent / "py.typed").exists(), name
from ugence_reasoning_method_governance import api
for n in api.__all__:
    assert hasattr(api, n), n
assert len(list(api.ContractErrorCode)) == 18 and len(list(api.RefusalCode)) == 20
from datetime import datetime, timezone
from ugence_governance_contracts.api import AttestationStatus, MetricClaim, SourceBasis, TransformationMethod
from ugence_uvi_policy_contracts.api import ComparisonOperator, GovernedThreshold
from ugence_readiness_comparison import compare
now = datetime(2026, 9, 2, tzinfo=timezone.utc); H = "a" * 64
cat_ref = api.ReasoningMethodCatalogRef("cat", "1", H)
lc, tot = api.ReasoningMethodRef(cat_ref, "linear_chain", "1"), api.ReasoningMethodRef(cat_ref, "tree_of_thought", "1")
rule = api.SufficiencyRule("r", "1", api.SufficiencyKind.THRESHOLD_BASED, GovernedThreshold("t", "u", ComparisonOperator.GTE, "0.9"))
pol = api.ComparisonPolicy("p", "1", rule, (api.ResourceDimension.LLM_CALLS,), None)
tc = api.TaskClassIdentity(api.TASK_CLASS_SCHEMA_VERSION, "tc", "d", "o", api.ConsequenceClass.RECOVERABLE, api.TaskReversibility.OUTCOME_REVERSIBLE, (), (), (), "pop", "b", H, pol)
b = api.BindingRef("b", "c", H, H, H)
def rec(m, calls, rid):
    tel = api.ExecutionTelemetry(calls, api.CountBasis.INJECTED_COUNTER, api.UsageAvailabilityToken.UNAVAILABLE_NOT_REPORTED, None, api.CountBasis.UNKNOWN, 1)
    return api.ReasoningMethodExecutionRecord(api.RECORD_SCHEMA_VERSION, rid, "t", "s", "i" + rid, m, b, "tc", tc.task_class_digest, H, "model", (), (), tel, None, "issuer", now, None)
r1, r2 = rec(lc, 1, "r1"), rec(tot, 4, "r2")
assert r1.attestation_status is AttestationStatus.UNATTESTED
try:
    rec.__globals__["api"].ReasoningMethodExecutionRecord(api.RECORD_SCHEMA_VERSION, "x", "t", "s", "i", lc, b, "tc", tc.task_class_digest, H, "model", (), (), r1.telemetry, None, "issuer", now, None, attestation_status=AttestationStatus.ATTESTED)
    raise SystemExit("producer set an evidence axis")
except api.ContractError as e:
    assert e.code is api.ContractErrorCode.EVIDENCE_AXIS_SET_BY_PRODUCER
def claim(cid, v): return MetricClaim(cid, "t", "s", "q", v, "u", SourceBasis.REPORTED, TransformationMethod.DIRECT)
def req(cands, recs, qs):
    return api.ReadinessComparisonRequest(api.COMPARISON_REQUEST_SCHEMA_VERSION, "req", tc, cat_ref, lc, cands, recs, qs, (claim("c1", "0.92"), claim("c2", "0.94")))
qa, qb = api.QualityResult(lc, "c1", "u", "0.92", None), api.QualityResult(tot, "c2", "u", "0.94", None)
res = compare(req((lc, tot), (r1, r2), (qa, qb)), produced_at=now)
outcomes = {a.method.method_id: a.outcome for a in res.assessments}
assert outcomes == {"linear_chain": api.FitOutcome.SUFFICIENT_PARETO_EFFICIENT, "tree_of_thought": api.FitOutcome.SUFFICIENT_RESOURCE_DOMINATED}, outcomes
assert res.result_digest == compare(req((tot, lc), (r2, r1), (qb, qa)), produced_at=now).result_digest
assert res.authority_resolution_basis == "REQUESTER_ASSERTED" and all(a.usage_scope == "RESEARCH_ONLY" for a in res.assessments)
for forbidden in ("agentic", "agentic_framework", "ugence_context_minimization", "ugence_agent_value_readiness", "governed_value", "numpy"):
    try:
        importlib.import_module(forbidden)
    except ImportError:
        continue
    raise SystemExit(f"{forbidden} is importable in the verification env")
print("VERIFIED: slice 1 distributions install and operate from wheels with declared dependencies only")
'''


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
        run([py, "-m", "pip", "install", "--no-index", "--find-links", wheels, "ugence-reasoning-method-governance", "ugence-readiness-comparison"])
        run([py, "-c", PROBE], cwd=tmp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
