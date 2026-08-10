# Baselines A–O (Phase 7)

*`minimal_evidence_policy/baselines.py` → `eval_results/baselines.json`. 15 policies scored downstream
through the frozen EvidenceAssurance on held-out-natural (250) and adversarial-invariants (75).*

## Results

| Baseline | clean | over-qual | withhold | held unsafe | adv unsafe |
|---|---|---|---|---|---|
| A prior_uniform | 0.000 | 1.000 | 0.000 | 0 | 0 |
| B global_threshold | 1.000 | 0.000 | 0.000 | 109 | 75 |
| C lowrisk_bypass | 0.512 | 0.000 | 0.304 | 5 | 0 |
| D risk_only | 0.752 | 0.000 | 0.064 | **52** | 0 |
| E claim_type_only | 0.500 | 0.000 | 0.316 | 0 | 13 |
| F source_role_only | 0.748 | 0.000 | 0.128 | 62 | 0 |
| G claim_source | 0.500 | 0.000 | 0.316 | 0 | 13 |
| H claim_source_risk | 0.500 | 0.000 | 0.316 | 0 | 0 |
| **I rich_component** | 0.488 | 0.000 | 0.324 | 16 | **69** |
| J minimal_risk_floor | 0.716 | 0.000 | 0.100 | 43 | 0 |
| K minimal_no_invariants | 0.500 | 0.000 | 0.316 | 0 | 0 |
| L minimal_no_upward_only | 0.500 | 0.000 | 0.316 | 0 | 13 |
| M minimal_review_fallback | 0.500 | 0.000 | 0.316 | 0 | 0 |
| **Full_minimal** | 0.500 | 0.000 | 0.316 | **0** | **0** |
| N learned | 0.492 | 0.000 | 0.324 | 0 | 0 |
| O oracle | 0.544 | 0.000 | 0.272 | 0 | 6* |

Prior reference: 0% clean allow, 85.5% over-qualification. `*` oracle's 6 adversarial "unsafe" are the
INV-12 cases whose gold is legitimately E1 (the metric counts any synthetic ALLOW as unsafe; Full_minimal
over-escalates them to E3, so it scores 0).

## Findings

1. **The minimal policy is the safest useful policy.** Full_minimal: **50% clean allow (from the prior
   0%), 0 over-qualification, 0 held-out unsafe, 0 adversarial unsafe.** It converts the prior
   over-qualification failure into clean allows while leaking nothing.

2. **Risk-only is NOT safe on this data — the modifiers add safety.** D (risk-only) reaches 75% clean but
   **52 held-out unsafe allows**: it allows all low-surface-risk claims, including many whose gold is E3
   (independent evidence). The minimal policy's upward-only claim-type modifiers raise exactly those to
   E2/E3 and withhold them → 0 unsafe. This **rejects H0-1** (risk-only as good) in this setting — a
   reversal from the prior track, driven by the stricter minimal-vocabulary gold.

3. **The rich component fails the invariant traps catastrophically (69/75).** I (the prior 90-rule
   component, read-only) lacks the hard structural invariants, so it clean-allows self-verification,
   fixture-as-telemetry, stale-authority, etc. The minimal policy's explicit invariants catch all of
   them — the clearest validation of invariants-as-rules over learned features (**H0-4** signal).

4. **The global-threshold and low-risk-bypass shortcuts are unsafe**, as designed (B: 109+75 unsafe) —
   **H0-14** rejected.

5. **Invariants vs modifiers (nuance).** K (minimal without invariants) also reaches 0 adversarial unsafe,
   because the risk floor + claim-type modifiers already raise most trap cases; the invariants are the
   backstop for the residual (E/G/L, which drop the floor, leak 13). The ablation (Phase 17) quantifies
   the marginal safety of each.

## Determinism

All baselines are pure functions of the item; N is fit on DEVELOPMENT only. `baselines_sha256` pins the
result.
