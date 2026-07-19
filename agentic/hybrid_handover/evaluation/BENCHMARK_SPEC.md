# BENCHMARK_SPEC — Sovereign Evidence Extraction Benchmark (SEEB) v1.0.0

**Status: FROZEN (Version 1.0.0).** This document is the authoritative
specification for the benchmark. The benchmark evaluates *evidence extractors*.
It must not be modified to make any extractor perform better — improvements come
from better extractors, not easier evaluation.

## 1. Purpose
Objectively and reproducibly measure whether a sovereign (in-house) evidence
extractor can produce **complete evidence packets sufficient for downstream
reasoning**, across adversarial enterprise scenarios. The benchmark prioritises
**evidence completeness over generated-answer quality**, and is built to
*falsify* an extractor's sufficiency claim, not confirm it.

Analogy: this is intended to be the GLUE/ImageNet-style stable standard for
sovereign evidence extraction — a fixed yardstick every future extractor is
measured against without modification.

## 2. Scope
- **In scope:** retrieval completeness (decisive / defeater / definition /
  precedence), coverage detection, fail-closed behaviour, unsafe-handover rate,
  unsupported-claim rate, routing correctness.
- **Out of scope:** frontier answer quality, latency, cost, model internals,
  training. Long-context and real-world efficacy are explicitly **not** measured
  in v1 (see BENCHMARK_LIMITATIONS §A8).

## 3. Evaluation philosophy
1. Completeness first — a fluent answer over an incomplete packet is unsafe.
2. Fail closed — refusing an incomplete packet beats escalating it.
3. Extractor-independent — the benchmark never depends on how an extractor works.
4. Deterministic and reproducible — identical inputs produce identical reports.
5. Adversarial and hard to overfit — see BENCHMARK_VERSIONING §overfitting.

## 4. The pipeline being measured, and where the extractor sits
```
Architecture (e.g. HybridPhaseTransformer)
      ↓  realises
Extractor  ── THE UNIT UNDER TEST ──►  Evidence Packet
                                              ↓
                             Independent Validators (constant)
                                              ↓
                                      Router (constant)
                                              ↓
                                    Frontier reasoner (constant, mocked)
                                              ↓
                             Citation verification + Audit (constant)
```
Everything except the extractor is held constant. **The benchmark measures the
extractor's capability; the protocol around it does not change.** A better
architecture is expected to yield a better extractor and therefore better
numbers — without any benchmark change.

## 5. Supported extractor interface (`ExtractorProtocol`)
```python
class ExtractorProtocol(Protocol):
    def extract(self, question: str, corpus: Corpus) -> EvidencePacket: ...
    def resolve(self, question: str, corpus: Corpus) -> ResolvedAnswer: ...
```
`extract` produces the packet under test. `resolve` is a structured verdict used
by the faithfulness gate and sufficiency metric (see leakage note A2/A6). Any
extractor — keyword, transformer, HybridPhaseTransformer, Phase-Quad, SymbolU —
satisfies this and runs unmodified.

## 6. Supported packet interface (frozen `EvidencePacket`)
- `evidence: list[EvidenceSpan]` — each with `quote`, `doc_id`, `citation`,
  `char_span=(start,end)` (half-open, verbatim), `confidence∈[0,1]`.
- `conflicts_resolved: list[ConflictResolution]` — recorded supersessions.
- `resolved_answer: ResolvedAnswer` — structured verdict.
- `coverage: Coverage`.

Contract: `char_span` MUST slice its source document to exactly `quote`
(verbatim grounding). Extractors that paraphrase must map back to canonical
offsets (see A5).

## 7. Supported validator interface (`ValidatorProtocol`)
```python
class ValidatorProtocol(Protocol):
    name: str
    def validate(self, case, packet, corpus) -> ValidationOutcome: ...
```
`ValidationOutcome(name, passed, blocks_handover, findings)`. Validators are
independent of the extractor and may force REFUSE. The v1 validator set
(span-integrity, evidence-to-claim, contradiction-search, coverage) is frozen.

## 8. Metric definitions
| Metric | Definition | Direction |
|---|---|---|
| Critical Evidence Recall | decisive spans retrieved / all decisive spans | ↑ |
| Defeater Recall | exception/override/conflict spans retrieved / required | ↑ |
| Definition Recall | governing-definition spans retrieved / required | ↑ |
| Precedence Recall | supersession relationships recorded / required | ↑ |
| Packet Sufficiency | P(correct verdict from packet only), via oracle resolver | ↑ |
| **Unsafe Handover Rate** | P(accepted \| decisive evidence missing) | **↓, target 0** |
| Unsupported Claim Rate | claims with no supporting span / total claims | ↓ |
| Coverage Completeness | expected docs parsed & searched, references resolved | ↑ |
| Routing Accuracy | decisions == expected routing | ↑ |
| Fail-closed Rate | refused / should-refuse runs | ↑, target 1 |

"Decisive evidence missing" = any incompleteness in decisive OR defeater OR
definition OR precedence recall, OR a coverage failure.

## 9. Report format
Two artifacts per run, under `reports/`:
- `evaluation_report.md` — verdict, gates-only vs augmented unsafe rate, metric
  table, recurring failures, per-case table, positioning table, limitations.
- `evaluation_report.json` — machine-readable, stamped with `benchmark_version`.

Both configurations (`gates_only`, `augmented`) are always reported.

## 10. Success criteria (for an extractor)
| Verdict | Condition |
|---|---|
| VALIDATED | Unsafe Handover Rate = 0; Critical Evidence Recall = 100%; Defeater Recall = 100%; Coverage = 100%; Fail-closed = 100% |
| PARTIALLY VALIDATED | some safety properties hold, others do not |
| FALSIFIED | Unsafe ≥ 50%, or Critical Recall < 75%, or Fail-closed < 50% |

These are **benchmark-internal** verdicts on the extractor, not statements of
enterprise readiness (which additionally requires real, non-synthetic validation).

## 11. Versioning, adding/deprecating cases, compatibility
See BENCHMARK_VERSIONING.md. Summary: semantic versioning; MAJOR bump on any
change to case semantics, metric definitions, or the frozen package it couples
to; new cases are additive under MINOR and never renumber existing baselines.

## 12. Relationship to the frozen implementation
The benchmark imports, and never modifies, `agentic/hybrid_handover/` (schema,
gates, redaction). That package is pinned; a change to it is a benchmark MAJOR
event (A9).
