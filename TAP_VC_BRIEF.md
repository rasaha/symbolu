# Truth Assurance Platform (TAP) — VC Brief

**Ugence Labs | Assertion Governance for Enterprise AI**
*The independent authority that determines whether an AI-generated assertion is sufficiently supported before it is delivered.*
*Version 2.0.0 — July 2026 (external / evidence-based) · Category: Enterprise AI Assurance · Status: emerging capability*

> **Product family.** TAP is the **assertion-side** control in the **AI Control Plane** of the Ugence Labs
> platform (canonical taxonomy in `UGENCE_PLATFORM_OVERVIEW.md`). It is the analogue of **ActionGate** (see
> `ACTIONGATE_VC_BRIEF.md`): **ActionGate governs what an AI *does*; TAP governs what an AI *says*; ACP
> decides whether an authorized action is operationally safe now.** This brief is written to be defensible
> line-by-line from the repository. Every quantitative statement corresponds to a committed evaluation
> artifact; the maturity and limitations are stated as plainly as the results.

---

## 1. Executive Summary

Enterprises can now generate fluent AI answers. They still cannot **independently prove** that a given
answer was supported before it reached a user, a customer, or a regulator. Today that judgment is usually
made by the same model that produced the answer — the system grading its own work.

**TAP is an external, model-independent assertion-governance layer.** It evaluates a *completed* response
and returns one of three outcomes — **DELIVER**, **QUALIFY**, or **ABSTAIN** — with a replayable record of
why. It does not generate text; it governs whether text may leave the system.

The program behind TAP is falsification-first: a sequence of preregistered, hash-pinned studies whose most
valuable outputs are **negative results and rejected complexity**. Those studies establish the *mechanism*
and the *architecture* of assertion governance on synthetic corpora. They do **not** yet establish
production efficacy, human agreement, or commercial ROI — and this document does not claim they do. The
next value-creating step is a bounded enterprise shadow deployment on real data. The investment is in the
**trust-and-governance layer** that makes consequential enterprise AI admissible in the first place.

---

## 2. The Enterprise Problem

In consequential workflows — regulated reporting, compliance drafting, financial analysis, clinical
information, customer-facing communications — the limiting question is no longer *"can the model answer?"*
It is:

> *Can the enterprise independently determine, and later prove, that a delivered assertion was supported —
> qualified when uncertain, or withheld when evidence was insufficient?*

An unsupported statement presented as fact is not a productivity issue; it is an admissibility issue. It
can be operationally, contractually, or legally unacceptable regardless of how rarely it occurs. Enterprises
need a control that sits **outside** the generator and answers that question with an auditable record — not
a confidence number produced by the generator itself.

---

## 3. Why Current AI Architecture Stops Short

Foundation models, retrieval, and agent frameworks have advanced **generation** and **evidence access**.
None of them provides a **model-independent enterprise authority over assertions** at the delivery boundary.
The recurring structural weakness is self-assessment: the system that wrote the answer is trusted to certify
the answer.

**Generation and governance are different functions and belong to different authorities:**

- **Foundation models generate.** They produce fluent, plausible text; fluency is not support.
- **TAP governs delivery.** It decides, independently of the generator, whether the completed assertion may
  be delivered as-is, must be qualified, or must be withheld.

Keeping these separate is the point. A generator asked to police itself has no independent standard to
police against.

---

## 4. What TAP Is

TAP is an external assertion-governance layer that inspects a completed response, decomposes it **without
altering its meaning**, checks each claim against evidence, and applies a risk-aware delivery decision.

```
   User request
        │
        ▼
   LLM / agent / application  ── generates a completed response (any provider)
        │
        ▼
   ┌──────────────────────────── TAP ────────────────────────────┐
   │  ClaimIntegrity   decompose safely (preservation-first)       │
   │  ScopeIntegrity   gated handling of exception/scope spans      │
   │  EvidenceAssurance support / contradiction / staleness / gaps  │
   │  AssertionGate    risk-aware delivery decision                 │
   └──────────────────────────────────────────────────────────────┘
        │
        ▼
   DELIVER · QUALIFY · ABSTAIN   ── with a replayable audit record
        │
        ▼
   Enterprise workflow
```

Its founding design principle is not an assertion of ambition; it is the direct conclusion of a completed
study (Section 6):

> **Evidence assurance is trustworthy only when semantic scope is preserved before verification begins.**

---

## 5. Why TAP Is Different

TAP defines a **category — Assertion Governance / Evidence-Grounded Delivery** — rather than competing
inside an existing one. The adjacent technologies are **complementary inputs, not substitutes**:

| Adjacent technology | What it does well | Why it does not close the gap |
| --- | --- | --- |
| Prompt engineering | Shapes generation | Improves the answer; does not independently certify it |
| RAG / retrieval | Supplies evidence to the generator | Better inputs, still self-graded output |
| Agent frameworks | Orchestrate multi-step work | Produce more assertions to govern, not governance |
| Model confidence | A generation-side signal | The generator scoring itself — the core weakness |
| Moderation | Blocks harmful/abusive content | Orthogonal to *evidential support* |
| Guardrails | Filter prompts/outputs by rules | Pattern rules, not claim-level evidence evaluation |
| LLM self-evaluation | The model critiques itself | Not an independent authority |

TAP consumes several of these as signals and adds what none provides: **external, claim-level,
scope-preserving, evidence-grounded delivery decisions with a replayable audit trail, independent of the
model, provider, or framework that produced the text.**

---

## 6. Technical Evidence

**Read this whole section as one statement.** Every result is from our own repository, on **synthetic,
self-authored, deterministic** corpora with preregistered, hash-pinned success/kill criteria. There is
**no human/inter-annotator validation, no real-customer data, and no production-efficacy result** in TAP
today. What follows is *architectural and mechanism-level* evidence; the exact rates are construction-bounded
and are labelled as such in each study. The discipline itself is the signal: **the program repeatedly removed
complexity that did not improve the safety outcome.**

### 6a. Architectural findings (what the studies established about the problem)

- **Decomposition is a real, downstream-invisible failure surface.** When negation, numeric limits,
  exceptions, or population scope are dropped as a response is broken into claims, the downstream evidence
  check faithfully evaluates the *altered* claim — because it cannot see the original. This "no-tell"
  property is why assertion governance must **preserve semantic scope before verification**, not after.
- **The delivery decision is risk-concentrated.** Governance value is largest on high-risk assertions;
  low-risk supported content should pass without unnecessary qualification.
- **Correlated/silent failure is a real, bounded limit.** When grounding and entailment fail *together*,
  no evidence-composition tested can see it. TAP is therefore positioned as **defense-in-depth with a
  human/external-verification route for the no-tell residual — never as a sole safety layer.**

### 6b. Experimental findings (mechanism-level, synthetic, preregistered)

- **ClaimIntegrity** — corpus `ci_corpus_v1` (832 examples, 1,144 gold claims). *How* text is decomposed
  moves the safety endpoint by an order of magnitude: triple/parser extraction (OpenIE/SPO) produced
  **0.864** unsafe delivery; **preservation-first** sentence splitting produced **0.068**, identical across
  every risk tier.
- **ScopeIntegrity** — a small gated hybrid (≈4 pattern rules) reduced ClaimIntegrity's residual on the
  *general* corpus from **0.068 → 0.000** with no rise in false-rejection; **102 tests pass**. The study
  itself flags that *ungated* variants are catastrophic on the general corpus (**0.218–0.472**), so the
  claim rests on the un-rigged corpus, not a flattering one.
- **EvidenceAssurance** — corpus `ea_corpus_v1`. The reference stack drove **correlated-failure escape to
  0.000** on the modeled trap where every signal-only baseline and a learned comparator escape **0.67–1.00**;
  its residual false-block (**0.114**) is noise-floor, not structural. Its own shipped disclosure records the
  ceiling: a **no-tell** correlated failure (aligned passage, fabricated provenance) escapes **1.000** — a
  property of *any* metadata-based method, routed to human/external verification, never hidden.
- **AssertionGate** — corpus `age_corpus_v1`. No single signal suffices (agreement: confidence **0.31**,
  grounding **0.38**; unsupported-escape up to **1.00**). A risk-aware composition reaches **1.00 agreement
  with 0.00 unsupported-escape** on this corpus.

### 6c. Rejected ideas (why this is a strength)

The program declined to ship complexity it could not justify — the behavior a diligence team should want:

- **A heavyweight decomposition engine was not adopted.** A 15-probe component *tied* a 2-probe
  preservation-first splitter on the primary safety endpoint (**0.068 = 0.068**); its only distinct benefit
  was reference resolution (a secondary endpoint, **0.091 → 0.000**). The retained design is the *minimal*
  one: preservation-first splitting + reference resolution, with per-dimension checkers kept only as an
  **audit of untrusted extractors**.
- **A bespoke assertion-scoring engine was not adopted.** A trivial grounding-plus-entailment-plus-risk
  rule reproduced the ground truth and **strictly dominated** the dedicated engine (better on 6 items, worse
  on 0). Verdict: a **thin, risk-aware composition scoped to high-risk domains — not a novel engine.**
- **Aggressive/triple decomposition was prohibited**, being the demonstrated source of the 0.864 failure.

### 6d. Current limitations (stated, not hidden)

Synthetic, self-authored, deterministic corpora; "LLMs"/parsers in the studies are **deterministic local
stand-ins, labelled as simulated**. No human/inter-annotator agreement. No real-customer data. No production
integration or enforcement. The **Truth Assurance Pipeline** specification (`docs/truth_assurance_pipeline/`)
is an **architectural framework** that *"makes no empirical performance claims"*; its per-layer experiments
each pass their preregistered gates but carry the verdict **`PASS_WITH_LIMITED_CLAIM`** (two disclose they
are development, not blind-holdout, evaluations). The claim-validation prototype records its own verdict:
*"perfect scores are by construction … production deployment: NO."*

---

## 7. Product Positioning

TAP is **not** a hallucination detector, a fact-checker, a guardrail, a moderation layer, or an
action-authorization system. It is the **independent delivery authority** for AI assertions. Its
differentiation is the *combination*, not any single part: external governance · claim-level evidence
evaluation · **semantic-scope preservation** · explicit qualify/abstain outcomes · replayable provenance ·
and model/framework independence. Within the platform it is the assertion-side peer of ActionGate (actions)
and ACP (operational safety), keeping generation, assertion, action, and safety under distinct authorities.

---

## 8. Commercial Opportunity

TAP's economic logic is **deployment enablement**, not productivity. It allows enterprises to use AI in
workflows where **unsupported output is operationally, contractually, or legally inadmissible** — and where,
without an independent assurance boundary, AI cannot be deployed at all.

Four value paths, none of which requires a productivity claim:
- **Admissibility** — turn "cannot deploy AI here" into "can deploy under governed delivery."
- **Risk reduction** — fewer unsupported assertions reaching users or downstream decisions.
- **Review efficiency** — concentrate scarce human review on **indeterminate / high-risk** claims (the
  ABSTAIN and QUALIFY paths), not every response.
- **Platform leverage** — one assurance layer across many models, providers, and agent frameworks.

Highest-value environments: financial services, healthcare & life sciences, legal & compliance, insurance,
government/regulated industries, enterprise knowledge systems, and agent-generated reports. *ROI is
customer-specific and is not yet quantified; this brief makes no ROI claim.*

---

## 9. Competitive Landscape

| Category | Typical focus | TAP's distinct position |
| --- | --- | --- |
| Retrieval / RAG platforms | Better evidence *into* generation | Governs the *completed* assertion, after generation |
| Guardrail / moderation tools | Prompt/output filtering, policy strings | Claim-level evidence support with qualify/abstain + audit |
| Fact-checking / verification | Binary true/false on a claim | Scope-preserving decomposition; qualification when evidence is narrow |
| Eval / observability platforms | Offline benchmarking, monitoring | Runtime, per-assertion delivery decision at the boundary |
| Model-native confidence | Generator self-scoring | Independent authority — the generator does not certify itself |
| Action governance (ActionGate) | What the AI *does* | What the AI *says* — the assertion-side analogue |

The defensible position is category ownership at the **delivery boundary**, integrated with action
governance and operational safety — not a point tool inside any single category above.

---

## 10. Current Maturity

An explicit ladder — no rung is claimed beyond the evidence:

| Dimension | Status |
| --- | --- |
| Architecture | **Specified** (layered pipeline; typed interfaces; provenance/confidence/abstention models) |
| Mechanisms | **Prototyped** (ClaimIntegrity, ScopeIntegrity, EvidenceAssurance, AssertionGate as reference components) |
| Synthetic evaluation | **Completed** (preregistered, hash-pinned, falsification-first) |
| Human evaluation | **Pending** (no inter-annotator or expert-comparison study yet) |
| External validation | **Pending** (no third-party or real-customer data) |
| Production deployment | **Not yet** (no enforcement, no production integration) |
| Commercial ROI | **Not yet measured** |

---

## 11. Next Validation Milestone

The next value-creating step is **not** broader feature development. It is **one bounded enterprise shadow
deployment** on real data:

1. one domain, one claim class, customer-approved evidence sources;
2. TAP runs in **shadow mode** (decides, never enforces);
3. TAP decisions are compared against **expert reviewers**;
4. success is judged against **preregistered acceptance thresholds** — unsupported-delivery rate,
   qualification precision, abstention burden, latency/cost, and reviewer agreement;
5. expand only after threshold calibration.

This single milestone is what converts *architectural evidence* into *external efficacy evidence*, and it is
the specific use of investment.

---

## 12. Investment Thesis

As enterprises move from AI experimentation to consequential deployment, the scarce layer is not another
model — it is **enterprise trust infrastructure**: an independent authority that determines whether an
AI-generated assertion may be delivered, under what qualification, with what evidence, and with what audit
trail. That authority is what makes AI **admissible** in regulated and high-consequence work.

TAP is the assertion-governance layer of that infrastructure, complementing action governance (ActionGate)
and operational safety (ACP). Its current value is **architectural and strategic, evidenced by disciplined
falsification-first research that removed complexity wherever it failed to improve the outcome** — and it is
explicitly **not** yet commercially proven. The opportunity is to own the independent assertion authority
for enterprise AI as that authority becomes a deployment prerequisite.

---

## Honesty Anchor — What We Know / Believe / Have Yet to Prove

**What we know (evidenced in the repository).** Decomposition is a downstream-invisible failure surface,
and *how* you decompose moves the synthetic safety endpoint by an order of magnitude (OpenIE 0.864 vs
preservation-first 0.068). Preservation-first splitting plus reference resolution is the minimal sufficient
decomposer; heavyweight alternatives did not beat it and were rejected. Correlated/silent ("no-tell")
failure is a real limit that no evidence-composition tested can catch (disclosed ceiling escape = 1.000),
so governance must be defense-in-depth with a human/external route. The delivery decision is risk-concentrated
and reduces to a thin risk-aware composition on the studied corpora.

**What we believe (reasoned, not yet proven).** These mechanism-level results will *direction­ally* transfer
to real enterprise text; the architecture (preserve scope → check evidence → risk-aware deliver/qualify/
abstain, under audit) is the right decomposition of the problem; and an independent assertion-governance
boundary is becoming a prerequisite for regulated AI deployment.

**What we have yet to prove.** Production efficacy on real data; human/expert agreement; external and
third-party validation; calibrated cross-domain operation; latency/cost within enterprise bounds; and
commercial ROI. None of these is claimed today. The bounded shadow deployment in Section 11 is the honest
path to establishing them.

---

*Contact: Rakesh Mohan — Ugence Labs*
*Repo: `rasaha/symbolu` · Components: `claim_integrity/` (ClaimIntegrity) · `scope_integrity/` (ScopeIntegrity) · `evidence_assurance/` (EvidenceAssurance) · `assertion_governance/` + `assertion_gate_robustness/` (AssertionGate) · `relationship_claim_validation/` (claim-validation prototype) · `truth_assurance_pipeline/` (TAP architecture + E1–E5 layer studies)*
*Status: emerging capability · architecture specified · falsification-first synthetic studies complete · human validation NONE · real-data / external / production efficacy NOT established · companion: `TAP_INVESTOR_APPENDIX.md`*
