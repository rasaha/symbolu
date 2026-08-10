# Governance Semantics Experiment v0.1

**HybridRelationshipResolver Experimental v0.4** = v0.2 proposal + validation
(bit-identical) + an experimental **Governance Semantics Layer** + a documented adapter
+ the **frozen** packet builder. Only the governance-semantics layer is new.

**Question:** given a validated graph, can a deterministic governance-semantics layer
distinguish supersession / amendment / exception / parallel applicability / cumulative
requirements / conflicting authorities, and locate the node carrying the operative term?

**Answer:** operative-source selection (G3) — reading the answer from the
prohibition/permission-bearing clause instead of the highest-authority clause — cleanly
fixes 5/5 competing-authority cases (+0.088 selective, 0 breaks, coverage & Mode G
unchanged). But the full layer (G4) adds a governance-abstention rule that over-fires,
collapsing coverage 0.95→0.28 and inflating selective artificially. **Verdict: NO CLEAR
SIGNAL** for the full layer; operative selection is a clean mechanism worth further
research. It does, for the first time in the series, **demonstrate frozen governance as
the active bottleneck**. See `FINAL_VERDICT.md`.

> Governing set pinned to the frozen set → Mode G, discovery, classification, and Mode P
> are structurally preserved (verified). Frozen architecture NOT changed regardless of
> outcome. Not promoted, not production-ready, not RRB v1.0.

## Reproduce
```bash
python -m agentic.hybrid_handover.resolution.experiment_v4.lock_v4                     # lock + verify (incl. all prior locks)
python -m agentic.hybrid_handover.resolution.experiment_v4.run_governance_experiment    # → GOVERNANCE_SEMANTICS_RESULTS.json (2 byte-identical reps)
python -m agentic.hybrid_handover.resolution.experiment_v4.make_reports_v4             # → the data-driven reports + tables
```

## Code
| file | role |
|---|---|
| `governance_semantics.py` | status model, applicability/operative rules, abstention, evidence vectors, adapter, ablations G0-G4 |
| `hybrid_resolver_v4.py` | v0.4 resolver: v0.2 discovery → governance semantics → adapter → frozen packet |
| `run_governance_experiment.py` | orchestrator: G0-G4, primary endpoint, non-inferiority, fix/break, competing-authority, attribution, subgroups |
| `lock_v4.py` | pre-evaluation content-hash lock (v0.4 + specs + v0.3/v0.2/v0.1 + frozen platform) |
| `make_reports_v4.py` | deterministic report generator |

## Deliverables (14 docs, 14 tables)
`GOVERNANCE_SEMANTICS_PREREGISTRATION.md` · `GOVERNANCE_SEMANTICS_ARCHITECTURE.md` ·
`GOVERNANCE_STATUS_MODEL.md` · `GOVERNANCE_RULEBOOK.md` · `OPERATIVE_SOURCE_SPEC.md` ·
`GOVERNANCE_ABSTENTION_SPEC.md` · `GOVERNANCE_SEMANTICS_HIDDEN_LOCK.md` ·
`GOVERNANCE_ABLATIONS.md` · `COMPETING_AUTHORITY_ANALYSIS.md` ·
`GOVERNANCE_FAILURE_ATTRIBUTION.md` · `GOVERNANCE_SEMANTICS_RESULTS.md` ·
`STATISTICAL_ANALYSIS.md` · `REPRODUCIBILITY_REPORT.md` · `FINAL_VERDICT.md` ·
(+ `GOVERNANCE_DIAGNOSTIC_SUBGROUPS.md`) · data: `GOVERNANCE_SEMANTICS_RESULTS.json`.
