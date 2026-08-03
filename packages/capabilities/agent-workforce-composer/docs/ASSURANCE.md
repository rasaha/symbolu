# Assurance

## Invariants (tested)

| # | Invariant | Where |
|---|---|---|
| I1 | Constraint supremacy — any hard failure ⇒ not eligible | `test_eligibility.py::test_constraint_supremacy_no_partial_pass` |
| I2 | Total node accounting — each node exactly one role or non-agent disposition | `test_adapter.py::test_all_nodes_accounted_exactly_once` |
| I3 | Total agent accounting — one result per role × agent | `test_eligibility.py::test_total_agent_accounting` |
| I4 | No score/rank/winner in P1 outputs | `test_eligibility.py::test_no_score_or_rank_in_results`, `test_public_api.py` |
| I5 | Snapshot & result determinism | `test_determinism.py` |
| I6 | Ordering independence | `test_objects.py`, `test_determinism.py` |
| I7 | Evidence discipline (declared ≠ measured) | `test_evidence.py` |
| I8 | Version pinning of evidence | `test_evidence.py::test_wrong_agent_version_evidence_does_not_satisfy` |
| I9 | Expiry discipline | `test_evidence.py::test_expired_evidence_fails_closed` |
| I10 | Authority preservation | `test_examples.py::test_authority_preservation_across_all_examples` |
| I11 | Permission monotonicity | `test_eligibility.py::test_excessive_permission_requirement` |
| I12 | No empty-success ambiguity (`NO_ELIGIBLE_AGENT`) | `test_eligibility.py::test_empty_eligible_set_is_typed` |
| I13 | No ambient state (time/policy/snapshot injected) | `test_boundaries.py::test_no_system_clock_reads` |
| I14 | No runtime behaviour (no sockets/exec) | `test_boundaries.py` |
| I15 | Import-boundary integrity | `test_boundaries.py::test_no_forbidden_imports_in_source` |

## Verification surfaces
- `pytest tests` — package, adapter, eligibility, evidence, determinism, boundary,
  examples, public-API, CLI, and (optional) compiler-reference suites.
- `verify_agent_workforce_composer_distribution.py` — wheel/sdist build, wheel
  audit, clean-install outside the repo, CLI, cross-process determinism,
  reproducibility.
- `artifacts/public_api.json` — frozen public-API drift check.

Maturity is honest: `pilot_validated=false`, `production_certified=false`.

## P2 invariants (tested)

| # | Invariant | Where |
|---|---|---|
| P2-I1 | Eligibility supremacy — only P1-ELIGIBLE candidates ranked/selected/used as fallback | `test_ranking.py`, `test_fallback.py` |
| P2-I2 | No hard/soft compensation | `test_composition.py`, ranking separate from eligibility |
| P2-I3 | Ranking totality — each eligible candidate ranked once | `test_ranking.py::test_every_eligible_agent_ranked_once` |
| P2-I4 | Ranking determinism | `test_ranking.py::test_ranking_determinism_and_ordering_independence` |
| P2-I5 | Score reconstructability | `test_ranking.py::test_score_reconstruction` |
| P2-I6 | Tie-break totality | `test_ranking.py::test_deterministic_tie_break_total_order` |
| P2-I7 | Exact composition (vs brute-force oracle) | `test_composition.py::test_exact_optimum_matches_bruteforce_oracle` |
| P2-I8 | Total role accounting | `test_composition.py::test_total_role_and_non_agent_accounting` |
| P2-I9 | Non-agent preservation | `test_composition.py`, `test_plan.py::test_non_agent_dispositions_preserved` |
| P2-I10 | Interface compatibility | `test_composition.py::test_interface_compatibility_constraint_present` |
| P2-I11 | Least privilege | `test_permissions.py::test_least_privilege_invariants` |
| P2-I12 | No permission grant | `test_permissions.py::test_proposal_carries_no_grant_language` |
| P2-I13 | Authority monotonicity | `test_permissions.py::test_authority_bounded_by_ceilings` |
| P2-I14 | Fallback subset of eligible | `test_fallback.py::test_fallback_only_from_eligible_and_excludes_primary` |
| P2-I15 | Fallback uniqueness | `test_fallback.py::test_fallback_unique_and_ordered` |
| P2-I16 | Snapshot pinning | `test_fallback.py`, `test_plan.py::test_all_digests_pinned` |
| P2-I17 | No live state | `test_boundaries_p2.py::test_no_wall_clock_in_p2_core` |
| P2-I18 | Plan replay | `test_plan.py::test_replay_reproduces_plan_across_calls` |
| P2-I19 | No empty success | `test_plan.py::test_partial_never_reported_complete` |
| P2-I20 | Boundary integrity | `test_boundaries_p2.py` |

P1 compatibility is regression-tested in `test_p1_compat.py` (contract versions,
byte-identical P1 snapshot/policy digests, public-name availability).
