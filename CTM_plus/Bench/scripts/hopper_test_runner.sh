#!/usr/bin/env bash
# Phase 6M.6 Test 2 — Hopper build-vs-buy runner.
#
# ONE engineering experiment (no profiler, no code change, no kernel/quant change):
# does newer silicon (H100 / H200) recover the 0.22x aggregate throughput tax FOR
# FREE? Thin wrapper over `phase6l_capacity_demo.py --compare` that applies the
# FROZEN build-vs-buy decision to the measured aggregate-TPS ratio.
#
#   agg_ratio >= 0.30  -> DEPLOY HOPPER  (Hopper recovers it; STOP the 6F kernel work)
#   agg_ratio <  0.25  -> FUND 6F        (not native compute -> data-movement/layout)
#   0.25 .. 0.30       -> MARGINAL       (lean 6F; roofline would attribute the axis)
#
# See PHASE_6M_THROUGHPUT_RECOVERY_TEST_PLAN.md (Test 2) + PHASE_6M7_DECODE_ATTRIBUTION.md.
# Reuses existing tooling only — this adds NO instrumentation.
#
# Usage (on the pod):
#   bash CTM_plus/Bench/scripts/hopper_test_runner.sh
#   GPU_TAG=H200 BLIST=96,128 bash CTM_plus/Bench/scripts/hopper_test_runner.sh
# Re-baseline A100 the same way (writes A100_report.json for the 6M.6 axis annotation):
#   GPU_TAG=A100 bash CTM_plus/Bench/scripts/hopper_test_runner.sh
set -u

# --- Test-2 operating point (override via env) ---
MODEL="${MODEL:-Qwen/Qwen2.5-7B-Instruct}"
MML="${MML:-8192}"; MAXTOK="${MAXTOK:-512}"; PFRAC="${PFRAC:-0.95}"
BLIST="${BLIST:-96,128}"; GPUUTIL="${GPUUTIL:-0.5}"
GPU_TAG="${GPU_TAG:-H100}"
# FROZEN decision thresholds — do NOT loosen post-hoc.
DEPLOY_HOPPER_MIN="0.30"
FUND_6F_MAX="0.25"

# --- locate repo + scripts ---
ROOT=""
for R in /workspace/symbolu /home/user/symbolu \
         "$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." 2>/dev/null && pwd)"; do
  [ -n "$R" ] && [ -d "$R/CTM_plus" ] && ROOT="$R" && break
done
if [ -z "$ROOT" ]; then echo "FAIL: could not locate the symbolu repo"; exit 2; fi
SCRIPTS="$ROOT/CTM_plus/Bench/scripts"
OUT="${OUT_DIR:-$ROOT/CTM_plus/Bench/bench_out/phase6m6}"; mkdir -p "$OUT"

# --- venv (best-effort) ---
[ -f /workspace/venv-vllm/bin/activate ] && . /workspace/venv-vllm/bin/activate
PY="${PYBIN:-python3}"

# --- preconditions (fail fast with a clear reason) ---
echo "== preconditions =="
"$PY" - <<'PY' || { echo "PRECONDITION FAIL — fix the above before booking GPU time."; exit 2; }
import os, sys
try:
    import torch
except Exception as e:
    print(f"  FAIL torch import: {e}"); sys.exit(1)
if not torch.cuda.is_available():
    print("  FAIL: no CUDA GPU visible"); sys.exit(1)
name = torch.cuda.get_device_name(0)
print(f"  GPU: {name}")
if ("H100" not in name) and ("H200" not in name) and (os.environ.get("GPU_TAG","H100") not in ("A100",)):
    print(f"  WARN: expected H100/H200 but got {name!r}. Running anyway "
          "(set GPU_TAG to match, or use this to re-baseline A100).")
try:
    import vllm; print(f"  vllm: {vllm.__version__}")
except Exception as e:
    print(f"  FAIL vllm import: {e}"); sys.exit(1)
try:
    import int4_protected_C  # noqa: F401
    print("  int4_protected_C: loaded")
except Exception as e:
    print(f"  WARN: int4_protected_C NOT loaded ({type(e).__name__}) — the packed "
          "decode path may error/fall back; build it before a real run.")
mask = os.environ.get("PROTECT_MASK_PATH",
                      "/workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt")
ok = os.path.exists(mask)
print(f"  protect mask: {mask} [{'OK' if ok else 'MISSING'}]")
if not ok:
    print("  FAIL: protect mask missing — set PROTECT_MASK_PATH."); sys.exit(1)
PY

# --- run the capacity + aggregate-throughput compare (bf16 vs int4_protected) ---
CELL_OUT="$OUT/${GPU_TAG}_run"; mkdir -p "$CELL_OUT"
echo "== phase6l --compare on ${GPU_TAG} (model=$MODEL mml=$MML b-list=$BLIST max-tokens=$MAXTOK) =="
"$PY" "$SCRIPTS/phase6l_capacity_demo.py" --compare \
    --model "$MODEL" --mml "$MML" --max-tokens "$MAXTOK" --prompt-frac "$PFRAC" \
    --b-list "$BLIST" --gpu-util "$GPUUTIL" --out-dir "$CELL_OUT" \
  || { echo "RUN FAILED (see phase6l output above)"; exit 3; }

REPORT="$CELL_OUT/report.json"
if [ ! -f "$REPORT" ]; then echo "FAIL: no report.json at $REPORT"; exit 3; fi
cp "$REPORT" "$OUT/${GPU_TAG}_report.json"

# --- FROZEN build-vs-buy decision on the MEASURED ratio ---
"$PY" - "$OUT/${GPU_TAG}_report.json" "$DEPLOY_HOPPER_MIN" "$FUND_6F_MAX" "$GPU_TAG" <<'PY'
import json, sys
report, deploy_min, fund_max, tag = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
d = json.loads(open(report).read())
tp = d.get("throughput") or {}
agg = tp.get("aggregate_tps_ratio")
dn = d.get("density") or {}
dens = (dn.get("demonstrated_density_ratio") if isinstance(dn, dict) else None) \
       or (d.get("analysis") or {}).get("demonstrated_density_ratio")
print("=" * 70)
print(f"FROZEN build-vs-buy decision — {tag}")
print("=" * 70)
print(f"  aggregate_tps_ratio (protected/bf16): {agg}")
print(f"  density_ratio (should stay ~1.83x, hardware-invariant): {dens}")
if agg is None:
    print("  VERDICT: INCONCLUSIVE — no aggregate_tps_ratio (did BOTH cells reach the "
          "clean-max-B ceiling? re-run with a wider --b-list).")
    sys.exit(0)
if isinstance(dens, (int, float)) and not (1.6 <= dens <= 2.1):
    print(f"  SANITY WARN: density {dens} is OUTSIDE the ~1.83x hardware-invariant band "
          "-> suspect a measurement problem; do NOT trust agg until resolved.")
if agg >= deploy_min:
    print(f"  VERDICT: DEPLOY HOPPER.  agg {agg:.3f} >= {deploy_min} -> newer silicon "
          "recovers the tax FOR FREE.")
    print("           STOP the multi-week 6F kernel project; 'deploy on Hopper' is the "
          "zero-NRE throughput answer.")
elif agg < fund_max:
    print(f"  VERDICT: FUND 6F.  agg {agg:.3f} < {fund_max} -> native low-precision "
          "compute is NOT the lever.")
    print("           The gap is data-movement/layout -> read-path gather+dequant "
          "fusion (6F) is the project.")
else:
    print(f"  VERDICT: MARGINAL.  {fund_max} <= agg {agg:.3f} < {deploy_min} -> Hopper "
          "helps but does not clear the ~0.30x ceiling alone.")
    print("           Lean 6F; the Test-1 roofline (ncu, currently blocked) would "
          "attribute the residual to compute vs bandwidth.")
PY

# --- optional 6M.6 axis annotation if an A100 baseline report exists ---
A100="$OUT/A100_report.json"
if [ -f "$A100" ] && [ "$GPU_TAG" != "A100" ]; then
  echo "== 6M.6 axis annotation (A100 baseline vs ${GPU_TAG}; --bound-verdict unknown until roofline) =="
  "$PY" "$SCRIPTS/analyze_phase6m6_hardware.py" \
      --report "A100=$A100" --report "${GPU_TAG}=$OUT/${GPU_TAG}_report.json" \
      --bound-verdict unknown --out "$OUT/PHASE_6M6_${GPU_TAG}_report.txt" || true
fi

echo ""
echo "Artifacts -> $OUT/${GPU_TAG}_report.json"
echo "Paste back the VERDICT block. Commit the report so the decision is reproducible:"
echo "    git add -f $OUT/${GPU_TAG}_report.json && git commit -m 'phase6m6: ${GPU_TAG} capacity/tps report'"
