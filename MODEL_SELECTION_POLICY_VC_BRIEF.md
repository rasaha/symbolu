# Model Selection and Governed Inference — VC Brief

**Ugence Labs | Model Selection and Governed Inference Control Plane**
*A policy-driven layer that decides whether an AI request runs, which model handles it, what evidence its claims require, whether the answer may be delivered, and whether the proposed action may proceed.*
*Version 1.0.0 — July 2026 (external / evidence-based)*

> **Product family.** Model Selection and Governed Inference is the **inference-governance** entry
> point of the **AI Control Plane** in the Ugence Labs portfolio (canonical taxonomy in
> `UGENCE_PLATFORM_OVERVIEW.md`). It shares the platform's action-authorization primitive —
> **ActionGate** (see `ACTIONGATE_VC_BRIEF.md`) and the broader control plane
> (`AI_CONTROL_PLANE_VC_BRIEF.md`) — but its product boundary is upstream of execution: it governs
> **which model reasons and whether the resulting assertion is admissible**, then hands any proposed
> action to ActionGate. This brief describes the module as it exists in the repository today — its
> implemented mechanism, its validation state, and what remains unproved.

---

## Page 1 — The Problem

### Model choice is becoming a governance decision, not an inference-optimization decision.

Enterprises now run many models at once — frontier APIs, private models, small local models,
specialized models — across providers, sizes, costs, latencies, and risk levels. Today's model
routers optimize for **cost, latency, benchmark quality, token availability, or provider uptime**.
They do not answer the questions a risk, security, or compliance team actually has to answer:

- Is this model *permitted* for this task?
- Does it meet the required *quality threshold* — or is it just cheaper?
- May *sensitive data* be sent to this provider or deployment environment?
- Does the response carry *sufficient evidence* for what it claims?
- Can the answer be *delivered without qualification*?
- Is the *proposed action authorized*?
- Can the decision be *audited and reproduced*?

As enterprises move from AI assistants to AI agents, choosing a model is no longer a scoring problem.
It is a decision about **which intelligence is allowed to reason, what it may assert, and what it may
do, under whose authority, with what evidence, and with what audit trail.**

### The Ugence answer

A **layered inference-governance control plane** that sits between enterprise applications and AI
models and separates four decisions that are usually collapsed into one:

1. **Capability** — can a model perform the task at all?
2. **Selection** — among *eligible* models, which gives the best policy-defined utility?
3. **Assertion governance** — is the output sufficiently supported to deliver?
4. **Action governance** — is any proposed action permitted (handed to ActionGate)?

The model proposes; the control plane decides whether and how the request runs, whether the answer
may be shown, and whether the action may proceed. Hard constraints are applied **before** optimization
— a cheaper or faster model can never win by trading away quality, privacy, or risk controls.

---

## Page 2 — Architecture

```
   Enterprise request
        │
        ▼
   ExecutionGate        ── may this request execute at all?
        │
        ▼
   ModelPolicy          ── which ELIGIBLE model should handle it?
        │                  (hard constraints first, then policy-defined utility)
        ▼
   ClaimIntegrity       ── what exactly is being claimed?
        │
        ▼
   Minimal Evidence     ── what level of evidence does that claim require?
   Policy                 (E0 … E4 · ER — monotonic, ~12 transparent rules)
        │
        ▼
   EvidenceAssurance    ── does the available evidence meet that obligation?
        │
        ▼
   AssertionGate        ── may the response be delivered (as-is / qualified / withheld)?
        │
        ▼
   ActionGate           ── may the proposed action proceed?
        │                  ALLOW · ALLOW_WITH_CONSTRAINTS · DENY ·
        ▼                  ESCALATE_TO_HUMAN · REQUEST_MORE_EVIDENCE · SIMULATE_AND_RETRY
   Governed result + deterministic, replayable audit trace
```

### The model-selection engine

Candidate models are evaluated against task capability, minimum quality thresholds, cost, latency,
context requirements, privacy constraints, deployment restrictions, provider eligibility, evidence
requirements, operational availability, and enterprise policy. **Hard constraints filter first;
optimization runs only over the survivors.** A model that fails quality, privacy, risk, deployment,
or capability requirements is ineligible regardless of how cheap or fast it is. Among eligible models,
the engine selects the highest policy-defined utility.

### Structural principles (design invariants)

- **Hard quality gates** — low-cost models cannot compensate for unacceptable quality with a lower price.
- **Policy authority** — human-defined enterprise rules are the source of truth for critical decisions.
- **Native decision semantics** — the six ActionGate outcomes above are preserved, never compressed
  into a simplistic allow / block.
- **Evidence obligations by claim type** — implementation behavior may be supported by code and tests;
  performance claims require measurements; company policy requires an authoritative policy artifact;
  medical / legal / regulatory claims require stronger external authority; **model-generated statements
  cannot verify themselves.**
- **Monotonic governance** — increasing risk, uncertainty, actionability, or temporal sensitivity can
  only *raise* the evidence requirement; it can never make the system more permissive.

---

## Page 3 — Evidence (what has been proven)

All results are from our own repository and CI on real components, against **natural artifacts** (not
only synthetic demonstrations). The program ran as multiple **falsification-first** tracks with frozen,
pre-registered success/kill criteria; prior artifacts are protected by cryptographic freeze guards.

### The minimal evidence-obligation policy — frozen evaluation (10 / 10 criteria)

| Metric | Result |
| --- | ---: |
| Clean allow (natural-artifact utility) | **0% → 50%** |
| Over-qualification | **85.5% → 0%** |
| Unsafe high-risk allows | **0** |
| Unsafe action allows | **0** |
| Self-verification escapes | **0 of 13** |
| Monotonicity violations | **0 of 528** |
| Frozen technical success criteria passed | **10 of 10** |

The policy **withholds every high-risk claim** (0% clean allow at high risk) while restoring utility on
low/medium-risk supported content — the intended shape, not a utility edge bought with unsafe allows. It
beats both a risk-only baseline and a richer classifier on safety (**0 vs 52 of 85 total unsafe allows**),
and was deliberately **reduced to ~12 transparent rules** after the larger classifier failed to justify
its complexity.

### Control-flow and governance

- Unified **execution → model-selection → assertion → action** control flow.
- **Native ActionGate semantics preserved** (six outcomes, never collapsed).
- **Deterministic audit and replay**; **fail-closed** handling; **no autonomous enforcement** during testing.

### Reviewer workflow — packaged and reviewer-ready

Blinded two-stage review; training + qualification sets; role-based reviewer access; immutable reviewer
and system records; audit and replay; **mock-review exclusion from human metrics**; a frozen future
human-evaluation protocol. Readiness verdict: **REVIEWER-READY — WAITING FOR REAL REVIEWERS.**

### Honest limitations (status, not marketing)

- **Technical validation: completed.** **Reviewer workflow: ready.**
- **Real human validation: NOT yet performed.** Two calibration-round activations were correctly
  **blocked** — the first because no real reviewers were supplied, the second because the eligibility gate
  enforced reviewer independence and excluded a founder / stakeholder (a `COI = YES` checkbox does not
  waive a structural stake), and because qualification requires real graded responses the system will not
  fabricate.
- **External customer pilot: still gated. Production readiness: not claimed.**
- Evaluations run against authored/natural corpora and reference components; enforcement is never enabled
  and no external action is executed in this state.

---

## Page 4 — Positioning, moat, go-to-market, ask

### Market position

Ugence operates at the intersection of AI gateways, model routers, AI governance, agent security, policy
engines, privileged-action controls, and evidence/assertion governance. The opportunity is broader than
routing: an independent layer that controls **which intelligence is used, what it may assert, what it may
do, under whose authority, with what evidence, and with what audit trail.**

| Category | Typical focus | Ugence differentiation |
| --- | --- | --- |
| Model routers | Cost and latency | Policy, eligibility, quality gates, governance |
| AI gateways | Access, logging, provider abstraction | Decision authority across models, assertions, actions |
| AI governance tools | Compliance dashboards, inventory | Runtime control *before* assertion or action |
| Agent guardrails | Prompt / output filtering | Evidence, policy authority, native action decisions |
| Privileged-access systems | Human / machine access control | AI-generated action evaluation + contextual authorization |
| Evaluation platforms | Offline benchmarking | Runtime, task-specific model eligibility and selection |

### Moat / defensibility

The defensible asset is **not a single scoring algorithm**. It is the **governed decision architecture** —
policy-constrained model selection; separation of execution, selection, assertion, and action; native
multi-outcome semantics; claim-type evidence obligations; deterministic audit/replay; monotonic risk
controls; regulated-domain policy packages; accumulated shadow-pilot decision data; integration into
enterprise execution paths; and IP development.

### Go-to-market

- **Phase 1 — Internal & design-partner shadow pilots** (non-enforcing) where AI already recommends but
  does not autonomously execute: cybersecurity ops, financial ops, enterprise IT, media ops, support
  escalation, approval/refund workflows.
- **Phase 2 — Governed production recommendations** — model selection + assertion governance, humans
  retained for consequential cases.
- **Phase 3 — Constrained action governance** — selected low-risk actions under explicit policy limits;
  high-risk or ambiguous actions escalate.

**Business model:** enterprise platform license · usage-based control-plane pricing (per governed
request / assertion / selection / action) · regulated-domain packages · private/VPC/on-prem deployment ·
paid bounded-shadow-pilot and integration services.

### Next commercialization milestones

1. Complete real-reviewer calibration → 2. bounded internal single-tenant pilot → 3. one low-risk customer
shadow pilot → 4. establish operational-utility and reviewer-burden evidence → 5. convert to a paid
governed-inference pilot.

### The ask

Fund productization of the research implementation: enterprise APIs/integrations, policy-administration
and audit interfaces, reviewer and design-partner pilots, expanded model-provider integrations, security
and privacy hardening, regulated-domain policy packages, patent prosecution, and enterprise engineering +
GTM hires.

### Investment thesis

AI models are becoming interchangeable; enterprise authority is not. The winning enterprise layer may not
be the model — it may be the system that decides **which model may reason, which evidence is required,
which answer may be trusted, which action may proceed, and when a human must remain in control.**
**Ugence Labs is building that control plane.**

---

*Contact: Rakesh Mohan — Ugence Labs*
*Repo: `rasaha/symbolu` · Components: `minimal_evidence_policy/` (evidence-obligation policy) · `model_selection_experiment/` · `evidence_obligation/` · `governed_inference_pilot/` · `bounded_shadow_pilot/` · `reviewer_ready_pilot/` `reviewer_calibration_pilot/` (reviewer workflow)*
*Status: technical validation complete · reviewer workflow ready · human validation NOT EVALUATED · external pilot BLOCKED · production NOT claimed*
