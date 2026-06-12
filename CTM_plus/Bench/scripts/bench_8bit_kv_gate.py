#!/usr/bin/env python3
# 8-bit KV gate — substantiate or refute the "8-bit KV cache is the better
# fast tier" claim ON THE STACK WE SHIP (vLLM). Short by design (~12 min,
# 3 engine cells), but it measures every contested fact:
#
#   FACT 1 (availability): which kv_cache_dtype values THIS vLLM accepts, and
#          whether calculated KV scales are supported (runtime-introspected —
#          settles "standard flag in vLLM" claims; NB int8 is NOT expected).
#   FACT 2 (density): pool token-slots per backend (expect 8-bit == 2.00x
#          bf16 in-pool, same as int4_protected's pool; the difference is
#          sidecar/scale overhead, not pool slots).
#   FACT 3 (quality): needle retrieval at 8K and 32K (5 depths at 32K) +
#          the brief's 6-prompt greedy bit-exactness vs bf16 (identical
#          count + common-prefix overlap %) — the gate fp8 failed before.
#   FACT 4 (speed): B=1 decode tok/s at 32K ctx, CUDA graphs ON (production
#          posture — also yields the graphs-vs-eager bf16 delta vs the
#          eager 66 tok/s crossover baseline).
#
# Usage (pod):
#   M=NousResearch/Meta-Llama-3.1-8B-Instruct
#   pkill -9 -f vllm; sleep 2
#   python CTM_plus/Bench/scripts/bench_8bit_kv_gate.py --model $M --out-dir /tmp/kv8
#   #   --cells bf16,fp8_e4m3,fp8_e5m2   --reuse   --dry-run
#   python CTM_plus/Bench/scripts/bench_8bit_kv_gate.py --selftest   # CPU
#
# Honest scope: this gates vLLM's fp8 KV (the 8-bit option our stack offers).
# LMDeploy/TensorRT int8 KV is a different stack and is NOT tested here.
#
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

_NEEDLE_DEPTHS_32K = (0.2, 0.35, 0.5, 0.65, 0.8)
_NEEDLE_DEPTHS_8K = (0.25, 0.5, 0.75)

# The brief's 6-prompt greedy bit-exactness methodology (diverse, fixed).
_BITEXACT_PROMPTS = (
    "Explain the difference between a mutex and a semaphore in two sentences.",
    "Write a four-line poem about a lighthouse in winter.",
    "List three causes of the French Revolution, one line each.",
    "What does the Central Limit Theorem state? Answer briefly.",
    "Translate to French: 'The meeting was moved to Thursday morning.'",
    "Give a one-paragraph summary of how a refrigerator works.",
)


# ---------------------------------------------------------------------------
# Pure helpers (selftested)
# ---------------------------------------------------------------------------
def common_prefix_pct(ref: str, other: str) -> float:
    """% of the REFERENCE string matched as a common prefix by `other`."""
    if not ref:
        return 100.0 if not other else 0.0
    n = 0
    for a, b in zip(ref, other):
        if a != b:
            break
        n += 1
    return 100.0 * n / len(ref)


def quality_verdict(needle_ok_ref, needle_ok_cell, n_identical, mean_overlap):
    """Lite quality gate, thresholds stated in the output.

    PASS  : needles match the bf16 reference AND greedy outputs are
            near-bf16 (>=3/6 identical OR mean prefix overlap >= 80%) —
            the bar int4_protected MEASURABLY clears (3/6, 33-82% overlap).
    FAIL  : needles degrade vs bf16 (the fp8 failure mode), or greedy
            outputs diverge early everywhere.
    """
    needles_clean = needle_ok_cell >= needle_ok_ref
    near_bf16 = (n_identical >= 3) or (mean_overlap >= 80.0)
    if needles_clean and near_bf16:
        return "PASS (lite gate)"
    if not needles_clean:
        return "FAIL — needle retrieval degraded vs bf16 (the measured fp8 failure mode)"
    return "FAIL — greedy outputs diverge from bf16 (identical<3/6 and overlap<80%)"


def _code(i: int) -> str:
    import random
    rng = random.Random(7000 + i)
    a = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    return "-".join("".join(rng.choice(a) for _ in range(3)) for _ in range(3))


# ---------------------------------------------------------------------------
# Worker: one engine cell -> JSON
# ---------------------------------------------------------------------------
def _build_needle_prompt(tok, n_tokens, depth, code):
    base = ("Operations log: subsystem nominal, telemetry within bounds, no "
            "anomalies recorded during the interval under review. ")
    ids = tok(base * (n_tokens // 16 + 4))["input_ids"][:n_tokens]
    pos = max(1, min(len(ids) - 1, int(len(ids) * depth)))
    needle = tok(f" Confidential: the vault access code is {code}. ")["input_ids"]
    ids = (ids[:pos] + needle + ids[pos:])[:n_tokens]
    return tok.decode(ids) + ("\n\nQuestion: what is the vault access code "
                              "above? Answer with only the code.\nAnswer:")


def run_cell(args):
    import torch
    from vllm import LLM, SamplingParams

    # FACT 1: runtime support introspection (no guessing).
    import vllm
    from vllm.engine.arg_utils import EngineArgs
    fields = set(getattr(EngineArgs, "__dataclass_fields__", {}))
    scales_supported = "calculate_kv_scales" in fields
    facts = {
        "vllm_version": vllm.__version__,
        "calculate_kv_scales_supported": scales_supported,
        "int8_kv_supported": False,  # verified below by attempting nothing —
        # vLLM CacheConfig accepts auto/fp8/fp8_e4m3/fp8_e5m2 only; an int8
        # attempt raises at engine init. We assert from the accepted set:
    }
    try:
        from vllm.config import CacheConfig  # noqa: F401
        import inspect
        src = inspect.getsource(CacheConfig)
        facts["int8_kv_supported"] = '"int8"' in src or "'int8'" in src
        facts["accepted_kv_dtypes_source_hint"] = sorted(
            d for d in ("auto", "fp8", "fp8_e4m3", "fp8_e5m2", "int8")
            if f'"{d}"' in src or f"'{d}'" in src)
    except Exception as e:  # noqa: BLE001
        facts["cacheconfig_introspect_error"] = str(e)

    kw = dict(model=args.model, max_model_len=args.mml,
              gpu_memory_utilization=args.gpu_util,
              max_num_seqs=4, enable_chunked_prefill=False,
              enforce_eager=False)  # graphs ON: production posture
    if args.cell != "bf16":
        kw["kv_cache_dtype"] = args.cell
        if scales_supported and args.cell == "fp8_e4m3":
            kw["calculate_kv_scales"] = True
    llm = LLM(**kw)
    tok = llm.get_tokenizer()
    cc = llm.llm_engine.cache_config
    nb, bs = getattr(cc, "num_gpu_blocks", None), getattr(cc, "block_size", None)

    sp1 = SamplingParams(temperature=0.0, max_tokens=1)
    sp16 = SamplingParams(temperature=0.0, max_tokens=16)
    sp64 = SamplingParams(temperature=0.0, max_tokens=64, ignore_eos=True)

    # FACT 3a: needles (8K x3 depths, 32K x5 depths).
    needles = {}
    for n_tokens, depths in ((8000, _NEEDLE_DEPTHS_8K), (32000, _NEEDLE_DEPTHS_32K)):
        hits = []
        for i, d in enumerate(depths):
            code = _code(i + (0 if n_tokens == 8000 else 100))
            out = llm.generate([_build_needle_prompt(tok, n_tokens, d, code)],
                               sp16, use_tqdm=False)
            hits.append(code in out[0].outputs[0].text)
        needles[str(n_tokens)] = hits

    # FACT 3b: 6-prompt greedy outputs (driver compares vs bf16 cell).
    outs = llm.generate(list(_BITEXACT_PROMPTS), sp64, use_tqdm=False)
    bitexact_texts = [o.outputs[0].text for o in outs]

    # FACT 4: B=1 decode tok/s at 32K, two-pass (gen=1 then gen=257).
    tput_prompt = _build_needle_prompt(tok, 32000, 0.5, _code(999))

    def timed(n):
        sp = SamplingParams(temperature=0.0, max_tokens=n, ignore_eos=True)
        llm.generate([tput_prompt], sp, use_tqdm=False)        # warm
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        llm.generate([tput_prompt], sp, use_tqdm=False)
        torch.cuda.synchronize()
        return time.perf_counter() - t0

    t1, t257 = timed(1), timed(257)
    decode_tps = 256.0 / max(1e-6, t257 - t1)

    rep = {"cell": args.cell, "model": args.model, "mml": args.mml,
           "gpu_util": args.gpu_util, "graphs": True,
           "kv_scales_calculated": bool(kw.get("calculate_kv_scales", False)),
           "facts": facts,
           "num_gpu_blocks": nb, "block_size": bs,
           "total_token_slots": (nb * bs) if (nb and bs) else None,
           "needles": needles, "bitexact_texts": bitexact_texts,
           "decode_tps_32k_b1": round(decode_tps, 2)}
    Path(args.out).write_text(json.dumps(rep, indent=2))
    print(f"[kv8] cell={args.cell} slots={rep['total_token_slots']} "
          f"needle32k={sum(needles['32000'])}/{len(needles['32000'])} "
          f"tps={decode_tps:.1f} -> {args.out}", flush=True)
    return 0


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------
def sweep(args):
    outdir = Path(args.out_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    cells = [c.strip() for c in args.cells.split(",") if c.strip()]
    if "bf16" not in cells:
        cells.insert(0, "bf16")  # reference is mandatory

    data = {}
    for cell in cells:
        out = outdir / f"cell_{cell}.json"
        if not (args.reuse and out.exists()):
            cmd = [args.python, str(Path(__file__).resolve()), "--cell", cell,
                   "--model", args.model, "--mml", str(args.mml),
                   "--gpu-util", str(args.gpu_util), "--out", str(out)]
            print("  $ " + " ".join(cmd), flush=True)
            if args.dry_run:
                continue
            subprocess.run(["bash", "-c", "pkill -9 -f vllm; sleep 2"],
                           check=False)
            rc = subprocess.run(cmd, env=dict(os.environ)).returncode
            print(f"    -> exit={rc}", flush=True)
        if not args.dry_run:
            try:
                data[cell] = json.loads(out.read_text())
            except Exception as e:  # noqa: BLE001
                data[cell] = {"_error": str(e)}
    if args.dry_run:
        print("[dry-run] nothing executed.")
        return 0
    _report(data, args)
    (outdir / "kv8_gate_summary.json").write_text(json.dumps(data, indent=2))
    return 0


def _report(data, args):
    bf = data.get("bf16", {})
    ref_texts = bf.get("bitexact_texts") or []
    ref_n32 = sum((bf.get("needles") or {}).get("32000", []))
    facts = bf.get("facts", {})

    print("\n" + "=" * 96)
    print(f"8-BIT KV GATE — {args.model.split('/')[-1]}  (vLLM "
          f"{facts.get('vllm_version', '?')}, graphs ON, B=1, mml={args.mml})")
    print("=" * 96)
    print(f"FACT 1  availability on THIS stack: accepted kv dtypes ~ "
          f"{facts.get('accepted_kv_dtypes_source_hint', 'n/a')}; "
          f"int8 kv supported: {facts.get('int8_kv_supported')}; "
          f"calculated fp8 scales supported: "
          f"{facts.get('calculate_kv_scales_supported')}")
    print("-" * 96)
    print(f"{'cell':<10} {'slots':>9} {'density':>8} | {'needle8k':>8} "
          f"{'needle32k':>9} | {'ident/6':>7} {'overlap%':>8} | "
          f"{'tok/s@32K':>9} {'vs bf16':>8} | scales")
    print("-" * 96)
    rows = {}
    for cell, d in data.items():
        if d.get("_error"):
            print(f"{cell:<10} CELL ERROR: {d['_error']}")
            continue
        slots = d.get("total_token_slots")
        dens = (slots / bf["total_token_slots"]) if (
            bf.get("total_token_slots") and slots) else None
        nd = d.get("needles") or {}
        n8 = f"{sum(nd.get('8000', []))}/{len(nd.get('8000', []))}"
        n32 = f"{sum(nd.get('32000', []))}/{len(nd.get('32000', []))}"
        texts = d.get("bitexact_texts") or []
        ident = sum(1 for r, t in zip(ref_texts, texts) if r == t)
        ovl = (sum(common_prefix_pct(r, t) for r, t in zip(ref_texts, texts))
               / max(1, len(ref_texts)))
        tps = d.get("decode_tps_32k_b1")
        ratio = (tps / bf["decode_tps_32k_b1"]) if (
            bf.get("decode_tps_32k_b1") and tps) else None
        rows[cell] = dict(n32=sum(nd.get("32000", [])), ident=ident, ovl=ovl)
        print(f"{cell:<10} {slots or 0:>9,} "
              f"{(f'{dens:.2f}x' if dens else 'ref'):>8} | {n8:>8} {n32:>9} | "
              f"{ident:>5}/6 {ovl:>7.0f}% | {tps or 0:>9.1f} "
              f"{(f'{ratio:.2f}x' if ratio else 'ref'):>8} | "
              f"{'calc' if d.get('kv_scales_calculated') else 'default/none'}")
    print("-" * 96)
    for cell, r in rows.items():
        if cell == "bf16":
            continue
        v = quality_verdict(ref_n32, r["n32"], r["ident"], r["ovl"])
        print(f"VERDICT {cell}: {v}")
    print("Banked int4_protected reference (same gates, prior runs): density "
          "2.00x in-pool / 1.75x net of sidecars; hard-needle == bf16 to 60K; "
          "greedy 3/6 identical, 33-82% overlap on the rest; decode 0.17-0.67x.")
    print("Scope: vLLM fp8 only — LMDeploy/TensorRT int8 KV is a different "
          "stack, NOT tested here.")
    print("=" * 96)


def _selftest():
    fails = []

    def check(n, c):
        print(f"  [{'PASS' if c else 'FAIL'}] {n}")
        if not c:
            fails.append(n)

    check("overlap identical -> 100", common_prefix_pct("abcd", "abcd") == 100.0)
    check("overlap half -> 50", common_prefix_pct("abcd", "abXY") == 50.0)
    check("overlap disjoint -> 0", common_prefix_pct("abcd", "ZZZ") == 0.0)
    check("overlap empty ref+other -> 100", common_prefix_pct("", "") == 100.0)
    check("verdict PASS on clean needles + 3 identical",
          quality_verdict(5, 5, 3, 50.0).startswith("PASS"))
    check("verdict PASS on clean needles + high overlap",
          quality_verdict(5, 5, 0, 85.0).startswith("PASS"))
    check("verdict FAIL on degraded needles",
          "needle" in quality_verdict(5, 1, 6, 100.0))
    check("verdict FAIL on divergent greedy",
          "diverge" in quality_verdict(5, 5, 0, 12.0))
    print(f"\n{'ALL PASS' if not fails else str(len(fails)) + ' FAIL'}")
    return 0 if not fails else 1


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="8-bit KV (vLLM fp8) quality+density+speed gate vs bf16")
    ap.add_argument("--selftest", action="store_true")
    # worker
    ap.add_argument("--cell", choices=["bf16", "fp8_e4m3", "fp8_e5m2"])
    ap.add_argument("--out", default="/tmp/kv8_cell.json")
    # shared / driver
    ap.add_argument("--model", default="NousResearch/Meta-Llama-3.1-8B-Instruct")
    ap.add_argument("--mml", type=int, default=36096)
    ap.add_argument("--gpu-util", type=float, default=0.55)
    ap.add_argument("--cells", default="bf16,fp8_e4m3,fp8_e5m2")
    ap.add_argument("--out-dir", default="/tmp/kv8_gate")
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--reuse", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return _selftest()
    if args.cell:
        return run_cell(args)
    return sweep(args)


if __name__ == "__main__":
    raise SystemExit(main())
