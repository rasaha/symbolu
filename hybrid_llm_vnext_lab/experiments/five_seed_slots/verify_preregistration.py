#!/usr/bin/env python3
"""Fail if the pre-registered acceptance gates changed after they were committed. Stdlib.

Compares the live sha256 of ACCEPTANCE_GATES.json against the value recorded in
ACCEPTANCE_GATES.sha256 at pre-registration time. Any post-registration edit fails CI.
"""
from __future__ import annotations

import hashlib
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
GATES = HERE / "ACCEPTANCE_GATES.json"
RECORD = HERE / "ACCEPTANCE_GATES.sha256"

fails = []
if not GATES.exists():
    fails.append("ACCEPTANCE_GATES.json missing")
if not RECORD.exists():
    fails.append("ACCEPTANCE_GATES.sha256 missing")

if not fails:
    live = hashlib.sha256(GATES.read_bytes()).hexdigest()
    recorded = RECORD.read_text().strip()
    if live != recorded:
        fails.append(f"acceptance gates CHANGED after pre-registration: live {live[:12]} != recorded {recorded[:12]}")
    # holdout seeds must be exactly 3..7
    import json
    g = json.loads(GATES.read_text())
    if g.get("holdout_seeds") != [3, 4, 5, 6, 7]:
        fails.append(f"holdout seeds are not [3,4,5,6,7]: {g.get('holdout_seeds')}")

print(f"pre-registration integrity: {'OK' if not fails else 'FAILED'}")
for f in fails:
    print(f"  FAIL: {f}")
sys.exit(1 if fails else 0)
