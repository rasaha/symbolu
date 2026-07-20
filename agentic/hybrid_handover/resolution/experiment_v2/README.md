# Proposal Validation Experiment v0.1

**HybridRelationshipResolver Experimental v0.2** = v0.1 proposal generation
(unchanged) + a deterministic **Proposal Validation Layer** + the **frozen**
GraphTraversal governance & packet builder. Only the validation layer is new;
the v0.1 experiment and every frozen platform artifact are untouched.

**Question:** can unsupported relationship proposals be rejected before graph
construction without materially reducing genuine discovery?

**Answer:** yes for precision — discovery precision recovered **0.814 → 0.897**
(+0.083, bootstrap CI [0.020, 0.156]) at **zero recall loss**, removing 4 incorrect
edges and 0 correct ones — but the precision gain did **not** raise selective
accuracy. Verdict: **PROMISING VALIDATION LAYER (partial)**. See `VALIDATION_RESULTS.md`.

> The frozen architecture is NOT changed regardless of outcome. Not production-ready,
> not RRB v1.0; the result is one edge type on a 60-case pilot.

## Reproduce
```bash
python -m agentic.hybrid_handover.resolution.experiment_v2.lock_v2                    # (re)emit / verify lock
python -m agentic.hybrid_handover.resolution.experiment_v2.run_validation_experiment  # → VALIDATION_RESULTS.json (2 byte-identical reps)
python -m agentic.hybrid_handover.resolution.experiment_v2.make_reports_v2            # → the data-driven reports
```

## Code
| file | role |
|---|---|
| `validator.py` | per-edge validation gates, confidence vector, rejection taxonomy, ablations V0–V4 |
| `hybrid_resolver_v2.py` | v0.2 resolver: v0.1 proposal → validation → frozen governance/packet |
| `run_validation_experiment.py` | orchestrator: V0–V4 on visible + hidden, primary endpoint, taxonomy |
| `lock_v2.py` | pre-evaluation content-hash lock (v0.2 sources + v0.1 + frozen platform) |
| `make_reports_v2.py` | deterministic report generator |

## Deliverables
`PROPOSAL_VALIDATION_PREREGISTRATION.md` · `VALIDATION_RULEBOOK.md` ·
`CONFIDENCE_VECTOR_SPEC.md` · `EDGE_REJECTION_ANALYSIS.md` · `VALIDATION_ABLATIONS.md` ·
`VALIDATION_RESULTS.md` · `FAILURE_TAXONOMY.md` · `REPRODUCIBILITY_REPORT.md` ·
`HIDDEN_EVALUATION_LOCK_V2.md` · data: `VALIDATION_RESULTS.json`,
`VALIDATION_EDGE_RECORDS.json`.
