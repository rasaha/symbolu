# Exploratory Resolver Study v0.1

An exploratory, preregistered **architecture-falsification** study. Question: does a
richer deterministic relationship-proposal layer — feeding the *frozen*
GraphTraversal governance + packet builder — produce a measurable owner-clean
capability signal on the visible corpus and the frozen 60-case Hidden Relationship
Corpus Pilot v0.2?

**The purpose is not to prove the architecture, but to decide whether it is worth
further research.** Answer: **PROMISING SIGNAL, not non-inferior in current form.**
See `FINAL_VERDICT.md`.

> Not production-ready. Not RRB v1.0. Sixty synthetic cases are a pilot, not a
> certification corpus (Q6 = NO, a priori).

## How to reproduce
```bash
python -m agentic.hybrid_handover.resolution.experiment.run_experiment   # → EXPERIMENT_RESULTS.json (2 byte-identical reps)
python -m agentic.hybrid_handover.resolution.experiment.analyze          # → EXPERIMENT_ANALYSIS.json (slices, attribution)
python -m agentic.hybrid_handover.resolution.experiment.make_reports     # → the table reports below
python -m agentic.hybrid_handover.resolution.experiment.lock             # → re-emit / verify the hidden-evaluation lock
```
Everything is deterministic; the only RNG is the fixed-seed bootstrap in `stats.py`.

## Code
| file | role |
|---|---|
| `hybrid_resolver.py` | HybridRelationshipResolver Experimental v0.1 + ablations A0–A6 |
| `hidden_data.py` | read-only merged view of the 60 hidden cases (evidence + gold) |
| `hidden_metrics.py` | frozen owner-clean metric definitions re-applied to hidden data |
| `stats.py` | exact McNemar, paired bootstrap CI, Holm correction |
| `run_experiment.py` | orchestrator: 6 comparators + A0–A8, visible + hidden, 2 reps |
| `analyze.py` | generalization slices + per-case failure attribution |
| `lock.py` | content-hash lock of sources + frozen deps + manifest |
| `make_reports.py` | deterministic Markdown table generator |

## Documents
**Governance & method**
- `EXPERIMENT_PREREGISTRATION.md` — hypotheses, primary endpoint, frozen margins, ablations, stats (written before hidden eval)
- `HIDDEN_EVALUATION_LOCK.md` / `.json` — pre-evaluation content hashes + manifest
- `DATA_BOUNDARY.md` — what the resolver may/may not see; what was not modified
- `METHOD_BOUNDARY.md` — no LLM, no prompt, no training; how the resolver works

**Results**
- `RESULTS_SUMMARY.md` — one-page summary
- `FINAL_VERDICT.md` — verdict + the six required questions
- `PRIMARY_ENDPOINT_REPORT.md` — Table 2 (macro + bootstrap)
- `NON_INFERIORITY_REPORT.md` — Table 3 (frozen margins, violations)
- `COMPARATOR_REPORT.md` — Table 1 (6 resolvers × metrics)
- `ABSTENTION_COVERAGE_REPORT.md` — Table 4 (abstention decision + coverage)
- `STATISTICS_REPORT.md` — Tables 5–7 (McNemar, bootstrap, Holm)
- `ABLATION_REPORT.md` — Table 8 (A0–A8)
- `GENERALIZATION_REPORT.md` — Tables 9–11 (capability, difficulty, edge-type, wording, negative control)
- `FAILURE_ATTRIBUTION_REPORT.md` — Table 12 (per-stage attribution)
- `REPRODUCIBILITY_REPORT.md` — determinism, byte-identical reps, lock verification
- `LIMITATIONS_AND_THREATS.md` — sample, construct, validity threats; scope of claims

## Data artifacts
- `EXPERIMENT_RESULTS.json` — full metrics, non-inferiority, statistics, ablations
- `EXPERIMENT_ANALYSIS.json` — slices + failure attribution
