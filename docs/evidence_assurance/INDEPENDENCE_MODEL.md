# Independence Model

*Phase 9. Multiple notions of independence, kept separate, then combined into a **verdict** (not an
opaque score). Implemented in `evidence_assurance/independence.py` over the provenance graph
(`provenance.py`). The governing rule: **different documents/publishers/URLs do not imply independent
evidence.***

## Notions of independence (separate)

| Notion | Observable from | Trustworthy when |
|---|---|---|
| **Document** | content hashes | distinct hashes (no exact duplication) |
| **Publisher** | publisher ids | ≥2 distinct AND provenance confidence ≥ 0.6 |
| **Upstream-source** | `upstream_source_id` | ≥2 distinct roots, not all derived from one |
| **Retrieval-path** | `retrieval_path` | ≥2 distinct paths (not one index/retriever) |
| **Temporal** | publication times | spread, not one snapshot mirrored |
| **Institutional** | publisher ownership | distinct owners (often opaque) |
| **Model** | which model produced a summary | **only partially observable → UNKNOWN, never assumed** |
| **Methodological** | shared training labels/method | **not in evidence metadata → UNKNOWN** |

## The verdict

`assess(case) → {INDEPENDENT | DEPENDENT | DUPLICATE | UNKNOWN}` plus:
- `effective_independent` — genuine independent sources, discounted by provenance confidence;
- `apparent_count` and `inflation_ratio = apparent / effective` (>1 ⇒ fake corroboration);
- per-notion booleans and reason codes.

**Decision:** if provenance is untrusted (confidence < 0.6 or missing) → **UNKNOWN** (cannot certify
independence from fabricated/absent metadata — never treat missing provenance as independence). Else
INDEPENDENT (≥2 effective, upstream-independent), DUPLICATE (exact duplication), or DEPENDENT.

## Measured discrimination (ea_corpus_v1)

| Partition | Independence verdict |
|---|---|
| CLEAN_INDEPENDENT | **INDEPENDENT** (312/312) |
| CLEAN_DEPENDENT | **DUPLICATE** (156/156) |
| CORRELATED_FAILURE | **DUPLICATE** (104/104) |
| ADVERSARIAL_PROVENANCE | **UNKNOWN** (52/52) — fabricated diversity is *not* trusted |

**Key limits (honest):** the independence verdict separates *independent* from *fake corroboration*,
but **DUPLICATE alone does not say whether the single underlying source is right or wrong** —
CLEAN_DEPENDENT (correct) and CORRELATED_FAILURE (wrong) are both DUPLICATE. Separating them requires
alignment + counterevidence on the underlying source (Phase 8, 10). And **model/methodological
independence is unobservable from evidence metadata** — the hardest correlated-failure types (shared
training data, model consensus on a false premise) are reported UNKNOWN, not solved.
