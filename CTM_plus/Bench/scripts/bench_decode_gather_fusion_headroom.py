#!/usr/bin/env python3
# Decode-path GATHER-vs-KERNEL fusion-headroom profiler.
#
# Before spending a CUDA cycle on the "6F" fusion (have the int4 kernel read the
# packed nibbles + 5 sidecars from the paged pool DIRECTLY via block_table —
# gather+dequant+splice in-kernel — instead of the Python pre-gather that
# materializes contiguous buffers first), this SIZES the win.
#
# Important context (verified in phase5b_backend_install.py):
#   * The DEQUANT is ALREADY in-kernel — the kernel gets packed int4 + sidecars
#     (`k_packed_int4=...`) and reconstructs bf16 in registers; NO bf16 KV is
#     written to HBM. That fusion is done.
#   * What remains is the GATHER: `get_packed_view_batched` (region
#     `*.view_gather`) materializes the scattered paged int4 + 5 sidecars into
#     contiguous buffers, plus the splice / bf16_backing / kernel_prep — the
#     pre-kernel overhead an in-kernel paged gather would eliminate or absorb.
#
# It turns on the existing DecodeProfiler (real CUDA-event GPU timing) and
# reports, in GPU time:
#     FUSEABLE  = view_gather + splice + bf16_backing + kernel_prep
#     KERNEL    = flash_attn_with_int4_kvcache  (irreducible attention compute)
#     headroom% = FUSEABLE / (FUSEABLE + KERNEL)   <- best-case recoverable
# and a go/no-go verdict. (host-side `seqids_blockids` is reported separately —
# it's an identity-resolution cost fixed by vectorization, not by kernel fusion.)
#
# Run it at the regime that matters — Llama-3.1-8B at LONG context (the read-skip
# crossover regime), B=1 (read-skip is batch=1):
#   M=NousResearch/Meta-Llama-3.1-8B-Instruct
#   export PROTECT_MASK_PATH=/workspace/dev/build-logs/meta_llama_3_1_8b_instruct_protect_mask_4pct.pt
#   python Bench/scripts/bench_decode_gather_fusion_headroom.py --model $M \
#       --context-tokens 32000 --gen 64 --batch 1
#   # sweep context to see how the split moves with length:
#   for C in 8000 16000 32000; do ... --context-tokens $C ; done
#   python Bench/scripts/bench_decode_gather_fusion_headroom.py --selftest   # CPU
#
from __future__ import annotations
import argparse
import os
import sys
import time
from pathlib import Path

for _r in (Path("/workspace/symbolu/CTM_plus"), Path(__file__).resolve().parent.parent):
    if (_r / "KVPolicy").is_dir() and str(_r / "KVPolicy") not in sys.path:
        sys.path.insert(0, str(_r / "KVPolicy"))
        break

# A fused in-kernel paged gather would eliminate/absorb these pre-kernel phases.
FUSEABLE = ("view_gather", "splice", "bf16_backing", "kernel_prep")
KERNEL = "kernel"
HOST = "seqids_blockids"  # identity resolution — vectorization target, not fusion


def headroom(summary, metric="gpu_us_total"):
    """Pure: profiler summary -> fusion-headroom breakdown. Selftested.

    Picks whichever read path actually ran (`batched.*` or `one.*` — the one
    whose `.kernel` region recorded calls), then splits its GPU time into the
    fuseable pre-kernel overhead vs the irreducible kernel.
    """
    prefixes = sorted({k.split(".", 1)[0] for k in summary if "." in k})
    chosen, chosen_kernel = None, 0.0
    for p in prefixes:
        kv = summary.get(f"{p}.{KERNEL}")
        if kv and kv.get(metric, 0) >= chosen_kernel:
            chosen, chosen_kernel = p, kv.get(metric, 0)
    if chosen is None:
        return None

    def g(short):
        return float((summary.get(f"{chosen}.{short}") or {}).get(metric, 0.0))

    fuse = {s: g(s) for s in FUSEABLE}
    fuse_total = sum(fuse.values())
    kernel = g(KERNEL)
    host = g(HOST)
    denom = fuse_total + kernel
    return {
        "path": chosen,
        "metric": metric,
        "fuseable_us": fuse_total,
        "fuseable_breakdown": fuse,
        "kernel_us": kernel,
        "host_us": host,
        "read_total_us": denom,
        "headroom_pct": (100.0 * fuse_total / denom) if denom else 0.0,
        "gather_pct": (100.0 * g("view_gather") / denom) if denom else 0.0,
    }


def verdict(headroom_pct):
    if headroom_pct >= 35:
        return ("GO — the pre-kernel gather DOMINATES; an in-kernel paged gather "
                "(6F) is worth a CUDA cycle. Best-case recovers up to the headroom%.")
    if headroom_pct >= 15:
        return ("MAYBE — gather is a real but not dominant chunk; size the headroom "
                "against the CUDA effort. The kernel itself is also significant.")
    return ("NO-GO for gather fusion — the KERNEL dominates; fusing the gather "
            "won't move much. Look at the attention kernel / precision instead.")


def _build_filler(tok, n_tokens):
    base = ("The quarterly logistics review noted that warehouse seven shipped "
            "on schedule while the northern depot lagged by two days. ")
    reps = max(2, n_tokens // 24 + 2)
    ids = tok(base * reps)["input_ids"][:max(1, n_tokens)]
    return tok.decode(ids)


def _find_inner_model(llm):
    for fn in (
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner.model,
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner.model_runner.model,
    ):
        try:
            m = fn(llm)
            if m is not None and hasattr(m, "named_modules"):
                return m
        except (AttributeError, IndexError):
            continue
    return None


def _reset_seq_states(model):
    if model is None:
        return
    import torch
    from kv_policy.phase5b_backend_install import Int4ProtectedAttentionImpl
    with torch.inference_mode():
        for _, sub in model.named_modules():
            impl = getattr(sub, "impl", None)
            if isinstance(impl, Int4ProtectedAttentionImpl):
                w = getattr(impl, "_phase5b_paged_writer", None)
                if w is not None:
                    try:
                        w.reset_sequence("all")
                    except Exception:
                        pass


def _print(summary, hd, args):
    print("\n" + "=" * 96)
    print(f"int4 decode read-path profile — {args.model.split('/')[-1]}  "
          f"ctx={args.context_tokens}  gen={args.gen}  B={args.batch}")
    print("=" * 96)
    rows = sorted(summary.items())
    hdr = (f"  {'phase':<26}{'n':>6}{'cpu_us_mean':>13}{'gpu_us_mean':>13}"
           f"{'gpu_us_total':>14}{'cpu/gpu':>9}")
    print(hdr + "\n  " + "-" * (len(hdr) - 2))
    for name, v in rows:
        ratio = v["cpu_us_mean"] / max(v["gpu_us_mean"], 0.01)
        print(f"  {name:<26}{v['n_calls']:>6}{v['cpu_us_mean']:>13.2f}"
              f"{v['gpu_us_mean']:>13.2f}{v['gpu_us_total']:>14.0f}{ratio:>8.1f}x")
    if hd is None:
        print("\n  (no kernel region recorded — did the int4 packed path run?)")
        return
    print("\n" + "-" * 96)
    print(f"FUSION HEADROOM ({hd['path']}.* path, GPU time):")
    print(f"  GATHER (view_gather)            {hd['gather_pct']:>5.1f}% of read path")
    fb = hd["fuseable_breakdown"]
    print(f"  FUSEABLE pre-kernel overhead    {hd['headroom_pct']:>5.1f}%  "
          f"(view_gather+splice+bf16_backing+kernel_prep)")
    print(f"      = {fb['view_gather']:.0f} + {fb['splice']:.0f} + "
          f"{fb['bf16_backing']:.0f} + {fb['kernel_prep']:.0f} us")
    print(f"  KERNEL (irreducible attention)  {100 - hd['headroom_pct']:>5.1f}%  "
          f"({hd['kernel_us']:.0f} us)")
    print(f"  (host seqids_blockids, separate: {hd['host_us']:.0f} us — "
          f"vectorization target, not fusion)")
    print("-" * 96)
    print(f"VERDICT: {verdict(hd['headroom_pct'])}")
    print(f"  -> fusing the gather could recover UP TO {hd['headroom_pct']:.0f}% of "
          f"the int4 read-path GPU time (best case; the fused kernel still does "
          f"some in-register gather, so realized < this).")
    print("=" * 96)


def main(argv=None):
    ap = argparse.ArgumentParser(description="int4 decode gather-vs-kernel fusion headroom")
    ap.add_argument("--model", default="NousResearch/Meta-Llama-3.1-8B-Instruct")
    ap.add_argument("--context-tokens", type=int, default=32000)
    ap.add_argument("--max-model-len", type=int, default=0,
                    help="0 -> context_tokens + 4096 headroom")
    ap.add_argument("--gen", type=int, default=64, help="decode tokens to profile over")
    ap.add_argument("--batch", type=int, default=1, help="B (read-skip regime is 1)")
    # 0.70 (not 0.85): pool size doesn't affect the timing split, but the
    # out-of-pool sidecars scale with the pool — 0.85 leaves ~3 GiB margin
    # at 32K ctx (knife-edge), 0.70 leaves ~20 GiB.
    ap.add_argument("--gpu-util", type=float, default=0.70)
    ap.add_argument("--n-runs", type=int, default=2)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return _selftest()

    try:
        import torch
        from vllm import SamplingParams
        import kv_policy.int4_protected  # noqa: F401
        from kv_policy.int4_protected import Int4ProtectedLLM
        from kv_policy import phase5b_backend_install as bi
    except ImportError as e:
        print(f"FAIL import: {e}")
        return 1
    if not os.environ.get("PROTECT_MASK_PATH"):
        print("WARNING: PROTECT_MASK_PATH unset — int4 load will likely fail.")

    mml = args.max_model_len or (args.context_tokens + 4096)
    print(f"Loading {args.model} (max_model_len={mml}) ...", flush=True)
    # EAGER is required, not a preference: under CUDA-graph replay the python
    # read path (where the profiler regions live) executes only at capture
    # time, so a graphs run records ~nothing per decode step. Eager also
    # avoids capture-time staging/workspace on top of the out-of-pool
    # sidecars (OOM at gpu_util 0.85 on A100-80G otherwise).
    llm = Int4ProtectedLLM(model=args.model, max_model_len=mml,
                           gpu_memory_utilization=args.gpu_util,
                           enforce_eager=True,
                           max_num_seqs=max(2, args.batch))
    tok = llm.get_tokenizer()
    model = _find_inner_model(llm)
    prompt = _build_filler(tok, args.context_tokens) + "\n\nWrite a brief summary:"
    sp = SamplingParams(temperature=0.0, max_tokens=args.gen, ignore_eos=True)
    prompts = [prompt] * args.batch

    print("Warmup (profiling off) ...", flush=True)
    llm.generate(prompts, sp)

    prof = bi.DecodeProfiler()
    walls = []
    for _ in range(max(1, args.n_runs)):
        _reset_seq_states(model)
        prof.reset()
        bi._DECODE_PROFILER = prof
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        llm.generate(prompts, sp)
        torch.cuda.synchronize()
        walls.append(time.perf_counter() - t0)
        bi._DECODE_PROFILER = None
    summary = prof.summarize()
    print(f"profiled {args.n_runs} run(s); median wall={sorted(walls)[len(walls)//2]:.3f}s")
    _print(summary, headroom(summary), args)
    return 0


def _selftest():
    fails = []

    def check(n, c):
        print(f"  [{'PASS' if c else 'FAIL'}] {n}")
        if not c:
            fails.append(n)

    # gather-dominated -> GO
    s = {
        "batched.seqids_blockids": {"gpu_us_total": 50, "cpu_us_mean": 5, "gpu_us_mean": 1, "n_calls": 10},
        "batched.view_gather":     {"gpu_us_total": 300, "cpu_us_mean": 5, "gpu_us_mean": 1, "n_calls": 10},
        "batched.splice":          {"gpu_us_total": 80, "cpu_us_mean": 5, "gpu_us_mean": 1, "n_calls": 10},
        "batched.bf16_backing":    {"gpu_us_total": 40, "cpu_us_mean": 5, "gpu_us_mean": 1, "n_calls": 10},
        "batched.kernel_prep":     {"gpu_us_total": 30, "cpu_us_mean": 5, "gpu_us_mean": 1, "n_calls": 10},
        "batched.kernel":          {"gpu_us_total": 450, "cpu_us_mean": 5, "gpu_us_mean": 1, "n_calls": 10},
    }
    hd = headroom(s)
    fuse = 300 + 80 + 40 + 30
    check("picks batched path", hd["path"] == "batched")
    check("fuseable sums correctly", abs(hd["fuseable_us"] - fuse) < 1e-6)
    check("headroom% = fuse/(fuse+kernel)",
          abs(hd["headroom_pct"] - 100 * fuse / (fuse + 450)) < 1e-6)
    check("host reported separately (not in headroom)", hd["host_us"] == 50)
    check("verdict GO when >=35%", "GO" in verdict(hd["headroom_pct"]))

    # kernel-dominated -> NO-GO
    s2 = {"one.view_gather": {"gpu_us_total": 20, "cpu_us_mean": 1, "gpu_us_mean": 1, "n_calls": 5},
          "one.splice": {"gpu_us_total": 10, "cpu_us_mean": 1, "gpu_us_mean": 1, "n_calls": 5},
          "one.bf16_backing": {"gpu_us_total": 5, "cpu_us_mean": 1, "gpu_us_mean": 1, "n_calls": 5},
          "one.kernel_prep": {"gpu_us_total": 5, "cpu_us_mean": 1, "gpu_us_mean": 1, "n_calls": 5},
          "one.kernel": {"gpu_us_total": 900, "cpu_us_mean": 1, "gpu_us_mean": 1, "n_calls": 5}}
    hd2 = headroom(s2)
    check("picks one path when only it has kernel", hd2["path"] == "one")
    check("NO-GO when kernel dominates", "NO-GO" in verdict(hd2["headroom_pct"]))
    check("empty summary -> None", headroom({}) is None)

    print(f"\n{'ALL PASS' if not fails else str(len(fails)) + ' FAIL'}")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
