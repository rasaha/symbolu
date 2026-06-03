# Phase 9 — retention prototype RESULT (v1: inconclusive by design)

> **Status: MEASURED, but the test was flawed — INCONCLUSIVE on the bet.**
> Qwen2.5-7B, ctx=16000, budget=2048. Companion to the runbook + proxy result.

## Result

| depth | recent | sink_recent | relevance (v1) |
|---:|---:|---:|---:|
| 0.10 | 0.0 | 0.0 | 0.0 |
| 0.30 | 0.0 | 0.0 | 0.0 |
| 0.50 | 0.0 | 0.0 | 0.0 |
| 0.70 | 0.0 | 0.0 | 0.0 |
| 0.90 | **1.0** | **1.0** | **0.0** |

## Why this is INCONCLUSIVE, not a refutation

- The **generation mechanism works**: `recent` hits at depth 0.90 (needle ~1600
  tokens from the end, inside its 2048 window). So the reduced-prompt path is
  sound; the failure is purely in **selection**.
- **v1 scores the wrong signal.** Importance = each context token's *question-
  relevance at prefill* (hidden-state cosine). The answer is a **random code the
  question never names**, so the payload tokens score LOW and are not selected —
  v1 keeps the question-echoing words and drops the answer. At depth 0.90 it even
  loses a needle `recent` trivially keeps.
- **Real H2O/SnapKV score attention during DECODE**, when the model's query
  actively retrieves the code — so they would keep the payload. v1 structurally
  can't see that (it scores before generation). So v1 fails for a reason that
  does NOT carry to the actual bet.

## What this means

The cheap incremental de-risk has **bottomed out**. A faithful test of "attention-
guided retention recovers recall" needs decode-time / observation-window
attention scoring — i.e. implementing SnapKV/H2O, which is most of the kernel
work itself. There is no cheaper rung left: the next step IS the build.

## The fork (decision recorded in chat)

- **Park:** the throughput prize is proven + length-scaling; quality-recovery is
  unproven and no longer cheaply probeable. Bank density (1.83×) + quality
  (= bf16) as the product; treat the read-skip kernel as an explicit,
  accepted-risk future bet (not de-risked further). PCAM gated likewise.
- **Build (v2 = the real thing):** implement decode-time attention-scored
  retention (SnapKV/H2O-style), first as a quality gate (needle + MMLU under
  retention), then — if quality holds — the throughput kernel. This is the
  multi-session build the incremental probes were trying to avoid, now justified
  only if the org wants the (proven) throughput prize enough to take the
  quality-recovery bet directly.

## Accumulated Phase 9 verdict

- Throughput: read-skip wins, length-scaling (+30% @4k → ~10× @16k). **Proven.**
- Quality under fixed read-skip: **destroyed** (proxy).
- Quality under attention-guided retention: **unproven** — fixed-window can't
  test it, and a prefill-relevance proxy (v1) is structurally inadequate. Only a
  decode-time attention implementation (≈ the build) can settle it.
- Proven, shippable product remains **density 1.83× + quality = bf16**.
