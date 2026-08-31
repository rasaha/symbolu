# ROADMAP — Evaluating Future Sovereign Evidence Extractors on SEEB

How every future extractor is measured. **The benchmark does not change; the
extractor does.** Each stage below runs the *identical* SEEB v1.x by
implementing `ExtractorProtocol` — no benchmark modification is permitted to make
a stage look better.

## The invariant
```
   Architecture            Extractor (ExtractorProtocol)     Benchmark
   ───────────             ─────────────────────────────     ─────────
   keyword rules      →    InHouseExtractor            ┐
   HybridPhaseXformer →    HybridPhaseExtractor V1     │
   HybridPhaseXformer →    HybridPhaseExtractor V2     ├─►  SEEB v1.x  (UNCHANGED)
   Phase-Quad         →    PhaseQuadExtractor          │
   Phase-Quad+SymbolU →    SymbolUExtractor            │
   future             →    ...                         ┘
```
Only the middle column changes. Improvement must show up as better SEEB numbers,
not as an easier SEEB.

## Stage ladder

| Stage | Extractor | Expected focus of improvement | Watch these metrics |
|---|---|---|---|
| 0 (baseline) | `InHouseExtractor` (keyword) | — reference floor | all (see BASELINE_RESULTS) |
| 1 | HybridPhaseTransformer V1 | long-range decisive recall without keywords | Critical Evidence Recall, Precedence Recall |
| 2 | HybridPhaseTransformer V2 | defeaters & definitions (non-keyword salience) | Defeater Recall, Definition Recall, **Unsafe Handover Rate** |
| 3 | Phase-Quad | ambiguity/conflict detection → abstention | Fail-closed Rate, Routing Accuracy |
| 4 | Phase-Quad + SymbolU | semantic precedence & policy override, negation | Packet Sufficiency, precedence on cases 9/16 |
| 5 | future | close the residual to zero unsafe handovers | **Unsafe Handover Rate → 0** |

## How to run any extractor
```python
from agentic.hybrid_handover.evaluation import run
from my_pkg import HybridPhaseExtractor      # implements ExtractorProtocol

report = run(extractor=HybridPhaseExtractor())
print(report["meta"]["benchmark_version"], report["verdict"])
print(report["metrics"]["augmented"]["unsafe_handover_rate"])
```
Then commit the produced `reports/` alongside a one-line note referencing the
`benchmark_version`. Compare only within the same MAJOR.MINOR.

## Promotion criteria (extractor → next stage)
An extractor is considered to have *advanced* only if, versus the prior stage on
the same SEEB version, it:
1. does not regress any safety metric (Unsafe Handover, Fail-closed), and
2. improves at least one completeness metric with no completeness regression, and
3. shows no evidence of span-over-broadening gaming (BENCHMARK_VERSIONING §G5).

## Enterprise-readiness gate (separate from stage promotion)
No extractor is "enterprise-ready" on SEEB alone. That claim additionally requires:
- **Unsafe Handover Rate = 0** and **Fail-closed = 100%** on SEEB (public + hidden), and
- a **real, non-synthetic** corpus evaluation (see LIMITATIONS §B, BENCHMARK_VERSIONING §G4), and
- long-context corpora added in SEEB v2 (LIMITATIONS §A8) passing at the same bar.

## Parallel benchmark work (does not block extractor work)
- SEEB v2: long-context corpora, definition-conflict & numeric-conflict
  validators, independent sufficiency oracle, domain-parameterised lexicons
  (see BENCHMARK_LIMITATIONS mitigations). These are benchmark releases, versioned
  per BENCHMARK_VERSIONING — not edits to v1.
