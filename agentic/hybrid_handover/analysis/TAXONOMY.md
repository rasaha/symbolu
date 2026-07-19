# TAXONOMY — Enterprise Evidence Tasks, and where retrieval saturates

A five-level taxonomy of enterprise evidence tasks, every SEEB case mapped, and
the retrieval saturation boundary drawn from the capability-isolation result.

## Levels
| Level | Name | Capability | Operation |
|---|---|---|---|
| **L1** | Pure Retrieval | Find a span that exists, or detect it is absent | lexical match / coverage |
| **L2** | Semantic Retrieval | Find a query-relevant span with no fixed keyword; follow a reference | similarity / reference-following |
| **L3** | Relationship Resolution | Record a typed relationship between spans (supersession, precedence) | graph edge |
| **L4** | Cross-document Governance | Reconcile/authorise across documents (versions, cycles) | selection / cycle detection |
| **L5** | Policy / Logical Reasoning | Negation, contradiction, policy-over-contract | logical operator |

## Every SEEB case mapped
| Level | Cases | Capability-isolation result |
|---|---|---|
| **L1 Pure Retrieval** | irrelevant_distractors, duplicate_amendment, ocr_corruption*, scanned_annex*, missing_appendix* | all **solved** (*abstention via coverage) |
| **L2 Semantic Retrieval** | buried_exception, conflicting_definitions, cross_document_reference | all **solved** |
| **L3 Relationship Resolution** | later_amendment_override, order_of_precedence, inconsistent_numbering | 1 solved (native pattern), 2 **RETRIEVAL INSUFFICIENT** |
| **L4 Cross-document Governance** | conflicting_versions, circular_reference | 2 **RETRIEVAL INSUFFICIENT** |
| **L5 Policy / Logical Reasoning** | policy_override, hidden_negation, conflicting_tables | 3 **RETRIEVAL INSUFFICIENT** |

## The saturation boundary
```
   L1 Pure Retrieval        ┐
   L2 Semantic Retrieval    ┘  ← SATURATED by conventional baselines (all solved)
   ────────────────────────────  retrieval ceiling (a maximal oracle adds nothing)
   L3 Relationship Resolution ┐
   L4 Cross-document Governance│  ← RESIDUAL: not a retrieval problem
   L5 Policy / Logical Reasoning ┘
```

- **L1–L2 are fully saturated.** Every L1/L2 case is solved by BM25/embedding/
  hybrid, and a perfect oracle adds nothing.
- **L3 is the boundary.** `later_amendment_override` is solved *only* because the
  shared reasoning module hard-codes that one prohibition→grant pattern — a point
  capability, not retrieval. The other L3 cases (order_of_precedence,
  inconsistent_numbering) are retrieval-insufficient.
- **L3–L5 are the residual** and are entirely retrieval-insufficient (7/7).

## Reading
Conventional retrieval has climbed as far as L2. The SEEB residual lives at L3+,
where the task is to compute *over* retrieved spans — typed relationships (L3),
cross-document reconciliation (L4), and logical/policy operators (L5). The
capability-isolation experiment shows this boundary is a property of retrieval
itself, not of any particular retriever or of the benchmark's construction.
