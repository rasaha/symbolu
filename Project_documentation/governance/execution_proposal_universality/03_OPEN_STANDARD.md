# Deliverable 6 — Execution Proposal as an Open Standard

Could the Execution Proposal become an open standard? Conceptual comparison to OpenAPI, OCI, MCP, OAuth, Kubernetes CRDs, and Git; and the minimum specification required.

Labels: `FACT` · `INTERPRETATION` · `RECOMMENDATION` · `EXTERNAL KNOWLEDGE`.

---

## 1. What kind of standard is it?

**INTERPRETATION.** The Execution Proposal is a **content-addressed, vendor-neutral description of an about-to-commit action, plus the authority requested for it.** Its closest conceptual relatives, and what it borrows from each:

| Standard | What it standardizes (EXTERNAL KNOWLEDGE) | What the Execution Proposal borrows |
|---|---|---|
| **OpenAPI** | a vendor-neutral *description* of an API surface so any client/tool interoperates | the idea of a neutral schema describing *what can be invoked*; the adapter is analogous to codegen from OpenAPI |
| **OCI (image/runtime spec)** | a content-addressed artifact (**digest**) that any runtime can pull/run identically | **content-addressing** — the `action_digest` is the OCI-like identity: same bytes → same digest → same behavior across runtimes |
| **MCP** | a protocol for a model to *discover and call tools* across vendors | the **actuation boundary** — MCP is where the tool-call already is; the Execution Proposal is the *governance envelope* around an MCP-style call |
| **OAuth** | delegated, scoped, revocable *authority* — a token that grants exactly a scope | the **authority model** — `credential_scope` + single-use token is OAuth-like, but bound to *one action* not a session (tighter than OAuth) |
| **Kubernetes CRDs** | a declarative, schema-validated *desired-state object* a control loop reconciles | the **declarative object** shape — the proposal is a validated resource a control plane admits/denies, like an admission-controller reviewing a CRD |
| **Git** | content-addressed, tamper-evident *history* (hash-chained commits) | the **tamper-evident identity chain** — ActionGate's hash-chained audit is Git-like; the proposal digest anchors it |

**INTERPRETATION.** The Execution Proposal is best understood as **"OCI-style content-addressing for agent actions + OAuth-style per-action authority + a K8s-admission-controller review model."** No existing standard covers *governed agent actuation*; MCP standardizes the *call*, not the *permission to commit it*. That gap is the standard's reason to exist.

---

## 2. The most important analogy: MCP is complementary, not competitive

**FACT + EXTERNAL KNOWLEDGE.** MCP standardizes *how a model calls a tool*. It does **not** standardize *whether that call is authorized, operationally safe, or bound to an identity*. The Execution Proposal sits exactly one layer up: it is the governance envelope produced *at* the MCP `tools/call` boundary (`02_RUNTIME_AUDIT_AND_ADAPTERS.md` §11).

**RECOMMENDATION.** Position the Execution Proposal as **"the governance layer MCP doesn't have."** Adopt MCP as the transport/discovery layer; define the Execution Proposal as the admission object over it. This makes adoption *additive* to the standard the industry is already converging on — the single highest-leverage strategic move (K4 mitigation, `00_...`).

---

## 3. Could third-party runtimes implement it?

**INTERPRETATION — yes, and `02_...` is the evidence:** eight non-Ugence runtimes were audited; six are SUPPORTED WITH ADAPTER and two PARTIAL, none flatly unsupported. Third-party implementation = writing the adapter (`02_...` anatomy) — the same effort as implementing an OpenAPI client or an MCP server. The bar is "expose a pre-commit interception point and normalize your action to `{tool, operation, targets, arguments}`."

---

## 4. Minimum specification required for an open standard

**RECOMMENDATION.** The spec must fix, and only fix, the following (anything more couples it to Ugence):

1. **The canonical action schema** — `{tool, operation (fixed taxonomy), targets, arguments}` + `reversibility`, with a **canonicalization profile** (JCS/RFC-8785, typed-string numerics, NFC, sorted keys) so digests are reproducible across implementations. `FACT`: this profile already exists (`jcs.py`, `hashing.py`).
2. **The identity rule** — `action_digest = H(canonical action bytes)`, with a **normative exclusion list**: provenance (runtime/model/objective), signatures, submission timestamps, and evidence MUST NOT be hashed (del. 5). This is what makes the same action from any runtime collide to one ID.
3. **The authority model** — `credential_scope` + `delegation_chain` semantics; single-use, action-bound tokens.
4. **The verdict contract** — a closed outcome set (the 6 ActionGate outcomes + the composed classes) and their meaning, so any control plane implementing the standard is interoperable with any adapter.
5. **The optional-layer contract** — `state_binding`, `evidence`, `context_bundle` as OPTIONAL, with the rule "optional fields may only raise scrutiny," and a fail-loud rule for vacuous `context_bundle`.
6. **Conformance vectors** — a fixed test corpus (action → expected digest → expected outcome) so implementations prove conformance. `FACT`: ActionGate already ships `fixtures/conformance_vectors.json`.

**What the spec must NOT fix (to stay vendor-neutral):** the reasoning/planning/memory model (runtime's business), the policy content (enterprise's business), the world-model (domain's business), the transport (MCP or otherwise).

---

## 5. Governance of the standard

**RECOMMENDATION.** For it to be a *standard* and not a *Ugence API* (the moat argument, del. 7): publish the schema + canonicalization + conformance vectors under an open spec; let the *policy*, *world-model*, and *control-plane implementation* remain competitive. Ugence differentiates on the **best control-plane implementation** (cross-domain ACP, non-compensatory determinism) and the **stewardship position**, not on owning the wire format. This is the OpenAPI/OAuth pattern: the spec is open; the best *implementations* win.

**SPECULATION (labeled).** If Ugence defines this and MCP or a foundation adopts a compatible governance envelope, the Execution Proposal could become the "OAuth for agent actions." If instead a hyperscaler ships a proprietary equivalent bundled with its cloud, the window closes. Timing and openness are the strategic variables, not feasibility — feasibility is established (`02_...`).
