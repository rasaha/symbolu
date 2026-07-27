# Phase Capability

## Validation, Falsification, and Test Specification

Frozen V2-S Phase Memory, Auxiliary Information-Health Signals, and Bounded Quadratic Integration

> **Document intent** — Convert every Phase capability statement into one of four things: a reproducible result, a pre-registered experiment, an explicit non-capability, or a prohibited claim. No architectural claim is accepted merely because it appears in a design document.

| Document control | Value |
| --- | --- |
| **Document version** | 1.0 |
| **Date** | 27 July 2026 |
| **Status** | Research validation specification; not a production claim |
| **Primary scope** | Frozen V2-S Phase recurrence and bounded enterprise evidence architectures |
| **Current research branch** | `claude/frozen-phase-transformer-diag-jzabnu` (project-reported) |
| **Frozen baseline** | 98/98 Phase tests and FREEZE OK (project-reported; rerun required at execution) |
| **Supersession rule** | This specification overrides unqualified claims in legacy pitch/design material unless the claim passes the evidence gates defined here. |

*Prepared for Soulpi / Ugence Labs research validation*

---

## Contents

1. Purpose, audience, and governing rule
2. Executive capability statement
3. Canonical frozen V2-S algorithm
4. Current evidence snapshot
5. Capability status and claim language
6. Architecture boundaries
7. Validation principles and source hierarchy
8. Test-family overview
9. Core long-range memory protocol
10. Long-document search and salience protocol
11. Auxiliary information-health (DHA) protocol
12. Bounded quadratic integration protocol
13. Cross-domain world-model transfer protocol
14. Causal controls and falsification matrix
15. Metrics and pre-registered acceptance criteria
16. Reproducibility and artifact requirements
17. Claim-to-evidence ledger
18. Enterprise pilot and production gates
19. Execution roadmap
20. Appendices: schemas, result format, test manifest, references

---

## 1. Purpose, Audience, and Governing Rule

This document is the canonical validation specification for Phase capability. It is written for researchers, engineers, reviewers, patent counsel, enterprise design partners, and diligence teams who need a precise answer to three questions: what Phase currently does, what it does not do, and what experiments would be sufficient to change that answer.

> **Governing rule** — Every statement about Phase must be traceable to a test ID, raw result artifact, code/configuration hash, baseline comparison, and causal control. Statements that lack this chain are hypotheses—not capabilities.

The document deliberately separates:

- **Mechanism:** the recurrent Phase update and its computational properties.
- **Capability:** a task-level behavior demonstrated under defined conditions.
- **Product role:** a bounded enterprise function that remains valid under real data, access controls, provenance requirements, and failure handling.
- **Vision:** a future hypothesis such as cross-domain world-state modeling.

The specification is not a marketing summary and does not assume that older architecture documents are correct. Legacy descriptions are treated as design hypotheses unless current frozen-code experiments reproduce them.

---

## 2. Executive Capability Statement

> **Current defensible statement** — Frozen V2-S is a bounded O(N) temporal memory candidate with strong controlled long-range cue-retention evidence. It is not validated as an exact evidence router, word-search engine, multi-hop relational reasoner, autonomous world model, or factual authority.

| Capability | Status | Current defensible interpretation |
| --- | --- | --- |
| **Long-range cue retention** | SUPPORTED / project-reported | Selective write with γ=1 preserved a controlled cue through 4,096 positions with bounded state. Must be rerun from committed artifacts. |
| **Autonomous selective write** | SUPPORTED / project-reported | Learned gate reportedly matched supervised/annealed variants on the controlled memory task. |
| **Exact word-occurrence search** | OUT OF SCOPE | Use an inverted index or full-text search. Phase may only add semantic/temporal salience. |
| **Exact evidence admission/routing** | UNSUPPORTED | Direct Phase guidance harmed bounded slots; retention-only guidance was inert; static capacity routing did not beat simpler routers. |
| **Multi-hop evidence traversal** | UNSUPPORTED | Current learned pointer failed held-out compositional generalization. Deterministic joins remain required. |
| **Auxiliary information health** | PROPOSED | Persistence, unresolved recurrence, context shift, and sequence anomaly are the most plausible enterprise targets; dedicated experiment required. |
| **Cross-domain world model** | PROPOSED / unvalidated | Phase may be a temporal-state substrate, but semantics, identity, relation composition, and authority must come from grounded structure. |

---

## 3. Canonical Frozen V2-S Algorithm

The validation target is the frozen V2-S recurrence, not the broader legacy Phase-Quad design. The canonical project-reported recurrence is:

```
S_t = S_{t-1} + B_t (k_t ⊙ v_t)

where:
  S_t  = persistent complex state
  B_t  = selective write gate
  k_t  = phase-aligned key representation
  v_t  = value representation
  ⊙    = elementwise complex binding

Frozen V2-S settings:
  gamma = 1
  omega = 0
  one persistent complex bank
  no C_t correction term
```

Required invariants:

- Linear sequence scan: state updates scale O(N) in sequence length.
- Bounded recurrent state: runtime state size does not grow with N.
- No mandatory exponential decay in the frozen configuration.
- No full N×N attention tensor inside the Phase core.
- Streaming continuation must produce the same result as one-pass processing within numerical tolerance.
- The frozen source hash, configuration hash, and freeze verifier must pass before any experiment runs.

> **Do not evolve the recurrence during capability testing** — Dynamic γ, token-dependent ω, and extra C_t-style correction terms have already produced no gain, catastrophic phase behavior, or inert behavior in project-reported experiments. New capability work must first change representation, supervision, or system boundaries—not the frozen recurrence.

---

## 4. Current Evidence Snapshot

The table below records the project-reported evidence available at the time of this specification. Every row is marked as requiring reproduction from committed code, raw JSON, and frozen configuration before it may be cited externally.

| Evidence ID | Area | Reported result | Evidence class | Action |
| --- | --- | --- | --- | --- |
| **E-01** | Frozen baseline | 98/98 tests; FREEZE OK | Project-reported | Rerun required |
| **E-02** | V2-S distant cue | Perfect or near-perfect decode through N=4,096 with selective writing; approximately 768 B state | Project-reported | Rerun + ≥3 seeds |
| **E-03** | Gate autonomy | Scratch, annealed, and teacher variants reportedly similar | Project-reported | Rerun + gate causal controls |
| **E-04** | Recurrence variants | Dynamic γ no gain; token-dependent ω catastrophic; C_t inert | Project-reported | Preserve as negative result |
| **E-05** | Phase-guided bounded slots | Direct guidance degraded write/read behavior; no-guidance recovered baseline | Project-reported | Preserve as negative result |
| **E-06** | Retention-only guidance | Approximately inert; negligible survival/eviction change | Project-reported | Preserve as negative result |
| **E-07** | Static capacity router | Single-hop simpler COND router matched oracle; Phase matcher worse under pressure; multi-hop static routing failed | Project-reported | Phase routing claim blocked |
| **E-08** | Bounded softmax | 10/10 correctness tests; no N×N tensor | Project-reported | Independent of Phase |
| **E-09** | Iterative pointer pipeline | Downstream accuracy high when pointer correct, but autonomous top-1 and held-out composition failed | Project-reported | Use deterministic joins |
| **E-10** | Auxiliary DHA role | Not yet executed | Proposed | Run T-DHA |
| **E-11** | Cross-domain world model | Not yet executed | Proposed | Run T-WM only after T-DHA |

> **Legacy 10K and "Phase essential" claims** — Legacy pitch/design documents describe 10K controlled retrieval and protected-path ablation claims. These are historical claims, not accepted current evidence, until the exact code path, data, checkpoints, ablation harness, raw JSON, and matched baselines are reproduced under this specification.

---

## 5. Capability Status and Claim Language

| Status | Definition | Permissible claim language |
| --- | --- | --- |
| **VERIFIED** | Reproduced from frozen code with raw artifacts, baselines, causal controls, and pre-registered thresholds. | "Phase demonstrated X under conditions Y." |
| **SUPPORTED** | Positive pilot evidence exists but lacks one or more decisive requirements such as multiple seeds, held-out transfer, or production data. | "Pilot evidence supports X; external validation remains pending." |
| **PROPOSED** | Architecturally plausible and testable, but no qualifying result exists. | "We are testing whether Phase can X." |
| **UNSUPPORTED** | Experiments do not show the claimed benefit, or simpler controls perform as well or better. | "Current evidence does not support X." |
| **FALSIFIED** | A pre-registered claim failed a decisive test or causal control. | "Under the tested design, X did not occur." |
| **OUT OF SCOPE** | The task belongs to deterministic search, schemas, indexes, policy engines, or another component. | "Phase is not used for X." |

Prohibited external claim forms:

- "Phase understands the whole document" without task-level evidence.
- "Phase searches words faster" when the comparator should be an inverted index.
- "Phase is a world model" without held-out-domain structural transfer.
- "Phase improves evidence routing" after static routing and slot-guidance failures.
- "Phase and Quadratic compose" unless the hybrid beats matched non-Phase temporal baselines and passes causal ablations.
- "Infinite memory" as a task capability; γ=1 prevents mandatory decay but does not guarantee unlimited retrievable information.

---

## 6. Architecture Boundaries

The enterprise architecture is valid only when each component has an exclusive responsibility:

| Component | Responsibility | Authority level |
| --- | --- | --- |
| **Text index / database index** | Exact words, phrases, IDs, entity equality, timestamps, versions | Authoritative |
| **Schema + ontology** | Record shape, entity/relation meaning, valid transitions | Authoritative design contract |
| **Evidence ledger** | Exact source records, spans, provenance, access metadata | Authoritative source of truth |
| **Deterministic join engine** | object_id → subject_id joins; tenant and policy filters | Authoritative |
| **Bounded quadratic attention** | Compare a small candidate set; resolve ambiguity, contradiction, version, relevance | Derived, evidence-linked |
| **Frozen Phase V2-S** | Long-stream temporal memory and optional soft signals | Auxiliary only |
| **DHA / information-health engine** | Combine deterministic checks, quadratic evidence features, and optional Phase signals | Policy-governed |
| **External LLM** | Draft, explain, summarize, or answer from the validated packet | Non-authoritative generator |

```
Large document / enterprise stream
        ↓
Exact indexing + schema/ontology normalization
        ↓
Evidence ledger with provenance and deterministic joins
        ↓
Bounded candidate packet
        ↓
Quadratic comparison and evidence-chain scoring
        +
Phase auxiliary temporal state
        ↓
DHA quality status + evidence IDs
        ↓
Validated API packet
        ↓
External LLM
```

> **Critical boundary** — Phase may influence an auxiliary quality score only. It must not silently change evidence IDs, entity joins, authority decisions, provenance, access rights, or consequential factual fields.

---

## 7. Validation Principles and Source Hierarchy

| Principle | Name | Operational requirement |
| --- | --- | --- |
| **P1** | Pre-register the claim | Write the threshold, baselines, and failure interpretation before the run. |
| **P2** | Separate mechanism from task | O(N) recurrence is not proof of retrieval, reasoning, or enterprise value. |
| **P3** | Use matched baselines | Compare against mean pooling, EMA, GRU, conventional linear recurrence, and deterministic features. |
| **P4** | Require causal dependence | Zero, shuffle, reverse, remove relevant segment, and remove irrelevant segment. |
| **P5** | Test held-out structure | Rename identities, hold out relation compositions, templates, and entire domains. |
| **P6** | Preserve negative results | Do not replace failed designs with stronger prose. |
| **P7** | No silent leakage | Training-only labels, oracle paths, or future information must not enter autonomous evaluation. |
| **P8** | Measure cost | Parameter count, latency, peak memory, state bytes, tokens/events processed. |
| **P9** | Artifact-first evidence | Raw JSON and executable tests outrank reports and pitch decks. |

Source hierarchy, highest to lowest confidence:

1. Level A: frozen code + executable tests + raw results + checkpoints + exact environment.
2. Level B: experiment report generated from Level A artifacts.
3. Level C: design specification or implementation prompt.
4. Level D: pitchbook, marketing copy, architecture narrative, or unreferenced summary.

---

## 8. Test-Family Overview

| Test ID | Family | Question | System boundary |
| --- | --- | --- | --- |
| **T-CORE** | Core long-range memory | Can V2-S preserve and retrieve controlled distant state with bounded memory? | Phase-only |
| **T-GATE** | Selective-write autonomy | Does the gate learn when to write without permanent supervision? | Phase-only |
| **T-STAB** | State stability and dilution | How do distractors, state rank, head redundancy, and distance affect recoverability? | Phase-only |
| **T-SEARCH** | Long-document search boundary | Does Phase add semantic/temporal salience beyond exact and embedding search? | Index + Phase |
| **T-DHA** | Auxiliary information health | Does Phase improve persistence, recurrence, shift, or anomaly scoring? | Deterministic + Quad + Phase |
| **T-COMPOSE** | Phase–Quadratic composition | Does late-fused Phase state improve bounded evidence comparison over matched temporal baselines? | Quad + Phase |
| **T-WM** | Cross-domain world-state transfer | Does Phase help recognize structural temporal patterns in an unseen domain? | Ontology + Quad + Phase |
| **T-ENT** | Enterprise shadow pilot | Do gains survive real bounded documents, provenance, abstention, and access controls? | Full bounded system |

> **Required sequencing** — Run T-CORE/T-GATE/T-STAB first. T-SEARCH may run independently. T-DHA must pass before T-COMPOSE is promoted. T-WM is blocked until Phase demonstrates a stable temporal signal and the relational representation passes identity-renaming and held-out composition controls.

---

## 9. Core Long-Range Memory Protocol (T-CORE / T-GATE / T-STAB)

### 9.1 Tasks

- Single distant cue: one relevant key/value appears once; query occurs at controlled distance.
- Multiple cues: several keys/values with interference and repeated keys.
- Update and supersession: old value followed by a newer authoritative value.
- Selective write: relevant events are sparse among dense distractors.
- Streaming equivalence: one-pass and chunked processing must match.

### 9.2 Required distances and pressures

| Dimension | Values |
| --- | --- |
| **Sequence length N** | 256, 1,024, 4,096; optional 8,192 and 16,384 after validity |
| **Relevant-event distance** | 64, 256, 1,024, 4,096 |
| **Distractor ratio** | 1×, 4×, 8×, 16× |
| **Seeds** | 1 validity seed; ≥3 decisive seeds |
| **State budget** | Frozen V2-S state bytes recorded exactly |

### 9.3 Arms

| Arm | Description |
| --- | --- |
| **C0** | Random state control |
| **C1** | Local/current event only |
| **C2** | Frozen V2-S with supervised selective write |
| **C3** | Frozen V2-S with annealed supervision |
| **C4** | Frozen V2-S learned from scratch |
| **C5** | Matched EMA / plain recurrent baseline |
| **C6** | Phase state zeroed at evaluation |
| **C7** | Phase state shuffled across examples |

### 9.4 Metrics and acceptance

Pre-registered pilot acceptance: top-1 cue decode ≥0.95 at N=4,096 for the selective-write task; ≤0.05 absolute degradation from N=256; zeroed/shuffled state must collapse toward chance; chunked and one-pass outputs must agree within numerical tolerance; at least one learned-gate arm must match supervised performance within 0.03.

The phrase "long-range memory validated" is limited to the tested data generator and state budget. It must not be generalized to language understanding, arbitrary documents, or exact enterprise evidence without T-SEARCH/T-DHA/T-ENT.

---

## 10. Long-Document Search and Salience Protocol (T-SEARCH)

> **Boundary under test** — Phase is not expected to beat an inverted index for exact word occurrences. The test asks whether it can add long-range semantic and temporal salience after exact retrieval and embeddings are already available.

### 10.1 Task set

| Task | Definition | Expected role |
| --- | --- | --- |
| **S1 Exact occurrence** | Find every occurrence of an exact word/phrase and return page/offset. | Inverted index should dominate; Phase must not be claimed. |
| **S2 Semantic paraphrase** | Find differently worded passages expressing the same issue. | Embedding/BM25 baseline. |
| **S3 Persistent issue** | Identify an issue introduced early and still active much later. | Phase-plausible. |
| **S4 Recurrence** | Issue appears, seems locally absent, then returns unresolved. | Phase-plausible. |
| **S5 Supersession** | Later amendment changes the active rule. | Phase-plausible with explicit timestamps/versions. |
| **S6 Harmless novelty** | Unusual wording that does not change the underlying state. | False-positive control. |

### 10.2 Arms

- Index only: exact inverted index / full-text search.
- BM25 or lexical ranking.
- Embedding retrieval.
- Index + embedding.
- Index + embedding + mean/EMA temporal pooling.
- Index + embedding + frozen Phase salience.

### 10.3 Metrics

Exact search: recall@all occurrences, offset accuracy, latency, and index size. Semantic tasks: recall@K, precision@K, nDCG, section-level AUROC/AUPRC, false-positive rate on harmless novelty, latency, and incremental memory.

Phase-specific acceptance requires a measurable gain on S3–S5 over the best non-Phase temporal baseline while showing no advantage claim on S1. Relevant-segment removal must reduce the Phase gain; irrelevant-segment removal must not.

---

## 11. Auxiliary Information-Health Protocol (T-DHA)

This is the primary recommended next Phase experiment. Exact joins and provenance are deterministic. Quadratic attention compares a bounded evidence packet. Phase supplies only long-stream auxiliary features to the information-health head.

### 11.1 Targets

| Target | Operational label |
| --- | --- |
| **Persistence** | A condition remains active across distant events. |
| **Unresolved recurrence** | A condition returns after apparent local disappearance without a valid resolution. |
| **Context shift / supersession** | A later event changes the active interpretation or policy. |
| **Sequence anomaly** | An event conflicts with the established temporal trajectory. |

### 11.2 Data contract

```json
{
  "document_id": "DOC-84",
  "section_id": "SEC-12",
  "evidence_id": "E-205",
  "subject_id": "project:delta",
  "relation_id": "org:owned_by",
  "object_id": "team:seven",
  "timestamp": "2026-07-01T10:30:00Z",
  "version": "3.2",
  "status": "active",
  "source_authority": 1.0,
  "source_span": {"page": 17, "start": 218, "end": 304}
}
```

### 11.3 Arms

| Arm | Model |
| --- | --- |
| **A0** | Deterministic metadata only |
| **A1** | Deterministic + bounded quadratic |
| **A2** | Deterministic + Phase |
| **A3** | Deterministic + bounded quadratic + Phase |
| **A4** | A1 + mean pooling |
| **A5** | A1 + exponential moving average |
| **A6** | A1 + matched small GRU |

### 11.4 Phase causal controls

- Normal Phase state.
- State zeroed.
- State shuffled across examples.
- State shuffled across time.
- Sequence reversed.
- Distant relevant segment removed.
- Irrelevant segment removed.

### 11.5 DHA output contract

```json
{
  "persistence_score": 0.81,
  "unresolved_recurrence_score": 0.74,
  "context_shift_score": 0.22,
  "sequence_anomaly_score": 0.18,
  "supporting_evidence_ids": ["E-101", "E-205", "E-388"],
  "quality_status": "REVIEW_REQUIRED",
  "phase_auxiliary_used": true,
  "phase_signal_confidence": 0.69
}
```

> **Authority rule** — Supporting evidence IDs must come from deterministic/quadratic processing. A latent Phase state may change an auxiliary score, but it may never manufacture or replace evidence IDs.

---

## 12. Bounded Quadratic Integration Protocol (T-COMPOSE)

The decisive question is not whether Phase and Quadratic are connected in code. It is whether Phase adds causal, generalizable information after a bounded quadratic evidence comparator already has correct candidates.

```
Deterministic candidate generation
        ↓
Bounded quadratic evidence comparison
        ↓
Quadratic features:
  contradiction, chain completeness, version relevance
        +
Frozen Phase features:
  persistence, recurrence, shift, temporal anomaly
        ↓
Late-fusion DHA head
```

### 12.1 Required comparisons

- Quadratic only versus Quadratic + Phase.
- Quadratic + Phase versus Quadratic + mean pooling.
- Quadratic + Phase versus Quadratic + EMA.
- Quadratic + Phase versus Quadratic + matched GRU.
- Normal Phase versus zeroed/shuffled/reversed Phase.

### 12.2 Acceptance

Phase-specific value requires A3 to improve macro AUROC and macro AUPRC by at least 0.05 over A1, improve relative Brier score by at least 10%, preserve the gain at N=4,096 and on held-out templates/entities, lose the gain under Phase zeroing/shuffling, and beat the best matched non-Phase temporal baseline by at least 0.03 macro AUROC.

If temporal state helps but Phase does not beat EMA/GRU, the correct conclusion is "temporal aggregation is useful; Phase is not specifically justified."

---

## 13. Cross-Domain World-Model Transfer Protocol (T-WM)

> **Vision boundary** — Phase does not know the meaning of Actor, Goal, Authority, Constraint, or Outcome. An ontology and grounding layer define those primitives. Phase may only preserve their temporal trajectory.

### 13.1 Canonical primitives

Recommended common primitives: Actor, Object, State, Goal, Constraint, Authority, Evidence, Action, Transition, Conflict, Resolution, Outcome.

Each domain adapter must map source records to these primitives with source spans and normalized IDs.

```
Hiring:
  Action = MakeOffer
  Constraint = BackgroundCheckIncomplete
  Authority = HRDirector
  Transition = OfferBlocked

Trading:
  Action = PlaceOrder
  Constraint = RiskApprovalIncomplete
  Authority = RiskPolicy
  Transition = OrderBlocked

Shared structure:
  proposed action + unresolved prerequisite → blocked transition
```

### 13.2 Transfer design

- Train on three domains; evaluate on a fourth unseen domain.
- Rename all entity IDs and surface relation names.
- Include structurally equivalent but lexically dissimilar cases.
- Include lexically similar but structurally different negative cases.
- Hold out relation compositions, not only entity pairs.

### 13.3 Arms

| Arm | Description |
| --- | --- |
| **R0** | Quadratic relational model only |
| **R1** | Quadratic + frozen Phase temporal state |
| **R2** | Quadratic + matched GRU temporal state |
| **R3** | Quadratic + deterministic temporal features |
| **R4** | Oracle canonical world-state representation |

### 13.4 World-model acceptance

Phase earns a world-model component claim only if R1 beats R0 and every matched temporal baseline on held-out-domain structural transfer, remains invariant to identity renaming, responds correctly to causal interventions, and predicts unseen transition patterns rather than memorized domain labels.

Even then, the permissible claim is "Phase is a temporal-state layer within a grounded relational world model," not "Phase is the world model."

---

## 14. Causal Controls and Falsification Matrix

| Control | Question | Expected result |
| --- | --- | --- |
| **State zeroing** | Does the head actually use Phase? | Phase gain collapses |
| **Example shuffle** | Is state tied to the correct example? | Phase gain collapses |
| **Time shuffle** | Is temporal order causal? | Temporal targets degrade |
| **Sequence reversal** | Does direction matter? | Supersession/recurrence changes appropriately |
| **Relevant segment removal** | Is the distant evidence load-bearing? | Target-specific score drops |
| **Irrelevant segment removal** | Is the signal selective? | Minimal change |
| **Identity renaming** | Did the model memorize IDs? | Predictions preserved |
| **Relation-name renaming** | Did it memorize English labels? | Structure preserved when ontology mapping preserved |
| **Candidate-order shuffle** | Did position leak? | Predictions invariant after remapping |
| **Future-label randomization** | Is evaluation leak-free? | Autonomous outputs unchanged |
| **Exact-index ablation** | Is Phase pretending to do joins? | Exact join accuracy should collapse; Phase must not replace it |
| **Phase coefficient sweep** | Is late fusion calibrated? | Small bounded contribution; no domination |

> **Falsification rule** — A positive headline metric is rejected if the gain survives state shuffling, disappears only after changing unrelated code paths, depends on oracle labels at evaluation, or collapses under identity renaming or held-out composition.

---

## 15. Metrics and Pre-Registered Acceptance Criteria

| Metric class | Required metrics | Interpretation rule |
| --- | --- | --- |
| **Retrieval** | Top-1, Top-K, MRR, recall@K | Do not substitute AUROC for top-1 routing. |
| **Classification** | AUROC, AUPRC, F1, precision, recall | Report class balance and operating threshold. |
| **Calibration** | Brier score, ECE, reliability plot | Required for DHA/API scores. |
| **Generalization** | Held-out entities, templates, compositions, domains | Primary world-model criterion. |
| **Causality** | Zero/shuffle/remove/reverse deltas | Required for Phase-specific claims. |
| **Efficiency** | Latency, peak RSS/VRAM, state bytes, parameters | Same hardware, threads, batch, sequence length. |
| **Complexity** | Events/tokens processed; attention working set | Prove no N×N tensor. |
| **Enterprise quality** | Provenance retention, abstention, conflict detection | Required before shadow pilot. |

| Gate | Pre-registered threshold |
| --- | --- |
| **T-CORE** | ≥0.95 at N=4,096; zero/shuffle collapse; chunk parity |
| **T-DHA Phase gain** | A3 − A1 ≥0.05 macro AUROC and AUPRC; ≥10% relative Brier improvement |
| **Phase specificity** | A3 − best(A4,A5,A6) ≥0.03 macro AUROC |
| **Long-sequence persistence** | Gain preserved at N=4,096 and longest held-out distance |
| **Held-out generalization** | No material collapse; predefine material as >0.10 absolute unless task specifies stricter |
| **Causal dependence** | Phase zero/shuffle removes most of the gain; irrelevant removal changes <0.02 |
| **World-model transfer** | R1 beats R0 and matched temporal baselines on unseen domain |
| **Enterprise pilot** | Provenance 100%; no unauthorized evidence; abstention works; human review path complete |

---

## 16. Reproducibility and Artifact Requirements

Every executed test family must produce the following:

| Artifact class | Required contents |
| --- | --- |
| **Code identity** | Repository URL/path, branch, commit, clean working tree |
| **Frozen identity** | Source hash, config hash, freeze verifier output |
| **Environment** | Python, PyTorch, OS, CPU/GPU, RAM/VRAM, thread count |
| **Data** | Generator version/hash, split manifest, seed, class balance |
| **Training** | Optimizer, LR, steps, batch, loss weights, checkpoints |
| **Evaluation** | Autonomous path, oracle path clearly separated, no training labels read |
| **Results** | Raw JSON/CSV, summary report, confidence intervals, per-seed rows |
| **Efficiency** | Warm-up protocol, latency repetitions, peak memory method |
| **Tests** | Unit, parity, leakage, causal, freeze, and no-N×N tests |
| **Failure record** | Crashes, excluded runs, early stops, and reasons |

### 16.1 Required result directory

```
experiments/<test_family>/
  README.md
  config/
  dataset.py
  train.py
  evaluate.py
  causal_controls.py
  tests/
  checkpoints/
  results/
    raw_seed_<n>.json
    metrics.csv
    resource_report.json
  FINAL_REPORT.md
  FINAL_RESULTS.json
```

The report must be generated from raw results where practical. Values copied manually into prose must be cross-checked by a test or script.

---

## 17. Claim-to-Evidence Ledger

| Claim ID | Claim | Current status | Required evidence |
| --- | --- | --- | --- |
| **CL-01** | Phase core scans sequences in O(N) | VERIFIED only after complexity/code inspection and no-N×N test | T-CORE |
| **CL-02** | Phase has bounded recurrent state | VERIFIED after state-size audit across N | T-CORE |
| **CL-03** | Phase preserves a controlled distant cue | SUPPORTED; rerun ≥3 seeds | T-CORE |
| **CL-04** | Phase learns selective write autonomously | SUPPORTED; rerun and gate ablation | T-GATE |
| **CL-05** | Phase searches exact word occurrences faster | OUT OF SCOPE / prohibited | T-SEARCH negative control |
| **CL-06** | Phase improves exact evidence routing | UNSUPPORTED under tested designs | Preserve negative results |
| **CL-07** | Phase improves bounded slots | UNSUPPORTED; direct guidance harmed and retention-only was inert | Preserve negative results |
| **CL-08** | Phase detects long-range persistence/recurrence | PROPOSED | T-DHA |
| **CL-09** | Phase detects context shift/supersession | PROPOSED | T-DHA |
| **CL-10** | Phase improves Quadratic information health | PROPOSED | T-COMPOSE |
| **CL-11** | Phase beats matched temporal baselines | PROPOSED | T-COMPOSE |
| **CL-12** | Phase is a world model | UNSUPPORTED / prohibited | T-WM cannot justify this wording |
| **CL-13** | Phase is a temporal-state layer within a world model | PROPOSED | T-WM |
| **CL-14** | Phase can fill authoritative API facts | PROHIBITED | Architecture boundary |
| **CL-15** | Phase can supply auxiliary DHA scores | PROPOSED | T-DHA + enterprise calibration |

---

## 18. Enterprise Pilot and Production Gates

| Gate | Requirement | Failure action |
| --- | --- | --- |
| **G0 Freeze integrity** | Frozen source/config hashes and tests pass | Stop if failed |
| **G1 Mechanism validity** | T-CORE/T-GATE pass | Phase remains research-only if failed |
| **G2 Auxiliary benefit** | T-DHA Phase gain passes pre-registered thresholds | No Phase API field if failed |
| **G3 Phase specificity** | Beats EMA/GRU and causal controls collapse gain | Use simpler temporal baseline if failed |
| **G4 Held-out transfer** | Entities/templates/compositions pass | No enterprise generalization claim if failed |
| **G5 Shadow pilot** | Real bounded domain, provenance, access control, abstention | Read-only pilot only |
| **G6 Production** | Security, audit, monitoring, rollback, human escalation | No autonomous authority |

### 18.1 Production authorization boundary

Even after all Phase gates pass, the authorized role is limited to an auxiliary information-health or salience feature. Deterministic systems remain authoritative for exact facts, identities, permissions, policy thresholds, and evidence provenance.

```json
Permitted production field:
  "phase_auxiliary": {
    "persistence_score": 0.81,
    "context_shift_score": 0.22,
    "confidence": 0.69
  }

Not permitted:
  "approved": true
  "authorized_actor": "Anita"
  "source_of_truth": "PhaseState"
```

---

## 19. Execution Roadmap

| Sequence | Action | Exit artifact |
| --- | --- | --- |
| **Step 1** | Reproduce frozen baseline | Hashes, 98/98, FREEZE OK, environment report |
| **Step 2** | Rerun T-CORE/T-GATE/T-STAB | Confirm or revise current supported claims |
| **Step 3** | Run T-SEARCH boundary tests | Prove exact-search non-role and semantic salience possibility |
| **Step 4** | Run T-DHA validity pilot | A0, A1, A3, A5 at N=256/1,024, one seed |
| **Step 5** | Conditional full T-DHA | All arms, N=4,096, ≥3 seeds only if validity passes |
| **Step 6** | Run T-COMPOSE | Only if Phase has a valid auxiliary signal |
| **Step 7** | Run T-WM | Only after identity-renaming and held-out composition controls pass |
| **Step 8** | Enterprise shadow pilot | One bounded domain; no production authority |

> **Recommended immediate next experiment** — Execute the Phase Auxiliary Information-Health Sensor pilot: deterministic joins + bounded quadratic comparison + late-fused frozen Phase signals for persistence, unresolved recurrence, context shift, and sequence anomaly.

---

## 20. Appendices

### Appendix A — Canonical Enterprise Event Schema

```json
{
  "$schema": "phase-enterprise-event/v1",
  "tenant_id": "tenant:alpha",
  "document_id": "doc:84",
  "section_id": "section:12",
  "evidence_id": "evidence:205",
  "subject": {"type": "Project", "id": "project:delta"},
  "relation": {"type": "owned_by", "ontology_id": "org:owned_by"},
  "object": {"type": "Team", "id": "team:seven"},
  "qualifiers": {
    "valid_from": "2026-07-01",
    "valid_to": null,
    "status": "active"
  },
  "source": {
    "page": 17,
    "start_offset": 218,
    "end_offset": 304,
    "version": "3.2",
    "authority": 1.0
  },
  "access": {
    "classification": "internal",
    "allowed_roles": ["reviewer", "approver"]
  }
}
```

### Appendix B — Standard Experiment Result Schema

```json
{
  "test_id": "T-DHA",
  "arm": "A3",
  "seed": 1,
  "commit": "<git-sha>",
  "source_hash": "<sha256>",
  "config_hash": "<sha256>",
  "dataset_hash": "<sha256>",
  "sequence_length": 4096,
  "metrics": {
    "macro_auroc": 0.0,
    "macro_auprc": 0.0,
    "macro_f1": 0.0,
    "brier": 0.0,
    "ece": 0.0
  },
  "causal_controls": {
    "phase_zero_delta": 0.0,
    "phase_shuffle_delta": 0.0,
    "relevant_remove_delta": 0.0,
    "irrelevant_remove_delta": 0.0
  },
  "resources": {
    "parameters": 0,
    "phase_state_bytes": 0,
    "latency_ms_p50": 0.0,
    "latency_ms_p95": 0.0,
    "peak_rss_mb": 0.0
  },
  "verdict": "PASS|FAIL|INVALID"
}
```

### Appendix C — Minimum Test Manifest

| Test | Assertion |
| --- | --- |
| **test_freeze_integrity** | Source/config hashes, 98 tests, FREEZE OK |
| **test_streaming_equivalence** | Chunked state equals one-pass state |
| **test_state_size_constant** | State bytes independent of N |
| **test_no_full_nxn** | No full attention tensor in Phase or bounded Quad path |
| **test_phase_zero_control** | Phase-specific gain disappears |
| **test_phase_shuffle_control** | Example/time shuffle removes temporal gain |
| **test_relevant_segment_removal** | Target score changes causally |
| **test_irrelevant_segment_removal** | Minimal target-score change |
| **test_identity_renaming** | Structure preserved |
| **test_relation_renaming** | Ontology-grounded structure preserved |
| **test_eval_label_leakage** | Autonomous outputs ignore training-only labels |
| **test_candidate_order_invariance** | Index remapping preserves results |
| **test_provenance_preservation** | Every output evidence ID resolves |
| **test_access_boundary** | Unauthorized evidence never enters packet |
| **test_report_matches_raw_json** | Generated report values equal raw artifacts |

### Appendix D — Current Non-Capabilities

- Exact word occurrence search.
- Authoritative fact extraction without schema/provenance validation.
- Exact entity joins from latent similarity.
- Reliable autonomous next-hop routing across unseen compositions.
- Policy authorization or consequential decision authority.
- General cross-domain world modeling.
- Unlimited retrievable memory merely because γ=1.

### Appendix E — References and Evidence Sources

| Ref. | Source |
| --- | --- |
| **R1** | PHASE_QUAD_LOCAL_ATTENTION_ALGORITHM.md, legacy architecture specification (February 2026). Use as design history; claims require reproduction. |
| **R2** | HYBRID_LLM_FALSIFICATION_ASSESSMENT.md (26 July 2026). Independent falsification-oriented assessment of implemented Phase/Quad claims. |
| **R3** | Reflective_Phase-Quad_Design_document.pdf. Project design context. |
| **R4** | COGNADE PITCHBOOK / COGNADE PITCHBOOK v2. Legacy product and architecture narrative; lower evidence priority than raw experiments. |
| **R5** | Current project-reported Phase diagnostic series: V2-S/V3 recurrence, Phase-guided slots, capacity router, iterative bounded quadratic, pointer repair/scorer verdicts (July 2026). |

> **Final document verdict** — The only current Phase role that is both technically coherent and worth testing next is a bounded auxiliary temporal-information signal. Every stronger claim remains blocked until the corresponding test family passes.

---

*END OF SPECIFICATION*
