# Phase 9 — read-skip proxy RESULT (the kernel de-risk)

> **Status: MEASURED (GPU, sliding-window proxy on Mistral-7B-Instruct-v0.1).**
> Valid cells (non-degenerate). Settles Step-0's two IFs as far as a *fixed-window*
> proxy can. Companion to `PHASE9_READSKIP_PROXY_RUNBOOK.md`.

## The measurement (context=4000, window=1024; OFF=full attention)

| depth | needle in window? | ON (read-skip) hit | OFF (full attn) hit |
|---:|:--:|---:|---:|
| 0.10 | no  | 0/4 | 4/4 |
| 0.50 | no  | 0/4 | 4/4 |
| 0.80 | yes | 1/4 | 4/4 |
| 0.95 | yes | 0/4 | 4/4 |

Throughput: ON 26.96 vs OFF 20.62 tps = **+30% at 4k**; **~10× at 16k** (earlier
run). The win **scales with context length** — exactly the Step-0 prediction.

`mean_gen_tokens`: ON 12.9, OFF 8.4 (both >3 → non-degenerate → valid).

## What it establishes

1. **Throughput prize is REAL and length-scaling.** This was the uncertain half
   going in (Step 0 *modeled* it). Now measured: read-skip decode is cheaper and
   the gap widens with context (+30% @4k → ~10× @16k). ✅
2. **Full-attention baseline is perfect (4/4 all depths)** — the model + task
   work, so the ON misses are about read-skip, not a broken harness.
3. **Fixed-pattern read-skip is quality-destructive.** It zeroes the
   outside-window needles (the expected H2O loss) **and** degrades the
   inside-window ones (0.95 → 0/4).

## The two caveats that stop this being a clean "build it"

- **The inside-window misses are partly a proxy artifact.** We forced
  `window=1024`, *below* Mistral's trained 4096 window → the ON cell is
  out-of-distribution (the model never saw a 1024 window), which degrades even
  in-window retrieval. Mistral cannot give a clean *in-distribution* fixed-window
  read-skip test: its viable full-attention band (~4k, ≈ its native window)
  leaves no room to skip in-distribution. The 16k attempt failed the other way
  (full attention OOD → degenerate). So the quality magnitude here is an
  upper bound on the damage, inflated by the forced sub-training window.
- **A FIXED window cannot test the kernel's actual value-add.** The real kernel
  would keep **sinks + recent + high-attention** tokens (H2O/SnapKV-style); the
  proxy keeps only a recent window. So the proxy measures the *floor* (dumb
  fixed skip), not what attention-guided retention recovers — which is precisely
  the unknown the build would resolve.

## Verdict: a genuine bet, not a slam-dunk

The de-risk converted Step-0's two IFs into measurement:
- **Throughput IF → confirmed** (real, length-scaling).
- **Quality IF → at real risk.** Fixed read-skip is destructive; the kernel's
  whole thesis is that attention-guided retention recovers it. Our proxy shows
  the damage is large enough that this recovery is a *real* bet, and it is the
  one thing a fixed-window proxy cannot prove — only the build can.

So the kernel go/no-go is now a well-characterized strategic bet:
- **Build** if the org wants the (length-scaling) throughput prize and believes
  the H2O/SnapKV result that learned/attention-guided retention recovers quality.
  The build's first gate must be: read-skip with sink+high-attention retention
  keeps needle + MMLU within noise (the thing the proxy couldn't test).
- **Park** if certainty is preferred: density (1.83×) + quality (= bf16) remain
  the proven, shippable product; read-skip stays bounded upside behind this bet.

This is the honest end state of the cheap de-risk: throughput proven, quality
risk real, retention-recovery unprovable without the build. PCAM-as-hardware
stays gated on the same bet (it is the fast-path embodiment of the retention
decision).
