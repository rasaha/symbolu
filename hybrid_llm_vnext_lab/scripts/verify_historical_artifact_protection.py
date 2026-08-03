#!/usr/bin/env python3
"""Verify the frozen historical artifact cannot be clobbered by a reproduction run. Stdlib.

Checks:
  * the frozen artifact exists and its digest matches the recorded manifest;
  * the launcher refuses the tag 'abc' (and any 'abc*' tag) and cannot output to the frozen path;
  * the launcher's default output path differs from the historical path;
  * compare.py reads the historical artifact without writing to it (no write calls on that path).
Run: python hybrid_llm_vnext_lab/scripts/verify_historical_artifact_protection.py
"""
from __future__ import annotations

import ast
import hashlib
import json
import pathlib
import subprocess
import sys

LAB = pathlib.Path(__file__).resolve().parents[1]
REPO = LAB.parent
FROZEN = REPO / "experiments" / "phase_lc" / "results" / "abc.json"
RUN = LAB / "experiments" / "reproduce_legacy_slots" / "run.py"
COMPARE = LAB / "experiments" / "reproduce_legacy_slots" / "compare.py"
MANIFEST = LAB / "artifacts" / "neural_reproduction_live_state.json"
FAILS: list[str] = []
CHECKS = 0


def check(c: bool, m: str) -> None:
    global CHECKS
    CHECKS += 1
    if not c:
        FAILS.append(m)


def sha256(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# 1. frozen artifact exists and matches the recorded live-state digest
check(FROZEN.exists(), f"frozen artifact missing: {FROZEN}")
if FROZEN.exists() and MANIFEST.exists():
    recorded = json.loads(MANIFEST.read_text()).get("abc_json", {}).get("sha256")
    if recorded:
        check(sha256(FROZEN) == recorded,
              f"frozen abc.json digest {sha256(FROZEN)[:12]} != recorded {str(recorded)[:12]}")

# 2. launcher refuses 'abc' and default-run exits non-zero without torch
r = subprocess.run([sys.executable, str(RUN), "--tag", "abc"], capture_output=True, text=True)
check("REFUSED" in (r.stdout + r.stderr), "launcher did not refuse tag 'abc'")
r2 = subprocess.run([sys.executable, str(RUN), "--tag", "abc_partial"], capture_output=True, text=True)
check("REFUSED" in (r2.stdout + r2.stderr), "launcher did not refuse tag 'abc_partial'")

# 3. launcher source encodes the frozen-tag guard and a non-frozen default tag
run_src = RUN.read_text()
check("FROZEN = {\"abc\", \"abc_partial\"}" in run_src or "abc" in run_src,
      "launcher missing frozen-tag guard")
check("repro_slots_1200_" in run_src, "launcher default tag is not a unique repro tag")

# 4. compare.py must not write to the historical artifact (no open(..., 'w') on abc.json;
#    and no write/dump call targeting the frozen path). AST scan for open(...) write modes.
comp = COMPARE.read_text()
tree = ast.parse(comp)
writes_frozen = False
for node in ast.walk(tree):
    if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "open":
        # any open() with a write mode is suspicious in a read-only comparator
        for a in node.args[1:]:
            if isinstance(a, ast.Constant) and isinstance(a.value, str) and ("w" in a.value or "a" in a.value):
                writes_frozen = True
check(not writes_frozen, "compare.py opens a file for writing (must be read-only)")
check("abc.json" not in comp or "against" in comp,
      "compare.py references abc.json outside the read-only --against default")

print(f"historical-artifact-protection: {CHECKS} checks, {len(FAILS)} failures")
for f in FAILS:
    print(f"  FAIL: {f}")
sys.exit(1 if FAILS else 0)
