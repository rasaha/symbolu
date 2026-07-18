"""CER public-draft conformance runner (self-contained).

Runs the reference implementation over the public conformance vectors and checks
that it reproduces, for every vector, the normalized payload, canonical bytes, and
action digest. Imports only the standard library and the CER reference package —
no proprietary ActionGate or ACP internals.

Usage:
    python conformance/run.py
Exit code 0 iff every vector passes.
"""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from reference import action_digest, canonical_bytes, normalized_payload, validate  # noqa: E402


def run() -> int:
    with open(os.path.join(_ROOT, "vectors", "vectors.json"), "r", encoding="utf-8") as fh:
        suite = json.load(fh)
    passed = 0
    total = 0
    for vec in suite["vectors"]:
        total += 1
        cer = vec["cer"]
        name = vec["name"]
        try:
            validate(cer)
            payload = normalized_payload(cer)          # deterministic projection
            canon = canonical_bytes(cer)               # JCS + Action Profile bytes
            digest = action_digest(cer)
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL {name}: reference raised {type(exc).__name__}: {exc}")
            continue
        # payload/bytes must be internally reproducible; digest must match the vector
        ok = (digest == vec["expected_digest"]
              and action_digest(cer) == digest
              and canonical_bytes(cer) == canon
              and normalized_payload(cer) == payload)
        if ok:
            passed += 1
            print(f"PASS {name}: {digest[:16]}…")
        else:
            print(f"FAIL {name}: digest {digest[:16]}… != expected {vec['expected_digest'][:16]}…")
    print(f"\n{passed}/{total} vectors passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(run())
