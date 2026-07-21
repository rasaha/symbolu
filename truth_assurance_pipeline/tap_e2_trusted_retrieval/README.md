# TAP-E2 — Evidence Retrieval

The second TAP research layer. Given an `IntentRecord` from the **frozen TAP-E1** layer,
it selects candidate **evidence units** for downstream truth reasoning. It determines
*which evidence should be supplied* — nothing more. It makes no factual, policy,
relationship, authorization, claim, or response judgment and never answers the user.

> If retrieval starts making truth/claim/policy judgments, that logic belongs in a later
> TAP layer (see TAP-E3 recommendation in the report).

## "Trusted" means (narrow)

Provenance-bearing, reproducible, attributable, traceable, confidence-scored, and
gap-aware. It does **not** yet mean the evidence is factually correct, authoritative,
applicable, sufficient for claim support, or free of contradiction — those belong to
later TAP layers (see the report, §1a).

## Honesty (read first)

- New synthetic enterprise corpus; no TAP-E1 prompt reused.
- **"Dense semantic retrieval" is a deterministic idf-weighted concept-vector stand-in,
  NOT neural embeddings.** Results are mechanism/construction validation on synthetic
  text only — not real-world retrieval quality or production readiness.
- The eval split was content-hash locked and the configuration preregistered, but eval
  outputs were inspected during iterative engineering — a **locked development
  evaluation, not an untouched/interpreter-blind holdout** (not double-blind).

## Layout

```
tap_e2_trusted_retrieval/
├── evidence_unit.py   # EvidenceUnit / Document / EvidenceProvenance
├── schema.py          # RetrievalRecord, RetrievalQuery, confidence, gaps
├── chunking.py        # sentence chunker + concept lexicon (semantic stand-in)
├── index.py           # lexical inverted index + concept-vector cosine
├── provenance.py      # provenance attachment
├── ranking.py         # interpretable multi-signal ranking
├── retrieval.py       # 9-stage pipeline + A–F baselines + gap detection
├── metrics.py         # retrieval metrics + independent critical failures
├── harness.py         # E1→E2 driver, dev-only selection, gates, verdict
├── loader.py          # gold-free public loader
├── corpus/            # 14 docs / 32 evidence units / 30 queries (eval locked)
├── experiments/       # runner, preregistration, locks, results
└── tests/
```

## Run

```bash
python -m truth_assurance_pipeline.tap_e2_trusted_retrieval.experiments.run_experiment
python -m pytest truth_assurance_pipeline/tap_e2_trusted_retrieval/tests/ -q
```

## Use

```python
from truth_assurance_pipeline.tap_e1_intent import IntentUnderstandingLayer, config as e1c, RawUserRequest
from truth_assurance_pipeline.tap_e2_trusted_retrieval import TrustedRetrievalLayer, RetrievalIndex, config
from truth_assurance_pipeline.tap_e2_trusted_retrieval.corpus import documents

intent = IntentUnderstandingLayer(e1c("V4")).interpret(
    RawUserRequest("q", "How long do we retain customer data?"))
rec = TrustedRetrievalLayer(config("F"), RetrievalIndex.build(documents.units())).retrieve(intent)
for c in rec.candidates:
    print(c.unit.unit_id, round(c.score, 3), c.signals.to_dict())
for g in rec.gaps:
    print("GAP", g.gap_type.value)
```

## Result

Selected baseline **F** (full pipeline; E effectively tied). All six preregistered gates
pass on the locked development-evaluation split; verdict **`PASS_WITH_LIMITED_CLAIM`**.
Supported claim (narrow): a deterministic, provenance-preserving retrieval architecture
with interpretable ranking, explicit gap detection, and typed `RetrievalRecord` generation
on this study's synthetic corpus — it does **not** independently establish production
retrieval performance or external generalization. The `RetrievalRecord` schema is the
provisional frozen downstream interface; the **next layer is TAP-E3 — Relationship
Analysis**. See
[`EXPERIMENT_REPORT.md`](../../docs/truth_assurance_pipeline/experiments/tap_e2_trusted_retrieval/EXPERIMENT_REPORT.md).
