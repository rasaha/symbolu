# Deliverable 8 — Enterprise Use Cases

Complete enterprise workflows showing where each Ugence product participates. Each workflow follows the same spine (Deliverable 3): the **Agent Runtime** reasons and proposes; the **AI Control Plane** authorizes and safety-checks; **AI Infrastructure** makes it cheap and scalable.

Labels: `FACT` (a product capability verified in the repo) / `INTERPRETATION` / `RECOMMENDATION`. Where a capability is a V2 gap, it is marked.

Legend: **AR**=Agent Runtime · **CM**=Context Minimization · **AG**=ActionGate · **ACP**=Autonomous Control Plane · **HLM**=Hybrid LLM · **CG**=CG LLM · **KV**=KVPro · **CSC**=Cloud Scaling Controller.

---

## 1. IT Operations — automated incident remediation

**Scenario.** An alert fires: a Kubernetes deployment is degraded. The system diagnoses and remediates with human sign-off for risky actions.

| Step | Product | What happens (FACT-anchored) |
|---|---|---|
| Ingest alert + logs + runbook | **CM** | Compress the large incident context to authorization-critical spans (FACT: 72% avg reduction, decision-invariant) |
| Diagnose root cause | **AR** + **HLM** | Runtime reasons over the (long) incident context; Hybrid LLM handles the long-context retrieval |
| Plan remediation (e.g., scale replicas, roll back a deploy) | **AR** | `goal_decomposition` → ordered actions; risk pre-screen flags the rollback as high-risk (FACT: `ToolRiskClassifier`) |
| Propose "scale web to N" | **AR → AG** | Execution Proposal + risk/uncertainty evidence |
| Authorize the scale | **AG** | Identity, RBAC, policy, approver quorum → 6-outcome verdict + token (FACT) |
| Is it safe against live cluster now? | **ACP** | Readiness/cooldown/blast-radius/capacity/freeze; the *real* `cloud_controller` supplies operational evidence (FACT: ACP consumes `cloud_controller`) |
| High-risk rollback needs sign-off | **AR (UX) → AG (authority)** | Runtime routes the approval; ActionGate binds the quorum decision |
| Execute with token | **AR** | Token-gated tool call via brokered credential (FACT: AG brokers single-use creds) |
| The remediation scales the fleet | **CSC** | Autoscaling of the underlying service, itself safety-gated (FACT: CSC read-only interlock) |
| Serving cost during the incident | **KV** | KV-cache compression keeps the diagnosis LLM calls cheap |
| Observe, reflect, update runbook memory | **AR** | Post-action reflection + memory update; if step failed, propose compensating action back through AG/ACP |

**INTERPRETATION.** This is the *canonical* Ugence workflow because ACP's live evidence (`cloud_controller`) and ActionGate's K8s reference are already built for exactly this domain (FACT). The runtime supplies the missing "intelligent diagnosis + plan" tier.

---

## 2. Financial Services — automated trade / payment operations

**Scenario.** An agent proposes portfolio rebalancing or a vendor payment; regulation demands hard authorization + four-eyes.

| Step | Product | What happens |
|---|---|---|
| Read policy, positions, market context | **CM** | Preserve authorization-critical spans (limits, mandates); drop noise |
| Reason about the rebalance | **AR** + **CG** | Runtime plans; CG LLM controls the answer-frame and audits the rationale (FACT: CG = frame control + answer audit) |
| Domain-behavior policy (FINANCE profile) | **AR** | `domain_policy` FINANCE profile shapes conservatism (FACT: built-in FINANCE profile) |
| Propose "execute trade / release payment" | **AR → AG** | Proposal + risk evidence (irreversibility, blast radius flagged) |
| Hard authorization | **AG** | MAX_COST / MAX_IRREVERSIBILITY / REQUIRE_APPROVER hard invariants (FACT: operators in `gate.py`); four-eyes quorum |
| Operational safety (settlement window, exposure now) | **ACP** | Freeze-window / capacity analogues for the financial domain (INTERPRETATION: needs a finance adapter; ACP core is cross-domain by design, FACT) |
| Execute on approval | **AR** | Token-gated |
| Immutable audit for the regulator | **AG** | Tamper-evident hash-chained authorization audit (FACT) |
| Runtime reasoning trace for explainability | **AR** | Separate reasoning trace (FACT: distinct from AG's decision audit) |

**RECOMMENDATION.** Financial services is where the **hard, non-compensatory** nature of ActionGate is the selling point — a probabilistic agent alone is unshippable in a regulated trading desk; the agent + a deterministic authority is the wedge. (Note: `agentic/policy/trading_guardrail_engine.py` exists as an agent-behavior guardrail — FACT — but authoritative trade authorization must be ActionGate's, not the runtime's.)

---

## 3. Healthcare — clinical documentation & order assistance

**Scenario.** An agent drafts clinical notes and proposes orders (labs, referrals); patient-safety and PHI rules are strict.

| Step | Product | What happens |
|---|---|---|
| Assemble patient chart context (large) | **CM** + **HLM** | Compress to decision-critical spans; Hybrid LLM for long-record retrieval |
| Draft note / propose order | **AR** + **CG** | Runtime reasons; CG LLM keeps the answer in the correct clinical frame and audits it (reduces the "wrong-frame" failure, FACT: CG's stated failure mode) |
| PHI-minimal context | **CM** | Deterministic minimization limits what the model reads (FACT: authorization-preserving) — a privacy control by construction |
| Propose a lab order / referral | **AR → AG** | Proposal; high-risk clinical actions flagged |
| Authorize the order | **AG** | REQUIRE_ATTESTATION / clinician approver quorum (FACT: operators exist) |
| Operational safety (drug interaction / protocol window) | **ACP** | Non-compensatory hard-constraint filter analogue (INTERPRETATION: clinical-safety adapter over the cross-domain core) |
| Clinician sign-off | **AR (UX) → AG (authority)** | Runtime surfaces; ActionGate binds |
| Audit for compliance | **AG** | Immutable record |

**INTERPRETATION.** Healthcare leans hardest on **Context Minimization as a privacy control** (minimal-necessary PHI) and **ACP's non-compensatory safety** (a soft "confidence 0.9" can never override a hard interaction constraint) — both FACT-level properties of those products.

---

## 4. Manufacturing — autonomous operations / robotics

**Scenario.** An agent supervises a robotic cell or a maintenance robot.

| Step | Product | What happens |
|---|---|---|
| Reason about the maintenance task | **AR** | Runtime plans the sequence |
| Propose a physical actuation | **AR → AG → ACP** | Proposal enters the Control Plane |
| Authorization | **AG** | Who/what may command the robot (identity, RBAC) |
| **Operational safety — the core** | **ACP** | This is ACP's *native* domain: "deterministic decision-and-authorization runtime between a robot's perception/prediction stack and its actuators" (FACT: `acp/ACP_ARCHITECTURE.md`); non-compensatory hard constraints, `NO_SAFE_ACTION` fallback |
| Execute / abstain | **AR / ACP** | ACP may return `NO_SAFE_ACTION`; runtime must accept and re-plan |
| Recover on fault | **ACP** | Deterministic failure-state machine (FACT) |

**FACT.** Manufacturing/robotics is the one domain where the *same frozen ACP core* already runs (FACT: robotics + cloud on one byte-identical core). The runtime adds the task-level intelligence above ACP's per-tick actuation safety. This is the strongest proof that runtime ⟂ control-plane generalizes across physical and digital domains.

---

## 5. Customer Support — tiered resolution with actions

**Scenario.** An agent resolves a support ticket, taking real actions (refund, reset, config change).

| Step | Product | What happens |
|---|---|---|
| Read ticket + account + KB | **CM** | Compress; preserve entitlement/authorization spans |
| Understand & plan resolution | **AR** + **CG** | Runtime reasons; CG LLM keeps the answer on-frame (reduces drift/generic answers, FACT: CG failure modes) |
| Multi-role handoff (diagnose → remediate) | **AR (multi-agent, V2)** | Hierarchical: a triage agent hands off to a remediation agent (Deliverable 5) — **V2 gap** |
| Propose a refund / account change | **AR → AG** | Proposal + risk (refund amount → MAX_COST) |
| Authorize | **AG** | Policy + approver for large refunds (quorum) |
| Operational safety (rate limit, fraud window) | **ACP** | Operational constraints (INTERPRETATION: support-domain adapter) |
| Execute + confirm to customer | **AR** | Token-gated action, then respond |
| Cost at support scale | **KV** + **CSC** | KV compression per conversation; CSC scales the fleet under load |

**RECOMMENDATION.** Customer support is the best **multi-agent** showcase (triage/remediation/QA roles) and therefore a good driver for the Deliverable-5 Layer-1 work — but only after single-agent + Control-Plane integration is solid.

---

## 6. Product-participation summary

| Product | IT Ops | FinServ | Healthcare | Manufacturing | Support |
|---|---|---|---|---|---|
| **Agent Runtime** | ✅ core | ✅ core | ✅ core | ✅ task tier | ✅ core (multi-agent) |
| **Context Minimization** | ✅ | ✅ | ✅ (privacy) | ◻ | ✅ |
| **ActionGate** | ✅ | ✅ (hard) | ✅ | ✅ | ✅ |
| **ACP** | ✅ (native cloud) | ◻ (adapter) | ◻ (adapter) | ✅ (native robotics) | ◻ (adapter) |
| **Hybrid LLM** | ✅ (long ctx) | ◻ | ✅ (long record) | ◻ | ◻ |
| **CG LLM** | ◻ | ✅ (audit) | ✅ (frame) | ◻ | ✅ (frame) |
| **KVPro** | ✅ | ✅ | ✅ | ◻ | ✅ |
| **Cloud Scaling Controller** | ✅ (native) | ✅ | ✅ | ◻ | ✅ |

✅ = clear participation · ◻ = optional / needs a domain adapter (INTERPRETATION).

**INTERPRETATION.** Across all five, the Agent Runtime is always the intelligence tier and always proposes into the Control Plane; ActionGate is always the authority; ACP is native where a live-state model exists (cloud, robotics) and needs a thin domain adapter elsewhere (FACT: ACP's core is cross-domain by construction). The infrastructure products participate wherever inference volume is high. No product ever does another's job — the same clean boundary holds in every workflow.
