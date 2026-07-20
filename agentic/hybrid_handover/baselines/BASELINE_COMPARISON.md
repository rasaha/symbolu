# BASELINE_COMPARISON — Conventional Extractors on SEEB v1.0.0

**Synthetic benchmark. Embedding/Hybrid ran in char-n-gram fallback (no neural
model available) — their numbers are a conservative lower bound for dense
retrieval.** All four extractors share the frozen relationship-resolution module
and differ only in retrieval (see EXTRACTOR_ARCHITECTURES.md). Benchmark unchanged.

## Results (augmented config)

| Metric | keyword | bm25 | embedding | hybrid |
|---|---|---|---|---|
| Critical Evidence Recall | 77.8% (56/72) | **83.3% (60/72)** | **83.3%** | **83.3%** |
| Defeater Recall | 60.0% (3/5) | **100% (5/5)** | **100%** | **100%** |
| Definition Recall | 0.0% (0/2) | **100% (2/2)** | **100%** | **100%** |
| Precedence Recall | 52.9% (9/17) | 52.9% (9/17) | 52.9% | 52.9% |
| Packet Sufficiency | 59.5% (25/42) | **61.9% (26/42)** | **61.9%** | **61.9%** |
| Coverage Completeness | 76.2% (32/42) | 76.2% | 76.2% | 76.2% |
| Unsupported Claim Rate | **9.9% (14/141)** | 10.6% | 10.6% | 10.6% |
| Unsafe Handover Rate | **17.4% (4/23)** | 20.0% (4/20) | 20.0% | 20.0% |
| Fail-closed Rate | **85.0% (17/20)** | 84.2% (16/19) | 84.2% | 84.2% |
| Routing Accuracy | 83.3% (35/42) | **88.1% (37/42)** | **88.1%** | **88.1%** |

BM25, embedding, and hybrid are **identical** on SEEB v1's short corpora: with
2–6 sentences per case and TOP_K=4, all three retrieve essentially the same
query-relevant spans. Differences would emerge on long-context corpora (SEEB v2).

## Key metric plots (Unsafe Handover — lower better; augmented)

```
keyword           ████·············· 17.4%   (4/23)
bm25 / emb / hyb  █████············· 20.0%   (4/20)
```
```
Definition Recall (higher better)
keyword           ·················· 0%
bm25 / emb / hyb  ██████████████████ 100%
```
```
Precedence Recall (higher better)
keyword           █████████·········  52.9%
bm25 / emb / hyb  █████████·········  52.9%   (identical — retrieval-invariant)
```

## Per-metric analysis — why each succeeds or fails

**Definition Recall — keyword 0% → retrieval 100% (retrieval WIN).**
`conflicting_definitions` asks "…how is Confidential Information defined?" The
definition sentences share the term "Confidential Information" with the question,
so any query-conditioned retriever surfaces them. The fixed-keyword extractor
only matches its termination lexicon and is structurally blind to definitions.
*Failure category: keyword lexicon blindness — solved by query conditioning.*

**Defeater Recall — keyword 60% → retrieval 100% (retrieval WIN).**
Keyword missed the `buried_exception` ("…locked in and may not exit early") and
the `order_of_precedence` clause ("the Order Form governs over the MSA") because
neither contains a termination keyword. Query-conditioned retrieval ranks them
in on lexical overlap with the question/context. *Failure category: low-salience
exceptions invisible to a fixed lexicon — solved by retrieval.*

**Critical Evidence Recall — 77.8% → 83.3% (modest WIN).**
Retrieval recovers a few decisive spans the fixed keyword set missed on
vocabulary mismatch (e.g. question says "penalty", document says "fee").

**Precedence Recall — 52.9% for ALL (retrieval CANNOT help).**
Precedence relationships are produced by the shared resolver, not by retrieval;
every retriever scores identically. This is the central negative result:
**improving retrieval alone does not change precedence/relationship recall.**
*Failure category: relationship reasoning — not a retrieval problem.*

**Unsafe Handover — the subtle result (absolute unchanged; composition shifts).**
Absolute unsafe handovers are **4 for every extractor**. The rate rises
(17.4%→20.0%) only because retrieval made 3 previously-incomplete runs complete,
shrinking the denominator. What matters is *which* cases are unsafe:

| | keyword unsafe | retrieval unsafe |
|---|---|---|
| `conflicting_definitions` | **UNSAFE** (missing definitions) | fixed → safe |
| `order_of_precedence` | safe (validator refused it) | **UNSAFE** (newly unmasked) |
| `inconsistent_numbering` | UNSAFE | UNSAFE |
| `policy_override` | UNSAFE | UNSAFE |
| `…/DropPrecedenceRule` | UNSAFE | UNSAFE |

Two movements:
1. Retrieval **eliminated** the one unsafe case caused by a *retrieval* gap
   (`conflicting_definitions`).
2. Retrieval **unmasked** `order_of_precedence`: keyword had accidentally been
   saved by the contradiction-search validator (which refused because keyword
   failed to retrieve the "governs over" clause). Once retrieval surfaces that
   clause, the validator is satisfied and the case escalates — but the resolver
   still cannot encode the precedence relationship, so it is now an unsafe accept.

**Every residual unsafe case is a precedence/relationship-reasoning failure.**
Better retrieval closes retrieval-shaped safety gaps and can *remove an
accidental safety net*, exposing the relationship-reasoning gap underneath.

**Fail-closed 85%→84.2%, Routing 83.3%→88.1%.** One fewer refusal (the unmasked
`order_of_precedence`) lowers fail-closed slightly; routing accuracy rises because
retrieval-completed cases now escalate as expected.

## Failure categories observed
- keyword lexicon blindness (definitions, low-salience exceptions) — **solved by retrieval**
- vocabulary mismatch (penalty/fee) — **mostly solved by retrieval**
- semantic-only defeaters (exit≈terminate) — **unsolved in fallback mode**; needs a real embedding
- precedence / order-of-precedence / policy override — **unsolved by all**; relationship reasoning
- version disambiguation, circular reference — **unsolved** (fail-closed misses, not unsafe)
- negation & prose-vs-table conflict — **unsolved** (complete packet, wrong verdict)

## Computational / implementation complexity
See EXTRACTOR_ARCHITECTURES.md. All pure-Python, O(n) per case. keyword is
trivial; bm25 low; embedding low; hybrid moderate (two retrievers). None require
GPU or external models in this run.

## Research conclusions (honest)

**Does semantic retrieval improve over keyword retrieval?** Yes, on *evidence
completeness* — the benchmark's primary objective. Query-conditioned retrieval
lifts Definition Recall 0%→100%, Defeater Recall 60%→100%, and Critical Recall
77.8%→83.3%.

**Where does it improve?** Exactly where the failure is *retrieval-shaped*: spans
that exist but carry no fixed keyword (definitions named in the query,
low-salience exceptions, vocabulary-mismatched decisive spans).

**Where does it fail?** Everywhere the failure is *relationship-shaped*.
Precedence Recall is unchanged (52.9%), and the residual unsafe handovers are
**entirely** precedence/policy-override cases. Retrieval can even *unmask* a
relationship failure that a validator was accidentally catching.

**Which cases remain unsolved even with (fallback) embedding retrieval?**
`inconsistent_numbering`, `policy_override`, `order_of_precedence`,
`…/DropPrecedenceRule` (all precedence), plus `conflicting_versions` /
`circular_reference` (disambiguation) and `hidden_negation` /
`conflicting_tables` (reasoning over complete evidence).

**Capability gap that appears to require explicit relationship reasoning rather
than better similarity search:** precedence/override discovery and cross-document
reconciliation. No retriever tested moves these, by construction and by result.

## Strongest conventional baseline
**The retrieval family (BM25 ≈ embedding ≈ hybrid) — tied.** They dominate keyword
on every completeness metric and on routing accuracy, at equal absolute unsafe
count. Among them, **BM25 is the most cost-effective** (no embedding model, O(n),
inverted-index-scalable) and is the recommended conventional reference point.
Keyword retains the lowest unsafe *rate*, but only via a denominator artifact and
an accidental validator refusal — not a real safety advantage.

## HybridPhaseTransformer readiness — where improvement would need to occur
Based solely on these results (no improvement claimed), a HybridPhaseTransformer
would need to demonstrate gains specifically in the categories conventional
retrieval does **not** move:

1. **Precedence Recall** (stuck at 52.9% for all) — record supersession/override
   relationships, not just retrieve the clauses.
2. **Cross-document reconciliation** — `policy_override`, `inconsistent_numbering`.
3. **Relationship discovery under the frozen resolver's blind spots** — the
   residual unsafe handovers are all here.
4. **Semantic-only defeaters** — `buried_exception`-style synonymy (where a real
   embedding, not the fallback, is the fair conventional comparator to beat).

It would need to do this **without** regressing the completeness metrics BM25
already solves, and **without** losing fail-closed behaviour. The benchmark stays
fixed; only the extractor changes.

## Limitations of this comparison
- SEEB v1 corpora are short (2–6 sentences); TOP_K=4 rarely binds, so retrieval
  selectivity is under-exercised and BM25/embedding/hybrid converge. Long-context
  corpora (SEEB v2) are needed to separate them.
- Embedding/Hybrid are char-n-gram fallbacks, not neural models — they understate
  dense retrieval, especially on synonymy (`buried_exception`).
- Precedence being retrieval-invariant is a *design choice* of this controlled
  comparison (shared resolver); it correctly attributes precedence to reasoning,
  not retrieval, but means these numbers do not test a retriever that also does
  its own relationship extraction.
