# Hybrid Handover — Enterprise Readiness Evaluation

> **Frozen as the Sovereign Evidence Extraction Benchmark (SEEB) v1.0.0.** This is
> a stable research artifact: it measures *any* future extractor without
> modification. Do not change the benchmark to make an extractor look better.
> Governing docs: [`BENCHMARK_SPEC.md`](BENCHMARK_SPEC.md) ·
> [`BASELINE_RESULTS.md`](BASELINE_RESULTS.md) ·
> [`BENCHMARK_COVERAGE.md`](BENCHMARK_COVERAGE.md) ·
> [`BENCHMARK_VERSIONING.md`](BENCHMARK_VERSIONING.md) ·
> [`ROADMAP.md`](ROADMAP.md) · [`BENCHMARK_LIMITATIONS.md`](BENCHMARK_LIMITATIONS.md).
> Integrity: `python -m agentic.hybrid_handover.evaluation.integrity` (must print OK).

A modular, **extractor-agnostic falsification framework** for the sovereign
hybrid handover layer. It exists to answer one question and to try to answer it
*negatively*:

> Can the sovereign hybrid layer reliably produce **complete** evidence packets
> that are sufficient for downstream reasoning?

It scores **evidence completeness, not answer fluency**. A packet that omits a
decisive amendment, exception, definition, or precedence rule is *unsafe* even if
the downstream model produces a confident answer. The single most important
metric is the **Unsafe Handover Rate** — the architecture must fail closed.

> **All corpora are SYNTHETIC.** These results bound the framework's behaviour
> and the current baseline extractor's behaviour. They are **not** a claim of
> real-world efficacy.

## Run

```bash
python -m agentic.hybrid_handover.evaluation.run_eval
python -m pytest tests/test_hybrid_handover_evaluation.py -q
```

Reports are written to `evaluation/reports/evaluation_report.{md,json}`.

## Design

Nothing depends on the concrete extractor. Everything plugs in via `protocols.py`:

| Module | Role |
|---|---|
| `cases.py` | Eval-case format: question, corpus, expected answer, required decisive / defeater / definition spans, precedence rules, coverage manifest, expected routing |
| `corpus.py` | 16 synthetic adversarial datasets, one per retrieval failure mode |
| `injectors.py` | 13 deterministic fault injectors (corpus-level and packet-level) |
| `validators.py` | **Independent** validation: span integrity, evidence-to-claim, contradiction search, coverage |
| `metrics.py` | The six enterprise metrics + aggregation |
| `harness.py` | Runs a case through the full flow under `gates_only` vs `augmented` |
| `report.py` | Aggregation, verdict classification, Markdown + JSON |
| `run_eval.py` | Single-command entry point |

Two configurations are always run so the report can show whether independent
validation actually helps:

- **`gates_only`** — the frozen pipeline's gates (grounding + packet-vs-full
  faithfulness) only.
- **`augmented`** — frozen gates **plus** the independent validators.

## Metrics

1. **Critical Evidence Recall** — decisive spans retrieved / all decisive spans
2. **Defeater Recall** — exception/conflict/override spans retrieved / required
3. **Packet Sufficiency Rate** — P(correct answer from packet only)
4. **Unsafe Handover Rate** — P(packet accepted | decisive evidence missing) — *must be 0*
5. **Unsupported Claim Rate** — claims lacking supporting evidence / total claims
6. **Coverage Completeness** — were all expected documents parsed & searched, references resolved

Plus Definition Recall, Precedence Recall, Routing Accuracy, and Fail-closed Rate.

## Plugging in a future extractor

```python
from agentic.hybrid_handover.evaluation import run
from my_pkg import HybridPhaseExtractor      # implements ExtractorProtocol

report = run(extractor=HybridPhaseExtractor())
print(report["verdict"], report["metrics"]["augmented"]["unsafe_handover_rate"])
```

The identical framework, cases, injectors, metrics, and report apply unchanged.

## Current baseline verdict (deterministic extractor, synthetic corpora)

**PARTIALLY VALIDATED — not enterprise-ready.** The independent validators cut
the Unsafe Handover Rate sharply (≈65% → ≈17%) but do **not** reach zero.
Residual unsafe handovers come from **missing definition and precedence
completeness**, which no current validator enforces. See the generated report
for the exact figures and the recommended next research phase.
