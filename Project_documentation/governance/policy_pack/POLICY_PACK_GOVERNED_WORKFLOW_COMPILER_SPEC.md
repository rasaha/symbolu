# Policy-Pack → Governed Workflow Compiler — Design Specification

**Ugence Labs | Ugence Decision Governance**
*A compiler that turns a reviewed governance policy pack into an independently testable, deployable, auditable governed workflow — with no manual workflow programming.*
*Version 0.1 (design spec) — August 2026 — Status: DESIGN / pre-implementation*

> **Terminology note — Ugence Decision Governance (2026-08-02).** Per
> [`docs/architecture/ADR_UGENCE_DECISION_GOVERNANCE_TERMINOLOGY_AND_BOUNDARIES.md`](docs/architecture/ADR_UGENCE_DECISION_GOVERNANCE_TERMINOLOGY_AND_BOUNDARIES.md):
> the canonical **umbrella** is **Ugence Decision Governance**. This spec composes existing
> bounded capabilities — **TAP**, **Decision Authority** (`decision_governance` package, name
> unchanged), **ActionGate**, **ACP**, **StoryGraph**, and **Model Selection** (a distinct
> capability, separate from Hybrid LLM). The compiler is a **product/tooling composition over
> capability public contracts**, not a new authority and not a copy of any engine. Any
> orchestration it emits runs on the **optional, bypassable** orchestrator / AI Control Plane;
> a single-capability deployment must not require them. Documentation-only; nothing is renamed.

---

## 0. Scope of this spec — "only partly"

The source idea spans three things: (a) an argument about how a policy-pack library differs
from training an AI model on public data, (b) a competitive-landscape read of adjacent
products (Appian, Pega, UiPath, Copilot Studio, Workato, ServiceNow), and (c) a concrete
system — a **Policy-Pack → Governed Workflow Compiler**.

**This document specifies only part (c).** Parts (a) and (b) are motivation and are compressed
into §1 and Appendix A; they are deliberately *not* elaborated here, because they are strategy
narrative, not design. Where this spec references the AI-training analogy at all, it does so to
fix one architectural decision (§7): learned models stay **advisory**; enforcement stays
**deterministic**. Everything else about the analogy and the market is out of scope.

What *is* in scope: the policy-pack artifact (its object model), the five-stage compiler, the
assurance it must generate, the human-approval gate, and how the compiled output maps onto
capabilities that already exist in this repository. This is a **[SPEC]** — measurable structure
and procedure — not production code and not a proof that the compiler is feasible today. Section
1 tries to kill it first.

---

## Table of contents

1. Falsification first — does this compiler need to exist?
2. Positioning — what the compiler is, in one sentence
3. The policy-pack artifact — object model
4. The five compilation stages
5. Compilation target — mapping to existing capabilities
6. Assurance generation — the tests the compiler must emit
7. Advisory ML vs. deterministic enforcement (the one inherited constraint)
8. Human approval and deterministic release
9. Interfaces, invariants, and failure modes
10. What this spec does **not** cover
- Appendix A — Why a policy pack is not public-data model training (compressed)
- Appendix B — Worked example: hiring-recommendation policy pack

---

## 1. Falsification first — does this compiler need to exist?

Written in the portfolio's falsification-first posture: state the strongest reasons this
layer should **not** be built, then check whether they hold.

**F1. "Existing tools already generate workflows from documents and natural language."**
True, and it is the strongest objection. Appian Composer, Pega Blueprint, UiPath Autopilot,
Copilot Studio, and Workato all turn descriptions or documents into working automation. The
falsifiable difference is not *"can it generate a workflow"* — they can — but *"does the output
carry an independently checkable governance interpretation"*: separated authority, required
evidence, exception/override semantics, exact-action constraints, sequence-risk checks, an
audit schema, and replay tests, all derived from the policy and **regenerable and diffable**
from it. If a competitor's generator emits those seven artifacts from a policy and re-derives
them deterministically on policy change, this layer is redundant. Per their published
capabilities (Appendix A), none does; that conclusion is an inference from documented behavior,
not a claim about undisclosed products.

**F2. "The hard part isn't compilation, it's the connectors and field mappings — and those are
manual anyway."** Partly true, and it bounds the claim. Someone must still establish system
identity, credentials, schema mappings, which field is authoritative, document precedence,
override approvers, block-vs-escalate rules, approval validity windows, and system-disagreement
behavior (source idea, "'No coding' does not mean no engineering"). The compiler does **not**
remove this work; it removes *manual workflow programming* and forces the mappings to be named,
typed, and test-covered. The honest target is **"no manual workflow programming; experts review
and approve machine-generated governance,"** not "zero humans."

**F3. "A deterministic compiler can't handle the ambiguity in real policy text."** This is why
extraction (Stage 2) produces *proposed* structured objects that a human approves (Stage 5), and
why the learned/NLP components are confined to *proposing* — never enforcing (§7). Ambiguity is
resolved at review time and frozen into the pack, not resolved at runtime by a model.

**F4. "If the enforcement modules already exist, the compiler is just glue."** The glue is the
product. The value is not re-implementing TAP/Decision Authority/ActionGate/ACP — those exist —
but **deriving, from one reviewed policy, a wiring across them plus the assurance suite that
proves the wiring matches the policy**, and keeping that derivation reproducible. Glue that is
generated, tested, replayable, and diffable against a policy is not a commodity.

**Verdict:** F1 and F4 define the differentiator (regenerable governance interpretation +
assurance, not workflow generation); F2 and F3 bound the claim (no manual workflow programming,
not zero humans; propose-then-approve, never learned enforcement). The layer survives its own
falsification **as a specification**. Whether it is *buildable to production quality today* is
an open empirical question this spec does not settle.

---

## 2. Positioning — what the compiler is, in one sentence

> **The Policy-Pack → Governed Workflow Compiler takes a reviewed governance policy pack and
> emits a governed workflow — evidence collectors, authority checks, decision gates, exception
> and override branches, action constraints, sequence-risk checks, an audit schema, and a full
> synthetic/replay test suite — wired across existing Ugence capabilities, gated on human
> approval, and enforced deterministically.**

Contrast with the adjacent market (compressed; full read in Appendix A):

```
Today's builders:   "Describe the workflow you want"  →  AI generates workflow steps
This compiler:      "Provide governance intent + policy + authority model + systems"
                        → AI derives the governed workflow
                        → generates controls, tests, evidence requirements
                        → human approves the compiled pack
                        → deterministic modules enforce it
```

The distinction is **workflow generation vs. governance compilation**: the second commits to a
policy interpretation that is separately testable and re-derivable, not just an executable graph.

---

## 3. The policy-pack artifact — object model

A **policy pack** is the compiler's input and its versioned unit of review. It is an executable
governance playbook, not a prose document. **[SPEC]** It is a structured artifact composed of the
following object types. Each object is typed, addressable, and carries provenance back to the
source it was extracted from.

| # | Object | Purpose | Compiles primarily to |
|---:|---|---|---|
| 1 | **Decision rule** | When a recommendation may become binding | Decision Authority gate |
| 2 | **Required evidence** | Evidence fields that must be present/valid | Evidence collectors + TAP admissibility |
| 3 | **Authority requirement** | Who holds authority for this action type | Decision Authority authority check |
| 4 | **Approval path** | Ordered approvals, segregation of duties | Decision gate sequence |
| 5 | **Prohibited condition** | Conditions that must hard-block | Block guard (fail-closed) |
| 6 | **Exception handling** | Named exceptions and their required behavior | Exception branch |
| 7 | **Override rule** | Who may override, with what justification/expiry | Override workflow |
| 8 | **Action constraint** | Bounds on the exact action (range, digest, once-only) | ActionGate exact-action authorization |
| 9 | **Sequence-risk pattern** | Linked-event patterns that raise collective risk | StoryGraph advisory check |
| 10 | **Legitimate counterexample** | Benign cases that resemble prohibited behavior | Negative test (must-allow) |
| 11 | **Connector mapping** | Policy concept → concrete enterprise system field | Connector configuration |
| 12 | **Test scenario** | Named positive/negative case with expected outcome | Synthetic test |
| 13 | **Audit requirement** | What must be recorded to reconstruct the decision | Audit schema fields |
| 14 | **Replay case** | A captured decision that must reproduce on re-run | Replay test |
| 15 | **Expected outcome** | The asserted result for a scenario/replay | Test oracle |

**Invariants on the artifact:**

- **Provenance.** Every object cites its source (policy clause, regulation, incident report,
  authority matrix, API schema). Objects with no source are flagged for review, never silently
  admitted.
- **Referential completeness.** Every `Action constraint` referencing an authority must resolve
  to an `Authority requirement`; every `Exception`/`Override` must name the `Decision rule` it
  modifies. Dangling references fail compilation.
- **Determinism of evidence.** `Required evidence` must map (via `Connector mapping`) to a field
  the compiler can mark **authoritative**; a policy concept with no authoritative field is a
  compile-time gap, surfaced to the reviewer.
- **Versioned + diffable.** A pack is content-addressed; two packs produce a structural diff at
  the object level, so a policy change shows exactly which gates/tests change.

---

## 4. The five compilation stages

**[SPEC]** The compiler is a five-stage pipeline. Stages 1–2 are *proposal* (may use NLP/ML,
always human-reviewable). Stages 3–4 are *deterministic synthesis*. Stage 5 is the human gate
and deterministic release (§8). No stage after 2 uses a learned model to make an enforcement
decision (§7).

**Stage 1 — Policy ingestion.**
Read source material: policies, regulations, process documents, authority matrices, API/connector
schemas, connector metadata, and prior incident reports. Output: a normalized corpus with
per-source provenance handles. *Nothing is interpreted yet — only ingested and addressed.*

**Stage 2 — Governance extraction.**
Extract the structured objects of §3 (rule, evidence, authority, exception, override, action
restriction, audit obligation, temporal condition, …) from the corpus, each linked to its source.
This is the one stage where document→structure inference lives. Output is **proposed** and enters
review; low-confidence or unsourced extractions are flagged, not admitted. Conflicts (two sources
disagree; document precedence unclear) are raised as review items, not silently resolved.

**Stage 3 — Workflow synthesis.**
Deterministically generate the governed workflow graph from the *approved* objects, using **only
the capabilities the policy requires**. The canonical chain is:

```
TAP  →  Decision Authority  →  ActionGate  →  ACP  →  execution
        (with StoryGraph as an advisory sequence-risk input)
```

A pack that only governs "may this recommendation become binding" emits just TAP + Decision
Authority; a pack that also governs an exact action adds ActionGate; one governing commit-time
operational safety adds ACP; one with linked-event risk adds StoryGraph. **No module is included
that the policy does not require** — this keeps a single-capability deployment free of the
optional orchestrator/AI Control Plane.

**Stage 4 — Assurance generation.**
Automatically emit the test suite (§6): positive, negative, missing-evidence, authority-conflict,
exception, override, replay, and legitimate-counterexample tests, each bound to an
`Expected outcome`. Assurance is generated *from the same approved objects* as the workflow, so
the tests and the workflow cannot drift from each other silently.

**Stage 5 — Human approval and deterministic release.**
An authorized reviewer approves the compiled pack (§8). On approval, the compiler emits a
**deployment package**: the workflow graph, the audit schema, the connector configuration, and
the frozen test suite, all versioned to the approved pack's content hash. Production enforcement
is deterministic and versioned; re-running the same pack reproduces the same package.

---

## 5. Compilation target — mapping to existing capabilities

The compiler does **not** implement enforcement. It targets the public contracts of capabilities
that already exist in this repository. This table is the authoritative object→module mapping; it
respects the authority boundaries fixed in the terminology audit (coordination never transfers
authority; each module owns one function).

| Compiled artifact | Capability (owner of the authority) | Repo location (implementation alias) |
|---|---|---|
| Evidence collectors + assertion admissibility | **TAP** | `tap_provider/` |
| Authority checks, decision gates, segregation of duties, override workflow, immutable decision record | **Decision Authority** | `decision_governance/` (frozen kernel; name unchanged) |
| Exact-action authorization, action constraints (range/digest/once-only) | **ActionGate** | `actiongate_provider/` (+ `cyber_security/action_gateway*`) |
| Commit-time operational clearance | **ACP** | `acp/` and `symbolu_robotics/autonomous_control_plane/` (shadow) |
| Sequence-risk checks (advisory only) | **StoryGraph** | `cyber_security/composite_threat_detector/` |
| Policy-bounded model/provider selection, where the workflow itself calls an LLM | **Model Selection** | `model_selection_pilot/` |
| Optional workflow composition of the above | **Optional orchestrator / AI Control Plane** | `ugence_console_api/orchestrator.py` (bypassable) |

**Authority guardrail the compiler must enforce at synthesis time:** it may wire modules together
but must never emit a graph in which one module self-authorizes another's decision. E.g. Decision
Authority may consume TAP evidence and StoryGraph advisory risk, but must not be wired to perform
exact-action authorization (ActionGate) or operational clearance (ACP). A synthesized graph that
violates a boundary is a **compile error**, not a warning.

---

## 6. Assurance generation — the tests the compiler must emit

The assurance suite is a first-class output, not an afterthought. **[SPEC]** For every approved
pack the compiler emits, at minimum:

- **Positive tests** — a compliant case reaches the approved outcome.
- **Negative tests** — a prohibited condition (§3 object 5) is blocked fail-closed.
- **Missing-evidence tests** — absence of each `Required evidence` field blocks or escalates as
  the policy dictates (never silently proceeds).
- **Authority-conflict tests** — an approver lacking authority, or the same identity acting as
  interviewer and final approver (segregation of duties), is rejected.
- **Exception tests** — each named exception triggers its required behavior, and *only* its case.
- **Override tests** — an override without documented justification, or past its expiry window,
  is rejected; a valid override is admitted and recorded.
- **Legitimate-counterexample tests** — each benign case that *resembles* prohibited behavior
  (§3 object 10) is correctly **allowed**. This is the false-positive guard.
- **Replay tests** — each `Replay case` reproduces its captured decision exactly on re-run.

**Coverage invariant:** every `Decision rule`, `Prohibited condition`, `Exception`, `Override`,
and `Authority requirement` in the pack must be referenced by at least one emitted test. A pack
whose compilation would leave any of these untested **fails Stage 4** — silent under-coverage is
treated as a defect, and any deliberately dropped coverage is logged, never omitted quietly.

---

## 7. Advisory ML vs. deterministic enforcement (the one inherited constraint)

This is the single architectural commitment carried over from the AI-training analogy (the rest
of that analogy is out of scope — Appendix A). Over time the pack library accumulates operational
data: which controls trigger, which holds are later approved, which evidence is usually missing,
which overrides are legitimate, which sequence-risk alerts are false positives. That data can
train models that **recommend or prioritize** policy changes, predict exceptions, flag evidence
gaps, and generate synthetic scenarios.

**Constraint (non-negotiable for high-consequence decisions):**

```
Machine learning        →  recommends or prioritizes a policy change
Human / governed process →  approves the policy
Deterministic policy pack →  enforces the approved rule
```

A learned model may **author or rank a proposal** that enters Stage 2 review; it may **never**
be an enforcement node in a synthesized graph. Enforcement stays deterministic, reviewable, and
versioned. This is what makes the compiled output more explainable, auditable, and enforceable
than a model trained on a corpus — the governance is captured **explicitly as rules, evidence,
tests, and mappings**, not implicitly in weights.

---

## 8. Human approval and deterministic release

**[SPEC]** Stage 5 is a governed gate, not a formality.

- **Who approves.** The reviewer(s) with authority over the pack's domain (legal, risk, security,
  business owner) approve intent and the compiled interpretation. The approver identity and role
  are recorded in the decision record.
- **What is approved.** The reviewer approves the *structured pack* (§3) and sees the generated
  workflow and assurance as evidence — including the flagged gaps: unsourced extractions,
  policy concepts with no authoritative field, and any coverage the compiler could not generate.
  Approval over unresolved gaps must be explicit.
- **Release is deterministic and content-addressed.** On approval the deployment package is frozen
  to the pack's content hash. Re-compiling the same approved pack reproduces the same package
  bit-for-bit (modulo timestamps, which are recorded, not embedded in logic).
- **Change control.** A new policy version produces a *new* pack and a structural diff (§3). The
  diff shows exactly which gates, constraints, and tests change, so re-approval is scoped to the
  delta, not the whole system.

---

## 9. Interfaces, invariants, and failure modes

**Compiler input contract.** A pack (§3) plus a **connector/system context**: system identity,
credentials handles, schema mappings, authoritative-field designations, document precedence,
override-approver directory, and block-vs-escalate defaults. Missing context is a compile-time
gap surfaced to the reviewer, never a silent default.

**Compiler output contract.** A deployment package: workflow graph, evidence collectors,
authority checks, decision gates, exception/override branches, action constraints, sequence-risk
checks, audit schema, connector configuration, and the frozen test suite — all versioned to the
approved pack.

**Global invariants.**
1. **Fail-closed.** Any prohibited condition, missing required evidence, or unresolved authority
   conflict blocks (or escalates per policy); it never proceeds by default.
2. **No silent drift.** Workflow and assurance are generated from one approved object set; they
   cannot diverge without a visible recompile and diff.
3. **No learned enforcement.** §7 — models propose, humans approve, deterministic packs enforce.
4. **Boundary preservation.** §5 — no synthesized graph lets a module self-authorize another's
   decision.
5. **Reproducibility.** Same approved pack → same package.

**Named failure modes (each must be handled, not hidden).**

| Failure mode | Required behavior |
|---|---|
| Ambiguous / conflicting source policy | Raise as Stage 2 review item; do not auto-resolve |
| Policy concept with no authoritative field | Compile-time gap; block release until reviewer decides |
| Extraction below confidence threshold | Flag as proposed-only; excluded from synthesis until approved |
| Systems disagree at runtime | Behavior is a pack object (block/escalate/prefer-source); never implicit |
| Coverage cannot be generated for a rule | Stage 4 failure; logged, surfaced, never dropped silently |
| Override past expiry / missing justification | Rejected and recorded |

---

## 10. What this spec does **not** cover

Consistent with §0 ("only partly"):

- It does **not** re-argue the AI-training-vs-policy-pack analogy beyond the one constraint in §7
  (compressed rationale in Appendix A).
- It does **not** provide a competitive teardown of Appian / Pega / UiPath / Copilot Studio /
  Workato / ServiceNow beyond the falsification framing in §1 and the compressed note in Appendix A.
- It does **not** specify the internal implementation of TAP, Decision Authority, ActionGate, ACP,
  StoryGraph, or Model Selection — those are existing capabilities; this compiler targets their
  public contracts.
- It does **not** commit an implementation schedule, cost model, or productization plan — those
  belong in the roadmap documents, not a design spec.
- It does **not** claim feasibility at production quality today; §1 explicitly leaves that as an
  open empirical question.

---

## Appendix A — Why a policy pack is not public-data model training (compressed)

Motivation only; not part of the design. Public-data AI training turns an enormous corpus into
model **weights** — probabilistic, generalized, broad but not operationally verified. A policy
pack is closer to an **executable governance playbook**: decision rules, required evidence,
authority requirements, approval paths, prohibited conditions, exceptions, overrides, action
constraints, sequence-risk patterns, counterexamples, connector mappings, tests, audit
requirements, and replay cases. The compounding loop *rhymes* with training (more deployments →
more real cases and exceptions → better packs → stronger tests → lower deployment effort → more
deployments), but the asset differs: `data → training → model weights` vs.
`client experience → generalized control pattern → executable policy → synthetic test → benchmark
→ reusable industry pack`.

The defensibility does **not** come from copying public laws/standards (available to everyone). It
comes from operational detail that only implementation reveals — how a rule maps to real
enterprise fields, which evidence is reliable, which exceptions actually occur, which controls
over-trigger, which approvals auditors accept, how policies interact across systems, what fails at
execution, which legitimate cases resemble prohibited ones, and how to reconstruct a decision
months later. A strong library layers three sources: **public foundation** (widely available),
**Ugence-authored operational content** (proprietary through engineering), and **client-derived
generalized, de-identified knowledge** (potentially the strongest moat, subject to contracts,
confidentiality, privacy, and data rights).

**Market note (inference from published capabilities, not a claim about undisclosed products):**
adjacent tools generate workflows from documents or natural language — Appian Composer
(documents→application), Pega Blueprint (requirements→blueprint), UiPath Autopilot
(description→automation), Copilot Studio (conversation→agent flow), Workato (plain language→
recipe), ServiceNow AI Agent Studio (NL→agentic workflow). None, per their published capabilities,
combines policy interpretation, authority separation, evidence requirements, exception semantics,
exact-action controls, sequence risk, test generation, and replay assurance into one automatic
compiler whose output is re-derivable from the policy.

---

## Appendix B — Worked example: hiring-recommendation policy pack

A hiring pack encodes: *a hiring recommendation may become binding only when required assessments
are complete, the decision maker has the correct authority, the interviewer and final approver
satisfy segregation of duties, required evidence is present, any override has a documented
justification, and the final action does not exceed the approved compensation range.*

Compiled (§4 → §5):

- **Required evidence → TAP + evidence collectors:** completed assessments, structured
  interview records; missing any ⇒ block/escalate (missing-evidence test, §6).
- **Authority requirement + Approval path → Decision Authority:** decision maker holds hiring
  authority for the level; interviewer ≠ final approver (segregation-of-duties test).
- **Override rule → override workflow:** override requires a documented justification and expires;
  unjustified/expired ⇒ rejected and recorded (override tests).
- **Action constraint → ActionGate:** the emitted offer must not exceed the approved compensation
  range (negative test on out-of-range offer; positive test on in-range).
- **Legitimate counterexample → must-allow test:** a senior hire at the top of an *approved*
  elevated band looks like an over-range offer but is compliant — must be allowed.
- **Audit requirement + Replay case:** record the evidence, authorities, approvals, and override
  justification such that the decision reconstructs months later; the captured decision reproduces
  on replay.

The point of the example: *that is not merely information — it is structured, testable operational
control*, and the compiler's job is to turn the reviewed pack into exactly that, with the tests
that prove it.
