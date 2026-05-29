#!/usr/bin/env python3
# Phase 6K.13 — capacity SATURATION demo (settle: net-real 2x or bookkeeping?).
#
# Clean post-fix facts (gpu_util=0.5, A100-80GB; 6G + long-context):
#   * int4_protected TOTAL HBM = bf16 + ~4.68 GB (sidecar+graph TAX). It does
#     NOT save memory at equal util.
#   * vLLM-reported max_concurrency is ~2x (8K: 110 vs 55) — within the KV
#     budget int4 packs ~4x tokens/block. BUT that's bookkeeping.
#   * 6H was INCONCLUSIVE (short prompts never filled the budget); long-context
#     scored NOT_JUSTIFIED *on total HBM* (wrong axis for capacity).
#
# The ONLY way to know if the 2x is a NET win is to FILL prompts to ~mml and
# ramp B until a cell saturates (heavy preemption / OOM). If int4 sustains a
# clean ~2x-higher B than bf16, the capacity story is demonstrated; if int4
# saturates at a similar/lower B (the +4.7 GB overhead eats it), the 2x is
# bookkeeping and the capacity claim should be dropped.
#
# worker(cell, mml, B): B copies of a ~0.85*mml-token prompt, max_num_seqs=B;
#   record completed / OOM / preemption / HBM / agg_tps + vLLM max_concurrency.
# driver: sweep B per cell, find the largest B that completes with no OOM and
#   ~no preemption, and report int4/bf16 ratio.
#
# Usage:
#   python CTM_plus/Bench/scripts/phase6k13_capacity_demo.py --selftest         # CPU
#   CELL=protected python CTM_plus/Bench/scripts/phase6k13_capacity_demo.py \
#     --worker --mml 8192 --batch 110
#   python CTM_plus/Bench/scripts/phase6k13_capacity_demo.py --mml 8192 2>&1 | tee /tmp/phase6k13.log

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

CELLS = ["bf16", "protected"]        # add "naive" via --cells if wanted
NAIVE_MASK_DEFAULT = "/workspace/dev/build-logs/qwen2_5_7b_protect_mask_naive.pt"

# Default B sweeps per mml, straddling bf16(≈55/26/12) and int4(≈110/53/24) conc.
DEFAULT_B = {
    8192:  [48, 56, 72, 96, 112, 128],
    16384: [24, 28, 40, 52, 60, 72],
    32768: [12, 16, 24, 28, 36],
}


def _long_prompt(target_tokens):
    # ~16 tokens/sentence; the worker also truncates to fit under mml.
    n = max(20, target_tokens // 16)
    return "Document: " + " ".join(
        f"Fact {i}: the town ledger recorded routine activity that week."
        for i in range(n)
    ) + "\n\nSummarize the document in one sentence."


def _sched_counters(llm):
    """Best-effort cumulative preemption count from the vLLM scheduler."""
    try:
        sched = llm.llm_engine.scheduler[0]
        for attr in ("num_cumulative_preemption", "num_preempted", "preemption_count"):
            v = getattr(sched, attr, None)
            if isinstance(v, int):
                return v
    except Exception:
        pass
    return 0


def _max_concurrency(llm, mml):
    try:
        cc = llm.llm_engine.cache_config
        nb = getattr(cc, "num_gpu_blocks", None)
        bs = getattr(cc, "block_size", None)
        if nb and bs:
            return round(nb * bs / mml, 1)
    except Exception:
        pass
    return None


def run_worker(mml, batch):
    import torch
    cell = os.environ.get("CELL", "protected")
    eager = os.environ.get("ENFORCE_EAGER", "0").strip() in ("1", "true", "yes")
    os.environ.pop("PHASE6B3_FORCE_EAGER", None)
    if cell == "naive":
        os.environ["PHASE6J_NAIVE_FORCE_ZERO"] = "1"
        os.environ["PROTECT_MASK_PATH"] = os.environ.get("NAIVE_MASK_PATH", NAIVE_MASK_DEFAULT)
    elif cell == "protected":
        os.environ["PHASE6J_NAIVE_FORCE_ZERO"] = "0"
        os.environ.pop("PROTECT_MASK_PATH", None)
    # int4 cells: bench-style hook ownership — disable the factory auto-hook.
    os.environ.setdefault("PHASE6E_FUSED_WRITER", "1")

    util = float(os.environ.get("GPU_UTIL", "0.5"))
    out = os.environ.get("OUTPUT", f"/tmp/phase6k13_{cell}_mml{mml}_B{batch}.json")
    rec = {"cell": cell, "mml": mml, "batch": batch, "gpu_util": util,
           "oom": False, "completed": 0, "preempts": 0, "hbm_gb": None,
           "agg_tps": None, "max_concurrency": None, "error": None}

    from vllm import SamplingParams
    try:
        if cell == "bf16":
            from vllm import LLM
            llm = LLM(model="Qwen/Qwen2.5-7B-Instruct", max_model_len=mml,
                      gpu_memory_utilization=util, dtype="bfloat16",
                      max_num_seqs=batch, enforce_eager=eager)
        else:
            os.environ["PHASE6K10_AUTO_HOOK"] = "0"   # bench installs its own hook
            from kv_policy.int4_protected import Int4ProtectedLLM
            from kv_policy.phase6b2_precapture_hook import (
                install_int4_protected_precapture_hook, _collect_writers,
                _collect_impls, _resolve_inner_model, _resolve_model_runner)
            llm = Int4ProtectedLLM(model="Qwen/Qwen2.5-7B-Instruct", max_model_len=mml,
                                   gpu_memory_utilization=util, max_num_seqs=batch,
                                   enforce_eager=eager)
            try:
                m = _resolve_inner_model(llm)
                install_int4_protected_precapture_hook(
                    _resolve_model_runner(llm), _collect_writers(m), impls=_collect_impls(m))
            except Exception as e:
                rec["error"] = f"hook: {type(e).__name__}: {e}"
    except Exception as exc:
        rec["oom"] = "out of memory" in str(exc).lower()
        rec["error"] = f"init: {str(exc)[:120]}"
        Path(out).write_text(json.dumps(rec, indent=2))
        print(f"[6k13 {cell} mml{mml} B{batch}] INIT FAIL oom={rec['oom']} {rec['error']}", flush=True)
        return 0

    rec["max_concurrency"] = _max_concurrency(llm, mml)
    sp = SamplingParams(temperature=0.0, max_tokens=8)
    prompt = _long_prompt(int(mml * 0.8))
    # Guard: truncate the prompt to fit (prompt + gen) under mml regardless of
    # the token estimate — vLLM errors on over-length prompts otherwise.
    try:
        tk = llm.get_tokenizer()
        ids = tk.encode(prompt)
        cap = mml - sp.max_tokens - 64
        if len(ids) > cap:
            prompt = tk.decode(ids[:cap])
            ids = ids[:cap]
        rec["prompt_tokens"] = len(ids)
    except Exception:
        rec["prompt_tokens"] = None
    pre = _sched_counters(llm)
    try:
        torch.cuda.reset_peak_memory_stats()
        t0 = time.time()
        outs = llm.generate([prompt] * batch, sp)
        dt = time.time() - t0
        rec["completed"] = sum(1 for o in outs if o.outputs and o.outputs[0].text)
        n_out = sum(len(o.outputs[0].token_ids) for o in outs if o.outputs)
        rec["agg_tps"] = round(n_out / dt, 1) if dt > 0 else None
        rec["hbm_gb"] = round(torch.cuda.max_memory_allocated() / 1e9, 2)
        rec["preempts"] = _sched_counters(llm) - pre
    except Exception as exc:
        rec["oom"] = "out of memory" in str(exc).lower()
        rec["error"] = f"gen: {str(exc)[:120]}"

    Path(out).write_text(json.dumps(rec, indent=2))
    print(f"[6k13 {cell} mml{mml} B{batch}] prompt_tok={rec.get('prompt_tokens')} "
          f"completed={rec['completed']}/{batch} oom={rec['oom']} "
          f"preempts={rec['preempts']} hbm={rec['hbm_gb']} tps={rec['agg_tps']} "
          f"max_conc={rec['max_concurrency']}", flush=True)
    return 0


def run_driver(mml, cells, b_list):
    rows = []
    for cell in cells:
        for B in b_list:
            out = f"/tmp/phase6k13_{cell}_mml{mml}_B{B}.json"
            env = dict(os.environ)
            env.update({"CELL": cell, "OUTPUT": out})
            env.setdefault("PHASE6E_FUSED_WRITER", "1")
            env.pop("PHASE6B3_FORCE_EAGER", None)
            print(f"\n=== 6k13: cell={cell} mml={mml} B={B} ===", flush=True)
            subprocess.run([sys.executable, __file__, "--worker",
                            "--mml", str(mml), "--batch", str(B)], env=env, check=False)
            try:
                rows.append(json.loads(Path(out).read_text()))
            except Exception as e:
                rows.append({"cell": cell, "batch": B, "error": str(e)[:60]})

    print("\n" + "=" * 96)
    print(f"PHASE 6K.13 — capacity saturation demo (mml={mml}, prompt≈0.85*mml, "
          f"gpu_util={os.environ.get('GPU_UTIL','0.5')})")
    print("=" * 96)
    print(f"  {'cell':>10} {'B':>5} | {'completed':>9} {'oom':>5} {'preempts':>8} "
          f"{'HBM GB':>7} {'agg_tps':>8} {'max_conc':>8}")
    print("  " + "-" * 80)
    clean_maxB = {}   # largest B with no OOM and ~no preemption
    for r in rows:
        if r.get("error") and r.get("completed", 0) == 0 and not r.get("oom"):
            print(f"  {r.get('cell','?'):>10} {r.get('batch','?'):>5} | ERROR {r['error']}")
            continue
        cell, B = r["cell"], r["batch"]
        clean = (not r.get("oom")) and r.get("completed") == B and (r.get("preempts") or 0) == 0
        if clean:
            clean_maxB[cell] = max(clean_maxB.get(cell, 0), B)
        tag = "  <-- OOM" if r.get("oom") else ("  <-- preempt" if (r.get("preempts") or 0) > 0 else "")
        print(f"  {cell:>10} {B:>5} | {str(r.get('completed'))+'/'+str(B):>9} "
              f"{str(r.get('oom')):>5} {r.get('preempts') or 0:>8} "
              f"{(r.get('hbm_gb') or 0):>7} {(r.get('agg_tps') or 0):>8} "
              f"{(r.get('max_concurrency') or 0):>8}{tag}")
    print("\n  clean max-B (all complete, no OOM, no preempt):", clean_maxB)
    if "bf16" in clean_maxB and "protected" in clean_maxB and clean_maxB["bf16"]:
        ratio = clean_maxB["protected"] / clean_maxB["bf16"]
        print(f"  DEMONSTRATED capacity ratio (protected/bf16) = {ratio:.2f}x")
        print("   ~2x => the audited 2x is a NET win (real capacity story).")
        print("   ~1x => bookkeeping; the +4.7GB sidecar tax eats the budget (drop the capacity claim).")
    print("=" * 96, flush=True)
    return 0


def _selftest():
    for mml in (8192, 16384):
        p = _long_prompt(int(mml * 0.85))
        chars = len(p); est = chars // 4
        assert "Summarize" in p
        print(f"  long_prompt(mml={mml}): chars={chars} ~tok={est} "
              f"(target≈{int(mml*0.85)}; headroom@util-dependent)")
    print("SELFTEST PASS")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--worker", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--mml", type=int, default=8192)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--cells", default=",".join(CELLS))
    ap.add_argument("--b-list", default="", help="comma list; default per-mml sweep")
    args = ap.parse_args()
    if args.selftest:
        return _selftest()
    if args.worker:
        return run_worker(args.mml, args.batch)
    b_list = [int(x) for x in args.b_list.split(",")] if args.b_list else DEFAULT_B.get(args.mml, [32, 48, 64])
    return run_driver(args.mml, args.cells.split(","), b_list)


if __name__ == "__main__":
    raise SystemExit(main())
