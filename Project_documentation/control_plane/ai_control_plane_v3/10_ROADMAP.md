# Part 10 — Roadmap

If runtime independence is feasible, design the roadmap. (It is feasible for the authorization + operational-safety spine — Part 2, Part 12 — so the roadmap follows.)

Labels: `FACT` (current state) · `RECOMMENDATION` · `INTERPRETATION`. Design-stage plan; no implementation is part of this milestone.

---

## 0. Starting point (FACT)

- ActionGate + ACP decision logic is runtime-independent (proven); ACP ran unchanged across robotics + cloud (proven in code).
- Context Minimization is ActionGate-coupled (proven).
- No non-Ugence runtime has been driven end-to-end; ActionGate transport is in-process/planned; only the K8s connector is validated; everything shadow-only, no production.
- The Execution Proposal contract exists as a design (Part 1), not a shipped interface.

---

## Stage 1 — Ugence Runtime only (prove the seam internally)

**RECOMMENDATION.** Before any external runtime, harden the contract with the one runtime you control.
- Implement the **Execution Proposal** as the real boundary object between Agent Runtime V2 and ActionGate/ACP (from `../agent_runtime_v2/`).
- **Demote `runtime`/`model_provider`/`objective` out of the ActionGate identity hash** into non-identity metadata (Part 1 §3, Part 11 R3) — the prerequisite for cross-runtime portability.
- Wire the Ugence Runtime's risk signals (raw-entropy, `ToolRiskClassifier`) as ActionGate evidence.
- Ship a real **network transport** for the proposal (today in-process) — the hard prerequisite for any remote runtime.
- Exit criterion: the Ugence Runtime proposes → ActionGate authorizes → ACP safety-checks → executes with a minted token, end-to-end, on the real K8s connector.

## Stage 2 — Partner runtime adapters (prove universality empirically)

**RECOMMENDATION.** Falsify or confirm universality (Part 7 §4) with real foreign runtimes.
- Build the **MCP adapter first** (universal shortcut — one adapter, many runtimes; the repo already prototypes it). Harden it for real credential brokering (FACT: current MCP adapter is "bypassable without network + credential isolation").
- Build a **LangGraph adapter** (strong pause/resume via checkpointer).
- Run the **universality test** (Part 7 §4): same enterprise action from Ugence, MCP-native, and LangGraph runtimes → assert identical `action_hash` + identical verdict.
- Exit criterion: a non-Ugence runtime's action is authorized and safety-checked with byte-identical results to the Ugence path. **This is the milestone that moves the verdict from PARTIALLY to UNIVERSAL.**

## Stage 3 — Open Runtime API (make the contract a product)

**RECOMMENDATION.**
- Publish the **Execution Proposal schema** and the verdict/token protocol as a documented, versioned open interface.
- Provide an **adapter SDK** (the checklist in Part 3 §2, as code) so third parties build their own adapters.
- Add **per-domain ACP adapters** beyond cloud/robotics (finance/healthcare/business-process world-models) so operational safety generalizes.
- Add **multi-tenant policy administration** (rotation, scoping, isolation) on top of the existing `policy_bundle` scoping.
- Exit criterion: a third party integrates a runtime Ugence never saw, using only public docs + the adapter SDK.

## Stage 4 — Enterprise AI Governance Platform

**RECOMMENDATION.**
- **Shared multi-runtime, multi-tenant Control Plane** (Part 8): internal + vendor + robot + cloud + BP agents under one authority, differentiated only by signed policy.
- **Rate/quota isolation** so one runtime cannot starve the shared gate (activate the dormant limiter).
- **Governance-grade audit + replay** as a first-class product surface (ActionGate already has the tamper-evident record; expose it).
- **Context Minimization** shipped as an ActionGate-pipeline feature (honestly scoped, Part 9), not as universal context governance.
- Exit criterion: an enterprise runs untrusted vendor agents against production under the same deterministic boundary as internal agents.

---

## Roadmap on one timeline

```
Stage 1  Ugence-only seam   ──▶  Stage 2  Partner adapters   ──▶  Stage 3  Open Runtime API  ──▶  Stage 4  Governance Platform
 (contract + transport +        (MCP + LangGraph adapters,       (public schema + adapter        (multi-runtime, multi-tenant,
  identity fix, native e2e)      universality test PASS)          SDK + domain adapters)           vendor-agent isolation)
        │                              │                                 │                                │
   verdict stays              verdict moves PARTIALLY→               universality                    platform GA
   PARTIALLY_SUPPORTED         (approaching) UNIVERSAL               productized
```

---

## Gating logic (INTERPRETATION)

- **Stage 1 is the honesty gate.** No external-runtime claim is credible until the seam and transport work with the runtime Ugence controls. The identity-hash fix is small but load-bearing (without it, cross-runtime approvals don't port).
- **Stage 2 is the verdict gate.** The universality test (Part 7 §4) is the single experiment that converts "architecturally supported" into "demonstrated." Until it passes, marketing must say "designed to" not "does."
- **Stages 3–4 are productization**, not architecture — they scale a proven seam to many runtimes, tenants, and domains.

**FACT-anchored feasibility.** The roadmap is feasible because the hardest thing — runtime-independent decision logic — is already proven in code (Part 2). What remains is transport, adapters, a small identity fix, domain world-models, and multi-tenant admin: all engineering, no architectural unknowns. The one genuine research question (does a foreign runtime produce an identical verdict?) is answered by the Stage-2 test, not by more design.
