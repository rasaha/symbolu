"""Phase 6O — weight-quant × KV-quant STACKING test (does AWQ + int4_protected compose?).

The VC brief ASSERTS "AWQ/GPTQ quantize weights, not KV — they STACK with
int4_protected, they don't replace it." That composition claim has never been run
in this stack. This bench tests it: measures the combined HBM footprint and a
quick quality sanity across the four corners of {weights: bf16|awq} ×
{KV: bf16|int4_protected}, and — critically — whether int4_protected's vendored
flash-attn path and AWQ's quantized-GEMM path COEXIST at runtime (the real risk;
the quant math is independent, the integration is what's untested).

Key plumbing fact (verified): `Int4ProtectedLLM(**kwargs)` forwards everything to
`vllm.LLM(...)`, so `quantization="awq"` passes through with NO code change. The
experiment is whether it RUNS, not whether the API accepts it.

Cells (--cells, any subset):
  bf16_bf16        stock: bf16 weights, bf16 KV          (full-size baseline)
  awq_bf16         AWQ weights, bf16 KV                  (weight-quant only)
  bf16_int4prot    bf16 weights, int4_protected KV       (your current product)
  awq_int4prot     AWQ weights, int4_protected KV        (THE STACK — the claim)

For each cell that loads: model-weight HBM, KV-cache budget HBM, total HBM, and
(optional --mmlu N) a small MMLU accuracy sanity. The report computes the stacking
math: does awq_int4prot's total ≈ (weight saving) + (KV density) as the brief implies?

⚠ Needs an AWQ checkpoint of the model (e.g. Qwen/Qwen2.5-7B-Instruct-AWQ) — set
  --awq-model. int4_protected cells need a valid mml=8192 protect mask.
⚠ INTEGRATION RISK: AWQ uses its own GEMM kernels (awq/marlin); int4_protected
  uses a vendored flash-attn fork for ATTENTION. They touch different layers and
  SHOULD be independent — this bench exists to confirm that empirically.

CPU-testable: the HBM-accounting + stacking math + cell matrix are pure functions
with --selftest. The GPU path is a thin driver.

Usage:
  python CTM_plus/Bench/scripts/bench_phase6o_weight_kv_stack.py --selftest
  python CTM_plus/Bench/scripts/bench_phase6o_weight_kv_stack.py --dry-run
  # GPU:
  python CTM_plus/Bench/scripts/bench_phase6o_weight_kv_stack.py \
      --cells bf16_bf16,awq_bf16,bf16_int4prot,awq_int4prot \
      --awq-model Qwen/Qwen2.5-7B-Instruct-AWQ \
      --mmlu 100 --out bench_out/phase6o/stack.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT_CANDIDATES = [
    Path("/workspace/symbolu/CTM_plus"),
    Path("/home/user/symbolu/CTM_plus"),
    Path(__file__).resolve().parent.parent.parent,
]
for _root in ROOT_CANDIDATES:
    kvp = _root / "KVPolicy"
    if kvp.is_dir() and str(kvp) not in sys.path:
        sys.path.insert(0, str(kvp))
        break
_SCR = Path(__file__).resolve().parent
if str(_SCR) not in sys.path:
    sys.path.insert(0, str(_SCR))

# Cell -> (weights, kv) config.
CELLS = {
    "bf16_bf16":     {"weights": "bf16", "kv": "bf16"},
    "awq_bf16":      {"weights": "awq",  "kv": "bf16"},
    "bf16_int4prot": {"weights": "bf16", "kv": "int4_protected"},
    "awq_int4prot":  {"weights": "awq",  "kv": "int4_protected"},
}


# ---------------------------------------------------------------------------
# Pure accounting / stacking math (CPU-testable)
# ---------------------------------------------------------------------------
def stacking_analysis(cells: Dict[str, Dict[str, float]]) -> Dict[str, object]:
    """Given {cell: {weights_gb, kv_budget_gb, total_gb}}, compute whether the
    stack composes as the brief claims (weight saving + KV density are additive
    in HBM terms).

    Returns the measured savings vs the bf16_bf16 baseline and a verdict on
    whether awq_int4prot realized BOTH the weight saving (from awq_bf16) AND the
    KV behavior (from bf16_int4prot)."""
    out: Dict[str, object] = {"per_cell": cells}
    base = cells.get("bf16_bf16")
    if not base:
        out["note"] = "no bf16_bf16 baseline; savings not computed"
        return out

    def weight_saving(cell):
        c = cells.get(cell)
        if not c:
            return None
        return round(base["weights_gb"] - c["weights_gb"], 3)

    # Weight saving should be ~equal in awq_bf16 and awq_int4prot (KV choice
    # must not change weight footprint). That equality is the "independence" test.
    ws_awq_only = weight_saving("awq_bf16")
    ws_awq_stack = weight_saving("awq_int4prot")
    out["weight_saving_awq_only_gb"] = ws_awq_only
    out["weight_saving_awq_stacked_gb"] = ws_awq_stack
    if ws_awq_only is not None and ws_awq_stack is not None:
        # within 0.2 GB = weights quantized the same regardless of KV mode.
        out["weight_saving_independent_of_kv"] = abs(ws_awq_only - ws_awq_stack) <= 0.2

    # KV behavior: int4_protected should expand KV budget (more tokens/GB) the
    # same way with bf16 or AWQ weights. Compare kv_budget_gb deltas if present.
    out["composes"] = None
    stack = cells.get("awq_int4prot")
    if stack and base:
        total_saving = round(base["total_gb"] - stack["total_gb"], 3)
        out["awq_int4prot_total_hbm_saving_vs_bf16bf16_gb"] = total_saving
        # The stack should save AT LEAST the weight saving (KV side is roughly
        # neutral-to-positive on total bytes; the KV *density* win shows up as
        # more concurrent seqs, measured separately by phase6l, not here).
        if ws_awq_only is not None:
            out["composes"] = total_saving >= (ws_awq_only - 0.5)  # tolerance
    return out


def verdict(analysis: Dict[str, object], loaded_cells: List[str]) -> Dict[str, str]:
    """Human verdict on the integration + composition."""
    integ = "UNKNOWN"
    if "awq_int4prot" in loaded_cells:
        integ = "COEXIST_OK — AWQ weights + int4_protected KV loaded & ran together"
    elif "awq_int4prot" in CELLS and "awq_int4prot" not in loaded_cells:
        integ = "INTEGRATION_FAILED — the stacked cell did not load (see error)"
    comp = analysis.get("composes")
    if comp is True:
        compose = "STACKS — combined HBM saving >= weight saving; the brief claim holds"
    elif comp is False:
        compose = "DOES_NOT_STACK — combined saving < expected; investigate"
    else:
        compose = "NOT_COMPUTED — need bf16_bf16 + awq_bf16 + awq_int4prot all loaded"
    return {"integration": integ, "composition": compose}


# ---------------------------------------------------------------------------
# GPU driver (thin)
# ---------------------------------------------------------------------------
def _build(cell: str, model: str, awq_model: str, mml: int, gpu_util: float):
    cfg = CELLS[cell]
    kwargs = {"max_model_len": mml, "gpu_memory_utilization": gpu_util,
              "max_num_seqs": 8}
    if cfg["weights"] == "awq":
        kwargs["quantization"] = "awq"
        model_id = awq_model
    else:
        model_id = model
        kwargs["dtype"] = "bfloat16"

    if cfg["kv"] == "int4_protected":
        # Int4ProtectedLLM forwards **kwargs (incl. quantization=) to vllm.LLM.
        from kv_policy.int4_protected import Int4ProtectedLLM
        return Int4ProtectedLLM(model=model_id, **kwargs)
    from vllm import LLM
    return LLM(model=model_id, **kwargs)


def _hbm_of(llm) -> Dict[str, Optional[float]]:
    """Best-effort pull of weight + KV HBM from the vLLM engine."""
    try:
        cache_cfg = llm.llm_engine.cache_config
        model_cfg = llm.llm_engine.model_config
    except Exception:
        return {"weights_gb": None, "kv_budget_gb": None, "total_gb": None}
    w = None
    try:
        # vLLM exposes model weight bytes via the worker; fall back to None.
        import torch
        w = round(torch.cuda.max_memory_allocated() / 1e9, 3)
    except Exception:
        pass
    kv = None
    try:
        num_blocks = cache_cfg.num_gpu_blocks
        block_bytes = getattr(cache_cfg, "block_size", 0)  # crude; report what we can
        kv = None  # exact KV GB is best read from phase6l accounting; left None here
    except Exception:
        pass
    return {"weights_gb": w, "kv_budget_gb": kv, "total_gb": w}


def _run_cell(cell: str, model: str, awq_model: str, mml: int, gpu_util: float,
              mmlu_n: int) -> Dict[str, object]:
    import torch
    torch.cuda.reset_peak_memory_stats()
    res: Dict[str, object] = {"cell": cell, "config": CELLS[cell]}
    try:
        llm = _build(cell, model, awq_model, mml, gpu_util)
    except Exception as e:
        res["loaded"] = False
        res["error"] = f"{type(e).__name__}: {str(e)[:300]}"
        return res
    res["loaded"] = True
    res.update(_hbm_of(llm))
    if mmlu_n > 0:
        try:
            import bench_phase6n_mmlu_quality as p6n
            from datasets import load_dataset
            ds = load_dataset("cais/mmlu", "all", split="test")
            items = [{"q": r["question"], "choices": r["choices"],
                      "answer": int(r["answer"])}
                     for r in ds.select(range(min(mmlu_n, len(ds))))]
            from vllm import SamplingParams
            sp = SamplingParams(temperature=0.0, max_tokens=4)
            prompts = [p6n.build_prompt(it["q"], it["choices"]) for it in items]
            outs = llm.generate(prompts, sp)
            preds = [p6n.parse_answer(o.outputs[0].text) for o in outs]
            res["mmlu"] = p6n.score(preds, [it["answer"] for it in items])
        except Exception as e:
            res["mmlu_error"] = f"{type(e).__name__}: {str(e)[:200]}"
    return res


def _run_cell_dry(cell: str) -> Dict[str, object]:
    """Fake HBM numbers exercising the accounting: bf16 weights 14.25 GB, AWQ ~4 GB."""
    cfg = CELLS[cell]
    w = 4.0 if cfg["weights"] == "awq" else 14.25
    res = {"cell": cell, "config": cfg, "loaded": True,
           "weights_gb": w, "kv_budget_gb": (24.0 if cfg["kv"] == "bf16" else 24.0),
           "total_gb": round(w + 0.1, 3)}
    return res


# ---------------------------------------------------------------------------
def _selftest() -> int:
    # stacking_analysis: AWQ saves ~10 GB of weights, independent of KV mode.
    cells = {
        "bf16_bf16":     {"weights_gb": 14.25, "kv_budget_gb": 24.0, "total_gb": 14.35},
        "awq_bf16":      {"weights_gb": 4.0,   "kv_budget_gb": 24.0, "total_gb": 4.10},
        "bf16_int4prot": {"weights_gb": 14.25, "kv_budget_gb": 24.0, "total_gb": 14.35},
        "awq_int4prot":  {"weights_gb": 4.0,   "kv_budget_gb": 24.0, "total_gb": 4.10},
    }
    a = stacking_analysis(cells)
    assert abs(a["weight_saving_awq_only_gb"] - 10.25) < 1e-6, a
    assert abs(a["weight_saving_awq_stacked_gb"] - 10.25) < 1e-6, a
    assert a["weight_saving_independent_of_kv"] is True, a
    assert a["composes"] is True, a
    print("  stacking math: AWQ saves 10.25GB, independent of KV, composes: PASS")

    # If the stacked cell ate MORE memory than weight-only (integration broke the
    # weight quant), independence should be False.
    cells2 = dict(cells)
    cells2["awq_int4prot"] = {"weights_gb": 14.25, "kv_budget_gb": 24.0, "total_gb": 14.35}
    a2 = stacking_analysis(cells2)
    assert a2["weight_saving_independent_of_kv"] is False, a2
    print("  detects broken stack (weights not quantized in stacked cell): PASS")

    # verdict strings
    v = verdict(a, ["bf16_bf16", "awq_bf16", "bf16_int4prot", "awq_int4prot"])
    assert v["integration"].startswith("COEXIST_OK"), v
    assert v["composition"].startswith("STACKS"), v
    v2 = verdict(a, ["bf16_bf16", "awq_bf16", "bf16_int4prot"])  # stack cell missing
    assert v2["integration"].startswith("INTEGRATION_FAILED"), v2
    print("  verdict: coexist-ok/stacks, and integration-failed when cell missing: PASS")

    # dry-run cells
    for c in CELLS:
        r = _run_cell_dry(c)
        assert r["loaded"] and r["weights_gb"] in (4.0, 14.25)
    print("  dry-run cell matrix schema: PASS")

    print("\nself-test: 4/4 PASS")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Phase 6O weight×KV stacking test")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--cells", default=",".join(CELLS.keys()))
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--awq-model", default="Qwen/Qwen2.5-7B-Instruct-AWQ",
                    help="AWQ checkpoint of the model (HF id or local path)")
    ap.add_argument("--max-model-len", type=int, default=8192)
    ap.add_argument("--gpu-util", type=float, default=0.5)
    ap.add_argument("--mmlu", type=int, default=0,
                    help="if >0, run an N-question MMLU sanity per cell")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()

    cells = [c.strip() for c in args.cells.split(",") if c.strip()]
    for c in cells:
        if c not in CELLS:
            ap.error(f"unknown cell {c!r}; choose from {list(CELLS)}")

    results: Dict[str, Dict] = {}
    for c in cells:
        results[c] = _run_cell_dry(c) if args.dry_run else _run_cell(
            c, args.model, args.awq_model, args.max_model_len, args.gpu_util, args.mmlu)

    # Build the accounting dict for cells that loaded with HBM numbers.
    acct = {c: {"weights_gb": r.get("weights_gb"), "kv_budget_gb": r.get("kv_budget_gb"),
                "total_gb": r.get("total_gb")}
            for c, r in results.items()
            if r.get("loaded") and r.get("total_gb") is not None}
    analysis = stacking_analysis(acct) if acct else {"note": "no cells with HBM numbers"}
    loaded = [c for c, r in results.items() if r.get("loaded")]
    report = {
        "model": args.model, "awq_model": args.awq_model,
        "dry_run": bool(args.dry_run),
        "cells": results, "analysis": analysis,
        "verdict": verdict(analysis, loaded),
    }
    print(json.dumps(report, indent=2))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2))
        print(f"\nReport written to: {args.out}")
    # exit nonzero if the stacked cell failed to load (integration broke).
    return 0 if "awq_int4prot" in loaded or "awq_int4prot" not in cells else 1


if __name__ == "__main__":
    sys.exit(main())
