#!/usr/bin/env python3
"""Reproducible independent-packaging proof for the canonical Model Selection
distribution ``ugence-model-selection``.

Builds the local wheel, inspects its contents, then installs it into a fresh
virtualenv with NO monorepo path and proves the capability behaves outside the
repository. Covers the packaging scenarios required by the migration:

  1. wheel contents ......... only ``ugence_model_selection`` source + metadata;
                              NO research/pilot/experiment/provider/benchmark code.
  2. canonical wheel only ... installs (stdlib only), imports ``ugence_model_selection``
                              and ``.api`` from site-packages, runs a minimal
                              eligibility + selection workflow and a NO_ELIGIBLE_MODEL
                              abstain — with no monorepo path on sys.path.

Run:  python packages/capabilities/model-selection/verify_model_selection_distribution.py
Exit 0 on success; non-zero on the first failed step.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import venv
import zipfile
from pathlib import Path

PKG = Path(__file__).resolve().parent

WHEEL_ONLY_CHECK = r'''
import sys
import ugence_model_selection as ms
from ugence_model_selection import api
assert ms.__version__ == "0.1.0", ms.__version__
assert "site-packages" in ms.__file__, ms.__file__
assert not any("/symbolu" in p for p in sys.path), sys.path
assert api.POLICY_VERSION == "exec_gate_v1", api.POLICY_VERSION

from ugence_model_selection.api import (
    ExecutionGate, ExecutableRegistry, ModelRecord, Candidate, Request, Signal,
    Evidence, EvidenceSource, select, EligibilityState, ReasonCode, fingerprint,
)
NOW = 1000.0
def ev():
    return Evidence(EvidenceSource.LIVE_PROBE, NOW, 1.0, ttl_seconds=3600.0)
def cand(provider="anthropic"):
    return Candidate(provider, provider + "-model", provider, region="us",
        context_limit=200000, structured_output=True, tool_use=True,
        price_in_per_mtok=3.0, price_out_per_mtok=15.0, signals={
            "reachable": Signal(True, ev()), "authenticated": Signal(True, ev()),
            "network_allowed": Signal(True, ev()), "model_available": Signal(True, ev()),
            "billing_active": Signal(True, ev()), "quota_state": Signal("ok", ev()),
            "observed_latency_ms": Signal(500.0, ev()), "reliability": Signal(0.99, ev()),
            "credential_expiry_ts": Signal(NOW + 100000, ev())})
# eligible + selected
req = Request("r1", context_tokens=1000, approved_providers={"anthropic"})
gate = ExecutionGate()
assert gate.evaluate(cand(), req, NOW).state is EligibilityState.ELIGIBLE
reg = ExecutableRegistry(gate); reg.upsert(ModelRecord("m1", cand(), observed_latency_ms=500.0))
sel = select(reg.evaluate(req, NOW)[0], req, quality_of=lambda r: 0.9)
assert sel.selected and sel.selected.internal_id == "m1" and not sel.abstained
# NO_ELIGIBLE_MODEL abstain
req2 = Request("r2", context_tokens=1000, approved_providers={"nobody"})
reg2 = ExecutableRegistry(gate); reg2.upsert(ModelRecord("m1", cand(), observed_latency_ms=500.0))
sel2 = select(reg2.evaluate(req2, NOW)[0], req2, quality_of=lambda r: 0.9)
assert sel2.selected is None and sel2.abstained is True
# deterministic fingerprint
d = gate.evaluate(cand(), req, NOW).to_dict()
assert fingerprint(d) == fingerprint(d)
print("CANONICAL-WHEEL-ONLY: OK")
'''

FORBIDDEN_WHEEL_SUBSTRINGS = (
    "model_selection_experiment", "model_selection_pilot", "model_selection_reconciliation",
    "governed_inference_pilot", "control_plane", "provider.py", "execute.py", "benchmark",
    "simulator", "corpus", "harness", "scenarios", "baselines",
)


def _run(cmd, **kw):
    print("  $", " ".join(str(c) for c in cmd))
    return subprocess.run(cmd, check=True, **kw)


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        dist = tmp / "dist"
        # 1) build the wheel
        try:
            _run([sys.executable, "-m", "build", "--wheel", "--outdir", str(dist), str(PKG)])
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("  (python -m build unavailable; falling back to pip wheel)")
            _run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--wheel-dir", str(dist), str(PKG)])
        wheels = list(dist.glob("ugence_model_selection-*.whl"))
        assert len(wheels) == 1, f"expected one wheel, got {wheels}"
        wheel = wheels[0]

        # 1a) inspect wheel contents — canonical source + metadata only
        names = zipfile.ZipFile(wheel).namelist()
        src = [n for n in names if n.startswith("ugence_model_selection/")]
        assert src, "wheel missing canonical package source"
        for n in names:
            low = n.lower()
            if low.endswith(".dist-info/record") or "/dist-info/" in low or n.startswith("ugence_model_selection"):
                continue
            raise AssertionError(f"unexpected wheel member: {n}")
        for n in names:
            for bad in FORBIDDEN_WHEEL_SUBSTRINGS:
                assert bad not in n, f"forbidden content in wheel: {n}"
        print(f"WHEEL CONTENTS OK: {wheel.name} ({len(src)} source members, canonical only)")

        # 2) clean-venv install + import + run
        env = tmp / "venv"
        venv.EnvBuilder(with_pip=True).create(env)
        py = env / ("Scripts" if sys.platform == "win32" else "bin") / "python"
        _run([str(py), "-m", "pip", "install", "--quiet", str(wheel)])
        _run([str(py), "-c", WHEEL_ONLY_CHECK])

    print("ALL MODEL-SELECTION DISTRIBUTION CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
