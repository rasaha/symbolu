#!/usr/bin/env python3
"""Reproducible proof that ugence-reasoning-method-advisor installs from a built
wheel with ONLY its declared first-party dependencies, advises deterministically,
and cannot import the reasoning runtime, the comparison engine, or any capability
package.

Run:  python packages/capabilities/reasoning-method-advisor/verify_reasoning_method_advisor_distribution.py
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
    REPO / "packages" / "capabilities" / "reasoning-method-advisor",
]

PROBE = r'''
import importlib, pathlib
m = importlib.import_module("ugence_reasoning_method_advisor")
assert "site-packages" in m.__file__ and (pathlib.Path(m.__file__).parent / "py.typed").exists()
from ugence_reasoning_method_advisor import api
for n in api.__all__: assert hasattr(api, n), n
from datetime import datetime, timezone
from ugence_reasoning_method_governance import api as g
now = datetime(2026, 9, 2, tzinfo=timezone.utc); H = "a" * 64
ev = (g.ImplementationEvidence(g.ImplementationEvidenceKind.CONCRETE_CLASS_REGISTERED, "r", now),
      g.ImplementationEvidence(g.ImplementationEvidenceKind.STUB_EXECUTION_COMPLETED, "s", now),
      g.ImplementationEvidence(g.ImplementationEvidenceKind.UNIT_TESTS_PRESENT, "t", now))
entries = tuple(sorted((g.ReasoningMethodEntry(m, "1", m, ev, (), ()) for m in ("map_reduce", "tree_of_thought")), key=lambda e: e.sort_key))
cat = g.ReasoningMethodCatalog(g.CATALOG_SCHEMA_VERSION, "cat", "1", entries, "issuer", now)
adm = api.Predicate(api.PredicateKind.IMPLEMENTATION_STATUS_IN, ("EXECUTABLE_TESTED",))
rules = tuple(sorted((api.Rule(f"r.{t}", "0", api.RuleKind.SUPPORT, api.Predicate(api.PredicateKind.STRUCTURAL_TOKEN_PRESENT, (t,)), (m,), "ref", "why")
                      for t, m in (("comparison_request", "map_reduce"), ("ambiguity_detected", "tree_of_thought"))), key=lambda r: r.rule_id))
rs = api.RuleSet(api.RULE_SET_SCHEMA_VERSION, "rules", "0", adm, rules, "prov", "issuer", now)
prof = g.TaskProfile(g.PROFILE_SCHEMA_VERSION, "p", "d", "o", g.ConsequenceClass.RECOVERABLE, g.TaskReversibility.OUTCOME_REVERSIBLE, (), (), ("comparison_request",), "pop")
req = api.ReasoningMethodAdvisoryRequest(api.ADVISORY_REQUEST_SCHEMA_VERSION, "req", prof, None, cat, rs)
a, b = api.advise(req, advised_at=now), api.advise(req, advised_at=now)
assert a.advisory_digest == b.advisory_digest
assert [q.method.method_id for q in a.qualifying] == ["map_reduce"] and a.primary.method_id == "map_reduce"
assert a.classification.value == "UNCLASSIFIED_EXPLORATORY" and a.eligibility.value == "INELIGIBLE_UNCLASSIFIED"
assert a.evidence_status == "COMPARISON_EVIDENCE_ABSENT" and a.usage_scope == "RESEARCH_ONLY"
two = api.advise(api.ReasoningMethodAdvisoryRequest(api.ADVISORY_REQUEST_SCHEMA_VERSION, "req2", g.TaskProfile(g.PROFILE_SCHEMA_VERSION, "p", "d", "o", g.ConsequenceClass.RECOVERABLE, g.TaskReversibility.OUTCOME_REVERSIBLE, (), (), ("comparison_request", "ambiguity_detected"), "pop"), None, cat, rs), advised_at=now)
assert two.primary is None and len(two.trade_offs) == 2
for forbidden in ("agentic", "ugence_readiness_comparison", "ugence_context_minimization", "ugence_agent_value_readiness", "governed_value", "numpy"):
    try:
        importlib.import_module(forbidden)
    except ImportError:
        continue
    raise SystemExit(f"{forbidden} is importable in the verification env")
print("VERIFIED: advisor installs from wheels with declared dependencies only and advises deterministically")
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
        run([py, "-m", "pip", "install", "--no-index", "--find-links", wheels, "ugence-reasoning-method-advisor"])
        run([py, "-c", PROBE], cwd=tmp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
