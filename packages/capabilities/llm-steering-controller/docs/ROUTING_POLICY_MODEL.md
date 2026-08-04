# Routing Policy Model

Routing policy is explicit and inspectable. It has two strictly separated parts: **hard constraints**
(decide eligibility) and **soft weights** (decide ranking among the eligible).

## Hard constraints (fail-closed, applied BEFORE scoring)

Fixed evaluation order (`constraints.py`):

1. `provider_not_prohibited` — request policy (hard)
2. `provider_approved` — if an approved-provider set is supplied (hard)
3. `model_not_prohibited` — request policy (hard)
4. `model_approved` — if an approved-model set is supplied (hard)
5. `not_deprecated` — a deprecated/retired candidate is disqualified (verified fact)
6. `modalities_supported` — required input modalities present (verified fact)
7. `structured_output_supported` — when required (verified fact)
8. `tool_use_supported` — when required (verified fact)
9. `capabilities_supported` — required capabilities present (verified fact)
10. `context_window_sufficient` — declared context ≥ `max(min_context_window, estimated_input_tokens)`
11. `privacy_tier_sufficient` — for `confidential`/`restricted`: model tier `high` **and** provider not
    training on data (fail-closed)
12. `data_residency_satisfied` — candidate serves an allowed region (fail-closed)
13. `cost_within_budget` — when a cost budget is configured (hard)
14. `latency_within_budget` — when a latency budget is configured (hard)

Rules that make the boundary trustworthy:

- **A high score can never restore a disqualified candidate.** Scoring runs only over survivors.
- **Prohibited providers/models cannot be re-admitted.**
- **Privacy and residency are fail-closed** — uncertainty rejects.
- **Missing/unknown capability metadata is treated as unsupported** (booleans default `False`, sets
  default empty).
- **Cost/context/latency/tool-use/structured-output requirements are enforced.**
- **No candidate → a typed failure** (`status = NO_ELIGIBLE_CANDIDATE`), never an arbitrary fallback.
- **Policy version is included in every result.**
- **Tie-breaking is deterministic and documented** (below).

## Soft weights (ranking only)

`policy.py` resolves a weight vector from a preference preset plus optional overrides. Presets change
only the `quality` / `cost` / `latency` weights; base weights (capability, policy, context, privacy,
reliability, availability) are fixed so presets stay comparable.

| Preference | quality | cost | latency |
|---|---|---|---|
| `quality_first` | 1.4 | 0.3 | 0.2 |
| `balanced` | 1.0 | 0.6 | 0.5 |
| `cost_first` | 0.7 | 1.4 | 0.3 |
| `latency_first` | 0.8 | 0.3 | 1.4 |

The total score is a **weight-normalized average**, so it always lies in `[0, 1]`. A soft weight (even a
huge override) changes ranking but never eligibility. Invalid weights (unknown dimension, negative,
all-zero) raise `PolicyViolation`.

## Tie-breaking

Candidates with an equal total score (compared at 6-decimal precision) are ordered by `model_id`
ascending, then `provider_id` ascending. This is surfaced in every recommendation as
`explanation.tie_break_rule` and is fully deterministic.

## Policy version

`SteeringRequest.policy_version` (default `steering-policy-1.0`) is bound onto the resolved policy and
appears in the result, the policy fingerprint, and the decision id — so a decision is always reproducible
against the exact policy it was produced under.
