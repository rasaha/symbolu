#!/usr/bin/env bash
# KVPro V3 Step-0 — Part A: environment / prerequisite gate (RunPod).
# Reports every prerequisite as PASS | FAIL | UNAVAILABLE | NOT_REQUIRED and writes env_gate.json.
# If the production int4 decode fork is absent it says so LOUDLY and prints how to restore it —
# it does NOT pretend the production kernel can be profiled.
set -u
PYBIN="${PYBIN:-python3}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# repo root = two levels up from scripts/kvpro_v3_profile/
ROOT="$(cd "$HERE/../.." && pwd)"
OUT="${1:-$HERE/env_gate.json}"
MASK="${PROTECT_MASK_PATH:-/workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt}"

# in-repo components (from the decode-path map)
BACKEND="$ROOT/CTM_plus/KVPolicy/kv_policy/phase5b_backend_install.py"
WRITER="$ROOT/CTM_plus/KVPolicy/kv_policy/phase5b_4c_paged_writer.py"
TRITON_K="$ROOT/CTM_plus/KVPolicy/kv_policy/int4_fused_attention_kernel.py"
CPU_ORACLE="$ROOT/CTM_plus/KVPolicy/kv_policy/int4_fused_attention_sketch.py"
BENCH="$ROOT/CTM_plus/Bench/scripts/bench_phase6_b4_throughput_gpu.py"
PATCH_GLOB="$ROOT/CTM_plus/Bench/scripts/apply_phase"*"_patches.py"

pass(){ printf "  [PASS]        %-34s %s\n" "$1" "${2:-}"; }
fail(){ printf "  [FAIL]        %-34s %s\n" "$1" "${2:-}"; }
unav(){ printf "  [UNAVAILABLE] %-34s %s\n" "$1" "${2:-}"; }
notr(){ printf "  [NOT_REQUIRED]%-34s %s\n" "$1" "${2:-}"; }

echo "=================================================================="
echo "KVPro V3 Step-0 — prerequisite gate    (repo: $ROOT)"
echo "=================================================================="

# emit JSON incrementally via a python helper reading a KEY=STATUS=DETAIL stream on fd 3
TMP="$(mktemp)"; : >"$TMP"
rec(){ echo "$1|$2|${3:-}" >>"$TMP"; }

# --- GPU / driver / CUDA ---
if command -v nvidia-smi >/dev/null 2>&1; then
  GPU="$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)"
  DRV="$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -1)"
  if [ -n "$GPU" ]; then pass "nvidia_gpu_visible" "$GPU"; rec nvidia_gpu_visible PASS "$GPU"
  else fail "nvidia_gpu_visible" "nvidia-smi ran but no GPU"; rec nvidia_gpu_visible FAIL ""; fi
  pass "gpu_driver" "$DRV"; rec gpu_driver PASS "$DRV"
else
  fail "nvidia_gpu_visible" "nvidia-smi not found"; rec nvidia_gpu_visible FAIL "no nvidia-smi"
  rec gpu_driver UNAVAILABLE ""
fi

# --- torch / cuda / triton / vllm ---
"$PYBIN" - "$TMP" <<'PY'
import sys
tmp = sys.argv[1]
def rec(k, s, d=""):
    open(tmp, "a").write(f"{k}|{s}|{d}\n"); print(f"  [{s:11}] {k:34} {d}")
try:
    import torch
    rec("pytorch_cuda_available", "PASS" if torch.cuda.is_available() else "FAIL",
        f"torch {torch.__version__} cuda={torch.cuda.is_available()}")
    if torch.cuda.is_available():
        rec("cuda_runtime", "PASS", f"cuda {torch.version.cuda}")
except Exception as e:  # noqa: BLE001
    rec("pytorch_cuda_available", "FAIL", f"torch import: {e}")
for mod, key, req in [("triton","triton_available",True),
                      ("vllm","vllm_version",True),
                      ("accelerate","accelerate",False),
                      ("datasets","datasets_for_real_mmlu",False)]:
    try:
        m = __import__(mod); rec(key, "PASS", getattr(m, "__version__", "?"))
    except Exception as e:  # noqa: BLE001
        rec(key, "FAIL" if req else "UNAVAILABLE", f"{mod}: {type(e).__name__}")
# The PRODUCTION int4 decode kernel is an EXTERNAL forked vLLM wheel — the decode hot path.
try:
    from vllm.vllm_flash_attn import flash_attn_with_int4_kvcache  # noqa: F401
    rec("flash_attn_with_int4_kvcache", "PASS", "external fork present (production decode path)")
except Exception as e:  # noqa: BLE001
    rec("flash_attn_with_int4_kvcache", "FAIL",
        f"ABSENT ({type(e).__name__}) — production decode path cannot be profiled")
PY

# --- in-repo KVPro components (present regardless of the external fork) ---
[ -f "$BACKEND" ]    && { pass int4_protected_backend "$BACKEND";        rec int4_protected_backend PASS "in-repo"; } \
                     || { fail int4_protected_backend "missing $BACKEND"; rec int4_protected_backend FAIL ""; }
[ -f "$WRITER" ]     && { pass paged_kv_writer "$WRITER";                rec paged_kv_writer PASS "in-repo"; } \
                     || { fail paged_kv_writer "missing";                rec paged_kv_writer FAIL ""; }
[ -f "$TRITON_K" ]   && { pass triton_route_a_kernel "$TRITON_K (PROFILE THIS)"; rec triton_route_a_kernel PASS "in-repo GPU kernel"; } \
                     || { fail triton_route_a_kernel "missing";          rec triton_route_a_kernel FAIL ""; }
[ -f "$CPU_ORACLE" ] && { pass cpu_numeric_oracle "$CPU_ORACLE";         rec cpu_numeric_oracle PASS "CPU correctness ref"; } \
                     || { unav cpu_numeric_oracle "missing";             rec cpu_numeric_oracle UNAVAILABLE ""; }
[ -f "$BENCH" ]      && { pass throughput_bench "$BENCH";                rec throughput_bench PASS "reuse for Part C"; } \
                     || { fail throughput_bench "missing";               rec throughput_bench FAIL ""; }

# --- protection mask ---
if [ -f "$MASK" ]; then pass protect_mask "$MASK"; rec protect_mask PASS "$MASK"
else fail protect_mask "not at $MASK — build via CTM_plus/Bench/scripts/calibrate_phase5b_protect_mask.py"; rec protect_mask FAIL "$MASK"; fi

# --- profiling tools + permissions ---
for tool in nsys ncu; do
  if command -v "$tool" >/dev/null 2>&1; then pass "${tool}_present" "$(command -v $tool)"; rec "${tool}_present" PASS ""
  else unav "${tool}_present" "not on PATH"; rec "${tool}_present" UNAVAILABLE ""; fi
done
# ncu counters usually need elevated perms / a permissive profiling flag
if command -v ncu >/dev/null 2>&1; then
  notr "ncu_counter_perms" "verify at run time (NVreg RmProfilingAdminOnly=0 or sudo); mark counters UNAVAILABLE if blocked"
  rec ncu_counter_perms NOT_REQUIRED "verify at run"
fi

# --- restore instructions if the production fork is absent ---
if ! grep -q "flash_attn_with_int4_kvcache|PASS" "$TMP"; then
  echo ""
  echo "------------------------------------------------------------------"
  echo "PRODUCTION int4 decode fork ABSENT. To profile the PRODUCTION path you must"
  echo "install the forked vLLM wheel that provides vllm.vllm_flash_attn.flash_attn_with_int4_kvcache,"
  echo "then apply the repo patches:"
  echo "  ls $PATCH_GLOB"
  echo "  # (these patch/verify the installed forked wheel — see their headers for the wheel source)"
  echo "Until then, Step-0 profiles the IN-REPO Triton route-A kernel ($TRITON_K),"
  echo "which is a real GPU kernel and a valid proxy for the in-kernel-gather + inline-dequant design."
  echo "------------------------------------------------------------------"
fi

# --- serialize JSON ---
"$PYBIN" - "$TMP" "$OUT" <<'PY'
import json, sys
checks = {}
for l in open(sys.argv[1]):
    p = l.rstrip("\n").split("|", 2)
    if len(p) >= 2:
        checks[p[0]] = {"status": p[1], "detail": p[2] if len(p) > 2 else ""}
prod_ok = checks.get("flash_attn_with_int4_kvcache", {}).get("status") == "PASS"
triton_ok = checks.get("triton_route_a_kernel", {}).get("status") == "PASS"
gpu_ok = checks.get("pytorch_cuda_available", {}).get("status") == "PASS"
blob = {
    "checks": checks,
    "can_profile_production_kernel": bool(prod_ok and gpu_ok),
    "can_profile_triton_route_a": bool(triton_ok and gpu_ok),
    "blocked_prerequisites": [k for k, v in checks.items() if v["status"] == "FAIL"],
    "label": "GPU-measured" if gpu_ok else "blocked",
}
json.dump(blob, open(sys.argv[2], "w"), indent=2)
print(f"\n[gate] can_profile_production_kernel={blob['can_profile_production_kernel']} "
      f"can_profile_triton_route_a={blob['can_profile_triton_route_a']}")
print(f"[gate] blocked: {blob['blocked_prerequisites'] or 'none'}")
print(f"[gate] -> {sys.argv[2]}")
PY
rm -f "$TMP"
