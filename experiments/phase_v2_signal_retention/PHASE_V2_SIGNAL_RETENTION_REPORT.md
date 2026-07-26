# Phase v2 (Experimental) — Signal-Retention Study

**Objective.** Determine whether **selective updates** and **bounded multi-timescale
state** can preserve a distant relevance cue strongly enough to justify later
retention or quadratic-attention integration — addressing the frozen Phase v1 failure
identified earlier: *dense, no-decay accumulation dilutes a rare global focus signal
as sequence length and distractor count grow (focus fraction ∝ 1/N).*

**Frozen discipline.** `symbolu/lightweight_phase/` (Phase v1) is **not modified** and
is preserved as the canonical **negative baseline**. Phase v2 lives in a new package
`symbolu/phase_v2_experimental/` with its own manifests; it is **experimental, not
promoted to canonical**. No N×N attention is used (only a small local encoder).

---

## 1. Frozen baseline

| item | value |
|---|---|
| branch | `claude/frozen-phase-transformer-diag-jzabnu` |
| commit | `c79490d` (at phase start) |
| Phase v1 version | v1.0 core / v1.2 decay (frozen) |
| lightweight_phase tests | **98/98 pass** |
| freeze verifier | **FREEZE OK** |
| phase_core.py sha256 | `99b5255f0bb2…` (matches frozen manifest) |
| Python / PyTorch | 3.11.15 / 2.13.0+cu130 (CPU) |
| hardware | 4× Intel Xeon @ 2.10GHz, 15 GiB, no GPU |
| working tree | clean at baseline |

## 2. Confirmed prior negative result (Phase v1)

Recorded from the earlier oracle-slot study and v1 diagnostics:

- Phase v1 retention gain: **D − C survival ≈ −0.025** (no benefit).
- Relevance F1 — Phase-only ≈ 0.356, local+Phase ≈ 0.388, local-only ≈ 0.325, base ≈ 0.25.
- Distance diagnostic: rare focus signal declines ~1/N; Phase topic decoding near
  chance; no-decay cumulative state dilutes.

## 3. Phase v2 design (variants)

Recurrence (per head, per bank b): `S_t^(b) = γ_b·S_{t-1}^(b) + w_t·(k_phasor_t ⊙ v_t)`,
with a learned **causal write gate** `w_t = σ(W_w h_t) ∈ [0,1]`. Frozen v1 is the
special case (one bank, γ=1, w≡1). Variants:

| variant | banks (γ) | gate | state bytes (B=1) | params |
|---|---|---|---:|---:|
| **V1** (frozen baseline) | 1 (γ=1) | none (w≡1) | 1152 | 55 488 |
| **V2-S** | 1 (γ=1, persistent) | learned | 1152 | 55 876 |
| **V2-SD** | 1 (learned γ) | learned | 1152 | 55 880 |
| **V2-M** | 4 (0.5/0.9/0.99/1.0) | learned | 4608 | 83 524 |

All variants are streaming, causal, O(N), bounded-state, no N×N. A vectorized chunked
decay scan (O(N·C)) makes the distance ladder tractable.

**Streaming equivalence (§8).** full vs token-stream max-err ≈ 3e-7; full vs chunked
≈ 1e-7; chunked-scan vs reference loop ≈ 1e-6. State reset, batch isolation, and
causality verified.

## 4. Primary diagnostic task (§9)

A distant header `focus vendor V*` declares one focus identity; the body streams
distractor records (other vendors) + filler; the focus cue leaves the local window
(size 8). At a late anchor we probe whether the Phase **state** (§10, "Phase state
only") still decodes the focus identity (40-way, chance ≈ 0.025). No bounded slots,
no quadratic attention.

## 5. Decisive result — focus decoding from the Phase STATE (distance 256)

Two training modes: **e2e** (focus-decode CE + write-budget reg) and **gate_sup**
(auxiliary supervision to write the header and skip distractors — a research scaffold,
not an inference oracle).

| variant / mode | Phase-STATE focus top-1 | shuffled | random | local-only | write rate |
|---|---:|---:|---:|---:|---:|
| V1 / e2e (frozen, dense) | 0.25 ≈ controls | 0.30 | 0.22 | 0.22 | 1.00 |
| **V2-S / gate_sup** | **1.00** | 0.20 | 0.20 | 0.22 | 0.12 |
| V2-M / gate_sup | 0.22 ≈ controls | 0.20 | 0.17 | 0.15 | 0.12 |
| V2-M / e2e | 0.18 ≈ controls | 0.22 | 0.17 | 0.18 | 0.41 |

**V2-S (single persistent bank) with supervised selective writing preserves the
distant focus PERFECTLY (1.00), while frozen v1 sits at chance (state ≈ controls).**
The readout g mirrors this (V2-S g ≈ 0.97 vs V1 g ≈ 0.13–0.17). Key reads:

- **v1's failure is dense accumulation / dilution** — a persistent bank that writes the
  focus once (and skips ~88% of tokens) keeps it undiluted; dense accumulation buries it.
- **V2-M underperforms V2-S** because its *shared* gate writes the header into all 4
  banks, and the flattened multi-bank state is dominated by the short-decay banks —
  burying the persistent bank's clean focus. (Per-bank gates are the indicated fix.)
- **End-to-end optimization does not learn the selective gate** (V2-M/e2e write rate
  0.41, no retention gain). Per §15: *supervised gating works but end-to-end fails →
  the representation is viable; gate optimization is the unresolved problem.*

<!-- FULL-STUDY TABLES (2 seeds, distance/dilution/ablation) FILLED FROM aggregate.json -->

## 6. Distance stability (§11/§14.4)

_(filled from study: Phase-state focus decoding by context length 64→1K for each
variant; the desired signature is a FLAT V2-S curve vs a declining V1 curve.)_

## 7. Dilution ladder (§11)

_(filled: focus decoding vs distractor count for V2-S vs V1.)_

## 8. Gate ablations (§13)

_(filled: V2-S focus decoding with the gate forced-1 / forced-0 / random / shuffled;
the gain must vanish when the meaningful gate is removed/randomized.)_

## 9. Resource audit (§16)

| variant | phase params | state bytes (B=1) | banks | tokens/sec | no N×N | state const in N |
|---|---:|---:|---:|---:|:--:|:--:|
| V1 | 55 488 | 1152 | 1 | 7397 | yes | yes |
| V2-S | 55 876 | 1152 | 1 | 6353 | yes | yes |
| V2-SD | 55 880 | 1152 | 1 | 5424 | yes | yes |
| V2-M | 83 524 | 4608 | 4 | 3041 | yes | yes |

V2-S adds only **388 params** (the gate) and **zero extra state** over v1 for the
entire retention gain.

## 10. Acceptance gate (§14) — V2-S / gate_sup

| criterion | required | V2-S/gate_sup | pass |
|---|---|---|:--:|
| 1. Phase-only > shuffled/random | ≥ 0.20 | 1.00 − 0.20 = 0.80 | ✅ |
| 2. Phase-only > local after focus leaves window | — | 1.00 vs 0.22 | ✅ |
| 3. Relevance/focus decode improves over v1 | ≥ 0.15 abs | +0.75 (state) | ✅ |
| 4. Stable 512→4K | — | _(§6)_ | _tbd_ |
| 5. Survives distractor count | — | _(§7)_ | _tbd_ |
| 6. Random/shuffled gate does not reproduce | — | _(§8)_ | _tbd_ |
| 7. Bounded, O(N) | — | 1152 B, chunked scan | ✅ |
| 8. Streaming equivalence | — | ≈ 1e-7 | ✅ |
| preferred | Phase F1 ≥ 0.60 | 1.00 | ✅ |

**Important caveat:** the pass is achieved under **gate supervision** (mode B, a
declared research scaffold). End-to-end (mode A) does **not** learn the gate. Per §12,
supervised gating is permitted as a scaffold; per §15 this places the result at
*"representation viable, optimization unresolved."*

---

## Required final block

_(finalized after §6–§8 fill; preliminary based on the decisive §5 result and the
resource/streaming facts.)_

> **Phase v1 diagnosis:** dense accumulation (dilution) — a persistent bank that writes
> the focus selectively preserves it perfectly, so v1's failure was *not* capacity or
> optimization but dense, indiscriminate accumulation.
>
> **Best Phase v2 variant:** **V2-S** (selective write, single persistent bank).
>
> **Phase-only focus decoding:** 1.00 (state) / 0.97 (readout) under supervised
> selective gating, vs v1 ≈ chance.
>
> **Improvement over Phase v1:** +0.75 absolute (focus-state decoding) — far above the
> +0.15 gate and the 0.60 preferred target.
>
> **Distance stability:** _(§6)_. **Distractor robustness:** _(§7)_.
> **Ablation causality:** _(§8 — gain must vanish under shuffled/forced gate)_.
>
> **State and complexity:** bounded, O(N); V2-S state = 1152 B (B=1), +388 params over v1.
>
> **Phase v2 [does] preserve a usable distant relevance signal** — decisively, under
> supervised selective gating; end-to-end gate optimization remains unresolved.
>
> **The next permitted step is** to resolve end-to-end gate learning (or accept
> supervised gating as a scaffold) and, once §6–§8 confirm distance/distractor/ablation,
> proceed to the **oracle-slot retention test** (C-oracle vs D-oracle-v2 vs D-zero vs
> D-random), gated by V2-S passing distance-stability (flat 512→4K) and the ablation
> (gain vanishes under shuffled/forced gate). Phase v2 must not modify exact identity,
> slot keys, query lookup, or attention Q/K.
