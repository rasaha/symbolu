# Edge Prioritization Experiment v0.1

**HybridRelationshipResolver Experimental v0.3** = v0.2 proposal + validation
(bit-identical) + a deterministic **Edge Prioritization** layer + the **frozen**
GraphTraversal governance & packet builder. Only the prioritization layer is new.

**Question:** given multiple valid relationship proposals, can a deterministic
prioritization layer identify which relationships should dominate governance —
improving downstream decisions without changing proposal or validation?

**Answer:** the layer re-ranks competing governance sources (by an explainable
priority vector, authority-first) and changed 2 governance decisions on the hidden
pilot — but they cancel (1 fix, 1 break) and selective accuracy is unchanged
(0.2982). No protected metric degraded. **Verdict: NO CLEAR SIGNAL.** See
`FINAL_VERDICT.md`.

> The layer touches only the ordering of the governance-input graph in the full
> pipeline, so discovery, governance Mode G, and packet Mode P are structurally
> unchanged (P0 reproduces v0.2 exactly). Frozen architecture NOT changed regardless
> of outcome. Not production-ready, not RRB v1.0.

## Reproduce
```bash
python -m agentic.hybrid_handover.resolution.experiment_v3.lock_v3                       # (re)emit / verify lock
python -m agentic.hybrid_handover.resolution.experiment_v3.run_prioritization_experiment  # → PRIORITIZATION_RESULTS.json (2 byte-identical reps)
python -m agentic.hybrid_handover.resolution.experiment_v3.make_reports_v3               # → the data-driven reports
```

## Code
| file | role |
|---|---|
| `prioritizer.py` | priority vector, competing-source ranking, governance-input reorder, ablations P0–P4 |
| `hybrid_resolver_v3.py` | v0.3 resolver: v0.2 discovery → prioritization → frozen governance/packet |
| `run_prioritization_experiment.py` | orchestrator: P0–P4 on visible + hidden, primary endpoint, competition/decision deltas |
| `lock_v3.py` | pre-evaluation content-hash lock (v0.3 + v0.2 + v0.1 + frozen platform) |
| `make_reports_v3.py` | deterministic report generator |

## Deliverables
`EDGE_PRIORITIZATION_PREREGISTRATION.md` · `PRIORITY_VECTOR_SPEC.md` ·
`EDGE_PRIORITY_RULEBOOK.md` · `COMPETING_EDGE_ANALYSIS.md` ·
`PRIORITIZATION_ABLATIONS.md` · `PRIORITIZATION_RESULTS.md` · `REPRODUCIBILITY_REPORT.md` ·
`FINAL_VERDICT.md` · `HIDDEN_EVALUATION_LOCK_V3.md` · data: `PRIORITIZATION_RESULTS.json`,
`PRIORITIZATION_COMPETITIONS.json`.
