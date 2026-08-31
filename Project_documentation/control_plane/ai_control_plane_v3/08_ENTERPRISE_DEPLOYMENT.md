# Part 8 — Enterprise Deployment Model

Many runtimes → one shared AI Control Plane → shared Infrastructure. Can heterogeneous agents (internal, vendor, robot, cloud, business-process) safely share one governance layer?

Labels: `FACT` (repo evidence) · `INTERPRETATION` · `RECOMMENDATION`.

---

## 1. The deployment topology

```
   ┌── RUNTIMES (heterogeneous, each with its own adapter) ──────────────┐
   │  internal agents  vendor agents  robot agents  cloud agents  BP agents│
   └───────┬───────────────┬─────────────┬────────────┬───────────┬───────┘
           │ adapter        │ adapter      │ adapter     │ adapter    │ adapter
           ▼                ▼              ▼             ▼            ▼
   ┌────────────── SHARED AI CONTROL PLANE (multi-tenant) ─────────────────┐
   │  Context Minimization (optional, per ActionGate pipeline)             │
   │  ActionGate   — one policy root-of-trust, per-tenant/per-domain policy │
   │  ACP          — per-DOMAIN world-model adapters (cloud, robotics, …)  │
   │  Composition  — one identity-bound verdict per action                 │
   └───────┬───────────────────────────────────────────────────────────────┘
           │ verdict + single-use token/credential
           ▼
   ┌────────────── SHARED INFRASTRUCTURE ─────────────────────────────────┐
   │  KVPro (KV efficiency)   ·   Cloud Scaling Controller (safe autoscale)│
   └───────────────────────────────────────────────────────────────────────┘
```

---

## 2. Can heterogeneous agents safely share one governance layer? YES — and the code already argues why.

**FACT-anchored — the four properties that make sharing safe:**

1. **Every action is identity-bound and per-action authorized.** ActionGate authorizes *one exact action, once*, bound to `action_hash` with a single-use nonce (FACT: `gate.py`). Two agents (internal + vendor) attempting different actions get independent verdicts; neither can replay or ride the other's authorization. Sharing the gate does not share authority.

2. **The gate is a pure function of the action + policy + state.** It holds no per-runtime session state that could leak between tenants (FACT: `evaluate()` purity, `gate.py:144–148`; `used_nonces` passed in). A shared gate is safe precisely because it is stateless-per-call.

3. **Policy is per-tenant/per-domain under one root-of-trust.** Enterprise-signed policy bundles are scoped and versioned (FACT: `policy.py:82–93`; `policy_bundle` scoping global<tenant<domain<env from the prior review). One Control Plane can enforce different policies for internal vs vendor vs robot agents without code changes — only different signed bundles.

4. **ACP evaluates per-domain against live state.** A robot agent's action is checked against robotics world-state; a cloud agent's against cluster state — via different `WorldStateProvider` adapters over the *same frozen core* (FACT: cross-domain reuse, `cloud/adapter.py`). One ACP core, many domain adapters.

**INTERPRETATION.** The Control Plane is *designed* to be multi-runtime and multi-tenant because it consumes only canonical actions + scoped policy + domain world-state — none of which is coupled to a specific runtime (Part 2). Sharing is not a retrofit; it is the natural consequence of the input contract.

---

## 3. The five agent classes, mapped

| Agent class | Runtime | Governance path (FACT-anchored) |
|---|---|---|
| **Internal agents** | Ugence Runtime (native adapter) | full pipeline; tightest policy |
| **Vendor agents** (3rd-party, less trusted) | LangGraph/CrewAI/etc. via adapter | **same gate, stricter policy bundle + mandatory attestation**; vendor identity as `principal`; ActionGate's compromised-agent isolation is the key control (FACT: `action_gateway_isolated` proved 27/27 attacks blocked) |
| **Robot agents** | robotics runtime | ActionGate (authorization) + **ACP robotics adapter** (native operational safety) |
| **Cloud agents** | ops/IaC runtime | ActionGate + **ACP cloud adapter** (native; consumes `cloud_controller`) |
| **Business-process agents** | RPA/workflow runtime | ActionGate authorization; ACP only if the BP touches a stateful system with a world-model |

**RECOMMENDATION — the vendor-agent case is the strongest enterprise argument.** A shared Control Plane lets an enterprise run *untrusted third-party agents* against production systems with the same deterministic, credential-controlling boundary it uses for internal agents — differing only by a stricter signed policy. This is precisely the "compromised agent" threat model ActionGate's isolated variant already validated (FACT). No runtime-side guardrail can offer this, because the vendor controls the runtime.

---

## 4. Isolation and multi-tenancy requirements (honest gaps)

**FACT — what is proven vs what is needed:**
- **Proven:** deterministic per-action authorization; compromised-agent isolation via netns/user/mTLS/Ed25519 in the isolated variant (FACT: `ISOLATED_GATE_THESIS_SUPPORTED`, 27/27 attacks blocked); credential brokering so agents never hold durable secrets.
- **Needed (not yet built — FACT/RECOMMENDATION):**
  - A **network transport** for the proposal (today in-process/planned) so remote runtimes can reach the shared gate.
  - **Per-tenant policy isolation at scale** — the scoping model exists (`policy_bundle`) but multi-tenant admin/rotation is not built.
  - **Per-domain ACP adapters** for non-cloud/robotics domains (finance/healthcare/BP) — the core is cross-domain but each new domain needs its world-model.
  - **Rate/quota isolation** so one runtime can't starve the shared gate (a facade exists in the framework; not wired).

**INTERPRETATION.** The deployment model is architecturally sound and the hardest safety property (compromised-agent isolation) is the one already demonstrated. What is missing is *productization* (transport, multi-tenant admin, more domain adapters), not a safety-architecture gap. This shapes the roadmap (Part 10) and the risks (Part 11).

---

## 5. Deployment conclusion

**INTERPRETATION.** Heterogeneous agents can safely share one Control Plane because safety is enforced **per action, per identity, per policy, per domain-world-state** — none of which is shared or coupled across runtimes. The shared layer is safe *because* it is a stateless-per-call deterministic function over canonical actions. The enterprise value is highest exactly where runtime-side governance is weakest: **untrusted vendor agents and cross-domain (robot + cloud) fleets under one authorization authority.**
