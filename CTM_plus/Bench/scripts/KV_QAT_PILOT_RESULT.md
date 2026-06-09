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

## Head-wise mixed precision (Option 1) — beats channel-protect on K RECON error (the one positive)

`kv_qat_headwise_probe.py`, at matched avg bits:

| model | uniform 4-bit | channel-protect 4% (4.47b) | head-mixed (4.50b) | per-head sens. spread |
|---|---:|---:|---:|---:|
| Qwen2.5-7B | 0.0268 | 0.0251 | **0.0201 (−20%)** | 2.48× (concentrated) |
| Mistral-7B-v0.3 | 0.0702 | 0.0651 | **0.0526 (−19%)** | 1.04× (flat) |

Head-granular bit allocation has **~20% lower K reconstruction error than
int4_protected's channel-bf16-protect**, on BOTH models — against the prior that finer
channel-granularity wins.

**Why (rate-distortion):** 4% of channels at bf16 (16-bit, over-precise) + 96% at 4-bit
is a lopsided allocation; spending the same budget as a uniform 4→~4.5-bit lift reduces
more total error (convex distortion → balanced beats extreme). Mistral's sensitivity is
FLAT yet head-mixed still wins → it's allocation efficiency, not head-concentration.

**CRUCIAL caveat — proxy vs downstream:** this is K *reconstruction* error, NOT model
quality. int4_protected's protect was validated DOWNSTREAM (token-agreement 0.737 vs
0.533, hard-needle) — it targets the outlier channels that *catastrophically* break the
attention inner product, which recon error under-weights. So head-mixed's lower recon
error does **not** establish it beats int4_protected on quality.

**Status: the ONE lever with a positive signal — but on a proxy.** Resolving test =
downstream token-agreement with head-mixed-allocated KV vs protect KV. If it holds
downstream, mixed-precision bit allocation is a real improvement to the int4_protected
design (Gemini's Option 1 instinct was right); if it evaporates, protect's value is the
catastrophic-outlier preservation recon error misses. Everything else (training,
rotation, scale-drop) stays negative.

### Downstream resolver — int4_protected WINS; head-mixed's recon edge inverts

Each K scheme applied at inference (fixed, calibrated; V bf16); perplexity + free-gen
token-agreement vs bf16:

| model | scheme | ppl-gap | gen-agree |
|---|---|---:|---:|
| Qwen2.5-7B | uniform-4b | +0.181 | 0.448 |
| Qwen2.5-7B | **protect [i4p]** | +0.133 | **0.523** |
| Qwen2.5-7B | head-mixed | +0.134 | 0.500 |
| Mistral-7B | uniform-4b | +0.050 | 0.807 |
| Mistral-7B | **protect [i4p]** | +0.009 | **0.930** |
| Mistral-7B | head-mixed | +0.016 | 0.737 |

**Channel-protect wins on BOTH metrics, BOTH models** — decisively on Mistral's hard
tail (0.93 vs 0.74). Head-mixed's ~20% *reconstruction*-error advantage **inverts**
downstream.

**Why:** protect's value is the catastrophic-outlier preservation that *average* metrics
(recon error, perplexity) under-weight. Head-mixed minimizes average K error but
under-protects the specific outlier channels whose error *cascades* in free generation.
Mistral (K 2.5× harder → leans more on protect) shows the large gap (+0.19). (gen-agree
is noisy, but protect ≥ head-mixed is consistent across 2 models × 2 metrics.)

**This validates int4_protected's channel-protect design on exactly the axis it was built
for.** The one lever that beat it on a proxy affirms it once measured downstream.

## FINAL VERDICT — every lever resolved

| lever | goal | result |
|---|---|---|
| KV-QAT training | remove protect tax | NEGATIVE (Qwen + Mistral; no gain, FT can hurt) |
| Hadamard rotation | remove protect (~1 GB) | NEGATIVE (redundant vs per-channel; Qwen + Mistral) |
| scale-metadata / polar | remove scale (~3.4 GB) | NEGATIVE cheap (needs heavy QJL kernels) |
| head-wise allocation | beat the protect *design* | wins recon error, **LOSES downstream** → protect validated |
| high-dim VQ (E8 lattice / HQMQ quaternion) | denser codec, recover hard tail | **PARKED** — its rotation + "no per-channel scale" + recon-MSE premises are exactly the three above (all negative here); multi-week kernel; → `VECTOR_QUANT_E8_HQMQ_EVAL.md` |
| **learned rotation + per-tensor** (SpinQuant/KurTail-style) | delete scale/protect (~3.4 GB) | **RESOLVED NEGATIVE — measured FAIL on 2 models.** Hard-tail gate: learned per-tensor **below even naive int4** on BOTH — Qwen 0.0404 / Llama 0.3854 vs protect 0.2656 / 0.5104. Llama is more rotatable (no layer-0 wall) but still loses; rotating to drop scales makes K *worse* than keeping them. TurboQuant package sym4 on Qwen = 0.0365 (8-bit sanity 0.70 → genuine low-bit wall). The one un-disproven lever is disproven. → §below |

**The CHEAP, data-oblivious removals are exhausted across two model families** (random/
Hadamard rotation, scale-drop, light KV-QAT all negative), and the protect-channel design
is downstream-optimal among them. The **one lever not yet disproven** is a **learned**
(data-dependent) rotation + per-tensor scale — the only point that can adapt to *where* K's
outliers live. The density-positive, footprint-negative memory verdict stands as the tested
conclusion **unless that learned-rotation probe clears a hard-tail gate** (§below).

## Lever 5 — learned rotation (the one open bet): RESOLVED NEGATIVE (measured)

> **RESULT (Qwen2.5-7B, pod, this run).** The one un-disproven lever is now disproven.
>
> **Phase A — recon screen** (`kv_qat_learned_rotation.py`, layers 0/13/27, ~2k tok):
> learned per-tensor K **never matches per-channel** — layer 0 **not_rotatable** (gap
> closed 4%, learned 0.103 vs per-channel 0.024 = 4.3× worse); layers 13/27 "rotatable"
> (80–83% gap closed) but still **1.6–1.9× worse** than per-channel (`matches_per_channel:
> False` everywhere). Learned **did** beat data-oblivious (hadamard/random) at deep layers
> — so learned > Hadamard/TurboQuant is confirmed — but rotation can't remove the residual
> (persistent/spectral) anisotropy.
>
> **Phase B — hard-tail gate** (`kv_qat_rotation_gate.py`, 16 prompts, free-gen, vs **protect**):
>
> | arm | free-gen agreement vs bf16 |
> |---|---:|
> | bf16 | 1.0 (ref) |
> | naive per-channel int4 | 0.2357 |
> | per-channel + **PROTECT** (the bar) | **0.2656** |
> | learned-R post-RoPE + per-tensor | **0.0404** |
>
> **FAIL by −0.225 vs protect.** Learned per-tensor (0.04) is **6× worse than even naive
> int4** (0.24): the ~1.6–4× per-token recon gap cascades over 48 free-gen tokens into a
> near-total collapse. The rotated single-scale K destroys generation.
>
> **CONFIRMED on a 2nd model — Llama-3.1-8B (more rotatable, still FAILs):**
>
> | arm | Qwen2.5-7B | Llama-3.1-8B |
> |---|---:|---:|
> | naive per-channel int4 | 0.2357 | 0.4714 |
> | per-channel + **PROTECT** (bar) | **0.2656** | **0.5104** |
> | learned-R + per-tensor | 0.0404 | 0.3854 |
> | learned − protect | −0.225 | **−0.125** |
>
> Llama's K is genuinely more rotatable (recon: no layer-0 wall, 1.5–1.8× residual vs
> Qwen's 1.6–4.3×; KurTail's "LLaMA-3 rotation-friendly" hint borne out) → learned per-tensor
> 0.39 vs Qwen's 0.04. **But it still FAILs**, and decisively: on BOTH models learned
> per-tensor is **below even naive per-channel int4** (Llama 0.385 < 0.471; Qwen 0.040 < 0.236).
> **Rotating to delete the scales makes K *worse* than keeping them** — there is no
> "trade per-channel for rotation" that wins.
>
> **Verdict: rotation cannot delete the ~3.4 GB scale/protect tax — measured on 2 models.**
> Now **6 independent lines** all negative: random-rotation scale-drop (7.1×), TurboQuant/QJL
> retirement (3052× ppl), KVLinC keeps per-channel K + adapters, Phase-A recon (no match),
> Phase-B gate **on Qwen (0.04) AND Llama (0.39)**, TurboQuant package sym4 on Qwen (0.0365,
> 8-bit sanity 0.70 → genuine low-bit wall). **Ship the hybrid scheduler.** Kernel work
> correctly NOT started (gated on a PASS that never came).
>
> *(Caveat on the bar: on this free-gen wikitext harness protect (0.27) only modestly beats
> naive (0.24) — int4 bites hard here; protect's larger advantage is on the serving-path /
> hard-needle metric, 0.737 vs 0.533. Immaterial to the verdict: learned loses to BOTH.)*

`kv_qat_learned_rotation.py` tests the single question the cheap negatives can't settle:
**is K's anisotropy *rotatable*?** It learns an orthogonal R by 4th-moment (kurtosis)
minimization on the Stiefel manifold (Cayley retraction), then asks whether per-tensor int4
in the rotated basis approaches per-channel. Output: a **gap-closed %** and a verdict
(`rotatable` / `partial` / `not_rotatable`).

**Three design fixes vs the external write-ups (all baked into the probe + tests):**
1. **First model = base Qwen2.5-7B (standard rope), NOT Qwen-1M.** Qwen-1M conflates
   "rotatable?" with "survives extreme rope?"; standard rope is apples-to-apples with the
   random-7.1× / Hadamard-+5% points.
2. **Rotate POST-RoPE K** (how the cache stores it) — and the probe **verifies the RoPE
   math**: post-RoPE rotation by *any* orthogonal R preserves attention (tested, diff
   1.8e-14); **pre-RoPE rotation by a *general* R BREAKS it** (tested, diff 14.2); only a
   RoPE-*commuting* R works pre-RoPE. So a general learned R must go post-RoPE = an
   **online per-token matmul, NOT foldable into weights** (corrects the claim that pre-RoPE
   "also works" / fuses for free).
3. **Recon is a PRE-FILTER, not the gate.** recon ≠ downstream (head-wise won recon, lost
   downstream). The GO/NO-GO is the **hard-tail** eval.

**Honest failure-detector:** the probe distinguishes **channel-axis** anisotropy (rotatable
— a rotation spreads it) from **row/spectral** anisotropy (failure-mode #1 — rotation only
*relocates* it). CPU selftest proves both (channel → `rotatable`, row → `not_rotatable`).

**Sequencing (do NOT build kernels first):**
```bash
# 1. RECON SCREEN (pod, venv-vllm) — is K rotatable at all? cheap, no kernels.
PYTHONPATH=KVPolicy python Bench/scripts/kv_qat_learned_rotation.py \
    --model Qwen/Qwen2.5-7B-Instruct --layers 0,13,27 --tokens 4000
#   verdict 'not_rotatable' on K-heavy layers -> ABANDON (ship the hybrid scheduler).
#   verdict 'rotatable' (gap >70%)            -> proceed to the gate:
# 2. HARD-TAIL GATE (built: kv_qat_rotation_gate.py) — 3-arm FREE-GENERATION agreement:
#    bf16 (1.0 ref) / per-channel+protect (the BAR, ~0.74) / learned-R post-RoPE +
#    per-tensor K. Learns R per (layer,head), rotates Q by the same R (GQA-mapped).
PYTHONPATH=KVPolicy python Bench/scripts/kv_qat_rotation_gate.py \
    --model Qwen/Qwen2.5-7B-Instruct --n-prompts 16 --gen 48
#    PASS iff learned >= per-channel+protect (NOT >= bf16; even protect doesn't reach
#    bf16 on this hard metric). FAIL -> ship the hybrid scheduler.
# 3. Only if the gate PASSES: the RoPE-fused online-rotation kernel (weeks) — the
#    throughput question, which recon/quality do not answer. NB: rotation is
#    post-RoPE (online matmul), NOT foldable into Wq/Wk; the recurring decode cost
#    is one Q@R per step (K is rotated once at write) -> plausibly small, measure first.
```

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
| Learned-rotation probe (lever 5) | `Bench/scripts/kv_qat_learned_rotation.py` + `Bench/tests/test_kv_qat_learned_rotation.py` |
| Memory verdict (unchanged) | `MEMORY_STORY.md` §6 |
