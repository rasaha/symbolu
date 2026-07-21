# TAP-E2 — Trusted Retrieval — Experiment Report

> **Research & falsification phase.** Second TAP layer. Retrieval only. TAP-E1 is a
> frozen baseline, imported through its public interface and never modified.

Code: [`truth_assurance_pipeline/tap_e2_trusted_retrieval/`](../../../../truth_assurance_pipeline/tap_e2_trusted_retrieval/)
· Results: [`experiments/results_v2.json`](../../../../truth_assurance_pipeline/tap_e2_trusted_retrieval/experiments/results_v2.json)
· Prereg: [`experiments/preregistration.json`](../../../../truth_assurance_pipeline/tap_e2_trusted_retrieval/experiments/preregistration.json)

---

## 1. Objective & boundary

The Trusted Retrieval Layer answers exactly one question: **which evidence should be
supplied to downstream truth reasoning?** It does **not** decide factual correctness,
policy applicability, relationship validity, authorization, claim truth, or response
quality, and it never answers the user. Input: an `IntentRecord` from TAP-E1 (+ optional
conversation / app metadata). Output: a versioned `RetrievalRecord`.

If retrieval ever began making truth/policy/claim judgments, that logic would belong in
a later TAP layer — it is deliberately excluded here.

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

## 11. Leakage controls

Locked eval split with a content-hash lock (`eval_inputs_hash`); a gold-free public
loader (query gold — relevant/partial/distractor/expected-gaps — is never exposed);
dev/eval separation with no id or text overlap; duplicate detection; a corpus hash
(documents + units); a frozen-components hash; and dev-only configuration selection.

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
configuration (F) on the locked eval split: full recall of authoritative evidence,
complete provenance, authority coverage, correct gap detection (conflict + missing +
no-authoritative), low false-evidence, and zero severe critical failures. **The claim is
limited** to mechanism/construction validation on a small synthetic corpus with a
deterministic semantic stand-in — not real-world retrieval quality or production
readiness. The ladder is honest: hybrid > single-signal on ranking, provenance filtering
removes unsourced evidence, gap detection is what eliminates hidden conflicts, and the
full pipeline (F) only marginally edges the simpler gap-detecting hybrid (E).

## 14. Next recommended layer (TAP-E3)

Retrieval now supplies **evidence units with provenance, confidence, and explicit
gaps** — but deliberately makes no judgment about whether that evidence *supports a
claim*. The natural next layer is **TAP-E3 — Evidence / Claim Grounding**: given a
`RetrievalRecord` (evidence units + gaps) and an `IntentRecord`, decide, per candidate
claim, whether the retrieved evidence **supports, partially supports, contradicts, or is
insufficient** — carrying the E2 provenance and gaps forward, and abstaining when E2
reports `INSUFFICIENT_EVIDENCE` / `CONFLICTING_SOURCES`. It should reuse the E2
`RetrievalRecord` and `EvidenceProvenance` as its frozen input interface, keep truth
judgments strictly separated from retrieval, and be evaluated against a grounding corpus
with support/contradiction/insufficient gold under the same locked-split + preregistered-
gate discipline.
