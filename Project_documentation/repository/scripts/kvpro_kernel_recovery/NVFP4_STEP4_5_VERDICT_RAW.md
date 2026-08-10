# Step 4/5 — RAW output + Step 6 VERDICT (NVFP4 protection transfer)

Concludes the 6-step qualification protocol. Harness qualified (Step 1), no integration bug (Step 2),
anomaly explained (Step 3), decisive K-isolated transfer test (Step 4), clean-model control (Step 5).

## Provenance
- harness commit: `72c6411a`, model paths as noted, wikitext-2 test, ctx=4096, tail-50% PPL
- logs: `/workspace/kvformat_step4_qwen25.log`, `/workspace/kvformat_step5_clean.log`

## Step 4 — decisive format-transfer, K ISOLATED (V held identical to int4_protected)

`nvfp4k_int4v_protected` swaps ONLY K's base quantizer (per-channel int4 -> per-block NVFP4); V is
int4 per-32-channel group, IDENTICAL to int4_protected. Same per-head mask, same budget. Qwen2.5-7B:

| protect | bf16 | int4_protected | nvfp4k_int4v_protected (K-only swap) | nvfp4_protected (K+V NVFP4) |
|--:|--:|--:|--:|--:|
| 2% | 5.1754 | **5.1787 (+0.06%) HOLDS** | 13465.03 (+260074%) | 13292.87 (+256747%) |
| 4% | 5.1754 | **5.1812 (+0.11%) HOLDS** | 132.40 (+2458%) | 135.08 (+2510%) |
| 6% | 5.1754 | 5.2378 (+1.21%) | 19.56 (+278%) | 19.41 (+275%) |
| 8% | 5.1754 | 5.2441 (+1.33%) | 22.22 (+329%) | 22.40 (+333%) |

**Reading:** `nvfp4k_int4v_protected` tracks `nvfp4_protected` within ~1% at every budget → holding V
identical does NOT rescue NVFP4. The failure is entirely in K's format. Swapping ONE variable (K:
per-channel int4 -> per-block NVFP4) reproduces the full catastrophe. NVFP4-K plateaus at ~+280-330%
(6-8%), never approaching the 1% gate; more budget won't fix it (per-block damage is distributed, not
concentrated in a few protectable channels). **The per-channel int4 K format is load-bearing; the
protection mechanism does NOT transfer to NVFP4 on outlier-heavy models.**

## Step 5 — clean-model control (Qwen3-8B, same family + QK-norm)

| format | PPL | vs bf16 | tag |
|---|--:|--:|---|
| bf16 | 10.5914 | — | baseline |
| fp8 | 10.6418 | +0.48% | HOLDS |
| int4_protected | 10.6770 | +0.81% | HOLDS |
| nvfp4 (plain) | 10.6953 | +0.98% | HOLDS |
| nvfp4_protected | 10.6509 | +0.56% | HOLDS |

**Reading:** on Qwen3 EVERYTHING holds — including PLAIN NVFP4 (no protection). Proves (1) the harness
is sound (does not universally break NVFP4), and (2) the Qwen2.5 collapse is model-specific: Qwen3's
QK-normalization removes the per-channel KV outliers, so NVFP4's per-block scale works. On clean
models NVFP4 needs neither protection nor per-channel int4 — Blackwell's native FP4 suffices.

## STEP 6 — VERDICT

**Category: TRANSFER_NOT_SUPPORTED** (on outlier-heavy models, at production protection budgets),
**with the crucial qualifier that transfer is UNNECESSARY on clean/QK-norm models.**

Evidence chain (all measured, not assumed):
1. Harness QUALIFIED — int4_protected reproduces production HOLDS @ 4% (+0.11%). [Step 1]
2. NOT an integration bug — 6/6 real-KV invariants pass on captured Qwen K (0%==plain, 100%==bf16,
   protected==source exactly), NaN/Inf-free. [Step 2]
3. Anomaly explained, not noise — NVFP4 per-16-channel block scale fails on Qwen2.5 boundary-layer
   (L0/L27) per-channel outliers; partial protection at 2% is non-monotonic at L27 (breaks error
   cancellation). Reconstruction coupling ruled out (coupling_delta<0 everywhere). [Step 3]
4. K is the sole driver — K-isolated swap (V held) reproduces the collapse; V confound negligible. [Step 4]
5. Model-specific — plain NVFP4 holds on Qwen3 (QK-norm); harness sound. [Step 5]

### Strategic implication (quality axis; scoped)

The KVPro quality advantage on outlier-heavy models is the **per-channel int4 K format**, not the
protection sidecar alone. Blackwell's native NVFP4 (per-block scale) cannot inherit that advantage by
adding the same protection — it fails by 4-5 orders of magnitude at the production budget and plateaus
far from the gate. **So Blackwell does NOT commoditize the protection IP by making NVFP4 fast** — on the
models where protection matters (outlier-heavy), NVFP4 can't hold quality at any reasonable budget.

BUT the segment where this matters is **shrinking**: QK-normalization (Qwen3 and most new models)
removes KV outliers upstream, and on those models plain NVFP4 already holds (+0.98%) — no protection,
no per-channel int4, no moat needed. This mirrors the fp8 finding exactly (Qwen2.5 hostile, Qwen3 clean).

### No winning quadrant for NVFP4-protected

| need \ model | outlier-heavy (Qwen2.5, older) | clean (Qwen3+, QK-norm) |
|---|---|---|
| speed | NVFP4-protected FAILS quality; int4=slow; only a custom int4 kernel or QK-norm helps | plain NVFP4 native-fast, holds — no protection needed |
| capacity | int4-protected holds (slow OK) | int4-protected or NVFP4 both fine |

NVFP4-protected is never simultaneously needed, fast, and quality-holding. The protection IP does not
find a home in the FP4 era: where it would add value (outlier models) NVFP4 can't hold; where NVFP4
holds (clean models) protection is unnecessary.

### Caveats (honest bounds)
- Quality axis only (PPL). Speed (NVFP4 native 1.0x vs int4 slow) is measured elsewhere and unchanged.
- One NVFP4 protection scheme tested (zero-then-quantize, K-only, 2-8% budget). Exotic schemes
  (per-block protection, g_scale exclusion, >8% budget) not exhaustively swept — but the 6->8% plateau
  (+278%->+329%) shows diminishing returns, so a reasonable-budget rescue is unlikely.
- Emulation matches Blackwell's numerical RESULT, not its speed; A100 stands in for FP4 tensor cores.
