# Roadmap — Agent Action Admissibility Gate (beachhead of record)

**Status:** the forward plan. The **concrete product of record is
`AGENT_ACTION_ADMISSIBILITY_MVP.md`.** Context and prior analysis:
`GAP_REGISTER.md`, `COMBINED_ARCHITECTURE_BCVF2_USE_SCC.md`, `BCVF_CONCEPT_DIRECTION.md`,
`USE_CONTRIBUTION_MAP.md`, `CRITICAL_TRANSITION_GOVERNANCE.md`, `kill_study/`.

**Rev. 4 (reconciliation with the MVP spec).** Established the **agent-action admissibility
gate** as the beachhead of record; restated the near-term product precisely (§0); repositioned
Organizational State Governance / Critical Transition Governance as a *possible later
generalization*, not the immediate product (§6); replaced the critical-path dependency graph
with the agent-gate build order (§3); reclassified prior work (§5). The earlier human-fraud /
attestation / OSGE phasing from Rev. 2–3 is **retained only as later-generalization context**,
not as the critical path. Revs 2–3 are preserved as history at the bottom.

---

## 0. Product of record (near-term)

> **A vendor-neutral pre-commit admissibility gate at the autonomous-agent tool-invocation
> boundary, initially governing production-infrastructure actions.**

Full specification: `AGENT_ACTION_ADMISSIBILITY_MVP.md`. The gate permits a consequential action
only when the proposed transition leaves the system inside a **conservatively enforceable
approximation of the safe viability kernel**. It **wins by safely allowing more legitimate
autonomy** than static permissions or approve-everything workflows — not merely by blocking more.

**Architectural sequence:**
```
agent proposes action
  → canonical action envelope
  → deterministic invariant checks            (hard, non-compensatory)
  → conservative viability approximation       (Viab̂(A) — under-approximation, not exact)
  → simulation / blast-radius evidence         (evidence, with fidelity classes)
  → allow / constrain / escalate / deny
  → audited commit
```

---

## 1. Supersession & continuity

- The MVP **narrows, it does not contradict**, the earlier architecture. The four-layer analysis
  (evidence → consequence → decision → orchestration) still holds; the gate is that architecture
  **instantiated for one concrete transition class.**
- **Production-infrastructure agent actions are the first concrete transition class** — the
  enumerated critical transitions of the prior threat-model step, made specific and buildable.
- **OSGE / Critical Transition Governance remains a *potential* end-state**, pursued **only after
  the beachhead is validated** (§6).
- **The gate must prove value independently of BCVF, USE, and SCC.** They are optional evidence
  modules, off the critical path (§5). The core viability gate must remain useful with all of
  them removed.

## 2. How we got here (condensed continuity)

```
BCVF (detector)         → refuted as a primary detector (kill_study)
USE / SCC (evidence)    → optional evidence modules, unproven / commodity
consequence-gating      → the right OBJECTIVE: act on expected loss, not anomaly
critical-transition gov → authorize consequential TRANSITIONS, not just users
agent-action gate       → the one buildable, vendor-neutral, chokepoint-defensible NARROWING
```
Detail lives in the referenced documents; this roadmap now leads with the narrowing.

---

## 3. Critical-path dependency graph

The critical path is the agent-gate build order (mapping to `AGENT_ACTION_ADMISSIBILITY_MVP.md`
§12 Stages 0–6). It does **not** include broad OSGE / systems-of-record integration.

```
[C1] canonical action-envelope schema                                  (MVP §2; Stage 0)
      → [C2] hard-invariant policy language + root of trust            (MVP §4; Stage 1)
          → [C3] deterministic gateway on ONE prod-infra tool surface  (MVP §5,§9; Stage 1)
              → [C4] credential brokering + bypass resistance          (MVP §9; Stage 1)
                     └─ enforcement, NOT monitoring, requires C4
                  → [C5] simulator / blast-radius integration          (MVP §5,§6; Stage 2)
                      → [C6] human approval + signed audit             (MVP §7,§8; Stage 3)
                          → [C7] OPERATIONAL EVALUATION vs policy-as-code
                                 & approve-everything baselines         (MVP §11; Stage 6)  ← thesis gate
      (parallel, optional) [O1] advisory semantic reasoning, escalate-only (MVP §5 Tier 3; Stage 4)
      (after single-surface proof) [E1] runtime-neutral MCP + non-MCP expansion (MVP §9; Stage 5)
```

**Thesis gate = C7 (the operational kill criterion, MVP §11):** the MVP is *not supported*
unless it prevents materially more unsafe *composite* actions than conventional policy-as-code
**and** auto-admits materially more legitimate actions than approve-everything — both by a
preregistered practical margin `Δ_min`, within preregistered delay / human-review / bypass
bounds. `O1` and `E1` are off the critical path and each must earn its place on the same test.

---

## 4. Explicit constraints (preserved, non-negotiable)

- **AI is advisory and safety-monotone**: it may only *escalate* assurance.
- **AI cannot override a hard invariant or approve a critical action**, and cannot lower required
  assurance or modify policy.
- **MCP is one integration opportunity, not an architectural dependency**; the policy and action
  model stay runtime-neutral (MCP + non-MCP).
- **Enforcement without credential control and egress restriction is monitoring, not
  enforcement** — envelope interception alone must be labeled as such.
- **Exact viability is not claimed.** The implementation uses a **conservative
  under-approximation** `Viab̂(A)`; the gap to true viability is the escalation region. **No claim
  of formal verification over the open world, and no novel mathematics** (viability /
  invariant-preservation + reachability + constraint logic applied to the agent action boundary).
- **BCVF, USE, SCC, and behavioral biometrics are optional evidence modules and are NOT on the
  MVP critical path.**

---

## 5. Reclassification of prior work

| Prior workstream | New status |
|---|---|
| Consequence-aware orchestration (expected-loss, `V·ρ`) | **Retained inside the gate's assurance policy** (escalation by reversibility / blast-radius / freshness; MVP §7) |
| Critical-transition governance / OSGE | **Retained as a later platform expansion** (§6), after beachhead validation |
| Liveness / attestation | **Retained as evidence and hard-gate inputs where applicable** (envelope `attestation_evidence`; freshness invariants; MVP §2,§4) |
| BCVF / USE / SCC | **Optional incremental experiments only** — off the critical path; each must pass the same `Δ_min` test or be dropped |
| Broad horizontal enterprise integration (systems-of-record) | **Deferred** — not part of the MVP; end-state only |

The product's security **does not wait on** BCVF, USE, SCC, biometrics, or novel liveness.

Effort concentrates on the C1→C7 critical path (envelope, hard invariants + root of trust,
enforcement chokepoint with credential brokering, simulation/blast-radius, human approval +
audit, operational evaluation). Optional intelligence (`O1`) and multi-runtime expansion (`E1`)
are funded only after the single-surface deterministic gate proves out.

---

## 6. Later generalization (not the immediate product)

Once the agent-action beachhead is validated at C7, the same admissibility abstraction can
generalize toward **Critical Transition Governance / OSGE** (`CRITICAL_TRANSITION_GOVERNANCE.md`):
broader transition classes, human-initiated critical transitions, systems-of-record integration
(ITSM / IAM / CI-CD / ticketing), and richer advisory semantic reasoning — all under the same
advisory + escalate-only + deterministic-policy + human-approval constraints (§4).

This is a **possible end-state, explicitly gated on beachhead success.** Broad horizontal
enterprise governance moves the competitive frame into GRC / policy-as-code / PAM / change-
governance (incumbent-held) and requires heavy integration; it is **not** the near-term product
and must not precede the MVP.

**Positioning of the near-term product (honest):** the defensible position is the **vendor-neutral
pre-commit chokepoint** governing agents on any model/runtime (the "neutral layer in a
multi-vendor world" pattern). Value lives in **enforcement + policy authority + cross-runtime
neutrality + calibrated consequence analysis**, not in any protocol adapter. Two first-class
risks (MVP §12): **protocol/runtime absorption** (admissibility becoming native to MCP/runtimes —
stay runtime-neutral, win on enforcement and neutrality) and **adoption timing** (demand is
incident-/compliance-driven; early buyers are risk-averse verticals).

---

## 7. Immediate next actions

1. **C1 — Canonical action-envelope schema** (`AGENT_ACTION_ADMISSIBILITY_MVP.md` §2) plus the
   ten concrete transitions (§10). *Largely specified; formalize as the machine schema.*
2. **C2 — Hard-invariant policy language + out-of-band root of trust** (§4).
3. **C3 — Deterministic gateway on ONE production-infrastructure tool surface** (Tier-1 checks +
   hard invariants; §5, §9) — real enforcement, no AI, no simulation.
4. **C4 — Credential brokering + egress control** so the gate is enforcement, not monitoring (§9).
5. Then **C5 (simulation/blast-radius) → C6 (human approval + signed audit) → C7 (operational
   evaluation vs policy-as-code and approve-everything).**

Off the critical path, funded only after C3–C4 prove out: `O1` advisory semantic reasoning
(escalate-only), `E1` MCP + non-MCP expansion, and any BCVF/USE/SCC evidence experiment (each on
the `Δ_min` drop-or-keep test).

Central message: **build the deterministic single-surface admissibility gate first (C1–C4),
prove it enforces (credential control) and that it beats policy-as-code on safety while beating
approve-everything on autonomy (C7). Everything else — semantic reasoning, multi-runtime, OSGE
generalization, and every behavioral evidence module — is optional and gated on that result.**

---

## Appendix — history (Rev. 2–3, superseded framing)

Retained for continuity; **not** the current critical path.

- **Rev. 2** (adaptive security orchestration): four-layer model (evidence → consequence →
  decision → orchestration); threat-modeling-first; commodity attestation vs novel liveness split;
  "Evidence Innovation Lane"; safety-monotone real-time agentic orchestration. These concepts
  survive **inside** the gate's assurance policy and constraints (§4, §5).
- **Rev. 3** (Critical Transition Governance / OSGE): reframe from authenticating identities to
  authorizing consequential organizational state transitions. **Repositioned** as the later
  generalization (§6), explicitly gated on the agent-action beachhead.
- The human-authentication / fraud-prevention phasing and the `G−1…G5` gates from those revs
  described a *different* (human-session) beachhead and are **not** part of the agent-action
  critical path. Where their ideas survive, they are reclassified in §5.
