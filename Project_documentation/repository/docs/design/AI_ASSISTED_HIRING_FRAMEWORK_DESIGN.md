# AI-Assisted Hiring Framework — Design Specification

*Ugence Labs · The Governed AI Platform · Draft Design · July 2026*

> **What this document is.** A **module design specification** an engineer can
> implement from. It transcribes the AI-Assisted Hiring Framework architecture
> diagram into concrete subsystems, data contracts, decision procedures, and
> governance boundaries. It defines *what each block is, what it consumes, what
> it emits, and how the blocks connect* — not production code.
>
> **What this document is not.** It is not a recruiting-product marketing piece
> and not a hiring policy. It does not claim to predict "the best candidate."
> The system's job is narrower and defensible: **evaluate job-relevant evidence,
> score it against a published rubric with confidence and reason codes, and hand
> a human an auditable recommendation.** The human makes the employment decision.
>
> **Design posture.** Written in the portfolio's falsification-first, governance-
> first style. Where a mechanism is a specification rather than a validated
> result it is labeled **[SPEC]**; where it is an empirical methodology to be run,
> **[METHOD]**; where it is an architectural argument, **[ARGUMENT]**. Every AI
> output in this system is *advisory evidence*, never an autonomous decision —
> this is the load-bearing invariant of the whole design.

---

## Table of contents

1. Abstract, Purpose, Core Claim
2. Falsification first — should this be built as a governed module?
3. The key boundary — AI evaluates evidence, humans decide
4. System overview and layer map
5. Layer 1 — Inputs
6. Layer 2 — Hiring Workflow (end-to-end)
7. Layer 3 — AI Platform Core (five engines)
8. Layer 4 — Evidence & Scoring Data Model (per capability layer)
9. Layer 5 — Human Decision & Governance
10. Layer 6 — Data & Infrastructure
11. Layer 7 — Monitoring & Continuous Improvement
12. Principles enforced — the built-in guardrails
13. Cross-cutting data contracts
14. Interfaces and integration points
15. Implementation plan and module breakdown
16. Validation plan
17. Honest risks and open questions
18. Appendix A — Worked example (single candidate, single layer)
19. Appendix B — Glossary and legend

---

## 1. Abstract, Purpose, Core Claim

### Abstract

This document specifies the **AI-Assisted Hiring Framework**, a governed
evaluation platform that turns candidate assessment into a structured,
auditable pipeline. Candidates produce *work-sample evidence* against a
role-derived rubric; an AI evaluation core extracts evidence, scores it across
**ten capability layers** with a 0–4 rubric and a Low/Medium/High confidence
signal, and attaches reason codes, evidence links, gaps, and stated AI
limitations to every score. A **consistency & fairness monitor** runs
standardization, bias/disparity, data-quality, and drift checks before any
result reaches a human. A **Human Decision & Governance** layer presents the
evidence to accountable humans — a domain expert, hiring manager, and HR
partner — who make and record the actual Advance / Hold / Reject decision with a
job-related rationale. The whole system rests on a **data & infrastructure
layer** (encrypted data lake, feature store, model store, IAM, HRIS/ATS
integration) and is watched by a **monitoring & continuous-improvement layer**
(performance, fairness dashboards, validity/reliability analysis, drift
detection, outcome feedback).

### Purpose

To give an engineering team an implementable definition of every block in the
architecture diagram: its responsibility, inputs, outputs, internal data
structures, the contracts between it and its neighbors, and the guardrails it
must enforce. It also states, explicitly, what the system is *not allowed* to do
— the prohibited-inference guardrail and the human-decision boundary are
first-class requirements, not afterthoughts.

This document specifically aims to:

* enumerate the seven architectural layers and the flow between them (data
  flow, feedback loop, governance/control, AI processing);
* define the **ten capability layers** and the **0–4 scoring rubric + confidence
  model** that together form the Evidence & Scoring Data Model;
* specify the **five AI Platform Core engines** as separable services with typed
  request/response contracts;
* specify the **Human Decision & Governance** surfaces so that AI output is
  presented as reviewable evidence and the final decision is always a recorded
  human act;
* fix the **guardrails** (job-relevant only, no prohibited inferences,
  explainable & auditable, human accountability, fair & inclusive, secure &
  private, accessible) as enforced invariants with concrete enforcement points;
* define the audit, versioning, access-control, and retention obligations that
  make the system legally defensible;
* provide a validation plan (validity, reliability, adverse-impact, drift) and
  an honest register of research risks.

### Core Claim

**A hiring decision is defensible when the evidence behind it is job-relevant,
the scoring is transparent and reproducible, the inference boundary is enforced,
and a named human owns the outcome.** This framework's contribution is not a
smarter ranking model; it is the *governed evaluation substrate* — rubric-bound
scoring, per-score reason codes and evidence links, an architecturally enforced
prohibited-inference guardrail, and an auditable human-decision boundary — that
makes AI-assisted hiring fair, transparent, and legally defensible by
construction rather than by policy promise.

---

## 2. Falsification first — should this be built as a governed module?

The portfolio's discipline is to try to kill a layer before building it.

**2.1 "An LLM can just read résumés and rank candidates."**
It can produce a ranking; it cannot produce a *defensible* one. Ranking from
résumés rewards credential proxies, imports the training corpus's demographic
correlations, and yields no auditable reason a candidate advanced or was
rejected. Under EEOC/Title VII, the EU AI Act (hiring is a high-risk use), and
NYC Local Law 144 (bias-audit + notice), an opaque ranker is a liability, not a
product. The defensible unit is *evidence evaluated against a published,
job-relevant rubric with reason codes* — which is exactly what a raw ranker
does not give you. **Falsification fails.**

**2.2 "ATS vendors already do this."**
Applicant Tracking Systems (Greenhouse, Lever, Workday) are systems of record
and workflow — they store applications, move candidates through stages, and
schedule interviews. They do not extract structured competency evidence from
work samples, do not score against a per-layer rubric with confidence, and do
not enforce a prohibited-inference guardrail. This framework is complementary:
it integrates *with* the ATS/HRIS (Layer 6) and supplies the evaluation and
governance the ATS lacks. **Falsification fails, but narrows the claim:** the
novelty is the *governed evaluation core + human-decision governance*, not
workflow plumbing.

**2.3 "Structured interviews and work-sample tests already exist in I-O
psychology — this is just software around known instruments."**
Correct, and that is the point. Structured, job-relevant assessments are the
*most* validated predictors of job performance in the I-O literature; the
failure mode in practice is inconsistent human application of them. This system
operationalizes validated assessment design (Layer 2 → capability layers) and
enforces *consistency* (Layer 3 fairness monitor) at scale. It is "software
around known-good instruments" — deliberately. The defensibility comes from not
inventing a novel psychometric. **Falsification fails.**

**2.4 "If a human makes the final call, the AI adds nothing."**
The AI adds *structured, consistent, auditable evidence extraction* the human
could not produce at scale or with equal consistency, and it makes the human's
reasoning legible (the human must engage with an Evidence Matrix and layer
scores, not a gut feel). The human boundary is not a weakness to be optimized
away — it is the mechanism that keeps accountability human and the system legal.
**Falsification fails.** The module is worth building **as a governed module**.

---

## 3. The key boundary — AI evaluates evidence, humans decide

> **Key Boundary (from the diagram, verbatim intent):** *AI provides assessments
> and recommendations; humans make the final employment decision.*

This is the system's single most important invariant. It is enforced, not
merely stated:

* **No auto-reject / no auto-advance.** No AI component may transition a
  candidate to a terminal disposition (Reject) or a binding advance (Offer)
  without a recorded human decision. The workflow state machine (§6) rejects any
  disposition write whose `actor_type != HUMAN`.
* **AI outputs are typed as `Recommendation`, never `Decision`.** The data model
  (§13) has two distinct record types. A `Decision` record *requires* a
  `human_actor_id`, a `rationale`, and a link to the `Recommendation` it
  accepted, modified, or overrode.
* **Override is first-class.** Humans may Advance / Hold / Reject against the AI
  recommendation. Overrides are captured with reason (§9.3), fed to monitoring
  (§11), and never suppressed.
* **The boundary is drawn in the diagram as a distinct control edge** (green
  "Governance / Control" arrow) from the AI Platform Core to Human Decision &
  Governance — implemented as a hard permission boundary in IAM (§10.5), not a
  UI convention.

---

## 4. System overview and layer map

The framework is seven layers. Arrows in the diagram carry a type; the design
preserves the type as the contract style between layers.

| # | Layer | Responsibility | Primary edge type in |
|---|-------|----------------|----------------------|
| 1 | **Inputs** | Role context, candidate data, assessment data, external references | Data Flow |
| 2 | **Hiring Workflow (end-to-end)** | The six human-facing stages of the hiring process | Data Flow + Feedback Loop |
| 3 | **AI Platform Core** | Five engines: design → deliver → ingest → evaluate → monitor | AI Processing |
| 4 | **Evidence & Scoring Data Model** | The per-capability-layer scored evidence produced by Layer 3 | AI Processing |
| 5 | **Human Decision & Governance** | Review console, decision panel, rationale, candidate comms, audit | Governance / Control |
| 6 | **Data & Infrastructure** | Data lake, index, feature store, model store, IAM, APIs | Data Flow (foundation) |
| 7 | **Monitoring & Continuous Improvement** | Performance, fairness, validity, drift, outcome feedback | Feedback Loop |

**Edge-type legend (implementation meaning):**

* **Data Flow (solid arrow):** synchronous or batched data movement; typed
  payloads over the internal API bus.
* **Feedback Loop (dashed arrow):** asynchronous signal returned to an upstream
  stage (e.g. hiring outcomes → validity analysis → rubric revision). Never
  carries a decision; only signal.
* **Governance / Control (green arrow):** a permissioned control edge; crosses
  the AI→Human boundary. Subject to IAM and audit.
* **AI Processing (purple arrow):** movement through the AI evaluation pipeline;
  every hop writes to the audit log and attaches reason codes.

The **Hiring Workflow (Layer 2)** is the process view; the **AI Platform Core
(Layer 3)** is the engine that powers stages 3–5 of that workflow. They are one
level in the diagram intentionally: workflow stage *n* is served by core engine
*n* where they correspond (see §7.0 mapping).

---

## 5. Layer 1 — Inputs

Four input families feed the system. Each is a typed ingestion contract with a
provenance stamp and a consent/eligibility flag.

### 5.1 Role & Context
Defines *what the job requires* — the source of truth for the rubric.
Fields: **Job Description, Outcomes, Competencies, Critical Risks, Policies &
Constraints, Legal Requirements.**
* Consumed by the **Role & Assessment Design Engine** (§7.1) to derive the ten
  capability-layer weightings and the score rules.
* `Legal Requirements` and `Policies & Constraints` also compile into the
  **prohibited-inference guardrail** configuration (§12.2) and the accommodation
  policy (§12.7).

### 5.2 Candidate Data
Everything the candidate submits or that describes their submission.
Fields: **Application / Résumé, Certifications, Portfolio, Responses, Work
Products, Interview Data.**
* Ingested through the **Candidate Portal** (§7.2); stored encrypted (§10.1).
* Each item is tagged `job_relevant: bool` at ingestion; non-job-relevant fields
  (e.g. graduation year, address) are **quarantined** from the feature store and
  never reach the evaluation engine (guardrail enforcement point, §12.1).

### 5.3 Assessment Data
The instruments and their results.
Fields: **Work Samples, Scenarios, Interview Responses, Feedback & Revisions.**
* Produced by assessment delivery (§7.2), normalized by ingestion (§7.3).

### 5.4 External References *(Optional & Relevant)*
Fields: **Reference Checks, Public Credentials.**
* Explicitly optional and gated by relevance + consent. Public-credential lookups
  must be *verification* (does this certification exist / is it valid), never
  open-web profiling of the person. This is a hard guardrail line (§12.2).

**Input contract (all families):** every ingested record carries
`{source, timestamp, consent_ref, job_relevant, provenance_hash}` and lands in
the Secure Data Lake (§10.1) before any processing.

---

## 6. Layer 2 — Hiring Workflow (end-to-end)

Six stages. Stages 1–3 and 6 are human/process-led; stages 3–5 are AI-assisted
via the Core (§7). The workflow is a state machine; the dashed feedback edges in
the diagram are the revision loops.

| Stage | Name | What happens | Core engine (§7) |
|-------|------|--------------|------------------|
| 1 | **Role Definition & Planning** | Hiring manager + HR define outcomes, competencies, risks, constraints | — (feeds §7.1) |
| 2 | **Sourcing & Screening** | Candidates enter; eligibility + consent captured | — |
| 3 | **Assessments** | Work Sample · Adaptive Scenario · Structured Interview · Feedback & Revision | §7.1, §7.2 |
| 4 | **AI Evaluation** | Evidence Extraction · Scoring & Analysis | §7.3, §7.4, §7.5 |
| 5 | **Human Review & Decision** | Accountable humans review evidence and decide | Layer 5 |
| 6 | **Offer & Onboarding (Feedback Loop)** | Offer, onboarding, and outcome capture back into monitoring | Layer 7 |

**State machine [SPEC].** States: `PLANNED → SOURCED → ASSESSING → EVALUATED →
IN_REVIEW → {ADVANCED | HOLD | REJECTED} → OFFERED → ONBOARDED`.
Invariants:
* `EVALUATED → IN_REVIEW` is automatic; `IN_REVIEW → {ADVANCED|HOLD|REJECTED}`
  requires a human `Decision` record (§3).
* `Feedback & Revision` (stage 3) allows a candidate to revise a work product
  within policy; each revision is a new evidence version (§13), never an
  overwrite.
* The **dashed feedback edges** connect stage 6 outcomes and stage 5 decisions
  back to stages 1–4 for continuous improvement (Layer 7); they carry signal,
  not identity, wherever aggregation suffices.

---

## 7. Layer 3 — AI Platform Core (five engines)

Five engines, pipelined left-to-right. Each is an independently deployable
service with a typed contract, its own audit stream, and no authority to write a
terminal decision.

**§7.0 Workflow↔engine mapping.** Design Engine ⇄ stage 1/3 setup; Delivery ⇄
stage 3 execution; Ingestion + Evaluation + Fairness Monitor ⇄ stage 4; output
flows to stage 5 (Human Review).

### 7.1 Role & Assessment Design Engine
*"Maps role outcomes to 10 capability layers, creates assessments, rubrics &
score rules."*
* **In:** Role & Context (§5.1).
* **Out:** an `AssessmentBlueprint` = `{layer_weights[10], rubric_rows,
  score_rules, assessment_items[], prohibited_inference_config}`.
* **Behavior:** decomposes the role into the ten capability layers (§8.2),
  assigns per-role weights (a layer may be weighted 0 if not job-relevant),
  authors the 0–4 rubric anchors per layer, and generates assessment items
  (work samples, adaptive scenarios, structured-interview guides). Rubrics are
  **versioned artifacts** (§13) — a candidate is always scored against a pinned
  rubric version.
* **Guardrail:** the blueprint must pass a *job-relevance check* — every rubric
  row must trace to a stated Outcome/Competency in §5.1, or it is rejected.

### 7.2 Assessment Delivery & Candidate Portal
*"Secure delivery of assessments, instructions, accessibility support, candidate
experience."*
* **In:** `AssessmentBlueprint`; candidate identity.
* **Out:** candidate submissions (Candidate Data §5.2, Assessment Data §5.3).
* **Behavior:** renders assessments, enforces time/window rules, provides
  **accessibility accommodations** (screen-reader support, extended time, format
  alternatives — guardrail §12.7), and captures the candidate experience.
* **Guardrail:** accessibility and equal-conditions are enforced here; the portal
  is the *Accessible* principle's enforcement point.

### 7.3 Evidence Ingestion & Normalization
*"Collects submissions in multiple formats, normalizes and indexes evidence
securely."*
* **In:** raw submissions (text, code, documents, audio/video transcripts,
  structured responses).
* **Out:** `NormalizedEvidence[]` — format-agnostic evidence units, each with a
  stable `evidence_id`, content hash, source pointer, and index entry.
* **Behavior:** de-formats, chunks, and indexes evidence into the Metadata &
  Index (§10.2); strips/quarantines non-job-relevant PII (§12.1); associates
  each evidence unit with the candidate and the assessment item.

### 7.4 AI Evaluation Engine
*"Evidence Extraction · Rubric Scoring · Gap Analysis · Confidence Scoring ·
Reason Codes."*
* **In:** `NormalizedEvidence[]`, pinned `AssessmentBlueprint`.
* **Out:** a `LayerScore` per capability layer (§8) → aggregated into a
  `CandidateEvaluation` (§13).
* **Behavior, per layer:**
  1. **Evidence Extraction** — pull the spans of evidence relevant to the layer.
  2. **Rubric Scoring** — assign 0–4 against the layer's rubric anchors.
  3. **Gap Analysis** — identify what evidence is *missing* to reach the next
     level (a gap is a first-class output, not a silent zero).
  4. **Confidence Scoring** — Low / Medium / High, driven by evidence
     sufficiency, consistency across items, and extraction certainty.
  5. **Reason Codes** — machine- and human-readable codes explaining the score,
     each linked to the evidence spans that justify it.
* **Guardrail:** the engine may **only** consume job-relevant evidence and may
  **only** emit scores against published rubric anchors. It is structurally
  incapable of emitting a hire/reject verdict — its output type is `LayerScore`,
  not `Decision`.

### 7.5 Consistency & Fairness Monitor
*"Standardization Checks · Bias & Disparity Detection · Data Quality Checks ·
Drift Monitoring."*
* **In:** `CandidateEvaluation` (and the batch/cohort of evaluations).
* **Out:** a `FairnessReport` attached to the evaluation, plus `flags[]`.
* **Behavior:**
  * **Standardization checks** — every candidate scored against the same pinned
    rubric under equal conditions; deviations flagged.
  * **Bias & disparity detection** — cohort-level statistics (e.g. selection-rate
    parity, four-fifths/adverse-impact screen) on *outcomes vs. protected-class
    aggregates the org lawfully monitors*, computed on aggregates, never used to
    alter an individual's score.
  * **Data quality checks** — flag low-signal or corrupt evidence, extraction
    failures, and out-of-distribution submissions.
  * **Drift monitoring** — detect score-distribution drift over time (feeds
    Layer 7).
* **Guardrail:** this monitor is a **gate** — an evaluation with unresolved
  critical flags is marked `REVIEW_BLOCKED` and surfaced to governance with the
  flag, rather than silently passed to a human as clean.

---

## 8. Layer 4 — Evidence & Scoring Data Model (per capability layer)

This is the heart of the system: the structured artifact every AI score lives
in, produced by §7.4 and checked by §7.5.

### 8.1 The scoring scale and confidence

**Score (evidence sufficiency against rubric):**

| Score | Label | Meaning |
|-------|-------|---------|
| 0 | **No Evidence** | Nothing in the evidence speaks to this layer |
| 1 | **Limited** | Partial or weak evidence |
| 2 | **Meets Minimum** | Meets the role's minimum bar |
| 3 | **Strong** | Clearly exceeds the minimum |
| 4 | **Exceptional** | Best-in-class evidence |

**Confidence (how much the system trusts its own score):** **Low · Medium ·
High** — a function of evidence quantity, cross-item consistency, and extraction
certainty. Low confidence is a signal to the human reviewer that the layer needs
human attention, **not** a reason to lower the score.

### 8.2 The ten capability layers

Every candidate is evaluated across these ten layers (weighted per role by
§7.1). Each is scored 0–4 with confidence, reason codes, and evidence links.

| # | Layer | What it evaluates |
|---|-------|-------------------|
| 1 | **Execution** | Does the candidate get the actual task done, correctly and completely? |
| 2 | **Qualification & Identity** | Verified credentials/qualifications and identity assurance (verification, not profiling) |
| 3 | **Work-Product Structure** | Quality, structure, and craft of the produced work |
| 4 | **Adaptive Cognition** | Handling novelty, ambiguity, and changing conditions (adaptive scenarios) |
| 5 | **Agency & Decision Ownership** | Takes ownership of decisions; acts without needing to be told each step |
| 6 | **Reasoning & Analysis** | Quality of reasoning, analysis, and judgment |
| 7 | **Role Purpose** | Alignment of the work to the role's actual purpose and outcomes |
| 8 | **Reflection & Self-Correction** | Detects own errors and revises (the Feedback & Revision loop, §6 stage 3) |
| 9 | **Professional Coherence** | Consistency, reliability, and professionalism across the body of evidence |
| 10 | **System & Stakeholder Responsibility** | Accounts for the wider system and stakeholders affected by the work |

> These ten layers are the fixed evaluation ontology. Roles vary the *weights*
> and *rubric anchors*, never the layer set — this fixed spine is what makes
> scores comparable across candidates and auditable across roles.

### 8.3 The per-layer record and the guardrail band

Beneath the ten layers, the model carries the audit-critical band shown in the
diagram: **Reason Codes · Evidence Links · Gaps · AI Limitations · Prohibited
Inferences Guardrail (🔒).**

A single `LayerScore` record [SPEC]:

```
LayerScore {
  layer_id:          enum(1..10)
  score:             int(0..4)
  confidence:        enum(LOW, MEDIUM, HIGH)
  reason_codes:      [ReasonCode]        # why this score
  evidence_links:    [EvidenceRef]       # exact spans that justify it
  gaps:              [Gap]               # what's missing to reach next level
  ai_limitations:    [Limitation]        # where the AI is unsure/unable
  rubric_version:    semver              # pinned rubric this was scored against
  model_version:     ref(ModelStore)     # which scoring model produced it
}
```

* **Reason Codes** — every score must carry ≥1 reason code; a score with no
  reason code is invalid and rejected by §7.4's output validator.
* **Evidence Links** — reason codes point at concrete evidence spans; this is
  what makes the score *auditable* rather than asserted.
* **Gaps** — missing evidence is explicit, so a low score reads as "insufficient
  evidence for X" not "candidate is bad."
* **AI Limitations** — the system states where it could not reliably evaluate
  (e.g. "video transcript low quality; Execution confidence LOW").
* **Prohibited Inferences Guardrail (🔒)** — a hard filter (§12.2) that runs on
  every reason code and evidence link: any inference about protected or
  non-job-relevant attributes (age, race, gender, disability, pregnancy,
  national origin, religion, etc., or proxies for them) is blocked and logged. A
  `LayerScore` cannot be emitted if the guardrail trips; it is returned to the
  engine as a violation for correction and audit.

---

## 9. Layer 5 — Human Decision & Governance

Where AI evidence becomes a human decision. Five surfaces, matching the diagram.

### 9.1 Human Review Console
Presents the AI's work as reviewable evidence:
**Evidence Matrix · Layer Scores & Confidence · Gaps & Flags · AI Explanations ·
Comparable Candidates.**
* The **Evidence Matrix** is candidates × ten capability layers, each cell a
  score+confidence that expands to reason codes and linked evidence.
* **Comparable Candidates** shows peers evaluated under the *same rubric version*
  only (apples-to-apples; cross-version comparison is blocked).
* Design requirement: a reviewer cannot reach a decision control without the
  evidence panel having been opened — the UI enforces *engagement with
  evidence*, supporting the Human Accountability principle.

### 9.2 Decision Panel
The accountable humans: **Domain Expert(s) · Hiring Manager · HR Partner.**
* Each decision records *which* humans participated. Panels are role-configurable
  per §5.1 policy.

### 9.3 Decision & Rationale
The recorded decision: **Advance / Hold / Reject · Rationale (Job-Related) ·
Overrides (If Any) · Approval.**
* A `Decision` record (§3, §13) *requires* a job-related rationale and, if it
  diverges from the AI recommendation, an explicit **override** reason.
* Approval implements any required second-signature/segregation-of-duties per
  policy.

### 9.4 Candidate Communication
**Outcome · Feedback (If Applicable) · Appeal / Challenge Process.**
* Candidates receive the outcome and, where policy allows, feedback grounded in
  the gaps (§8.3) — never in prohibited inferences.
* An **appeal/challenge process** lets a candidate contest an evaluation; a
  challenge triggers re-review and is logged (supports Local Law 144-style
  notice/appeal expectations).

### 9.5 Governance & Audit
**Audit Logs · Versioning · Access Control · Retention Policies.** Detailed in
§10.5–§10.6 and §12.

---

## 10. Layer 6 — Data & Infrastructure

The foundation every other layer stands on. Six components, matching the diagram.

* **10.1 Secure Data Lake (Encrypted).** Encrypted-at-rest store of all raw
  inputs and submissions. Encryption keys via IAM/KMS (§10.5). Source of truth
  for provenance.
* **10.2 Metadata & Index (Searchable).** The evidence index (§7.3) — enables
  retrieval of evidence spans for reason codes without re-scanning raw blobs.
* **10.3 Feature Store (Assessment Features).** Job-relevant features derived
  from evidence for scoring. **Enforcement point for §12.1:** only
  `job_relevant=true` features may be materialized here; protected/proxy
  attributes are structurally excluded, not merely unused.
* **10.4 Model Store (Scoring Models).** Versioned scoring/extraction models.
  Every `LayerScore` pins a `model_version` (§8.3) for reproducibility and
  audit; model changes are governed releases, not silent swaps.
* **10.5 Access & Identity (IAM).** Authn/authz and the enforcement of the
  **AI→Human control boundary** (§3): the permission to write a `Decision` is
  granted only to human decision-panel roles; no service principal holds it.
* **10.6 APIs & Integration (HRIS / ATS).** Integration with the org's HR
  Information System and Applicant Tracking System — candidate sync, stage
  updates, offer/onboarding handoff. This is how the framework *complements*
  rather than replaces existing recruiting systems (§2.2).

---

## 11. Layer 7 — Monitoring & Continuous Improvement

The feedback loop that keeps the system valid and fair over time. Five stages,
matching the diagram, connected by the dashed feedback edges back to Layers 1–3.

* **11.1 Performance Monitoring.** System health, latency, throughput, evaluation
  success/failure rates, extraction-error rates.
* **11.2 Fairness & Bias Dashboards.** Ongoing cohort-level disparity monitoring
  (selection rates, adverse-impact ratios) surfaced to governance. Aggregate
  only; never re-scores an individual.
* **11.3 Validity & Reliability Analysis.** [METHOD] The scientific core:
  * *Validity* — do layer scores predict on-the-job outcomes captured at stage 6?
    (criterion validity study, pre-registered.)
  * *Reliability* — inter-rater/inter-run consistency of scores; test-retest on
    equivalent assessment forms.
* **11.4 Drift Detection.** Score-distribution and model-behavior drift over time
  (fed by §7.5); triggers rubric/model review when thresholds trip.
* **11.5 Feedback Loop (Outcomes).** Hiring and performance outcomes flow back to
  §7.1 (rubric revision) and §10.4 (model calibration). **Guardrail:** outcome
  labels used for calibration are themselves screened for bias before they are
  allowed to influence scoring, to avoid laundering biased historical outcomes
  into the rubric.

---

## 12. Principles enforced — the built-in guardrails

The diagram's "Principles Enforced (Built-in Guardrails)" panel. Each is a
*checked invariant* with a named enforcement point, not a value statement.

| Principle | Enforcement point |
|-----------|-------------------|
| **12.1 Job-Relevant Only** | Ingestion quarantine (§5.2) + Feature Store exclusion (§10.3); every rubric row must trace to a stated Outcome/Competency (§7.1). |
| **12.2 No Prohibited Inferences** | The 🔒 guardrail filter on every reason code/evidence link (§8.3); external references limited to verification (§5.4). Trip → block + log, no score emitted. |
| **12.3 Explainable & Auditable** | Every score carries reason codes + evidence links (§8.3); every decision carries rationale (§9.3); everything is logged (§10.5). |
| **12.4 Human Accountability** | The AI→Human boundary (§3); `Decision` requires a human actor (§13); UI forces evidence engagement (§9.1). |
| **12.5 Fair & Inclusive** | Standardization + disparity checks (§7.5); fairness dashboards (§11.2); equal assessment conditions (§7.2). |
| **12.6 Secure & Private** | Encryption at rest (§10.1), IAM (§10.5), consent stamping (§5), retention limits (§10.6 / below). |
| **12.7 Accessible** | Accommodations enforced in the Candidate Portal (§7.2); accommodation never penalized in scoring. |

**Retention & versioning obligation.** Rubrics, models, evaluations, and
decisions are versioned and retained per the role's `Legal Requirements` (§5.1),
with a defined retention window and a right-to-erasure path that preserves the
audit trail's integrity (erase candidate PII, keep the anonymized decision
record required for defensibility).

---

## 13. Cross-cutting data contracts

The four record types that flow across layers. All are immutable, versioned, and
audit-stamped.

```
NormalizedEvidence {
  evidence_id, candidate_id, assessment_item_id,
  content_hash, source_ref, index_ref, job_relevant,
  format, created_at, provenance
}

LayerScore { ...as §8.3... }

CandidateEvaluation {
  evaluation_id, candidate_id, role_id,
  rubric_version, model_version,
  layer_scores: [LayerScore] (len 10),
  weighted_summary,            # NOT a decision — an aggregate view
  fairness_report: FairnessReport,
  status: enum(EVALUATED, REVIEW_BLOCKED),
  created_at
}

Recommendation {               # AI output — advisory only
  recommendation_id, evaluation_id,
  suggested_disposition: enum(ADVANCE, HOLD, REJECT),
  supporting_layers: [layer_id], caveats: [Limitation],
  actor_type: AI
}

Decision {                     # human output — binding
  decision_id, recommendation_id,      # what it responded to
  disposition: enum(ADVANCE, HOLD, REJECT),
  human_actor_id, panel: [actor_id],
  rationale_job_related: text,         # required
  override: Override | null,           # required if != recommendation
  approval: Approval,
  actor_type: HUMAN, created_at
}
```

**The type split `Recommendation` (AI) vs `Decision` (human) is the code-level
embodiment of §3.** A `Decision` with `actor_type != HUMAN` is unrepresentable /
rejected at write time.

---

## 14. Interfaces and integration points

* **Internal API bus [SPEC].** Engines (§7.1–§7.5) communicate over typed
  request/response contracts; each hop emits an audit event. Suggested surface:
  `POST /blueprint`, `POST /ingest`, `POST /evaluate`, `POST /fairness-check`,
  `GET /evaluation/{id}` (governance-scoped).
* **HRIS/ATS (§10.6).** Bi-directional: candidate + stage sync inbound; stage
  transitions, dispositions, offer/onboarding outbound. Adapter pattern per
  vendor (Greenhouse/Lever/Workday), so the core stays vendor-neutral.
* **IAM/KMS (§10.5).** OIDC/SAML for humans; workload identity for services;
  KMS-backed envelope encryption for the data lake.
* **Candidate Portal (§7.2).** External-facing; accessibility-compliant
  (WCAG-level target), consent capture, accommodation requests.
* **Governance/Audit export.** Read-only, tamper-evident export of the audit log
  and decision records for legal/compliance review and bias audits (§11.2).

---

## 15. Implementation plan and module breakdown

Suggested build order — foundation first, boundary early, evaluation last.

* **Milestone 0 — Foundation.** Layer 6 (data lake, index, IAM, feature store,
  model store) + the four data contracts (§13) + audit log. *Nothing scores yet;
  everything is storable, encrypted, versioned, and auditable.*
* **Milestone 1 — Boundary.** The `Recommendation`/`Decision` split (§3, §13),
  the workflow state machine (§6), and the Human Review Console skeleton (§9.1).
  *The human-decision boundary exists before any AI does.*
* **Milestone 2 — Design & Delivery.** Role & Assessment Design Engine (§7.1)
  and Candidate Portal (§7.2) incl. accessibility. *Roles produce blueprints;
  candidates submit evidence.*
* **Milestone 3 — Ingestion.** Evidence Ingestion & Normalization (§7.3) + the
  job-relevance quarantine (§12.1).
* **Milestone 4 — Evaluation.** AI Evaluation Engine (§7.4): extraction, rubric
  scoring, gap analysis, confidence, reason codes, and the 🔒 prohibited-
  inference guardrail (§12.2). *This is the highest-risk module — build it last,
  behind the boundary and the guardrail.*
* **Milestone 5 — Fairness Monitor.** Consistency & Fairness Monitor (§7.5) as a
  gate before human review.
* **Milestone 6 — Governance surfaces.** Decision Panel, Rationale, Candidate
  Communication + appeals (§9.2–§9.4).
* **Milestone 7 — Monitoring.** Layer 7 dashboards + validity/reliability study
  harness (§11).

**Module ↔ diagram-block traceability.** Each milestone above cites the exact
diagram block it implements, so implementation can be reviewed against the
architecture 1:1.

---

## 16. Validation plan

* **16.1 Boundary tests [METHOD].** Assert no code path can write a `Decision`
  with `actor_type=AI`; assert no AI component can transition a candidate to a
  terminal disposition. Fuzz the API bus for boundary violations.
* **16.2 Guardrail tests [METHOD].** Adversarial evidence containing
  protected-attribute signals and proxies; assert the 🔒 filter blocks and logs,
  and that no such signal appears in any reason code or feature.
* **16.3 Scoring reliability [METHOD].** Inter-run and (where applicable)
  inter-rater agreement on a held-out evidence corpus; test-retest on equivalent
  assessment forms. Target and method pre-registered.
* **16.4 Validity study [METHOD].** Criterion-validity: correlate layer scores
  with stage-6 on-the-job outcomes over a cohort; pre-registered, with adverse-
  impact analysis as a co-primary outcome.
* **16.5 Adverse-impact / bias audit [METHOD].** Four-fifths-rule and
  distribution parity across lawfully-monitored aggregates; run before launch and
  on a schedule (Local Law 144 cadence). Published bias-audit artifact.
* **16.6 Accessibility conformance.** Portal audited to the target WCAG level;
  accommodation paths tested end-to-end.
* **16.7 Auditability.** Given any `Decision`, reconstruct the full chain:
  inputs → evidence → layer scores → reason codes → recommendation → human
  rationale — from the audit log alone.

---

## 17. Honest risks and open questions

* **Rubric anchoring is judgment.** The 0–4 anchors per layer are authored by
  humans (§7.1) and can encode the author's bias. Mitigation: anchors trace to
  stated outcomes, are versioned, and are validated against outcomes (§11.3) —
  but this is a governance discipline, not a solved problem.
* **Confidence calibration.** Low/Medium/High must be *calibrated* against actual
  error rates, or it misleads reviewers. Requires a calibration study; until
  then, treat confidence as a coarse triage signal, stated as an AI limitation.
* **Proxy leakage.** Prohibited-inference blocking of explicit attributes is
  tractable; blocking *proxies* (e.g. zip code, extracurriculars, name
  linguistics) is the hard, open part. §12.1's feature quarantine and §16.5's
  adverse-impact monitoring are the defense-in-depth, not a guarantee.
* **Outcome-label bias.** Calibrating on historical hiring/performance outcomes
  risks laundering past bias into the rubric (§11.5). Mitigation: screen outcome
  labels before they influence scoring; prefer structured performance criteria
  over manager ratings where possible.
* **Automation bias in reviewers.** Humans may rubber-stamp AI recommendations,
  hollowing out the boundary. Mitigation: force evidence engagement (§9.1),
  monitor override rates (§11), and surface confidence/gaps prominently — but
  residual risk remains and must be watched.
* **Novel-work evaluation.** Adaptive Cognition (layer 4) and genuinely novel
  work products are the hardest to score reliably; expect Low confidence and
  route to human attention rather than over-claiming.

---

## 18. Appendix A — Worked example (single candidate, single layer)

*Role:* Backend Engineer. *Layer 1 — Execution.* *Assessment:* a work-sample
task (implement and test a rate limiter).

1. **Design (§7.1):** Execution weighted high for this role; rubric anchor for
   score 3 ("Strong") = *"working, tested implementation meeting all stated
   requirements with reasonable edge-case handling."*
2. **Delivery (§7.2):** candidate submits code + tests via the portal (extended
   time accommodation granted; not penalized).
3. **Ingestion (§7.3):** code and test files normalized into evidence units;
   commit metadata containing the candidate's name/email quarantined (§12.1).
4. **Evaluation (§7.4):** extraction pulls the implementation + passing tests;
   rubric scoring → **3 (Strong)**; gap analysis → *"no concurrency stress test →
   short of 4"*; confidence **HIGH** (clear, consistent evidence); reason code
   `EXEC-REQ-MET` + `EXEC-EDGE-PARTIAL`, each linked to specific files/lines.
5. **Fairness monitor (§7.5):** same rubric version as peers, equal conditions →
   no flag.
6. **Human review (§9):** reviewer opens the Evidence Matrix, sees Execution 3
   (HIGH) with linked code, notes the concurrency gap, and — with the other nine
   layers — records **ADVANCE** with a job-related rationale. The AI's
   `Recommendation(ADVANCE)` is *accepted*, and a human `Decision(ADVANCE)` is
   written. Had the human chosen REJECT, an override reason would be required and
   logged.

At every step: job-relevant only, reason-coded, evidence-linked, guardrail-
checked, human-decided.

---

## 19. Appendix B — Glossary and legend

* **Capability Layer** — one of the ten fixed evaluation dimensions (§8.2).
* **Rubric anchor** — the human-authored description of what each 0–4 score means
  for a layer, pinned by version.
* **Reason Code** — a coded, evidence-linked justification for a score.
* **Gap** — explicitly missing evidence needed to reach the next score level.
* **AI Limitation** — a stated boundary of what the AI could reliably evaluate.
* **Prohibited-Inference Guardrail (🔒)** — the hard filter blocking protected /
  non-job-relevant inferences and proxies (§12.2).
* **Recommendation vs Decision** — advisory AI output vs. binding human output
  (§3, §13).

**Edge legend (from the diagram):** solid = Data Flow · dashed = Feedback Loop ·
green = Governance / Control · purple = AI Processing.

**Key boundary (from the diagram):** *AI provides assessments and
recommendations; humans make the final employment decision.*

---

*End of specification. This document is the implementable transcription of the
AI-Assisted Hiring Framework architecture diagram; each numbered section maps to
a labeled block in that diagram, and each guardrail names its enforcement point
so the design can be reviewed and built against the architecture 1:1.*
