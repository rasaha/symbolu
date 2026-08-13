# Ugence + ServiceNow: Product-Anchored Runtime Governance Use Cases

## A ServiceNow-product-first, pipeline-driven use-case catalog

**Version:** 1.1 (factual & positioning correction of v1.0)
**Supersedes:** v1.0 (2026-08-13)
**Companion to:** the v3.0 *Runtime AI Decision & Execution Authority* differentiation package
**Audience:** ServiceNow architecture, product, security, risk & compliance, and partnership teams
**Purpose of this document.** The v3.0 differentiation package is organized *Ugence-package-first*
("here is our module, here is the adjacent ServiceNow capability"). This companion **inverts the
lens**: it walks the **ServiceNow product catalog** one product at a time and, for each, tells a
concrete *day-in-the-life* scenario in which an AI agent crosses from **recommending** to
**deciding and acting** — then shows the exact runtime moment where the Ugence packages enforce.
Each use case is written so a ServiceNow field team can co-sell it inside a product the customer
already owns.

**Two design principles the ServiceNow representative asked for:**

1. **Broader use cases, not single-module vignettes.** Every use case below is a **pipeline**:
   multiple Ugence modules fire in sequence across one workflow (evidence → decision → model →
   exact action → clearance → execution → assurance → lifecycle). The single canonical pipeline is
   defined in §2, and each use case names the subset of modules it activates.
2. **Grounded in current ServiceNow products.** Products and capabilities were verified against
   ServiceNow-owned sources on **2026-08-13** (see the source legend, §9). This edition captures
   **important ServiceNow capabilities that the v3.0 package's Appendix F did not reflect** — AI
   Control Tower's real-time *enforcement* and *Agent Deviation Detection*, Action Fabric, the
   **Autonomous Security** portfolio (Armis + Veza), and the **ServiceNow–NVIDIA OpenShell**
   runtime-enforcement direction. **These predate v3.0's 2026-08-11 verification** — they are gaps
   in v3.0's coverage, not new market developments — and they strengthen ServiceNow's runtime
   governance, which **sharpens, not softens, the honesty guardrails** below.

---

## 0. Honesty guardrails (carried forward from v3.0 — do not relax)

This catalog inherits the discipline of the v3.0 package. A ServiceNow reviewer will circulate it
internally; one inflated claim discounts the whole document.

- **No ServiceNow connector ships.** Every ServiceNow integration named here is **PROPOSED** —
  design intent over Ugence's vendor-neutral contracts, not shipped code. No package contains a
  ServiceNow adapter today.
- **Shipped ≠ production-validated.** The Ugence packages exist and are offline-verifiable, but
  most are **reference-grade** with **production deployment validation pending** (see the v3.0
  Appendix B maturity ladder). Where a package refuses its reference stand-ins in production, this
  document repeats that boundary.
- **ServiceNow is not described as lacking AI governance.** ServiceNow governs the AI estate *and*
  an increasingly capable agentic runtime. The differentiation is **narrower and specific**, and
  the genuine overlap zones (§3, and per-use-case "Overlap, stated honestly" notes) are named as
  overlaps — not as white space.
- **Research method & source hierarchy.** The product workflows and use cases here were researched
  **primarily through official ServiceNow product documentation at `docs.servicenow.com`**, not from
  marketing pages. The authority order used was:
  1. **ServiceNow Docs (`docs.servicenow.com`)** — existing product behavior and workflow mechanics;
  2. **ServiceNow release notes** — version and availability (what ships when);
  3. **ServiceNow Newsroom** — announcements, partnerships, strategy, and *future* availability;
  4. **ServiceNow Community** — supporting and release-explanation material.
  Reputable third-party press ([3P]) is used only to corroborate announcement facts (e.g. the
  Dec-2026 SOC availability), never as a primary source of product behavior.
- **Egress caveat (honest).** In *this* build environment, direct fetches to `www.servicenow.com`,
  `docs.servicenow.com` and `docs.nvidia.com` were egress-blocked, so the above sources were reached
  via web search returning those same ServiceNow-owned (and NVIDIA-owned) pages. **Exact quotes,
  release/patch numbers, and capability names should be spot-checked on the live documentation
  before customer use.**

---

## 1. Important ServiceNow capabilities not captured in v3.0 (read this first)

The v3.0 package's Appendix F did not reflect the ServiceNow capabilities below. **They are not new
market developments** — each predates v3.0's 2026-08-11 verification (Action Fabric GA'd at
Knowledge 2026 in May; AI Control Tower's enforcement and June-2026 controls, the Autonomous
Security portfolio's design partners, and the ServiceNow–NVIDIA OpenShell direction were all public
before 2026-08-11). They are **coverage gaps in v3.0**, and the v3.0 erratum in the accompanying
change note corrects Appendix F accordingly. Positioning that ignores them reads as stale, and each
**narrows the defensible Ugence differentiation to its sharpest, most honest form.**

| ServiceNow capability (source) | Availability | What it does | Effect on Ugence positioning |
|---|---|---|---|
| **AI Control Tower — enforcement** [3P: Knowledge 2026] | AVAILABLE NOW | Can **shut down a rogue agent in real time**; approval enforcement at the **Skill Kit** level so only approved providers/models reach skill & agent builders. | ServiceNow *enforces*, not just inventories. Ugence differentiation moves off "ServiceNow can't enforce" onto **mechanism**: a signed, per-action, per-payload authority artifact vs a platform kill-switch/allowlist. |
| **AI Control Tower — Agent Deviation Detection** [3P: Knowledge 2026] | AVAILABLE NOW | Runtime metric that **flags when an agent strays** from its authorized role — prompt-injection attempts, role-boundary breaches, override attempts. | Genuine overlap with **RA‑7 trajectory assurance**. Position as complementary + independent-verification, *not* as a capability ServiceNow lacks. |
| **Action Fabric** — MCP Server/Client + A2A; Anthropic first design partner (Claude Cowork → ServiceNow's governed execution layer) [SN Newsroom; SN Community] | AVAILABLE NOW (GA Knowledge 2026) | Opens ServiceNow's **system of action** to any external agent; **every action runs through AI Control Tower** (identity-verified, permission-scoped, auditable) with consumption metering, OAuth, audit trails, session management, role-based tool packages. | Strong overlap zone. Ugence differentiation is **per-payload/target-digest** authorization, **commit-time recheck**, and **independent post-effect verification** — not "ServiceNow can't govern external agents." |
| **ServiceNow–NVIDIA OpenShell** — trust layer for autonomous AI. **ServiceNow's public description:** policy is **authored centrally in AI Control Tower and enforced at runtime by OpenShell** on **every file read, command, and network call** the agent takes [SN Community]. **NVIDIA's technical description:** an open-source secure runtime that **starts agents at zero permissions**; enforcement is **below the container/application layer** via **seccomp** (syscall filtering), **Landlock LSM** (filesystem access), and **network namespaces** — **not eBPF** [NVIDIA docs: Security Best Practices]. Runs across major enterprise OSes/form factors (e.g. Ubuntu, Windows, OpenShift) [NVIDIA blog]. | AVAILABLE NOW / open-source | Couples central AICT policy to kernel-level runtime enforcement of file, command, and network access across form factors. | **Directly refutes any "runtime enforcement across heterogeneous/off-platform runtimes is unique to Ugence" claim.** Ugence must differentiate on the **authority artifact and its properties** (see thesis), not on "where enforcement can run." Added as overlap zone #5 (§3). |
| **Autonomous Security portfolio** — six unified security solutions; **Armis** (asset intelligence) + **Veza** (AI-native identity, least-privilege for AI agents) [SN Newsroom; 3P] | MIXED — some AVAILABLE NOW (e.g. Autonomous Remediation Agents, AI Agent Access Security, Non-Human Identity Remediation); **Tier 2 SOC AI Specialist ANNOUNCED / expected December 2026** | Autonomous, prevention-first cyber defense; the **Tier 2 SOC AI Specialist** is designed to investigate and execute multi-stage response (enrichment, correlation, **containment and blocking**), escalating high-risk to humans. | Makes the autonomous-containment (UC‑1) and access-provisioning (UC‑6) use cases timely — **but UC‑1's anchor is an ANNOUNCED Dec-2026 capability, not shipped** (see UC‑1). Sharp edge remains exact-target-digest authorization + independent operational clearance + effect reconciliation. |

**The one-sentence thesis (v1.1, narrowed):**

> ServiceNow *governs, enforces at runtime (including at the kernel level via OpenShell), and is
> moving to autonomously act*. Ugence's defensible, verifiable edge is **not** "enforcement that can
> run off-platform" — OpenShell already does that. It is the **nature of the authority artifact**: a
> **cryptographically signed, per-business-action authorization** bound to an **exact payload/target
> digest**, gated on **trusted evidence freshness**, **re-checked at commit**, subject to an
> **independent operational clearance**, **reconciled against observed effect** afterward, and
> **independently verifiable across heterogeneous runtimes**. Everything in this catalog is a
> variation on that one boundary.

---

## 2. The canonical pipeline (how the modules chain)

Every use case is a **subset of one ordered, fail-closed pipeline**. Authority never leaks across a
stage: each layer speaks a distinct decision verb, and uncertainty is never promoted to a favorable
one. Read the full chain once here; each use case then names which stages fire.

```
 POLICY            EVIDENCE            DECISION            MODEL              EXACT ACTION
 Policy Workflow   TAP (assertion) +   Decision Authority  Model Authority    ActionGate
 Compiler          RA‑5 trusted        (binding; AI barred  (ALLOW/DENY/HOLD/  (AUTHORIZED per
 → workflow_ir     admission           as principal)        ESCALATE + fallbk) payload digest)
      │                 │                   │                   │                   │
      ▼                 ▼                   ▼                   ▼                   ▼
 SEQUENCE          CLEARANCE           EXECUTION           RUNTIME ASSURANCE   LIFECYCLE
 StoryGraph        Action Clearance    Agent Runtime       RA‑7 trajectory +   RA‑6 revoke /
 (OBSERVE/         (ACP: CLEAR/HOLD/   (CER; fails closed   RA‑8 effect         supersede / epoch
 ESCALATE)         BLOCK/ESCALATE)     if ungoverned)       reconciliation      propagation

 Binding it together: Risk Authority — RiskDecision → signed RiskAuthorizationEnvelope (Ed25519)
 Non-compensatory:    P ∧ E ∧ R ∧ A ∧ O ∧ L → execute;  any ¬ → no execution (fail-closed)
```

**Reading a use-case pipeline.** Each use case lists its active stages as a chain, e.g.
`Decision Authority → Model Authority → ActionGate → ACP → Agent Runtime → RA‑8`. Stages not listed
are simply not exercised by that scenario — the pipeline is the same; the workflow lights up a path
through it.

---

## 3. Genuine overlap zones (name them, don't hide them)

Five zones are real overlap with *current* ServiceNow capability and must be discussed as
granularity / independent-verification extensions, never as governance gaps:

1. **ActionGate ↔ Action Fabric / AI Control Tower.** Action Fabric already routes every agent
   action through identity-verified, permission-scoped, auditable execution. Ugence's proposed
   narrow edge: **per-payload/target-digest** authorization **re-checked at commit**. Whether
   ServiceNow offers an equivalent *per-payload-digest, commit-time* binding is a **discovery
   hypothesis to confirm with the customer's architects — not an established gap.** *Pitch
   granularity, not a governance hole.*
2. **RA‑7 trajectory assurance ↔ AI Control Tower Agent Deviation Detection.** Both risk-type
   runtime behavior and flag deviation. Ugence's emits a **neutral reassessment signal into an
   authority-lifecycle owner (RA‑6)** and is independently verifiable; ServiceNow's is a native
   platform metric. *Complementary.*
3. **RA‑6 revocation ↔ AI Control Tower real-time shutdown.** Both can stop a misbehaving agent.
   Different mechanism: a **kill-switch** vs an **authority-lifecycle epoch/revoke** that makes the
   signed envelope inert at the next pre-effect recheck while enforcement stays read-only.
4. **Model Authority ↔ AICT Skill-Kit provider approval.** Both restrict which models run. Ugence's
   proposed edge: a **per-request binding authorization** with **governed fallback and expiry**,
   rather than a config-level allowlist.
5. **Runtime execution enforcement ↔ ServiceNow–NVIDIA OpenShell.** This is the zone most easily
   overclaimed. **ServiceNow's public description:** policies are **centrally authored in AI Control
   Tower and enforced at runtime by OpenShell on every file read, command, and network call** the
   agent takes. **NVIDIA's technical description:** OpenShell starts agents at **zero permissions**
   and enforces below the container/application layer via **seccomp** (syscall filtering),
   **Landlock LSM** (filesystem access), and **network namespaces** — **not eBPF** — across major
   enterprise OSes/form factors. **Ugence therefore must not claim that runtime enforcement across
   heterogeneous or off-platform runtimes is unique to it.** The honest differentiation is the
   *authority artifact*: a signed, per-business-action, digest-bound, evidence-fresh,
   commit-rechecked, operationally-cleared, effect-reconciled decision that is *independently
   verifiable* — a governance-decision layer that composes with (and can sit alongside/upstream of)
   an OpenShell-style execution sandbox, not a competitor to kernel-level sandboxing.

Everywhere else the relationship is **complementary** (system of record + workflow + platform
enforcement vs an independent, signed authority-decision artifact), which is the core partnership
story (v3.0 §F.3).

---

## 4. Use-case template (repeatable)

Each use case uses the same seven fields so field teams can co-sell any of them without re-learning
the structure:

1. **ServiceNow product & workflow** — what the customer does today (docs-verifiable)
2. **The autonomy moment** — where AI stops recommending and acts
3. **Runtime-authority question** — one of the five spine questions
4. **Ugence pipeline** — the chained modules + decision verbs
5. **ServiceNow role → Ugence role** — system of record vs runtime enforcement split
6. **Overlap, stated honestly** — the nearest ServiceNow capability and the narrow differentiation
7. **Discovery question** — the question to ask in the evaluation meeting

Integration status for **all** use cases: **PROPOSED** (no ServiceNow connector ships).

---

## 5. The use-case catalog (12 defined)

Broad, pipeline-driven use cases across the ServiceNow product surface. The five marked **★** are
developed in full depth in §6.

| # | Use case | ServiceNow product anchor | Ugence pipeline (module chain) |
|---|---|---|---|
| **UC‑1 ★** *(FUTURE — Dec 2026)* | Autonomous security-incident containment | Security Incident Response / Autonomous Security (**Tier 2 SOC AI Specialist — ANNOUNCED, expected Dec 2026**) | Decision Authority → Model Authority → **ActionGate (host/account/IP digest)** → ACP → Agent Runtime → RA‑8 → RA‑6 |
| **UC‑2 ★** | Runtime model authorization for regulated data | AI Control Tower (model/provider governance; Skill Kit) | PWC → Context Minimization → **Model Authority (per-request ALLOW/DENY/HOLD/ESCALATE + fallback)** → ActionGate |
| **UC‑3 ★** | EU AI Act high-risk action enforcement | AI Control Tower — AI Risk & Compliance / IRM | PWC → **RA‑5 trusted evidence** → Decision Authority → **Risk Authority (signed envelope)** → ActionGate → RA‑8 |
| **UC‑4 ★** | Governing external agents on the system of action | Action Fabric + AI Agent Fabric (MCP/A2A; Claude/Copilot/Gemini) | **Agent Runtime (vendor-neutral CER)** → Model Authority → ActionGate → **StoryGraph** → ACP → RA‑7 |
| **UC‑5 ★** | Autonomous change execution | Change Management + ITOM auto-remediation | **Decision Authority (no AI self-auth)** → ActionGate (CI + change digest) → **ACP (blackout/conflict)** → Cloud Scaling Operations → RA‑8 |
| UC‑6 | Autonomous access provisioning with SoD | ITSM Request / Virtual Agent / Employee Center (+ Veza) | Decision Authority → ActionGate (entitlement digest) → **ACP (SoD/risk posture)** → RA‑8 |
| UC‑7 | Autonomous customer refunds / credits | Customer Service Management (Now Assist for CSM) | Decision Authority (delegated $ threshold) → **ActionGate (amount+account digest)** → ACP → RA‑8 |
| UC‑8 | Autonomous procurement / PO issuance | Sourcing & Procurement Operations / PSM | **PWC (">$100K → CFO")** → TAP (supplier-cert evidence) → Decision Authority → ActionGate → RA‑8 |
| UC‑9 | Governed multi-agent workforce | AI Agent Orchestrator / Autonomous Workforce | **AWC (least-privilege plan, grants nothing)** → per-agent Decision Authority + ActionGate → StoryGraph → RA‑7 |
| UC‑10 | Agentic hiring with human-binding decisions | HRSD / Recruitment Workspace (HR Talent AI Agent) | TAP → **Hiring Governance Authority (AuthorityType has no AI member)** → immutable DecisionRecord → RA‑8 |
| UC‑11 | Autonomous vulnerability remediation / emergency patch | Security Operations — Vulnerability Response | Decision Authority → ActionGate (CI-set + patch digest) → ACP (window + CMDB criticality) → **RA‑6 mid-flight revoke** → RA‑8 |
| UC‑12 | Data-boundary governance for agentic workflows | Workflow Data Fabric / Zero Copy + AICT AI Security & Privacy | **Context Minimization (+ token accounting)** → Model Authority → ActionGate |

> Every use case chains **three or more** Ugence modules, satisfying the "broader, pipeline"
> requirement. UC‑1, UC‑3, UC‑4, UC‑5 exercise the deepest chains (six+ stages).

---

## 6. The five lead scenarios (deep)

Developed in full using the §4 template. These are the highest-consequence, most product-anchored,
best-pipeline stories — lead with them.

### UC‑1 ★ — Autonomous security-incident containment  ·  **ANNOUNCED / FUTURE (Dec 2026 anchor)**

> **Availability label.** This is a **forward-looking** scenario. Its ServiceNow anchor — the
> **Tier 2 SOC AI Specialist** that autonomously performs **containment and blocking** — is
> **ANNOUNCED, expected December 2026** [SN Newsroom; 3P: cxtoday, shashi.co]. **It has not
> shipped.** Related Autonomous Security capabilities *are* AVAILABLE NOW (e.g. Autonomous
> Remediation Agents, AI Agent Access Security, Non-Human Identity Remediation), and the underlying
> action/identity plumbing (Action Fabric, Veza, Armis) is available now — but the specific
> autonomous-containment agent this use case rides on is a **December 2026 opportunity**, and the
> Ugence integration on top of it is **PROPOSED**. Present it as "where this is going," not as a
> capability the customer can buy today.

**1. ServiceNow product & workflow.** *Security Incident Response* within the **Autonomous
Security** portfolio [SN: Security Incident Response; SN Newsroom: Autonomous Security]. On its
December-2026 roadmap, ServiceNow's **Tier 2 SOC AI Specialist** is designed to autonomously build
and execute multi-phase response plans — enrichment, correlation, **containment and blocking** —
escalating only high-risk decisions to a human analyst. Actions reach endpoints/identity through
Action Fabric, routed through AI Control Tower; asset context comes from Armis, identity from Veza.

**2. The autonomy moment.** The AI specialist decides to **isolate a compromised host, disable an
account, or block an IP** and executes it without a human — the difference between "recommend
isolation" and "host `srv‑prod‑0412` is now offline."

**3. Runtime-authority question.** *What exact action is authorized, and is it safe to execute now?*

**4. Ugence pipeline.**
```
Decision Authority        binding containment authority is delegated (not AI self-granted)
      ▼
Model Authority           only an approved model may reason over the incident (regulated telemetry)
      ▼
ActionGate                AUTHORIZED bound to the EXACT target digest: isolate host srv‑prod‑0412
                          — approving "isolate a host" is NOT approving isolation of any host
      ▼
Action Clearance (ACP)    CLEAR/BLOCK on live state: is the target a business-critical CI? in a
                          maintenance freeze? would isolation break a dependent revenue service?
      ▼
Agent Runtime (CER)       executes the containment; fails closed if the governance seam is unwired
      ▼
RA‑8 execution assurance  reconciles that ONLY srv‑prod‑0412 was isolated (EXECUTION_EFFECT_MISMATCH
                          if the blast radius exceeded the authorization)
      ▼
RA‑6 lifecycle            revokes authority instantly if the trajectory breaches scope
```

**5. ServiceNow role → Ugence role.** ServiceNow owns the security incident, the response plan, the
asset (Armis/CMDB) and identity (Veza) context, and the audit trail. Ugence converts the approved
containment into an **exact-target, signed authorization** and adds an **independent live-safety
veto** and **effect reconciliation** the incident record refers to.

**6. Overlap, stated honestly.** By December 2026 ServiceNow expects to perform autonomous
containment natively, and via AI Control Tower it can already shut a rogue agent down and flag
deviation; OpenShell already enforces command/network policy at the kernel level. The proposed,
narrow Ugence edge: **per-target-payload-digest** authorization (this host, this account — not the
class of action), a **non-compensatory operational clearance** independent of the authorization, and
**post-effect reconciliation** that surfaces a content-hash-vs-authorization mismatch. **Whether
ServiceNow's Dec-2026 specialist binds authorization to an exact target digest with commit-time
recheck is a discovery hypothesis to confirm — not an assumed gap.** This is granularity and
independent verification, not a claim that ServiceNow cannot contain.

**7. Discovery question.** *"When the Tier 2 SOC AI Specialist ships and isolates a host
autonomously, will the authorization be bound to that exact host and payload and re-checked at
commit — and is there a separate live-safety gate that can block it even when the authorization is
perfectly valid?"*

---

### UC‑2 ★ — Runtime model authorization for regulated data  ·  **SN anchor AVAILABLE NOW · Ugence integration PROPOSED**

> **Availability label.** ServiceNow anchor (AI Control Tower model/provider governance, Skill-Kit
> approval enforcement) is **AVAILABLE NOW** [SN: AI Control Tower; SN Community: AICT June 2026
> release]. The Ugence per-request Model Authority layer on top is a **PROPOSED INTEGRATION**.

**1. ServiceNow product & workflow.** *AI Control Tower* model/provider governance [SN: AI Control
Tower]. AI Stewards govern customer-configured model providers alongside ServiceNow OEM providers
from one page, with **approval enforcement at the Skill Kit level** so only approved providers/models
reach skill and agent builders, plus data-routing controls.

**2. The autonomy moment.** A running skill/agent is about to send a **request that touches
regulated data** (PHI, EU-resident PII) to a model provider. Approving the provider *in general* is
not the same as approving *this request* to it.

**3. Runtime-authority question.** *Which model is allowed to make this decision, right now, for
this data?*

**4. Ugence pipeline.**
```
Policy Workflow Compiler   compile the data-residency / model-eligibility policy → workflow_ir
      ▼
Context Minimization       reduce the request to minimum-necessary; account tokens; fail closed if
                           equivalence to the full context can't be established
      ▼
Model Authority            per-REQUEST ModelAuthorizationDecision: ALLOW / DENY / HOLD / ESCALATE,
                           with GOVERNED FALLBACK to an approved model and an expiry — e.g. DENY a
                           non-region model for a PHI-bearing request, fall back to an approved one
      ▼
ActionGate                 the downstream action inherits the model authorization as a bound input
```

**5. ServiceNow role → Ugence role.** AICT owns the model inventory, provider approvals, and
Skill-Kit-level policy. Ugence issues the **per-request binding model authorization** with fallback
and expiry that the AICT policy configures but does not itself adjudicate per call.

**6. Overlap, stated honestly.** AICT's Skill-Kit approval enforcement already ensures only approved
models are *available*. Ugence's edge is the shift from **availability (config allowlist)** to a
**per-request binding decision** that can `HOLD`/`ESCALATE`, carries an **expiry**, and specifies a
**governed fallback** — evaluated against *this* request's data, not the builder's configuration.

**7. Discovery question.** *"Is model choice a configuration allowlist, or a per-request binding
authorization — with governed fallback and expiry — evaluated against the specific data this
request carries?"*

---

### UC‑3 ★ — EU AI Act high-risk action enforcement  ·  **SN anchor AVAILABLE NOW · Ugence integration PROPOSED**

> **Availability label.** ServiceNow anchor (AI Control Tower — AI Risk & Compliance, multi-framework
> control mapping) is **AVAILABLE NOW** [SN: AI Control Tower; SN: AICT Solution Brief; 3P:
> Knowledge 2026]. The Ugence signed-envelope enforcement layer is a **PROPOSED INTEGRATION**.

**1. ServiceNow product & workflow.** *AI Control Tower — AI Risk & Compliance* over *Integrated
Risk Management* [SN: AI Control Tower]. AICT ships pre-built content aligned to the **EU AI Act**
and **NIST AI RMF**, and a single control can map simultaneously to the EU AI Act, Colorado AI Act,
California AI Act and NIST AI RMF. It classifies AI use cases and runs the risk/compliance workflows.

**2. The autonomy moment.** An AI use case classified **high-risk** is about to take a consequential
action. The compliance state is *approved* in the register — but is every required control
**currently satisfied by trusted evidence** at the instant of action?

**3. Runtime-authority question.** *Did execution stay within an approved, evidence-backed authority
— and can we prove a stale "PASS" cannot slip through?*

**4. Ugence pipeline.**
```
Policy Workflow Compiler        compile the EU AI Act control set → deterministic workflow_ir
      ▼
RA‑5 trusted evidence           a caller-asserted status="PASS" is INERT; only an evidence-derived,
                                RA‑re-checked ControlResult satisfies a required control
      ▼
Decision Authority              binding decision under delegated authority (AI barred as principal)
      ▼
Risk Authority                  mints the signed, scoped, time-bound RiskAuthorizationEnvelope
                                (Ed25519) ONLY if an ALLOW-family RiskDecision grants authority
      ▼
ActionGate                      enforces the envelope on a bounded, offline hot path (no LLM,
                                no regulatory-text reinterpretation)
      ▼
RA‑8 execution assurance        reconciles observed effect against the authorized scope
```

**5. ServiceNow role → Ugence role.** AICT/IRM remains the system of record for the risk register,
control mappings and compliance workflows. Ugence converts that approved compliance state into a
**signed per-action authority artifact whose validity depends on controls being currently, trustedly
satisfied** — "your GRC system tells you what your AI policy is; Ugence makes it executable."

**6. Overlap, stated honestly.** AICT now *enforces* (approval enforcement, real-time shutdown) and
maps controls across frameworks — this is strong. The proposed Ugence extension is a
**cryptographically signed, scoped, revocable per-action authorization artifact bound to a payload
digest and gated on trusted, re-checked evidence**. **Whether AICT already issues an equivalent
signed, evidence-fresh per-action artifact is a discovery hypothesis to test with the customer's
architects — not something these sources establish either way.** Position the signed-envelope +
trusted-admission boundary as making an approved AICT governance state enforceable at the exact
action, not as a compliance gap.

**7. Discovery question.** *"When a high-risk AI action fires, what stops it if a required control's
evidence is stale or merely caller-asserted — and is the resulting authority a signed, scoped,
revocable artifact, or a workflow status?"*

---

### UC‑4 ★ — Governing external agents on the system of action  ·  **SN anchor AVAILABLE NOW · Ugence integration PROPOSED**

> **Availability label.** ServiceNow anchor (Action Fabric MCP/A2A, GA at Knowledge 2026; AI Agent
> Fabric; every action routed through AI Control Tower; **plus ServiceNow–NVIDIA OpenShell**
> kernel-level runtime enforcement) is **AVAILABLE NOW** [SN Newsroom: "opens its full system of
> action"; SN Community: Action Fabric MCP/A2A explained; SN Community + NVIDIA: OpenShell]. The
> Ugence authority-artifact layer on top is a **PROPOSED INTEGRATION**.
>
> **Positioning caution — do not overclaim.** ServiceNow already governs external agents *and*
> already enforces execution across heterogeneous runtimes (Action Fabric routes every action
> through AICT; **OpenShell enforces central AICT policy at the kernel level on every file read,
> command and network call, across PCs, data centers and clouds**). Ugence therefore does **not**
> claim unique off-platform or cross-runtime enforcement. The differentiation is confined to the
> **properties of an independent authority-decision artifact** (below).

**1. ServiceNow product & workflow.** *Action Fabric* + *AI Agent Fabric*. ServiceNow opens its
**full system of action** to any MCP-compatible external agent — Claude, Copilot Studio, Moveworks,
AWS Bedrock, custom — with **Anthropic as first design partner** (Claude Cowork connected to
ServiceNow's governed execution layer). **Every action runs through AI Control Tower**
(identity-verified, permission-scoped, auditable), with an MCP Server Console for metering, OAuth,
audit and role-based tool packages; **ServiceNow–NVIDIA OpenShell** enforces the resulting policy at
runtime.

**2. The autonomy moment.** An **external** agent executes a governed action headlessly over
MCP/A2A. ServiceNow governs and enforces that action. The remaining question is whether each such
action carries an **independent, signed, digest-bound authority record** the enterprise can verify
and reconcile *separately from the platform that executed it*.

**3. Runtime-authority question.** *For each external-agent action, is there a signed
per-business-action authorization — bound to an exact payload/target digest, evidence-fresh,
re-checked at commit, operationally cleared, and reconciled against effect — that is independently
verifiable, and does anything flag when a sequence of individually-allowed steps assembles a harmful
capability?*

**4. Ugence pipeline.**
```
Agent Runtime (CER)        a Canonical Execution Request as an independent governance-decision seam
                           (a layer that composes with an OpenShell-style execution sandbox — it
                           issues/verifies authority; it does not replace kernel-level enforcement)
      ▼
Model Authority            per-request model authorization for the external agent's step
      ▼
ActionGate                 AUTHORIZED bound to the exact payload/target digest of the MCP tool call,
                           re-checked at commit time
      ▼
StoryGraph (sequence)      OBSERVE/ESCALATE when benign steps assemble a harmful capability across
                           the multi-step external-agent plan
      ▼
Action Clearance (ACP)     independent live operational veto before dispatch
      ▼
RA‑7 runtime assurance     trajectory assessment → neutral reassessment signal (NORMAL/ESCALATED),
                           independently verifiable
```

**5. ServiceNow role → Ugence role.** Action Fabric is the governed *doorway* into ServiceNow's
system of action; AICT verifies identity/permission/audit for every action; OpenShell enforces
policy at the kernel level. Ugence adds an **independent, signed, digest-bound authority-decision
record** per business action and a **sequence-risk** signal across the plan — an authority/evidence
layer that composes *with* ServiceNow's execution enforcement, not a substitute for it.

**6. Overlap, stated honestly.** This is the **strongest overlap zone**. Action Fabric + AICT govern
external agents thoroughly, and OpenShell enforces execution across form factors — so Ugence claims
**neither** a governance gap **nor** unique cross-runtime enforcement. The confined, defensible
edges are the **artifact properties**: (a) a **signed per-business-action** authorization bound to an
**exact payload/target digest**; (b) **trusted evidence freshness** as a precondition; (c)
**commit-time recheck**; (d) an **independent operational clearance**; (e) **post-effect
reconciliation**; and (f) **independent verification across heterogeneous runtimes** (verifiable by a
party other than the executor). **Whether ServiceNow already emits an equivalent independently
verifiable signed per-action artifact is a discovery hypothesis to confirm with its architects.**
Anthropic being ServiceNow's design partner makes this a partnership-native conversation, not a
competitive one.

**7. Discovery question.** *"For each external-agent action governed by Action Fabric and enforced by
OpenShell, is there an independently verifiable, signed per-action authorization bound to the exact
payload — re-checked at commit and reconciled against the observed effect — and does anything flag
when a sequence of allowed steps assembles a disallowed capability?"*

---

### UC‑5 ★ — Autonomous change execution  ·  **SN anchor AVAILABLE NOW · Ugence integration PROPOSED**

> **Availability label.** ServiceNow anchor (Change Management windows/conflict detection; ITOM
> agentic change-impact analysis and auto-remediation) is **AVAILABLE NOW** [SN: ITOM; SN Newsroom:
> Fully Autonomous IT; SN Store: Now Assist for ITOM]. The Ugence authorization/clearance layer on
> top is a **PROPOSED INTEGRATION**. *Note: some deeper autonomous-remediation capabilities are
> rolling out in waves through 2026 — confirm the customer's specific release before scoping.*
>
> **Ugence Cloud Scaling Controller / Operations maturity (four dimensions — do not conflate):**
> **(1) Core Cloud Scaling Controller: IMPLEMENTED.** **(2) Production validation: PILOT PENDING.**
> **(3) Additional agentic-AI capabilities: UNDER ACTIVE DEVELOPMENT.** **(4) ServiceNow
> integration: PROPOSED — no connector currently ships.** The core is **not downgraded** because
> broader agentic-AI features are still in development; those are additive. Representative-facing
> wording: *"Ugence Cloud Scaling Controller is implemented and awaiting pilot validation.
> Additional capabilities for broader agentic-AI workflows continue to be developed, while
> ServiceNow integration remains proposed."*

**1. ServiceNow product & workflow.** *Change Management* + *ITOM* autonomous remediation [SN: ITOM;
SN Store: Now Assist for ITOM]. Agentic workflows analyze change impact on the CMDB; ITOM AI agents
autonomously handle alert triage, root-cause analysis, and trigger orchestrated **auto-remediation**
runbooks. Change Management owns freeze/blackout/maintenance windows and conflict detection.

**2. The autonomy moment.** An AI agent **auto-approves and executes a standard change** —
restart a service, push a config, scale a cluster, fail over — with no human in the loop.

**3. Runtime-authority question.** *Can AI make and execute this change without self-authorizing,
bound to the exact CI, and only when the environment is clear?*

**4. Ugence pipeline.**
```
Decision Authority          the change is bound only within delegated authority — AuthorityType has
                            NO AI member, so the agent structurally cannot self-approve the change
      ▼
ActionGate                  AUTHORIZED bound to the EXACT CI + change payload digest (this cluster,
                            this config version — not "changes of this type")
      ▼
Action Clearance (ACP)      CLEAR/HOLD/BLOCK on live change state: blackout window? conflicting
                            change? dependent-service freeze? — a non-compensatory pre-dispatch veto
      ▼
Cloud Scaling Operations    gated CONTROLLED_EXECUTION requiring an explicit ExecutionAuthorization;
                            dry_run by default
      ▼
Agent Runtime (CER)         executes the change
      ▼
RA‑8 execution assurance    reconciles that the executed change matched the authorized CI + payload
```

**5. ServiceNow role → Ugence role.** ServiceNow owns the change record, CMDB impact, windows,
conflict detection and the runbook. Ugence adds the **structural bar on AI self-approval**, the
**exact-CI authorization**, and turns ServiceNow's window/conflict state into a **fail-closed
pre-dispatch veto** separate from the authorization decision.

**6. Overlap, stated honestly.** Change Management *already* enforces freeze windows and conflict
detection, and ITOM already auto-remediates. Ugence's edge is (a) authorization bound to the **exact
CI + payload digest** re-checked at commit, and (b) treating live change state as an **independent,
non-compensatory clearance** — the action can be perfectly authorized and still `BLOCK` on live
conditions — plus the **structural** (in-code) guarantee that the AI never authorizes its own
change. Complementary to Change Management, not a replacement.

**7. Discovery question.** *"When an AI agent auto-executes a standard change, what structurally
prevents it from approving its own change, is the authorization bound to that exact CI and payload,
and can a live blackout block it independently of how valid the approval is?"*

---

## 7. Cross-cutting: one audit lineage across all use cases

The **Governance Story Graph** (proposed module in v3.0) ties every use case above into one causal
lineage: *why an AI decision was allowed → what evidence and authority backed it → what action
executed → what effect was reconciled → what that implies for future authority*. Mapped to the CMDB
and AI Case Management, it gives the ServiceNow customer a single "story" per autonomous action —
the natural home for the receipts these pipelines emit (decision records, signed envelopes,
clearance verdicts, RA‑7/RA‑8 assessments). It remains **proposed / design-only** and is named as
such.

### 7.1 Enterprise Governed Value (developing — cross-cutting roadmap capability, *not* an authorization stage)

> This is a **roadmap note**, not a new gate in the §2 pipeline. It does not authorize, clear, or
> execute anything.

Ugence is **developing an Enterprise Governed Value capability to verify whether agentic workflows
deliver attributable business outcomes while preserving cost, risk, compliance, quality, and service
constraints.**

**Acknowledge ServiceNow first.** ServiceNow **AI Control Tower already measures AI adoption,
business impact, realized value, and ROI** — this is a real, shipped strength, and the proposed
Ugence capability does **not** claim ServiceNow lacks ROI measurement.

The proposed Ugence extension is positioned **only as evidence-backed *attribution*** that connects,
into one verifiable chain per workflow:

- **approved objectives and baselines** (what outcome was authorized, measured against what
  starting point);
- **governed workflow and execution receipts** (the decision records, signed envelopes, clearance
  verdicts, and RA‑7/RA‑8 assessments the pipelines already emit);
- **model and infrastructure costs** (including the token accounting from Context Minimization and
  scaling actuation from Cloud Scaling Operations);
- **observed outcomes** (the reconciled real-world effect);
- **attribution rules** (how outcomes are causally tied back to the governed actions); and
- **preserved risk, compliance, quality, and service constraints** (evidence the value was not
  realized by breaching a governance boundary).

In short: ServiceNow measures adoption, impact and realized value; the proposed Ugence capability
adds **evidence-backed attribution** that a *specific governed action* produced a *specific outcome*
**without** trading away cost, risk, compliance, quality, or service constraints. Maturity:
**developing / proposed**; ServiceNow integration **PROPOSED**.

---

## 8. Recommended sequencing for the ServiceNow conversation

1. **Open with UC‑5** (autonomous change execution) — an available-now, low-controversy product
   the customer already runs, where the exact-CI authorization and independent clearance land
   cleanly.
2. **Acknowledge ServiceNow's runtime strength first** (§1) — enforcement, Agent Deviation
   Detection, Action Fabric, and **OpenShell kernel-level enforcement** — then land the narrowed
   v1.1 thesis (§1). Naming OpenShell yourself is what earns the room's trust.
3. **Then UC‑3** (EU AI Act enforcement) — the highest-value, available-now governance→enforcement
   story, where trusted evidence freshness and the signed envelope are the point.
4. **Then UC‑4** (external agents) — the partnership-native zone with Anthropic as design partner;
   explicitly disclaim unique cross-runtime enforcement and confine the pitch to the artifact
   properties.
5. **Name all five overlap zones yourself** (§3), including OpenShell, before the reviewer does.
6. **Present UC‑1 as a December 2026 opportunity** — a forward-looking "where this goes when the
   Tier 2 SOC AI Specialist ships," clearly labeled ANNOUNCED/FUTURE, never as available today.
7. **Close on partnership** (system-of-record vs runtime-enforcement split; v3.0 §F.3): ServiceNow is the system of record, system of action, and
   runtime enforcement (Action Fabric + AICT + OpenShell); Ugence is an independent, signed
   authority-decision artifact that composes with it. Every integration is **PROPOSED**; every
   package is independently deployable if a ServiceNow partnership is not pursued.

---

## 9. Source legend (ServiceNow-owned & press sources, verified 2026-08-13)

Per the research method (§0), the **primary source is ServiceNow product documentation at
`docs.servicenow.com`**, with release notes for availability, Newsroom for announcements/future
availability, and Community for supporting material; third-party press corroborates announcement
facts only. Direct page fetches were egress-blocked in this environment, so these ServiceNow-owned
(and NVIDIA-owned) pages were reached via web search and **should be spot-checked live before
customer use**. ServiceNow-owned sources are marked **[SN]**; NVIDIA-owned sources **[NVIDIA]**;
reputable third-party corroboration **[3P]**.

- **[SN] AI Control Tower** — https://www.servicenow.com/products/ai-control-tower.html
- **[SN] AI Control Tower — expansion (discover/observe/govern/secure/measure any AI)**, Newsroom — https://newsroom.servicenow.com/press-releases/details/2026/ServiceNow-expands-AI-Control-Tower-to-discover-observe-govern-secure-and-measure-AI-deployed-across-any-system-in-the-enterprise/default.aspx
- **[SN] AI Control Tower — What's new (June 2026 release)**, Community — https://www.servicenow.com/community/ai-control-tower-articles/ai-control-tower-what-s-new-in-the-june-2026-release/ta-p/3561445
- **[SN] Action Fabric** — https://www.servicenow.com/platform/action-fabric.html
- **[SN] "ServiceNow opens its full system of action to every AI Agent"**, Newsroom — https://newsroom.servicenow.com/press-releases/details/2026/ServiceNow-opens-its-full-system-of-action-to-every-AI-Agent-in-the-enterprise/default.aspx
- **[SN] Action Fabric: MCP Server, MCP Client, and A2A explained**, Community — https://www.servicenow.com/community/now-assist-articles/action-fabric-mcp-server-mcp-client-and-a2a-explained/ta-p/3557794
- **[SN] Enable MCP and A2A for your agentic workflows (FAQs, Zurich Patch 4)**, Community — https://www.servicenow.com/community/now-assist-articles/enable-mcp-and-a2a-for-your-agentic-workflows-with-faqs-updated/ta-p/3373907
- **[SN] "ServiceNow delivers Autonomous Security"**, Newsroom — https://newsroom.servicenow.com/press-releases/details/2026/ServiceNow-delivers-Autonomous-Security-the-industrys-most-complete-security-offering/default.aspx
- **[SN] Security Incident Response** — https://www.servicenow.com/products/security-incident-response.html
- **[SN] Security Operations (SecOps)** — https://www.servicenow.com/products/security-operations.html
- **[SN] Now Assist Guardian**, Docs — https://www.servicenow.com/docs/bundle/zurich-intelligent-experiences/page/administer/now-assist-platform/concept/now-assist-guardian.html
- **[SN] Agentic AI for Hiring Experiences: Overview**, Community — https://www.servicenow.com/community/hrsd-articles/agentic-ai-for-hiring-experiences-overview/ta-p/3514999
- **[SN] Agentic AI Capabilities for HR**, Community — https://www.servicenow.com/community/hrsd-blog/agentic-ai-capabilities-for-hr/ba-p/3288346
- **[SN] IT Operations Management (ITOM)** — https://www.servicenow.com/products/it-operations-management.html
- **[SN] "ServiceNow Sets New Standard for Fully Autonomous IT"**, Newsroom — https://newsroom.servicenow.com/press-releases/details/2025/ServiceNow-Sets-New-Standard-for-Fully-Autonomous-IT-Envisioning-a-Zero-Downtime-Zero-Outage-Future-With-Agentic-AI/default.aspx
- **[SN] AI Control Tower — Solution Brief (Govern any AI at Scale)** — https://www.servicenow.com/content/dam/servicenow-assets/public/en-us/doc-type/resource-center/solution-brief/sb-ai-control-tower.pdf
- **[SN] ServiceNow builds the trust layer for Autonomous AI with NVIDIA OpenShell**, Community — https://www.servicenow.com/community/in-other-news/servicenow-builds-the-trust-layer-for-autonomous-ai-with-nvidia/ba-p/3553486
- **[3P/NVIDIA] NVIDIA OpenShell — secure runtime for autonomous AI agents** — https://blogs.nvidia.com/blog/secure-autonomous-ai-agents-openshell/ ; https://docs.nvidia.com/openshell/about/overview ; https://github.com/NVIDIA/openshell ; https://thenewstack.io/nvidia-openshell-agent-runtime/
- **[3P] AICT enforcement (Knowledge 2026)** — https://thelettertwo.com/2026/05/05/servicenow-expands-ai-control-tower-knowledge-2026/ ; https://erp.today/servicenow-ai-security-governance-knowledge-2026/
- **[3P] Autonomous Security / Armis + Veza; Tier 2 SOC AI Specialist expected Dec 2026 (two-wave rollout)** — https://siliconangle.com/2026/08/04/servicenow-debuts-six-autonomous-security-products-built-armis-veza/ ; https://www.helpnetsecurity.com/2026/08/04/servicenow-ai-specialists/ ; https://www.cxtoday.com/security-privacy-compliance/servicenow-moves-to-lock-down-enterprise-ai-agents-with-autonomous-security-portfolio/ ; https://www.shashi.co/2026/08/servicenow-rolls-six-security-products.html
- **[3P] Action Fabric / Anthropic design partner** — https://www.bankinfosecurity.com/servicenows-new-platform-also-governs-everyone-elses-ai-a-31631

> **Also see** the v3.0 package's Appendix F source legend for the base product URLs (IRM, Policy &
> Compliance, AI Agents, AI Agent Orchestrator, CMDB, Change/Event Management, HRSD, SPO/PSM).

---

## 10. Status summary

- **Deliverable type:** ServiceNow-product-anchored, pipeline-driven use-case catalog (companion to
  the v3.0 differentiation package).
- **Version:** 1.1 — factual & positioning correction of v1.0 (see the change log in the
  accompanying note).
- **Use cases defined:** 12 (§5). **Developed in full depth:** 5 lead scenarios (§6).
- **Every use case** chains ≥3 Ugence modules as a pipeline (requirement met).
- **Availability discipline:** each lead scenario carries an availability label — **AVAILABLE NOW /
  ANNOUNCED-FUTURE / PROPOSED INTEGRATION**. UC‑1's anchor (Tier 2 SOC AI Specialist) is
  **ANNOUNCED, expected Dec 2026** — not shipped.
- **Positioning correction:** Ugence does **not** claim unique off-platform or cross-runtime
  enforcement — ServiceNow–NVIDIA OpenShell already enforces at the kernel level across form
  factors (overlap zone #5). Differentiation is confined to the **independent, signed
  authority-decision artifact** and its properties (§1 thesis).
- **Evidence discipline:** "the verified sources do not show X" is treated throughout as a
  **discovery hypothesis to confirm with the customer's architects**, not as proof ServiceNow lacks
  X.
- **Cloud Scaling Controller / Operations (four-dimension status, UC‑5):** core **IMPLEMENTED**;
  production validation **PILOT PENDING**; additional agentic-AI capabilities **UNDER ACTIVE
  DEVELOPMENT**; ServiceNow integration **PROPOSED (no connector ships)**. Retained in the UC‑5
  pipeline; not downgraded for in-development additions.
- **Enterprise Governed Value (§7.1):** a **developing, cross-cutting roadmap capability** (not an
  authorization stage) providing **evidence-backed attribution**; acknowledges AICT already measures
  adoption, business impact, realized value and ROI.
- **Research method:** primary source is **`docs.servicenow.com`** (docs → release notes → Newsroom
  → Community); third-party press corroborates announcement facts only (§0).
- **OpenShell precision:** enforcement described as **seccomp + Landlock LSM + network namespaces
  (not eBPF)**, with ServiceNow's AICT-relationship description distinguished from NVIDIA's technical
  description (§1, §3).
- **Integration status:** all PROPOSED. **Package maturity:** shipped but mostly reference-grade,
  production deployment validation pending (per v3.0 Appendix B).
- **Verification:** ServiceNow capabilities checked against ServiceNow-owned + corroborating
  sources on 2026-08-13; live pages should be spot-checked (egress caveat, §0). The capabilities in
  §1 **predate** v3.0's 2026-08-11 verification and are coverage gaps in v3.0's Appendix F.
