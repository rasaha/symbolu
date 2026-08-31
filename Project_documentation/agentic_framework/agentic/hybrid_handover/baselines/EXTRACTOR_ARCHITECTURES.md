# EXTRACTOR_ARCHITECTURES — Conventional Baselines for SEEB v1.0.0

Four conventional extractors, all behind the identical frozen
`ExtractorProtocol`, all run through the unchanged benchmark. The benchmark does
not know which extractor is running; only dependency injection changes.

## Controlled-comparison design
To isolate **retrieval capability**, every baseline shares the SAME frozen
relationship-resolution module (`InHouseExtractor`'s resolver + conflict/answer
construction). Baselines differ ONLY in the retrieval front-end that selects
evidence spans. Therefore:

- `resolved_answer`, `conflicts_resolved` (→ **Precedence Recall**) and coverage
  are identical across baselines — precedence is *not* a retrieval variable here.
- `evidence` spans differ → Critical / Defeater / Definition Recall, packet-only
  Sufficiency, faithfulness, Unsafe Handover vary.

This is a deliberate control: it answers "does better *retrieval* alone move the
metrics?" without conflating it with better reasoning.

## Dependency / environment note (honest scope)
No `numpy`, `scikit-learn`, or `sentence-transformers` were available, and no
model download was attempted. **All four baselines are pure-Python and
dependency-free.** The Embedding and Hybrid baselines therefore run in a
**character-3-gram cosine fallback** — a lexical proxy for a dense retriever. They
capture subword overlap (terminate/termination) but NOT true synonymy
(exit ≈ terminate). Their numbers are a **conservative lower bound** for a real
neural embedding model, not a ceiling. Substituting a real model requires only
replacing `EmbeddingExtractor.vectorise`.

## The four extractors

| Name | Retrieval algorithm | Deps | Time complexity | Impl. complexity |
|---|---|---|---|---|
| `keyword` | Fixed domain-keyword sentence match (the frozen baseline) + full-corpus rule resolver | none | O(n) scan | trivial |
| `bm25` | Okapi BM25 (k1=1.5, b=0.75), query-conditioned, top-K sentences | none | O(n·|q|) | low |
| `embedding` | Char-3-gram TF cosine NN (fallback for dense retrieval), top-K | none | O(n·d) | low |
| `hybrid_retriever` | Min-max-normalised BM25 ⊕ embedding fusion, top-K | none | O(n·(|q|+d)) | moderate |

`n` = sentences in corpus, `|q|` = query terms, `d` = n-gram vocab. Retrieval
budget `TOP_K = 4` (small because SEEB v1 corpora are short — see comparison doc).

## Interface conformance
Each satisfies `ExtractorProtocol`:
```python
def extract(self, question, corpus) -> EvidencePacket   # retrieval front-end differs
def resolve(self, question, corpus) -> ResolvedAnswer    # shared frozen resolver
```
`keyword` delegates both to `InHouseExtractor`. `bm25`/`embedding`/`hybrid`
subclass `BaseRetrieverExtractor`, implementing only `rank(question, corpus)`;
the base class handles top-K selection, verbatim span construction (exact
`char_span` offsets so spans ground cleanly), and packaging via the shared
resolver.

## Expected scalability
- **keyword**: O(n), trivially scalable; blind to anything outside its fixed lexicon.
- **bm25**: O(n) with an inverted index in production; scales to large corpora; vocabulary-mismatch sensitive.
- **embedding (real model)**: O(n) encode + ANN retrieval; scales with a vector index; strongest on paraphrase/synonymy — untested here (fallback mode).
- **hybrid**: production-standard; best recall/robustness at the cost of running two retrievers.

## Adding a new extractor (e.g. HybridPhaseTransformer)
Implement `ExtractorProtocol`, register it in `registry.py`, and it runs through
the identical benchmark and comparison unchanged — see `../evaluation/ROADMAP.md`.
