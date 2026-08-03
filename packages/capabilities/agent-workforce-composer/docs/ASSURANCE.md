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
