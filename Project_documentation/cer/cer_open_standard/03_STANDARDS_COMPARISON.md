# Deliverable 6 — Comparison with Existing Standards

Where CER overlaps, where it is fundamentally different, and — critically — **what it should reuse rather than reinvent**. Compared: OpenAPI, OCI, MCP, OAuth, Kubernetes CRDs, CloudEvents, Git, Terraform Plan.

Labels: `INTERPRETATION` · `RECOMMENDATION` · `EXTERNAL KNOWLEDGE` (standards' designs are general knowledge to a Jan-2026 cutoff).

---

## 1. The comparison

| Standard | What it standardizes (EXTERNAL KNOWLEDGE) | Overlap with CER | Fundamental difference |
|---|---|---|---|
| **OpenAPI** | a vendor-neutral *description of an API surface* | the idea of a neutral schema describing invocable operations; CER's `tool`/`operation` is OpenAPI-adjacent | OpenAPI describes *capability* (what can be called); CER describes *one committed request + its authority* (an instance, governed). Description vs governed instance. |
| **OCI** | content-addressed artifacts by **digest**; any runtime pulls/runs identically | **the core identity mechanism** — CER's `action_digest` is OCI's digest idea applied to actions | OCI addresses *artifacts*; CER addresses *actions-plus-authority*. Same content-addressing, different content. |
| **MCP** | protocol for a model to *discover and call tools* | **the actuation boundary + transport** — CER is emitted *at* the MCP `tools/call` seam | MCP standardizes the *call*; CER standardizes *whether the call may commit*. MCP has no authority/identity/verdict model. **Complementary, not competing.** |
| **OAuth** | delegated, scoped, revocable *authority* (tokens/scopes) | **the authority model** — `credential_scope` + single-use token is OAuth-shaped | OAuth grants a *session/role* scope; CER binds authority to *one exact action, once*. Tighter than OAuth (per-action, not per-session). |
| **K8s CRDs** | declarative, schema-validated *desired-state objects* an admission controller reviews | **the admission-review shape** — a control plane admits/denies a CER like an admission webhook reviews a CRD | CRDs are *desired state* reconciled by a loop; CER is a *pre-commit action request* judged once. Reconciliation vs pre-commit gate. |
| **CloudEvents** | a **vendor-neutral envelope** for events; fixed attributes, producer-defined `data` | **the envelope + domain-profile structure** (Deliverable 2) — the closest structural relative | CloudEvents describes *something that happened* (past); CER describes *something to be authorized* (future, governed). Notification vs governed request. |
| **Git** | content-addressed, tamper-evident *history* (hash-chained) | **the audit chain** — ActionGate's hash-chained audit + CER `audit.prev_digest` is Git-like | Git versions *content*; CER's chain versions *decisions*. |
| **Terraform Plan** | a **reviewable diff of intended changes**, approved before `apply` | **the strongest behavioral analogy** — propose-review-then-commit; a Terraform plan is essentially a CER for infra, reviewed by a human/policy before apply | Terraform Plan is Terraform-specific and its "policy" (Sentinel/OPA) is bolted alongside; CER is runtime- and domain-neutral and puts authority/safety *in the contract*. |

---

## 2. The two closest relatives — and what they teach

**INTERPRETATION.**
- **CloudEvents is the structural template.** It solved *exactly* CER's TF4 problem (universal envelope, domain-specific payload) and did it as a successful CNCF open standard with multiple vendor implementations. CER should copy its governance and structure wholesale: a small fixed attribute set + extension attributes + content-mode for the `data`/action, with domain profiles as the analog of CloudEvents "extensions/profiles."
- **Terraform Plan is the behavioral template.** It proved enterprises *want* a reviewable, machine-checkable artifact of "what will change" before it changes — and that policy-as-code (Sentinel/OPA) reviewing that artifact is a viable enterprise control. CER generalizes Terraform's plan→policy→apply from one tool to *any agent action*. `RECOMMENDATION`: pitch CER to enterprises as "Terraform Plan for agent actions" — a concept regulated buyers already understand.

---

## 3. Could CER reuse existing standards? — **Yes, and it must (falsification TF1/TF2 mitigation)**

**RECOMMENDATION — CER should be a *composition of existing standards*, not a greenfield format.** This is the single biggest adoption-cost reducer:

```
CER =
  CloudEvents envelope      (identity, attributes, content-mode)      ← reuse
  + OCI-style digest        (action_digest, algorithm-agility)        ← reuse the pattern
  + OAuth-shaped authority  (scoped, delegable, but per-action)       ← reuse the model
  + MCP transport/boundary  (where the CER is emitted)                ← reuse
  + JCS/RFC-8785 canon      (already in-repo: jcs.py)                 ← reuse (FACT)
  + a small NEW schema:     action(operation-class + profiled body) + verdict contract
```

**INTERPRETATION.** Almost nothing in CER is genuinely new. The *only* new normative content is (a) the universal operation-class taxonomy, (b) the per-action (not per-session) authority binding, and (c) the verdict/composition contract. Everything else is a profile of formats the industry already runs. This matters enormously for the open-standard question: **you are not asking OpenAI or Google to adopt a new wire format — you are asking them to emit a CloudEvents-shaped envelope, at their MCP boundary, with an OCI-style digest and OAuth-style scope.** That is a plausible ask; a brand-new format is not.

**The risk of reuse (name it):** composing five standards means inheriting five standards' evolution and five committees' politics. `RECOMMENDATION`: pin specific versions in a CER profile and treat upstream changes via capability negotiation (Deliverable 9), rather than tracking each upstream live.
