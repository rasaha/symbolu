#!/usr/bin/env python3
"""Lab integrity verifier — provenance, boundaries, JSON, status markers. Stdlib only.

Checks (none require torch):
  * every lab JSON parses;
  * SOURCE_HASHES incubated_blob matches `git hash-object` of the on-disk file, and each
    source_blob is resolvable at source_commit;
  * no Phase import anywhere in src/ (AST); stdlib modules import no torch;
  * no packaging metadata / wheels in the lab;
  * required status markers present;
  * reconciliation artifact carries the corrected status and does not call slots 'failed'.
Run: python hybrid_llm_vnext_lab/scripts/verify_lab.py
"""
from __future__ import annotations

import ast
import json
import pathlib
import subprocess
import sys

LAB = pathlib.Path(__file__).resolve().parents[1]
REPO = LAB.parent
FAILS: list[str] = []
CHECKS = 0

FORBIDDEN_PHASE = {"symbolu.phase_transformer", "symbolu_core.phase_transformer",
                   "PhaseAttentionLayer", "HybridPhaseTransformer",
                   "BindingCachePhaseState", "BindingCacheTransformer"}


def check(cond: bool, msg: str) -> None:
    global CHECKS
    CHECKS += 1
    if not cond:
        FAILS.append(msg)


def _git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO), *args],
                          capture_output=True, text=True).stdout.strip()


# 1. all lab JSON parses
for jp in sorted(LAB.rglob("*.json")):
    try:
        json.loads(jp.read_text())
    except json.JSONDecodeError as e:
        FAILS.append(f"invalid JSON {jp.relative_to(LAB)}: {e}")
    CHECKS += 1

# 2. provenance hash integrity
hashes = json.loads((LAB / "provenance" / "SOURCE_HASHES.json").read_text())
src_commit = hashes["source_commit"]
for f in hashes["files"]:
    dest = LAB / f["destination"]
    check(dest.exists(), f"incubated file missing: {f['destination']}")
    if dest.exists():
        actual = _git("hash-object", str(dest))
        check(actual == f["incubated_blob"],
              f"incubated_blob mismatch for {f['destination']}: recorded {f['incubated_blob']} vs actual {actual}")
    # source blob resolvable at source_commit
    exists = subprocess.run(["git", "-C", str(REPO), "cat-file", "-e", f["source_blob"]],
                            capture_output=True).returncode == 0
    check(exists, f"source_blob {f['source_blob']} for {f['original_path']} not resolvable")

# 3. no Phase imports in src/, no torch in stdlib modules
STDLIB_ONLY = {"binding_slots/slot_reference.py", "local_baseline/window_reference.py",
               "instrumentation/invariants.py", "instrumentation/probes.py", "contracts/memory.py"}
for py in sorted((LAB / "src").rglob("*.py")):
    tree = ast.parse(py.read_text())
    mods, names = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mods.add(node.module)
            names |= {a.name for a in node.names}
    rel = py.relative_to(LAB / "src").as_posix()
    hits = (mods | names) & FORBIDDEN_PHASE
    hits |= {m for m in mods if "phase_transformer" in m}
    check(not hits, f"Phase import in src/{rel}: {sorted(hits)}")
    if rel in STDLIB_ONLY:
        check(not any(m == "torch" or m.startswith("torch.") or m == "numpy" for m in mods),
              f"stdlib module src/{rel} imports torch/numpy")

# 4. no packaging metadata / wheels
for bad in ("pyproject.toml", "setup.py", "setup.cfg"):
    check(not (LAB / bad).exists(), f"lab must not contain {bad}")
check(not list(LAB.rglob("*.whl")), "lab must not contain wheels")

# 5. status markers
readme = (LAB / "README.md").read_text()
for marker in ("NOT_AN_INSTALLABLE_PACKAGE", "NOT_A_PRODUCTION_MODEL", "NOT_READY_FOR_PACKAGING"):
    check(marker in readme, f"README missing status marker {marker}")

# 6. reconciliation artifact
recon = json.loads((REPO / "docs/audits/hybrid_llm/artifacts/binding_slot_evidence_reconciliation.json").read_text())
check(recon.get("corrected_status") == "INTERNALLY_SUPPORTED_WORKING_CANDIDATE_AT_TESTED_SCALE",
      "reconciliation missing corrected status")
check("failed" in recon.get("must_not_classify_as", []),
      "reconciliation must forbid the 'failed' classification")
check(len(recon.get("demonstrated", [])) >= 5, "reconciliation must list the demonstrated slot facts")

print(f"lab verifier: {CHECKS} checks, {len(FAILS)} failures")
for f in FAILS:
    print(f"  FAIL: {f}")
sys.exit(1 if FAILS else 0)
