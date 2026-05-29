# Phase 6J — CORRECTED quality verdict (clean, post-collapse-fix)

> **Headline: do NOT close the int4_protected line. Reframe it.** The earlier
> `PROTECT_MASK_NOT_VALIDATED` → "close as negative result" recommendation was
> built on **collapse-corrupted** data (the 6K.9/6K.10 decode bugs). On clean
> post-fix data the story inverts:
>
> * **Needle is solved by *naive* int4 already** (≈ bf16) → the needle gate is
>   **saturated** and no longer discriminates the protect mask.
> * **Protected int4 delivers a real, large fidelity gain**: **+20.4 points**
>   of bf16 token-agreement over naive (0.533 → 0.737).
>
> So this is a **sidecar-memory-cost vs fidelity-gain tradeoff**, not a failed
> research line. See `PHASE_6K7_INT4_DISPATCH_FIX_FINDINGS.md` for the three
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

### Hard needle (6K.12) — de-saturated retrieval, mml=8192

The easy needle saturates (naive ≈ bf16), so 6K.12 stresses it (multi-needle,
look-alike distractors, conflicting facts, QA-over-context). Two metrics bracket
the FORMAT ambiguity (FORMAT = answer present but verbose / leaked the other
field — the eval logs raw `qa` outputs to adjudicate it):
`strict = HIT / total` (FORMAT counts against) and
`retrieval = HIT / (total − FORMAT)` (FORMAT excluded).

| cell | strict | retrieval | genuine misses |
|---|---|---|---|
| bf16 | 0.833 | 1.000 | 0 |
| naive int4 | 0.792 | 0.905 | 1 `NEAR_V` (V-bound) + 1 `MISS_K` (K-bound) |
| protected int4 | 0.833 | 1.000 | 0 |
| **prot − naive** | **+0.041** | **+0.095** | protect recovers both |

The bf16 row (strict 0.833 / retrieval 1.000, all 4 non-HITs are `FORMAT`)
confirms the FORMAT spread is **verbosity, not retrieval failure** — bf16
retrieves everything. **Under stress the gap reappears:** on retrieval, naive
drops below bf16 (0.905) and protected recovers it to bf16 level (1.000),
fixing both a V-bound and a K-bound miss. Sample is thin (24 items / 6 per
mode) → **directional**: a *small real* protect retrieval advantage when int4
is actually stressed, to confirm with more items and higher mml (16K/32K).
Strengthens "reframe, don't close": protect helps **both** general fidelity
(+20.4 pt) **and** stressed long-context retrieval (modestly).

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

The open decision: **is +20.4 pts of bf16 token-agreement worth the protect
sidecar memory** for the target workload — and **do harder needle tests reveal
a long-context retrieval advantage** that the saturated easy-needle hides?

## 5. Next-eval checklist

- [x] clean post-fix needle (above)
- [x] clean token-agreement (above)
- [x] failure-mode buckets (`phase6k11`: K_BOUND / NEAR_V / COLLAPSE)
- [x] **HARD needle** (`phase6k12_hard_needle.py`): de-saturated — retrieval
      naive 0.905 vs protected 1.000 (=bf16), gap **+0.095** (strict gap
      +0.041); thin sample (see §1). **TODO: confirm at 16K/32K, more items.**
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
