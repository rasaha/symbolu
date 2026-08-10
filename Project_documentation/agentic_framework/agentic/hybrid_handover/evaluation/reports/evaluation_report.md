# Hybrid Handover — Enterprise Readiness Evaluation

**Sovereign Evidence Extraction Benchmark (SEEB) v1.0.0**

> **SYNTHETIC EVALUATION.** All corpora are synthetic. This measures whether the sovereign hybrid layer can reliably produce *complete* evidence packets. It prioritises evidence completeness over generated-answer quality, and attempts to *falsify* the design.

## Verdict: **PARTIALLY VALIDATED**

Preventing a stronger verdict:

- Unsafe Handover Rate = 17.4% (4/23) (must be 0 — architecture must fail closed)
- Fail-closed rate = 85.0% (17/20) (accepted packets it should have refused)
- Defeater Recall = 60.0% (3/5) (missed exceptions/overrides are critical)
- Critical Evidence Recall = 77.8% (56/72)
- Coverage Completeness = 76.2% (32/42)

## Key finding — does independent validation reduce unsafe handovers?

| Configuration | Unsafe Handover Rate (P(accept \| decisive missing)) |
|---|---|
| Frozen gates only | 65.2% (15/23) |
| Gates + independent validators | 17.4% (4/23) |

## Primary enterprise-readiness metrics (augmented config)

| Metric | Value |
|---|---|
| Critical Evidence Recall | 77.8% (56/72) |
| Defeater Recall | 60.0% (3/5) |
| Definition Recall | 0.0% (0/2) |
| Precedence Recall | 52.9% (9/17) |
| Packet Sufficiency Rate | 59.5% (25/42) |
| **Unsafe Handover Rate** | **17.4% (4/23)** |
| Unsupported Claim Rate | 9.9% (14/141) |
| Coverage Completeness | 76.2% (32/42) |
| Routing Accuracy | 83.3% (35/42) |
| Fail-closed Rate (should-refuse cases) | 85.0% (17/20) |

## Recurring failure modes

- Unsafe under augmented validation: `['conflicting_definitions', 'inconsistent_numbering', 'later_amendment_override', 'policy_override']`
- Missed defeaters (exceptions/overrides): `['buried_exception', 'order_of_precedence']`
- Missed definitions: `['conflicting_definitions']`

## Per-case results (augmented)

| Case | Injector | Decision | Exp | Dec | Def | Defn | Prec | Missing | Unsafe | Suff | Cov |
|---|---|---|---|---|---|---|---|---|---|---|---|
| later_amendment_override | none | ESCALATE | ESCALATE | 3/3 | 0/0 | 0/0 | 1/1 | . | . | Y | Y |
| buried_exception | none | REFUSE | ESCALATE | 1/1 | 0/1 | 0/0 | 0/0 | Y | . | Y | Y |
| conflicting_definitions | none | ESCALATE | ESCALATE | 1/1 | 0/0 | 0/2 | 0/0 | Y | **Y** | Y | Y |
| order_of_precedence | none | REFUSE | ESCALATE | 1/1 | 0/1 | 0/0 | 0/1 | Y | . | . | Y |
| conflicting_versions | none | ESCALATE | REFUSE | 2/2 | 0/0 | 0/0 | 0/0 | . | . | . | Y |
| duplicate_amendment | none | ESCALATE | ESCALATE | 1/1 | 0/0 | 0/0 | 0/0 | . | . | Y | Y |
| ocr_corruption | none | REFUSE | REFUSE | 0/1 | 0/0 | 0/0 | 0/0 | Y | . | . | . |
| scanned_annex | none | REFUSE | REFUSE | 0/1 | 0/0 | 0/0 | 0/0 | Y | . | Y | . |
| hidden_negation | none | ESCALATE | ESCALATE | 1/1 | 1/1 | 0/0 | 0/0 | . | . | . | Y |
| conflicting_tables | none | ESCALATE | ESCALATE | 1/1 | 1/1 | 0/0 | 0/0 | . | . | . | Y |
| cross_document_reference | none | ESCALATE | ESCALATE | 2/2 | 0/0 | 0/0 | 0/0 | . | . | Y | Y |
| circular_reference | none | ESCALATE | REFUSE | 1/1 | 0/0 | 0/0 | 0/0 | . | . | . | Y |
| missing_appendix | none | REFUSE | REFUSE | 1/1 | 0/0 | 0/0 | 0/0 | Y | . | Y | . |
| irrelevant_distractors | none | ESCALATE | ESCALATE | 1/1 | 0/0 | 0/0 | 0/0 | . | . | Y | Y |
| inconsistent_numbering | none | ESCALATE | ESCALATE | 1/1 | 0/0 | 0/0 | 0/1 | Y | **Y** | . | Y |
| policy_override | none | ESCALATE | ESCALATE | 1/1 | 1/1 | 0/0 | 0/1 | Y | **Y** | . | Y |
| later_amendment_override | DropCriticalSpan | REFUSE | REFUSE | 1/3 | 0/0 | 0/0 | 1/1 | Y | . | . | Y |
| later_amendment_override | DropException | ESCALATE | ESCALATE | 3/3 | 0/0 | 0/0 | 1/1 | . | . | Y | Y |
| later_amendment_override | DropDefinition | ESCALATE | ESCALATE | 3/3 | 0/0 | 0/0 | 1/1 | . | . | Y | Y |
| later_amendment_override | DropLastAmendment | REFUSE | REFUSE | 2/3 | 0/0 | 0/0 | 0/1 | Y | . | . | Y |
| later_amendment_override | DropPrecedenceRule | ESCALATE | REFUSE | 3/3 | 0/0 | 0/0 | 0/1 | Y | **Y** | Y | Y |
| later_amendment_override | CorruptLocator | REFUSE | ESCALATE | 3/3 | 0/0 | 0/0 | 1/1 | . | . | Y | Y |
| later_amendment_override | TruncatedPacket | REFUSE | REFUSE | 2/3 | 0/0 | 0/0 | 1/1 | Y | . | . | Y |
| later_amendment_override | RandomChunkRemoval | REFUSE | REFUSE | 1/3 | 0/0 | 0/0 | 1/1 | Y | . | . | Y |
| later_amendment_override | DuplicateWrongVersion | ESCALATE | ESCALATE | 3/3 | 0/0 | 0/0 | 1/1 | . | . | Y | Y |
| later_amendment_override | ParserFailure | REFUSE | REFUSE | 2/3 | 0/0 | 0/0 | 0/1 | Y | . | Y | . |
| later_amendment_override | OCRNoise | REFUSE | REFUSE | 2/3 | 0/0 | 0/0 | 0/1 | Y | . | Y | . |
| later_amendment_override | MissingAnnex | REFUSE | REFUSE | 1/3 | 0/0 | 0/0 | 0/1 | Y | . | . | . |
| later_amendment_override | BrokenReference | REFUSE | REFUSE | 3/3 | 0/0 | 0/0 | 1/1 | Y | . | Y | . |
| irrelevant_distractors | DropCriticalSpan | REFUSE | REFUSE | 0/1 | 0/0 | 0/0 | 0/0 | Y | . | . | Y |
| irrelevant_distractors | DropException | ESCALATE | ESCALATE | 1/1 | 0/0 | 0/0 | 0/0 | . | . | Y | Y |
| irrelevant_distractors | DropDefinition | ESCALATE | ESCALATE | 1/1 | 0/0 | 0/0 | 0/0 | . | . | Y | Y |
| irrelevant_distractors | DropLastAmendment | REFUSE | REFUSE | 0/1 | 0/0 | 0/0 | 0/0 | Y | . | . | Y |
| irrelevant_distractors | DropPrecedenceRule | ESCALATE | ESCALATE | 1/1 | 0/0 | 0/0 | 0/0 | . | . | Y | Y |
| irrelevant_distractors | CorruptLocator | REFUSE | ESCALATE | 1/1 | 0/0 | 0/0 | 0/0 | . | . | Y | Y |
| irrelevant_distractors | TruncatedPacket | REFUSE | REFUSE | 0/1 | 0/0 | 0/0 | 0/0 | Y | . | . | Y |
| irrelevant_distractors | RandomChunkRemoval | ESCALATE | ESCALATE | 1/1 | 0/0 | 0/0 | 0/0 | . | . | Y | Y |
| irrelevant_distractors | DuplicateWrongVersion | ESCALATE | ESCALATE | 1/1 | 0/0 | 0/0 | 0/0 | . | . | Y | Y |
| irrelevant_distractors | ParserFailure | REFUSE | REFUSE | 1/1 | 0/0 | 0/0 | 0/0 | Y | . | Y | . |
| irrelevant_distractors | OCRNoise | ESCALATE | ESCALATE | 1/1 | 0/0 | 0/0 | 0/0 | . | . | Y | Y |
| irrelevant_distractors | MissingAnnex | REFUSE | REFUSE | 0/1 | 0/0 | 0/0 | 0/0 | Y | . | . | . |
| irrelevant_distractors | BrokenReference | REFUSE | REFUSE | 1/1 | 0/0 | 0/0 | 0/0 | Y | . | Y | . |

## Enterprise positioning — what is / is NOT supported by these results

| Claim | Supported by this run? |
|---|---|
| Evidence-grounded escalation (fails closed) | **No** — nonzero unsafe handover (17.4% (4/23) augmented, 65.2% (15/23) gates-only) |
| Reduced long-context frontier token usage | Demonstrated only on synthetic corpora (see handover demo); not a real-world measurement |
| Private data stays in perimeter (redaction) | Mechanically enforced + tested, on synthetic data |
| Auditability | Yes — every decision, gate, and validator finding is recorded |
| Reduced unsupported generation | Partial — unsupported-claim rate measured; not zero |

## Known limitations

- All corpora are SYNTHETIC and small; results bound the framework's behaviour, not real-world efficacy.
- The extractor under test is the frozen deterministic keyword/sentence extractor, NOT a neural HybridPhaseTransformer. Its failures are the baseline's, not necessarily the architecture's ceiling.
- Definitional-conflict omissions are measured (definition_recall) but NOT independently blocked by any validator — the contradiction search keys on defeater language, not on conflicting definitions.
- Numeric prose-vs-table conflicts (conflicting_tables) are not automatically detected; both spans may be present while the resolver silently picks one.
- 'Packet sufficiency' is computed with the deterministic resolver as the downstream reasoner and is therefore bounded by that resolver's capability, not a frontier model's.
- Token-reduction / private-data-retention claims are demonstrated on synthetic corpora only.

## Recommended next research phase

- Replace the deterministic extractor with a HybridPhaseTransformer-backed extractor implementing ExtractorProtocol, and re-run this identical framework to get the first neural numbers.
- Add a DefinitionConflictValidator that detects multiple governing definitions of the same defined term and blocks handover.
- Add a numeric-conflict validator for prose-vs-table disagreements.
- Source a small REAL (non-synthetic) contract set under NDA to replace at least the control corpora and measure real Critical Evidence Recall.
- Calibrate an abstention/confidence threshold so the extractor itself proposes REFUSE, rather than relying solely on downstream validators.
