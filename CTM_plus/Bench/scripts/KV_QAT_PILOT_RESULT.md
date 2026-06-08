# KV-aware fine-tune PILOT — RESULT (negative, well-qualified)

> **Verdict: a light LoRA KV-QAT fine-tune does NOT make Qwen2.5-7B measurably more
> int4-tolerant than a plain LoRA control (`B1 − B0 ≈ 0` at two distortion
> strengths).** So this lever does **not** reduce protected-sidecar dependence; the
> +4.7 GB footprint tax is **not** removed by it. The memory verdict
> (`MEMORY_STORY.md` §6: density-positive, **footprint-negative**) stands.

## Setup

- Qwen2.5-7B-Instruct; LoRA r=16 on q/k/v/o (10.1 M params, **0.13%**); 200 steps;
  `Salesforce/wikitext` (wikitext-103-raw-v1); seq 4096.
- **Post-RoPE** K + V fake-quant via `INT4CacheKVRouteA.round_trip_kv` (dequant_fallback
  = naive int4 = the design's **0%-protect** arm), straight-through estimator.
- Arms: **A0** base (no train), **B0** LoRA + **no** fake-quant (control, captures
  fine-tune drift), **B1** LoRA + KV-QAT.
- Eval (`kv_qat_eval.py`): teacher-forced argmax **token-agreement, int4-KV vs
  bf16-KV**, 32 × 512 wikitext-test positions, using the **same** `round_trip_kv`
  distortion as training (train==eval parity — no fused_v2 gap). Measured at
  group-32 and group-128.

## Numbers — int4-vs-bf16 token-agreement

| arm | group-32 | group-128 |
|---|---:|---:|
| A0 base | 0.9498 | 0.9325 |
| B0 control | 0.9624 | 0.9484 |
| **B1 KV-QAT** | **0.9609** | **0.9493** |
| **B1 − B0** | **−0.0015** | **+0.0009** |

`B1 − B0` is within noise (|Δ| ≈ 15–25 of 16,352 positions) at **both** strengths.
B0 alone captures the entire (small, +0.013–0.016 over base) benefit; KV-awareness
adds nothing on top.

## Why (consistent across signals)

- **Training loss B1 ≈ B0 throughout** (B1 only ~0.005–0.02 higher). Cross-entropy is
  insensitive to the KV distortion → **weak adaptation pressure** → no inference-time
  robustness gain. The eval confirms what the train curve foreshadowed.
- **KILL GATE 4** triggered at group-32 and re-confirmed at group-128.
- **Stage-5 sidecar sweep (protect 5/3/0) is MOOT** and was not run: with no
  robustness gain over the control, there is nothing that would let B1 drop protect
  channels where B0/base could not.

## Honest scope — what this does and does NOT claim

- Tests **one cheap lever**: LoRA (0.13% of params), 200 steps. It does **not** test
  full fine-tuning, longer/larger QAT, or **learned rotations (SpinQuant/QuaRot)** —
  the heavier interventions the literature used to actually remove outlier dependence.
  Claim is therefore **"light LoRA KV-QAT doesn't help,"** NOT "training can't help."
- The eval metric (teacher-forced argmax) is **near-ceiling** (base 0.93–0.95 even
  under int4) — less sensitive than a generation-based / downstream-task metric, and
  far gentler than the brief's naive-int4 0.533 (a harsher/generation measure). The
  null is **robust across two strengths**, but a more sensitive eval could surface
  effects this one can't. Direction (no gain) is clear; absolute headroom is limited.

## Implication

- The post-hoc int4_protected sidecar tax is **not** removed by this training lever;
  the density-not-footprint memory framing is unchanged.
- The training-side counterfactual, **as cheaply tested, does not flip the memory
  story.** If revisited, higher-EV levers (in rough order): (a) **learned rotation
  before quant** (SpinQuant-style — removes K outliers *without* fine-tuning), (b)
  full FT / longer QAT, (c) a **generation/downstream** eval for sensitivity, (d) a
  harsher quant (2-bit) to open real headroom.

## Follow-up: rotation lever (QuaRot/SpinQuant-style) — ALSO negative, and instructive

Training-free test (`kv_qat_rotation_test.py`, base Qwen2.5-7B, group-128, Hadamard on
head_dim=128): rotate Q,K post-RoPE by an orthogonal `R` (attention scores preserved),
then quantize the **rotated** K (V bf16 to isolate K).

| metric | raw K-int4 | rotated K-int4 |
|---|---:|---:|
| K quant rel-error | 0.0238 | **0.0251 (worse, +5%)** |
| token-agreement vs bf16 | 0.9464 | 0.9432 (−0.003) |

Rotation did **not** help — it slightly hurt. **Why:** `round_trip_kv` already quantizes
K **per-channel** (each channel its own scale) — which *is* the outlier handling rotation
provides. QuaRot's win is for **per-tensor** quant (one outlier channel forces a huge
tensor-wide scale); against per-channel quant, rotation only smears the channel structure
the quantizer already exploits → neutral-to-harmful. (Exactly why KIVI/KVQuant use
per-channel K.)

**Meta-finding (both levers):** in this regime K int4 error is already tiny (~2.4%) and
agreement ~0.95 — barely a problem for any lever to fix. The protect sidecar earns its
keep on the **hard tail** (the brief's 0.533→0.737 token-agreement on the *serving* path /
hard-retrieval), which this cheap teacher-forced + `round_trip_kv` harness does not reach.
So neither training nor rotation helped *where we can cheaply measure*; definitively
settling "can you drop protect" needs the **hard regime** (fused_v2 serving quant /
generation-based / long-context).

**Combined verdict: both cheap "remove-the-tax" levers (KV-QAT training, Hadamard
rotation) are negative in the measurable regime. The density-not-footprint memory story
stands.**

## Hard-regime confirmation (free generation) — the "too easy" caveat is RESOLVED

The teacher-forced metric was near-ceiling. Re-ran in the harsh regime: greedy free
generation, use_cache=False (full-block requant), 16 wikitext prompts × 48 gen tokens,
int4-vs-bf16 (`kv_qat_gen_eval.py`, group-32).

| arm | gen agreement | mean common-prefix /48 |
|---|---:|---:|
| A0 base | 0.236 | 8.2 |
| B0 control | 0.237 | 9.4 |
| B1 KV-QAT | **0.194** | **7.4** |

int4 NOW bites hard — generation agreement crashes 0.95 → ~0.24 (cascading), so there
is real headroom. And **B1 − B0 = −0.043** (B1 slightly WORSE, shorter prefix). Even
where int4 genuinely wrecks generation, KV-QAT does NOT help — marginally hurts. The
"too easy" caveat is resolved: **the training negative is now definitive across easy
AND hard regimes (B1 ≤ B0 in both).**

## Lever 3 result + FINAL SYNTHESIS — three cheap levers, all negative

**Scale-metadata probe** (`kv_qat_scale_probe.py`, base Qwen2.5-7B, group-32): can a
per-vector norm + random rotation + FIXED int4 quantizer (no per-block scales) match
per-channel int4?

| scheme | K quant rel-error | scale metadata (scalars/token·head) |
|---|---:|---:|
| per-channel int4 (current) | 0.0176 | 8 |
| polar-core (fixed quantizer) | **0.1249 (7.1× worse)** | 1 |

No. Dropping per-block scales inflates K error 7.1×. Qwen2.5's K is strongly
anisotropic — after a random rotation the coordinates do NOT become the uniform
≈N(0,1/D) the fixed quantizer assumes, so it misallocates bins on exactly the
informative directions. Reclaiming the 3.4 GB this way needs the full TurboQuant
pipeline (data-dependent Lloyd-Max + a 1-bit QJL corrector + custom kernels) — a real
engineering project, not a cheap probe.

### Three independent cheap levers to remove the KV tax — ALL negative

| lever | targets | result | why |
|---|---|---|---|
| **1. KV-QAT training** (LoRA) | protect channels | **negative** (B1−B0 ≈ 0 easy; −0.043 hard) | light FT doesn't undo outlier geometry; slightly worse in free-gen |
| **2. Outlier rotation** (Hadamard/QuaRot) | protect ch. (~1 GB) | **negative** (K err +5%, 0.0238→0.0251) | `round_trip_kv` already **per-channel** → rotation redundant/harmful |
| **3. Scale-metadata** (rot + fixed quant) | scale/xmin (~3.4 GB) | **negative as cheap lever** (K err 7.1× worse) | anisotropic K breaks the uniform-sphere assumption; needs QJL kernels |

> **Record correction:** Hadamard outlier-rotation (lever 2) is **NOT** a confirmed
> win here — it was **measured negative** (+5% error). QuaRot helps **per-tensor**
> quant; against an already **per-channel** KV quantizer it is redundant. Any
> recommendation to "execute Hadamard rotation for a cheap win" contradicts the data.

**Bottom line:** none of the three cheap levers removes the protect/scale tax on
Qwen2.5-7B. Common thread — the K representation is already well-served by per-channel
int4, and its anisotropic outlier structure defeats data-oblivious transforms (for
outliers *and* for metadata). The protect sidecar exists because the hard tail
genuinely needs it; no cheap transform removes that need. **The density-positive,
footprint-negative memory verdict (`MEMORY_STORY.md` §6) is the final, tested
conclusion.** The only remaining path — a full TurboQuant Lloyd-Max + QJL + custom
kernel pipeline — is a real engineering project with uncertain payoff: documented,
not recommended.

## Cross-model check — Mistral-7B-Instruct-v0.3 (cheap levers generalize)

Re-ran the two training-free probes on Mistral (model-agnostic hooks):

| probe | Qwen2.5-7B | Mistral-7B-v0.3 |
|---|---|---|
| rotation: per-channel K err (g128) | 0.0238 | 0.0607 |
| rotation: + Hadamard | 0.0251 (+5%) | 0.0640 (+5%) → still WORSE |
| scale-probe: per-channel K err (g32) | 0.0176 | 0.0449 |
| scale-probe: polar-core fixed | 0.1249 (7.1×) | 0.1244 (2.8×) → still WORSE |

Both cheap levers replicate as **negative** on Mistral — same direction, same
mechanism. The Qwen conclusions **generalize across model families.**

Nuance: Mistral's K is ~2.5× **harder** to per-channel int4-quantize (0.045 vs 0.018
at g32). The polar-core absolute error is ~identical across both (~0.124 — the
fixed-quantizer floor), so Mistral's smaller ratio is just a worse baseline, not a
working lever. Mistral leans MORE on the protect sidecar → it also has more headroom
for the one lever NOT re-tested here, **KV-QAT training** — the only regime where a
Mistral re-run could still surprise.

### Mistral training (B0/B1) — small, noisy, opposite-sign to Qwen; still no win

Hard-regime free-gen agreement (group-32), 16 prompts × 48 tokens:

| arm | Qwen2.5-7B | Mistral-7B-v0.3 |
|---|---:|---:|
| base (A0) | 0.236 | 0.740 |
| b0 control | 0.237 | 0.580 |
| b1 KV-QAT | 0.194 | 0.619 |
| **B1 − B0** | **−0.043** | **+0.038** |

- **B1 − B0 flips sign across models** (−0.04 Qwen, +0.04 Mistral) and both are within
  the high-variance noise band (per-prompt 0.58–1.0). b0 was eval'd on the merged save,
  b1 in-process (LoRA-active) — same forward in theory, but the sign isn't airtight.
- **Neither b1 beats its base** (Qwen 0.194<0.236; Mistral 0.619<0.740). KV-QAT does
  NOT make the model more int4-robust than the untrained model on either family.
- **New Mistral nuance:** plain LoRA FT (b0) *hurt* int4 robustness (0.74→0.58) — didn't
  happen on Qwen — and KV-QAT only partially clawed that back (→0.62), not to base.

**Cross-model verdict on the training lever: no consistent benefit (B1−B0 ≈ 0 ± noise,
sign-unstable), and in no case does training beat baseline int4 robustness. KV-QAT
stays negative; FT can even hurt. Density-not-footprint stands.**

## Reproduce

```bash
# train (per arm)
PYTHONPATH=KVPolicy python Bench/scripts/kv_qat_pilot.py --arm b0 --steps 200 --max-seq-len 4096 --merge --output kv_qat_b0
PYTHONPATH=KVPolicy python Bench/scripts/kv_qat_pilot.py --arm b1 --steps 200 --max-seq-len 4096 --merge --output kv_qat_b1
# eval (per arm, per group size)
for M in Qwen/Qwen2.5-7B-Instruct ./kv_qat_b0 ./kv_qat_b1; do
  PYTHONPATH=KVPolicy python Bench/scripts/kv_qat_eval.py --model $M --group-size 32
  PYTHONPATH=KVPolicy python Bench/scripts/kv_qat_eval.py --model $M --group-size 128
done
```

## Pointers

| thing | where |
|---|---|
| Design + hypotheses | `KV_AWARE_TRAINING_EXPERIMENT_DESIGN.md` |
| Runbook + gates | `KV_QAT_PILOT_RUNBOOK.md` |
| Train harness | `Bench/scripts/kv_qat_pilot.py` |
| Eval | `Bench/scripts/kv_qat_eval.py` |
| Fake-quant core (STE + parity) | `KVPolicy/kv_policy/kv_aware_qat.py` |
| Memory verdict (unchanged) | `MEMORY_STORY.md` §6 |
