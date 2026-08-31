"""Run every probe in this closure re-audit and report a summary.

Run: python audit/tev2-1446-closure-reaudit/run_all.py [repo-root] [tev1-baseline-root]

If tev1-baseline-root is omitted, pins_and_api.py (which needs a second
checkout to diff against) is skipped rather than guessed at.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
root = sys.argv[1] if len(sys.argv) > 1 else str(here.parents[1])
base = sys.argv[2] if len(sys.argv) > 2 else None

PROBES = [
    ("F-01/F-03 anchor forgery", "anchor_forgery.py", [root]),
    ("F-02 backend differential", "backend_differential.py", [root]),
    ("F-04/F-05 reverification shapes", "reverification_shapes.py", [root]),
    ("F-08 key hygiene", "key_hygiene.py", [root]),
    ("F-09 gate + survivors", "gate_and_survivors.py", [root]),
]
if base:
    PROBES.append(("TEV-1 pins + API parity", "pins_and_api.py", [root, base]))

results = []
for label, script, args in PROBES:
    proc = subprocess.run([sys.executable, str(here / script), *args], capture_output=True, text=True)
    ok = proc.returncode == 0
    results.append((label, ok))
    print(f"\n{'=' * 70}\n{label} ({script})\n{'=' * 70}")
    print(proc.stdout)
    if proc.stderr:
        print(proc.stderr, file=sys.stderr)

print(f"\n{'=' * 70}\nSUMMARY\n{'=' * 70}")
for label, ok in results:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
if not base:
    print("  [SKIPPED] TEV-1 pins + API parity (no baseline root given)")

sys.exit(0 if all(ok for _, ok in results) else 1)
