# DATA_BOUNDARY — Exploratory Resolver Study v0.1

What the resolver under test may and may not see, and what was and was not touched.

## The resolver's inputs (identical for every comparator)
`resolve(question: str, evidence: list[EvidenceSpan])` — nothing else. Each
`EvidenceSpan` carries only the quote text, a citation string, a document id, and a
character span. The resolver **never** receives, at any stage:

- opaque hidden-case ids with meaning, or the seed/pilot split label;
- the capability tag, difficulty level, variation family, or negative-control flag;
- the gold graph, gold governance, gold packet expectation, or gold abstention flag;
- annotator rationales, ambiguity labels, per-edge confidences, or adjudication notes.

The capability / difficulty / variation / negative-control fields exist only in the
evaluation-facing gold and are used solely to *slice results after the fact* — they
are read by the metric harness, never by any resolver.

## What was NOT modified (verified byte-identical at lock time)
SEEB v1.0.0; the Hybrid Handover; the retrieval benchmarks; the baseline
extractors; the Relationship Resolution Measurement Specification v1.0; the
Relationship Corpus Curation Specification v1.0; the visible development corpus;
the 22 hidden seed cases; the 38 hidden pilot cases; every hidden annotation;
lifecycle / adjudication records; and the existing deterministic resolvers
(Frozen, Rule, GraphTraversal) and adversarial resolvers. Their SHA-256 hashes are
recorded in HIDDEN_EVALUATION_LOCK.md and re-checked by `lock.verify()` (zero drift).

## What was added (this study only)
`experiment/` — the new experimental resolver, a re-application of the frozen
owner-clean metric definitions to the hidden data (without editing the spec code),
the statistics module, the orchestrator, the lock, and the reports. Nothing here
feeds back into any frozen artifact.

## Corpus discipline
- The hidden corpus was **not** expanded, rewritten, or re-annotated.
- **No per-case hidden failure was inspected before the lock** or before all
  preregistered runs completed. Threshold selection (τ=0.5) and lexicon design used
  the visible corpus and general legal English only.
- No resolver was tuned against the hidden corpus. The two capability regressions
  discovered post-lock (`table_vs_text`, `hierarchical_governance`) were deliberately
  **left unfixed** to avoid post-hoc tuning; they are logged as future work.

## Synthetic data
All evidence is synthetic. No real contracts, PII, or customer data are involved.
