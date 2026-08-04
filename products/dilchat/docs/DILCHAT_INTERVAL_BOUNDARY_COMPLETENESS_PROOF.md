# DilChat — Interval Boundary-Completeness Proof (Workstream B)

**Claim to justify:** the interval evaluator (`astrology/interval.py`) never omits a
rashi / nakshatra / pada classification that the Moon actually occupies during the
UTC birth-time interval.

This document gives the mathematical argument (strategy **B**, conservative
angular-motion bound), states the preconditions and half-open semantics, and maps
each to enforced code + tests. Sampling density alone is **not** the proof — the
argument rests on a bound plus a post-condition that fails loudly if unmet.

## 1. Method

`evaluate_interval` samples the configured real provider on a 30-minute grid across
`[start, end]`, then **adaptively densifies**: while the forward angular gap between
two adjacent samples is `≥ W_min` (the smallest category width = one pada =
`360/108 ≈ 3.3333°`), it inserts the midpoint. It classifies each sample with the
exact half-open Decimal arithmetic (`derivation.py`) and returns, per field, the set
of distinct categories seen (`STABLE` if one; `AMBIGUOUS`/`INDETERMINATE` if more).

## 2. Preconditions

**P1 — Monotonic prograde motion.** The Moon's geocentric ecliptic longitude is
strictly increasing (the Moon is never retrograde in longitude; its mean motion is
≈13.2°/day and the true rate stays positive). Therefore, for adjacent samples
`a, b`, the forward angular distance `Δ = (lon(b) − lon(a)) mod 360` equals the true
arc length traversed between them.

**Enforcement:** if any forward gap exceeds `180°`, the path is treated as
non-monotonic/discontinuous and the evaluator raises `EphemerisUnavailableError`
(test `test_non_monotonic_path_rejected`). Real Moon motion over ≤ ~25 h intervals
(≤ ~15°) never triggers this; a broken provider fails loudly rather than
under-reporting.

**P2 — Provider availability.** Every sample (including densification midpoints)
must be computable; a provider failure raises and is propagated
(`test_provider_failure_propagates`).

## 3. Completeness lemma

> **Lemma.** If every adjacent forward gap satisfies `Δ < W_min`, then no category is
> skipped: every category interval `[kw, (k+1)w)` (for the field of width
> `w ≥ W_min`) that the path enters contains at least one sample.

**Proof.** Suppose a category `C = [kw, (k+1)w)` of width `w ≥ W_min` is entered by
the (continuous, monotonic by P1) path but contains no sample. Then two adjacent
samples `a < b` bracket `C` with `lon(a) < kw` and `lon(b) ≥ (k+1)w`. Hence the arc
length `Δ = lon(b) − lon(a) > (k+1)w − kw = w ≥ W_min`, contradicting `Δ < W_min`. ∎

Because rashi (`w = 30°`) and nakshatra (`w = 360/27`) widths both exceed
`W_min = 360/108`, the lemma covers all three fields simultaneously (a nakshatra
boundary is also a pada boundary, so simultaneous crossings are handled — test
`test_nakshatra_and_pada_cross_together`).

## 4. Post-condition (the part that makes it a proof, not a hope)

After densification the evaluator computes `max_gap = max Δ` and, if
`max_gap ≥ W_min` (densification hit its depth cap on a pathological provider),
**raises** rather than returning a possibly-incomplete result. Thus either the
lemma's hypothesis holds (and completeness follows) or the evaluation fails
explicitly. Density is therefore a *sufficient, verified* condition — not an assumed
one. (`test_two_boundaries_between_coarse_samples_are_caught` forces 15°/h motion so
a raw 30-min step spans >2 padas; densification still catches every crossed pada and
the seen-nakshatra set is contiguous.)

## 5. Wrap-around and interval semantics

- **360°→0° wrap:** handled by the `mod 360` forward-distance and per-sample
  normalization; at 0° a rashi, nakshatra and pada boundary coincide, so a 359°→1°
  sweep yields rashi `{11,0}`, nakshatra `{26,0}`, pada indeterminate
  (`test_wrap_360_to_0_crosses_rashi_nakshatra_pada`).
- **Multiple boundaries in one interval:** supported (contiguous seen-sets;
  `test_several_pada_crossings`).
- **Half-open `[start, end)`:** the UTC interval is treated as half-open. A boundary
  exactly at `start` belongs to the **higher** category (start is included), so a
  path beginning on a boundary and moving up is `STABLE` in that higher category
  (`test_boundary_exactly_at_interval_start_is_half_open`).
- **Boundary exactly at end:** closed sampling includes the `end` instant, a
  **conservative over-approximation**: it may add the just-entered category at an
  exact-end boundary (over-reporting ambiguity), but it never under-reports
  (`test_crossing_exactly_at_interval_end`).
- **Provider discontinuity / unavailable sample:** raises (P2).
- **Retrograde/anomalous motion:** rejected by P1 (the Moon has no true longitude
  retrograde; the guard catches a misbehaving provider).

## 6. What is proven vs. limited

| Property | Status |
|----------|--------|
| Category **set** completeness (no category skipped) | **Proven** (Lemma + §4 post-condition + P1 guard) |
| Determinism for identical inputs/version | Proven (`test_determinism_and_trace_has_transitions`) |
| Stable not marked ambiguous; ambiguous not collapsed | Proven (dedicated tests) |
| Exact crossing **timestamps** in the trace | **Not implemented** — the trace records category sets and the seen-order, bracketed to sample resolution, not bisection-refined crossing times. |
| Half-open end-instant handling | Conservative (closed sampling; may over-report at an exact-end boundary, never under-report). |

## 7. Verdict

**`INTERVAL_BOUNDARY_COMPLETENESS_PROVEN_WITH_LIMITATIONS`.**

Category-set completeness is proven under the enforced monotonic-prograde
precondition and the fail-closed density post-condition (no category can be
skipped, or the evaluation fails explicitly). The two limitations — exact
crossing-time refinement is not implemented, and the end instant is sampled closed
(conservative) — do not affect completeness of the reported classification sets and
are safe (never under-report). Refining crossing timestamps into the explanation
trace is the remaining work to reach the unqualified
`INTERVAL_BOUNDARY_COMPLETENESS_PROVEN` verdict.
