# Phase 9 — Capstone: read-skip from idea to a breakeven, quality-safe production kernel

> One-page summary of the Phase 9 arc (PR #1058). Audience: anyone picking this
> up cold. The detailed findings live in the per-step docs referenced below.

## The question

int4_protected is the shipped product (1.83× KV density, = bf16 quality). It is a
*density* play, so on its own it is **slower** than bf16 (0.22–0.54×). The only
way int4 wins **throughput** is **read-skip**: not re-reading the cold majority of
the KV cache each decode step. Phase 9 asked: **is read-skip real — does it win
throughput without losing quality — and can it ship in software, or does it need
the PCAM chip?**

## The arc (each step gated the next)

| Step | What | Result | Doc |
|---|---|---|---|
| **0 — model it** | CPU cost model; derive the achievable skip rate | Prize is real (~1.9×) **at long context with aggressive skip**; length-dependent | `PHASE9_STEP0_FINDINGS.md` |
| **scope** | does read-skip even exist in the code? | No — it's a *build*. The evictor is cross-request, not intra-sequence | `PHASE9_READSKIP_NOT_IMPLEMENTED.md` |
| **de-risk: throughput** | sliding-window proxy (Mistral) | Throughput win is real, ~10× at 16k | `PHASE9_READSKIP_PROXY_RESULT.md` |
| **de-risk: quality** | decode-time attention-retention harness | **GREEN** — retention preserves the needle where fixed windows fail | `PHASE9_DECODE_RETENTION_RESULT.md` |
| **build P1** | cache gather `kernel_inputs(active_positions)` + shared selection logic | byte-eq foundation, CPU-tested | `PHASE9_READSKIP_KERNEL_BUILD_PLAN.md` |
| **build P2** | retention controller + GPU scoring + route-A wiring | live end-to-end behind `INT4_READSKIP_MODE` | (commits) |
| **build P2c** | runner `--int4-kv-backend fused_v2` + functional smoke | **fused_v2 serving proven** (first time); read-skip executes | (commits) |
| **P3 — real needle** | needle through production fused_v2 + read-skip | byte-eq 6/6; **quality 1.0**; throughput **2× slower** (v1) | `PHASE9_P3_RESULT.md` |
| **P4 — profile** | attribute the slowdown | NOT dispatch-bound: overhead ~25%; attention 67% didn't shrink (config kept ~80%) | `PHASE9_P3_RESULT.md` §P4 |
| **P4b/c — regime** | aggressive skip + longer generation | quality 1.0 at **86% skip**; throughput **−48.7% → −20% → breakeven** | `PHASE9_P3_RESULT.md` §P4b/c |

## The verdict

- **Quality + correctness: PROVEN on the production kernel.** Needle 1.0 at every
  depth up to 86% skip; off-vs-retain_all byte-eq 6/6. The H2O quality risk —
  the genuinely uncertain part — is retired.
- **Throughput: viable — breakeven, up from 2× slower**, reached purely by entering
  the right regime (enough skip + amortized observe), quality free throughout.
- **Not a hardware mandate.** We never hit a dispatch floor only silicon breaks;
  PCAM stays correctly parked. Remaining gains are known software optimizations
  (kernel-emitted block scores — the biggest lever; longer context; v2 in-kernel
  skip) toward the cost model's ~1.9×.
- **The product is untouched.** int4_protected density + quality stand regardless.

## Mapping to the goal ("most token value per watt per user")

- **per user** (density) — shipped. **token value** (accuracy) — shipped, *including
  under read-skip*. **per watt** (read-skip throughput) — moved from negative to
  breakeven at preserved quality, with headroom. Two of three levers proven; the
  third now viable and trending.

## A meta-lesson worth keeping

The build's hardest fights were **measurement validity, not the algorithm**: an
eager+bf16 QK-matmul precision artifact (fixed with fp32) and number-laden filler
each masqueraded as quality failures until the baseline was forced to 1.0; and the
"2× slower" headline turned out to be a wrong-regime config (~80% retained), not a
fundamental tax. *Validate the yardstick before judging the policy* — every
premature verdict here was a baseline bug.

## Pick-up point for the next session

1. **Kernel-emitted block scores** (fused kernel already computes softmax `p` → sum
   per block): removes the full-K torch scoring + observe-phase full read. Largest
   expected lever from breakeven toward a real win.
2. **Longer context (16k/32k)** runs — the prize grows with length (Step 0).
3. **v2 in-kernel block-skip** to remove the residual host gather.
All upside; the sign is already non-negative and quality is settled.
