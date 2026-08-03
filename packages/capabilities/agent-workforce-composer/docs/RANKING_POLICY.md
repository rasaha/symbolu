# Ranking Policy

Ranking evaluates **only** P1-`ELIGIBLE` candidates (`rank_eligible_candidates`).
Hard eligibility and ranking are strictly separate — a high score never
compensates for a failed hard constraint.

## Score representation
Integer **basis points** (0..10000). The only float→bp conversion is criterion
normalization, done with `decimal.Decimal` in a fixed local context with
`ROUND_FLOOR` (exact, cross-platform, monotonic). Weighting and summation are pure
`int` math, so `total_score == sum(weighted_contribution_bp)` exactly
(`AgentRankResult.reconstruct_total()`). Precision: 1 bp. Rounding: ROUND_FLOOR.

## Criteria (default policy)
evidence_strength (weakest-link precedence rank of required-capability evidence),
evidence_freshness (remaining validity fraction), measured_quality, observed
reliability, latency_headroom (lower-better), cost_efficiency (lower-better),
security_headroom, audit_strength. Each has bounds `[lo,hi]` and a bp weight;
default weights sum to 10000. Only metrics supported by the P1 profile/evidence
contracts are used. A missing metric contributes 0 bp.

## Tie-breaking (frozen total order)
`total_score` desc → evidence_strength → evidence_freshness → reliability → cost →
latency → `provider_id` → `agent_id` → `agent_version`. The lexical identity tail
guarantees a deterministic total order. Tie-breaking never depends on input order,
dict order, hash randomization, wall clock, availability, or network.

## Monotonicity
`normalize_higher_better` / `normalize_lower_better` are monotonic; a weighted sum
of monotonic terms is monotonic in each beneficial criterion. Higher cost/latency
never improves its (lower-better) criterion. Tested in `tests/test_ranking.py`.
