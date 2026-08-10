# The Canonical Execution Proposal — Vendor-Neutral Schema (Deliverable 2)

**Design constraint (from the milestone):** design it around *every* runtime, **not** around Ugence's. It must be producible by OpenAI Agents SDK, LangGraph, CrewAI, Google ADK, AutoGen, Semantic Kernel, Claude Code, the Ugence Agent Runtime, and future runtimes.

Labels: `FACT` (grounded in repo input-contract audits) · `INTERPRETATION` · `RECOMMENDATION` · `EXTERNAL KNOWLEDGE`.

This schema is the *only* object that crosses the runtime → AI Control Plane boundary. It supersedes the Ugence-flavored draft in `../ai_control_plane_v3/01_RUNTIME_CONTRACT.md` by removing every field that assumed the Ugence runtime.

---

## 1. Design rules (why the schema is shaped this way)

1. **Describe the ACTION, never the reasoning.** `FACT`: the audits in `../ai_control_plane_v3/02_RUNTIME_INDEPENDENCE_AUDIT.md` showed ActionGate/ACP read only the action, world-state, authority, evidence, and policy — never prompt/reasoning/memory/model/orchestration. So the schema carries only what governance actually consumes.
2. **Every mandatory field must be producible by the *weakest* runtime.** If a field can only come from a runtime with a specific internal (a trace, a plan graph, a model logit), it cannot be mandatory.
3. **Provenance is metadata, never identity.** `FACT`: ActionGate currently hashes `runtime`/`model_provider`/`objective` into the action identity, which breaks cross-runtime portability (`projection.py:44–46`). This schema records provenance but **excludes it from the identity digest** — the pattern ACP already uses for its `provenance` field (`envelopes.py:62`).
4. **Optional fields raise scrutiny; they never lower a bar.** `FACT`: ActionGate evidence "can only raise scrutiny, never lower a hard invariant" (`ACTIONGATE_VC_BRIEF.md`). A runtime that omits an optional field gets *more* scrutiny, never a bypass.
5. **Governance pulls world + policy elsewhere.** The runtime does not supply policy or live world-state; the Control Plane pulls those from the enterprise root-of-trust and a domain `WorldStateProvider`. Keeps the runtime's burden minimal.

---

## 2. The schema

```jsonc
// ExecutionProposal v0 — vendor-neutral. Wire format is illustrative (JSON/JCS).
{
  "schema": "execution_proposal/v0",

  // ── IDENTITY (DERIVED, not supplied) ─────────────────────────────
  // action_digest = H( canonical_bytes( action ) )  — a pure function of the
  // ACTION ONLY. Provenance is NOT an input. Two runtimes emitting the same
  // action produce the same digest.  (FACT-motivated: fixes ai_control_plane_v3 R3)
  "action_digest": "<computed by the adapter/CP, not the runtime>",

  // ── PRINCIPAL — who is acting (MANDATORY) ────────────────────────
  "principal": {
    "id": "string",                 // stable agent/session principal
    "key_id": "string",             // signing key reference
    "signature": "string",          // signs the action_digest
    "on_behalf_of": "string|null"   // human/service the agent acts for (optional)
  },

  // ── ACTION — what exactly is to be done (MANDATORY) ──────────────
  "action": {
    "tool": { "namespace": "string", "name": "string" },   // e.g. {"k8s","scale"}
    "operation": "READ|WRITE|EXECUTE|DELETE|GRANT|TRANSFER|CONFIGURE|DEPLOY|COMMUNICATE|OTHER",
    "targets": [ { "type": "string", "id": "string" } ],   // resources touched
    "arguments": { },               // canonical, typed-string numerics (JCS profile)
    "reversibility": "REVERSIBLE|COMPENSATABLE|IRREVERSIBLE|UNKNOWN"
  },

  // ── AUTHORITY — the permission requested (MANDATORY) ─────────────
  "authority": {
    "credential_scope": { "principal": "string", "permissions": ["string"], "ttl_s": 0 },
    "delegation_chain": [ { "id": "string", "type": "string", "grants": ["string"] } ]
  },

  // ── STATE BINDING — closes time-of-check/time-of-use (STRONGLY RECOMMENDED) ──
  "state_binding": {
    "world_state_hash": "string|null",     // hash of the state the decision assumes
    "observed_at": "rfc3339|null",         // freshness
    "source": "string|null"                // where the state came from
  },

  // ── EVIDENCE — scrutiny-only, may only tighten (OPTIONAL) ────────
  "evidence": {
    "risk_level": "string|null",           // runtime's own risk classification
    "uncertainty": 0.0,                     // e.g. normalized entropy [0,1]
    "expected_effects": [ ],                // dry-run / simulator output
    "attestation": { },                     // device/runtime attestation
    "citations": [ ]                        // grounding refs, if any
  },

  // ── HUMAN CONTEXT — routing, not authority (OPTIONAL) ────────────
  "human_context": {
    "linked_ticket": "string|null",         // change-management ref (SoD)
    "approvals": [ ]                         // approvals bound to action_digest
  },

  // ── CONTEXT BUNDLE — ONLY for an ActionGate+ContextMin pipeline (OPTIONAL) ──
  // See §4: not universal; degrades to no-op if spans lack `contrib`.
  "context_bundle": null,

  // ── PROVENANCE — recorded, NEVER in the identity digest (OPTIONAL METADATA) ──
  "provenance": {
    "runtime": "string",            // "langgraph/0.x", "openai-agents/1.x", "claude-code", ...
    "model": "string",              // model id, if known
    "objective": "string",          // free-text task label; advisory only
    "correlation_id": "string"      // session/trace correlation
  },

  // ── POLICY REFERENCE — which enterprise policy to judge against (MANDATORY) ──
  "policy_ref": { "version": "string", "digest": "string" }
}
```

---

## 3. Field classification: mandatory / optional / never

| Class | Fields | Why (FACT-anchored) |
|---|---|---|
| **MANDATORY** | `principal`, `action.{tool,operation,targets,arguments,reversibility}`, `authority`, `policy_ref` | Exactly the inputs ActionGate's predicates read to decide (`gate.py:46–234`). Every action-taking runtime can supply them. |
| **STRONGLY RECOMMENDED** | `state_binding` | Enables ACP operational safety + TOCTOU closure. Absent → ACP abstains (fail-closed), not bypass. |
| **OPTIONAL** | `evidence`, `human_context`, `context_bundle`, `provenance.*`, `principal.on_behalf_of` | Raise scrutiny or enable extra layers; never lower a bar. |
| **DERIVED** | `action_digest` | Pure function of `action`; computed by adapter/CP, not runtime-supplied. |
| **MUST NEVER EXIST** | `prompt`, `system_message`, `reasoning_trace`, `chain_of_thought`, `scratchpad`, `memory_state`, `conversation_history`, `planning_graph`, `reflection_state`, `model_weights`, `sampling_params`, `orchestration_internal` | `FACT`: grep of the Control-Plane decision paths found zero references to any of these (`../ai_control_plane_v3/02_...`). Governance must never depend on runtime internals. |

---

## 4. The one non-universal field: `context_bundle`

**FACT.** Context Minimization requires ActionGate-shaped spans (`SemanticUnit.contrib`, a single action `base`, a frozen `source_type` taxonomy) and its guarantee is computed against ActionGate specifically; generic text yields a *vacuous* guarantee (`compressor.py:36–58`, `units.py:41`, `extractor.py:76–79`).

**RECOMMENDATION.** `context_bundle` is **optional and pipeline-specific**, not part of the universal contract. A runtime not using ActionGate spans sets it to `null` and loses nothing governance-critical. Do not require it; do not present it as universal context governance. The adapter must **refuse to certify** a compression whose invariance signature is constant (fail-loud), so misuse cannot masquerade as a passing guarantee.

---

## 5. Why this schema is genuinely vendor-neutral

**INTERPRETATION, tested against the design rules.**
- It contains **no field only the Ugence runtime can produce.** `evidence.uncertainty` (Ugence's raw-entropy strength) is optional, not mandatory — a runtime without it simply omits it.
- Every MANDATORY field is a property of *an action a runtime is about to take*, which every agent framework has by definition (they all "wire a model to a tool-calling loop," `FACT`: `ACTIONGATE_VC_BRIEF.md:21–22`).
- Provenance is recorded but identity-excluded, so the *same action* from OpenAI, LangGraph, or Claude Code yields the *same* `action_digest` and the *same* verdict — the property that makes it a shared standard rather than a Ugence API.

**Falsification check.** The one way this schema fails vendor-neutrality is if a runtime cannot express its action as `{tool, operation, targets, arguments}`. The only hard case (`EXTERNAL KNOWLEDGE`) is a free-form **code executor** (AutoGen running arbitrary code): the "action" is opaque until executed. Handling: the adapter marks `operation: EXECUTE`, `reversibility: UNKNOWN`, and relies on a Control-Plane `SIMULATE_AND_RETRY` / dry-run to classify effects before authorizing — the action is still expressible, just at coarse granularity. This is an adapter cost, not a schema failure.
