# TAP-E1 — Intent Understanding Layer

A **new, self-contained** research track for the first phase of the Truth Assurance
Platform (TAP). It converts a raw user request into an explicit, structured
`IntentRecord` describing *what the user appears to want and what remains unresolved*
— and nothing more.

> **Boundary:** this layer interprets the request. It does **not** validate the
> world. It never decides factual correctness, retrieval, policy, claim support,
> authorization, or the final response, and it **never answers the request it is
> analyzing**. Trusted Retrieval, Relationship/Governance/Claim/Response Truth,
> Evidence Packets, ActionGate, and production TAP orchestration are out of scope and
> are not implemented or modified here.

> **Honesty:** the corpus is synthetic and human-authored for this study (no prior
> frozen intent corpus exists in this repository). The V0/V1 "model interpretation"
> is a **deterministic heuristic stand-in, not an LLM**, so the study is fully
> reproducible. Results validate a *mechanism on synthetic inputs only* — not
> real-world accuracy, downstream truth improvement, or production readiness.

## Layout

```
truth_assurance_pipeline/tap_e1_intent/
├── schema.py         # versioned IntentRecord + typed fields + validator
├── extraction.py     # deterministic-first extraction (spans retained)
├── provenance.py     # append-only ledger + precedence resolution
├── ambiguity.py      # materiality-classified ambiguity detection
├── conflicts.py      # conflict detection + instruction precedence
├── clarification.py  # proceed / assume / clarify / abstain policy
├── interpreter.py    # the layer + V0–V5 ablation ladder
├── metrics.py        # metrics + independent critical-failure counts
├── evaluator.py      # deterministic harness, gates, verdict, locks
├── loader.py         # leakage-controlled public loader (hidden gold withheld)
├── corpus/cases.py   # synthetic 86-case corpus (dev/eval/negative/adversarial)
├── experiments/      # run_experiment.py, preregistration.json, results_v1.json
└── tests/            # 30 behavioral tests
```

Everything TAP-E1 lives in this one tree (it is understandable, testable, movable,
and removable as a unit). The only files outside it are the canonical docs under
`docs/truth_assurance_pipeline/experiments/tap_e1_intent_understanding/` and the
empty `truth_assurance_pipeline/__init__.py` package marker.

## Run it

```bash
# reproduce the experiment (writes results_v1.json + experiment_lock.json)
python -m truth_assurance_pipeline.tap_e1_intent.experiments.run_experiment

# behavioral tests
python -m pytest truth_assurance_pipeline/tap_e1_intent/tests/ -q
```

## Use it

```python
from truth_assurance_pipeline.tap_e1_intent import (
    IntentUnderstandingLayer, RawUserRequest, config,
)

layer = IntentUnderstandingLayer(config("V4"))
rec = layer.interpret(RawUserRequest("r1", "Update the brief with TAP."))
print(rec.interpretation_status)          # AMBIGUOUS
print(rec.selected_interpretation)        # None  (does not commit)
print([a.dimension for a in rec.material_ambiguities])
```

## Result

Selected config **V4**; all five preregistered gates pass on the hidden eval split;
verdict **`PASS_WITH_LIMITED_CLAIM`**. See
[`EXPERIMENT_REPORT.md`](../../docs/truth_assurance_pipeline/experiments/tap_e1_intent_understanding/EXPERIMENT_REPORT.md)
and [`FAILURE_ANALYSIS.md`](../../docs/truth_assurance_pipeline/experiments/tap_e1_intent_understanding/FAILURE_ANALYSIS.md).
