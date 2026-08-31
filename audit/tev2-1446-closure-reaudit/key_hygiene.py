"""Independent re-audit of closure finding F-08 against the MERGED head.

F-08: TrustedEvidenceSigningKey must not expose the raw seed through any
public, accidental or introspection route — no dataclass field, no `.seed`,
no `__dict__`, no successful pickle/copy/deepcopy, no leak through exception
text on bad input.

Run: python audit/tev2-1446-closure-reaudit/key_hygiene.py <repo-root>
"""
from __future__ import annotations

import copy
import dataclasses
import pickle
import sys
from pathlib import Path

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "packages/trusted-evidence-authority/src"))

from ugence_trusted_evidence_authority.authority.backend import TrustedEvidenceSigningKey

SEED = bytes(range(32))
k = TrustedEvidenceSigningKey(SEED)
failures = []


def record(ok, label):
    print(f"  [{'ok' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


record(not dataclasses.is_dataclass(k), "not a dataclass (so dataclasses.asdict cannot walk it)")
record(not hasattr(k, "__dict__"), "no instance __dict__ (slots-only)")
record(not hasattr(k, "seed"), "no .seed attribute")
record(not any(SEED.hex() in str(getattr(k, s, "")) for s in getattr(k, "__slots__", ())),
       "no slot's string form contains the seed hex")

record(SEED.hex() not in repr(k), "seed hex not present in repr()")
record(SEED.hex() not in str(k), "seed hex not present in str()")

try:
    pickle.dumps(k)
    record(False, "pickle.dumps succeeded (seed could escape via serialization)")
except Exception as e:
    record(True, f"pickle.dumps raises ({type(e).__name__})")

try:
    copy.copy(k)
    record(False, "copy.copy succeeded")
except Exception as e:
    record(True, f"copy.copy raises ({type(e).__name__})")

try:
    copy.deepcopy(k)
    record(False, "copy.deepcopy succeeded")
except Exception as e:
    record(True, f"copy.deepcopy raises ({type(e).__name__})")

try:
    k.extra = "x"
    record(False, "attribute assignment after construction succeeded")
except Exception as e:
    record(True, f"attribute assignment raises ({type(e).__name__})")

try:
    k.sign("not bytes")
    record(False, "sign() accepted a non-bytes message without raising")
except Exception as e:
    record(SEED.hex() not in str(e), f"exception text on bad sign() input does not leak the seed ({type(e).__name__})")

# vars()/dir() sweep: does anything reachable via introspection carry the seed?
via_vars = False
try:
    via_vars = SEED.hex() in str(vars(k))
except TypeError:
    pass  # no __dict__ -> vars() itself raises, which is the desired outcome
record(not via_vars, "vars(k) does not expose the seed (or vars() itself raises)")

via_dir = any(SEED.hex() in str(getattr(k, name, "")) for name in dir(k) if not name.startswith("__"))
record(not via_dir, "no public attribute reachable via dir() renders the seed")

# The signing key must still work after all of the above.
sig = k.sign(b"still works")
record(len(sig) == 64, "signing key remains functional after the hygiene sweep (64-byte signature)")

print()
if failures:
    print(f"FAIL: {len(failures)} check(s) did not hold: {failures}")
    sys.exit(1)
print("PASS: F-08 holds against the merged head — no public or accidental route "
      "exposes the raw seed, and the key remains functional")
