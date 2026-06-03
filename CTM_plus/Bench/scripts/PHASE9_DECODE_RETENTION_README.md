# Phase 9 — decode-time attention retention harness (`phase9_decode_retention_harness.py`)

A **quality-gate** harness to decide whether the read-skip / sparse-decode kernel
is worth building. It is **not** the optimized CUDA kernel and does not try to be
fast — it keeps the full KV cache and **masks** attention to dropped historical
positions (positions/rotary stay exact). Correctness and comparability over speed.

## Why the previous v1 was invalid, and what the correct signal is

v1 ranked historical tokens by **prefill hidden-state cosine to the question**.
The needle answer is a **random code the question never names**, so the payload
tokens scored low and were dropped — v1 kept the question-echoing words and lost
the answer. That is a structural flaw, not a test of the bet.

The correct signal is **decode-time attention mass into historical KV blocks**:
as the model generates the answer, its generated-token queries reveal which
blocks it is actually retrieving from. This harness aggregates that attention by
block over the first `observe_steps` generated tokens (EMA-refreshed every
`refresh_every`), then retains sinks + recent + top-attended blocks (+ neighbors).

## Policies compared (same KV budget)

| policy | keep-set |
|---|---|
| `full_attention` | everything (baseline) |
| `recent_only` | recent window + BOS |
| `sink_recent` | sink/BOS blocks + recent window |
| `decode_attention_retention` | sinks + recent + top decode-attended blocks + neighbors |

## The mandatory diagnostic: `needle_retained`

Every needle case logs `needle_token_span`, `needle_block_ids`,
`retained_block_ids`, and **`needle_retained`** — so a miss is attributable:
- `needle_retained = false` → **selection failure** (the policy dropped the block).
- `needle_retained = true` but `hit = false` → **generation / attention-path
  failure** (the block was kept but the answer still didn't come out).

## Run

```bash
cd /workspace/symbolu/CTM_plus && source /workspace/venv-vllm/bin/activate
# CPU logic check (no model):
python Bench/scripts/phase9_decode_retention_harness.py --selftest
# the deliverable smoke (ctx 4096; depths 0.1/0.5/0.9; 2 seeds; all 4 policies):
python Bench/scripts/phase9_decode_retention_harness.py --smoke \
  --output-json Bench/bench_out/PHASE9_DECODE_RETENTION/smoke.json
# fuller run later:
python Bench/scripts/phase9_decode_retention_harness.py \
  --context-lens 4096,8192 --depths 0.10,0.30,0.50,0.70,0.90,0.95 --seeds 4 \
  --output-json Bench/bench_out/PHASE9_DECODE_RETENTION/full.json
```

All knobs are CLI-overridable: `--block-size --sink-tokens --recent-tokens
--observe-steps --attention-budget-tokens --neighbor-blocks --refresh-every
--score-decay --max-new-tokens --model --dtype --device`.

## Interpreting the decision (printed by the harness)

- **GREEN** — `decode_attention_retention` is within ~5–10% of `full_attention`
  on needle/random-code **and** MMLU smoke. The kernel is worth building.
- **YELLOW** — needle retention improves materially but is unstable by
  depth/seed (or retains < ~60% of needles). Tune `block_size`, `observe_steps`,
  `attention_budget_tokens`, `neighbor_blocks` before committing.
- **RED** — retention does not keep needle payloads (selection fails and won't
  tune), or keeps them but still fails. Park the read-skip kernel.
- **INVALID** — `full_attention` baseline is not near-perfect, generation is
  degenerate, or `needle_retained` is missing. Fix the harness before concluding.

**Discipline:** never claim success on throughput alone; never claim failure
without the `needle_retained` logs distinguishing selection vs generation. The
purpose is to **decide whether the kernel is worth building, not to build it.**

## Notes / limitations

- Masking (not physical KV pruning) keeps the full cache — faithful for quality,
  not a throughput measurement (throughput was measured separately; read-skip
  wins, length-scaling).
- `attn_implementation="eager"` is required for decode-time `output_attentions`;
  prefill at 16k is memory-heavy under eager — start at 4k/8k, extend if stable.
- First pod run is a plumbing shakeout (the masked cached-decode path is
  validated on the pod, not on the CPU author box).
