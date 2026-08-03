# Ranking Policy Design

- **Only P1-eligible** candidates are ranked (`rank_eligible_candidates` filters on
  `EligibilityState.ELIGIBLE`). Hard eligibility and ranking are separate layers.
- **Numeric representation: integer basis points** (0..10000). Float→bp conversion
  is confined to normalization via `Decimal` in a fixed context with `ROUND_FLOOR`
  (exact, cross-platform, monotonic). Weighting/summation are pure `int`, so
  `total_score == Σ weighted_contribution_bp`. Precision 1 bp; rounding ROUND_FLOOR.
- **Criteria** are drawn only from P1 profile/evidence fields: evidence_strength
  (weakest-link precedence), evidence_freshness, quality, reliability, latency
  (lower-better), cost (lower-better), security, audit.
- **Tie-break** (frozen total order): total_score → evidence_strength → freshness →
  reliability → cost → latency → provider_id → agent_id → agent_version.
- **Monotonicity** proven for higher-better and lower-better normalizers.
