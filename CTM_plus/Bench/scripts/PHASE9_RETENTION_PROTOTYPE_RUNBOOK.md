# Phase 9 — retention prototype runbook (`phase9_retention_prototype.py`)

> **The quality-bet test.** The proxy proved read-skip wins throughput but a
> FIXED recent window destroys recall. The kernel's bet is that **attention-
> guided retention** recovers it. This tests that bet minimally — quality only,
> HF transformers, Qwen2.5-7B (strong, cached, no sliding-window OOD), no Triton.

## What it does

Three retention policies at the **same KV budget**, on a needle-in-haystack by
depth:

| policy | keep-set | role |
|---|---|---|
| `recent` | last `budget` tokens | = the sliding-window proxy (drops early/mid needle) |
| `sink_recent` | sinks + recent | StreamingLLM (sinks ≠ recall) |
| `relevance` | sinks + recent + top-(budget) middle by question-relevance | **the bet** |

## Run (GPU pod)

```bash
cd /workspace/symbolu/CTM_plus && source /workspace/venv-vllm/bin/activate
# pull latest first (git fetch/reset to the branch), then:
python Bench/scripts/phase9_retention_prototype.py \
  --context-tokens 16000 --budget 2048 --depths 0.1,0.3,0.5,0.7,0.9 --items 4 \
  --out Bench/bench_out/PHASE9_RETENTION/retention.json
```

CPU self-test (no model): `python Bench/scripts/phase9_retention_prototype.py --selftest`.

## The decision

- **`relevance` HITS the early/mid depths where `recent` MISSES** (same budget)
  → attention-guided retention recovers quality → **kernel build JUSTIFIED**
  (true-attention scoring, the v2, should do ≥ this).
- **`relevance` also misses them** → selection isn't keeping the needle → the bet
  is in doubt → don't build on this basis.

## Caveats (carry into any writeup)

1. **v1 importance = question-RELEVANCE** (hidden-state cosine), a memory-safe
   *proxy* for true attention. The v2 is real attention scores (SnapKV-style obs
   window). If v1 already works, v2 should be ≥; if v1 fails, v2 is worth trying
   before concluding.
2. **This needle has lexical overlap with its question** → an EASY case for
   relevance scoring. Treat a `relevance` win as necessary-not-sufficient; re-run
   harder modes (distractor/conflict) before a final go.
3. **Reduced-PROMPT, not reduced-cache** → renumbers positions; valid for "is the
   needle kept?" (quality), not for throughput (already measured separately).
4. First pod run is a plumbing shakeout (HF cache/generate paths unvalidated on
   the CPU container).
