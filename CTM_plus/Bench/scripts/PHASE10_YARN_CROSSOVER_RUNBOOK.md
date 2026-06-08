# Phase 10 — YaRN long-context crossover runbook (prove read-skip goes throughput-POSITIVE)

> **Goal.** Phase 10 measured read-skip `retention` at **−10.6% vs full-int4 at 32K**,
> with the A/B gap **halving 16K→32K** and extrapolating to a **~50K crossover**
> (see `PHASE10_FINAL_VERDICT.md`). The crossover sits past Qwen2.5-7B's **32K native
> window**, so we couldn't measure it — only extrapolate. This run extends the
> context with **YaRN rope-scaling** and turns the extrapolation into a measured
> number: **does `retention` cross above `off` somewhere around 48–56K, and how
> positive is it at 64K?**

## The one harness change (committed, low-risk)

`phase9_p3_fused_needle.py` now takes **`--hf-overrides '<json>'`**, passed straight
to `vLLM LLM(hf_overrides=...)` across all three engine builders (off / retention /
bf16). Empty = byte-for-byte the prior behavior (unit-checked). Its purpose is to
inject `rope_scaling` so a 32K-native model can run past its window.

## YaRN config

Qwen2.5-7B is native 32K. **Factor 2.0 → 65 536** covers the whole 40–64K sweep
(use the *smallest* factor that covers your max context — a larger factor degrades
sub-32K quality more than necessary):

```
'{"rope_scaling":{"rope_type":"yarn","factor":2.0,"original_max_position_embeddings":32768}}'
```

> ⚠ **Key-name fallback.** vLLM 0.7.3 / transformers version may want `"type":"yarn"`
> instead of `"rope_type":"yarn"`. If the engine errors on the rope config at
> startup, flip that one key. The harness passes the JSON verbatim, so it's a
> one-character change — no code edit.

## Quality gate (do this first — a positive tps with broken recall is worthless)

Static YaRN perturbs RoPE everywhere, so **confirm needle still passes at extended
context before trusting any speed number.** The A/B is apples-to-apples (both `off`
and `retention` use the *same* YaRN rope), but if YaRN itself breaks retrieval at
56–64K the experiment is moot. Gate: **needle must stay 1.0/1.0** at each context.
If it drops for *both* modes, that's a YaRN-quality ceiling, not a read-skip
problem — note it and cap the sweep where needle still holds.

## Run — YaRN crossover sweep

Same tuned read-skip config as the verdict (`KERNEL_SCORES`, sink 64 / recent 512 /
budget 512, `REFRESH=0`). One consistent rope (YaRN factor 2) across the whole
sweep so the Δ% trend is continuous. Anchor at 32K (should reproduce ~−10.6%, i.e.
YaRN didn't distort the comparison), then climb through the predicted crossover:

```bash
cd /workspace/symbolu && git pull origin claude/bold-johnson-rXAd4 && cd CTM_plus
YARN='{"rope_scaling":{"rope_type":"yarn","factor":2.0,"original_max_position_embeddings":32768}}'

for CTX in 32000 44000 52000 60000; do
INT4_READSKIP_KERNEL_SCORES=1 INT4_READSKIP_SINK=64 INT4_READSKIP_RECENT=512 \
INT4_READSKIP_BUDGET=512 INT4_READSKIP_REFRESH=0 \
python Bench/scripts/phase9_p3_fused_needle.py --ab --ab-modes off,retention \
  --context-tokens $CTX --max-model-len 65536 --hf-overrides "$YARN" --ab-gen 128 \
  --seeds 1,2,3 --depths 0.1,0.5 --repeats 3 --warmup 2 \
  --out Bench/bench_out/PHASE10_AB/yarn_ctx${CTX}.json
done
```

- **`--max-model-len 65536`** must exceed `context + gen + prompt overhead`; 64K
  context won't fit under 65 536, hence the 60 000 top of the sweep.
- **OOM risk at 60K:** `off` holds the full int4 KV for 60K × the batch. If the
  engine OOMs at init, raise `--gpu-util 0.7` (default 0.6) or trim the top point.
- Skip fraction will rise to **~97%** at 60K (retained stays budget-bounded ~1.7K
  while context grows) — that's the whole point: bounded retained vs linear `off`.

## What to look for → the decision

Tabulate `retention vs off` Δ% per context:

| ctx | predicted | read |
|---|---|---|
| 32K | ~−10.6% (anchor) | reproduces native? (validates YaRN didn't skew it) |
| 44K | ~−4% | closing |
| 52K | **~0% (crossover)** | **the number** |
| 60K | **positive** | the headline: read-skip *faster* than full-attention |

- **Crosses positive by ~52–60K, needle 1.0/1.0** → the read-skip thesis is
  *measured*, not extrapolated. Update the VC brief's projected row to MEASURED and
  this is the slide: *"at 60K, read-skip decodes faster than full-attention while
  reading 97% less KV, quality preserved."*
- **Stays negative through 60K** → the extrapolation was optimistic; the structural
  gather cost is larger than modeled. Fall back to the **density** framing (already
  the verdict) and don't claim a speed crossover.
- **Needle drops for both modes at high ctx** → YaRN quality ceiling; report the
  crossover only up to where recall holds, and note Qwen2.5-7B needs a better
  long-context base (or a natively-long model) for the full demo.

## Notes

- This sweep uses YaRN at 32K too (for a consistent rope); that point is the
  control. If YaRN-32K diverges a lot from the native-32K −10.6%, the rope change
  is confounding the comparison — investigate before trusting the high-ctx points.
- A natively-long model (e.g. a 128K-trained Qwen/Llama) would remove the YaRN
  caveat entirely and is the cleaner demo if available — the `--hf-overrides` flag
  is then simply left empty.

---

## NEXT VALID TEST — native long-context model (no YaRN), with a hard claim gate

YaRN factor-2 on 32K-native Qwen2.5-7B **broke quality** (needle 0.0/0.0 even at 32K)
while still showing the throughput crossover (~42K, +2.5% at 44K). So the crossover
*physics* are confirmed but **not usable**. The only valid way to claim a real
crossover is on a model **natively trained for long context** — no rope hacking — so
the quality gate can actually pass.

**Model (primary): `Qwen/Qwen2.5-7B-Instruct-1M`** — *same architecture* as the tested
read-skip backend (28L, 4 KV heads, D=128), so the int4 route-A kernels work
unchanged, but natively long (no YaRN; leave `--hf-overrides` empty).
**Fallback: `meta-llama/Llama-3.1-8B-Instruct`** — standard attention, native 128K,
already int4_protected-validated; use if the Qwen-1M config trips vLLM 0.7.3 (DCA).

**Step 1 — sanity at short ctx (loads in int4 read-skip + quality intact?):**
```bash
M=Qwen/Qwen2.5-7B-Instruct-1M
INT4_READSKIP_KERNEL_SCORES=1 INT4_READSKIP_SINK=64 INT4_READSKIP_RECENT=512 \
INT4_READSKIP_BUDGET=512 INT4_READSKIP_REFRESH=0 \
python Bench/scripts/phase9_p3_fused_needle.py --ab --ab-modes off,retention \
  --model $M --context-tokens 8000 --max-model-len 65536 --ab-gen 64 \
  --seeds 1 --depths 0.5 --repeats 2 --warmup 1 \
  --out Bench/bench_out/PHASE10_AB/native_sanity.json
```
**Gate 1:** quality must be `1.0/1.0`. If 0.0 → the model isn't running correctly in
the int4 backend (or DCA conflict) → switch to the Llama fallback before sweeping.

**Step 2 — crossover sweep (only if Gate 1 passed), NO `--hf-overrides`:**
```bash
for CTX in 32000 44000 52000 60000; do
INT4_READSKIP_KERNEL_SCORES=1 INT4_READSKIP_SINK=64 INT4_READSKIP_RECENT=512 \
INT4_READSKIP_BUDGET=512 INT4_READSKIP_REFRESH=0 \
python Bench/scripts/phase9_p3_fused_needle.py --ab --ab-modes off,retention \
  --model $M --context-tokens $CTX --max-model-len 65536 --ab-gen 128 \
  --seeds 1,2,3 --depths 0.1,0.5 --repeats 3 --warmup 2 \
  --out Bench/bench_out/PHASE10_AB/native_ctx${CTX}.json
done
```

## THE CLAIM GATE (both must hold, at the same context)

> Claim "read-skip is throughput-positive at long context" **only if**, at some ctx:
> 1. **`retention vs off` > 0** (throughput crossover), AND
> 2. **needle quality = 1.0 / 1.0** (model still does the task).
>
> Throughput-positive with broken quality (the YaRN result) is **not a claim** — it's
> mechanism confirmation. Quality-intact but throughput-negative is **not a claim**
> either. Both, together, or it stays "projected."
