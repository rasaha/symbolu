#!/usr/bin/env python3
# Phase 6K.8 — characterize the CUDA-graph-mode protected collapse.
#
# State after 6K.7: the dispatch fix made EAGER fully correct (all N coherent),
# but CUDA-graph mode (enforce_eager=False) still collapses protected decode on
# short/medium prompts — and it's NON-DETERMINISTIC across runs (same prompt,
# same .so: 'Paris' one run, 'pérdida pérdida…' the next). That signature points
# at uninitialized / stale state (or a capture-replay ordering issue) in the
# capture-only batched path (_read_decode_packed_batched + captured
# write_decode_batched + the precapture-hook one-time pool sync) that the
# verified eager B=1 path bypasses.
#
# We CANNOT intercept the kernel under graph replay (the captured CUDA ops run
# without re-entering Python). So this probe characterizes the bug behaviorally
# to localize it:
#
#   Test 1 (first-vs-warm + within-process determinism):
#     run the SAME prompt N times in ONE process. If request #1 collapses but
#     later ones recover -> first-decode init/sentinel bug. If all vary ->
#     nondeterministic state. If all identical -> deterministic-by-prompt.
#
#   Test 2 (prompt-length map): one short prompt per length bucket -> which
#     collapse (the original bug was non-monotonic in prompt token count).
#
# Run it 2-3 times (fresh process each) to also gauge CROSS-process determinism.
#
# Usage:
#   export PYTHONPATH=/workspace/symbolu/CTM_plus/KVPolicy:$PYTHONPATH
#   python CTM_plus/Bench/scripts/phase6k8_graph_state_probe.py 2>&1 | tee /tmp/phase6k8.log
#   # (run it a couple times; compare across runs)
#
# Env:
#   ENFORCE_EAGER=1   -> control run in eager (expect all coherent)
#   PHASE6E_FUSED_WRITER defaults to 1 here (matches the bench/production path)

import os
import sys

os.environ.setdefault("PHASE6E_FUSED_WRITER", "1")
# This probe deliberately exercises CUDA-graph mode unless told otherwise.
os.environ.setdefault("PHASE6B3_FORCE_EAGER", "0")


def _collapsed(text: str) -> bool:
    """Heuristic: repetition collapse (pérdida-style) or near-zero diversity."""
    words = text.split()
    if len(words) < 6:
        return False
    distinct_ratio = len(set(words)) / len(words)
    # longest run of one repeated word
    longest = cur = 1
    for a, b in zip(words, words[1:]):
        cur = cur + 1 if a == b else 1
        longest = max(longest, cur)
    top_count = max((words.count(w) for w in set(words)), default=0)
    return distinct_ratio < 0.4 or longest >= 4 or top_count >= 6


def _flag(text: str) -> str:
    return "COLLAPSE" if _collapsed(text) else "ok"


def main():
    eager = os.environ.get("ENFORCE_EAGER", "0").strip() in ("1", "true", "yes")
    from kv_policy.int4_protected import Int4ProtectedLLM
    from vllm import SamplingParams

    mode = "EAGER" if eager else "CUDA-GRAPH"
    print(f"\n[6k8] mode={mode}  PHASE6E_FUSED_WRITER={os.environ['PHASE6E_FUSED_WRITER']}  "
          f"PROTECT_MASK_PATH={os.environ.get('PROTECT_MASK_PATH','(default)')}", flush=True)

    llm = Int4ProtectedLLM(
        model="Qwen/Qwen2.5-7B-Instruct", max_model_len=8192,
        gpu_memory_utilization=0.5, max_num_seqs=8, enforce_eager=eager,
    )
    sp = SamplingParams(temperature=0.0, max_tokens=24)
    tok = llm.get_tokenizer()

    def gen(prompt):
        out = llm.generate([prompt], sp)[0]
        n_in = len(out.prompt_token_ids)
        return n_in, out.outputs[0].text

    same = "What is the capital of France? Answer in one sentence."
    print("\n" + "=" * 78)
    print(f"TEST 1 — same prompt x6 in one process (first-vs-warm + determinism)")
    print(f"  prompt={same!r}")
    print("=" * 78)
    t1 = []
    for i in range(6):
        n_in, text = gen(same)
        t1.append(text)
        print(f"  req#{i+1} (N={n_in:>3}) [{_flag(text):8s}] {text!r}")
    n_collapse_1 = sum(_collapsed(t) for t in t1)
    all_same = len(set(t1)) == 1
    first_only = _collapsed(t1[0]) and not any(_collapsed(t) for t in t1[1:])
    print(f"\n  within-process: identical={all_same}  collapsed={n_collapse_1}/6  "
          f"first-only-collapse={first_only}")

    prompts = [
        "List three primary colors and their names.",                          # ~9
        "What is the capital of France? Answer in one sentence.",              # ~13
        "Summarize the water cycle in one short sentence for a child.",        # ~15
        "Name two programming languages and one use case for each, briefly.",  # ~16
        "In one sentence, explain what photosynthesis is and why it matters.", # ~16
        "Give me a one-line definition of machine learning in plain English.", # ~15
    ]
    print("\n" + "=" * 78)
    print("TEST 2 — prompt-length map (which lengths collapse)")
    print("=" * 78)
    for p in prompts:
        n_in, text = gen(p)
        print(f"  N={n_in:>3} [{_flag(text):8s}] {text!r}")

    print("\n" + "-" * 78)
    print("READ:")
    print("  * first-only-collapse=True  -> first-decode init/sentinel bug "
          "(precapture-hook one-time pool sync under capture).")
    print("  * identical=False across the 6 reqs, or different output when you")
    print("    re-run this script -> nondeterministic = uninitialized/stale state.")
    print("  * collapse correlates with N (some lengths only) -> partial-block /")
    print("    batched-splice handling under the padded-batch graph.")
    print("  * EAGER control run (ENFORCE_EAGER=1) should show NO collapse.")
    print("-" * 78 + "\n", flush=True)


if __name__ == "__main__":
    sys.exit(main())
