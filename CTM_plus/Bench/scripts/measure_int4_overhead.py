#!/usr/bin/env python3
# Measure the int4_protected overhead parameters the hybrid scheduler needs.
#
# WHY
#   hybrid_kv_scheduler.py models the bf16-vs-int4 crossover from three numbers:
#     * per_token_frac   -- int4 KV+sidecar bytes / bf16 KV bytes, per token
#     * stage_per_slot_mb-- the PagedKVWriter per-active-slot staging pool
#     * fixed_tax_gb     -- load-independent int4 overhead (CUDA-graph tax +
#                           fixed sidecars + the per-slot intercept)
#   Of these, per_token_frac is well-anchored (audited ~1.8x density) but the
#   crossover DRIVER -- whether it's the per-slot staging (a per-SEQUENCE
#   crossover) or the fixed tax (a LOAD crossover) -- is not yet pinned. This
#   script measures all three on the GPU pod and prints them ready to paste into
#   the scheduler, so the crossover stops being an estimate.
#
# HOW (pod, venv-vllm)
#   It reuses the proven introspection in audit_phase6g_sidecar_overhead.py
#   (builds the real Int4ProtectedLLM, walks every writer's sidecar tensors,
#   categorizes per_token / per_block / per_slot / fixed, snapshots HBM incl.
#   non_pytorch_gb = the CUDA-graph private-pool tax). It adds:
#     1. a bf16 baseline (stock vLLM LLM) for the per_token_frac denominator and
#        the CUDA-graph delta, and
#     2. a SECOND int4 run at a different max_num_seqs, so the per_slot pools'
#        slope isolates true per-slot bytes from any fixed intercept.
#
#   derive_cost_params() -- the decomposition math -- is pure (no torch) and is
#   verified here in --selftest against synthetic ground truth. The GPU workers
#   only produce the raw (bytes, hbm) measurements that feed it.
#
# Run:
#   # CPU, anywhere -- verify the decomposition math:
#   python CTM_plus/Bench/scripts/measure_int4_overhead.py --selftest
#
#   # GPU pod -- measure and print scheduler flags (spawns workers per config):
#   python CTM_plus/Bench/scripts/measure_int4_overhead.py --run \
#       --model Qwen/Qwen2.5-7B-Instruct --max-model-len 16384 --slots 8,64
#
# Output: a paste-ready line, e.g.
#   --per-token-frac 0.55 --stage-per-slot-mb 1.2 --fixed-tax-gb 1.30

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

GB = 1024 ** 3
MB = 1024 ** 2

# Make sibling scripts importable (audit_phase6g lives next to us).
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))


# --------------------------------------------------------------------------- #
# The decomposition math -- PURE (no torch). Tested in --selftest.
# --------------------------------------------------------------------------- #
def int4_bytes_per_token_all_layers(m: dict) -> float:
    """int4_protected total KV bytes per token (summed over layers): the
    vLLM-managed int4 cache + the per_token and per_block sidecars amortized
    over the cached tokens."""
    L = m["num_layers"]
    ct = m["total_cache_tokens"]
    if ct <= 0 or L <= 0:
        raise ValueError("bad int4 measurement: total_cache_tokens/num_layers")
    cache = m["cache_bytes_per_token_per_layer"] * L
    cat = m["sidecar_by_category_bytes"]
    per_tok_side = cat["per_token"] / ct          # already summed over layers
    per_blk_side = cat["per_block"] / ct
    return cache + per_tok_side + per_blk_side


def derive_cost_params(bf16: dict, int4_a: dict, int4_b: dict | None = None) -> dict:
    """Turn raw worker measurements into the three scheduler parameters.

    bf16   : {num_layers, kv_bytes_per_token_per_layer, hbm:{non_pytorch_gb,...}}
    int4_a : int4 measurement at max_num_seqs = Sa (see worker schema)
    int4_b : (optional) a SECOND int4 measurement at a different max_num_seqs Sb;
             needed to separate stage_per_slot (slope) from the fixed intercept.
             If omitted, stage_per_slot is estimated as per_slot_bytes / Sa and
             the intercept is assumed 0 (less precise -- flagged in the result).
    """
    L = int4_a["num_layers"]
    bf16_per_tok = bf16["kv_bytes_per_token_per_layer"] * L
    if bf16_per_tok <= 0:
        raise ValueError("bad bf16 measurement: kv_bytes_per_token_per_layer")

    i4_per_tok = int4_bytes_per_token_all_layers(int4_a)
    per_token_frac = i4_per_tok / bf16_per_tok

    ps_a = int4_a["sidecar_by_category_bytes"]["per_slot"]
    Sa = int4_a["max_num_seqs"]
    if int4_b is not None:
        ps_b = int4_b["sidecar_by_category_bytes"]["per_slot"]
        Sb = int4_b["max_num_seqs"]
        if Sb == Sa:
            raise ValueError("int4_b must use a different max_num_seqs than int4_a")
        stage_per_slot = (ps_b - ps_a) / (Sb - Sa)
        per_slot_intercept = ps_a - stage_per_slot * Sa
        slope_method = f"two-point (S={Sa},{Sb})"
    else:
        stage_per_slot = ps_a / Sa if Sa else 0.0
        per_slot_intercept = 0.0
        slope_method = f"single-point (S={Sa}, intercept assumed 0)"

    # Fixed tax: CUDA-graph private-pool delta vs bf16 (measured at matched
    # config A) + fixed-category sidecars + the per-slot intercept.
    graph_delta_gb = (int4_a["hbm"]["non_pytorch_gb"] - bf16["hbm"]["non_pytorch_gb"])
    fixed_sidecars = int4_a["sidecar_by_category_bytes"]["fixed"]
    fixed_tax_gb = (max(0.0, graph_delta_gb)
                    + fixed_sidecars / GB
                    + max(0.0, per_slot_intercept) / GB)

    return {
        "per_token_frac": round(per_token_frac, 4),
        "stage_per_slot_mb": round(stage_per_slot / MB, 3),
        "fixed_tax_gb": round(fixed_tax_gb, 3),
        "_detail": {
            "bf16_bytes_per_token_all_layers": bf16_per_tok,
            "int4_bytes_per_token_all_layers": round(i4_per_tok, 1),
            "per_slot_slope_method": slope_method,
            "per_slot_intercept_mb": round(per_slot_intercept / MB, 3),
            "cuda_graph_delta_gb": round(graph_delta_gb, 3),
            "fixed_sidecars_gb": round(fixed_sidecars / GB, 3),
            "net_density_x": round(1.0 / per_token_frac, 3),
            "crossover_hint": ("LOAD-driven (fixed tax dominates -> policy #6 load-switch)"
                               if (stage_per_slot / MB) < 4.0
                               else "PER-SEQUENCE-driven (per-slot staging -> policy #4 routing)"),
        },
    }


def flags_line(params: dict) -> str:
    return (f"--per-token-frac {params['per_token_frac']} "
            f"--stage-per-slot-mb {params['stage_per_slot_mb']} "
            f"--fixed-tax-gb {params['fixed_tax_gb']}")


# --------------------------------------------------------------------------- #
# GPU workers (pod only). Lazy torch/vLLM import; reuse audit_phase6g helpers.
# --------------------------------------------------------------------------- #
def worker_bf16(model: str, max_model_len: int, gpu_util: float,
                max_num_seqs: int, out: Path) -> int:
    import torch
    from vllm import LLM, SamplingParams
    import audit_phase6g_sidecar_overhead as a6g

    torch.cuda.reset_peak_memory_stats()
    llm = LLM(model=model, max_model_len=max_model_len,
              gpu_memory_utilization=gpu_util, max_num_seqs=max_num_seqs,
              enforce_eager=False)
    llm.generate(["Hello"], SamplingParams(temperature=0.0, max_tokens=2))
    torch.cuda.synchronize()
    kv = a6g._kv_cache_summary(llm)
    hbm = a6g._hbm_snapshot()
    NB = kv.get("num_gpu_blocks") or 0
    BS = kv.get("block_size") or 0
    kv_bytes = kv.get("kv_cache_bytes") or 0     # per-layer tensor bytes
    per_tok_per_layer = (kv_bytes / (NB * BS)) if (NB and BS) else 0.0
    payload = {
        "kind": "bf16", "model": model, "max_model_len": max_model_len,
        "max_num_seqs": max_num_seqs,
        "num_layers": _num_layers(llm) or 0,
        "kv_bytes_per_token_per_layer": per_tok_per_layer,
        "num_gpu_blocks": NB, "block_size": BS,
        "hbm": hbm,
    }
    out.write_text(json.dumps(payload, indent=2))
    print(f"[bf16] wrote {out}: {per_tok_per_layer:.1f} B/tok/layer, "
          f"non_pytorch={hbm['non_pytorch_gb']:.2f} GB")
    return 0


def worker_int4(model: str, max_model_len: int, gpu_util: float,
                max_num_seqs: int, out: Path) -> int:
    import os
    os.environ.setdefault("PHASE6E_FUSED_WRITER", "1")
    import torch
    from vllm import SamplingParams
    import audit_phase6g_sidecar_overhead as a6g
    from kv_policy.int4_protected import Int4ProtectedLLM

    torch.cuda.reset_peak_memory_stats()
    llm = Int4ProtectedLLM(model=model, max_model_len=max_model_len,
                           gpu_memory_utilization=gpu_util,
                           max_num_seqs=max_num_seqs)
    llm.generate(["Hello"], SamplingParams(temperature=0.0, max_tokens=2))
    torch.cuda.synchronize()

    inner = a6g._find_inner_model(llm)
    writers = a6g._collect_writers(inner) if inner is not None else []
    if not writers:
        print("FAIL: no Int4ProtectedAttentionImpl writers found")
        return 2
    by_cat = {"per_token": 0, "per_block": 0, "per_slot": 0, "fixed": 0}
    for w in writers:
        for name, attr, scaling in a6g.SIDECAR_INVENTORY:
            by_cat[scaling] = by_cat.get(scaling, 0) + a6g._bytes_of(getattr(w, attr, None))

    kv = a6g._kv_cache_summary(llm)
    hbm = a6g._hbm_snapshot()
    NB = kv.get("num_gpu_blocks") or 0
    BS = kv.get("block_size") or 32
    kv_bytes = kv.get("kv_cache_bytes") or 0
    per_tok_per_layer = (kv_bytes / (NB * BS)) if (NB and BS) else 0.0
    payload = {
        "kind": "int4", "model": model, "max_model_len": max_model_len,
        "max_num_seqs": max_num_seqs,
        "num_layers": len(writers),
        "cache_bytes_per_token_per_layer": per_tok_per_layer,
        "sidecar_by_category_bytes": by_cat,
        "total_cache_tokens": NB * BS,
        "num_gpu_blocks": NB, "block_size": BS,
        "hbm": hbm,
    }
    out.write_text(json.dumps(payload, indent=2))
    print(f"[int4 S={max_num_seqs}] wrote {out}: per_slot="
          f"{by_cat['per_slot']/MB:.2f} MB, per_token={by_cat['per_token']/GB:.2f} GB, "
          f"non_pytorch={hbm['non_pytorch_gb']:.2f} GB")
    return 0


def _num_layers(llm):
    try:
        return llm.llm_engine.model_config.hf_config.num_hidden_layers
    except AttributeError:
        return None


# --------------------------------------------------------------------------- #
# Driver (pod): spawn the workers, derive, print scheduler flags.
# --------------------------------------------------------------------------- #
def run_driver(args) -> int:
    slots = [int(s) for s in args.slots.split(",") if s.strip()]
    if len(slots) < 1:
        print("FAIL: --slots needs >=1 value (>=2 to separate per-slot from fixed)")
        return 2
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    def spawn(kind, S):
        out = out_dir / f"{kind}_mml{args.max_model_len}_s{S}.json"
        cmd = [sys.executable, __file__, f"--worker-{kind}",
               "--model", args.model, "--max-model-len", str(args.max_model_len),
               "--gpu-util", str(args.gpu_util), "--max-num-seqs", str(S),
               "--output", str(out)]
        print(f"=== spawn {kind} (max_num_seqs={S}) ===")
        if subprocess.run(cmd, check=False).returncode != 0:
            raise SystemExit(f"worker {kind} S={S} failed")
        return json.loads(out.read_text())

    bf16 = spawn("bf16", slots[0])
    int4_a = spawn("int4", slots[0])
    int4_b = spawn("int4", slots[1]) if len(slots) >= 2 else None

    params = derive_cost_params(bf16, int4_a, int4_b)
    (out_dir / "cost_params.json").write_text(json.dumps(params, indent=2))

    print("\n" + "=" * 64)
    print("int4_protected overhead -> hybrid_kv_scheduler parameters")
    print("=" * 64)
    print(json.dumps(params, indent=2))
    print("\nPaste into the scheduler:")
    print(f"  python Bench/scripts/hybrid_kv_scheduler.py --crossover {flags_line(params)}")
    print(f"\nCrossover regime: {params['_detail']['crossover_hint']}")
    return 0


# --------------------------------------------------------------------------- #
# Selftest: verify derive_cost_params recovers known ground truth (CPU).
# --------------------------------------------------------------------------- #
def _synthesize(num_layers, bf16_bpt_layer, int4_cache_bpt_layer,
                per_token_gb, per_block_gb, stage_per_slot_mb, fixed_sidecar_gb,
                graph_gb_int4, graph_gb_bf16, total_cache_tokens, S):
    """Build the worker JSONs that WOULD be produced for a known config."""
    bf16 = {
        "num_layers": num_layers,
        "kv_bytes_per_token_per_layer": bf16_bpt_layer,
        "hbm": {"non_pytorch_gb": graph_gb_bf16},
    }
    int4 = {
        "num_layers": num_layers, "max_num_seqs": S,
        "cache_bytes_per_token_per_layer": int4_cache_bpt_layer,
        "total_cache_tokens": total_cache_tokens,
        "sidecar_by_category_bytes": {
            "per_token": per_token_gb * GB,
            "per_block": per_block_gb * GB,
            "per_slot": stage_per_slot_mb * MB * S,     # scales with slots
            "fixed": fixed_sidecar_gb * GB,
        },
        "hbm": {"non_pytorch_gb": graph_gb_int4},
    }
    return bf16, int4


def selftest() -> int:
    fails = []

    def check(name, cond):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        if not cond:
            fails.append(name)

    print("measure_int4_overhead selftest (derive_cost_params recovery)")

    # Ground truth (Qwen-like): bf16 2048 B/tok/layer (4 kvH * 128 D * 2(KV) * 2B),
    # int4 cache 512 B/tok/layer (1/4), per_token sidecar 2.0 GB, per_block 1.3 GB,
    # stage 1.2 MB/slot, fixed sidecar 0.05 GB, graph tax int4 1.10 vs bf16 0.20 GB.
    common = dict(num_layers=28, bf16_bpt_layer=2048, int4_cache_bpt_layer=512,
                  per_token_gb=2.0, per_block_gb=1.3, stage_per_slot_mb=1.2,
                  fixed_sidecar_gb=0.05, graph_gb_int4=1.10, graph_gb_bf16=0.20,
                  total_cache_tokens=1_000_000)
    bf16, int4_a = _synthesize(S=8, **common)
    _, int4_b = _synthesize(S=64, **common)
    p = derive_cost_params(bf16, int4_a, int4_b)

    # int4 per token all layers = 512*28 + (2.0+1.3)GB/1e6 tok
    #   = 14336 + (3.3*2**30)/1e6 = 14336 + 3543.3 = 17879.3 B
    # bf16 per token all layers = 2048*28 = 57344 B ; frac = 0.3118
    check("per_token_frac recovered (~0.312)", abs(p["per_token_frac"] - 0.3118) < 0.002)
    check("stage_per_slot recovered (1.2 MB)", abs(p["stage_per_slot_mb"] - 1.2) < 0.05)
    # fixed = graph delta (0.90) + fixed sidecar (0.05) + intercept(0) = 0.95
    check("fixed_tax recovered (~0.95 GB)", abs(p["fixed_tax_gb"] - 0.95) < 0.02)
    check("per-slot intercept ~0 (clean slope)",
          abs(p["_detail"]["per_slot_intercept_mb"]) < 0.05)
    check("crossover correctly flagged LOAD-driven (stage<4MB)",
          "LOAD-driven" in p["_detail"]["crossover_hint"])

    # Single-point fallback (no int4_b): stage = per_slot_total/S, intercept 0.
    p1 = derive_cost_params(bf16, int4_a, None)
    check("single-point stage_per_slot ~1.2 MB", abs(p1["stage_per_slot_mb"] - 1.2) < 0.05)
    check("single-point method flagged", "single-point" in p1["_detail"]["per_slot_slope_method"])

    # A non-zero intercept must be separated by the two-point slope.
    bad = json.loads(json.dumps(int4_a))
    bad["sidecar_by_category_bytes"]["per_slot"] += 0.5 * GB     # +0.5GB fixed lump on S=8
    bad2 = json.loads(json.dumps(int4_b))
    bad2["sidecar_by_category_bytes"]["per_slot"] += 0.5 * GB    # same lump on S=64
    p2 = derive_cost_params(bf16, bad, bad2)
    check("two-point slope ignores a shared per-slot intercept (stage still ~1.2)",
          abs(p2["stage_per_slot_mb"] - 1.2) < 0.05)
    check("the intercept is captured into fixed_tax (~0.5 GB lump)",
          abs(p2["_detail"]["per_slot_intercept_mb"] - 512.0) < 5.0)

    print(f"\n{'ALL PASS' if not fails else f'{len(fails)} FAIL: ' + ', '.join(fails)}")
    print("\nflags from the synthetic run:  " + flags_line(p))
    return 0 if not fails else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Measure int4_protected overhead for the hybrid scheduler")
    ap.add_argument("--selftest", action="store_true", help="CPU: verify the decomposition math")
    ap.add_argument("--run", action="store_true", help="pod: spawn workers + derive params")
    ap.add_argument("--worker-bf16", action="store_true")
    ap.add_argument("--worker-int4", action="store_true")
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--max-model-len", type=int, default=16384)
    ap.add_argument("--gpu-util", type=float, default=0.5)
    ap.add_argument("--max-num-seqs", type=int, default=8, help="worker mode: slots for this run")
    ap.add_argument("--slots", default="8,64", help="driver: two max_num_seqs to separate per-slot/fixed")
    ap.add_argument("--output", type=str, help="worker mode: JSON output path")
    ap.add_argument("--output-dir", default="bench_out/int4_overhead", help="driver: output dir")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if args.worker_bf16:
        return worker_bf16(args.model, args.max_model_len, args.gpu_util,
                           args.max_num_seqs, Path(args.output))
    if args.worker_int4:
        return worker_int4(args.model, args.max_model_len, args.gpu_util,
                           args.max_num_seqs, Path(args.output))
    if args.run:
        return run_driver(args)
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
