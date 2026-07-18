# Step 2/3 instrument — RAW output (Qwen2.5-7B-Instruct)

Real-model-path instrumentation of the QUALIFIED harness. Data only — verdict is deferred to Step 6.

## Provenance
- harness commit: `ac0f4222` (instrument) / measured on that tree
- instrument: `CTM_plus/Bench/scripts/bench_kv_format_instrument.py`
- model: `Qwen/Qwen2.5-7B-Instruct`, wikitext-2 test, ctx=4096, tail-50% PPL
- JSON artifacts: `nvfp4_instrument_pf02.json`, `nvfp4_instrument_pf06.json` (on pod `/workspace/...`)
- command:
  ```bash
  for pf in 0.02 0.06; do
    python CTM_plus/Bench/scripts/bench_kv_format_instrument.py \
      --model Qwen/Qwen2.5-7B-Instruct --protect-frac $pf \
      --formats bf16,int4_protected,nvfp4,nvfp4_protected 2>&1
  done
  ```

## Step 2 — eval metrics + real-KV invariants

| pf | format | PPL | meanCE | tok p50 | p95 | p99 | max | NaN/Inf |
|--:|---|--:|--:|--:|--:|--:|--:|:--:|
| 2% | bf16 | 5.1754 | 1.6439 | 0.757 | 6.175 | 9.823 | 16.157 | False |
| 2% | int4_protected | 5.1787 | 1.6446 | 0.788 | 6.119 | 9.805 | 16.627 | False |
| 2% | nvfp4 | 3098.25 | 8.0386 | 7.607 | 13.993 | 16.349 | 19.323 | False |
| 2% | nvfp4_protected | 13292.88 | 9.4950 | 9.567 | 14.797 | 16.797 | 24.890 | False |
| 6% | int4_protected | 5.2378 | 1.6559 | 0.770 | 6.260 | 9.923 | 16.877 | False |
| 6% | nvfp4_protected | 19.4090 | 2.9657 | 2.189 | 8.461 | 11.589 | 18.376 | False |

**Real-KV invariants (captured layer-0 Qwen K), both pf: ALL PASS**
`0pct==plain_int4`, `0pct==plain_nvfp4`, `100pct==bf16_int4`, `100pct==bf16_nvfp4`,
`protect_replaces_int4`, `protect_replaces_nvfp4`. ⇒ emulation faithful; NOT an integration bug.

## Step 3 — per-layer trace (plain NVFP4 vs protected NVFP4)

Key structure: reconstruction error is dominated by BOUNDARY layers 0 and 27 ("massive activations").
Middle-layer `unprot` K-MSE ≈ 0.02–0.06; **layer 0 ≈ 3.7–5.0, layer 27 ≈ 7.1–9.1** (100–450x higher).
Attention-output MSE at **layer 27 ≈ 0.67–0.72** vs ≤0.03 elsewhere — L27 dominates the error budget.

- `coupling_delta < 0` at EVERY layer (mean −0.132 @2%, −0.184 @6%): protecting IMPROVES unprotected-
  channel reconstruction everywhere. ⇒ the anomaly is NOT reconstruction coupling.
- @2%: layers where protected perturbs attention MORE than plain = 4/28, mean attn_delta +0.00033.
  The dominant layer 27 has attn_delta **+0.044** (protected WORSE) — partial protection at L27 breaks
  error-cancellation, and because L27 dominates, the whole model degrades (PPL 13293 > plain 3098).
- @6%: 5/28 layers, mean attn_delta −0.0115; layer 27 attn_delta **−0.285** (protected MUCH better) ⇒
  recovery to PPL 19.4. So the 2%→6% flip is driven by layer 27.

**Instrument classification (both pf):** "Neither recon-coupling nor mean attention perturbation is
worse for protected — the anomaly concentrates in a few layers/tokens, not a uniform effect. NOT noise
until those specific rows are explained." → the specific rows (layers 0 & 27) ARE now explained:
NVFP4's per-16-channel block scale cannot represent Qwen2.5's boundary-layer per-channel outliers;
partial protection at 2% is non-monotonic at L27. Not RNG, not a bug — a real NVFP4 format property.

Caveat: deep-layer `attn_mse` uses each run's own (already-drifted) bf16 reference, so deep-layer
numbers are approximate; layer 0 is drift-free and the L27 magnitude is far too large to be drift.
Unconfounded signals (PPL, token percentiles, invariants) corroborate.

## Per-layer table @ 2% (verbatim)

```
  layer   unprot_pl   unprot_pr    couple_Δ  attnMSE_pl  attnMSE_pr       attnΔ  worse?
      0      4.9784      3.7136      -1.265    0.014538    0.016464   +0.001926  <<<
      3     0.18952     0.093968   -0.09555  0.00076639  0.00045601  -0.0003104
     13     0.065275      0.0313    -0.03398   0.0021906   0.0011246   -0.001066
     19     0.059801     0.029931   -0.02987   0.0040365   0.0011286   -0.002908
     26     0.023165     0.016971  -0.006195    0.027718    0.012486    -0.01523
     27      9.1114      7.0891      -2.022      0.6722     0.71644    +0.04424  <<<
  (middle layers omitted; full data in nvfp4_instrument_pf02.json)
  RECON coupling>0: 0/28  mean -0.13211    DOWNSTREAM attn worse: 4/28  mean +0.00033  first layer 0
```

## Per-layer table @ 6% (verbatim, boundary rows)

```
  layer   unprot_pl   unprot_pr    couple_Δ  attnMSE_pl  attnMSE_pr       attnΔ  worse?
      0      2.9512      1.0466      -1.905    0.014538   0.0047085   -0.009829
     27       3.487     0.71496      -2.772      0.6722     0.38679     -0.2854
  RECON coupling>0: 0/28  mean -0.18442    DOWNSTREAM attn worse: 5/28  mean -0.011525  first layer 11
```
