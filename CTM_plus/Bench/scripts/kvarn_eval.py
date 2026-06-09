#!/usr/bin/env python3
# KVarN vs bf16 quality eval -- run in venv-kvarn (vLLM 0.22.0).
#
# WHY a separate script (not kv_qat_rotation_gate.py): KVarN is a vLLM CACHE-DTYPE
# (`kvarn_k4v2_g128`) on vLLM 0.22.0; the gate is HF (AutoModelForCausalLM) on the
# 0.7.3 stack. Different harness + different vLLM generation. This runs entirely in
# the KVarN env and anchors on bf16 (the common reference your other numbers use).
#
# HOW: two passes save greedy-generated token IDs; `--compare` computes free-gen
# token agreement (same metric as the gate, so it sits next to protect 0.51 / learned
# 0.385 / TurboQuant -- modulo the vLLM-version + prompt-set caveat noted below).
#
# Run (venv-kvarn):
#   python kvarn_eval.py --mode bf16  --out bf16.json     --gen 48
#   python kvarn_eval.py --mode kvarn --out kvarn.json    --gen 48
#   python kvarn_eval.py --compare bf16.json kvarn.json
#   python kvarn_eval.py --selftest                       # CPU, agreement math only
#
# CAVEATS baked into --compare output:
#   * bf16 here is full-precision KV IN vLLM 0.22.0 -- so this measures KVarN's quant
#     cost cleanly (same engine). Cross-comparison to the 0.7.3 int4_protected gate is
#     only via the shared bf16 anchor, NOT a direct number.
#   * built-in instruction prompts (not wikitext) -> absolute agreement differs from
#     the gate's; the KVarN-vs-bf16 *gap* is the apples-to-apples signal.

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 16 diverse instruction prompts (Qwen2.5-7B-Instruct is instruction-tuned).
PROMPTS = [
    "Explain how a hash map works, step by step.",
    "Write a Python function that returns the nth Fibonacci number.",
    "Summarize the causes of the French Revolution in three sentences.",
    "What is the difference between TCP and UDP? Be precise.",
    "Prove that the square root of 2 is irrational.",
    "Describe the water cycle to a ten-year-old.",
    "List five trade-offs between SQL and NoSQL databases.",
    "Translate 'The quick brown fox jumps over the lazy dog' into French.",
    "Explain gradient descent and why the learning rate matters.",
    "Write a haiku about the ocean at dawn.",
    "What are the main differences between mitosis and meiosis?",
    "Give a step-by-step plan to debug a memory leak in a C++ program.",
    "Explain the concept of opportunity cost with an example.",
    "How does HTTPS keep a connection secure? Walk through the handshake.",
    "Describe how a transformer attention mechanism computes its output.",
    "What is the difference between accuracy and precision in measurement?",
]


# --------------------------------------------------------------------------- #
# Agreement metric (CPU-testable) -- identical definition to the gate.
# --------------------------------------------------------------------------- #
def token_agreement(ref, test):
    n = min(len(ref), len(test))
    if n == 0:
        return 0.0, 0
    matched = sum(1 for i in range(n) if ref[i] == test[i])
    pre = 0
    for i in range(n):
        if ref[i] == test[i]:
            pre += 1
        else:
            break
    return matched / n, pre


def compare(ref_path: str, test_path: str) -> int:
    ref = json.loads(Path(ref_path).read_text())
    test = json.loads(Path(test_path).read_text())
    keys = sorted(set(ref["outputs"]) & set(test["outputs"]), key=int)
    matched = total = prefix = 0
    G = ref.get("gen", 0)
    for k in keys:
        a, p = token_agreement(ref["outputs"][k], test["outputs"][k])
        n = min(len(ref["outputs"][k]), len(test["outputs"][k]))
        matched += int(a * n); total += n; prefix += p
    agree = matched / max(1, total)
    print(f"\n[kvarn-eval] {test.get('mode','?')} vs {ref.get('mode','?')} "
          f"({test.get('model','?')}, {len(keys)} prompts, gen={G})")
    print(f"  free-gen token agreement = {agree:.4f}   mean_prefix = {prefix/max(1,len(keys)):.1f}/{G}")
    print(f"  reference = full-precision KV in the SAME engine (vLLM "
          f"{ref.get('vllm','?')}).")
    print("  NOTE: compare the GAP to bf16, not the absolute, when lining up against the")
    print("  gate's protect 0.51 / learned 0.385 (different vLLM version + prompt set).")
    return 0


# --------------------------------------------------------------------------- #
# GPU mode: generate greedily with a given KV dtype, save token IDs.
# --------------------------------------------------------------------------- #
def run_mode(args) -> int:
    from vllm import LLM, SamplingParams
    import vllm
    cdt = "auto" if args.mode == "bf16" else args.kvarn_dtype
    kw = dict(model=args.model, dtype="float16", gpu_memory_utilization=args.gpu_util)
    if args.max_model_len:
        kw["max_model_len"] = args.max_model_len
    if args.mode == "kvarn":
        kw["kv_cache_dtype"] = cdt
        kw["block_size"] = args.block_size
    print(f"[kvarn-eval] mode={args.mode} kv_cache_dtype={cdt} vllm={vllm.__version__}", flush=True)
    llm = LLM(**kw)
    sp = SamplingParams(temperature=0.0, max_tokens=args.gen)   # greedy
    prompts = PROMPTS[:args.n_prompts]
    outs = llm.generate(prompts, sp)
    payload = {
        "mode": args.mode, "model": args.model, "vllm": vllm.__version__,
        "kv_cache_dtype": cdt, "gen": args.gen,
        "outputs": {str(i): list(o.outputs[0].token_ids) for i, o in enumerate(outs)},
    }
    Path(args.out).write_text(json.dumps(payload))
    print(f"[kvarn-eval] wrote {args.out} ({len(prompts)} prompts)", flush=True)
    return 0


def selftest() -> int:
    fails = []

    def check(name, cond):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        if not cond:
            fails.append(name)

    print("kvarn_eval selftest")
    a, p = token_agreement([1, 2, 3, 4], [1, 2, 9, 4])
    check("agreement 3/4", abs(a - 0.75) < 1e-9)
    check("prefix stops at first mismatch (2)", p == 2)
    a, p = token_agreement([5, 6, 7], [5, 6, 7])
    check("identical -> 1.0, full prefix", a == 1.0 and p == 3)
    check("empty -> 0.0", token_agreement([], [1]) == (0.0, 0))
    check("16 built-in prompts present", len(PROMPTS) == 16)
    print(f"\n{'ALL PASS' if not fails else f'{len(fails)} FAIL: ' + ', '.join(fails)}")
    return 0 if not fails else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="KVarN vs bf16 free-gen agreement (vLLM 0.22)")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--mode", choices=["bf16", "kvarn"])
    ap.add_argument("--compare", nargs=2, metavar=("REF", "TEST"))
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--kvarn-dtype", default="kvarn_k4v2_g128")
    ap.add_argument("--block-size", type=int, default=128)
    ap.add_argument("--n-prompts", type=int, default=16)
    ap.add_argument("--gen", type=int, default=48)
    ap.add_argument("--gpu-util", type=float, default=0.85)
    ap.add_argument("--max-model-len", type=int, default=4096)
    ap.add_argument("--out", default="kvarn_out.json")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.compare:
        return compare(*args.compare)
    if args.mode:
        return run_mode(args)
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
