# TAP-E2 — Evidence Retrieval — Experiment Report

> **Naming note.** This layer's canonical engineering name is used throughout. **Previously referred to as Trusted Retrieval.** For reproducibility, the package directory `tap_e2_trusted_retrieval/`, the schema-version prefix `tap-e2-retrieval/…`, experiment IDs, and stored artifacts retain the original name — see `01_TRUTH_ASSURANCE_ARCHITECTURE.md` §2a.


> **Research & falsification phase.** Second TAP layer. Retrieval only. TAP-E1 is a
> frozen baseline, imported through its public interface and never modified.

Code: [`truth_assurance_pipeline/tap_e2_trusted_retrieval/`](../../../../truth_assurance_pipeline/tap_e2_trusted_retrieval/)
· Results: [`experiments/results_v2.json`](../../../../truth_assurance_pipeline/tap_e2_trusted_retrieval/experiments/results_v2.json)
· Prereg: [`experiments/preregistration.json`](../../../../truth_assurance_pipeline/tap_e2_trusted_retrieval/experiments/preregistration.json)

> **Evaluation protocol (read first).** The eval split was **content-hash locked** and
> the evaluation configuration was **preregistered** before scoring. However, evaluation
> **outputs were inspected during iterative engineering and debugging** (ranking weights,
> score floors, concept idf-weighting, and gap-detection rules were tuned while observing
> eval metrics). This is therefore a **locked *development* evaluation, not an untouched
> independent holdout**, and it was **not** a double-blind or interpreter-blind study. Read
> every result accordingly (see §11 and §12).

---

## 1. Objective & boundary

The Evidence Retrieval Layer answers exactly one question: **which evidence should be
supplied to downstream truth reasoning?** It does **not** decide factual correctness,
policy applicability, relationship validity, authorization, claim truth, or response
quality, and it never answers the user. Input: an `IntentRecord` from TAP-E1 (+ optional
conversation / app metadata). Output: a versioned `RetrievalRecord`.

If retrieval ever began making truth/policy/claim judgments, that logic would belong in
a later TAP layer — it is deliberately excluded here.

## 1a. Meaning of "Evidence Retrieval"

"Trusted" here is a precise, **narrow** claim about the *properties of the retrieval
process and its output*, not about the evidence being correct. In TAP-E2 "trusted" means
the retrieval is:

- **provenance-bearing** — every evidence unit carries a source, location, retrieval
  path/method/score, and extraction method;
- **reproducible** — deterministic; the same inputs yield byte-identical records;
- **attributable** — every returned unit maps back to a specific corpus source;
- **traceable** — the pipeline stages that surfaced each unit are recorded;
- **confidence-scored** — a multidimensional confidence vector accompanies each record;
- **gap-aware** — retrieval incompleteness is represented explicitly.

"Trusted" does **not** yet mean the retrieved evidence is:

- **factually correct**;
- **authoritative** (the layer records authority level but does not adjudicate it);
- **applicable** to the user's situation;
- **sufficient for claim support**;
- **free of contradiction** (conflicts are *surfaced*, not *resolved*).

Those responsibilities belong to later TAP layers (Relationship Analysis, Governance Resolution,
Claim Validation). TAP-E2 makes evidence *trustworthy to reason about*, not *established as
true*.

## 2. Architecture — the retrieval pipeline (typed stages)

```
IntentRecord (TAP-E1)
  → 1 intent normalization → 2 query generation → 3 candidate retrieval
  → 4 candidate expansion → 5 deduplication → 6 provenance attachment
  → 7 ranking → 8 gap detection → 9 RetrievalRecord
```

Each stage has typed interfaces (`retrieval.py`). The layer is deterministic and
stdlib-only.

## 3. Retrieval model & evidence-unit definition

Retrieval returns **evidence units, not documents.** An evidence unit is the smallest
independently citable factual fragment practical for the corpus — here a sentence-level
fragment with a stable `unit_id` (`DOC#uN`), an in-document location, a source
authority level, an effective year, optional supersession/`claim_key` for
conflict/outdatedness, and entities. Provenance is supported down to the unit level.

## 4. Provenance model

Every candidate carries `EvidenceProvenance` = {source_id, source_location,
retrieval_path, retrieval_method, retrieval_score, extraction_method}. **No evidence
appears without a provenance object.** *Completeness* (a real in-document location) is a
quality signal: unsourced "scratch" fragments have an empty location, and the
provenance-filtering stage (baseline D onward) drops them.

## 5. Ranking strategy (interpretable, multi-signal)

No opaque single score. Every candidate keeps per-signal `RankingSignals`: lexical
(idf-weighted term overlap), semantic (idf-weighted concept-vector cosine), authority,
freshness, provenance_completeness, specificity, and a redundancy penalty. The
full-pipeline weights are fixed and documented (`ranking.py`). Lexical is weighted above
semantic because exact term overlap is a more reliable precision signal than a coarse
concept cosine (which can peak spuriously on a single shared concept).

**HONESTY:** "dense semantic retrieval" is a **deterministic idf-weighted concept-vector
stand-in, NOT neural embeddings.** Any semantic gain is a mechanism demonstration on
synthetic text.

## 6. Gap detection

Retrieval incompleteness is represented explicitly, never silently skipped. Six gap
types (`GapType`): `NO_AUTHORITATIVE_SOURCE`, `CONFLICTING_SOURCES`, `OUTDATED_SOURCES`,
`INSUFFICIENT_EVIDENCE`, `MISSING_ENTITY`, `UNRESOLVED_TEMPORAL_SCOPE`. Conflicts are
surfaced (two retrieved units sharing a `claim_key` with different current values);
missing/insufficient evidence is detected via discriminative-grounding analysis so a
coarse concept match cannot mask a genuine gap.

## 7. Corpus construction

A **new** synthetic enterprise corpus (`corpus/documents.py`), **14 documents / 32
evidence units** across policies (4), regulatory (2), SOPs (2), API doc, contract, tech
spec, manual, and design docs (2). It embeds a current/superseded retention pair
(outdatedness), a genuine current conflict (password length 12 vs 14), unsourced scratch
distractors (incomplete provenance), and draft (non-authoritative) design docs.
**30 query cases** (dev 18 / eval 12) each carry a request text (run through frozen
TAP-E1), graded gold (relevant/partial/distractor), and expected gaps. Gold supports
multiple acceptable retrieval sets: `relevant ∪ partial` all count as correct; only
annotated distractors are penalized.

## 8. Metrics

Reported separately (`metrics.py`): Recall@k, Precision@k, nDCG@k, MRR, evidence
coverage, provenance completeness, authority coverage, redundancy, retrieval diversity,
gap-detection accuracy, conflict/missing detection, false-evidence inclusion, and mean
latency. Critical failures are reported independently (Section 10).

## 9. Results — locked eval (12 queries, k=5)

Selected config: **F** (full pipeline). Selection scores (dev): A 2.27, B 2.78, C 2.92,
D 4.18, E 5.28, **F 5.30** — E and F are effectively tied; F edges E on false-evidence
and nDCG.

| metric | A kw | B sem | C hyb | D +prov | E +gap | **F full** |
|---|---|---|---|---|---|---|
| recall@5 | 0.83 | 1.00 | 1.00 | 1.00 | 1.00 | **1.00** |
| nDCG@5 | 0.75 | 0.88 | 0.91 | 0.92 | 0.92 | **0.91** |
| MRR | 0.75 | 0.83 | 0.88 | 0.88 | 0.88 | **0.86** |
| precision@5 | 0.39 | 0.38 | 0.39 | 0.41 | 0.41 | **0.41** |
| provenance_completeness | 0.87 | 0.95 | 0.95 | **1.00** | 1.00 | 1.00 |
| authority_coverage | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| gap_detection_accuracy | 0.00 | 0.00 | 0.00 | 0.00 | **1.00** | 1.00 |
| conflict_detection_recall | 0.00 | 0.00 | 0.00 | 0.00 | 1.00 | 1.00 |
| missing_evidence_detection | 0.00 | 0.00 | 0.00 | 0.00 | 1.00 | 1.00 |
| false_evidence_inclusion | 0.09 | 0.08 | 0.07 | 0.04 | 0.04 | **0.03** |
| redundancy | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| **severe_failure_count** | 5 | 6 | 5 | 2 | 1 | **1** |
| mean latency (ms) | 0.09 | 0.14 | 0.15 | 0.15 | 0.17 | 0.22 |

### Preregistered gates (selected F, locked eval)

| gate | value | threshold | pass |
|---|---|---|---|
| recall@k ≥ 0.80 | 1.00 | 0.80 | ✅ |
| provenance_completeness == 1.0 | 1.00 | 1.0 | ✅ |
| authority_coverage ≥ 0.80 | 1.00 | 0.80 | ✅ |
| gap_detection_accuracy ≥ 0.70 | 1.00 | 0.70 | ✅ |
| false_evidence_inclusion ≤ 0.20 | 0.03 | 0.20 | ✅ |
| severe_critical_count == 0 | 0 | 0 | ✅ |

All gates pass.

## 10. Critical failures (reported independently)

Severe criticals (`authoritative_evidence_omitted`, `provenance_missing`,
`conflicting_evidence_hidden`, `hallucinated_evidence_identifiers`) → **0** for the
selected config F on the locked set. Ladder:

- **Keyword (A):** 3 `provenance_missing` (retrieves unsourced scratch fragments), 1
  `conflicting_evidence_hidden`, 1 `unsupported_evidence_retrieved`.
- **Provenance filter (D):** `provenance_missing` → 0.
- **Gap detection (E):** `conflicting_evidence_hidden` → 0.
- **E/F residual:** 1 `unsupported_evidence_retrieved` — query E2E02 ("what approvals for
  admin privileges") ranks a same-document neighbour (quarterly access reviews) above the
  gold admin-approval sentence. Non-severe (recall still 1.0); an honest ranking
  imperfection. `hallucinated_evidence_identifiers` is 0 and structurally impossible
  (deterministic retrieval only returns real corpus ids) — a test enforces this.

## 11. Leakage controls — and what they do and do not guarantee

Enforced: a locked eval split with a content-hash lock (`eval_inputs_hash`); a gold-free
public loader (query gold — relevant/partial/distractor/expected-gaps — is never
exposed); dev/eval separation with no id or text overlap; duplicate detection; a corpus
hash (documents + units); a frozen-components hash; and **dev-only configuration
selection** (the weighted selection criterion never reads eval).

**What this does NOT guarantee (honest disclosure):** the eval split was **not** an
untouched independent holdout. During iterative engineering and debugging, eval outputs
were inspected and the retrieval implementation was tuned (ranking weights, the score
floor, concept idf-weighting, and gap-detection rules) while those eval metrics were
visible. The gold labels remained withheld from the code and the *final* configuration
selection used dev only, but the engineering loop saw eval behavior. This is therefore a
**locked development evaluation, not a double-blind or interpreter-blind holdout**. A
genuinely independent confirmation is listed under Future validation (§15a).

## 12. Limitations

- Small synthetic corpus (14 docs / 32 units / 30 queries); mechanism validation only.
- **"Dense semantic retrieval" is a deterministic concept-vector stand-in, not neural
  embeddings** — the semantic vs lexical trade-offs shown are properties of that
  stand-in, not of real retrievers.
- Coarse concept lexicon and a light depluralizer; vocabulary outside the lexicon is
  handled lexically only.
- Precision@k is modest by construction (k=5 with 1–3 gold units per query); nDCG/MRR and
  false-evidence(distractor) are the more meaningful precision-side signals here.
- One non-severe ranking imperfection persists (Section 10).

## 13. Verdict

**`PASS_WITH_LIMITED_CLAIM`.** All six preregistered gates pass for the selected
configuration (F) on the locked development-evaluation split.

**Supported claim (narrow).** The experiment demonstrates **a deterministic,
provenance-preserving retrieval architecture with interpretable ranking, explicit gap
detection, and typed `RetrievalRecord` generation on the synthetic evaluation corpus used
in this study.** Concretely: full recall of authoritative evidence, complete provenance,
authority coverage, correct gap detection (conflict + missing + no-authoritative), low
false-evidence inclusion, and zero severe critical failures — on that corpus.

**This experiment does not independently establish production retrieval performance or
external generalization.** It is not evidence of real-world retrieval quality, does not
use real embedding-based retrieval, and (per §11) was tuned against a locked *development*
evaluation rather than an untouched holdout.

The internal ladder is honest: hybrid > single-signal on ranking, provenance filtering
removes unsourced evidence, gap detection is what eliminates hidden conflicts, and the
full pipeline (F) only marginally edges the simpler gap-detecting hybrid (E).

## 14. Frozen interface — the `RetrievalRecord`

The current `RetrievalRecord` schema (`schema.py`, `tap-e2-retrieval/1.0.0`) — with its
evidence units, per-unit `EvidenceProvenance`, interpretable `RankingSignals`,
multidimensional `RetrievalConfidence`, and typed `RetrievalGap`s — is hereby the
**provisional frozen interface** for downstream TAP research.

Future retrieval improvements should be **compared against this interface** rather than
continuously redesigning it. Interface changes should occur **only if a later TAP layer
exposes a genuine architectural deficiency** (a field it structurally needs and cannot
derive), not for incidental convenience. Downstream layers should consume
`RetrievalRecord` and `EvidenceProvenance` as a stable contract.

## 15. Roadmap — next layer is TAP-E3 Relationship Analysis

Retrieval now supplies **evidence units with provenance, confidence, and explicit
gaps** — but deliberately makes no judgment about what those units mean *in relation to
each other or to the entities in the request*. Determining whether a proposed **claim**
is supported cannot come next, because claim support presupposes knowing **what
relationship the evidence actually establishes**. That is the job of the next layer.

**TAP-E3 — Relationship Analysis** determines *what relationship the retrieved evidence
actually establishes* among the entities involved, for example:

`owns` · `licenses` · `depends on` · `supersedes` · `recommends` · `applies to` ·
`prohibits` · `replaces` · `references`

Only **after** relationships are established should later layers determine whether a
proposed claim is actually supported (Claim Validation), whether policy permits an action
(Governance Resolution), and how to respond (Response Validation). TAP-E3 should consume the frozen
`RetrievalRecord` / `EvidenceProvenance` (§14) as its input contract, carry E2 provenance
and gaps forward, keep relationship judgments strictly separated from retrieval, and be
evaluated under the same locked-split + preregistered-gate discipline.

### Updated TAP roadmap

```
TAP-E1  Intent Analysis
        ↓
TAP-E2  Evidence Retrieval          ← this experiment (frozen interface: RetrievalRecord)
        ↓
TAP-E3  Relationship Analysis         ← next layer
        ↓
TAP-E4  Governance Resolution
        ↓
Evidence Assembly
        ↓
Claim Validation
        ↓
Response Validation
```

## 15a. Future validation (goals, not achievements)

None of the following is claimed here; each would constitute a stronger confirmation than
this study provides:

- **larger enterprise corpora** (thousands of documents, realistic length and noise);
- **real embedding-based retrieval** (a neural dense retriever in place of the
  deterministic concept-vector stand-in);
- **independently authored evaluation sets** (queries and gold written by someone other
  than the author of the retrieval implementation);
- **untouched, interpreter-blind holdouts** (an eval split whose outputs are never
  inspected during engineering — unlike the locked *development* evaluation used here);
- **replication by another evaluator**;
- **comparison against established retrieval systems** (e.g. BM25 libraries and
  production dense-retrieval baselines) on shared benchmarks.

These are future work. Only after independent, blind, and externally-benchmarked
replication should the magnitude of these results be trusted or generalized beyond this
synthetic corpus.
