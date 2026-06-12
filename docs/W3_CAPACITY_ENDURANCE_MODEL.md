# W3 Capacity + Endurance Model — Protection-Structured NAND Tiering

**Status:** conservative hardening of the earlier optimistic "2.22× tokens/GB" figure.
**Scope:** W3 only. Per the keystone check, read-skip is *approximate* heavy-hitter
retention (not exact-vs-full-attention), so it is **not** modeled as novelty here;
flash offload is integration context. The sole wedge under test is **placing the
int4_protected protect-mask structure across NAND reliability tiers.**
**Model code:** `ndol/sim/w3_capacity.py` (`python -m ndol.sim.w3_capacity`). Capacity
is deterministic, so this is an analytical model — the right tool; all inputs are stated.

> **Headline:** under a conservative ECC/RBER model the capacity claim drops from
> **2.22× → ~2.06× vs bf16**, and the W3-specific marginal over uniform int4_protected
> is only **~1.14×** (not 1.23×). W3 is **below** the all-QLC ceiling (2.16×) — so
> protect-mask tiering *trades* capacity for protected-bit reliability rather than
> maximizing capacity — and the gain **collapses** once QLC end-of-life RBER ≥ ~5e-2.
> Separately, **endurance binds before capacity** for hot KV: QLC sustains only
> ~0.83 DWPD for a 3-yr life.

---

## 1. Systems compared

| # | System | Placement |
|---|---|---|
| 1 | bf16 / TLC | baseline |
| 2 | int4 uniform / TLC | — |
| 3 | int4_protected / TLC | quantization only, uniform tier |
| 4 | **W3 tiered** | protected bits → TLC, 4-bit bulk → QLC |
| 5 | int4_protected / all-QLC | capacity ceiling, reliability-aggressive |

## 2. Equations

Binary entropy and the ECC code rate (Shannon BSC limit, LDPC efficiency η):

```
H2(p)            = -p·log2(p) - (1-p)·log2(1-p)
ECC_code_rate(r) = max(0, η · (1 - H2(r)))            # usable data fraction of raw bits
usable_bits_per_cell(tier) = density(tier) · ECC_code_rate(RBER(tier)) / OP_factor
```

Higher cell density ⇒ higher RBER ⇒ more parity ⇒ *less* of the extra raw capacity is
usable. This is the correction the naive "QLC = 4/3× TLC" misses.

Physical footprint and capacity (silicon-normalized so cell density is captured):

```
cells_per_token = Σ_region  logical_bits_region · align / usable_bits_per_cell(tier_region)
tokens_per_GB   = C_cells / cells_per_token,     C_cells = 8e9 / usable_bits_per_cell(TLC)
```

`logical_bits` includes bulk + protected + sidecar (group scale/zero) + protect-mask
metadata (a *static per-model* mask, so amortized ≈ 0/token). `OP_factor` and `align`
fold in over-provisioning/endurance-reserve and page/block padding.

Endurance (write-once-read-many KV):

```
sustainable_DWPD(tier)      = PE_budget(tier) / (365 · life_years · WAF)
lifetime_years(tier, dwpd)  = PE_budget(tier) / (365 · dwpd · WAF)
```

## 3. Parameters (conservative, end-of-life)

| | SLC | TLC | QLC |
|---|---|---|---|
| density (bits/cell) | 1 | 3 | 4 |
| RBER (EOL) | 1e-6 | 5e-3 | 2e-2 |
| P/E budget | 60 000 | 3 000 | 1 000 |

η=0.90, OP=1.10, align=1.03, WAF=1.1, life=3 yr. int4_protected net density vs bf16 =
**1.80×** (measured, VC brief / PHASE6N). QLC-eligible 4-bit-bulk fraction φ=0.75.
Geometry: Llama-3.1-8B (128 KiB/token bf16).

**After ECC+OP, usable data bits/cell:** SLC 0.818, TLC 2.343, QLC 2.810 →
**QLC/TLC = 1.199×** (vs the naive 1.333×). That ~10-point haircut is the whole story.

## 4. Effective KV-tokens per GB

| system | tokens/GB | ×bf16 | ×int4_protected |
|---|---|---|---|
| bf16 / TLC | 7.41k | 1.00 | 0.56 |
| int4 / TLC | 26.34k | 3.56 | 1.98 |
| int4_protected / TLC | 13.33k | 1.80 | 1.00 |
| **W3 (protected→TLC, bulk→QLC)** | **15.23k** | **2.06** | **1.14** |
| int4_protected / all-QLC | 15.99k | 2.16 | 1.20 |

Two conservative facts the optimistic model hid:
- **2.22× → 2.06×** vs bf16; **W3 marginal 1.23× → 1.14×** vs uniform int4_protected.
- **W3 (2.06×) < all-QLC (2.16×).** Tiering protected onto the safer tier *costs*
  ~5% capacity vs dumping everything on QLC. So W3 is **not** a capacity maximizer —
  its value is reliability of the precision-critical bits, *bought with* capacity.

## 5. Sensitivity

**vs QLC end-of-life RBER (the collapse axis):**

| RBER_QLC | QLC bits/cell | W3 ×bf16 | W3 ×int4p | verdict |
|---|---|---|---|---|
| 1e-2 | 3.008 | 2.16 | 1.20 | holds |
| 2e-2 | 2.810 | 2.06 | 1.14 | holds |
| 3e-2 | 2.637 | 1.96 | 1.09 | weak |
| 5e-2 | 2.335 | 1.80 | **1.00** | **collapsed** |
| 7e-2 | 2.075 | 1.64 | 0.91 | collapsed |
| 1e-1 | 1.738 | 1.43 | 0.79 | collapsed |

At QLC EOL RBER ≥ ~5e-2 — well within realistic aged-QLC range — QLC's post-ECC density
equals TLC's and **the entire W3 capacity benefit disappears** (and goes negative beyond).

**vs QLC-eligible bulk fraction φ:** even at φ=0.90 the W3 marginal is only 1.18×
(φ=0.50 → 1.09×; φ=0.75 → 1.14×). The bulk fraction does not rescue the claim.

**vs ECC efficiency η:** the QLC/TLC ratio (1.199×) is **independent of η** (it cancels),
confirming the result is driven by RBER physics, not the ECC-efficiency assumption.

## 6. Endurance — binds before capacity for hot KV

| tier | P/E | sustainable DWPD (3-yr) | lifetime @ 10 DWPD |
|---|---|---|---|
| SLC | 60 000 | 49.8 | 14.9 yr |
| TLC | 3 000 | 2.49 | 0.75 yr |
| QLC | 1 000 | **0.83** | **0.25 yr (≈3 months)** |

Write-once-read-many keeps WAF low (~1.1) and — crucially — KV-cache lifetime (seconds–
minutes) ≪ NAND retention (weeks), so **retention refresh never fires**: no refresh
overhead. *But* the sheer write **volume** of KV churn is the limiter: a per-request-
rewritten ("hot") KV tier easily exceeds 10 DWPD, at which **QLC lasts ~3 months**. QLC is
only endurance-viable for **warm/reused** KV (e.g., shared prefix caches read across many
requests, low rewrite rate), not per-request churn. Note the protect mask keys on
*precision*, not *churn* — so W3 does **not** solve endurance; that needs a separate
churn-based placement.

## 7. Verdict

**Not patent-worthy as a capacity claim.** Reasoning:
- The capacity benefit is modest (**~1.14× over uniform int4_protected**) and **bounded by
  RBER** — it vanishes at realistic aged-QLC error rates (≥5e-2).
- W3 is **dominated on capacity by all-QLC**; its only edge is reliability of protected
  bits, which a strong-enough ECC on QLC could also provide — narrowing the distinctness.
- The surrounding art is crowded: InstInfer/HiFC (KV on flash + pseudo-SLC tiering),
  MixKVQ/KVmix/ShadowKV (precision-aware KV structure). W1 (exact selection) already
  collapsed; W2 (flash offload) is anticipated.
- Endurance, not capacity, is the binding constraint for the hot-KV use case.

**Recommendation:**
1. **Defensive publication** of the specific mechanism — *use the int4_protected protect
   mask as the RBER-tolerance key for per-region NAND tier placement (error-tolerant 4-bit
   bulk → densest endurance-viable tier; precision-critical protected bits → safer tier)* —
   to establish prior art and keep the lane open without an expensive, narrow filing.
2. **Product-only differentiator** for the realized value: **~2.0× more long-context KV
   tokens per GB at bf16-parity quality**, marketed honestly as *warm/reused-KV* tiering
   (prefix caches), with the QLC endurance caveat stated. This is a genuine product win
   even though it is not novel enough to patent.
3. **Do not file** a standalone W3 capacity patent. If any filing is pursued, the only
   plausibly-narrow claim is "quantization-protection-mask-derived error-tolerance as the
   placement key across NAND reliability tiers" — and even that should be pressure-tested
   against InstInfer/HiFC/MixKVQ before spending on it.

*Caveats: RBER/P-E values are conservative public-datasheet order-of-magnitude, not
vendor silicon; the QLC-eligible bulk fraction φ and the int4_protected internal split are
parameterized (the 1.80× net density is the measured anchor). A real QLC RBER + ECC-budget
measurement on the target media is required before any of these numbers anchor a decision.*
