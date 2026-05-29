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
> **Decision language: keep / reframe — protected int4 is NOT a failed line.**
> It provides a large general-fidelity gain and a modest hard-retrieval gain, at
> a sidecar-memory cost. The remaining decision is whether the fidelity-per-GB
> (plus any perplexity / downstream improvement) justifies the protected
> sidecars. See `PHASE_6K7_INT4_DISPATCH_FIX_FINDINGS.md` for the three
> correctness fixes that unblocked this measurement.

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
