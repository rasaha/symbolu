# Competing Operative Resolution Experiment v0.1

**HybridRelationshipResolver Experimental v0.5** = G3 operative-source selection
(bit-identical) + a deterministic **Competing Operative Resolution Layer** that abstains
only on GENUINE unresolved conflict, replacing G4's coarse co-occurrence abstention.

**Question:** can a precise conflict model distinguish genuine unresolved conflict from
scoped override / exception / parallel applicability / cumulative requirements / mere
permission-prohibition co-occurrence, and abstain only when the outcome is genuinely
unresolved?

**Answer:** the model is safe and correct — it retains all five G3 fixes, never
over-abstains (coverage 0.95→0.933, false-abstention 0, vs G4's 0.28 / 0.5), and provably
abstains only on genuine conflict (synthetic gates C8/C9). But the hidden pilot contains
**zero genuine unresolved conflicts** (every competition is compatible or resolved), so it
adds no selective gain. **Verdict: NO CLEAR SIGNAL** (too few activating cases). The clear
next step is corpus work, not more resolver machinery. See `FINAL_VERDICT.md`.

> Control C0 = G3 exactly. Discovery / classification / validation / governing set / Mode P
> are structurally preserved. Frozen architecture NOT changed. Not promoted, not
> production-ready, not RRB v1.0.

## Reproduce
```bash
python -m agentic.hybrid_handover.resolution.experiment_v5.synthetic_fixtures                 # C8/C9 fixtures
python -m agentic.hybrid_handover.resolution.experiment_v5.lock_v5                             # lock + verify all prior locks
python -m agentic.hybrid_handover.resolution.experiment_v5.run_competing_operative_experiment  # → RESULTS.json (2 byte-identical reps)
python -m agentic.hybrid_handover.resolution.experiment_v5.make_reports_v5                     # → data-driven reports + tables
```

## Code
| file | role |
|---|---|
| `competing_operative.py` | OperativeCandidate schema, scope, 10 conflict predicates, classification, precise abstention, ablations C0-C4 |
| `hybrid_resolver_v5.py` | v0.5 resolver: G3 (unchanged) → competing-operative resolution → frozen packet |
| `synthetic_fixtures.py` | invented conflict fixtures for gates C8/C9 (not from hidden text) |
| `run_competing_operative_experiment.py` | orchestrator: C0-C4, C0-C9 gates, primary endpoint, transitions, conflict categories, packet-cardinality, attribution |
| `lock_v5.py` | pre-evaluation content-hash lock (v0.5 + specs + v0.4/v0.3/v0.2/v0.1 + frozen) |
| `make_reports_v5.py` | deterministic report generator |

## Deliverables (17 docs, 19 tables)
Preregistration · architecture · operative-candidate schema · scope spec · conflict-predicate
spec · conflict-classification rulebook · precise-abstention spec · packet-cardinality
boundary · hidden lock · ablations · case-transition analysis · packet-limitation analysis ·
failure attribution · results · statistical analysis · reproducibility · final verdict
(+ 12 questions). Data: `COMPETING_OPERATIVE_RESULTS.json`.
