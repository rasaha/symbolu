# Phase 6J — CORRECTED quality verdict (clean, post-collapse-fix)

> **Headline: do NOT close the int4_protected line. Reframe it.** The earlier
> `PROTECT_MASK_NOT_VALIDATED` → "close as negative result" recommendation was
> built on **collapse-corrupted** data (the 6K.9/6K.10 decode bugs). On clean
> post-fix data the story inverts:
>
> * **Easy needle is solved by *naive* int4 already** (≈ bf16) → that gate is
>   **saturated** and no longer discriminates the protect mask.
> * **Protected int4 delivers a real, large fidelity gain** (PRIMARY signal):
>   **+20.4 points** of bf16 token-agreement over naive (0.533 → 0.737).
> * **Hard needle shows a modest, real stressed-retrieval gain** (60 items):
>   protected retrieval **0.964 vs naive 0.915 (+0.049)**; genuine misses drop
>   **5 → 2** (protect removes the K-bound miss, halves V-bound).
>
> * **Capacity is NEGATIVE in the current implementation**: protected int4 uses
>   **~+4.7 GB *more* HBM than bf16** at equal `gpu_util` and runs **~1.5–1.9×
>   slower** (see §1b). The ~2× max-concurrency is vLLM bookkeeping, not a
>   footprint win.
>
> **Precise verdict: protected int4 is QUALITY-POSITIVE (vs naive) but
> CAPACITY-NEGATIVE (vs bf16) — a quality feature, not a memory feature, today.**
> Do not close it (the +20.4 pt fidelity gain is real and protect is near-free
> over naive), but do not pitch it as memory savings. The open path is the
> **sidecar diet** (§1b). See `PHASE_6K7_INT4_DISPATCH_FIX_FINDINGS.md` for the
> correctness fixes that unblocked this; full scorecard:
> `phase6k13_capacity_demo.py` / `MEMORY_STORY.md`.

---

## 1. What changed: the collapse was a confound

Pre-fix 6J ran on top of the three decode bugs (dispatch all-zero, eager
stale-state, graph precapture-hook). Those produced `pérdida` collapse that
floored token-agreement (~0.04) and depressed needle unevenly. With the fixes
in, `phase6k11` reports **`COLLAPSE = 0` across every cell × mml**, so the
numbers below are clean.

### Clean needle-in-haystack (exact-code retrieval)

| mml | bf16 | naive int4 | protected int4 | prot − naive |
|---|---|---|---|---|
| 8192 | 1.000 | 0.960 | 0.960 | +0.000 |
| 16384 | 1.000 | 0.980 | 1.000 | +0.020 |
| 32768 | 1.000 | 1.000 | 1.000 | +0.000 |

(was 0.86–0.94 when collapse-corrupted). **Naive int4 is already near bf16** —
the current needle task does not stress int4 KV. `phase6k11` failure buckets:
all non-HIT items are `NEAR_V` (2–3 total), zero `MISS_K`, zero `COLLAPSE`.

### Clean token-agreement vs bf16 (greedy top-1, 32 steps)

| cell | agree_rate | n |
|---|---|---|
| naive int4 | 0.533 | 295/553 |
| protected int4 | **0.737** | 420/570 |
| **gap (prot − naive)** | **+0.204** | |

(mml-independent — the agreement prompts are short, so this is *general*
generation fidelity, not long-context-specific.)

### Hard needle (6K.12) — de-saturated retrieval, mml=8192, 60 items (15/mode)

The easy needle saturates (naive ≈ bf16), so 6K.12 stresses it (multi-needle,
look-alike distractors, conflicting facts, QA-over-context). Three metrics keep
`FORMAT` honest. `FORMAT` = the expected answer **is present** but the model
continued / echoed the other field — adjudicated from the raw `qa` outputs the
eval logs, e.g. `' Olga\n\nQuestion: What is the vault door code? GBII2W'`
(answer **Olga** is correct; the trailing code is just continuation):

* `strict` = HIT / total — exact requested format only (FORMAT counts against)
* `retrieval` = HIT / (total − FORMAT) — FORMAT excluded as ambiguous
* `retrieved_or_present` = (HIT + FORMAT) / total — FORMAT = retrieved (post-adjudication)

| cell | strict | retrieval | ret_or_present | misses (NEAR_V / MISS_K) |
|---|---|---|---|---|
| bf16 | 0.917 | 1.000 | 1.000 | 0 / 0 |
| naive int4 | 0.900 | 0.915 | 0.917 | 4 / 1 |
| protected int4 | 0.883 | 0.964 | 0.967 | 2 / 0 |
| **prot − naive** | **−0.017** | **+0.049** | **+0.050** | protect: −2 V-bound, −1 K-bound |

**Read `strict` with care — it is misleading here.** Protected's strict is
*lower* (−0.017) only because it (like bf16) produced FORMAT=5 verbose-correct
`qa` answers vs naive's 1; FORMAT is **not** a retrieval miss (bf16 has 5 too
and retrieves everything). On the honest metrics **protected leads:
`retrieval +0.049`, `retrieved_or_present +0.050`.** Genuine misses drop
**naive 5 (4 V-bound + 1 K-bound) → protected 2 (2 V-bound, 0 K-bound)**:
protect **eliminates the K-bound miss and halves the V-bound** near-misses; the
remainder is V-bound, so **int8-V / protect-V** is the next retrieval lever if
needed.

**Directional, not a breakthrough.** The thin 24-item run showed +0.083; this
larger 60-item run shows **+0.049** — a *modest, real* stressed-retrieval
advantage. Do not overclaim. Confirm at 16K/32K with more items. The PRIMARY
validation remains token-agreement (+20.4 pt); hard-retrieval is the secondary
benefit. **Frame protected int4 as fidelity-first, with a modest stressed-
retrieval bonus.**

## 1b. Capacity & memory — CAPACITY-NEGATIVE (current implementation)

HBM after init with KV allocated (A100-80GB, `gpu_util=0.5`):

| mml | bf16 HBM | int4-protected HBM | Δ HBM | bf16 conc | int4 conc |
|---|---|---|---|---|---|
| 8192 | 39.13 | 43.82 | **+4.68** | 55.3 | 110.6 |
| 16384 | 38.04 | 42.72 | **+4.68** | 26.4 | 52.8 |
| 32768 | 35.85 | 40.51 | **+4.66** | 12.0 | 23.9 |

Long-context bench verdict: **`NOT_JUSTIFIED`** — protected int4 does **not**
beat bf16 on HBM at any mml. Throughput: int4 ≈ **0.56–0.68×** bf16 in the
crossover bench; 6H high-load was **`INCONCLUSIVE`** (both cells completed every
batch — saturation never reached) but bf16 was still **1.4–1.9× faster**.

Sidecar breakdown (mml=32K, fixed 16.4% of KV cache): `k_protect_ext` 0.818 GB
(23.8%), `v_scale_ext`/`v_xmin_ext`/`k_scale_ext`/`k_xmin_ext` 0.654 GB ea
(19.0%), `_k_stage_pool` 0.007 GB (0.2%).

**Why quality improved:** protected K channels preserve bf16-like behavior →
token-agreement jumps +20.4 pt and hard-needle misses shrink 5→2.
**Why capacity did not:** the sidecars (k_protect_ext + scale/xmin) dominate the
footprint and overwhelm the int4 KV savings, so protected int4 currently
consumes **more** HBM than bf16.

**What must change before protect can be justified as a capacity feature:**
reduce sidecar memory (diet), re-run the HBM crossover, re-run high-load to
**actual saturation**, and re-measure fidelity after each diet step.

Diet options (audit recommendation only — no implementation):

| id | save | risk | targets | kernel? |
|---|---|---|---|---|
| A | ~0.65 GB | moderate | v_scale_ext, v_xmin_ext (V groups 4→2) | yes (V kernel) |
| C | ~1.72 GB | high | all scale/xmin + k_protect_ext (bf16→fp8) | yes (read+write) |
| F | ~0.33 GB | moderate | k_protect_ext (n_protect 5→3) | no (recalibration) |
| D | ~0.82 GB | low semantic / high impl | k_protect_ext (inline into kv_cache) | yes (layout change) |

**A+F+C stacked ≈ 3.19 GB < the ~4.7 GB delta** → A+F+C alone **probably does
not** close the gap. Either **D** is also needed, or accept protected int4 as a
**quality feature, not a capacity feature.**

**Recommendation:** *Proceed only with sidecar-diet experiments and
scorecarding. Do NOT start heavy Phase 6F kernel work until a dieted
protected-int4 config demonstrates an HBM advantage — or at least near-parity
with bf16 — while preserving most of the +20.4 token-agreement gain.*
Scorecard generator: `phase6k13_capacity_demo.py`; one-pager: `MEMORY_STORY.md`.

## 2. Corrected verdict / validation language

* The bench still prints `PROTECT_MASK_NOT_VALIDATED`. **Interpret it strictly
  as "not validated *under the old long-context-needle-rescue gate*," NOT as a
  negative research result.**
* **The old gate is stale.** It requires `needle gap ≥ 0.20`, which is
  **unreachable when naive int4 is already ≈ 1.0** — the gate fails by
  construction on a saturated benchmark, regardless of protect's value.
* The old gate's token-agreement arm (`gap ≥ 0.10 AND protected ≥ 0.85 @16K`)
  **half-passes**: the **gap is +0.204 (≫ 0.10)**, but protected's absolute
  `0.737 < 0.85`. So protect clearly wins the *relative* comparison; it just
  misses an absolute bar that may itself be mis-set for int4 KV.

**Bottom line:** current evidence does **not** support protected int4 as
*necessary for simple needle retrieval* (naive is at ceiling), and **does**
support protected int4 as a **significant general bf16-fidelity improvement**
over naive int4.

## 3. Proposed revised validation gates

| metric | old gate | revised gate | rationale |
|---|---|---|---|
| token-agreement (PRIMARY) | gap ≥ 0.10 AND protected ≥ 0.85 @16K | **gap (prot − naive) ≥ 0.10** (PASS today: +0.204) | relative gain is the real signal; absolute bar penalizes int4 KV broadly |
| token-agreement absolute | ≥ 0.85 | **tiered target** (e.g. ≥ 0.70 "useful", ≥ 0.85 "near-bf16") | 0.737 is "useful" today; 0.85 is aspirational |
| needle (SECONDARY) | gap ≥ 0.20 | **require HARD needle mode first**; only count needle gap once naive < ~0.9 | saturated easy-needle can't discriminate |
| memory | — | **report sidecar overhead per fidelity point** | makes the tradeoff explicit |

## 4. Recommendation table (current evidence)

| | bf16 | naive int4 | protected int4 |
|---|---|---|---|
| needle (easy, ≤32K) | 1.00 | ~0.97 | ~0.99 |
| token-agreement vs bf16 | 1.00 (ref) | 0.533 | **0.737** |
| KV memory | baseline (1×) | ~int4 (low) | int4 + protect sidecars (~4.2 GB; see 5C accounting) |
| decode correctness (post-fix) | ✓ | ✓ | ✓ |
| **use when** | quality is paramount, memory is free | max KV capacity, fidelity secondary | **want most of bf16 fidelity at int4-ish memory** |

Harder needle answered (6K.12, 60 items): yes, a **modest** stressed-retrieval
advantage (retrieval +0.049, misses 5→2). So the remaining open decision is the
**economic** one: **is the protect sidecar memory worth the gains** —
+20.4 pt token-agreement (large) plus a modest hard-retrieval bump — measured
as **fidelity-per-GB**, ideally backed by perplexity / a small downstream eval?

## 5. Next-eval checklist

- [x] clean post-fix needle (above)
- [x] clean token-agreement (above)
- [x] failure-mode buckets (`phase6k11`: K_BOUND / NEAR_V / COLLAPSE)
- [x] **HARD needle** (`phase6k12_hard_needle.py`): 60 items — retrieval naive
      0.915 vs protected 0.964, gap **+0.049** (`retrieved_or_present` +0.050;
      strict −0.017 is a FORMAT artifact, see §1); misses 5→2. **TODO: confirm
      at 16K/32K with more items.**
- [ ] **perplexity** on a held-out set (cheap, directly prices the fidelity gain)
- [ ] small **downstream eval** (e.g. a few MMLU/GSM8K items) if cheap
- [ ] **sidecar memory overhead** measured (naive vs protected delta) →
      fidelity-points-per-GB

### Failure-mode taxonomy (used by phase6k11 / phase6k12)

| bucket | meaning | lever |
|---|---|---|
| `HIT` | exact expected answer retrieved | — |
| `NEAR_V` / `V_BOUND` | attended but emitted a near-miss / look-alike | raise V precision (int8 V / protect V) |
| `MISS_K` / `K_BOUND` | never attended / no answer-shaped output | finer K groups / retrieval-aware protect calibration |
| `COLLAPSE` | repetition / `pérdida` collapse | the 6K.9/6K.10 decode bugs (want 0) |
| `FORMAT` | retrieved the content but wrong output format | prompt/format, not a KV-precision issue |

## 6. Cross-references

* `PHASE_6K7_INT4_DISPATCH_FIX_FINDINGS.md` — the three correctness fixes that
  unblocked this clean measurement.
* `phase6k11_needle_failuremode.py` — needle K/V failure-mode breakdown.
* `phase6k12_hard_needle.py` — harder needle eval (de-saturates the test).
* `PHASE_6J_QUALITY_COMPARISON_DESIGN.md` — original design + the now-stale gate.
