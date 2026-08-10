# Part 2 — Runtime Independence Audit

The central falsification test. For Context Minimization, ActionGate, and ACP, do they depend on the runtime's **prompt format · reasoning strategy · memory architecture · planning algorithm · reflection algorithm · model family · orchestration implementation** — or only on the execution proposal? Every dependency is labeled **RUNTIME-INDEPENDENT**, **RUNTIME-SPECIFIC**, or **UNKNOWN**.

Labels: `FACT` (code/spec evidence, cited) · `INTERPRETATION`. This audit was conducted by reading the actual input contracts and grepping the decision paths, not from the marketing briefs.

---

## 1. The dependency matrix

Rows = the seven runtime-internal concepts the milestone names. Columns = the three Control Plane components. Cell = the independence label + the decisive evidence.

| Runtime-internal concept | Context Minimization | ActionGate | Autonomous Control Plane (ACP) |
|---|---|---|---|
| **Prompt format** | RUNTIME-INDEPENDENT — input is a pre-segmented `Context`, no template/chat parser (`compressor.py`, grep clean) | RUNTIME-INDEPENDENT — no prompt field read; grep clean (`gate.py`) | RUNTIME-INDEPENDENT — consumes `CanonicalActionCandidate`, no prompt (`interfaces.py:57–126`) |
| **Reasoning strategy** | RUNTIME-INDEPENDENT — grep clean (`compressor.py`) | RUNTIME-INDEPENDENT — "no AI, no broad consequence reasoning" (`gate.py:5`) | RUNTIME-INDEPENDENT — decision from candidate+world only |
| **Memory architecture** | RUNTIME-INDEPENDENT *for the runtime's memory*; RUNTIME-SPECIFIC to ActionGate's **span schema** (`SemanticUnit.contrib`, `units.py:41`) | RUNTIME-INDEPENDENT — no memory field | RUNTIME-INDEPENDENT — stateless per tick; world injected |
| **Planning algorithm** | RUNTIME-INDEPENDENT | RUNTIME-INDEPENDENT — the only "planner" token is a disclosure trust-level, not an algorithm (`remediation.py:38–42`) | RUNTIME-INDEPENDENT — "ACP consumes a planner," is not one (`Project_documentation/control_plane/acp/ACP_ARCHITECTURE.md`) |
| **Reflection algorithm** | RUNTIME-INDEPENDENT | RUNTIME-INDEPENDENT — grep clean | RUNTIME-INDEPENDENT |
| **Model family** | RUNTIME-INDEPENDENT (genuine) — "gate, not the reader, computes preservation… holds across model families" (brief `:237–239`); regex tokenizer, not a model BPE (`units.py:28–33`) | RUNTIME-INDEPENDENT as control; `model_provider` is required+hashed but **decision-inert** (`projection.py:44–46`) | RUNTIME-INDEPENDENT |
| **Orchestration implementation** | RUNTIME-INDEPENDENT — grep clean for langgraph/crewai/autogen | RUNTIME-INDEPENDENT — "transport- and framework-agnostic" by design (`ACTIONGATE_VC_BRIEF.md:76`) | RUNTIME-INDEPENDENT — imports no agent SDK/ROS/K8s client |

**INTERPRETATION.** Across 21 cells, the decision logic of all three components is RUNTIME-INDEPENDENT with respect to *how the action was produced*. The only RUNTIME-SPECIFIC couplings are in *data-schema* rows, not *decision-logic* rows — and they are concentrated in Context Minimization.

---

## 2. Do they depend only on the execution proposal? Component verdicts.

### 2.1 ActionGate — RUNTIME-INDEPENDENT (strong)

**FACT.**
- `gate.evaluate(envelope, signed_policy, *, evidence, approvals, now, used_nonces, algorithm_id)` is a **pure function** — clock is passed in; no globals, env, network, or wall-clock in the decision path (`gate.py:144–148`).
- The decision reads only `arguments`, `credential_scope`, `delegation_chain`, `reversibility`, `state_freshness`, `linked_ticket`, evidence, approvals, and the enterprise-signed policy (`gate.py:46–234`).
- Grep for `prompt|reasoning|memory|reflection|orchestrat|langgraph|crewai|autogen|temperature|model_family`: **zero** matches in the decision path.
- Policy is authored out-of-band by a root-of-trust; the runtime is a policy *subject*, never its author (`policy.py:5–6,105–120`).
- A foreign framework can construct a valid envelope; the gate never branches on which framework produced it (audit Q6).

**RUNTIME-SPECIFIC residue (data only):** `runtime`, `model_provider`, `objective` are required + hashed but **never read by any predicate** — provenance labels, control-inert (`schema.py:40–46`, `projection.py:44–46`). Their presence in the hash creates a cross-runtime approval-portability wrinkle (Part 11, R3).

### 2.2 ACP — RUNTIME-INDEPENDENT core, DOMAIN-SPECIFIC adapters (strong)

**FACT.**
- Every ACP interface consumes only `CanonicalActionCandidate` + `CanonicalWorldState` (+ constraints/versions/clock); none names a prompt, model, memory, reasoning trace, or agent identity (`interfaces.py:24–180`).
- The one field that could carry generator info — `CanonicalActionCandidate.provenance` — is free-text and **explicitly excluded from identity** (`envelopes.py:62`, `ACP_CANONICAL_IDENTITY.md:37`). ACP structurally cannot condition its decision on which runtime produced the action.
- Identity is a generic content hash: `sha256("acp\x1f{domain}\x1fv{version}\x1f" + canonical_json(value))` (`identity.py:107–111`).
- **The core ran byte-for-byte unchanged across two domains** — the same `LexicographicActionSelector`, `ReferenceCommitRevalidator`, identity function, and error hierarchy decide both a robotics motion candidate and a K8s scale/rollout candidate (`cloud/adapter.py:35–36,155–156,224`; `cloud/envelopes.py:1–8,21–22`). **This is the load-bearing precedent for domain/runtime independence, and it is real in code.**
- ACP imports **nothing** from ActionGate — only an opaque `AuthorizationVerdict` enum token (`cloud/composition.py:28,38–49`).

**DOMAIN-SPECIFIC (not runtime-specific):** the envelope field schemas, constraint predicates, tie-break sort keys, and recommendation mappings differ per domain (cloud vs robotics). This is a *world-model* requirement — operational safety cannot be judged without a model of the domain's live state — not a coupling to the agent runtime.

### 2.3 Context Minimization — RUNTIME-INDEPENDENT to the runtime, RUNTIME-SPECIFIC to ActionGate (split)

**FACT.**
- **Independent of the agent framework and the downstream model:** grep clean for prompt/template/chat/memory/reasoning/orchestration/langgraph/crewai/autogen; token counting is a regex tokenizer, not a model BPE (`units.py:28–33`); the model-portability claim is genuine because the gate, not the reader, computes preservation (brief `:237–239`).
- **Coupled to ActionGate as the fixed oracle:** the invariance signature reads ActionGate's exact decision record — `outcome`, `dispositive_rules`, `applied_constraints`, and the canonical envelope (`compressor.py:17,36–58`; `adapter.py`). The oracle is **not pluggable**; swapping it requires rewriting `_eval` + `signature` + `adapter`.
- **Coupled to an ActionGate-shaped span schema:** a span is a `SemanticUnit` whose load-bearing `contrib` maps to ActionGate request-spec fields (`units.py:41`, `extractor.py:45–79`); `source_type` is a frozen 15-type taxonomy (`units.py:22–26`); the context needs a single action `base{tool,verb,target}` (`units.py:62–65`).
- **Silent-degradation failure mode:** a generic runtime feeding contrib-less text makes `oracle_spec` merge nothing, so the signature is constant across ablations → the invariance check becomes a no-op → the guarantee is vacuous (`extractor.py:76–79`; audit Q6).

**INTERPRETATION.** Context Minimization is best understood as a *component of the ActionGate authorization pipeline*, not as an independent context-governance layer that any runtime can adopt. Its "true for any reader" claim is about downstream *models*, not about being pluggable into any *runtime's* context governance. The brief is internally honest about this (`:509`, `:559` = "integrate as a pre-read context stage in the ActionGate runtime").

---

## 3. UNKNOWNs (honest gaps)

| Item | Why UNKNOWN | Evidence |
|---|---|---|
| Whether an arbitrary **third-party runtime** can drive the full pipeline end-to-end | Both demonstrated domains are driven by this repo's own deterministic offline reader / `MockReader`; no external agent framework has actually produced a candidate | `END_TO_END_CONTROL_PLANE_SPEC.md:22–25`; ACP audit caveat |
| Whether the **end-to-end identity chain** generalizes | Its current instantiation uses K8s + ActionGate digest conventions and "LLM stage" wording — confined to the integration binding, but not yet exercised for a non-Ugence runtime | `CONTEXT_TO_ACTION_IDENTITY_BINDING.md`; `KUBERNETES_OPERATION_IDENTITY_BINDING.md:29–33` |
| Whether a **live transport** carries the proposal | ActionGate transport is in-process/planned; only the K8s connector is validated; the MCP adapter is "bypassable without network + credential isolation" | prior review; `action_gateway_mcp` README |

**INTERPRETATION.** The UNKNOWNs are all *empirical/maturity* gaps (nobody has plugged in LangGraph yet; no network transport shipped), not *architectural* couplings. The architecture *permits* runtime-independence and the code *demonstrates domain-independence*; what is unproven is a live external runtime, not a hidden dependency.

---

## 4. Audit conclusion

**FACT-anchored.**
1. **ActionGate + ACP decision logic is runtime-independent** — proven by pure-function analysis, grep-confirmed absence of runtime concepts, `provenance`-excluded-from-identity, and byte-for-byte cross-domain reuse.
2. **Context Minimization is runtime-independent *toward the runtime and the model* but coupled to ActionGate** — it is a pipeline optimization, not a universal governance layer.
3. **The residual couplings are (a) three decision-inert provenance fields hashed into ActionGate's identity, (b) ACP's principled per-domain world-model adapters, and (c) Context Minimization's ActionGate-specific oracle+schema.** None of these is a dependency on the runtime's prompt/reasoning/memory/planning/reflection/model/orchestration.

This audit is the evidentiary spine of the verdict in Part 12.
