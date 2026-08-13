# Ugence + ServiceNow: Product-Anchored Runtime Governance Use Cases

## A ServiceNow-product-first, pipeline-driven use-case catalog

**Version:** 1.0 (companion to the v3.0 *Runtime AI Decision & Execution Authority* differentiation package)
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
   ServiceNow-owned sources on **2026-08-13** (see the source legend, §7). This edition
   deliberately captures **ServiceNow capabilities that postdate the v3.0 package's 2026-08-11
   verification** — AI Control Tower's new real-time *enforcement* and *Agent Deviation Detection*,
   Action Fabric's GA with Anthropic as design partner, and the **Autonomous Security** portfolio
   (Armis + Veza). These strengthen ServiceNow's runtime governance and therefore **sharpen, not
   soften, the honesty guardrails** below.

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
- **Method caveat.** Direct fetches to `www.servicenow.com` were egress-blocked in this
  environment (as they were for the v3.0 package). Product descriptions were assembled from
  ServiceNow-owned pages surfaced via web search (product pages, `docs.servicenow.com`,
  ServiceNow Community, ServiceNow Newsroom). **Exact marketing quotes, release/patch numbers, and
  capability names should be spot-checked on the live pages before customer use.**

---

## 1. What changed on the ServiceNow side since v3.0 (read this first)

Between the v3.0 verification (2026-08-11) and this edition (2026-08-13), ServiceNow's *runtime*
governance advanced materially. The rep will know these; positioning that ignores them reads as
stale. All four **narrow** the defensible Ugence differentiation to its sharpest form:

| New / matured ServiceNow capability (2026) | What it does | Effect on Ugence positioning |
|---|---|---|
| **AI Control Tower — enforcement** ("enforcement muscle", Knowledge 2026) | Can **shut down a rogue agent in real time**; approval enforcement at the **Skill Kit** level so only approved providers/models reach skill & agent builders. | ServiceNow now *enforces*, not just inventories. Ugence differentiation moves off "ServiceNow can't enforce" and onto **mechanism**: a signed, per-action, per-payload authority artifact vs a platform kill-switch/allowlist. |
| **AI Control Tower — Agent Deviation Detection** | Runtime metric that **flags when an agent strays** from its authorized role — prompt-injection attempts, role-boundary breaches, override attempts. | Genuine overlap with **RA‑7 trajectory assurance**. Position as complementary + vendor-neutral, *not* as a capability ServiceNow lacks. |
| **Action Fabric (GA, Knowledge 2026)** — MCP Server/Client + A2A; Anthropic first design partner (Claude Cowork → ServiceNow's governed execution layer) | Opens ServiceNow's **system of action** to any external agent; **every action runs through AI Control Tower** (identity-verified, permission-scoped, auditable) with consumption metering, OAuth, audit trails, session management, role-based tool packages. | Strongest overlap zone. Ugence differentiation is **per-payload-digest** authorization and a **vendor-neutral CER that travels off-platform** — not "ServiceNow can't govern external agents." |
| **Autonomous Security portfolio (Aug 2026)** — six autonomous security products; a **Tier 2 SOC AI Specialist** that autonomously executes containment/blocking, escalating only high-risk to humans; built on **Armis** (asset intelligence) and **Veza** (AI-native identity, least-privilege for AI agents). | ServiceNow now ships **autonomous action** in security, and least-privilege identity for agents (Veza). | Makes the autonomous-containment and access-provisioning use cases *more* timely, and makes **exact-target-digest authorization + independent operational clearance + effect reconciliation** the sharp edge. |

**The one-sentence sharpened thesis:**

> ServiceNow now *governs, enforces, and even autonomously acts*. Ugence's defensible, verifiable
> edge is the **cryptographically signed, per-action, per-payload authorization artifact —
> re-checked at commit, cleared by an independent live gate, reconciled against observed effect,
> and enforceable even when the runtime is not ServiceNow.** Everything in this catalog is a
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

Four zones are real overlap with *current* ServiceNow capability and must be discussed as
granularity/vendor-neutrality extensions, never as governance gaps:

1. **ActionGate ↔ Action Fabric / AI Control Tower.** Action Fabric already routes every agent
   action through identity-verified, permission-scoped, auditable execution. Ugence's narrow edge:
   **per-payload-digest** authorization **re-checked at commit** — not shown in the verified
   ServiceNow sources. *Pitch granularity, not a gap.*
2. **RA‑7 trajectory assurance ↔ AI Control Tower Agent Deviation Detection.** Both risk-type
   runtime behavior and flag deviation. Ugence's is **vendor-neutral** and emits a **neutral
   reassessment signal into an authority-lifecycle owner (RA‑6)** rather than a platform metric.
   *Complementary.*
3. **RA‑6 revocation ↔ AI Control Tower real-time shutdown.** Both can stop a misbehaving agent.
   Different mechanism: a **kill-switch** vs an **authority-lifecycle epoch/revoke** that makes the
   signed envelope inert at the next pre-effect recheck while enforcement stays read-only.
4. **Model Authority ↔ AICT Skill-Kit provider approval.** Both restrict which models run. Ugence's
   edge: a **per-request binding authorization** with **governed fallback and expiry**, not a
   config-level allowlist.

Everywhere else the relationship is **complementary** (system of record + workflow vs runtime
enforcement artifact), which is the core partnership story (v3.0 §F.3).

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
| **UC‑1 ★** | Autonomous security-incident containment | Security Incident Response / Autonomous Security (Tier 2 SOC AI Specialist) | Decision Authority → Model Authority → **ActionGate (host/account/IP digest)** → ACP → Agent Runtime → RA‑8 → RA‑6 |
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

### UC‑1 ★ — Autonomous security-incident containment

**1. ServiceNow product & workflow.** *Security Incident Response* within the **Autonomous
Security** portfolio. ServiceNow's **Tier 2 SOC AI Specialist** autonomously builds and executes
multi-phase response plans — enrichment, correlation, **containment and blocking** — escalating only
high-risk decisions to a human analyst. Actions reach endpoints/identity through Action Fabric,
routed through AI Control Tower; asset context comes from Armis, identity from Veza.

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

**6. Overlap, stated honestly.** ServiceNow *already* performs autonomous containment and, via AI
Control Tower, can shut a rogue agent down and flag deviation. The narrow, verifiable Ugence edge:
**per-target-payload-digest** authorization (this host, this account — not the class of action) plus
a **non-compensatory operational clearance** independent of the authorization, and **post-effect
reconciliation** that a content-hash-vs-authorization mismatch surfaces. This is granularity and
independence, not a claim that ServiceNow cannot contain.

**7. Discovery question.** *"When the SOC AI Specialist isolates a host autonomously, is the
authorization bound to that exact host and payload and re-checked at commit — and is there a
separate live-safety gate that can block it even when the authorization is perfectly valid?"*

---

### UC‑2 ★ — Runtime model authorization for regulated data

**1. ServiceNow product & workflow.** *AI Control Tower* model/provider governance. AI Stewards
govern customer-configured model providers alongside ServiceNow OEM providers from one page, with
**approval enforcement at the Skill Kit level** so only approved providers/models reach skill and
agent builders, plus data-routing controls.

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

### UC‑3 ★ — EU AI Act high-risk action enforcement

**1. ServiceNow product & workflow.** *AI Control Tower — AI Risk & Compliance* over *Integrated
Risk Management*. AICT ships pre-built content aligned to the **EU AI Act** and **NIST AI RMF**, and
a single control can map simultaneously to the EU AI Act, Colorado AI Act, California AI Act and
NIST AI RMF. It classifies AI use cases and runs the risk/compliance workflows.

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
maps controls across frameworks — this is strong. The verified sources do **not** show a
**cryptographically signed, scoped, revocable per-action authorization artifact bound to a payload
digest and gated on trusted, re-checked evidence**. That signed-envelope + trusted-admission
boundary is the extension; position it as making an approved AICT governance state enforceable at
the action, not as a compliance gap.

**7. Discovery question.** *"When a high-risk AI action fires, what stops it if a required control's
evidence is stale or merely caller-asserted — and is the resulting authority a signed, scoped,
revocable artifact, or a workflow status?"*

---

### UC‑4 ★ — Governing external agents on the system of action

**1. ServiceNow product & workflow.** *Action Fabric* + *AI Agent Fabric* (GA at Knowledge 2026).
ServiceNow opens its **full system of action** to any MCP-compatible external agent — Claude,
Copilot Studio, Moveworks, AWS Bedrock, custom — with **Anthropic as first design partner** (Claude
Cowork connected to ServiceNow's governed execution layer). **Every action runs through AI Control
Tower** (identity-verified, permission-scoped, auditable), with an MCP Server Console for metering,
OAuth, audit and role-based tool packages.

**2. The autonomy moment.** An **external** agent (outside ServiceNow's runtime) executes a
governed ServiceNow action headlessly over MCP/A2A — *and* the enterprise wants the **same
enforcement** to hold when that agent also acts on non-ServiceNow systems in the same task.

**3. Runtime-authority question.** *Can one vendor-neutral execution contract enforce the same
authority across ServiceNow and non-ServiceNow runtimes — and catch a harmful sequence of
individually-benign steps?*

**4. Ugence pipeline.**
```
Agent Runtime (CER)        one vendor-neutral Canonical Execution Request + fail-closed governance
                           seam; the SAME contract whether the step lands on ServiceNow or elsewhere
      ▼
Model Authority            per-request model authorization for the external agent's step
      ▼
ActionGate                 AUTHORIZED bound to the exact payload of the MCP-published tool call
      ▼
StoryGraph (sequence)      OBSERVE/ESCALATE when benign steps assemble a harmful capability across
                           the multi-step external-agent plan
      ▼
Action Clearance (ACP)     live operational veto before dispatch
      ▼
RA‑7 runtime assurance     trajectory assessment → neutral reassessment signal (NORMAL/ESCALATED)
```

**5. ServiceNow role → Ugence role.** Action Fabric is the governed *doorway* into ServiceNow's
system of action; AICT verifies identity/permission/audit for every action that passes through it.
Ugence adds a **vendor-neutral CER that travels with the agent off-platform** and a
**sequence-risk** signal across the whole plan — enforcement that isn't scoped to the ServiceNow
doorway alone.

**6. Overlap, stated honestly.** This is the **strongest overlap zone**. Action Fabric + AICT
already govern external agents thoroughly *for actions routed through ServiceNow*, including
identity, permission scope, audit, metering and Agent Deviation Detection. Ugence does **not** claim
ServiceNow cannot govern external agents. The two narrow edges: (a) **per-payload-digest**
authorization re-checked at commit, and (b) a **single governance seam that also binds the agent's
non-ServiceNow steps** in the same task, so a step that leaves the ServiceNow system of action isn't
outside the authority envelope. Anthropic being ServiceNow's design partner makes this a
partnership-native conversation, not a competitive one.

**7. Discovery question.** *"When Claude or Copilot acts through Action Fabric on ServiceNow and
then acts on a non-ServiceNow system in the same task, does one authority contract cover both steps
— and does anything flag when a sequence of allowed steps assembles a disallowed capability?"*

---

### UC‑5 ★ — Autonomous change execution

**1. ServiceNow product & workflow.** *Change Management* + *ITOM* autonomous remediation. Agentic
workflows already analyze change impact on the CMDB; ITOM AI agents autonomously handle alert
triage, root-cause analysis, and trigger orchestrated **auto-remediation** runbooks. Change
Management owns freeze/blackout/maintenance windows and conflict detection.

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

---

## 8. Recommended sequencing for the ServiceNow conversation

1. **Open with UC‑1 or UC‑5** (autonomous action the customer can picture in a product they own).
2. **Acknowledge ServiceNow's 2026 runtime strength first** (§1) — enforcement, deviation
   detection, Action Fabric, Autonomous Security — then land the sharpened thesis (§1, one-liner).
3. **Walk one pipeline end-to-end** (§2) so the distinct verbs and fail-closed conjunction are
   concrete.
4. **Name the overlap zones yourself** (§3) before the reviewer does — it is the fastest way to
   earn the credibility the narrow differentiation needs.
5. **Close on partnership** (§7 split): ServiceNow is the system of record and system of action;
   Ugence is the vendor-neutral runtime-authority artifact between them. Every integration is
   **PROPOSED**; every package is independently deployable if a ServiceNow partnership is not
   pursued.

---

## 9. Source legend (ServiceNow-owned & press sources, verified 2026-08-13)

Product pages on `www.servicenow.com` were egress-blocked; the following were surfaced via web
search and should be spot-checked live before customer use. ServiceNow-owned sources are marked
**[SN]**; reputable third-party corroboration is marked **[3P]**.

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
- **[3P] AICT enforcement (Knowledge 2026)** — https://thelettertwo.com/2026/05/05/servicenow-expands-ai-control-tower-knowledge-2026/ ; https://erp.today/servicenow-ai-security-governance-knowledge-2026/
- **[3P] Autonomous Security / Armis + Veza** — https://siliconangle.com/2026/08/04/servicenow-debuts-six-autonomous-security-products-built-armis-veza/ ; https://www.helpnetsecurity.com/2026/08/04/servicenow-ai-specialists/
- **[3P] Action Fabric / Anthropic design partner** — https://www.bankinfosecurity.com/servicenows-new-platform-also-governs-everyone-elses-ai-a-31631

> **Also see** the v3.0 package's Appendix F source legend for the base product URLs (IRM, Policy &
> Compliance, AI Agents, AI Agent Orchestrator, CMDB, Change/Event Management, HRSD, SPO/PSM).

---

## 10. Status summary

- **Deliverable type:** ServiceNow-product-anchored, pipeline-driven use-case catalog (companion to
  the v3.0 differentiation package).
- **Use cases defined:** 12 (§5). **Developed in full depth:** 5 lead scenarios (§6).
- **Every use case** chains ≥3 Ugence modules as a pipeline (requirement met).
- **Integration status:** all PROPOSED. **Package maturity:** shipped but mostly reference-grade,
  production deployment validation pending (per v3.0 Appendix B).
- **Verification:** ServiceNow capabilities checked against ServiceNow-owned + corroborating
  sources on 2026-08-13; live pages should be spot-checked (egress caveat, §0).
