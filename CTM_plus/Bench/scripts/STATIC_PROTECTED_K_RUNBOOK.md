# §20.4.2 follow-on — static outlier-protected K + the roadmap to ship

Status: **harness landed CPU-side, unit tests green.** One GPU run pending.

## Why — the gap between §20.4.2 and a shippable claim

§20.4.2 measured **protected-K (top 4% of K channels at FP16) + V-INT4 →
100% needle at 16k, ~3.1× compression** — the first config that beats FP8.
But that sweep selected the outlier channels **dynamically** (recomputed
per block from the live K). A shippable cache cannot do that — it needs a
**fixed** channel set. This experiment closes that gap.

`--k-protect-static` freezes the protected channel set per layer on the
first (prefill) update and reuses it for every later update — the
per-sequence-static config. If it holds the dynamic result's quality, the
ship config is essentially validated; full offline-corpus calibration
(Roadmap Exp 5) becomes a robustness step rather than an open question.

## Experiment 1 — static-protection validation (run now)

Prerequisites: identical to the K-INT8 run — pod, packages, `pip uninstall
-y torchvision`, HF cache on `/workspace` or `/dev/shm`. The branch must
include `--k-protect-static` (`... --help | grep k-protect-static`).

```bash
cd /workspace/symbolu/CTM_plus/Bench
mkdir -p bench_out/protected_k_static
for FRAC in 0.02 0.04; do
  echo "=== static k_protect_fraction=${FRAC} ==="
  python -m ctm_bench.scripts.track_e_long_context \
    --model Qwen/Qwen2.5-7B-Instruct --dtype float16 --device auto \
    --context-lengths 16000 --needle-depths 0.1,0.5,0.9 \
    --needle-samples 8 --needle-decode-tokens 64 --skip-perplexity \
    --k-bits 4 --v-bits 4 \
    --k-protect-fraction ${FRAC} --k-protect-static \
    --output bench_out/protected_k_static/static_${FRAC}.json
done
```

~10 min, 2 cells. Compare against the §20.4.2 **dynamic** results:
dynamic 2% = 96%, dynamic 4% = 100%.

### Decision rule

* **static 4% holds ~100%** (within noise) → a frozen channel set works;
  the per-sequence-static config is validated. Proceed to Roadmap Exp 5
  (offline calibration) for the model-static ship version, and in parallel
  to Exp 6 (throughput) — the real gate.
* **static 4% drops materially below dynamic** → the prefill-derived set
  is insufficient. Bump the fraction (try 0.06 / 0.08 static) and/or move
  straight to per-layer / offline calibration (Exp 3 / Exp 5).
* Either way, **note throughput is still unmeasured** — quality validation
  does not make this shippable on its own.

## Roadmap — taking protected-K to a shippable, FP8-beating product

Quality is now in good measured shape; the experiments below split into
*cheap quality de-risking* (Exp 2–5) and *the decisive cost* (Exp 6).

| # | Experiment | Question | Cost | Why it matters |
|---|---|---|---|---|
| 2 | **32k long-context** | Does protected-K hold at 32k, not just 16k? | cheap (~15 min) | KV memory dominates at long context — that's the whole value prop. Run `track_e_long_context.py --context-lengths 32000` with protected-K. |
| 3 | **Per-layer protection budget** | Do all layers need 4%, or do some tolerate 1–2%? | cheap | K outlier structure varies by layer; a per-layer budget could push compression past 3.1× at the same quality. |
| 4 | **Multi-model replication** | Does the outlier-protection story replicate on Mistral-7B / Llama-3-8B? | cheap | Outlier channels are model-specific; the *approach* should generalize but must be checked before any general claim. |
| 5 | **Offline-corpus calibration** | Does a *model-static* channel set (calibrated once on a corpus, not per-sequence) hold quality? | medium | The true ship config. Builds on `calibrate_int4_scales.py`; gates the "fixed, no per-sequence cost" claim. |
| 6 | **Throughput / route-A** | Does protected-K KV actually run *fast* — competitive with FP8? | **expensive, decisive** | The dominant remaining risk. A mixed FP16-outlier + INT4 layout is *harder* for a fused kernel than uniform INT4; FP8 has hardware tensor-core support. **This is what decides whether protected-K is a real product or just a good quality result.** |
| 7 | **Downstream long-context tasks** | Does the 100% needle generalize to real tasks (long-doc QA, summarization)? | medium | Needle is one probe; breadth-of-quality evidence for partners. |

**Honest critical path:** Exp 1–5 are cheap and the quality story is
already strong — they broaden and harden a claim that's looking good. **Exp
6 (throughput) is the gate.** Protected-K at ~3.1× / 100% quality only
beats FP8 in practice if it also runs fast enough; until Exp 6 is measured,
"beats FP8" is a *compression-and-quality* claim, not an end-to-end one.
Recommended order: Exp 1 → Exp 2 (both cheap, do immediately) → Exp 6
(start the throughput/kernel work in parallel — it is the long pole) →
Exp 3/4/5/7 as quality-breadth fills in.
