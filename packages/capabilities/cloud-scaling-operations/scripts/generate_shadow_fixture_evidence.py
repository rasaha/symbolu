#!/usr/bin/env python3
"""Generate the committed FAKE_LOCAL_FIXTURE shadow-harness evidence.

Writes deterministic fixture artifacts to artifacts/shadow_harness_fixture/. This is
fake/local evidence only — no real cluster is accessed. Re-running reproduces identical
deterministic artifacts (canary/integrity/aggregate embed environment-dependent detail
and are excluded from the verifier's byte-for-byte comparison).
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
for p in (str(PKG), str(PKG / "src"), str(PKG.parent / "cloud-scaling-controller" / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from shadow_validation.evidence import generate_fixture_evidence  # noqa: E402
from shadow_validation.integrity import verify_evidence_dir  # noqa: E402
from shadow_mutation_canaries import run_mutation_canaries  # noqa: E402

import os  # noqa: E402

# Default target is the committed fixture location; CI overrides with a temp dir so the
# committed evidence is never mutated by a verification run.
OUT = Path(os.environ.get("SHADOW_FIXTURE_OUT", str(PKG / "artifacts" / "shadow_harness_fixture")))


def main() -> int:
    canaries = run_mutation_canaries()
    # First pass into a temp dir to compute the integrity report we embed.
    tmp = Path(tempfile.mkdtemp(prefix="shadow-fixture-tmp-"))
    generate_fixture_evidence(str(tmp), canary_results=canaries)
    report = verify_evidence_dir(str(tmp))
    # Final pass into the committed location with the integrity report embedded.
    OUT.mkdir(parents=True, exist_ok=True)
    aggregate = generate_fixture_evidence(str(OUT), canary_results=canaries,
                                          integrity_report=report)
    final = verify_evidence_dir(str(OUT))
    print(f"generated committed fixture evidence -> {OUT}")
    print(f"verdict={aggregate['verdict']} integrity_ok={final['ok']}")
    return 0 if final["ok"] and aggregate["verdict"].endswith("FIXTURE_OK") else 1


if __name__ == "__main__":
    raise SystemExit(main())
