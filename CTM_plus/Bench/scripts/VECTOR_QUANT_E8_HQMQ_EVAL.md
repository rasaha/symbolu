# Evaluation — high-dimensional vector quantization for the KV cache (E8 lattice / QuIP#-class; Hurwitz-quaternion HQMQ)

> **What this is.** A due-diligence read of an external design brief proposing two
> high-dimensional **vector-quantization (VQ)** families for the KV cache:
> **E8 lattice VQ** (QuIP#/VPTQ lineage; the brief cites a KV port called "NexusQuant")
> and **Hurwitz-Quaternion Multiplicative Quantization (HQMQ)**. The brief is
> mathematically literate and its *strategic* conclusion ("park it unless you fund a
> kernel team; ship read-skip") is correct. This document records **why** that's the
> right call using our own measured evidence — and corrects two things the brief got
> wrong about our results.

## TL;DR verdict — PARK as a research bet; do NOT pivot

1. **The math is real and correctly described.** E8 is the proven-optimal sphere packing
   in 8-D (Viazovska, 2016 — Fields Medal 2022). The Conway–Sloane closest-point routine
   (int-or-half decomposition + even-parity fix), the bounded **E8P** 2¹⁶ codebook, and
   **RVQ** stacking (`D ∝ 2^{-2bm}`) are all faithfully stated. The 24-cell / Hurwitz-unit
   substrate for 4-D quaternion VQ is also real geometry (the 24 unit Hurwitz quaternions
   = binary tetrahedral group 2T = D4's minimal vectors). For **weights**, this lineage
   (QuIP#, VPTQ, AQLM) is genuinely SOTA at 2-bit. Full credit.
2. **But it leans on assumptions we have already MEASURED to fail on our K** — and on a
   premise (lower MSE ⇒ better quality) we measured to be a **trap**. See §3. In short:
   its incoherence-rotation step regresses our per-channel K (+5%, tested); its
   "no per-channel scale" promise costs **7.1×** K error on Qwen2.5 (tested); and its
   entire "why the math wins" is a reconstruction-MSE argument that our head-wise →
   downstream resolver showed does **not** predict hard-tail quality.
3. **Provenance is shaky.** QuIP#/VPTQ are verifiable (pre-cutoff). **"NexusQuant"
   (claimed Apr 2026) and "HQMQ" (claimed May 2026) are after my knowledge cutoff — I
   cannot confirm they exist**, and the HQMQ description has internal contradictions (§2).
   Treat the headline perplexity numbers as **unverified**.
4. **Systems cost is exactly as the brief concedes** — a multi-week Triton/CUDA lattice-
   lookup (E8) or online Clifford/quaternion-multiply (HQMQ) kernel that adds *compute* to
   a **bandwidth-bound** decode op and abandons the Cartesian D=128 layout the entire
   int4_protected + read-skip stack is built on.
5. **The shipping asset is unchanged and the brief under-sells it:** read-skip's measured
   **+25 % → +72 %** long-context throughput win (the brief quotes "+14.4 %" — that was the
   short sanity run, not the headline; see §6).

**Decision: document and park.** If a dedicated CUDA-kernel team ever exists, the *one*
place this could earn its keep is the **extreme-rope / hard-anisotropy** regime
(Qwen2.5-1M), the only regime where scalar int4_protected itself broke (measured this
session — §5). Everywhere we currently ship, we already hold quality **and** already win
throughput, so VQ buys cost, not headroom.

## 1. What's real and correctly stated (credit where due)

| Claim in the brief | Assessment |
|---|---|
| E8 = densest 8-D lattice; Λ₈ = (all-int ∪ all-half-int) with even coordinate sum | **Correct.** Standard Conway–Sloane definition. |
| Conway–Sloane closest-point in O(1) via round-to-int / round-to-half + parity fix | **Correct.** This is the canonical E8 decoder; no database search. |
| E8P bounded shell, 2¹⁶ codebook for 2-bit×8-D; RVQ to reach 4-bit; `D ∝ 2^{-2bm}` | **Correct** and exactly how QuIP# does it. |
| 24-cell / Hurwitz units (2T) as a 4-D direction codebook; left-mult is an S³ isometry | **Correct geometry.** D4 is the optimal 4-D lattice quantizer; its 24 minimal vectors form the 24-cell. |
| Proven for **weights** (QuIP#, VPTQ pack 70B/405B to 1–2 bit at stable ppl) | **True.** Lattice/vector PTQ is real, reproduced, and competitive for weights. |

**Calibrate the headline MSE claim.** The textbook **granular** gain of E8 over a scalar
(Z) grid is the dimensionless second-moment ratio `G(Z)/G(E8) = 0.08333 / 0.07168 ≈ 1.16`,
i.e. **≈16 % lower MSE (≈0.65 dB) at equal rate** — not 30 %. The brief's "up to 30 %" is
the optimistic end (folds in boundary/shaping gain, or compares against a naïver scalar
baseline than our **per-channel** int4). The gain is real; ~16 % is the honest center, and
it is a *granular* gain on the **already-easy** part of the distribution (see §3).

## 2. Provenance — what I can and cannot verify

- **Verifiable (pre-cutoff):** QuIP# (Cornell, 2024), VPTQ (Microsoft, 2024). Real, SOTA
  for weights.
- **Unverifiable (post-cutoff):** **"NexusQuant" (Apr 2026)** and **"HQMQ" (May 2026)** are
  after my Jan-2026 knowledge cutoff. I cannot confirm the papers exist or that their
  benchmark numbers are real. They are stated in the brief as settled fact
  ("definitively proved", "published two weeks ago"); they should be held as **claims**
  until a paper or repo is in hand.
- **Internal tensions in the HQMQ description** (independent of provenance):
  1. **"No calibration dataset"** vs. **"median-multiplier outlier extraction step."** An
     outlier-extraction step *is* data statistics (per-channel medians). The method is not
     calibration-free; it's gradient-free, which is a weaker claim.
  2. **24 direction points is coarse.** Quantizing a 4-D unit direction to the nearest of
     24 vertices leaves ~30° covering error; the claimed 0.02–0.10 ppl recovery rests
     entirely on the **residual/secondary** codebook, not the 24-cell. "A purely random
     secondary codebook automatically creates a flawless packing" overstates a finite
     random-coding argument (quasi-uniform *asymptotically*, with variance at finite size).
  3. **The rescued baseline is weaker than ours.** "Naïve int4 → 10,000+ ppl on
     Qwen2.5-7B" describes **per-tensor** (or 2-bit) int4. Our **per-channel** int4 on
     Qwen2.5-7B is nowhere near catastrophic — needle 1.0/1.0, MMLU at parity (Phase 6N).
     HQMQ "recovering FP16" is measured against a failure mode **we don't run**, so its
     marginal value over *our* baseline is far smaller than the headline implies.

## 3. The load-bearing assumptions we have already MEASURED to fail (the core of the eval)

Both families rely on the same three premises. We tested all three on our exact K and they
are negative or trap-shaped. (Sources are committed in this repo.)

| Premise both E8/HQMQ rely on | Brief's framing | **Our measured result** | Source |
|---|---|---|---|
| **Data-oblivious rotation** spreads outliers so uniform lattice cells aren't overwhelmed | "Hadamard rotation spreads outlier spikes uniformly" | **+5 % WORSE** K error (0.0238 → 0.0251). `round_trip_kv` is already **per-channel**, which *is* the outlier handling; rotation smears that structure. | `kv_qat_rotation_test.py`; `KV_QAT_PILOT_RESULT.md` §"rotation lever" |
| **No per-channel scale needed** — "high-dim structural stability without data-dependent per-coordinate scales" | the lattice + global token scale α replaces per-channel scales | **7.1× WORSE** K error when per-block/-channel scales are dropped. Qwen2.5 K is strongly **anisotropic**; after rotation the coordinates do **not** become uniform. | `kv_qat_scale_probe.py`; `KV_QAT_PILOT_RESULT.md` §"hard-regime" |
| **Lower reconstruction MSE ⇒ better model** | "30 % less MSE → preserves the hard tail" | **FALSIFIED.** Head-wise mixed precision **won** K recon error but **lost** downstream (ppl + gen-agreement); channel-protect won downstream. Recon-MSE does not predict hard-tail quality. | `kv_qat_headwise_probe.py` + `kv_qat_downstream_resolver.py`; `KV_QAT_PILOT_RESULT.md` §"downstream resolver" |

**The catch-22 this creates for E8/HQMQ on our K.** The lattice needs the rotation to tame
channel outliers so its (uniform) cells aren't overwhelmed — but on our **per-channel** K
the rotation *regresses* (+5 %, row 1). Skip the rotation and the anisotropic channels
overwhelm the lattice exactly as the scale-drop probe showed (7.1×, row 2). And even if you
thread that needle and win the ~16 % granular MSE, row 3 says that MSE win need not move the
**hard tail**, which is the only thing `protect` is for. Meanwhile `protect` already
neutralizes the outlier channels directly and cheaply (top-4 % K at bf16, ~1 GB sidecar) —
no rotation, no lattice, no online decode kernel.

## 4. Systems reality (agreeing with the brief, sharpened)

- **It adds compute to a bandwidth-bound op.** Decode-time KV reconstruction is
  memory-bandwidth-bound (low arithmetic intensity). E8 needs an on-the-fly Triton lookup
  to decode bit-packed indices into SRAM before the Tensor Cores; HQMQ needs online 4-D
  Clifford/quaternion multiplies. Both *spend* compute to *save* bytes — the wrong side of
  the roofline for decode unless the byte-saving relieves the actual bottleneck.
- **read-skip already attacks the real bottleneck** — it cuts the *number of KV positions
  read per step* (~95 % skip) with **no per-element decode math**. That is why it produces
  a measured throughput win (§6) where a denser codec would add latency.
- **It abandons the Cartesian D=128 layout** the whole int4_protected route-A kernel +
  vendored flash-attn fork is built around. This is not a config flag; it is a new codec,
  a new kernel, and a re-validation of the entire correctness suite — a multi-week build at
  minimum, as the brief itself states.

## 5. The honest steelman — the one regime where it *could* matter

Be fair: these methods target **anisotropy and hard-tail outliers**, and we found exactly
**one** regime this session where scalar int4_protected itself breaks on that axis —
**extreme-rope long context**. `Qwen2.5-7B-Instruct-1M` (rope_theta cranked for a 1M
window) holds int4 quality at 8K (needle 1.0) but **`off` itself collapses to 0.667/0.0 by
32K** (`native_ctx32000.json`, this session). Standard-rope models (Llama-3.1, Mistral-v0.3)
hold 1.0/1.0 to 30–60K, so they have **no quality headroom for VQ to recover** — VQ there is
pure added cost.

So *if* this is ever pursued: scope it to the **extreme-rope / hard-anisotropy** regime,
and **compose, don't replace** — keep `protect` on the outlier channels (no rotation needed
there) and apply lattice/quaternion VQ only to the well-behaved residual. Expected value is
still low (rows 1–3 of §3 + the kernel cost), but that is the only intellectually honest
place to point the bet.

## 6. Corrections to the brief's claims about *our* results

- **read-skip is not "+14.4 % at 32K."** That figure is the **sanity** run
  (`llama_sanity32k.json`, gen=64, repeats=2 — warmup-heavy). The **measured headline** is
  **+25.0 % @32K → +46.4 % @44K → +58.8 % @52K → +72.2 % @60K** (`llama_ctx*.json`,
  gen=128), needle **1.0/1.0** throughout, and **replicated on Mistral-7B-v0.3 at +25.6 %
  @30K**. The brief under-quotes our own win by roughly half.
- **"Zero quality degradation" needs its caveat.** True for `off` on standard-rope models,
  but the read-skip **retention** policy's quality is **model-dependent**: Llama held
  1.0/1.0, **Mistral dropped depth-0.5 to 0.667** at the same keep-set. The throughput win
  generalizes; the skip *quality* must be validated per model. (See `PHASE10_FINAL_VERDICT.md`
  §"GENERALIZATION".)

## 7. Decision

**Park as a research bet, contingent on a dedicated kernel team, scoped to the extreme-rope
regime; do not pivot.** Ship read-skip + int4_protected. This is the brief's own bottom
line — reached here through our measured evidence (per-channel rotation regression, the 7.1×
scale-drop, the recon-vs-downstream trap) rather than on faith in two unverifiable 2026
papers.

### Pointers
- Tested levers behind §3: `KV_QAT_PILOT_RESULT.md` (rotation +5 %, scale-drop 7.1×,
  head-wise→downstream resolver).
- read-skip measured curve + cross-model generality: `PHASE10_FINAL_VERDICT.md`;
  raw JSONs in `Bench/bench_out/PHASE10_AB/` (`llama_ctx*`, `mistral_ctx30k`,
  `native_ctx32000`).
- `protect` design rationale (why top-4 % bf16 K beats redistributing the error):
  `KVPolicy/INT4_PROTECTED_README.md`.
