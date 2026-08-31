# Hierarchical / group-level BCVF — design proposal

**Status:** design only. No implementation. The brief's
*"research / scope expansion — longer horizon"* line item lands as
this doc; promotion to a deliverable is gated on the
ship-when-ready criteria in §13.

## §1 Why this exists

The current BCVF kernel runs all-pairs across `M` predictor
trajectories. At today's deployment scale (`M = 3` for the
characterization suite, `M = 4` for the production stack: IMU +
LiDAR + VO + GNSS) the all-pairs structure is ideal — every
predictor is genuinely independent, no two share a clock or a
coordinate frame, and the per-predictor attribution is sharp.

When `M` scales beyond 4–6 — a full sensor suite with multiple
LiDARs, multiple cameras, multiple radars, plus IMU / GNSS / wheel
odometry — two failure modes appear:

* **Quadratic cost growth.** Pair count is `M(M−1)/2`. At `M = 8`
  that's 28 pairs; at `M = 12` it's 66; at `M = 16` it's 120. The
  per-tick BCVF runtime grows quadratically.
* **Per-predictor attribution dilution.** Each predictor's
  attribution is the sum of pair costs that include it: `M − 1`
  pairs. A single bad LiDAR among five LiDARs and three cameras
  has its disagreement spread across 7 pairs, only some of which
  are with healthy peers — attribution magnitude shrinks below
  useful triage thresholds.
* **Correlated within-class failures invisible at the flat level.**
  Two LiDARs sharing a clock fail together when the clock drifts;
  the all-pairs BCVF between them sees zero disagreement. The
  failure shows up only against the camera / radar predictors —
  but at flat M it's diluted across many pairs.

A two-level BCVF — first **within** a sensor group (LiDAR cluster,
camera cluster, ...), then **across** group representatives —
addresses all three. Cost grows with the largest group's
within-group pair count plus the across-group pair count, not the
flat all-pairs count. Attribution localises to the group level
when a group disagrees with the rest, and to the predictor level
when a predictor disagrees within its group. Correlated within-
class failures become loud at the across-group level, where the
group's representative is offset coherently from the others.

## §2 Current design (flat all-pairs)

Recap (see `core.py` + `manifold.py` for the implementation):

* Inputs: `(M, H, 3)` SE(2) predictor tensor, `M ≥ 2`, `H ≥ 3`.
* For each pair `(i, j)` with `i < j`, compute the body-frame
  error trajectory `e_ij(t)` and its second-order time derivative.
* Per-pair cost: `gate(|e_ij''|) · pseudo_huber(|e_ij''|)`,
  bounded above by the Huber tail.
* Per-pair cost is added to **both** predictors in the pair so
  attribution is symmetric.
* Total = sum over all `M(M−1)/2` pairs.
* Trust shaping: per-predictor cost → softmin → trust weights.

The kernel's Lemma-1 invariance — second-order = exactly zero on
a constant offset and on a linear drift — carries by definition of
the second derivative. Any extension to a hierarchy must preserve
this property at both levels.

## §3 Proposed structure — two-level BCVF

Configuration introduces a `groups` field on `BCVFConfig`:

```python
groups: Optional[Tuple[Tuple[int, ...], ...]] = None
```

* `None` (default) means flat all-pairs — backwards-compatible with
  every existing caller.
* A tuple of tuples partitions `range(M)` into groups, e.g.
  `groups = ((0, 1), (2, 3, 4), (5, 6, 7))` for `M = 8` predictors
  split into three sensor classes.

Validation: groups must partition `range(M)` exactly — every
predictor index appears in exactly one group, no missing or
duplicated indices. Group sizes ≥ 1.

The kernel then computes:

1. **Within-group cost** for each group (§4).
2. **Group representative trajectories** (§5).
3. **Across-group cost** between representatives (§6).
4. **Total cost** = α · sum(within) + β · across (§7).
5. **Per-predictor attribution** combining both levels (§8).

## §4 Level 1 — within-group BCVF

For each group `g` with members `m₁, ..., m_k`:

* Run the existing flat all-pairs BCVF on the `k` member
  trajectories: `BCVF_within(g) = compute_bcvf_cost(traj[m₁..m_k])`.
* `k = 1` → no pairs → zero cost (degenerate, allowed).
* `k = 2` → one pair (the trivial within-group case).
* `k ≥ 3` → standard all-pairs.

The within-group computation reuses the existing kernel verbatim
— same gate threshold, same Huber `δ`, same `cost_order`. No
parameter forking. A within-group certification follow-on would
just re-run the existing 1320-cell grid with a hand-curated
group of `k` predictors per cell.

## §5 Group representative — three options

A representative trajectory `repr(g)` collapses group `g` to a
single `(H, 3)` trajectory consumed by the across-group BCVF.

| Option | Description | Lemma 1? | Pros | Cons |
|---|---|---|---|---|
| **A — Trust-weighted mean** | Compute within-group trust weights from `BCVF_within(g)`, then `repr(g) = sum_i w_i · traj[m_i]`. | Yes — linear combination of constants/linear-functions stays constant/linear; second derivative cancels. | Bad members get downweighted; representative cleanly tracks the consensus. | Requires the within-group BCVF + trust shaping to run before across-group. Two-pass. |
| **B — Arithmetic mean** | `repr(g) = mean(traj[m_i])` (uniform weights). | Yes — mean is linear; second derivative cancels. | Simplest, single pass. | A bad member drags the representative; across-group fires more weakly than option A would suggest, dilution by `1/k`. |
| **C — Winner-take-all** | `repr(g) = traj[m*]` where `m*` is the within-group lowest-cost predictor. | Conditionally — depends on `m*` having a well-defined trajectory. Selection itself is non-linear (argmin); strict invariance is property-of-the-input, not property-of-the-rule. | Sharp signal — representative is one of the actual member trajectories. | Loses information; can flicker (argmin chatter) — the same chatter problem V2 was built to mitigate, recurring at the group level. |

**Recommendation:** Option A as the default, with B as a fallback
for callers that want a single-pass implementation. Option C is
not recommended outside a small-scale sanity check — the chatter
risk is real and the V2 Schmitt-trigger machinery would need to
be replicated at the group level to suppress it.

Heading averaging uses circular statistics (`atan2(sum_i sin θ_i,
sum_i cos θ_i)`) — same convention the trust-weighted consensus
already uses for the per-tick output.

## §6 Level 2 — across-group BCVF

Given `N = len(groups)` representatives `repr(g₁), ..., repr(g_N)`:

* Run flat all-pairs BCVF on the representatives:
  `BCVF_across = compute_bcvf_cost([repr(g₁), ..., repr(g_N)])`.
* `N = 1` → zero across-group cost (single group means hierarchical
  reduces to flat within-group).
* `N = 2` → one across-group pair.

The across-group BCVF naturally has lower sensitivity than within-
group on a single-predictor outlier: under option A or B, a single
bad member's deviation appears in the representative scaled by
`1/k` (option B) or by the member's trust weight (option A,
typically `≪ 1/k` if the within-group BCVF flagged it). The
across-group level fires only when the group's *consensus* drifts
— either because the group is small and the deviation is large,
or because the within-group failure is correlated (every member
moves together, e.g. shared-clock drift).

## §7 Total cost composition

```
BCVF_total = α · Σ_g BCVF_within(g)  +  β · BCVF_across
```

Default `α = β = 1.0`. Configurable via `BCVFConfig.alpha_within`,
`BCVFConfig.beta_across`. Tuning question deliberately deferred to
the implementation phase — characterization data should drive the
choice, not pre-commitment.

The two terms are dimensionally identical (both are sums of
`gate · huber` per pair) so unweighted summation is sensible. A
caller wanting a strict "fire only on across-group failures" mode
can set `α = 0`; a caller wanting "ignore correlated group
failures" can set `β = 0`. Both are pathological but the knobs
exist.

## §8 Per-predictor attribution

Each predictor `i` in group `g(i)` accumulates two contributions:

```
attribution(i) = α · within_attribution(i, g(i))
               + β · across_attribution(g(i)) / |g(i)|
```

Where:

* `within_attribution(i, g)` is the existing per-predictor
  attribution from `BCVF_within(g)` — the `(M, H)` per-step
  per-predictor cost summed across the horizon.
* `across_attribution(g)` is the per-group attribution from
  `BCVF_across`, computed as if each group representative were a
  single predictor.
* The `/ |g|` distributes the across-group cost equally among
  group members. Across-group disagreement is a *group-level*
  observation; the kernel cannot tell which member is responsible
  by looking at the representative alone.

A future extension could distribute `across_attribution(g)`
*proportionally* to within-group rank (the worse a member is, the
more across-group cost it gets) — but that compounds two
attribution signals and is hard to interpret. Equal distribution
keeps the within-group signal and the across-group signal
addressable independently in the report writers.

## §9 Lemma 1 carry-through

The flat kernel's invariance: under cost order = SECOND, total
cost is exactly zero (up to fp64 noise) on a constant-bias and
linear-drift family.

Hierarchical preservation:

* **Within-group:** the within-group BCVF is the existing kernel
  on a subset of trajectories. Invariance carries by definition.
* **Across-group, options A and B:** the representative is a
  linear combination of group-member trajectories. Linear
  combinations of constants are constants; linear combinations of
  linear-in-time functions are linear-in-time. The second derivative
  of either is zero. Across-group BCVF is exactly zero (up to fp64
  noise) on the same nominal families.
* **Across-group, option C:** invariance requires the selected
  member to itself be Lemma-1-clean, which holds when the input
  family is constant-bias / linear-drift on every member — i.e.
  the same precondition as flat BCVF. Edge case: option C +
  noise_floor where the within-group argmin flickers between
  members. Not recommended (see §5 cons).

The certification grid's `constant_bias` and `linear_drift`
families therefore continue to assert max-cost ≤ 1e-9 on the
*hierarchical* total under the recommended configuration —
the grid expansion in §11 adds new families specifically for
hierarchical-only failure shapes, but the existing nominal
families don't need to change.

## §10 Failure modes the new design adds

| Mode | Description | Mitigation |
|---|---|---|
| **Group misconfiguration** | Caller assigns predictors to groups in a way that doesn't reflect physical correlation (e.g., a LiDAR in the camera group). Within-group BCVF reads spurious disagreement; across-group reads spurious agreement. | Groups are caller responsibility; `BCVFConfig` validation rejects only malformed partitions. The recommendation is "group by physical sensor class" + a documented `group_topology` field on the runtime that platform-team integrators populate from their hardware inventory. |
| **Single-member groups** | A group of size 1 produces zero within-group cost; the predictor contributes only to the across-group level. | Allowed by design — a singleton group is the natural default for a sensor class with only one member (e.g. one IMU, one GNSS). The within-group degeneracy is correct, not a bug. |
| **Asymmetric group sizes** | A group of 10 LiDARs paired against a group of 1 GNSS. Within-group costs are dominated by the size-10 group (45 pairs). Total is biased toward within-LiDAR-group disagreements. | Not a correctness issue — the bias reflects reality: more sensors = more chances for one to disagree. If callers want size-normalised costs, the option is to divide each within-group cost by `k(k−1)/2` before summing. Configurable via a `size_normalize_within: bool = False` flag (default off; opt in if a buyer's stack needs it). |
| **Cross-group correlated failure** | All LiDARs share a clock; the clock drifts. Within-group BCVF is silent (every LiDAR sees the same drift). Across-group fires (LiDAR group's representative is offset coherently from the camera / GNSS groups). | This is exactly the case the hierarchy is meant to catch — featured in §11 as the canonical new characterization family. |
| **Within-group correlated failure** | Two of three LiDARs share a clock; the third is independent. The shared-clock pair drifts together → within-group sees disagreement only from the third. Within-group BCVF could *mis-attribute* to the healthy independent LiDAR. | A real concern. Mitigation in the implementation phase: a `correlated_within_group` characterization family would expose it; the kernel itself doesn't need a change, but the calibration of within-group threshold T may need to be relaxed for groups expected to share state. Documented as a known limit. |

## §11 Certification implications

The 1320-cell certification grid (`run_primary_grid`, 22 configs ×
60 seeds, every per-config Wilson 95% CI lower bound ≥ 0.90)
covers the flat M = 3 case. Hierarchical adds:

* **New characterization families** specific to the hierarchy:
  * `cross_group_drift` — one whole group drifts coherently
    (shared-clock model). Across-group BCVF must fire; within-
    group BCVF must stay quiet.
  * `within_group_correlated` — two members of one group drift
    together; within-group BCVF must NOT mis-attribute to the
    third (independent) member.
  * `mismatched_group_size` — N = 2 with sizes 1 and k. Across-
    group cost asymmetry doesn't degrade flat-case detection.
  * `singleton_group_majority` — N groups of size 1 each (no
    within-group pairs). Hierarchical degenerates to flat
    across-group BCVF — must reproduce the flat result exactly.

* **Per-config Wilson floor still applies.** Each new family
  contributes one or more configs with the same per-config 60-seed
  cadence and the same `CERTIFICATION_FLOOR = 0.90` lower-bound
  requirement.

* **Estimated grid expansion:** 22 + ~5 = ~27 configs × 60 seeds
  = ~1620 cells. Sub-second on the existing host budget; no slow-
  marking required.

* **SOTIF traceability matrix** (clause 6, hazard identification)
  gains the new families as additional named hazard inputs. The
  `safety_case/SOTIF_TRACEABILITY.md` snapshot would refresh on
  the implementation commit.

## §12 Backward compatibility

* `BCVFConfig.groups` defaults to `None`. Every existing caller
  continues to run flat all-pairs BCVF.
* `compute_bcvf_cost` signature unchanged (no positional argument
  added; `groups` is read off the config).
* All 38 entries in `STABLE_API` continue to resolve and behave
  identically when `groups is None`.
* The hierarchical path is additive — flat behaviour is preserved
  bit-exact at `groups = ((0, 1, ..., M-1),)` (single group of all
  predictors → within-group equals flat, across-group is empty).
  Pinned by a regression test in the implementation commit.
* `__version__` bump on landing: minor (e.g. 0.4.x → 0.5.0)
  because the change is additive and stable-signature-preserving.
  No deprecation cycle required.

## §13 Ship-when-ready criteria

Hierarchical promotion from design-only to implementation requires
all three of:

1. **Real fleet data shows `M > 6` in production** — at least one
   buyer's stack has 8+ predictors.
2. **Flat-BCVF attribution dilution observed on that data** —
   per-predictor attribution magnitude shrinks below the triage-
   useful threshold (a SOTIF triage tool reading the per-predictor
   cost can no longer rank predictors confidently).
3. **The §11 certification-grid extension passes locally** —
   prototype implementation must hit the Wilson 95% CI lower-bound
   floor of 0.90 on every new family before the change lands in
   trunk.

Until all three trigger, hierarchical stays in the design-doc
phase. The flat kernel is shipping `production` for `M = 3` and
`M = 4` and the 1320-cell grid certifies it; nothing in this doc
takes that away.

## §14 API sketch (no implementation)

```python
from dataclasses import dataclass, field
from typing import Optional, Tuple

import numpy as np


@dataclass
class BCVFConfig:
    # ... existing fields unchanged ...

    groups: Optional[Tuple[Tuple[int, ...], ...]] = None
    """Predictor groupings. ``None`` (default) means flat
    all-pairs BCVF — backwards-compatible. A tuple of tuples
    must partition ``range(M)`` exactly: every index appears in
    exactly one group, no missing / duplicated indices."""

    representative: str = "trust_weighted"   # "trust_weighted" | "mean" | "winner_take_all"
    """Group-representative computation. See HIERARCHICAL_BCVF_DESIGN.md §5."""

    alpha_within: float = 1.0
    beta_across: float = 1.0
    """Total = alpha_within · sum(within) + beta_across · across."""

    size_normalize_within: bool = False
    """If True, divide each within-group cost by ``k(k−1)/2`` so
    asymmetric group sizes don't dominate. Off by default."""


def compute_hierarchical_bcvf_cost(
    trajectories: np.ndarray,    # (M, H, 3)
    config: BCVFConfig,
) -> BCVFResult:
    """Hierarchical BCVF kernel. ``config.groups`` controls the
    decomposition; ``None`` falls through to ``compute_bcvf_cost``."""
    # Validation:
    #   - ``groups`` partitions range(M) exactly.
    #   - Group sizes ≥ 1.
    #   - representative ∈ {"trust_weighted", "mean", "winner_take_all"}.
    raise NotImplementedError(
        "See HIERARCHICAL_BCVF_DESIGN.md — design only, not yet implemented."
    )
```

The dataclass fields above are illustrative — the implementation
PR is the authoritative source. The point of the sketch is to
make the API surface concrete enough to discuss without committing
to it.

## §15 Open questions (deliberately not decided)

* **Default representative.** §5 recommends option A (trust-
  weighted mean). Option B (arithmetic mean) is the simpler
  fallback. The decision is implementation-time, informed by
  characterization data on options A vs B for the new family
  set in §11.
* **`α / β` exposure.** §7 names them as configurable, but the
  default (`1.0 / 1.0`) is opinionated. Whether to expose them
  in the public API or keep them internal is an open question —
  fewer knobs is better unless an integrator needs them.
* **Across-group attribution distribution.** §8 distributes
  equally; proportional-to-rank is a possible refinement.
  Implementation-time choice.
* **Group adaptation at runtime.** Static groups (set in config)
  are the default. Dynamic groups (where membership shifts based
  on a learned trust score) are out of scope for the first
  hierarchical iteration — flagged here so a future RFC remembers
  the boundary.

## §16 What this is NOT

* Not a replacement for flat BCVF. The `M = 3 / M = 4` flat case
  remains the production default and the certification target.
* Not a feature flag toggle. Hierarchical is an opt-in via
  `BCVFConfig.groups`; default behaviour is byte-identical to
  v0.4.0.
* Not part of the public API yet. `compute_hierarchical_bcvf_cost`
  is in the design doc, not in `_api.STABLE_API` or
  `_api.PROVISIONAL_API`. Promotion to the registry happens with
  the implementation commit per §12.
* Not a SOTIF clause artifact today. The `safety_case` matrix
  references the implementations that ship; this doc is a
  forward-looking architecture note. The clause-evidence wiring
  lands with the implementation, not with the design.
