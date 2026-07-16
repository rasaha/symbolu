#!/usr/bin/env bash
# KVPro V3 Step-0 — Part C/D: CUDA-event timing of the IN-REPO Triton route-A fused kernel (POD-ONLY,
# HW-UNTESTED). This path does NOT need the external production fork — it times the real, present kernel
# CTM_plus/KVPolicy/kv_policy/int4_fused_attention_kernel.py. A fused kernel is one launch, so per-stage
# splitting is done by DIFFERENTIAL ablation (Part D): protect-overlay on vs off isolates the protect
# stage. Emits cuda_events.json {stage_wall_ms, per_ctx}. Writes label=UNAVAILABLE (never fabricated) if
# the kernel/API is not reachable.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; ROOT="$(cd "$HERE/../.." && pwd)"
PYBIN="${PYBIN:-python3}"; OUTDIR="${OUTDIR:-$HERE/runs}"; mkdir -p "$OUTDIR"
OUT="${OUT:-$OUTDIR/cuda_events.json}"
export KVV3_ROOT="$ROOT" KVV3_OUT="$OUT" KVV3_CTXS="${CONTEXTS:-4096 16384 32768}" KVV3_ITERS="${ITERS:-50}"

"$PYBIN" - <<'PY'
import json, os, sys
OUT = os.environ["KVV3_OUT"]; ROOT = os.environ["KVV3_ROOT"]
ctxs = [int(c) for c in os.environ["KVV3_CTXS"].split()]; iters = int(os.environ["KVV3_ITERS"])
sys.path.insert(0, os.path.join(ROOT, "CTM_plus", "KVPolicy", "kv_policy"))

def bail(msg):
    json.dump({"label": "UNAVAILABLE", "error": msg, "stage_wall_ms": {}}, open(OUT, "w"), indent=2)
    print(f"[UNAVAILABLE] {msg} -> {OUT}"); sys.exit(3)

try:
    import torch
except Exception as e:  # noqa: BLE001
    bail(f"torch import failed: {e}")
if not torch.cuda.is_available():
    bail("no CUDA GPU")
try:
    import int4_fused_attention_kernel as RA          # the in-repo Triton route-A kernel wrapper
except Exception as e:  # noqa: BLE001
    bail(f"cannot import int4_fused_attention_kernel: {e}")

entry = getattr(RA, "fused_protected_k_decode_attention_gather", None) or \
        getattr(RA, "fused_protected_k_decode_attention", None)
if entry is None:
    bail("route-A entry (fused_protected_k_decode_attention[_gather]) not found; adapt this harness to "
         "the kernel's current signature before timing (kept honest rather than guessing).")

def ev_time(fn, n):
    torch.cuda.synchronize(); s = torch.cuda.Event(True); e = torch.cuda.Event(True)
    for _ in range(3): fn()                                  # warmup
    torch.cuda.synchronize(); s.record()
    for _ in range(n): fn()
    e.record(); torch.cuda.synchronize()
    return s.elapsed_time(e) / n

# The operator must provide a builder that returns kwargs for `entry` at a given context length. We do
# NOT hand-fabricate the packed-int4 + block-table contract here (it is version-specific); instead we look
# for an in-repo helper. If absent, emit UNAVAILABLE with the exact next step.
build = getattr(RA, "make_synthetic_inputs", None) or getattr(RA, "_demo_inputs", None)
if build is None:
    bail("no in-repo synthetic-input builder (RA.make_synthetic_inputs) — provide one that matches the "
         "current kernel signature, then re-run. Timing was NOT fabricated.")

per_ctx = {}
for ctx in ctxs:
    try:
        kw = build(context_len=ctx)
        full = ev_time(lambda: entry(**kw), iters)
        kw_np = dict(kw); kw_np["protect_mask"] = None if "protect_mask" in kw_np else kw_np.get("protect_mask")
        noprot = ev_time(lambda: entry(**kw_np), iters) if "protect_mask" in kw else None
        per_ctx[str(ctx)] = {"fused_ms": round(full, 4),
                             "protect_ablation_ms": round(full - noprot, 4) if noprot else "UNAVAILABLE"}
    except Exception as e:  # noqa: BLE001
        per_ctx[str(ctx)] = {"error": str(e)}
# roll a representative stage_wall_ms from the mid context
mid = str(ctxs[len(ctxs)//2])
prot = per_ctx.get(mid, {}).get("protect_ablation_ms", "UNAVAILABLE")
blob = {"label": "GPU-measured", "kernel": "int4_fused_attention_kernel (route-A, Triton)",
        "per_ctx": per_ctx, "stage_wall_ms": {"attention": per_ctx.get(mid, {}).get("fused_ms", "UNAVAILABLE"),
        "protect": prot}, "note": "fused kernel; protect isolated by ablation. gather/dequant are inlined "
        "and not separable without ncu source counters."}
json.dump(blob, open(OUT, "w"), indent=2)
print(f"[GPU-measured] route-A CUDA-event timing -> {OUT}")
PY
