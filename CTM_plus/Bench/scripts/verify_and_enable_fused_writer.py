#!/usr/bin/env python3
"""Track 2 — correctness-GATED enable of the fused CUDA decode-write kernels.

The fused decode-write path (`PHASE6E_FUSED_WRITER=1`, kernels
`fused_decode_write_{k,v}.cu`) is the already-BUILT, low-risk write-path
optimization. It ships DEFAULT-OFF (enforced by
tests/verify_phase6e_fused_byte_eq.py::test_default_env_is_off) until it is
GPU-verified. This script is the gate that authorizes turning it on for a
measurement run — it NEVER changes the shipped default.

The gate has TWO conditions, and BOTH must hold, because the fused path
*silently falls back to the byte-identical Python reference* when the CUDA
extension is missing (so byte-eq alone would pass with NO speedup):

  1. byte-equivalence GREEN  — verify_phase6e_fused_byte_eq.py --device cuda
     exits 0 (every mutated state tensor identical between inline and fused).
  2. int4_protected_C ACTUALLY LOADED — else fused==Python ref, enabling the
     flag buys nothing and would be a misleading no-op.

On GO it prints the blessed `export PHASE6E_FUSED_WRITER=1` and, if `--then`
is given, runs that command with the flag set. On NO-GO it exits non-zero
with the reason and does NOT authorize the flag.

Honest ceiling note (do not oversell this lever): PHASE_6M_ATTRIBUTION_FINDINGS
(6M.4) measured the writer "already at its lower bound" with the tax on the
READ side (decode kernel ~29% + gather ~15%), and 6M.3 found CUDA-graph capture
~neutral at saturation. So this write-path enable is a correct no-regret move,
but its expected throughput ceiling is LOW; the 6M.7 attribution + the Test-1
roofline decide the real lever.

Usage (on the pod):
    python CTM_plus/Bench/scripts/verify_and_enable_fused_writer.py --device cuda
    python CTM_plus/Bench/scripts/verify_and_enable_fused_writer.py --device cuda \
        --then python CTM_plus/Bench/scripts/phase6l_capacity_demo.py --compare ...

Dry-run the GATE LOGIC on CPU (no CUDA; expects NO-GO "extension not loaded"):
    python CTM_plus/Bench/scripts/verify_and_enable_fused_writer.py --device cpu
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def _find_verifier() -> Path:
    """Locate verify_phase6e_fused_byte_eq.py from a few known roots."""
    here = Path(__file__).resolve()
    candidates = [
        here.parent.parent.parent / "KVPolicy" / "tests" / "verify_phase6e_fused_byte_eq.py",
        Path("/workspace/symbolu/CTM_plus/KVPolicy/tests/verify_phase6e_fused_byte_eq.py"),
        Path("/home/user/symbolu/CTM_plus/KVPolicy/tests/verify_phase6e_fused_byte_eq.py"),
    ]
    for c in candidates:
        if c.exists():
            return c
    raise SystemExit(f"FAIL: verify_phase6e_fused_byte_eq.py not found (looked in {candidates})")


def run_gate(device: str) -> dict:
    """Run the byte-eq verifier as a subprocess; classify GO / NO-GO.

    byte_eq_pass = verifier exit code 0 (unittest OK).
    extension_loaded = the verifier's cuda branch printed the 'extension loaded'
    line (it prints 'NOT loaded' when int4_protected_C is missing)."""
    verifier = _find_verifier()
    proc = subprocess.run(
        [sys.executable, str(verifier), "--device", device],
        capture_output=True, text=True,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    byte_eq_pass = proc.returncode == 0
    ext_loaded = ("int4_protected_C extension loaded" in out)
    ext_not_loaded = ("int4_protected_C NOT loaded" in out)

    go = bool(byte_eq_pass and ext_loaded and device == "cuda")
    if go:
        reason = ("GO: byte-eq GREEN and int4_protected_C loaded on CUDA — the "
                  "fused CUDA write kernels are correctness-verified. Authorized to "
                  "enable PHASE6E_FUSED_WRITER=1 for a MEASUREMENT run (default stays "
                  "OFF).")
    elif device != "cuda":
        reason = (f"NO-GO: device={device}. On non-CUDA the fused path is the Python "
                  "reference — there is no CUDA kernel to enable. Re-run with "
                  "--device cuda on the pod.")
    elif not byte_eq_pass:
        reason = ("NO-GO: byte-equivalence FAILED (verifier exit "
                  f"{proc.returncode}). Correctness gate: do NOT enable the fused "
                  "writer. See the verifier output for the divergent state tensor.")
    elif ext_not_loaded or not ext_loaded:
        reason = ("NO-GO: byte-eq passed but int4_protected_C is NOT loaded — the "
                  "fused path fell back to the Python reference, so enabling the flag "
                  "buys NO speedup. Build the extension "
                  "(CTM_plus/CUDA_int4_protected: pip install -e . --no-deps) then "
                  "re-run.")
    else:
        reason = "NO-GO: unclassified; inspect the verifier output below."

    return {
        "go": go,
        "device": device,
        "byte_eq_pass": byte_eq_pass,
        "verifier_returncode": proc.returncode,
        "extension_loaded": ext_loaded,
        "reason": reason,
        "verifier_output_tail": "\n".join(out.strip().splitlines()[-12:]),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Gate the fused CUDA write-kernel enable on byte-eq + extension load")
    ap.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    ap.add_argument("--json-out", type=Path, default=None)
    ap.add_argument("--then", nargs=argparse.REMAINDER, default=None,
                    help="on GO, run this command with PHASE6E_FUSED_WRITER=1 set")
    args = ap.parse_args(argv)

    v = run_gate(args.device)
    print("=" * 72)
    print("Track 2 — fused CUDA write-kernel enable gate")
    print("=" * 72)
    print(f"  byte_eq_pass      : {v['byte_eq_pass']} (verifier exit {v['verifier_returncode']})")
    print(f"  extension_loaded  : {v['extension_loaded']}")
    print(f"  VERDICT           : {'GO' if v['go'] else 'NO-GO'}")
    print(f"  {v['reason']}")
    if v["verifier_output_tail"]:
        print("  --- verifier output (tail) ---")
        for ln in v["verifier_output_tail"].splitlines():
            print(f"    {ln}")
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(v, indent=2))

    if not v["go"]:
        return 1
    print("\n  AUTHORIZED — to enable for a measurement run:")
    print("      export PHASE6E_FUSED_WRITER=1")
    if args.then:
        cmd = [c for c in args.then if c != "--"]
        if cmd:
            print(f"\n  Running with the flag set: {' '.join(cmd)}")
            env = dict(os.environ, PHASE6E_FUSED_WRITER="1")
            return subprocess.run(cmd, env=env).returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
