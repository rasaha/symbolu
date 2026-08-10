# Part 7 — Universal AI Control Plane

Can every runtime emit the same Execution Proposal? If not, why not? If yes, which fields are mandatory, optional, and which should never exist?

Labels: `FACT` (repo evidence) · `INTERPRETATION` · `RECOMMENDATION` · `EXTERNAL KNOWLEDGE`.

---

## 1. Can every runtime emit the same Execution Proposal?

**Answer: YES for the action-authorization proposal; NO for a single universal proposal that also carries context governance. INTERPRETATION, grounded in Part 2.**

- **YES (ActionGate + ACP path).** Every runtime that ultimately *calls a tool / takes an action* can, through an adapter, express that action as `principal + requested_action + credential_scope + state_binding` (Part 1, Part 3). This is universal because the thing being governed — an action against a system — is a universal concept; every agent framework emits tool calls (FACT: `ACTIONGATE_VC_BRIEF.md:21–22`, "MCP servers, function-calling APIs, and agent frameworks all wire a model to a tool-calling loop"). The proposal describes the *action*, which every runtime has, not the *reasoning*, which differs.

- **NO (Context Minimization path).** The `context_bundle` cannot be uniformly emitted, because it requires ActionGate-shaped spans (`contrib`, action `base`, frozen `source_type`) and only yields a guarantee inside an ActionGate pipeline (FACT: `compressor.py:36–58`, `units.py:41`; audit Q6). A runtime can *always* emit the action; it can only *sometimes* emit a meaningful context bundle.

**INTERPRETATION.** The universal object is the **action proposal**, not the **context bundle**. This is the single most important design conclusion of the milestone: the universal AI Control Plane is universal on its *authorization + operational-safety* axes, and pipeline-specific on its *context* axis.

---

## 2. Why some runtimes cannot emit certain fields (the honest limits)

| Field | Which runtimes struggle, and why (FACT / EXTERNAL KNOWLEDGE) |
|---|---|
| `requested_action.operation` (fixed taxonomy) | Free-form **code executors** (AutoGen `UserProxyAgent` running arbitrary code) can't always map an action to a 10-op taxonomy — the action is "run this code," whose effects aren't known until run. Needs a `SIMULATE_AND_RETRY` / dry-run to classify. (FACT: taxonomy `schema.py:34–38`; EXTERNAL: AutoGen code exec.) |
| `state_binding` (current_state_hash + freshness) | Runtimes acting on systems with **no observable state hash** (a fire-and-forget webhook) can't bind state; ActionGate can still authorize but ACP can't evaluate operational safety (nothing live to check). |
| `context_bundle` | Any runtime not using ActionGate spans (§1). |
| `risk_evidence` | Runtimes with no uncertainty signal (most competitors) simply omit it — it's optional and scrutiny-only, so absence is safe (FACT: evidence "can only raise scrutiny"). |
| `expected_outcome` | Runtimes without a simulator omit it; optional. |

**INTERPRETATION.** None of these is a *blocker* to governance — they degrade gracefully: a missing optional field means less scrutiny-raising evidence, not a bypass; a missing `state_binding` means ACP abstains rather than mis-approves (fail-closed). The only hard requirement is the mandatory action core, which every action-taking runtime can express.

---

## 3. Field taxonomy: mandatory / optional / never

**RECOMMENDATION.** The universal Execution Proposal schema:

### Mandatory (every runtime must supply; ActionGate reads them)
- `principal` — agent_identity{id, key_id, sig}
- `requested_action.tool` — {server_id, tool_name}
- `requested_action.operation` — from the frozen taxonomy
- `requested_action.target_resource[]`
- `requested_action.arguments` — canonical Action Profile
- `credential_scope` — {principal, permissions, ttl}
- `authority_chain` — delegation_chain[], delegator
- `reversibility`
- `policy_version`

**FACT basis:** these are exactly the fields ActionGate's predicates read to decide (`gate.py:46–234`).

### Optional (raise scrutiny or enable extra layers; never lower a bar)
- `state_binding` — enables ACP operational safety + TOCTOU closure (strongly recommended where a state exists)
- `risk_evidence` — scrutiny-only
- `expected_outcome` — simulator/dry-run
- `rollback_plan`, `linked_ticket`, `attestation`, `approvals[]`
- `context_bundle` — only in an ActionGate + Context-Minimization pipeline

### Should never exist (governance must never depend on runtime internals)
**FACT-anchored** (Part 2 grep-confirmed the Control Plane reads none of these):
- `prompt`, `system_message`, `chat_template`
- `reasoning_trace`, `chain_of_thought`, `scratchpad`
- `memory_state`, `conversation_history`
- `planning_algorithm`, `reflection_algorithm`
- `model_weights`, `temperature`, `sampling_params`
- `orchestration_graph`, `framework_internal_state`

**RECOMMENDATION — the contested three.** `runtime`, `model_provider`, `objective` currently exist as *mandatory + hashed* fields (FACT: `schema.py:40–46`). They should be **demoted to optional, non-identity metadata** (Part 1 §3, Part 11 R3). They describe the producer, not the action; keeping them in the identity hash makes proposals non-portable across runtimes for no decision benefit (they are control-inert, FACT: `projection.py:44–46`).

---

## 4. The universality test (falsifiable)

**RECOMMENDATION — how to prove or disprove universality empirically** (this has NOT been done; FACT: only Ugence's offline reader has driven the pipeline, `END_TO_END_CONTROL_PLANE_SPEC.md:22–25`):

1. Take three genuinely different runtimes (e.g., LangGraph, an MCP-native SDK, and a bespoke script).
2. Have each attempt the *same* enterprise action (e.g., "scale deployment web to 3").
3. Through each runtime's adapter, produce the canonical proposal.
4. Assert: all three produce the **same `action_hash`** (after demoting the provenance fields per §3) and receive the **same ActionGate + ACP verdict**.
5. If yes → universality demonstrated. If the hashes differ only because of provenance fields → the §3 fix is validated as necessary. If they differ for *action* reasons → a hidden coupling exists (falsified).

**INTERPRETATION.** This test is the missing empirical link. The architecture *predicts* it passes (the action is identical; the Control Plane reads only the action). Until it is run, universality is *architecturally supported but empirically undemonstrated* — which is exactly the qualification the verdict (Part 12) applies.
