# Phase 9 — decode-time retention RESULT (the quality bet PAYS — GREEN)

> **Status: MEASURED, GREEN (preliminary fast run; full confirmation pending).**
> The decisive quality-gate for the read-skip kernel. Qwen2.5-7B, eager+fp32
> (the validated clean+observable config), ctx 8192.

## The result (fast run: ctx8192, depths 0.1/0.5/0.9, 2 seeds, needle task)

| policy | needle hit | needle_retained | d0.1 | d0.5 | d0.9 |
|---|---:|---:|:--:|:--:|:--:|
| full_attention | 1.00 | 1.00 | 2/2 | 2/2 | 2/2 |
| recent_only | 0.33 | 0.33 | 0/2 | 0/2 | 2/2 |
| sink_recent | 0.33 | 0.33 | 0/2 | 0/2 | 2/2 |
| **decode_attention_retention** | **1.00** | **1.00** | 2/2 | 2/2 | 2/2 |

MMLU smoke = 1.0 for every policy. **DECISION: GREEN** (retention within ~10% of
full; needle Δ=0.00, mmlu Δ=0.00).

## What it proves

- **The H2O risk is real:** `recent_only`/`sink_recent` drop the needle's block at
  depths 0.1/0.5 (`needle_retained 0/2`) → the answer dies. A fixed window is
  quality-destructive, exactly as the sliding-window proxy showed.
- **Attention-guided retention recovers it:** `decode_attention_retention` keeps
  `needle_retained = 1.0` at *every* depth and recovers `hit = 1.0`. The
  decode-time attention signal — what the generated-token queries actually
  retrieve — **correctly selects the needle's block**, where prefill-relevance
  (v1) and fixed windows fail. `needle_retained` separates the mechanisms: this is
  a *selection* success, not a generation fluke.
- **No MMLU regression.**

So Step-0's two IFs are both satisfied: read-skip **wins throughput**
(proxy ~10× at long ctx) **and preserves quality** (this run) via attention-guided
retention. The read-skip kernel is **justified**.

## How the baseline was made trustworthy (the long detour, recorded)

The result is only credible because the baseline is. Getting `full_attention` to a
clean 1.0 took isolating several confounds (each was a real bug, all fixed):

1. Leading-zero / char-copy errors on random codes → unambiguous payloads.
2. Number-laden filler (`Log entry {i}`) injected ~450 distractor numbers →
   **number-free prose filler**.
3. Chat-transcript run-on → hardened greedy `GenerationConfig` + explicit
   stop-token + split-at-newline.
4. **The big one — `attn_implementation="eager"` + bf16 fuzzed the QK matmul**
   (0→1 digit flips, word truncations), capping the baseline at ~0.9. Diagnosed
   via the multi-context preflight: **sdpa-bf16 = 1.0 at every length**, eager-bf16
   ≈ 0.9. Retention *needs* eager (for decode-attn `output_attentions`), so the fix
   is **eager + fp32** → baseline 1.0 at ctx 512/2048/4096, observation intact.

## Confirmation: multi_needle is GREEN too

The `multi_needle` task (three sections, distinct codes, ask for ONE — the test
that retention keeps the *correct* payload, not merely *a* code) ran at ctx8192
(eager+fp32, depths 0.1/0.5/0.9, 2 seeds):

| policy | needle hit | needle_retained | d0.1 | d0.5 | d0.9 |
|---|---:|---:|:--:|:--:|:--:|
| full_attention | 1.00 | 1.00 | 2/2 | 2/2 | 2/2 |
| recent_only | 0.33 | 0.33 | 0/2 | 0/2 | 2/2 |
| sink_recent | 0.33 | 0.33 | 0/2 | 0/2 | 2/2 |
| **decode_attention_retention** | **1.00** | **1.00** | 2/2 | 2/2 | 2/2 |

Same clean separation: retention keeps the right code at every depth; the fixed
windows drop it at 0.1/0.5. DECISION: GREEN. **Both tasks now confirm GREEN.**

## Caveats — what remains (honest)

1. **Modest N:** 6 items/policy/task (12 needle items/policy across both tasks).
   The *separation is perfect* (retention=full=1.00 vs fixed-window=0.33 on both
   tasks, all depths) so more seeds are unlikely to flip it — but the full
   160-case run (4 seeds × 5 depths × both tasks) is worth banking for the record.
2. **Quality proxy, not the kernel:** masking (full cache kept), fp32/bf16 not
   int4. The build must verify the *composition* (int4 cold store + read-skip) and
   that physical KV pruning reproduces the masked behaviour.
3. This is the **quality** half; throughput was measured separately (proxy ~10×).

## Confirmation run (do this before final sign-off)

```
python Bench/scripts/phase9_decode_retention_harness.py \
  --attn-impl eager --dtype float32 \
  --context-lens 8192 --depths 0.10,0.30,0.50,0.70,0.90 --seeds 4 \
  --tasks needle_random_code,multi_needle \
  --output-json Bench/bench_out/PHASE9_DECODE_RETENTION/ctx8k_full.json
```

If `decode_attention_retention` stays ≈ full (incl. `multi_needle`) → final GREEN:
**build the read-skip kernel** (int4_protected cold store + attention-guided
read-skip). If `multi_needle` drops materially → YELLOW: the selection keeps *a*
code but not always the right one; tune block/observe/budget before committing.

## Bottom line for the kernel decision

The minimal decode-time retention prototype turns the read-skip bet from "unproven"
to **measured GREEN (preliminary)**: attention-guided retention recovers the recall
a fixed window destroys, at no MMLU cost. Pending the `multi_needle` + larger-sample
confirmation, the kernel is justified — the int4 *throughput* prize is reachable
without sacrificing quality.
