# Governance Studio — Demo Script

Presenter narrative for the four demo scenarios. Every number below is produced by
the **real** AWC P1/P2 engine over the committed `demo_data/` fixtures and is frozen
in `expected_outputs/`. Nothing here is hand-authored output.

Fixed `logical_time = 1_000_000.0`. All agents, evidence, workflows and policies are
**synthetic**.

Maturity language to keep on screen throughout:

> Eligibility means an agent remains *permitted for consideration*. It does not mean
> the agent was selected, assigned, authorized, or executed. Permission-bound
> proposals are planning-time proposals — no permission is granted or provisioned.

---

## 1. Procurement — *the top individuals are not the team*

**1. Business context.** A purchase request must be validated, supplier evidence
collected, supplier risk analysed, and a recommendation drafted — then a human
approves, and governance capabilities authorize and clear the actual purchase.

**2. Workflow steps (9 nodes).** `proc_request_validation` (rule) →
`proc_supplier_evidence` (agent) → `proc_supplier_risk` (agent) →
`proc_recommendation` (agent) → `proc_binding_approval` (human) →
`proc_purchase_auth` (governance) → `proc_commit_clearance` (governance) →
`proc_audit` (deterministic) → `proc_terminal`.

**3. AI-agent roles (3).** supplier evidence collection, procurement risk analysis,
procurement recommendation.

**4. Human / governance-controlled steps.** Binding approval →
`HUMAN_AUTHORITY_REQUIRED`; purchase authorization and commit-time clearance →
`EXISTING_GOVERNANCE_CAPABILITY_OWNS_STEP`; request validation and audit →
`DETERMINISTIC_SERVICE_PREFERRED`; terminal → `NO_AI_AGENT_REQUIRED`.

**5. Eligible agents.** evidence → `agent_supplier_evidence` (Anthropic),
`agent_general_analyst` (OpenAI); risk → `agent_procurement_risk` (Anthropic) only;
recommendation → `agent_procurement_recommendation` (Anthropic) only.

**6. Notable eliminations.** `agent_india_procurement` → `RESIDENCY_MISMATCH` +
`DEPLOYMENT_ENVIRONMENT_MISMATCH` (IN residency under a US-required policy); the
specialists are mutually ineligible across roles on `MISSING_REQUIRED_CAPABILITY`.

**7. Selected team.** evidence → **`agent_general_analyst` (OpenAI, rank #2, 7604
bp)**; risk → `agent_procurement_risk` (Anthropic); recommendation →
`agent_procurement_recommendation` (Anthropic).

**8. Team-level trade-off — the headline.** Individually, the top-ranked evidence
agent is `agent_supplier_evidence` (Anthropic, **7819 bp**). The greedy per-role
choice is therefore **all three roles on Anthropic** — which violates the **67%
provider-concentration limit** (3/3 = 100%). The generalist is the enterprise's only
non-Anthropic procurement agent and is eligible only for evidence collection, so the
composer's single feasible optimum keeps the two harder specialist roles on their top
agents and moves evidence collection to the lower-ranked generalist. **The
individually top-ranked candidates do not form the selected team.**

**9. Proposed permissions.** Each assignment proposes `read_context` with authority
scope 1 — least-privilege, carrying the no-grant notice.

**10. Fallback coverage.** evidence → `PARTIAL` (fallback `agent_supplier_evidence`,
the dropped top specialist); risk → `NO_FALLBACK_AVAILABLE`; recommendation →
`NO_FALLBACK_AVAILABLE` (single eligible holder each).

**11. Plan maturity and limitations.** `plan_state = COMPLETE`, exact optimum. This
is a plan, not an execution: no permission is granted and no purchase is authorized —
those remain human/governance-owned nodes.

---

## 2. Customer Support — *clean team; a specialist correctly benched*

**1. Business context.** A support ticket is triaged, relevant customer knowledge is
retrieved, and a response is drafted; a human decides on escalation and approves.

**2. Workflow steps (6 nodes).** `sup_triage` (agent) → `sup_retrieval` (agent) →
`sup_draft` (agent) → `sup_escalation_decision` (human) → `sup_human_approval`
(human) → `sup_terminal`.

**3. AI-agent roles (3).** support triage, customer knowledge retrieval, customer
response drafting.

**4. Human / governance-controlled steps.** Escalation decision and human approval →
`HUMAN_AUTHORITY_REQUIRED`; terminal → `NO_AI_AGENT_REQUIRED`.

**5. Eligible agents.** triage → `agent_support_triage`, `agent_multilingual_support`;
retrieval → `agent_knowledge_retrieval`, `agent_multilingual_support`,
`agent_general_analyst`; draft → `agent_response_drafting`,
`agent_multilingual_support`.

**6. Notable eliminations.** `agent_threat_analysis` — a cybersecurity specialist in
the same registry — is **eliminated on every support role** (`MISSING_REQUIRED_CAPABILITY`).
It is never mis-assigned to drafting on generic contract compatibility.

**7. Selected team.** triage → `agent_support_triage`; retrieval →
`agent_knowledge_retrieval`; draft → `agent_response_drafting` — the top-ranked agent
for each role (a clean, greedy-feasible team spanning two providers).

**8. Team-level trade-offs.** None binding: the greedy team already satisfies the
67% provider-concentration limit (2/3 Anthropic), so no swap is forced.

**9. Proposed permissions.** `read_context`, authority scope 1, least-privilege, with
the no-grant notice.

**10. Fallback coverage.** retrieval → `COMPLETE` (`agent_multilingual_support`,
`agent_general_analyst`); triage → `PARTIAL`; draft → `PARTIAL`
(`agent_multilingual_support`).

**11. Plan maturity and limitations.** `plan_state = COMPLETE`. The value on show is
*honest exclusion*: a strong but off-domain specialist is benched by capability
requirements, not by intuition.

---

## 3. Cybersecurity — Feasible — *a real team, and honest "no fallback"*

**1. Business context.** A security incident requires evidence collection, threat
analysis, incident correlation, and a security recommendation, under a level-4
clearance bar; a human escalates and governance bounds any action.

**2. Workflow steps (9 nodes).** `sec_evidence_collection` (agent) →
`sec_threat_analysis` (agent) → `sec_incident_correlation` (agent) →
`sec_recommendation` (agent) → `sec_sequence_risk` (governance advisory) →
`sec_human_escalation` (human) → `sec_action_boundary` (governance) → `sec_audit`
(deterministic) → `sec_terminal`.

**3. AI-agent roles (4).** security evidence collection, threat analysis, incident
correlation, security recommendation.

**4. Human / governance-controlled steps.** Sequence-risk and action boundary →
`EXISTING_GOVERNANCE_CAPABILITY_OWNS_STEP`; human escalation →
`HUMAN_AUTHORITY_REQUIRED`; audit → `DETERMINISTIC_SERVICE_PREFERRED`; terminal →
`NO_AI_AGENT_REQUIRED`.

**5. Eligible agents.** evidence → `agent_security_evidence` (Anthropic),
`agent_general_analyst` (OpenAI); threat → `agent_threat_analysis` (Anthropic) only;
correlation → `agent_incident_correlation` (OpenAI) only; recommendation →
`agent_security_recommendation` (OpenAI) only.

**6. Notable eliminations.** `agent_low_clearance` → `SECURITY_CLASSIFICATION_INSUFFICIENT`
(cleared to level 2, below the required 4), on every role it declares.

**7. Selected team.** evidence → `agent_security_evidence`; threat →
`agent_threat_analysis`; correlation → `agent_incident_correlation`; recommendation →
`agent_security_recommendation`. Two Anthropic + two OpenAI (50% concentration,
within limit).

**8. Team-level trade-offs.** The team spans two providers, satisfying provider- and
failure-domain concentration limits; each role takes its top-ranked cleared agent.

**9. Proposed permissions.** `read_context`, authority scope 1, least-privilege, with
the no-grant notice.

**10. Fallback coverage.** evidence → `PARTIAL` (fallback `agent_general_analyst`);
threat, correlation, recommendation → **`NO_FALLBACK_AVAILABLE`** — each specialist
capability is held by a single cleared agent. This is surfaced honestly, not hidden.

**11. Plan maturity and limitations.** `plan_state = COMPLETE`, exact optimum, but
with a candid resilience gap: three of four roles have no backup agent. The plan says
so.

---

## 4. Cybersecurity — No Feasible Team — *the honest "no"*

**1. Business context.** The same incident-response need, but under a stricter
provider-concentration policy and a registry where only one approved provider is
cleared to level 4.

**2. Workflow steps (7 nodes).** `sec_evidence_intake` (rule) → `sec_threat_analysis`
(agent) → `sec_incident_correlation` (agent) → `sec_human_escalation` (human) →
`sec_action_boundary` (governance) → `sec_audit` (deterministic) → `sec_terminal`.

**3. AI-agent roles (2).** threat analysis, incident correlation.

**4. Human / governance-controlled steps.** Intake → `DETERMINISTIC_SERVICE_PREFERRED`;
escalation → `HUMAN_AUTHORITY_REQUIRED`; action boundary →
`EXISTING_GOVERNANCE_CAPABILITY_OWNS_STEP`; audit → deterministic; terminal → none.

**5. Eligible agents.** threat → `agent_threat_analysis` (Anthropic) only; correlation
→ `agent_incident_correlation` (Anthropic) only. **Both roles are individually
eligible** — this is not an empty registry.

**6. Notable eliminations.** `agent_openai_threat` (level 2) and `agent_google_threat`
(level 3) → `SECURITY_CLASSIFICATION_INSUFFICIENT`. No non-Anthropic provider clears
the level-4 bar.

**7. Selected team.** **None.**

**8. Team-level trade-off — the reason.** A two-role team can only be staffed from a
single provider (Anthropic), i.e. 100% provider concentration, but the policy caps
concentration at 60% and requires ≥2 providers. There is **no feasible team**.

**9. Proposed permissions.** None — there is no assignment to bound.

**10. Fallback coverage.** Not applicable — no primary was selected.

**11. Plan maturity and limitations.** `plan_state = NO_FEASIBLE_TEAM`. The studio
renders this as a typed, explained failure — **never** as an empty but successful
dashboard. The credible fix (a second cleared provider, or a policy exception) is a
governance decision, shown but not taken.

---

## Presenter closing

Across four scenarios the studio shows the same engine producing a non-greedy team, a
clean team, an honest resilience gap, and an honest refusal — all deterministic, all
replayable to the same fingerprints, all on synthetic data, and all strictly
planning-time. No agent was executed; no permission was granted; no business action
was authorized.
