# Ugence AI Control Plane — Productization Roadmap
### Internal / data-room document — not for first investor contact

> **Terminology update — Ugence Decision Governance (2026-08-01).** Per
> [`Project_documentation/repository/docs/architecture/ADR_UGENCE_DECISION_GOVERNANCE_TERMINOLOGY_AND_BOUNDARIES.md`](../docs/architecture/ADR_UGENCE_DECISION_GOVERNANCE_TERMINOLOGY_AND_BOUNDARIES.md):
> the canonical **umbrella** is **Ugence Decision Governance**; the **AI Control Plane** named in this
> title is the **optional, bypassable** administration & coordination layer, not the umbrella and not a
> universal authority. The "Decision Governance kernel" listed below is the **Decision Authority**
> capability (`decision_governance` package, name unchanged). **Model Selection** is a distinct
> capability, separate from Hybrid LLM. Documentation-only; nothing is renamed.

*Purpose: answer the question every investor asks after the first look — "what
exactly must be built, in what order, by whom, and in how many months?" — and derive
the pre-seed round size **bottom-up** rather than by convention.*

> **How to use this document.** It converts the implemented, internally-validated
> modules (see the Ugence Technical Evidence Catalogue) into one enterprise-
> deployable v1 product over an **18-month** plan. Every cost figure marked
> **⟨assumption⟩** is an illustrative placeholder to be replaced with a real quote
> before circulation. The round size is the *output* of the model in §8, not an
> input.

---

## 1 · Starting point — current reusable components

What already exists and can be reused, versus what must be built to make it a
product. (Maturity labels per the Technical Evidence Catalogue.)

| Component | Reuse status | What is proven today |
|---|---|---|
| **ActionGate** | Reusable core | Deterministic action authorization; 274 tests; 27/27 red-team blocked; Kubernetes surface |
| **Autonomous Control Plane (ACP)** | Reusable core | Operational-safety clearance; runtime-independent; cross-domain; shadow-only against fixtures |
| **Decision Governance kernel** | Reusable core | Version-frozen kernel (v1.0.0); AI-advisory/human-binding separation; identity-preserving |
| **Agent Runtime + CER contract** | Reusable core | Canonical Execution Request; identical identity across 3 real runtimes; 1,550+ tests |
| **Truth Assurance Platform (TAP)** | Partial (prototype) | Claim/scope/evidence layers prototyped on synthetic data; one layer only |
| **Context Minimization** | Reusable accelerator | Authorization-preserving compression; cross-model; frozen benchmark |
| **KVPro** | Reusable accelerator | int4_protected codec on real GPUs; ~1.8× net density |
| **Model Selection policy** | Reusable accelerator | Governed selection; passes pre-registered criteria (synthetic) |

**Read:** the *reasoning/governance mechanisms exist*. What does **not** yet exist is
the connective tissue that makes them one operable product: shared services, a
console, connectors, durable persistence, identity, and the fully-wired
decision→action→execution→reconciliation loop against live systems.

---

## 2 · Integration gaps (what must be built)

The gaps between "modules that pass tests" and "one product a customer runs":

1. **The live governed loop.** Decision Governance → CER → ActionGate → ACP →
   execution → reconciliation is proven *in parts and on fixtures*; it is not wired
   end-to-end against a live execution target. **(Highest priority.)**
2. **Shared identity & multi-tenancy.** Today: static identity stand-ins, single-host
   stores. Needed: multi-tenant identity, organization isolation, real approver
   identity.
3. **Durable, tamper-evident persistence.** Today: in-memory repositories, reference
   HMAC signing. Needed: durable append-only audit with a real hash-chain and key
   custody.
4. **Unified control surface.** No admin console today. Needed: one console for
   policy, review queues, findings, and audit reconstruction.
5. **Standard external APIs & canonical contracts.** Internal contracts exist (CER);
   needed: stable public APIs and versioned contracts across modules.
6. **Connectors.** Needed: two runtime connectors (native + one third-party adapter,
   both partly demonstrated) and one governed execution-target connector (Kubernetes).
7. **Deployment modes as product features.** Shadow / recommendation / enforcement
   exist conceptually; needed as first-class, per-control configuration.
8. **Security & observability.** External security review, access control,
   logging/metrics/tracing, deployment tooling.

---

## 3 · Shared platform services required

The services all modules will depend on (the bulk of "product consolidation"):

- **Identity & tenancy** — multi-tenant identity, org isolation, RBAC for operators,
  approver identity binding.
- **Policy service** — author/version/publish policies and rubrics with segregation
  of duties.
- **Evidence & audit service** — durable, tamper-evident, replayable records;
  reconstruction API.
- **Canonical contract layer** — CER + decision identities exposed as stable APIs.
- **Console** — operator UI for policy, review, findings, audit reconstruction.
- **Connector framework** — runtime adapters + execution-target adapters.

---

## 4 · v1 scope — ships vs deferred

| Ships in enterprise-deployable v1 | Deferred (post-v1 / domain packages) |
|---|---|
| Multi-tenant identity + org isolation | Additional systems-of-record connectors (ATS, HRIS, claims, finance) |
| Durable, tamper-evident audit | Autonomous Runtime (robotics) productization |
| Secure public APIs + canonical contracts | PSE and other adjacent IP |
| Two runtime connectors | Broad multi-cloud execution targets (AWS, GCP, Terraform) beyond Kubernetes |
| One enterprise identity integration | TAP hardened beyond first prototype layer (staged in) |
| One governed execution-target connector (Kubernetes) | Model Selection as a separately-sold product |
| Shadow + controlled enforcement for selected actions | Full regulated-industry certification |
| Console (policy · review · findings · audit) | |

**v1 anchors on the infrastructure-agent wedge** (Kubernetes execution target). TAP
enters v1 in a limited, staged form; Decision Governance ships with the hiring
reference plus one live infrastructure workflow.

---

## 5 · Quarterly milestones (18 months = 6 quarters)

| Quarter | Theme | Exit criteria |
|---|---|---|
| **Q1** | Foundations | Shared identity/tenancy scaffold; persistence + tamper-evident audit backend; API contracts frozen; team core hired |
| **Q2** | Live governed loop | End-to-end Decision→CER→ActionGate→ACP→execution→reconciliation wired against Kubernetes in shadow |
| **Q3** | Console + connectors | Operator console v1; two runtime connectors; enterprise identity integration; first design-partner in shadow |
| **Q4** | Enterprise readiness | External security review; observability/deployment tooling; controlled enforcement for selected actions; 1st pilot findings report |
| **Q5** | Pilot scale + enforcement | 2–3 paid pilots running; first shadow→enforcement conversion; second-domain kernel reuse demonstrated |
| **Q6** | v1 GA + proof | Enterprise-deployable v1 GA; ≥1 paid enforcement deployment; measured false-positive/false-block + audit-reconstruction results |

---

## 6 · Staffing plan & ramp

Small team focused on converting existing technology into a deployable product.

| Role | Start | Active months (of 18) |
|---|---|---|
| Founder (product + architecture) | M1 | 18 |
| Founding product / platform eng lead | M1 | 18 |
| Enterprise integration engineer #1 | M2 | 17 |
| Product designer / frontend (console) | M3 | 16 |
| Security & compliance lead (fractional ≈0.5 FTE) | M4 | 15 |
| Enterprise integration engineer #2 | M5 | 14 |
| Founding enterprise GTM / design-partner lead | M7 | 12 |

---

## 7 · Pilot dependencies

- **v1 loop wired** (Q2) before any enforcement; shadow can begin once identity +
  audit + one runtime connector exist (late Q2/Q3).
- **Design partner:** a GCC/enterprise with a Kubernetes-acting agent and an
  identified sponsor + approval group.
- **Access:** read-only telemetry (Prometheus/cluster state) for shadow; scoped
  credentials for controlled enforcement.
- **Data processing / security sign-off** from the partner before enforcement mode.

---

## 8 · Bottom-up budget → round size

> **All figures ⟨assumption⟩ — replace with real quotes (Hyderabad market, actual
> cloud/GPU usage, real vendor bids).** FX ⟨assumption⟩ ≈ ₹83 / US$1. The round size
> is the model's output.

### 8a · Payroll (fully-loaded, 18 months)

| Role | ⟨assumption⟩ ₹/month | Active mo | Total (₹L) |
|---|---:|---:|---:|
| Founder | 2.0 | 18 | 36.0 |
| Product / platform eng lead | 3.3 | 18 | 59.4 |
| Integration engineer #1 | 2.1 | 17 | 35.7 |
| Integration engineer #2 | 2.1 | 14 | 29.4 |
| Product designer / frontend | 1.9 | 16 | 30.4 |
| Security & compliance (0.5 FTE) | 1.25 | 15 | 18.8 |
| GTM / design-partner lead | 2.5 | 12 | 30.0 |
| **Payroll subtotal** | | | **≈ ₹239.7L (₹2.40 Cr · ~$289K)** |

### 8b · Non-payroll (18 months)

| Category | ⟨assumption⟩ Total (₹L) |
|---|---:|
| Cloud + GPU (dev, KVPro benchmarking, pilot infra) | 36 |
| External security review / pen-test | 15 |
| Legal / IP / patents / incorporation | 20 |
| Pilot integration & travel (2–3 partners) | 15 |
| Tools / SaaS / infra | 10 |
| GTM / marketing / events | 10 |
| **Non-payroll subtotal** | **≈ ₹106L (~$128K)** |

### 8c · Total and round size

| Line | ₹ | US$ |
|---|---:|---:|
| Payroll subtotal | 2.40 Cr | ~$289K |
| Non-payroll subtotal | 1.06 Cr | ~$128K |
| **Subtotal** | **3.46 Cr** | **~$417K** |
| Contingency (15%) | 0.52 Cr | ~$63K |
| **18-month total** | **≈ 3.98 Cr** | **≈ $480K** |

**Working-estimate pre-seed raise: ≈ ₹5 Cr (~US$600K)** — the 18-month total plus
buffer, sized to reach the **first paid enforcement deployment** with runway to
spare rather than to the next unfinished prototype.

> **This is a working estimate, not a confirmed raise.** Every §8 input is an
> ⟨assumption⟩. The final amount will be set once Hyderabad hiring, cloud/GPU
> infrastructure, security/compliance, and legal/IP costs are replaced with current
> quotes. Directionally reasonable; not yet validated.

**Allocation vs the first-look 55 / 25 / 20 split** (sanity check, at ₹5 Cr):
Product consolidation ~₹2.75 Cr · Enterprise readiness ~₹1.25 Cr · Commercial
validation ~₹1.0 Cr — consistent, since product-role payroll dominates.

---

## 9 · Product acceptance criteria (v1 "done")

v1 is complete when, for the Kubernetes infrastructure-agent wedge:

1. A proposed agent action flows Decision→CER→ActionGate→ACP→execution→reconciliation
   **end-to-end against a live target**, with each stage recorded.
2. Multi-tenant identity + org isolation enforced; approvals bound to real approver
   identity.
3. Audit records are durable, tamper-evident, and reconstruct a complete decision
   chain on demand.
4. Shadow, recommendation, and enforcement modes are per-control configurable.
5. Two runtime connectors + one Kubernetes execution-target connector operate in a
   customer environment.
6. An external security review is passed at an agreed bar.
7. ≥1 paid pilot has produced a findings report; ≥1 control has run in enforcement.

---

## 10 · Risks & contingency

- **Integration underestimated** — the live loop (Q2) is the critical path; slip here
  cascades. *Mitigation:* wire the thinnest end-to-end path first; harden later.
- **Pilot access latency** — enterprise security sign-off can be slow. *Mitigation:*
  start shadow (read-only) early; sequence enforcement after trust is built.
- **Hiring in a competitive market** — *Mitigation:* fractional security/compliance;
  contractors for surge; stagger starts (see §6).
- **Scope creep into new domains** — *Mitigation:* v1 is Kubernetes-only; all other
  systems-of-record are explicitly deferred (§4).
- **Cost assumptions** — every figure in §8 is ⟨assumption⟩; the round should be
  re-derived once real quotes land.

---

*Companion to the Ugence AI Control Plane — Investor First Look and the Ugence
Technical Evidence Catalogue. Internal / data-room use.*
