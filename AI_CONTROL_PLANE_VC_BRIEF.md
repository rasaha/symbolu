# AI Control Plane — VC / Technical Brief

**Ugence Labs | AI Control Plane**
*Runtime-independent governance for autonomous AI: authorize the exact action, then clear it against live operational safety — the same way across every runtime.*
*Version 1.0.0 — July 2026 (external / evidence-based)*

> **Product family.** The AI Control Plane is the **governance platform** in the Ugence Labs
> portfolio. It governs execution requests produced by the **Ugence Agent Runtime** (its native
> reference producer, see `AGENTIC_FRAMEWORK_VC_BRIEF.md`) **and by third-party runtimes** via
> the Canonical Execution Request (CER) contract. This is the broader platform moat; the runtime
> is one (native) producer in front of it. The canonical platform architecture — **Specialized AI
> Systems · AI Control Plane · AI Infrastructure** — is defined in `UGENCE_PLATFORM_OVERVIEW.md`.

---

## Page 1 — The Problem

### Every runtime governs differently; enterprises need one answer

Enterprises are deploying autonomous agents on many runtimes at once — LangGraph in one team, a
hosted cloud agent in another, a home-grown loop in a third. Each runtime couples **planning,
tool selection, policy checks, and execution** in its own loop, and each exposes a **different
action representation and enforcement seam**. So the questions a risk, security, or compliance
team must answer have a *different* answer per runtime:

- *What exactly is about to happen — as a stable, signed object?*
- *Who authorized this specific action; can that authorization be replayed or transferred?*
- *Is it operationally safe against live state right now, independent of who generated it?*
- *Can we prove the thing that executed is the thing that was authorized?*

You cannot certify, insure, or audit an autonomous fleet when the answer depends on which
framework happened to generate the action. **Governance must be decoupled from generation** and
made **runtime-independent** — one control plane in front of many runtimes.

### The Ugence answer

The **AI Control Plane** governs a runtime-independent object — the **Canonical Execution
Request (CER)** — through three composable layers:

1. **Context Minimization** *(where applicable)* — reduce the decision to the minimal governed context.
2. **ActionGate** — **authorize the exact action** (identity, RBAC, privilege monotonicity,
   separation-of-duties, approvals, evidence, replay protection, policy operators).
3. **Autonomous Control Plane (ACP)** — decide whether the authorized action is **operationally
   safe against live state right now**, and compose that with the authorization.

The runtime proposes; the Control Plane decides whether and how it executes; the governed result
returns to the runtime. The Control Plane never generates actions and never depends on which
runtime produced them.

---

## Page 2 — Architecture

```
   CER (from any runtime: Ugence-native or third-party via adapter)
        │
        ▼
   Context Minimization   ── minimal governed context (where a span contract exists)
        │
        ▼
   ActionGate             ── AUTHORIZE the exact action
     • action identity (content hash, provenance-excluded)
     • RBAC · privilege monotonicity · separation-of-duties
     • approvals & evidence bound to the action hash
     • replay protection (nonce + state) · policy operators
        │  verdict: ALLOW / ALLOW_WITH_CONSTRAINTS / DENY / escalate / more-evidence
        ▼
   ACP operational safety ── SAFE-NOW against live state?
     • per-domain deterministic safety checks (blast radius, freeze,
       state-drift, capacity, replication, rollback-available, …)
        │  recommendation: PROCEED / HOLD / REOBSERVE
        ▼
   Composition            ── PROCEED · BLOCKED_BY_AUTHORIZATION · PENDING_AUTHORIZATION · HELD_BY_ACP
        │
        ▼
   Governed execution result ──► back to the runtime (observation / memory / reflection)
```

Two non-negotiable invariants: **an ActionGate denial is never overridden by ACP**, and **ACP
can only hold — it can never mint authorization**. An action proceeds **iff both layers pass**.

### Exact-action authorization (the core primitive)

CER identity is the **content hash of the action** under a versioned identity profile that
**excludes provenance** (which runtime, model, or objective produced it). Consequences:

- The **same actuation from different runtimes produces the same action identity** — so one
  authorization decision applies regardless of producer.
- **Any material change to the action changes the identity** — approvals and evidence bind to the
  hash and **fail closed** if the action is modified after approval.
- **Evidence and approvals cannot transfer** across different actions or domains.
- Identity is **stable from proposal → authorization → operational clearance → execution** — you
  can prove the thing that executed is the thing that was authorized.

### Operational-safety composition (per-domain, deterministic)

ActionGate answers *"is it authorized?"*; ACP answers *"is it safe against live state now?"*.
ACP's core is **domain-neutral**; each domain adds a thin deterministic safety adapter (e.g.
Kubernetes: blast radius, freeze window, readiness, state-drift; database: reachability,
affected-row bound, transaction capacity, replication, migration conflict, state-version drift,
rollback-available). The composition and its outcome set are shared and unchanged across domains.

---

## Page 3 — Evidence (what has been proven)

All results are from our own repository and CI on real components — not third-party benchmarks.

### Runtime independence & cross-runtime interoperability
- **Three real runtimes** — the native Ugence runtime, **LangGraph** (1.2.9, real StateGraph +
  ToolNode interception), and the **OpenAI Agents SDK** (0.18.2, real Runner + tool-call
  interception) — produce **identical action identity** for the identical actuation, with
  different provenance.
- **No runtime-specific branch in the control plane** — ActionGate and ACP contain zero runtime
  tokens; the Control Plane receives only the CER. Verified by an ownership scan in CI.

### Cross-domain governance
- **Two Kubernetes profiles** — `kubernetes.scale.v1` and `kubernetes.rollout.v1` — governed
  end-to-end, distinct non-colliding identities.
- **A materially different domain — `database.mutation.v1`** — governed by the **existing**
  ActionGate operation taxonomy (`DB_MUTATION`/rule R7) with **0 lines changed** in ActionGate,
  plus a new deterministic database operational-safety adapter reusing the frozen composition
  core **unchanged**. All four composed outcomes reproduce in the database domain.

### Independent implementability (the standard is real)
- A **clean-room** second implementation of CER — written from the published spec, importing
  none of the reference code, standard-library only — reproduces **byte-identical** normalized
  payloads, canonical bytes, and digests across the entire existing corpus. **0 identity-affecting
  specification ambiguities** across 77 differential items + a 29-case cross-domain corpus.

### Security invariants (all hold)
Exact-action binding; no cross-domain evidence/approval transfer; no cross-profile identity
collision; provenance cannot alter identity; ActionGate DENY is final; ACP cannot authorize;
stale state invalidates eligibility; no secret enters identity/logs/vectors; no runtime branch in
the frozen core; no bypass to the real tool executor in governed mode.

### CER V0.3 verdicts (per pre-registered thresholds)
`CER_INDEPENDENT_IMPLEMENTATION_CONFORMANT` · `CER_CROSS_DOMAIN_SUPPORTED` ·
`CONTROL_PLANE_CROSS_DOMAIN_SUPPORTED` · `CER_SECURITY_INVARIANTS_HOLD` ·
`CER_V0_3_READY_FOR_PUBLIC_REPOSITORY`. **No standards-body or industry-adoption claim.**

### Honest limitations (shadow / reference)
- ACP runs against **authored fixtures** in these results (no live cluster / live database
  telemetry); it is **shadow-only** and actuates nothing.
- ActionGate uses **reference HMAC signing**, not production asymmetric key custody.
- Two actuation domains proven (Kubernetes + database); database DELETE reserved for a future
  profile. Deterministic producers (no live LLM in the conformance runs).
- **ActionGate/ACP are not authoritative in production** in this state — they are a reference
  control plane with a proven contract, not a certified deployment.

---

## Page 4 — Positioning, moat, roadmap, ask

### Positioning
- **Governable across Ugence and third-party runtimes.** The value is that one governance layer
  fronts many runtimes through CER — the Ugence Agent Runtime is the *native* producer; others
  integrate via a CER adapter SDK.
- **CER is a versioned interoperability contract implemented by the Ugence AI Control Plane** —
  **not** an industry standard already adopted by the market.

### Moat
- **Runtime-independent, exact-action authorization** with a versioned, provenance-excluded
  identity — proven identical across three real runtimes.
- **Operational-safety composition** with domain-neutral core + thin deterministic per-domain
  adapters — extended to a new domain with **0 core changes**.
- **Independently implementable contract** — a clean-room implementation reproduces byte-identical
  identity, evidence a real standard exists (not one vendor's code).
- **Native producer coupling** with the Agent Runtime, plus an adapter path for the rest of the market.

### Roadmap
**Near term** — production asymmetric signing & key custody; live-cluster and live-database ACP
paths; CER conformance suite + adapter SDK; audit-log persistence and export.
**Medium term** — additional domains (filesystem / generic HTTP with versioned ActionGate
operations); third independent CER implementation (different language); design-partner pilots.
**Later** — managed control-plane service; certification (e.g. SOC 2) on the managed offering; an
independent conformance program.

### The ask
Fund **AI Control Plane commercialization**: ActionGate and ACP hardening, CER conformance and
adapters, live pilots, and production signing/audit infrastructure. This is the platform-level
asset; the Agent Runtime brief funds the native producer separately. The two are complementary:
the runtime makes rich canonical requests; the Control Plane governs whether and how they execute
— across every runtime, not just ours.

---

*Contact: Rakesh Mohan — Ugence Labs*
*Repo: `rasaha/symbolu` · Components: `cyber_security/action_gate_reference/` (ActionGate) · `symbolu_robotics/autonomous_control_plane/` (ACP) · `cer_v0_1/` `cer_v0_2/` `cer_v0_3/` (CER)*
*Positioning: AI Control Plane · runtime-independent governance · CER = versioned interoperability contract (not an adopted standard)*
