# Deliverable 11 — Repository, Product & Pitchbook Impact

Assume CER becomes official. What changes — nothing, everything, or something precise? Covers runtime, ActionGate, ACP, Context Minimization, Infrastructure, product positioning, pitchbook.

Labels: `FACT` (repo-verified) · `INTERPRETATION` · `RECOMMENDATION`.

---

## 1. Code impact — mostly *nothing*, one small fix (extends `../execution_proposal_universality/04`)

| Component | Change | Detail (FACT) |
|---|---|---|
| **ActionGate** | **One small change** | Exclude `runtime`/`model_provider`/`objective` from the identity projection (`projection.py:44–46`) so cross-vendor digests collide (Deliverable 3; threat T3). Decision logic unchanged. |
| **ACP** | **None** | Already consumes only candidate+world; imports nothing runtime-specific; ran unchanged across 2 domains (`FACT`). |
| **Context Minimization** | **None (add a guard)** | Stays optional/ActionGate-coupled; `RECOMMENDATION`: add fail-loud on a vacuous `context_bundle` (T-guard). |
| **Infrastructure (KVPro, Cloud Controller)** | **None** | Below the verdict; already runtime-agnostic. |
| **Runtime (Agent Runtime)** | **Repositioned, shrinks** | Becomes *one CER emitter among many*; internal soft-authorization duplicates removed (`FACT`: prior review). |
| **New: adapter tier + conformance suite** | **Additive** | Declarative MCP adapter first (`action_gateway_mcp` seed, `FACT`); donate the existing conformance vectors (`fixtures/conformance_vectors.json`, `FACT`). |

**FACT-anchored conclusion:** the repository is *already* built as if the runtime were interchangeable (the `MockReader` seam, zero runtime imports). CER becoming official **does not require re-architecting the Control Plane** — it requires one identity fix, a fail-loud guard, and building the adapter/conformance ecosystem. This is the strongest evidence that the standard is a *naming and hardening* of a separation the code already has, not a rebuild.

---

## 2. Product positioning impact — a genuine inversion

**FACT (the current framing).** The pitchbook sells "governance as a **runtime contract, not middleware**" where the contract is *internal to the Ugence runtime* — "the execution ordering `cancel → budget → approve → execute` is pinned by the test suite" (`docs/XOZENCE_PITCHBOOK.md:827,853`), and "we control both the adapter interface" (`:781`). Governance is a *property of our runtime*.

**INTERPRETATION — CER inverts this.** If governance is an *open contract any runtime emits into*, the value proposition moves from:
- **Before:** "our runtime enforces governance as a tested contract" (runtime-centric; competes with LangGraph et al. on runtime quality — where Ugence is behind, `FACT`).
- **After:** "we steward the open governance contract *and* ship the best control plane that implements it" (contract + control-plane-centric; competitors' runtimes become emitters, not rivals).

**RECOMMENDATION.** This is a *stronger* position, but it requires the pitchbook to stop selling the runtime as the moat (Deliverable 7 of `../execution_proposal_engine/` already concluded the moat is the Control Plane, not the runtime). The repositioning: **"Ugence: the control plane for the open agent-governance standard."**

---

## 3. Pitchbook impact — what must change

**RECOMMENDATION (specific edits, no marketing language — architectural repositioning only):**
1. **Reframe the "runtime contract" claim** (`:716,827,853`) from *internal-to-our-runtime* to *the open CER standard we steward*. The `cancel→budget→approve→execute` invariant becomes an *implementation* detail of our control plane, not the product.
2. **Add CER as a portfolio primitive** — the interface between the "Specialized AI Systems" family and the "AI Control Plane" family (`../execution_proposal_engine/` Deliverable 7 diagram), now named and (proposed) open.
3. **Reposition the Agent Runtime** as the *reference emitter*, not the flagship — "bring your own runtime; ours ships pre-integrated" (`../ai_control_plane_v3/09`).
4. **Move the moat language** from "our runtime enforces the ordering" to "we run the best control plane for the standard + we steward the standard" (Deliverable 12).
5. **Keep the honest scope** — Context Minimization stays an ActionGate-pipeline feature (not universal context governance); the "universal" claim is actuation-boundary-conditioned, not intent-level (`FACT`: prior falsifications).

**INTERPRETATION.** The pitchbook change is larger than the code change. The code is ~ready; the *story* moves from "we built a governed runtime" to "we defined the governance standard and run the best implementation of it." That is a bigger, more defensible claim — but only if Ugence actually cedes the standard to neutral governance (Deliverable 12), because a pitchbook claiming "open standard" over a proprietary contract is the T4 credibility risk.

---

## 4. Net answer: "Nothing? Everything?"

**INTERPRETATION.**
- **Code: nearly nothing** (one identity fix + additive adapter/conformance ecosystem). The Control Plane is already runtime-independent.
- **Positioning: nearly everything** — the center of the story moves from the runtime to the contract + the control plane, and the runtime is demoted to a reference implementation.
- **Strategy: a real fork in the road** — CER is only "official and open" if Ugence donates governance (T4); otherwise it is an official *internal* contract with open docs. The next deliverable decides which.
