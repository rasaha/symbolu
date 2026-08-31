# Part 1 — The Runtime Contract

**Milestone:** AI Control Plane V3 — runtime-agnostic governance. Design-first research; no production code, no implementation.
**Question under test:** can the AI Control Plane govern *any* autonomous runtime, or only Ugence's? This part designs the minimal interface a runtime must expose so the Control Plane never depends on runtime internals.

Labels: `FACT` (repo evidence, cited) · `INTERPRETATION` · `RECOMMENDATION` · `EXTERNAL KNOWLEDGE`.

Evidence base: the three input-contract falsification audits summarized in `02_RUNTIME_INDEPENDENCE_AUDIT.md`, plus the prior milestones in `../agentic_framework_review/` and `../agent_runtime_v2/`.

---

## 1. Design principle: the Control Plane pulls; the runtime pushes only the action

**FACT.** The Control Plane's three components consume very little from the runtime:
- **ActionGate** consumes a **canonical action envelope** and decides purely from the action + authority + enterprise-signed policy + externally-supplied state/evidence/approvals. Its decision logic reads none of: prompt, reasoning, memory, planner, reflection, model family, orchestration (grep-confirmed absence; `gate.py:46–234`).
- **ACP** consumes a **`CanonicalActionCandidate`** and evaluates it against a **`CanonicalWorldState`** that ACP obtains from a **`WorldStateProvider`** — i.e., from the *domain/environment*, **not** from the runtime (`symbolu_robotics/autonomous_control_plane/interfaces.py:24–36`).
- **Policy** is authored out-of-band by an enterprise root-of-trust, **not** by the runtime (`policy.py:5–6,105–120`).

**INTERPRETATION — the load-bearing insight.** Governance does not ask the runtime for the world, the policy, or its internal reasoning. It asks the runtime for exactly one thing: *the exact action it wants to commit, plus who is asking.* Everything else (world state, policy, live safety facts) the Control Plane pulls from the environment and the enterprise. This is why the contract can be minimal and why runtime-independence is even possible.

---

## 2. The minimal contract — the Execution Proposal

**RECOMMENDATION.** The one object that crosses the runtime→Control-Plane boundary. Fields are classified MANDATORY / OPTIONAL / MUST-NOT-EXIST, each justified by what the Control Plane code actually reads.

```
ExecutionProposal {

  // ── MANDATORY (ActionGate reads these to decide) ─────────────────
  principal            // agent_identity{id, key_id, sig} — WHO is acting
  requested_action {   // WHAT exactly is to be done
    tool               // tool{server_id, tool_name}
    operation          // enum from the frozen operation taxonomy
    target_resource[]  // what it acts on
    arguments          // the decision facts (sole source of fact extraction)
  }
  credential_scope     // {principal, permissions, ttl} — the authority requested
  state_binding {      // closes the time-of-check/time-of-use gap
    current_state_hash
    state_freshness{as_of, source}
  }
  authority_chain {    // delegation_chain[], delegator{id,type} — privilege provenance
  }
  reversibility        // enum — consequence class
  policy_version       // which enterprise policy this was evaluated against

  // ── OPTIONAL (raise scrutiny or enable extra layers; never lower a bar) ──
  risk_evidence        // scrutiny-only; ActionGate evidence that can only tighten
  expected_outcome     // expected_effects — simulator/dry-run output
  rollback_plan        // for reversibility gating
  linked_ticket        // change-management reference (SoD)
  attestation          // device/runtime attestation as EVIDENCE
  approvals[]          // human approvals bound to this action's identity
  context_bundle       // only if Context Minimization is in the pipeline (see §4)

  // ── DERIVED (computed by canonicalization; not runtime-supplied) ─────────
  execution_identity   // action_hash = H(canonical bytes of the action) — DERIVED

  // ── MUST-NOT-EXIST (runtime internals; governance must never depend on) ──
  // prompt / system_message / chat_template
  // reasoning_trace / chain_of_thought / scratchpad
  // memory_state / conversation_history
  // planning_algorithm / reflection_algorithm
  // model_weights / temperature / sampling_params
  // orchestration_graph / framework_internal_state
}
```

**FACT grounding for the field set:** the MANDATORY fields are exactly the fields of ActionGate's canonical action envelope that its predicates actually read — `arguments` (fact extraction, `gate.py:46–70`), `credential_scope`+`delegation_chain` (privilege monotonicity, `gate.py:105–111`), `state_freshness` (staleness, `gate.py:123–125`), `reversibility` (`MAX_IRREVERSIBILITY`, `gate.py:230–232`), `linked_ticket` (SoD, `gate.py:114–120`), plus ACP's `CanonicalActionCandidate` (`envelopes.py:44–83`). The OPTIONAL fields are the ones that "can only raise scrutiny, never lower a hard invariant" (`ACTIONGATE_VC_BRIEF.md`).

---

## 3. The three fields that expose runtime identity (handle with care)

**FACT.** ActionGate's envelope currently *requires and hashes* three fields that describe the producing runtime: `runtime`, `model_provider`, `objective` (`schema.py:40–46`, `projection.py:44–46`). They are **decision-inert** — no predicate branches on them (`objective` is "Tier-3 advisory only," `ACTION_GATE_SPECIFICATION.md:49`). But because they sit *inside the hashed payload*, two runtimes emitting an otherwise-identical action produce **different `action_hash` values**.

**INTERPRETATION.** This is the single concrete place where the current contract is *runtime-specific by construction*: an approval bound to `action_hash` under runtime A will not match the same action from runtime B. It is a provenance-vs-identity design choice, not a governance dependency.

**RECOMMENDATION.** For a runtime-agnostic contract, move `runtime`/`model_provider`/`objective` **out of the identity projection** and into non-identity metadata — exactly the pattern ACP already uses for its `provenance` field (`envelopes.py:62`: `metadata={"identity": False}`). Then the action identity is a pure function of *what is being done*, not *who produced it*, and approvals/evidence become portable across runtimes. (See Part 11, risk R3.)

---

## 4. Context Bundle — optional, and coupled (do not over-promise)

**FACT.** Context Minimization is **not** a general context-governance layer for any runtime. It consumes a pre-segmented `Context` of `SemanticUnit` spans whose load-bearing field `contrib` is keyed to ActionGate's request-spec, and its preservation guarantee is computed by, and defined against, the ActionGate gate specifically (`compressor.py:17,36–58`; `units.py:41`; brief `:509`). A generic agent feeding it contrib-less text gets a "silently vacuous guarantee" (audit finding).

**RECOMMENDATION.** In the universal contract, `context_bundle` is **optional** and only meaningful when the runtime is willing to (a) segment its context into ActionGate-shaped spans and (b) run inside an ActionGate authorization pipeline. It is a *pipeline optimization*, not part of the mandatory governance contract. Do not require it for runtime-independence; do not market it as universal context governance. (See Part 5 and Part 12.)

---

## 5. The smallest contract that works

**RECOMMENDATION — the irreducible minimum** for the Control Plane to govern an action with **zero** dependence on runtime internals:

> **`principal` + `requested_action{tool, operation, target_resource, arguments}` + `credential_scope` + `state_binding`.**

Everything else is optional enrichment (evidence, expected outcome, context bundle) or enterprise/domain-supplied (policy, world state). With this five-field core, ActionGate can render an authorization verdict and ACP — given a domain `WorldStateProvider` — can render an operational-safety verdict, and neither ever learns how the action was reasoned into existence.

**FACT — this is falsifiable and was tested.** The audits confirmed that ActionGate's `evaluate()` is a pure function of exactly these inputs plus policy/evidence/approvals/now, and that ACP's interfaces consume only candidate+world (`02_RUNTIME_INDEPENDENCE_AUDIT.md`). The contract above is not aspirational; it is the contract the code already implements.
