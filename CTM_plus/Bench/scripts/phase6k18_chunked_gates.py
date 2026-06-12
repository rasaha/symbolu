#!/usr/bin/env python3
# Phase 6K.18 — chunked-prefill probes + gates (PHASE6K18_CHUNKED_PREFILL_DESIGN.md).
#
# WHAT RUNS WHERE:
#   P2 prize probe (STOCK bf16):     --probe p2 --chunked {on,off} ...
#   G2 S1-chunked byte-gate:         --mode {mono,chunked} then --compare A B
#   G3 greedy A/B:                   --greedy {mono,chunked} then --compare-greedy A B
#   G4/G5/G6 cells: see NEXT_POD_SESSION_INT4_GPU_RUNS.md (reuse
#   phase6k12_hard_needle via NEEDLE_CHUNKED/NEEDLE_GPU_UTIL + this script's
#   P2 mixed cell on the int4 engine).
#
# G2 NOTE (why this script has its own compare): chunked finalize ORDER
# legitimately differs from monolithic — a boundary block finalizes from
# STAGING after the next chunk's full blocks — so events are aligned BY
# BLOCK ID (dump field added in 6K.18), then byte-compared with the same
# field semantics as phase6k16_byte_gate (incl. the 6N protect-format
# marker). Index-aligned compare would false-fail a correct build.
#
# Usage (pod, venv-vllm; PROTECT_MASK_PATH must point at the per-model mask):
#   M=NousResearch/Meta-Llama-3.1-8B-Instruct
#   # G2:
#   python Bench/scripts/phase6k18_chunked_gates.py --mode mono    --dump /tmp/s1_mono.pt    --model $M
#   python Bench/scripts/phase6k18_chunked_gates.py --mode chunked --dump /tmp/s1_chunked.pt --model $M
#   python Bench/scripts/phase6k18_chunked_gates.py --compare /tmp/s1_mono.pt /tmp/s1_chunked.pt
#   # G3:
#   python Bench/scripts/phase6k18_chunked_gates.py --greedy mono    --out /tmp/g3_mono.json    --model $M
#   python Bench/scripts/phase6k18_chunked_gates.py --greedy chunked --out /tmp/g3_chunked.json --model $M
#   python Bench/scripts/phase6k18_chunked_gates.py --compare-greedy /tmp/g3_mono.json /tmp/g3_chunked.json
#   # P2 (stock bf16, the prize bound — run BEFORE trusting any chunked claim):
#   python Bench/scripts/phase6k18_chunked_gates.py --probe p2 --chunked off --p2-tokens 44000  --gpu-util 0.85 --model $M --out /tmp/p2_44k_off.json
#   python Bench/scripts/phase6k18_chunked_gates.py --probe p2 --chunked on  --p2-tokens 44000  --gpu-util 0.85 --model $M --out /tmp/p2_44k_on.json
#   python Bench/scripts/phase6k18_chunked_gates.py --selftest        # CPU

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

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
sys.path.insert(0, str(Path(__file__).resolve().parent))

FIELDS = ("packed_k", "packed_v", "k_scale", "k_xmin", "k_protect",
          "v_scale", "v_xmin")

# Chunk budget for the gate cells: NOT a multiple of 32 so chunk
# boundaries land mid-block and exercise the D1 tail splice (472 % 32 =
# 24). Shared by G2/G3 so the cells stress the same machinery.
GATE_CHUNK_BUDGET = 472


# ----------------------------------------------------------------- prompts
def build_gate_prompt(n_sentences: int, seed_tag: str = "alpha") -> str:
    """Deterministic prose long enough to span several chunk budgets.
    ~17-20 tokens/sentence on Llama-class tokenizers."""
    parts = [
        f"[{seed_tag}] The archive entry {i:04d} records that station "
        f"{(i * 7) % 97} logged a pressure of {900 + (i * 13) % 200} "
        f"millibars during shift {(i % 3) + 1}, noted by operator "
        f"{['Ada', 'Boyd', 'Chen', 'Dara'][i % 4]}."
        for i in range(n_sentences)
    ]
    return " ".join(parts) + "\nSummarize the records above in one sentence."


def greedy_prompt_set() -> list:
    """6 medium prompts + ONE >2-chunk prompt (the design's G3 set)."""
    ps = [
        build_gate_prompt(40, "alpha"),
        build_gate_prompt(55, "bravo"),
        "Explain, step by step, why the sky appears blue at noon and "
        "reddish at sunset. Be precise about scattering.",
        build_gate_prompt(48, "carol"),
        "Write a four-line poem about a paged KV cache that never "
        "forgets the protected channels.",
        build_gate_prompt(60, "delta"),
        # the >2-chunk prompt: ~120 sentences ≈ 2200+ tokens ≈ 5 chunks
        # at the 472-token gate budget.
        build_gate_prompt(120, "echo-long"),
    ]
    return ps


# ----------------------------------------------------------------- engines
def _mk_int4(model, *, chunked: bool, mml: int, gpu_util: float,
             apc: bool = False):
    import kv_policy.int4_protected  # noqa: F401  (registers backend)
    from kv_policy.int4_protected import Int4ProtectedLLM
    kw = {}
    if chunked:
        kw["enable_chunked_prefill"] = True
        kw["max_num_batched_tokens"] = GATE_CHUNK_BUDGET
        # vLLM requires max_num_batched_tokens >= max_num_seqs; keep
        # seqs small so the tiny gate budget is legal.
        kw["max_num_seqs"] = 8
    if apc:
        kw["enable_prefix_caching"] = True
    return Int4ProtectedLLM(
        model=model, max_model_len=mml, gpu_memory_utilization=gpu_util,
        enforce_eager=True, **kw)


def run_byte_mode(args):
    """G2 worker: one engine, one long prompt, dump finalized blocks."""
    os.environ["INT4_PROTECTED_DUMP_BLOCKS"] = args.dump
    Path(args.dump).unlink(missing_ok=True)
    llm = _mk_int4(args.model, chunked=(args.mode == "chunked"),
                   mml=args.max_model_len, gpu_util=args.gpu_util,
                   apc=args.apc)
    from vllm import SamplingParams
    prompt = build_gate_prompt(120, "byte-gate")   # ~2200 tok ≈ 5 chunks
    llm.generate([prompt], SamplingParams(temperature=0.0, max_tokens=2))
    import torch
    ev = torch.load(args.dump, weights_only=True) if Path(args.dump).exists() else []
    blocks = [e.get("block_id", "?") for e in ev]
    print(f"[6k18-g2] mode={args.mode} dumped {len(ev)} finalize events "
          f"(blocks {blocks}) -> {args.dump}")
    return 0 if ev else 1


def compare_dumps(mono_path, chunked_path):
    """G2 compare: align by block id, byte-compare every field."""
    import torch
    a = torch.load(mono_path, weights_only=True)
    b = torch.load(chunked_path, weights_only=True)

    def by_block(evs, label):
        out = {}
        for e in evs:
            bid = e.get("block_id")
            if bid is None:
                print(f"[6k18-g2] {label}: dump predates the block_id "
                      f"field — re-run the {label} mode on this build.")
                return None
            out.setdefault(int(bid), e)      # first finalize of the block
        return out

    da, db = by_block(a, "mono"), by_block(b, "chunked")
    if da is None or db is None:
        return 1
    common = sorted(set(da) & set(db))
    print("\n" + "=" * 74)
    print(f"S1-CHUNKED BYTE-GATE (G2) — {len(common)} blocks aligned by id "
          f"(mono={sorted(da)} chunked={sorted(db)})")
    print("=" * 74)
    if not common:
        print("G2: n/a — no overlapping finalized blocks (dump env not "
              "honored, or different prompts?)")
        return 1
    all_ok = True
    for bid in common:
        ea, eb = da[bid], db[bid]
        bad = []
        fa = ea.get("k_protect_format", "bf16")
        fb = eb.get("k_protect_format", "bf16")
        if fa != fb:
            bad.append(f"k_protect_format({fa}!={fb}: rerun both modes "
                       f"with the same INT4_PROTECTED_PROT_INT8)")
        for f in FIELDS:
            ta, tb = ea[f], eb[f]
            if ta.shape != tb.shape:
                bad.append(f"{f}(shape {tuple(ta.shape)}!={tuple(tb.shape)})")
                continue
            va = ta.view(torch.int16) if ta.dtype == torch.bfloat16 else ta
            vb = tb.view(torch.int16) if tb.dtype == torch.bfloat16 else tb
            if not torch.equal(va, vb):
                bad.append(f"{f}({int((ta != tb).sum())} elems differ)")
        status = "OK " if not bad else "FAIL"
        if bad:
            all_ok = False
        print(f"  block[{bid:3d}] {status}" + ("" if not bad else "  " + ", ".join(bad)))
    only_a, only_b = sorted(set(da) - set(db)), sorted(set(db) - set(da))
    if only_a or only_b:
        print(f"  (unmatched blocks: mono-only={only_a} chunked-only={only_b} "
              f"— dump cap is 16 events; informational unless common set "
              f"is tiny)")
    print("-" * 74)
    print("G2 VERDICT:", "PASS — same 32 tokens => byte-identical "
          "nibbles/scale/xmin/protect regardless of chunk boundaries "
          "(K quant is block-local; the machinery is right)." if all_ok else
          "FAIL — a finalized block differs across chunking. THE BUILD IS "
          "WRONG — full stop (design: gate 2 red means do not proceed).")
    print("=" * 74)
    return 0 if all_ok else 1


# ----------------------------------------------------------------- G3
def run_greedy(args):
    llm = _mk_int4(args.model, chunked=(args.greedy == "chunked"),
                   mml=args.max_model_len, gpu_util=args.gpu_util,
                   apc=args.apc)
    from vllm import SamplingParams
    sp = SamplingParams(temperature=0.0, max_tokens=64)
    prompts = greedy_prompt_set()
    outs = llm.generate(prompts, sp)
    rec = []
    for i, o in enumerate(outs):
        rec.append({"i": i, "token_ids": list(o.outputs[0].token_ids),
                    "text": o.outputs[0].text})
    Path(args.out).write_text(json.dumps(
        {"mode": args.greedy, "model": args.model, "records": rec}, indent=2))
    print(f"[6k18-g3] mode={args.greedy} wrote {len(rec)} greedy outputs "
          f"-> {args.out}")
    return 0


def compare_greedy(mono_path, chunked_path):
    a = json.loads(Path(mono_path).read_text())
    b = json.loads(Path(chunked_path).read_text())
    ra, rb = a["records"], b["records"]
    n = min(len(ra), len(rb))
    print("\n" + "=" * 74)
    print(f"G3 GREEDY A/B — chunked vs monolithic ({n} prompts)")
    print("=" * 74)
    n_exact = 0
    for i in range(n):
        ta, tb = ra[i]["token_ids"], rb[i]["token_ids"]
        if ta == tb:
            n_exact += 1
            print(f"  prompt[{i}] EXACT ({len(ta)} tokens)")
        else:
            div = next((j for j in range(min(len(ta), len(tb)))
                        if ta[j] != tb[j]), min(len(ta), len(tb)))
            print(f"  prompt[{i}] diverges at token {div}/{len(ta)} "
                  f"| mono: ...{ra[i]['text'][:48]!r}"
                  f" | chunked: ...{rb[i]['text'][:48]!r}")
    print("-" * 74)
    print(f"G3: {n_exact}/{n} bit-exact. EXPECTATION: near-bar, NOT "
          f"necessarily {n}/{n} — chunk k attends to QUANTIZED full "
          f"context blocks where monolithic attends to exact bf16 (the "
          f"bounded S3 context-quant residual, same class as APC). "
          f"Divergent outputs must be COHERENT near-ties; adjudicate any "
          f"degenerate text as FAIL (machinery, not residual).")
    print("=" * 74)
    return 0


# ----------------------------------------------------------------- P2
def _nvml_peak_sampler(stop_flag, out):
    try:
        import pynvml
        pynvml.nvmlInit()
        h = pynvml.nvmlDeviceGetHandleByIndex(0)
        while not stop_flag["stop"]:
            used = pynvml.nvmlDeviceGetMemoryInfo(h).used
            out["peak"] = max(out.get("peak", 0), int(used))
            time.sleep(0.05)
    except Exception as e:                      # pragma: no cover
        out["error"] = str(e)


def run_probe_p2(args):
    """P2 prize bound on STOCK bf16 (--engine bf16, the default): peak
    memory + TTFT + concurrent-decode stall, chunked on/off. DECISION
    rule (design): if chunking does not let the long prompt run at util
    0.85 on bf16, the int4 prize is smaller than claimed — re-scope
    before trusting G4. With --engine int4 the same measurement body is
    gate G5 (mixed-batch TTFT on the protected backend)."""
    import threading
    from vllm import SamplingParams
    import torch

    chunked = args.chunked == "on"
    mml = max(args.max_model_len, args.p2_tokens + 256)

    stop = {"stop": False}
    peak = {}
    t = threading.Thread(target=_nvml_peak_sampler, args=(stop, peak),
                         daemon=True)
    t.start()

    t0 = time.perf_counter()
    if args.engine == "int4":
        import kv_policy.int4_protected  # noqa: F401
        from kv_policy.int4_protected import Int4ProtectedLLM
        kw = dict(model=args.model, max_model_len=mml,
                  gpu_memory_utilization=args.gpu_util,
                  enforce_eager=True, max_num_seqs=16)
        if chunked:
            kw["enable_chunked_prefill"] = True
            if args.p2_budget:
                kw["max_num_batched_tokens"] = args.p2_budget
        llm = Int4ProtectedLLM(**kw)
    else:
        from vllm import LLM
        kw = dict(model=args.model, max_model_len=mml, dtype="bfloat16",
                  gpu_memory_utilization=args.gpu_util, enforce_eager=True,
                  max_num_seqs=16)
        if chunked:
            kw["enable_chunked_prefill"] = True
            if args.p2_budget:
                kw["max_num_batched_tokens"] = args.p2_budget
        else:
            kw["enable_chunked_prefill"] = False
        llm = LLM(**kw)
    t_init = time.perf_counter() - t0

    tok = llm.get_tokenizer()
    base = build_gate_prompt(60, "p2")
    ids = tok.encode(base)
    reps = max(1, args.p2_tokens // max(1, len(ids)) + 1)
    long_prompt = " ".join([base] * reps)
    n_tok = len(tok.encode(long_prompt))

    sp1 = SamplingParams(temperature=0.0, max_tokens=1)
    torch.cuda.reset_peak_memory_stats()
    t0 = time.perf_counter()
    out = llm.generate([long_prompt], sp1)
    t_prefill = time.perf_counter() - t0
    m = out[0].metrics
    ttft = None
    if m is not None and m.first_token_time and m.arrival_time:
        ttft = m.first_token_time - m.arrival_time

    # Concurrent-decode stall cell: 8 short decoders + the long prompt in
    # ONE batch; per-request TTFT of the shorts measures the stall.
    shorts = [f"Count slowly from {i} upward in words:" for i in range(8)]
    spd = SamplingParams(temperature=0.0, max_tokens=64)
    t0 = time.perf_counter()
    outs = llm.generate(shorts + [long_prompt], spd)
    t_mixed = time.perf_counter() - t0
    short_ttfts = []
    for o in outs[:-1]:
        mm = o.metrics
        if mm is not None and mm.first_token_time and mm.arrival_time:
            short_ttfts.append(round(mm.first_token_time - mm.arrival_time, 3))

    stop["stop"] = True
    t.join(timeout=1.0)

    res = {
        "probe": "p2", "engine": args.engine,
        "chunked": chunked, "model": args.model,
        "gpu_util": args.gpu_util, "mml": mml, "prompt_tokens": n_tok,
        "budget": kw.get("max_num_batched_tokens"),
        "init_s": round(t_init, 2),
        "prefill_wall_s": round(t_prefill, 3),
        "ttft_s": None if ttft is None else round(ttft, 3),
        "torch_peak_alloc_gib": round(
            torch.cuda.max_memory_allocated() / 2**30, 3),
        "torch_peak_reserved_gib": round(
            torch.cuda.max_memory_reserved() / 2**30, 3),
        "nvml_peak_used_gib": (round(peak["peak"] / 2**30, 3)
                               if "peak" in peak else None),
        "nvml_sampler_error": peak.get("error"),
        "mixed_wall_s": round(t_mixed, 2),
        "short_ttfts_s": short_ttfts,
    }
    Path(args.out).write_text(json.dumps(res, indent=2))
    print(f"[6k18-p2] {json.dumps(res, indent=2)}")
    print("[6k18-p2] DECISION INPUT: compare nvml_peak_used_gib + whether "
          "this cell ran AT ALL at the requested util (OOM => the spike "
          "exceeds headroom), and short_ttfts_s chunked-on vs off.")
    return 0


# ----------------------------------------------------------------- selftest
def selftest():
    fails = []

    def check(name, cond):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        if not cond:
            fails.append(name)

    print("phase6k18_chunked_gates selftest")
    p = build_gate_prompt(10)
    check("prompt deterministic", p == build_gate_prompt(10))
    check("greedy set is 7 prompts (6 + one >2-chunk)",
          len(greedy_prompt_set()) == 7)
    check("gate budget exercises the tail (not %32)",
          GATE_CHUNK_BUDGET % 32 != 0)

    import torch
    ev = [{"block_id": i, "k_protect_format": "bf16",
           **{f: torch.randint(0, 255, (4, 4), dtype=torch.uint8)
              for f in FIELDS}} for i in range(3)]
    import copy
    same = copy.deepcopy(ev)
    # chunked order differs (boundary block finalizes later) — must PASS.
    same = [same[1], same[0], same[2]]
    pa, pb = "/tmp/_6k18a.pt", "/tmp/_6k18b.pt"
    torch.save(ev, pa)
    torch.save(same, pb)
    check("order-insensitive identical dumps PASS", compare_dumps(pa, pb) == 0)
    same[0] = dict(same[0])
    same[0]["k_scale"] = same[0]["k_scale"].clone()
    same[0]["k_scale"][0, 0] ^= 1
    torch.save(same, pb)
    check("1-byte diff FAILS", compare_dumps(pa, pb) == 1)
    legacy = [{k: v for k, v in e.items() if k != "block_id"} for e in ev]
    torch.save(legacy, pb)
    check("pre-block_id dump refused", compare_dumps(pa, pb) == 1)

    ja, jb = "/tmp/_6k18a.json", "/tmp/_6k18b.json"
    Path(ja).write_text(json.dumps({"records": [
        {"i": 0, "token_ids": [1, 2, 3], "text": "abc"}]}))
    Path(jb).write_text(json.dumps({"records": [
        {"i": 0, "token_ids": [1, 2, 4], "text": "abd"}]}))
    check("greedy compare runs (informational)",
          compare_greedy(ja, jb) == 0)

    # The factory contract this script depends on (CPU-checkable):
    from kv_policy.int4_protected import _resolve_chunked_prefill
    check("resolver: default pinned False", _resolve_chunked_prefill(None) is False)
    check("resolver: explicit True supported", _resolve_chunked_prefill(True) is True)
    from kv_policy.phase5b_4c_paged_writer import (
        set_chunked_active, chunked_active,
    )
    set_chunked_active(True)
    check("chunked flag arms", chunked_active())
    set_chunked_active(False)
    check("chunked flag disarms", not chunked_active())

    print(f"\n{'ALL PASS' if not fails else f'{len(fails)} FAIL: ' + ', '.join(fails)}")
    return 0 if not fails else 1


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="6K.18 chunked-prefill probes + gates")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--mode", choices=["mono", "chunked"],
                    help="G2 byte-gate worker")
    ap.add_argument("--compare", nargs=2, metavar=("MONO", "CHUNKED"))
    ap.add_argument("--greedy", choices=["mono", "chunked"],
                    help="G3 greedy worker")
    ap.add_argument("--compare-greedy", nargs=2, metavar=("MONO", "CHUNKED"))
    ap.add_argument("--probe", choices=["p2"])
    ap.add_argument("--engine", choices=["bf16", "int4"], default="bf16",
                    help="p2 prize probe = bf16 (default); G5 = int4")
    ap.add_argument("--chunked", choices=["on", "off"], default="off",
                    help="for --probe p2")
    ap.add_argument("--apc", action="store_true",
                    help="G6: also enable prefix caching (D4 cell)")
    ap.add_argument("--dump", default="/tmp/s1_6k18.pt")
    ap.add_argument("--out", default="/tmp/p6k18_out.json")
    ap.add_argument("--model", default="NousResearch/Meta-Llama-3.1-8B-Instruct")
    ap.add_argument("--max-model-len", type=int, default=8192)
    ap.add_argument("--gpu-util", type=float, default=0.5)
    ap.add_argument("--p2-tokens", type=int, default=44000)
    ap.add_argument("--p2-budget", type=int, default=2048,
                    help="max_num_batched_tokens for the chunked P2 cell")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.compare:
        return compare_dumps(*args.compare)
    if args.compare_greedy:
        return compare_greedy(*args.compare_greedy)
    if args.mode:
        return run_byte_mode(args)
    if args.greedy:
        return run_greedy(args)
    if args.probe == "p2":
        return run_probe_p2(args)
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
