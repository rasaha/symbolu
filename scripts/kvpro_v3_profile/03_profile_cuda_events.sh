#!/usr/bin/env bash
# KVPro V3 Step-0 — Part C/D: CUDA-event timing of the IN-REPO Triton route-A fused kernel (POD-ONLY,
# HARDWARE-UNTESTED). No external fork needed. Inputs are built by route_a_builder.make_kernel_inputs
# (the writer-faithful packed view adapted to the kernel's signed/offset/head-major contract, numerically
# CPU-validated against the sketch oracle). A fused kernel is one launch, so per-stage splitting is done by
# DIFFERENTIAL ablation (Part D): protect-overlay on vs off isolates the protect stage. Emits
# cuda_events.json {stage_wall_ms, per_ctx}. Writes label=UNAVAILABLE (never fabricated) if GPU/kernel/
# Triton is missing.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYBIN="${PYBIN:-python3}"; OUTDIR="${OUTDIR:-$HERE/runs}"; mkdir -p "$OUTDIR"
export KVV3_HERE="$HERE" KVV3_OUT="${OUT:-$OUTDIR/cuda_events.json}"
export KVV3_CTXS="${CONTEXTS:-4096 16384 32768}" KVV3_ITERS="${ITERS:-50}"
export KVV3_HKV="${HKV:-4}" KVV3_D="${HEAD_DIM:-128}" KVV3_G="${GQA_G:-7}" KVV3_BS="${BS:-32}"

"$PYBIN" - <<'PY'
import json, os, sys
OUT = os.environ["KVV3_OUT"]
sys.path.insert(0, os.environ["KVV3_HERE"])
ctxs = [int(c) for c in os.environ["KVV3_CTXS"].split()]; iters = int(os.environ["KVV3_ITERS"])
H_kv, D, G, BS = (int(os.environ[k]) for k in ("KVV3_HKV", "KVV3_D", "KVV3_G", "KVV3_BS"))

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
    import route_a_builder as RB
    import int4_fused_attention_kernel as RA
except Exception as e:  # noqa: BLE001
    bail(f"import failed: {e}")
if not getattr(RA, "_HAVE_TRITON", False):
    bail("Triton not available (GPU build) — route-A kernel cannot launch")
entry = getattr(RA, "fused_protected_k_decode_attention", None)
if entry is None:
    bail("fused_protected_k_decode_attention not found in the route-A kernel module")

def call(kw):
    return entry(kw["q"], kw["k_packed"], kw["k_scale"], kw["k_offset"], kw["k_fp16"],
                 kw["protect_mask"], kw["v_packed"], kw["v_scale"], kw["v_offset"],
                 group_size_k=kw["group_size_k"], group_size_v=kw["group_size_v"], asymmetric=kw["asymmetric"])

def ev_ms(fn, n):
    for _ in range(3): fn()                              # warmup
    torch.cuda.synchronize(); s = torch.cuda.Event(True); e = torch.cuda.Event(True)
    s.record()
    for _ in range(n): fn()
    e.record(); torch.cuda.synchronize()
    return s.elapsed_time(e) / n

per_ctx = {}
for ctx in ctxs:
    try:
        kw, meta = RB.make_kernel_inputs(ctx, H_kv=H_kv, D=D, G=G, BS=BS, seed=0, device="cuda")
        full = ev_ms(lambda: call(kw), iters)
        kw_np = dict(kw); kw_np["protect_mask"] = torch.zeros_like(kw["protect_mask"])   # ablation: protect off
        noprot = ev_ms(lambda: call(kw_np), iters)
        per_ctx[str(ctx)] = {"fused_ms": round(full, 4), "no_protect_ms": round(noprot, 4),
                             "protect_ablation_ms": round(full - noprot, 4), "S_kv": meta["S_kv"], "iters": iters}
        print(f"  ctx={ctx:6} fused={full:.4f}ms no_protect={noprot:.4f}ms protect_delta={full-noprot:+.4f}ms")
    except Exception as e:  # noqa: BLE001
        per_ctx[str(ctx)] = {"error": str(e)}
        print(f"  ctx={ctx}: [error] {e}")

mid = str(ctxs[len(ctxs) // 2])
prot = per_ctx.get(mid, {}).get("protect_ablation_ms", "UNAVAILABLE")
blob = {"label": "GPU-measured", "kernel": "int4_fused_attention_kernel.fused_protected_k_decode_attention",
        "geom": {"H_kv": H_kv, "D": D, "G": G, "BS": BS}, "per_ctx": per_ctx,
        "stage_wall_ms": {"attention": per_ctx.get(mid, {}).get("fused_ms", "UNAVAILABLE"), "protect": prot},
        "note": "fused kernel; protect isolated by ablation (protect_mask off). gather/dequant are inlined "
                "and not separable without ncu source counters. Inputs CPU-validated vs the sketch oracle."}
json.dump(blob, open(OUT, "w"), indent=2)
print(f"[GPU-measured] route-A CUDA-event timing -> {OUT}")
PY
