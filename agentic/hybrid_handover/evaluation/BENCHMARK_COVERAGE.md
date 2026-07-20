# BENCHMARK_COVERAGE — SEEB v1.0.0

Maps every case to the capability it measures and the metric it drives (Phase F),
rates each case's difficulty (Phase E), flags keyword-trivial cases, and records
capability gaps to fill in Version 2.

## Coverage matrix: Case → Capability → Primary metric

| # | Case | Capability measured | Primary metric(s) | Difficulty |
|---|---|---|---|---|
| 1 | `later_amendment_override` | Long-range supersession resolution | Precedence Recall | Moderate |
| 2 | `buried_exception` | Low-salience exception retrieval | Defeater Recall | Hard |
| 3 | `conflicting_definitions` | Definitional completeness | Definition Recall | Extreme |
| 4 | `order_of_precedence` | Explicit precedence-rule capture | Defeater + Precedence Recall | Hard |
| 5 | `conflicting_versions` | Version disambiguation / abstention | Fail-closed, Routing | Hard |
| 6 | `duplicate_amendment` | Duplicate handling | Critical Evidence Recall | Easy |
| 7 | `ocr_corruption` | Source-quality abstention | Coverage, Fail-closed | Hard |
| 8 | `scanned_annex` | Unparsed-content coverage detection | Coverage, Fail-closed | Moderate |
| 9 | `hidden_negation` | Negation-sensitive interpretation | Packet Sufficiency | Hard |
| 10 | `conflicting_tables` | Prose-vs-table numeric conflict | Defeater Recall, Sufficiency | Hard |
| 11 | `cross_document_reference` | Reference following | Critical Evidence Recall | Moderate |
| 12 | `circular_reference` | Circular-reference detection / abstention | Fail-closed, Routing | Hard |
| 13 | `missing_appendix` | Missing-document coverage | Coverage, Fail-closed | Moderate |
| 14 | `irrelevant_distractors` | Distractor robustness | Critical Evidence Recall | Easy |
| 15 | `inconsistent_numbering` | Numbering normalisation + precedence | Precedence Recall | Hard |
| 16 | `policy_override` | Policy-over-contract precedence | Defeater + Precedence Recall | Hard |

Difficulty distribution: Easy ×2, Moderate ×4, Hard ×9, Extreme ×1.

## Keyword-trivial cases (Phase E — flag, do NOT replace in v1)
These are solvable for their *decisive* recall by naive keyword matching and
therefore under-discriminate strong vs weak extractors. Flagged for replacement
or hardening in v2; **retained unchanged in v1** for comparability.

| Case | Why trivial | v2 action |
|---|---|---|
| `irrelevant_distractors` | single keyword-visible clause; distractors lack the keyword | add distractors that DO contain the keyword but are irrelevant |
| `duplicate_amendment` | decisive clause keyword-visible; truncated dup is obvious | make the duplicate subtly divergent, not truncated |
| `later_amendment_override` (decisive spans only) | termination clauses are keyword-visible; only the precedence link is hard | keep — the precedence dimension remains discriminating |

Note: cases whose *decisive* spans are keyword-visible can still be hard on
**defeater / definition / precedence** dimensions (e.g. case 4, 16). Difficulty
is per-capability, not per-case.

## Capability categories covered in v1
Supersession · exceptions · definitions · explicit precedence · version conflict
· duplication · OCR/source quality · unparsed coverage · negation · table/prose
conflict · cross-reference · circular reference · missing document · distractor
robustness · numbering · policy override.

## Missing capability categories (Phase F — for Version 2, do NOT add now)
| Gap | Why it matters |
|---|---|
| **Long-context (10k–100k tokens)** | The architecture's central claim; v1 corpora are short (see LIMITATIONS A8) |
| Temporal / effective-date reasoning | Supersession often keys on dates, not document order |
| Multi-hop definition chains (A→B→C) | Real contracts nest definitions |
| Quantitative aggregation across schedules | Fees/caps summed across annexes |
| Implicit precedence (no explicit clause) | Hardest real-world conflict resolution |
| Numeric unit / currency conflicts | Cross-unit contradictions |
| Multilingual / mixed-language corpora | Enterprise reality |
| Redaction-inference adversarial | Does redaction leak via inference, not literal match |
| Entity/pronoun ambiguity | "the Company" resolution across docs |
| Obligations conflict across ≥3 parties | Multi-party precedence |

## Metric → capability crosswalk
- **Critical Evidence Recall** ← cases 1,6,11,14 (+ decisive spans everywhere)
- **Defeater Recall** ← cases 2,4,10,16
- **Definition Recall** ← case 3
- **Precedence Recall** ← cases 1,4,15,16
- **Coverage / Fail-closed** ← cases 5,7,8,12,13 (+ all corpus-level injectors)
- **Packet Sufficiency** ← cases 9,10 (reasoning-sensitive), plus all
