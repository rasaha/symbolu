#!/usr/bin/env python3
"""Phase 9 — MINIMAL attention-guided RETENTION prototype (the quality-bet test).

The proxy proved: read-skip wins throughput (length-scaling) but a FIXED recent
window destroys needle retrieval. The kernel's whole bet is that **attention-
guided retention** (keep sinks + recent + the high-importance middle tokens)
RECOVERS that quality. A fixed-window proxy can't test that. This does — minimally,
quality-only (speed irrelevant), OUTSIDE vLLM (no Triton kernel), via HF
transformers on a strong long-context model (Qwen2.5-7B; no sliding-window OOD).

Mechanism (SnapKV/H2O-lite, reduced-PROMPT form — robust, no cache surgery):
  1. Tokenize [context-haystack + question].
  2. Score each CONTEXT token's importance = its relevance to the QUESTION
     (cosine of hidden states at a mid layer; a memory-safe proxy for the
     attention the question pays it — true attention scoring is the v2).
  3. Build a keep-set of size `budget` under each POLICY, ALWAYS keeping the
     question tokens, then generate (full attention) on the reduced prompt.
  4. Measure needle hit-rate by depth, per policy.

The three policies at the SAME budget are the experiment:
  * recent        — keep the last `budget` context tokens (= the sliding-window
                    proxy; drops the early/mid needle).
  * sink_recent   — sinks + recent (StreamingLLM; sinks restore fluency but, per
                    the paper, NOT mid-context recall).
  * relevance     — sinks + recent + top-(budget) middle by question-relevance
                    (the BET: does keeping the relevant tokens retain the needle?).

DECISIVE READ:
  * relevance HITS the early/mid-depth needles that `recent` MISSES, at the same
    budget  ->  attention-guided retention recovers quality  ->  the kernel build
    is JUSTIFIED (and v2 with true attention scoring should be >= this).
  * relevance ALSO misses them  ->  selection doesn't keep the needle; the bet
    is in doubt  ->  do NOT build on this basis; investigate scoring.

CAVEATS (state them in any writeup):
  * v1 importance is question-RELEVANCE (hidden-state cosine), not true attention.
    It's a proxy; the lexical overlap between this needle and its question makes
    it an EASY case — also run --mode distractor/conflict for a harder signal.
  * reduced-prompt (not reduced-cache) renumbers positions; fine for a retention
    quality test ("is the needle kept?"), not a throughput test.

Usage:
  python phase9_retention_prototype.py --selftest                 # CPU, no model
  python phase9_retention_prototype.py --context-tokens 16000 --budget 2048 \
      --depths 0.1,0.3,0.5,0.7,0.9 --items 4 --out retention.json  # GPU pod
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from phase6k12_hard_needle import _code, _filler, classify  # noqa: E402

POLICIES = ("recent", "sink_recent", "relevance")


def build_needle(context_tokens: int, depth_frac: float, rng):
    """Return (context_text, question_text, expected). Single needle at a
    controlled depth in filler. ~12 tokens/filler-sentence."""
    total = max(30, context_tokens // 12)
    before = max(0, int(round(depth_frac * total)))
    after = max(0, total - before)
    code = _code(rng)
    needle = f"The access code for section ALPHA is {code}."
    context = f"{_filler(before)} {needle} {_filler(after)}"
    question = ("\n\nQuestion: What is the access code for section ALPHA? "
                "Answer with only the code.")
    return context, question, code


def select_keep(n_ctx: int, importance, policy: str, budget: int,
                n_sink: int, n_recent: int):
    """Pure selection logic (CPU-testable). Return a SORTED list of kept context
    indices (0..n_ctx-1), |kept| <= budget. `importance` is a length-n_ctx list
    (higher = more relevant); only used by the 'relevance' policy."""
    budget = max(1, min(budget, n_ctx))
    if policy == "recent":
        keep = set(range(max(0, n_ctx - budget), n_ctx))
    elif policy == "sink_recent":
        n_sink_e = min(n_sink, budget)
        n_rec = budget - n_sink_e
        keep = set(range(n_sink_e)) | set(range(max(0, n_ctx - n_rec), n_ctx))
    elif policy == "relevance":
        keep = set(range(min(n_sink, n_ctx)))                 # sinks
        keep |= set(range(max(0, n_ctx - n_recent), n_ctx))   # recent
        remaining = budget - len(keep)
        if remaining > 0:
            mid = [j for j in range(n_ctx) if j not in keep]
            mid.sort(key=lambda j: importance[j], reverse=True)  # high-importance first
            keep |= set(mid[:remaining])
    else:
        raise ValueError(f"unknown policy {policy!r}")
    return sorted(keep)


def run(args) -> int:
    import random
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    rng = random.Random(args.seed)
    tok = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=torch.bfloat16, device_map="cuda")
    model.eval()

    def importance_scores(context_text, question_text):
        """Question-relevance per context token = cosine(hidden_ctx_j,
        mean_hidden_question) at a mid layer. Memory-safe (hidden states are
        seq*hidden, not seq*seq)."""
        ctx_ids = tok(context_text, return_tensors="pt").input_ids
        q_ids = tok(question_text, return_tensors="pt").input_ids
        full = torch.cat([ctx_ids, q_ids], dim=1).to("cuda")
        with torch.no_grad():
            out = model(full, output_hidden_states=True, use_cache=False)
        layer = args.score_layer if args.score_layer >= 0 else \
            len(out.hidden_states) + args.score_layer
        h = out.hidden_states[layer][0].float()        # [seq, H]
        n_ctx = ctx_ids.shape[1]
        ctx_h = h[:n_ctx]
        q_h = h[n_ctx:].mean(0, keepdim=True)
        ctx_n = torch.nn.functional.normalize(ctx_h, dim=-1)
        q_n = torch.nn.functional.normalize(q_h, dim=-1)
        scores = (ctx_n @ q_n.T).squeeze(-1).tolist()  # [n_ctx]
        return ctx_ids[0].tolist(), q_ids[0].tolist(), scores

    def answer(reduced_ctx_ids, question_text):
        ctx_text = tok.decode(reduced_ctx_ids, skip_special_tokens=True)
        prompt = ctx_text + question_text
        chat = tok.apply_chat_template(
            [{"role": "user", "content": prompt}],
            tokenize=False, add_generation_prompt=True)
        ids = tok(chat, return_tensors="pt").input_ids.to("cuda")
        with torch.no_grad():
            out = model.generate(ids, max_new_tokens=args.max_gen,
                                  do_sample=False,
                                  pad_token_id=tok.eos_token_id)
        return tok.decode(out[0, ids.shape[1]:], skip_special_tokens=True)

    depths = [float(x) for x in args.depths.split(",") if x.strip()]
    results = {p: {f"{d:.2f}": {"hits": 0, "items": 0} for d in depths}
               for p in POLICIES}
    for d in depths:
        for _ in range(args.items):
            context, question, expected = build_needle(args.context_tokens, d, rng)
            ctx_ids, _q_ids, scores = importance_scores(context, question)
            for policy in POLICIES:
                keep = select_keep(len(ctx_ids), scores, policy, args.budget,
                                   args.n_sink, args.n_recent)
                reduced = [ctx_ids[i] for i in keep]
                text = answer(reduced, question)
                hit = classify(text, expected, [], "multi") == "HIT"
                results[policy][f"{d:.2f}"]["hits"] += int(hit)
                results[policy][f"{d:.2f}"]["items"] += 1
            print(f"[retention] depth={d:.2f} done "
                  f"(recent={results['recent'][f'{d:.2f}']['hits']} "
                  f"sink_recent={results['sink_recent'][f'{d:.2f}']['hits']} "
                  f"relevance={results['relevance'][f'{d:.2f}']['hits']} "
                  f"/ {results['recent'][f'{d:.2f}']['items']})", flush=True)

    summary = {
        "model": args.model, "context_tokens": args.context_tokens,
        "budget": args.budget, "n_sink": args.n_sink, "n_recent": args.n_recent,
        "score_layer": args.score_layer,
        "hit_rate_by_policy_depth": {
            p: {d: round(c["hits"] / c["items"], 3) if c["items"] else None
                for d, c in results[p].items()} for p in POLICIES},
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(summary, indent=2))
    print("\n=== RETENTION PROTOTYPE — hit rate by policy x depth ===")
    hdr = "depth   | " + " | ".join(f"{p:>11}" for p in POLICIES)
    print(hdr + "\n" + "-" * len(hdr))
    for d in depths:
        dk = f"{d:.2f}"
        row = " | ".join(f"{summary['hit_rate_by_policy_depth'][p][dk]:>11}"
                         for p in POLICIES)
        print(f"{dk:>7} | {row}")
    print(f"\nwrote {args.out}")
    print("READ: if 'relevance' hits early/mid depths where 'recent' misses, "
          "attention-guided retention recovers quality -> kernel JUSTIFIED.")
    return 0


def _selftest() -> int:
    n = 100
    imp = [0.0] * n
    imp[10] = 9.9   # a high-importance middle token (the "needle")
    # recent keeps the tail only -> excludes idx 10.
    kr = select_keep(n, imp, "recent", budget=20, n_sink=4, n_recent=16)
    assert kr == list(range(80, 100)), kr
    assert 10 not in kr
    # sink_recent adds the head -> still excludes idx 10.
    ks = select_keep(n, imp, "sink_recent", budget=20, n_sink=4, n_recent=16)
    assert set(range(4)) <= set(ks) and 10 not in ks, ks
    # relevance keeps sinks+recent+top-importance middle -> MUST include idx 10.
    kv = select_keep(n, imp, "relevance", budget=20, n_sink=4, n_recent=8)
    assert 10 in kv, ("relevance must keep the high-importance token", kv)
    assert len(kv) <= 20, kv
    # budget >= n_ctx keeps everything.
    ke = select_keep(30, [0.0] * 30, "recent", budget=999, n_sink=4, n_recent=8)
    assert ke == list(range(30)), ke
    # needle builder: depth controls placement; needle text present.
    import random
    c, q, exp = build_needle(3000, 0.2, random.Random(1))
    assert f"is {exp}." in c and "access code" in q
    assert c.index("access code") < len(c) * 0.5, "depth 0.2 -> early"
    print("retention prototype self-test: PASS")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--context-tokens", type=int, default=16000)
    ap.add_argument("--budget", type=int, default=2048,
                    help="KV token budget kept per request (the read-skip keep-set size)")
    ap.add_argument("--n-sink", type=int, default=4)
    ap.add_argument("--n-recent", type=int, default=512)
    ap.add_argument("--depths", default="0.1,0.3,0.5,0.7,0.9")
    ap.add_argument("--items", type=int, default=4)
    ap.add_argument("--max-gen", type=int, default=16)
    ap.add_argument("--score-layer", type=int, default=-2,
                    help="hidden-state layer for relevance scoring (negative = from end)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="retention.json")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return _selftest()
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
