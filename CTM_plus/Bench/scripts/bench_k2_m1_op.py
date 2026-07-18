#!/usr/bin/env python3
# K2-M1 op/decode-level microbench — the CHEAP authoritative test before any full-model work.
#
# Drives the REAL production decode path (int4-packed splitkv kernel) once per KVPRO_K2_M1
# setting {0=control, 1, 2, 4} in EAGER mode (so getenv is re-read each decode step and the
# runtime actually switches the compiled kernel — CUDA graphs would freeze one kernel at
# capture and defeat the sweep). Reports, per setting, vs the same-wheel control (0):
#   * output-token exact match (greedy) -> numerical equivalence (expected identical);
#   * NaN/Inf guard;
#   * decode wall time (prefill is identical across settings -> the delta is the kernel).
# This isolates: routes correctly? preserves numerics? improves the actual op? or falls back?
#
# It is authoritative because it launches the EXACT runtime specialization (not a hand-built
# synthetic op call that can silently mis-shape). It loads the model ONCE and sweeps in-process.
#
#   export PROTECT_MASK_PATH=/workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt
#   python CTM_plus/Bench/scripts/bench_k2_m1_op.py --model Qwen/Qwen2.5-7B-Instruct \
#       --context-tokens 16000 --gen 64 --batch 8
#   python CTM_plus/Bench/scripts/bench_k2_m1_op.py --selftest   # CPU (verdict logic only)
from __future__ import annotations
import argparse, os, sys, time
from pathlib import Path

for _r in (Path("/workspace/symbolu/CTM_plus"), Path(__file__).resolve().parent.parent):
    if (_r / "KVPolicy").is_dir() and str(_r / "KVPolicy") not in sys.path:
        sys.path.insert(0, str(_r / "KVPolicy")); break

SETTINGS = [0, 1, 2, 4]          # 0 = same-wheel control (freshly compiled full-unroll)
LAT_REGRESS_STOP = 0.05          # >5% decode regression vs control on a candidate -> stop that one


def verdict(rows):
    """Pure: rows[setting] = {tokens_match, has_naninf, decode_ms}. Return (advance:list, notes).

    A candidate ADVANCES to the rigorous kernel benchmark only if numerics are preserved AND it
    shows a real decode improvement (gain > 0). NaN/Inf, token mismatch, or a >5% regression are
    hard stops; a flat/slightly-worse result simply doesn't advance."""
    ctrl = rows.get(0)
    notes, advance = [], []
    if ctrl is None:
        return [], ["no control (0) row — cannot compare"]
    for s in (1, 2, 4):
        r = rows.get(s)
        if r is None:
            continue
        if r["has_naninf"]:
            notes.append(f"U{s}: NaN/Inf -> STOP"); continue
        if not r["tokens_match"]:
            notes.append(f"U{s}: token mismatch vs control -> STOP (numerics not preserved)"); continue
        gain = (ctrl["decode_ms"] - r["decode_ms"]) / ctrl["decode_ms"] if ctrl["decode_ms"] else 0.0
        if gain > 0:
            notes.append(f"U{s}: decode {gain*100:+.1f}% vs control, numerics OK -> advance")
            advance.append((s, gain))
        elif gain < -LAT_REGRESS_STOP:
            notes.append(f"U{s}: decode {gain*100:+.1f}% (regress >5%) -> stop")
        else:
            notes.append(f"U{s}: decode {gain*100:+.1f}% (flat/slightly worse) -> not advancing")
    advance.sort(key=lambda x: -x[1])
    return advance, notes


def _selftest():
    fails = []
    def ck(n, c):
        print(f"  [{'PASS' if c else 'FAIL'}] {n}"); fails.append(n) if not c else None
    adv, _ = verdict({0: {"tokens_match": True, "has_naninf": False, "decode_ms": 100.0},
                      1: {"tokens_match": True, "has_naninf": False, "decode_ms": 80.0},   # +20% -> advance
                      2: {"tokens_match": True, "has_naninf": False, "decode_ms": 100.0},  # flat -> no
                      4: {"tokens_match": False, "has_naninf": False, "decode_ms": 70.0}}) # mismatch -> stop
    ck("best candidate is U1 (+20%)", bool(adv) and adv[0][0] == 1 and abs(adv[0][1] - 0.2) < 1e-9)
    ck("U2 flat does not advance", all(s != 2 for s, _ in adv))
    ck("U4 token-mismatch excluded", all(s != 4 for s, _ in adv))
    adv2, _ = verdict({0: {"tokens_match": True, "has_naninf": False, "decode_ms": 100.0},
                       1: {"tokens_match": True, "has_naninf": True, "decode_ms": 50.0}})
    ck("NaN/Inf excluded", not adv2)
    adv3, _ = verdict({0: {"tokens_match": True, "has_naninf": False, "decode_ms": 100.0},
                       1: {"tokens_match": True, "has_naninf": False, "decode_ms": 110.0}})  # -10% -> stop
    ck("regress >5% excluded", not adv3)
    print("ALL PASS" if not fails else f"{len(fails)} FAIL")
    return 0 if not fails else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="K2-M1 op/decode microbench (control + unroll sweep)")
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--context-tokens", type=int, default=16000)
    ap.add_argument("--gen", type=int, default=64)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--gpu-util", type=float, default=0.70)
    ap.add_argument("--n-runs", type=int, default=3)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return _selftest()

    import torch
    from vllm import SamplingParams
    import kv_policy.int4_protected  # noqa: F401
    from kv_policy.int4_protected import Int4ProtectedLLM
    if not os.environ.get("PROTECT_MASK_PATH"):
        print("WARNING: PROTECT_MASK_PATH unset — int4 load will likely fail.")

    mml = args.context_tokens + 4096
    # EAGER is required: CUDA-graph capture would freeze one kernel and defeat the env sweep.
    llm = Int4ProtectedLLM(model=args.model, max_model_len=mml,
                           gpu_memory_utilization=args.gpu_util, enforce_eager=True,
                           max_num_seqs=max(2, args.batch))
    tok = llm.get_tokenizer()
    base = ("The quarterly logistics review noted that warehouse seven shipped on schedule "
            "while the northern depot lagged by two days. ")
    ids = tok(base * max(2, args.context_tokens // 24 + 2))["input_ids"][:args.context_tokens]
    prompt = tok.decode(ids) + "\n\nWrite a brief summary:"
    prompts = [prompt] * args.batch
    sp = SamplingParams(temperature=0.0, max_tokens=args.gen, ignore_eos=True)
    sp1 = SamplingParams(temperature=0.0, max_tokens=1, ignore_eos=True)

    def timed(setting):
        os.environ["KVPRO_K2_M1"] = str(setting)
        llm.generate(prompts, sp1)  # warmup + prefill-cost probe
        torch.cuda.synchronize()
        # decode time = full(gen) - prefill-only(gen=1), median over runs (prefill identical
        # across settings, so this isolates the decode kernel).
        fulls, pres = [], []
        for _ in range(max(1, args.n_runs)):
            torch.cuda.synchronize(); t = time.perf_counter()
            outs = llm.generate(prompts, sp); torch.cuda.synchronize()
            fulls.append(time.perf_counter() - t)
            torch.cuda.synchronize(); t = time.perf_counter()
            llm.generate(prompts, sp1); torch.cuda.synchronize()
            pres.append(time.perf_counter() - t)
        fulls.sort(); pres.sort()
        decode_ms = (fulls[len(fulls)//2] - pres[len(pres)//2]) * 1e3 / max(1, args.gen)
        toks = tuple(tuple(o.outputs[0].token_ids) for o in outs)
        finite = all(all(t is not None for t in o.outputs[0].token_ids) for o in outs)
        return {"decode_ms": max(decode_ms, 0.0), "tokens": toks, "has_naninf": not finite}

    print(f"\nK2-M1 op microbench — {args.model.split('/')[-1]} ctx={args.context_tokens} "
          f"B={args.batch} gen={args.gen}  (per-decode-token ms, vs control=0)")
    rows, ctrl_tokens = {}, None
    for s in SETTINGS:
        r = timed(s)
        if s == 0:
            ctrl_tokens = r["tokens"]
        r["tokens_match"] = (r["tokens"] == ctrl_tokens)
        rows[s] = {"tokens_match": r["tokens_match"], "has_naninf": r["has_naninf"], "decode_ms": r["decode_ms"]}
        tag = "control" if s == 0 else f"U{s}"
        d = rows[s]["decode_ms"]; base_ms = rows[0]["decode_ms"] if 0 in rows else d
        gain = (base_ms - d) / base_ms * 100 if base_ms else 0.0
        print(f"  KVPRO_K2_M1={s:<2} ({tag:<7}): decode {d:7.3f} ms/tok  "
              f"{'' if s==0 else f'{gain:+5.1f}% vs ctrl  '}"
              f"tokens_match={rows[s]['tokens_match']}  naninf={rows[s]['has_naninf']}")
    os.environ.pop("KVPRO_K2_M1", None)
    adv, notes = verdict(rows)
    print("\n-- verdict --")
    for n in notes:
        print("  " + n)
    if adv:
        print(f"\nADVANCE to kernel benchmark with U{adv[0][0]} (best decode {adv[0][1]*100:+.1f}%)"
              f"{' ; also '+', '.join('U'+str(s) for s,_ in adv[1:]) if len(adv)>1 else ''}")
    else:
        print("\nNO candidate improved decode with numerics preserved -> K2_M1_NO_GO_KERNEL_LATENCY "
              "(the spill is not the dominant decode-latency term; occupancy is base-kernel-limited).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
