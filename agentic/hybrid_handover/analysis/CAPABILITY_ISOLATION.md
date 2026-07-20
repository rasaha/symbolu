# CAPABILITY ISOLATION — Is the SEEB plateau retrieval or reasoning?

**Phase type:** analysis only. SEEB, the baseline extractors, and the frozen
handover package are unmodified (verified). No HybridPhaseTransformer is
implemented or proposed. All corpora are synthetic.

## Question
The baseline comparison showed retrieval lifting Definition 0→100% and Defeater
60→100% while **Precedence stayed 52.9% and absolute unsafe handovers were
unchanged**. Is that plateau (A) an implementation limitation, (B) a benchmark
artifact, or (C) an inherent limitation of retrieval-based architectures?

## Method — the oracle counterfactual
For every case we ask: *"If an oracle retrieved every relevant span perfectly,
would the benchmark still fail?"* We answer it empirically, not rhetorically, by
running a **maximal retrieval oracle** — a diagnostic probe that returns **every
sentence** of the corpus as evidence (the strongest possible retrieval front
end; it cannot miss anything) and hands it to the same frozen reasoning module
every baseline uses. We then re-score under the unchanged benchmark.

- If a case is solved by the oracle → **RETRIEVAL LIMITED** (the deficit was retrieval).
- If a case still fails under the oracle → **RETRIEVAL INSUFFICIENT** (the deficit is *not* retrieval — perfect retrieval doesn't help).

"Solved" = expected routing achieved with complete decisive/defeater/definition/
precedence evidence and a sufficient packet (completeness-first).

## Result

| # solved by BM25 baseline | # RETRIEVAL LIMITED | # RETRIEVAL INSUFFICIENT |
|---|---|---|
| 9 / 16 | **0** | **7** |

**Zero cases are retrieval-limited.** Every unresolved case remains unsolved even
when retrieval is perfect.

| Case | Level | Baseline | Oracle (perfect retrieval) | Classification |
|---|---|---|---|---|
| later_amendment_override | L3 | solved | solved | already solved |
| buried_exception | L2 | solved | solved | already solved |
| conflicting_definitions | L2 | solved | solved | already solved |
| duplicate_amendment | L1 | solved | solved | already solved |
| ocr_corruption | L1 | solved (abstain) | solved | already solved |
| scanned_annex | L1 | solved (abstain) | solved | already solved |
| cross_document_reference | L2 | solved | solved | already solved |
| missing_appendix | L1 | solved (abstain) | solved | already solved |
| irrelevant_distractors | L1 | solved | solved | already solved |
| **order_of_precedence** | L3 | fail | **fail** | RETRIEVAL INSUFFICIENT |
| **inconsistent_numbering** | L3 | fail | **fail** | RETRIEVAL INSUFFICIENT |
| **policy_override** | L5 | fail | **fail** | RETRIEVAL INSUFFICIENT |
| **conflicting_versions** | L4 | fail | **fail** | RETRIEVAL INSUFFICIENT |
| **circular_reference** | L4 | fail | **fail** | RETRIEVAL INSUFFICIENT |
| **hidden_negation** | L5 | fail | **fail** | RETRIEVAL INSUFFICIENT |
| **conflicting_tables** | L5 | fail | **fail** | RETRIEVAL INSUFFICIENT |

Machine-readable: `CAPABILITY_ISOLATION.json`.

## Per-case: why retrieval succeeds or fails, and the failure category

| Case | Category | Why perfect retrieval does / does not solve it |
|---|---|---|
| irrelevant_distractors | pure retrieval | Span exists; retrieval isolates it. Solved. |
| duplicate_amendment | pure retrieval / duplicate | Intact clause present; retrieval finds it. Solved. |
| ocr_corruption | coverage / parse failure | Source garbled; correct = abstain; coverage detects. Solved. |
| scanned_annex | missing document / coverage | Content is an un-OCR'd image; abstain; coverage detects. Solved. |
| missing_appendix | missing document | Decisive doc absent; retrieval cannot invent it; coverage → abstain. Solved. |
| buried_exception | semantic retrieval | Low-salience exception carries no keyword; query-conditioned retrieval surfaces it. Solved. |
| conflicting_definitions | semantic retrieval / definition | Definitions named in the query; retrieval surfaces both. Solved. |
| cross_document_reference | reference following | Referenced value exists (Schedule C present); retrieval follows it. Solved. |
| **order_of_precedence** | **precedence reasoning** | The 'Order Form governs over the MSA' clause is retrievable, but making it govern is a typed EDGE, not a span. Perfect retrieval leaves precedence 0/1. |
| **inconsistent_numbering** | **precedence + normalisation** | Both clauses retrievable; recording that §7.01 supersedes §7.1 needs a normalisation edge + a supersession edge. Not a span. |
| **policy_override** | **policy reasoning** | Policy span retrievable; the overridden_by(clause, policy) relationship is not. Verdict stays wrong, precedence 0/1. |
| **conflicting_versions** | **version reasoning** | Both 'Amendment 3' spans retrieved; deciding which governs (or abstaining) needs version/authority selection. Retrieval yields ambiguity, not resolution. |
| **circular_reference** | **cross-document reconciliation** | A→B→A cycle; every pointer span retrieved; the value never exists. Needs cycle detection → abstain. Retrieval cannot detect a cycle. |
| **hidden_negation** | **logical contradiction / negation** | Evidence is COMPLETE; the verdict inverts on 'In no event'. A polarity error is unaffected by retrieval. |
| **conflicting_tables** | **logical contradiction** | Prose (3 mo) and table (6 mo) both retrieved; resolving the contradiction needs a precedence/consistency operator over the two spans. |

## Answering (A) / (B) / (C)

- **Not (A) implementation limitation.** BM25, the char-n-gram embedding, the
  hybrid retriever, AND a maximal oracle that returns *every* sentence all
  plateau at the identical seven failures and the identical 52.9% precedence.
  The plateau is invariant to retrieval implementation and even to a perfect
  retriever — it cannot be an implementation quirk.
- **Not (B) benchmark artifact.** The cases pass integrity (0 errors); the
  failures occur on well-formed relationship structures with valid ground truth.
  The short-corpus artifact (limited retrieval selectivity) affects only *how
  easily* retrievers reach saturation — it does not create the plateau, which
  persists under an oracle that ignores selectivity entirely.
- **(C) inherent limitation of retrieval.** Perfect retrieval solves 0 of the 7
  unresolved cases. The residual is, by construction and by measurement, not a
  retrieval problem.

## Central output
**Every unresolved SEEB case is RETRIEVAL INSUFFICIENT.** The plateau is an
inherent limitation of retrieval-based extraction for this benchmark's
relationship, governance, and logical cases — see `RELATIONSHIP_GRAPHS.md` and
`TAXONOMY.md`.

## Final answer — have conventional baselines saturated the retrieval component of SEEB?
**Yes.** Conventional retrieval solves every case whose difficulty is *finding a
span that exists* (Levels 1–2, plus reference-following and coverage-based
abstention). A maximal retrieval oracle adds nothing beyond the baselines. What
remains is not retrieval.

**The irreducible capability gap** is the ability to compute *over* retrieved
spans rather than merely surface them:
- record and traverse **typed relationships** (supersession, order-of-precedence,
  policy override) — a graph operation, not a similarity operation;
- **reconcile across documents** (version/authority selection, cycle detection);
- apply **logical operators** to complete evidence (negation, contradiction
  between representations).

These are reasoning capabilities. Whether and how any particular architecture
supplies them is out of scope for this phase and is not claimed here.
