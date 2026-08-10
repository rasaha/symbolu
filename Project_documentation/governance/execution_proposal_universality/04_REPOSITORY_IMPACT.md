# Deliverable 8 — Repository Impact

Every place in the repository that currently assumes "our runtime," and whether the assumptions disappear under the Execution Proposal contract. Would ActionGate / ACP / Context Minimization / AI Infrastructure change?

Labels: `FACT` (grep/source-verified this milestone) · `INTERPRETATION` · `RECOMMENDATION`.

---

## 1. Does the Control Plane assume "our runtime"? — Investigation results

**FACT — the Control Plane imports nothing from the Ugence runtime.** A grep for `import ... agentic_framework` / `from agentic` across `acp/`, all `cyber_security/action_gate*` packages, `experiments/actiongate_context_ablation/`, and `symbolu_robotics/autonomous_control_plane/` returned **no matches** (excluding tests). The governance code has zero compile-time dependency on the Agent Runtime.

**FACT — the producer is already abstracted as a generic "reader."** The end-to-end pipeline names the runtime slot "**LLM stage (reader)**," implemented by a **`MockReaderClient`** — "a DETERMINISTIC rule-based reader used ONLY to validate plumbing" (`experiments/actiongate_context_ablation/llm_client.py:138`; `Project_documentation/control_plane/acp/END_TO_END_CONTROL_PLANE_SPEC.md:22`). The reader's contract is: *read the proposed action from the surviving context spans → emit a canonical operation or `INSUFFICIENT_CONTEXT`.* It is a **placeholder for any runtime**, not the Ugence runtime.

**FACT — the only real coupling is DOMAIN-shaped, not RUNTIME-shaped.** The reader emits a `KubernetesOperation` (`Project_documentation/control_plane/acp/END_TO_END_CONTROL_PLANE_SPEC.md:23,61`). That is a *domain* action type (K8s), swappable per domain, exactly as ACP swaps envelope schemas across robotics/cloud (`FACT`: `../ai_control_plane_v3/`). It does not assume a particular *runtime*.

**FACT — "current runtime authoritative" ≠ "our Agent Runtime."** Phrases like "ACP shadow-only; current runtime authoritative" (`Project_documentation/control_plane/acp/ACP_PHASE2_PREREGISTRATION.md:8`, etc.) refer to the **incumbent production control system** (e.g., the real HPA/actuator) being authoritative while ACP runs in shadow — not to the Ugence Agent Runtime. This is a wording collision to avoid misreading.

---

## 2. Where the (minor) runtime-shaped assumptions live, and their fate

| Location | Assumption today (FACT) | Fate under the contract |
|---|---|---|
| `experiments/actiongate_context_ablation/llm_client.py` `MockReaderClient` | a stand-in "reader" produces the proposed action | **Replaced by the adapter output** — any runtime's adapter emits the proposal; MockReader was always a placeholder. Disappears (becomes one of many producers). |
| `Project_documentation/control_plane/acp/END_TO_END_CONTROL_PLANE_SPEC.md` "LLM stage (reader)" | the pipeline has a single reader slot | **Generalizes** — the "reader" slot becomes "any runtime + adapter." The slot stays; its sole-occupant assumption goes. |
| Reader emits `KubernetesOperation` | K8s-shaped action | **Domain, not runtime** — stays for the K8s domain; other domains define their own action type. No runtime assumption to remove. |
| Context Minimization `base {tool, verb, target}` + `SemanticUnit.contrib` | ActionGate-shaped spans | **ActionGate coupling, not runtime coupling** (`FACT`). Unchanged; Context Min remains an ActionGate-pipeline optimization. |
| ActionGate envelope hashes `runtime`/`model_provider`/`objective` | provenance in identity | **Must change (small):** demote to non-identity metadata so cross-runtime IDs collide (del. 5, K8). This is the *one* concrete code-level change the contract requires. |

---

## 3. Would each component change?

| Component | Change required? | Detail (FACT/INTERPRETATION) |
|---|---|---|
| **ActionGate** | **Minimal.** | One real change: exclude `runtime`/`model_provider`/`objective` from the identity projection (`projection.py:44–46`) so the same action from different runtimes yields the same `action_hash` (del. 5). Everything else — the pure-function evaluator, the 24-field envelope, the policy model — is already runtime-agnostic (`FACT`: `../ai_control_plane_v3/`). No decision-logic change. |
| **ACP** | **None.** | ACP already consumes only candidate+world, imports nothing runtime-specific, and ran unchanged across two domains (`FACT`). It never saw "our runtime" to begin with. New runtimes = new adapters upstream, invisible to ACP. |
| **Context Minimization** | **None (scope clarification only).** | Stays an ActionGate-coupled optional layer. `RECOMMENDATION`: add the fail-loud guard for a vacuous `context_bundle` (del. 1) so non-conforming runtimes fail visibly. No structural change. |
| **AI Infrastructure (KVPro, Cloud Scaling Controller)** | **None.** | Infrastructure sits *below* the verdict (executes what's authorized) and is already runtime-agnostic — KVPro is a vLLM backend path, the Cloud Controller governs autoscaling. Neither references a runtime. Unaffected. |
| **The Agent Runtime** | **Repositioned, shrinks.** | It becomes *one adapter-emitter among many* (`../execution_proposal_engine/`). Its internal soft-authorization duplicates (World B PDP, etc.) are removed (`FACT`: prior review). Net: less surface. |

---

## 4. Conclusion

**FACT-anchored.** The repository is **already ~95% runtime-independent on the Control-Plane side**: zero runtime imports, a generic reader seam, and only a domain-shaped (not runtime-shaped) action type. The Execution Proposal contract does **not** require re-architecting ActionGate, ACP, Context Minimization, or Infrastructure. It requires:
1. **One small ActionGate change** — demote provenance out of the identity hash (del. 5).
2. **Replacing the `MockReader` placeholder** with real adapter outputs (`02_...`) — additive, not a rewrite.
3. **A fail-loud guard** on Context Minimization's vacuous-guarantee case — hygiene, not structure.

**INTERPRETATION.** This is a strong, non-obvious result of the falsification: the architecture is not something Ugence must *build toward* — the Control Plane is *already* built as if the runtime were interchangeable (a `MockReader` slot), because the milestones that produced it deliberately kept the runtime out. The contract mostly *names and hardens* a separation the code already has. The dangerous work is not in the repo (it's ~ready); it is in the *adapters* and the *empirical demonstration* (del. 9).
