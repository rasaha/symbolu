# Scoring and Explanation

## Evidence class (read this first)

**All scores are ESTIMATED from declared / configured metadata — never measured production
performance.** Quality, reliability, and availability come from configured class-prior maps; cost and
latency come from configured class priors (or caller-supplied numeric estimates) normalized across the
eligible set. The package makes **no claim of objective superiority** from these configured weights.

`CandidateScore.measurement_basis` is always `estimated_from_declared_metadata`.

## Dimensions (each a fit score in `[0, 1]`, higher is better)

| Dimension | Meaning | Basis |
|---|---|---|
| `capability_fit` | fraction of required capabilities present (1.0 for eligible, since missing caps are hard-gated) | verified fact |
| `policy_fit` | 1.0 if the candidate carries the request's policy-domain tag, else 0.75 baseline | configured |
| `context_fit` | context headroom vs need; 1× → 0, ≥4× → 1.0 | verified fact |
| `quality_score` | quality tier prior (`economy…frontier` → 0.2…1.0) | configured prior |
| `latency_score` | 1 − normalized latency across the eligible set (fastest → 1.0) | estimated |
| `cost_score` | 1 − normalized cost across the eligible set (cheapest → 1.0) | estimated |
| `privacy_score` | 1.0 for `high` tier else 0.6; ×0.7 if the provider trains on data | configured |
| `reliability_score` | reliability class prior | configured prior |
| `availability_score` | availability class prior | configured prior |

## Normalization

- **Cost and latency** are normalized *relative to the eligible set*: `min → 1.0`, `max → 0.0`, and a
  constant set → all `1.0`. This is why scoring must run **after** hard filtering — the reference set is
  the eligible candidates.
- **Class-prior dimensions** use fixed, documented maps (see `scoring.py` / `estimate.py`), independent
  of the candidate set.
- **Missing data** is handled by the hard stage (disqualification) for required capabilities; for soft
  dimensions, defaults are conservative.

## Aggregation

`total = Σ(weightᵢ · componentᵢ) / Σ(weightᵢ)` → a weight-normalized average in `[0, 1]`. Weights come
from the policy preset + overrides. The recommendation exposes both raw `components` and `weighted`
contributions so any total is reproducible by hand.

## Confidence

`confidence` is a **dispersion diagnostic, not a quality guarantee**:

- single eligible candidate → fixed `0.6` (no comparison possible),
- otherwise → `clamp(0.55 + 1.5 · (top − runner_up), 0, 1)`.

`confidence_basis` states which rule produced it. A low confidence contributes to an **escalation
recommendation** (never an action).

## Explanation & evidence

`RoutingExplanation` gives a one-line summary plus ordered reasons (candidate counts, the winner and its
leading weighted dimensions, the runner-up margin, and the "hard-before-soft" guarantee), the weight
preset used, and the tie-break rule. `RoutingEvidence` fingerprints the registry/request/policy and
records every rejection (with its failing constraints) and every eligible candidate's full score — enough
to reproduce filtering and ranking exactly.
