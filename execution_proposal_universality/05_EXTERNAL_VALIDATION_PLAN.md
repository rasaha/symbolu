# Deliverable 9 — External Validation Plan

The strongest experiment to prove (or falsify) cross-runtime equivalence. This is the experiment that would move the verdict from `PARTIALLY_SUPPORTED` toward `SUPPORTED`.

Labels: `FACT` · `INTERPRETATION` · `RECOMMENDATION`. Design only — no implementation in this milestone.

---

## 1. The design

**One identical enterprise task**, implemented independently in five runtimes, each converted through its adapter to a canonical Execution Proposal, each run through the same Control Plane.

```
   ┌── OpenAI Agents ──┐
   ┌── CrewAI ─────────┤
   ┌── LangGraph ──────┤─▶ adapter ─▶ Execution Proposal ─▶ Context Min ─▶ ActionGate ─▶ ACP ─▶ compose
   ┌── Claude Code ────┤
   └── Ugence Runtime ─┘
                              measure at each stage:
                              proposal identity · authorization identity · operational identity · execution identity
```

**RECOMMENDATION — the task must be chosen to isolate the variable under test.** Use the domain the Control Plane already models: a **Kubernetes operation** (`FACT`: the only domain with a real ACP world-model + ActionGate connector). Concretely:

> **Task:** "The `web` deployment in namespace `protected` is under-provisioned; bring it to 3 replicas, respecting policy and safety."

Every runtime is given the same tools (the same MCP/k8s tool surface — this **controls for FF1**, the actuation-surface variable) and the same enterprise policy bundle and the same observed cluster state fixture.

---

## 2. The critical controls (or the experiment proves nothing)

**INTERPRETATION — these controls are what separate a real test from a rigged one:**
1. **Shared actuation surface (controls FF1).** All five runtimes must actuate through the *same* tool (e.g., one MCP `k8s.scale` tool), not each its own client. Otherwise IDs differ for a correct reason and the test is uninterpretable. The experiment tests *"same action, different runtimes,"* not *"same intent, different tools."*
2. **Frozen policy + frozen world-state fixture.** Same `policy_ref` and same `state_binding` inputs to every run, so authorization/operational identity isn't moved by input drift.
3. **Provenance-excluded identity (controls K8).** Run with the del. 5 fix applied (runtime/model/objective out of the hash); otherwise the proposal IDs are *guaranteed* to differ and the headline metric is meaningless.
4. **Independent implementations.** Five different engineers/prompts author the five runtime tasks, so convergence isn't an artifact of copied code.
5. **Include the two hard cases as a stretch arm.** Add AutoGen (code-exec) and Bedrock (return-control) as a *secondary* arm to test FF2/FF3 explicitly — expect these to require lower-boundary interception and possibly diverge.

---

## 3. The four measured identities and their success criteria

| Measure | Definition | Success criterion | What a failure means |
|---|---|---|---|
| **Proposal identity** | `action_digest` after provenance exclusion | **all 5 identical** | if not → a hidden field is in the hash (residual coupling) — falsifies universality |
| **Authorization identity** | ActionGate outcome + `action_hash` + dispositive rules | **all 5 identical** | if not → the gate saw different actions/authority — actuation-surface leak |
| **Operational identity** | ACP recommendation + evidence | **all 5 identical** (given identical state_binding) | if not → a runtime bound different state (FF4) — the weakest equivalence |
| **Execution identity** | composed eligibility class + (would-be) token binding | **all 5 identical** | if not → the identity chain didn't bind uniformly |

**RECOMMENDATION — report the equivalence as a lattice, not a single number.** The honest expectation from the falsification: **proposal + authorization identity should be exactly equal** across the five (they read only the action, which is controlled to be identical); **operational identity equal** only if state_binding is controlled; the AutoGen/Bedrock stretch arm may diverge at the *proposal* stage (coarser action), which is itself the finding.

---

## 4. What success would prove — and what it would NOT

**Success (all five collide on proposal + authorization + operational + execution identity):**
- `FACT`-grade proof that **the Control Plane governs five independent runtimes identically for the same actuation** — i.e., the runtime is interchangeable *at the governance interface* and the Control Plane is runtime-independent *in practice*, not just by construction. This converts the milestone-3 UNKNOWN (empirical undemonstration, K6) into a demonstrated result.

**What success would NOT prove (state these to avoid over-claiming):**
- It would **not** prove "same intent → same proposal" — the experiment *controls* the tool surface, so it proves equivalence *given* a shared surface (the honest claim, FF1/K1), not unconditional universality.
- It would **not** prove the runtimes are *equal in value* — five runtimes emitting the same governed proposal can differ enormously in *how good* that proposal is (right tool? right args? well-calibrated uncertainty?). The experiment tests interface-equivalence, not reasoning quality (del. 7).
- It would **not** prove production-readiness — it is a controlled fixture, not a live cluster with a network transport (K7).

---

## 5. The falsification value of the experiment

**INTERPRETATION — this experiment is designed to *fail loudly* if the hypothesis is wrong.** If proposal identity does *not* collapse across runtimes after the controls, the exact stage of divergence names the residual coupling:
- divergence at **proposal** → a runtime-specific field leaked into the action or its hash;
- divergence at **authorization** → the runtimes expressed different authority for the "same" action;
- divergence at **operational** → state-binding differs (FF4);
- divergence at **execution** → the identity chain is not runtime-uniform.

That diagnostic property is why this is the *strongest* experiment: it does not just seek confirmation — each possible failure points at a specific, fixable coupling. **RECOMMENDATION:** run it as the gating experiment for adopting the Execution Proposal as the official contract (del. 11); a green result is the evidence that upgrades `PARTIALLY_SUPPORTED` to `SUPPORTED`.
