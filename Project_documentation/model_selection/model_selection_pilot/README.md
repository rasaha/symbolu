# Model Selection Policy — Real-Model Shadow Pilot

A bounded, isolated pilot that tests whether the Model Selection Policy Engine can
predict the best eligible model for a real document-intelligence task **before**
execution, using only routing-time information — and whether that advantage survives
contact with real models.

**Current state: the harness is complete and tested, but no real model was executable
in this environment (see `PILOT_STATUS.md`). It ran in `SELF_TEST` (stub) mode to
validate the pipeline. No real-model results are fabricated.**

Imports nothing from the production tree (Hybrid LLM, ActionGate, TAP, KVPro, Cloud
Scaling). Follows the phase-1 synthetic experiment (`../model_selection_experiment/`)
and the specs in the repository root.

---

## Run

```bash
cd model_selection_pilot
python3 registry.py           # build verified registry (provenance-stamped)
python3 build_corpus.py        # build corpus + dev/shadow split
python3 harness.py             # counterfactual + all arms + ablations + report
python3 -m pytest tests -q     # 17 deterministic behavior tests
```

To run against **real** models, set provider keys and a spend cap, then re-run
`harness.py` — it auto-switches to `REAL` mode when all five adapters resolve:

```bash
export OPENAI_API_KEY=...  ANTHROPIC_API_KEY=...        # + valid AWS/Bedrock access
export PILOT_MAX_SPEND_USD=5.00                         # hard cap; aborts before exceeding
```

See `PILOT_STATUS.md` for the exact unblock steps and the credential probe results.

---

## Design highlights

- **Corrected decision order (F2):** 1 enterprise/governance hard constraints → 2
  verified technical eligibility → 3 minimum-quality gate → 4 minimum-reliability gate
  → 5 rank by utility → 6 fallback. A model predicted below the quality bar is
  eliminated, not merely down-ranked (fixing the phase-1 soft-quality weakness). The
  gate is **lenient under thin evidence** (indeterminate-pass) to avoid over-abstention.
- **Mandated ablations:** F1 (soft quality) vs F2 (hard gate); F2 vs G (bounded
  cold-start self-assessment). Self-assessment supplies **task-shape fields only**
  (decomposition, tool need, difficulty, weakness, prompting strategy) — never price,
  latency, compliance, eligibility, deployment, availability, context, or deprecation;
  enforced in code (`advisory.validate`) and tests. Preflight cost/latency charged to G.
- **Routing-time information boundary:** the policy sees a sanitized task view only;
  ground truth (`_oracle`) and post-execution outcomes are withheld and boundary-checked.
- **Full counterfactual:** every eligible model runs on every task; the best-eligible
  and Pareto set come from **observed** outcomes, never registry values alone.
- **Deterministic scoring:** rule-based per class (extraction F1, classification
  accuracy, summarization grounded-coverage/unsupported, QA correctness+evidence,
  clause P/R/F1, schema validity). No LLM judge.
- **Cost guard:** dry-run + worst-case + hard cap + per-call abort.
- **Provenance + versioning:** every registry field carries provenance/source/
  date_verified/verification_status; telemetry snapshots and policy/registry are versioned
  and pinned into every decision record.

## File map

| File | Role |
|---|---|
| `common.py` | deterministic hashing, IO, constants |
| `registry.py` / `data/registry.json` | verified model metadata + provenance |
| `build_corpus.py` / `data/corpus_*.json` | synthetic document-intelligence corpus + dev/shadow split |
| `provider.py` | execution adapters (anthropic/openai/bedrock real; deterministic stub) |
| `advisory.py` | bounded self-assessment field rules + validation |
| `policy.py` | routing-time policy (F1/F2/G), info boundary, decision records |
| `arms.py` | baselines A–E |
| `costguard.py` | dry-run + hard cap |
| `execute.py` | full counterfactual runner |
| `scoring.py` | deterministic per-class scorers |
| `telemetry.py` | regime-gated snapshots from dev outcomes |
| `metrics.py` | regret + secondary + commercial metrics |
| `harness.py` | orchestration + ablations + report |
| `tests/test_pilot.py` | 17 deterministic behavior tests |
| `PILOT_STATUS.md` | BLOCKED report + credential probe + unblock steps |
| `FALSIFICATION_PREREGISTRATION.md` | thresholds fixed before real results |
| `SELF_TEST_REPORT.md` | stub validation (explicitly NOT evidence) |
| `RECOMMENDATION.md` | provisional recommendation, gated on the real run |

## Results layout

- `results/raw/` — raw model outputs + token usage (separate store).
- `results/normalized/` — per-(task,model) scores/cost/latency (dev + shadow).
- `results/aggregate.json` — all arm scores, ablations, commercial, stability.
- `results/decision_records_F2_G_mature.json`, `results/decision_record_samples.json`.
