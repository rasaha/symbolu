# RESULTS_SUMMARY — Exploratory Resolver Study v0.1

One page. For the full picture read FINAL_VERDICT.md and the per-table reports.

## Headline
Swapping a richer **relationship-proposal layer** in front of the **frozen**
GraphTraversal governance + packet builder raises the hidden owner-clean macro
**0.4973 → 0.5761 (+0.0788)** on the 60-case Hidden Relationship Corpus Pilot v0.2.
The gain is statistically significant (bootstrap 95% CI [0.035, 0.131] excludes zero;
discovery-completeness McNemar p = 7.6e-05), broad-based, and reproducible — but it
**fails two preregistered non-inferiority constraints** (discovery precision and
selective accuracy). **Verdict: PROMISING SIGNAL, not non-inferior in current form.**

## Primary endpoint (hidden owner-clean macro)
| resolver | macro | disc F1 | class | govG | packP | selective |
|---|---|---|---|---|---|---|
| GraphTraversal | 0.4973 | 0.3031 | 0.7333 | 0.6000 | 0.5167 | 0.3333 |
| Hybrid | **0.5761** | **0.5512** | **0.9143** | 0.6000 | 0.5167 | 0.2982 |

Governance and packet are identical (frozen reuse) → the gain is isolated to discovery.

## Where it wins
- Discovery recall 0.18 → 0.42; classification 0.73 → 0.91.
- Improves in **both** wording families (seed +0.086, pilot +0.074) and at all five
  difficulty levels.
- Biggest capability gains: nested/scoped exceptions, version supersession, circular
  and implicit references, insufficient-evidence handling.
- Biggest edge-type gains: `exception_to` 0.18 → 0.57, `references` 0.35 → 0.70.
- Negative controls: hybrid **0.70 vs 0.47** — it does not hallucinate governance.

## Where it costs
- **Discovery precision 1.00 → 0.814** (over-proposes edges) — violates the 0.05 margin.
- **Selective accuracy 0.333 → 0.298** — violates the 0.03 margin.
- Two capabilities regress (`table_vs_text`, `hierarchical_governance`), left unfixed
  to avoid post-hoc tuning.

## What is NOT harmed
Unsafe/overconfident answers unchanged (2 = 2); false-abstention 0.0; missed-abstention
improves (0.267 → 0.217); determinism holds (two byte-identical repetitions).

## Attribution (ablations)
A1 (remove the semantic proposal layer) returns the macro to the GraphTraversal
baseline — the proposal layer is the **entire** source of the gain. The confidence gate
(A4) and provenance filter (A5) are inert on this corpus.

## Six questions, in brief
Q1 signal? **YES.** Q2 significant? **YES.** Q3 attributable to relationship reasoning?
**YES.** Q4 non-inferior/safe-tradeoff? **NO** (precision + selective violations, but no
safety regression). Q5 generalizes across families/difficulty *within the pilot*?
**YES.** Q6 broad generalization / certification? **NO** (60 synthetic cases are a
pilot). See FINAL_VERDICT.md.

## Status
HybridRelationshipResolver **Experimental v0.1** — promising, not promoted. Not
production-ready. Not RRB v1.0.
