# ActionGate — VC Brief

**Ugence Labs | Pre-Commit Admissibility and Enforcement for Autonomous AI Agents**
*Version 1.0.0 — Updated July 2026 (external / evidence-based)*

> **Product family.** ActionGate is part of the Ugence Labs autonomous-systems portfolio.
> Some products in that portfolio produce behavioral, semantic, identity, attestation, or
> model-risk *evidence*. ActionGate can consume such evidence as optional inputs, but its
> product boundary is narrower and stands on its own: **deterministic pre-commit
> authorization and enforcement of consequential agent actions.** It grants authority to one
> exact action, once, and never depends on any single evidence source to do so. This brief
> describes ActionGate as it exists in the repository today — its implemented mechanism, its
> validation state, and what remains unproved.

---

## Page 1 — The Problem

### Autonomous-agent stacks lack a unified way to bind policy, approval, state, credential, and execution to one exact action.

The last eighteen months made it easy to give an LLM tools: MCP servers,
function-calling APIs, and agent frameworks all wire a model to a
tool-calling loop. Deterministic pre-commit checks already exist in
pieces — admission controllers, transaction-authorization systems, policy
engines, and domain-specific controls each decide something before an
action lands. What is missing is a **unified, vendor-neutral way to bind
policy, human approval, current state, credential issuance, and execution
to one exact agent-generated action** — the layer between *"the model
emitted a tool call"* and *"that exact call committed against a production
system."* That seam is where consequential harm happens — a wrong
database written, a payment released, a resource deleted, a credential
used past its intended scope — and it is precisely the seam that current
tooling treats as an afterthought.

The industry's reflex has been to add **monitoring**: log the calls,
score the outputs, filter the text, alert on anomalies. Monitoring tells
you what an agent *did*. It does not decide, before the fact, whether a
specific action is *permitted to commit* — and it does not hold the
credential the action needs, so it cannot actually stop one. An agent
that is observed but still holds a durable privileged credential is an
agent that can act despite the observer.

The questions a security-conscious buyer asks about an autonomous agent
map poorly onto what monitoring and RBAC provide:

| The question a buyer asks | What monitoring / static access control offers |
|---|---|
| *"Can a specific action be refused before it commits — not flagged after?"* | Post-hoc alerts and output classifiers; the action has already run. |
| *"Is the authority scoped to the one exact action that was approved, or to a role the agent keeps?"* | Static RBAC grants a standing role; any in-role action is permitted, not just the approved one. |
| *"If the agent is compromised, can it still use the credentials it holds?"* | Usually yes — the agent holds durable tokens; interception without credential control is monitoring, not enforcement. |
| *"Can a human approval be bound to this exact action, so it can't be replayed against a different one?"* | Approvals are typically coarse (a role, a session, a time window), not bound to an action's identity. |
| *"Is the state the decision was made against still true at the moment of commit?"* | Time-of-check/time-of-use gaps are rarely closed; the world can change between check and act. |

The gap is not model quality and not observability. It is a missing
**decision-and-enforcement boundary**: a deterministic layer that, for
each consequential action, decides admissibility against policy, evidence,
current state, human approval, and consequence — and then makes the
decision real by controlling the credential the action needs.

### Why bolting this onto an existing agent loop is hard

Retrofitting enforcement onto a tool-calling loop runs into three
structural problems. First, **decisions must be deterministic and
attributable** — the same action under the same policy and state must
always produce the same outcome, and that outcome must be reconstructable
for audit. Probabilistic or prompt-embedded checks do not clear that bar.
Second, **enforcement must control the credential, not merely observe the
call** — if the agent still holds durable authority, an interception layer
is advisory. Third, **the check must survive an adversarial and compromised
agent** — malformed input, replayed approvals, widened scope, stale state,
and a hijacked process must all be handled at the boundary, not assumed
away.

Our position is that this belongs in a **vendor-neutral pre-commit
enforcement layer** that sits at the agent's tool boundary, is transport-
and framework-agnostic, and treats authorization as a deterministic state
machine with non-compensatory hard invariants. That is the category
ActionGate is built for.

**In one line:** *ActionGate is a vendor-neutral pre-commit enforcement
layer that grants authority to one exact action, once, only after policy,
evidence, state, approval, and consequence requirements are satisfied.*

---

## Page 2 — The Architecture

### ActionGate — enforcement at the pre-commit boundary, not monitoring around it

ActionGate places a deterministic decision-and-enforcement layer between
an autonomous agent and the systems it acts on. Every action entering an
ActionGate-supported adapter is reduced to a **canonical action envelope**,
canonicalized to a stable identity, evaluated by a frozen decision state
machine, and — if allowed — executed *only* through a single-use, narrowly
scoped credential the agent never holds. The agent proposes; ActionGate
disposes; the credential broker makes the disposition real.

### The implemented pre-commit flow

```
  agent tool call  (MCP adapter today; transport-neutral core, HTTP/gRPC planned)
        │
        ▼
  Canonical Action Envelope  ──►  24-field structured action
        │
        ▼
  Canonicalize + Hash        ──►  JCS + Action-Profile canonicalization,
        │                         domain-separated length-prefixed hashing
        │                         → deterministic action hash
        ▼
  Decision State Machine     ──►  one of six frozen outcomes:
        │                         ALLOW · ALLOW_WITH_CONSTRAINTS ·
        │                         SIMULATE_AND_RETRY · REQUEST_MORE_EVIDENCE ·
        │                         ESCALATE_TO_HUMAN · DENY
        │   (non-compensatory hard invariants; a hard failure
        │    cannot be bought back by any soft/optional score)
        ▼
  Exact-Action Approval Bind ──►  approval bound to action hash + policy hash
        │                         + approver + scope + constraints + expiry + nonce
        ▼
  Execution Token + Broker   ──►  single-use scoped credential minted just-in-time;
        │                         agent holds no durable privileged credential;
        │                         replay / scope-widening rejected;
        │                         broker independently recomputes the action hash
        ▼
  Commit-time State Verify   ──►  re-read state, optimistic-concurrency CAS
        │                         (closes the time-of-check/time-of-use gap)
        ▼
  Execute  +  Tamper-evident Audit Record  (hash-chained, replayable)
```

The pipeline — **canonicalize → hash → decide → bind → broker → verify →
execute → audit** — is a deterministic contract exercised end-to-end by
the test suite, not a set of optional middleware hooks. A hard-invariant
failure cannot be outvoted by a soft score; an approval bound to one action
hash cannot authorize another; a credential minted for one action cannot be
replayed or widened for another.

### The nine technical properties enforcement rests on

1. **Canonical action envelope (24 fields).** Every action ActionGate
   authorizes is expressed in one structured envelope — actor, action type, target,
   parameters, scope, consequence class, evidence, approval, and more — so
   that authorization operates on a single, comparable representation.
2. **Deterministic action identity.** JCS plus an Action-Profile
   canonicalization, combined with domain-separated, length-prefixed
   hashing (distinct domains for action, approval, policy, evidence,
   simulation, audit, and execution-token), yields a stable action hash.
   One framed canonicalizer serves both the gateway and the broker — there
   is exactly one implementation, exercised by parser-differential tests.
3. **Six frozen decision outcomes.** ALLOW, ALLOW_WITH_CONSTRAINTS,
   SIMULATE_AND_RETRY, REQUEST_MORE_EVIDENCE, ESCALATE_TO_HUMAN, DENY — a
   closed set, decided by a deterministic state machine.
4. **Non-compensatory hard invariants.** Hard requirements (REQUIRE,
   MUST_HAVE, FORBID, MAX_SCOPE, MAX_COST, MAX_BLAST_RADIUS,
   MAX_IRREVERSIBILITY, REQUIRE_APPROVER, REQUIRE_SIMULATION,
   REQUIRE_ATTESTATION) cannot be bought back by a soft score. Optional/AI
   evidence may *escalate* a decision; it can never *override* a hard denial.
5. **Exact-action approval binding.** A human approval is bound to the
   action hash, policy hash, approver, scope, constraints, issue/expiry
   times, nonce, and sequence — so an approval for one action cannot be
   replayed against another.
6. **Single-use scoped credential broker.** The agent never holds durable
   privileged credentials. The broker mints a narrowly scoped, time-limited
   credential just-in-time for the one approved action; replay and
   scope-widening are rejected. Controlling the credential is what converts
   interception into enforcement.
7. **Commit-time state verification (TOCTOU protection).** Before commit,
   state is re-read and applied under optimistic-concurrency / compare-and-set,
   closing the gap between the moment of check and the moment of action.
8. **Independent broker recomputation.** The broker recomputes the action
   identity independently rather than trusting the gateway's assertion,
   preventing a compromised or defective gateway from substituting another
   action — **assuming the broker itself remains trusted** (a compromised
   broker is a trusted-boundary failure, outside this threat model).
9. **Transport-neutral core with a real control-plane reference.** The core
   is a deterministic in-process runtime; MCP is the currently implemented
   protocol integration, not an architectural dependency, and the core is
   designed for additional adapters such as HTTP or gRPC (planned, not yet
   built). A real Kubernetes reference implementation exercises the pattern
   against a live control plane (etcd + kube-apiserver, server-side dry-run,
   scoped TokenRequest/RBAC, PodSecurity admission).

### Optional evidence inputs — additive, never load-bearing

ActionGate can consume optional evidence — behavioral/identity signals,
attestation, model-risk or confidence scores — through the
REQUEST_MORE_EVIDENCE outcome and the soft-scoring path. Two rules hold
without exception: optional evidence can only **raise** scrutiny (escalate,
add constraints, deny), never **lower** a hard invariant; and the product's
core guarantees hold with **no** optional evidence present. The enforcement
thesis does not depend on any behavioral-biometrics, semantic, or confidence
signal — those are a separate research track, not a dependency.

### Developer surface — one boundary, deterministic decisions

At the protocol level the boundary is a single pre-commit lifecycle:

```
prepare canonical action envelope
    → evaluate against signed policy (+ optional evidence / approval)
    → receive one of six deterministic outcomes
    → attach required simulation or human approval (if demanded)
    → obtain a single-use execution authorization
    → execute exactly once through the broker (agent holds no durable credential)
    → verify state at commit + append a tamper-evident audit record
```

The reference core exposes this as a small, functional Python surface
(`action_gate_ref`) — envelopes are plain JSON/dict objects validated
against a frozen schema, and the decision is a pure function of the envelope,
the signed policy, and the current time:

```python
from action_gate_ref import gate, schema

schema.validate_envelope(envelope)                 # frozen envelope schema
decision = gate.evaluate(
    envelope, signed_policy,
    evidence=evidence,      # optional; can only raise scrutiny
    approvals=approvals,    # each bound to this action's hash
    now="2026-07-12T00:00:00Z",
)
# decision["outcome"] ∈ {ALLOW, ALLOW_WITH_CONSTRAINTS, SIMULATE_AND_RETRY,
#                        REQUEST_MORE_EVIDENCE, ESCALATE_TO_HUMAN, DENY}
```

The same operations are exercised from a real CLI (`action_gate_ref`:
`validate-envelope`, `canonicalize`, `hash-action`, `verify-approval`,
`verify-token`, `verify-audit-chain`). Credential brokering and single-use
execution live in the separately-tested gateway package, not in the
reference core. The reference core is Python 3.11+ standard-library only and
ships with conformance vectors, a frozen envelope schema, and frozen
transition tables, so an integrator can verify byte-for-byte that their
implementation matches the specified decision behavior. The runnable
enforcement gateway, the MCP protocol adapter, and the Kubernetes reference
build on that same core without changing the decision contract.

**Honest surface note.** The reference core is deliberately scoped: no
network, no MCP, no credential custody, no AI/biometric evidence — it
proves the decision machine in isolation. Credential brokering, transport,
and control-plane enforcement live in the separately-tested gateway, MCP,
and Kubernetes packages. This separation is intentional and is reflected
in the evidence table on Page 4.

---

## Page 3 — Competitive Landscape

### The category: an AI Action Authorization platform, not another IAM

ActionGate is best described as *a new cybersecurity platform focused on AI
agent authorization and action governance* — an **enterprise AI Action
Authorization Platform that secures autonomous agents before they perform
real-world actions.** It is deliberately **not** positioned as "the next
Microsoft Entra ID." Entra, Okta, and the IAM incumbents are identity
platforms — directory services, SSO, MFA, conditional access, federation,
lifecycle, PIM, thousands of SaaS integrations, a decade and thousands of
engineers. Inviting that comparison would set expectations around identity
and directory services that are outside ActionGate's scope. It is also not
"just a tool" (a JWT library, an OPA engine, an admission webhook, an MCP
middleware) — those are *components*. ActionGate aims to be the **control
plane in front of every consequential AI action**, which is a platform.

The distinction is a matter of which question is being answered. Entra
answers *"who are you?"*. ActionGate answers *"should this exact
AI-generated action execute, right now?"* — a different problem, one layer
down the stack.

### Where ActionGate sits in the enterprise stack

```
  Identity           ──►  Microsoft Entra / Okta        (who may authenticate)
       │
  Authentication
       │
  Authorization
       │
  Secrets            ──►  CyberArk / HashiCorp Vault     (who receives credentials)
       │
  Infra Policy       ──►  OPA / Gatekeeper / Kyverno     (is this config allowed)
       │
  Cloud Permissions  ──►  AWS IAM / Azure RBAC           (what a role may do)
       │
  ═══════════════════════════════════════════════════════════════════════
       an AI agent decides to perform a specific action
  ═══════════════════════════════════════════════════════════════════════
       │
       ▼
  ██  ActionGate  ██   ← decides admissibility of THIS action, then
       │                 mints a single-use credential to execute it
       ▼
  Runtime execution  ──►  Kubernetes · GitHub · Terraform · Databases ·
                          Email · Payments · Cloud APIs
```

ActionGate operates **after identity is established but before an action
executes**. That placement is deliberate: it avoids competing head-on with
identity vendors, and instead sits at the seam the whole stack above leaves
open once an autonomous agent — not a human at a console — is the thing
choosing the next action.

### Four adjacent categories, not one competitor

ActionGate does not have a single incumbent competitor; today its
capabilities are spread across four adjacent categories, and it sits between
all four rather than replacing any one of them.

| Category | Examples | What they protect |
|---|---|---|
| **Identity** | Microsoft Entra, Okta | Who may authenticate |
| **Privileged access** | CyberArk, BeyondTrust | Who receives privileged credentials |
| **Policy engines** | OPA, Gatekeeper, Kyverno, HashiCorp Sentinel | Whether an infrastructure configuration is allowed |
| **AI agent frameworks** | LangGraph, CrewAI, OpenAI Agents | How agents execute tools |

ActionGate combines pieces of these — policy evaluation, credential
brokering, an execution boundary — into one runtime focused specifically on
AI-generated actions. That makes it materially larger than a developer
library, and materially more specialized than an identity platform. As an
*illustrative* (not precise) sense of relative breadth: an OPA-class engine
is roughly 8–10× a single library, a privileged-access module perhaps ~20×,
ActionGate at full planned scope perhaps 30–80×, and Entra ID 500–1000×. The
point of the scale is only this — ActionGate is a focused platform with room
to grow, not an identity suite and not a component.

"Agent security" is a noisy space, but most of the crowd is solving a
different problem than ActionGate. Most tools **observe** agent behavior or
**grant standing access**; ActionGate **decides admissibility before commit
and controls the credential** so the decision is enforceable. The table
below positions ActionGate against each family, stating for every row how
it differs and why that difference matters to a security buyer.

| Category | Representative players | What they ship | How ActionGate differs — and why it matters |
|---|---|---|---|
| **Agent frameworks / tool-calling loops** | LangChain / LangGraph, CrewAI, AutoGen, MCP servers | Libraries and protocols that wire an LLM to tools and dispatch calls. | These decide *which* tool the model wants; they do not deterministically decide whether a specific call is *admissible to commit*, and they do not hold the credential. **Why it matters:** ActionGate sits at the boundary they dispatch *into*, adding a deterministic decision + single-use scoped credential — additive, not competitive. |
| **AI guardrails / output moderation** | NeMo Guardrails, Guardrails AI, Llama Guard | Content-level filters and classifiers over model text. | Guardrails protect *text*; a wrong or over-scoped *action* is not something a content filter is positioned to refuse. **Why it matters:** ActionGate intervenes at the action-commit boundary and composes with a text guardrail rather than replacing it. |
| **Agent observability / eval** | LangSmith, Langfuse, Arize, Helicone | Instrumentation that records prompts, calls, and traces after the fact. | Observability answers *"what did the agent do?"*; it is monitoring, not enforcement, and holds no credential. **Why it matters:** ActionGate answers *"is this exact action allowed to commit right now?"* and emits its own tamper-evident audit record as a byproduct of deciding. |
| **Identity / secrets / privileged-access** | Vault, cloud IAM/STS, SPIFFE/SPIRE, PAM | Issue and broker credentials and workload identity. | Strong at *issuing* scoped credentials, but they grant to a role/workload, not to *one exact approved action*, and they do not run the pre-commit admissibility decision. **Why it matters:** ActionGate uses just-in-time scoped credentials as its enforcement mechanism, but binds them to a specific action hash and approval — it consumes this layer rather than replacing it. |
| **Policy engines / admission control** | OPA/Gatekeeper, Kyverno, Kubernetes admission | Evaluate declarative policy against requests (often at the control-plane admission point). | Powerful policy evaluation, but scoped to their platform's request model and blind to agent-specific concerns (exact-action approval binding, consequence class, agent-held credentials, TOCTOU at the agent boundary). **Why it matters:** ActionGate's Kubernetes reference *uses* admission and server-side dry-run, and adds the exact-action credential-broker enforcement admission alone does not provide. |

### Feature-level differentiation

In the table below, "No" means *not the product family's native abstraction*
— not a claim that it is impossible to approximate through custom
configuration or integration. The point is where each capability sits at the
center of the product versus at its periphery.

| Capability | ActionGate | Guardrails / moderation | Observability | IAM / secrets brokers |
|---|---|---|---|---|
| Deterministic pre-commit **admissibility decision** | **Yes** — six frozen outcomes | No (text-level) | No (post-hoc) | No (grants access, not per-action admissibility) |
| Decision bound to a **single exact action identity** | **Yes** — canonical hash | No | No | Partial (role/workload, not one action) |
| **Single-use scoped credential** the agent never holds | **Yes** — broker-minted | No | No | Partial (scoped, but not per-approved-action, replay-bound) |
| **Human approval bound to the action hash** | **Yes** | No | No | No |
| **Commit-time state verification** (TOCTOU) | **Yes** — CAS re-read | No | No | No |
| Optional evidence can only **raise** scrutiny | **Yes** — non-compensatory | N/A | N/A | N/A |
| Transport-neutral core | **MCP implemented; HTTP/gRPC planned** | Varies | Varies | Varies |
| Ecosystem breadth / maturity | Early, focused | **Broad** | **Broad** | **Mature** |

### How the authorization primitive differs

ActionGate defines a focused product category around AI action
authorization by integrating known policy, capability, approval, and audit
primitives at the agent-action boundary. It does not claim a new
computer-science primitive — the differentiation is the *unit of
authorization* and the *lifecycle they are bound into*, illustrated below.

1. **The decision object is an action, not a principal.** Traditional policy
   asks *"can Alice delete Pods?"* and RBAC answers yes/no for the role.
   ActionGate asks *"can Alice's agent delete **this exact** Pod, with this
   justification, this state hash, this approval, right now?"* — the
   authorization unit is one individual action, not a user or role. This is
   the biggest conceptual difference. **(MEASURED — the 24-field envelope +
   action hash.)**
2. **Just-Enough Authorization, not Just-In-Time.** Privileged-access tools
   grant a credential good for 15–60 minutes. ActionGate mints a capability
   for one approved action, executes exactly once, then destroys it — not
   "just-in-time" but "just-enough." **(MEASURED — single-use scoped broker.)**
3. **Canonical action identity as the security primitive.** Competitors
   authorize *principal → role → permission*. ActionGate authorizes
   *canonical action envelope → action hash → approval → execution token →
   one execution.* **(MEASURED.)**
4. **Approval bound to one immutable action.** A traditional approval reads
   "approve Terraform, production." An ActionGate approval binds to *delete
   deployment · namespace=payments · resource=X · state-hash=ABC ·
   rollback=XYZ · policy-version=1.3* — it cannot be replayed against a
   different action. **(MEASURED — exact-action approval binding.)**
5. **One abstraction across heterogeneous actions (breadth is roadmap).**
   Policy engines each understand one domain (Kyverno: Kubernetes; Sentinel:
   Terraform). ActionGate's envelope is designed so *delete Pod / delete IAM
   role / delete S3 bucket / delete repo / delete database* share one
   authorization model. **Today only the Kubernetes reference is validated;
   the transport-neutral core makes the abstraction real, but AWS, GitHub,
   Terraform, and database connectors are roadmap, not shipped.**
6. **AI-first by construction.** Existing products assume *human → requests
   action.* ActionGate assumes *AI agent → generates action → needs
   authorization.* That assumption changes the architecture (deterministic
   identity, non-compensatory gates, agent holds no durable credential).
   **(MEASURED.)**
7. **A runtime lifecycle, not a policy verdict.** OPA returns *policy →
   allow → done.* ActionGate runs *policy → approval → capability →
   execution → verification → audit → destroy capability* as one bound
   lifecycle. **(MEASURED.)**
8. **Behavioral intelligence — future, not a current claim.** If the
   optional behavioral/identity/confidence work succeeds, authorization could
   eventually fuse *identity + behavior + confidence + policy + exact action.*
   This is a **roadmap item on a separate research track, not a present
   differentiator**, and can only ever *raise* scrutiny.

### Competitive positioning matrix

This matrix describes each product's **primary/native abstraction**, not the
limits of what it could be configured to do. Enterprise platforms may
approximate several of these capabilities through custom policy, workflow,
conditional access, or integration; the cells below mark where a capability
is *central* to the product versus adjacent to it. Labels: **Native**
(central capability) · **Config/integration** (achievable but not the native
abstraction) · **Ref-impl** (implemented in ActionGate's reference) ·
**Planned** · **Not established in this review**.

| Product | Identity | Policy | Action-bound identity | Single-use capability | AI-native | Cross-domain |
|---|---|---|---|---|---|---|
| **Microsoft Entra** | Native | Config/integration | Not central | Config/integration | Not central | Native |
| **CyberArk** | Native | Config/integration | Not central | Partial (short-lived) | Not central | Native |
| **OPA** | — | Native | Not central | — | Not central | Native |
| **Kyverno** | — | Native | Not central | — | Not central | Kubernetes |
| **HashiCorp Sentinel** | — | Native | Not central | — | Not central | Terraform |
| **AI agent frameworks** | — | Minimal | Not central | — | Native | Varies |
| **ActionGate** | Uses existing identity | Native | **Ref-impl** | **Ref-impl** | Native | **Planned** * |

\* *Cross-domain breadth is the design intent of the transport-neutral core
and the domain-agnostic envelope. Today it is **reference-validated on
Kubernetes**; additional connectors (AWS IAM, Terraform, GitHub, databases)
are planned, not yet shipped. The label marks architectural fit, not present
breadth.*

**The safest competitive statement.** We do not claim these products *cannot*
do the above. Their **primary abstraction is identity, entitlement, policy,
or admission**; ActionGate's **primary abstraction is a canonical, one-use
autonomous-agent action lifecycle.** That difference in what sits at the
center of the product — not a checkbox a competitor lacks — is the positioning.

### Where the moat is — and is not

**The moat is the runtime, not any single feature.** We are deliberately
careful *not* to claim the moat is "action hashing" or "credential brokering"
on their own — both have related precedents. The stronger, more honest
framing is architectural: **ActionGate is a deterministic authorization
runtime for AI-generated actions, in which an immutable action description,
policy evaluation, human approval (when required), short-lived capability
issuance, execution verification, and audit are all bound into a single
execution lifecycle.** That end-to-end binding — not any one primitive — is
what positions ActionGate as an authorization runtime designed for autonomous
AI systems rather than another policy engine.

**Primary — what the product rests on (all MEASURED in the repository):**
- **Deterministic exact-action admissibility, credential-enforced.** The
  combination of (a) a canonical action identity, (b) a frozen
  non-compensatory decision machine, and (c) a single-use scoped credential
  the agent never holds is the durable differentiator. Interception without
  credential control is monitoring; ActionGate controls the credential.
- **Enforcement survives a compromised agent within a stated threat model.**
  An isolated, fully-executed compromised-agent experiment demonstrates that
  the exact-action + isolated-broker design blocks decisive attacks that
  static RBAC, admission-only, and time-window-JIT designs do not.

**Secondary optionality — upside, not the foundation:**
- **Optional evidence inputs** (behavioral, semantic, attestation,
  model-risk). These can raise scrutiny and enrich escalation decisions, but
  the product's guarantees hold without them. They are a separate research
  track; the company does not depend on any one of them.

**Honest scope — where ActionGate does not compete (year one).** It does not
try to win on policy-engine breadth, secrets-management maturity, or agent-
framework ecosystem. It wins on the one boundary those layers leave open:
deterministic, credential-enforced, exact-action admissibility at the agent's
pre-commit seam — within a single-host, trusted-broker threat model today.

### In one sentence

Frameworks decide which tool to call, guardrails filter text, observability
records what happened, and IAM grants standing access — ActionGate decides,
deterministically and before commit, whether *this exact action* is allowed,
and holds the credential that makes the decision real.

---

## Page 4 — Evidence & Roadmap

### What is measured today (v1.0.0, internal evidence)

| Area | Current state |
|---|---|
| **Reference conformance core** | 123 tests passing — canonical envelope, JCS + Action-Profile canonicalization, domain-separated hashing, six-outcome state machine, hard-invariant operators, conformance vectors (Python 3.11+ stdlib only). |
| **Runnable enforcement gateway** | 39 tests passing — single-use execution token + scoped broker-minted credential; nine end-to-end enforcement demonstrations; transport-agnostic core. |
| **MCP protocol adapter** | 43 tests passing — tool-invocation interception → canonical envelope → gateway → execution only via valid token + single-use broker capability; fifteen end-to-end scenarios. |
| **Kubernetes control-plane reference** | 30 tests total: 14 environment-independent tests (passing) and 16 real-cluster tests that skip when the control plane is unavailable. *Separately*, 18 real-cluster demonstration scenarios (server-side dry-run, scoped TokenRequest/RBAC, PodSecurity admission, commit-time state verification) execute in the reference cluster environment — these are demonstrations, not counted in the 30 tests. |
| **Isolated compromised-agent experiment** | 39 tests total: 37 environment-independent tests (unit 14 + remediation 11 + parser-differential 12, all passing) and 2 end-to-end isolation tests that skip without root / netns privileges. Covers four protection domains, netns/user/process separation, Ed25519 public-key-only verification, mTLS SAN identity, durable SQLite replay store, independent broker recomputation, tamper-evident audit checkpoints. *Separately*, the compromised-agent red-team run executes 27 attacks (see verdict row) — a demonstration, not part of the 39 tests. |
| **Total** | **274 tests** across the five packages (123 + 39 + 43 + 30 + 39), each auditable per the rows above; where a row lists demonstrations, they are stated separately and are **not** folded into the 274. Cluster demonstrations and root-required tests skip cleanly without that infrastructure. |
| **Mechanical red-team verdict (isolated)** | `ISOLATED_GATE_THESIS_SUPPORTED` — 27/27 attacks blocked, all **executed** (no asserted/hard-coded passes). On the decisive-attack baseline, the exact-action gateway + isolated broker design blocks attacks that static RBAC (blocks 1), admission-only (blocks 1), and time-window-JIT (blocks 1) do not. |
| **Independent architectural validation** | **`SUPPORTED_WITH_LIMITATIONS`** — see below. |

All numbers above are from this repository and its test suites — not
third-party benchmarks. No external red-team or third-party audit has been
run yet (see roadmap).

### Independent security status: `SUPPORTED_WITH_LIMITATIONS`

An independent architectural validation was run against ActionGate's
enforcement theses. Its first pass returned `PARTIALLY_SUPPORTED`, raising
eleven findings (N1–N11): policy-completeness bypass on non-container fields
(N1, HIGH), double-commit + residual RBAC + audit gap on teardown failure
(N2, HIGH), partial-commit/crash recovery (N3), an agent-triggerable gateway
DoS (N4), the broker not recomputing the action hash (N5), red-team verdict
inflation from asserted-not-executed attacks (N6), distributed-replay
split-brain (N7), unverified fetch of the trust base (N8), unframed ad-hoc
hashing (N9), coarse transport identity (N10), and a parser-differential
surface (N11).

Each finding was remediated at the mechanism level, and the remediation is
itself tested (`test_remediation.py`, plus the executed attack suite): the
falsifying defects (N1, N2, N4) no longer reproduce and each now has an
executed, measured block; exact-action binding is broker-verified (N5); the
verdict is 27/27 **executed** rather than partly asserted (N6); audit
divergence is deterministically detectable (N3); duplicate execution is
rejected across a second broker on a shared store (N7); transport identity is
SAN-based (N10); trust roots are pinned (N8); and a single framed
canonicalizer serves both sides (N9), exercised by parser-differential tests
(N11). Two latent bugs the new executable tests surfaced (manifest aliasing,
audit-chain fork under concurrency) were found and fixed.

This lifted the honest standing from `PARTIALLY_SUPPORTED` to
**`SUPPORTED_WITH_LIMITATIONS`**. It deliberately stops short of a stronger
verdict because real limitations remain **by scope, not oversight**:
single-host durable store (no cross-host distributed transaction), a trusted
broker / signing-root / cluster, file-permission key custody with pure-Python
crypto, an unverified build-time supply chain, and race coverage measured
only for the update path. We report this verdict rather than the bare
mechanical `ISOLATED_GATE_THESIS_SUPPORTED` because independent validation is
the more conservative and more honest statement of where ActionGate stands.

### Evidence classification

| Signal / capability | Evidence | Status |
|---|---|---|
| Six-outcome decision machine + hard invariants | 123 reference tests + conformance vectors | **MEASURED** |
| Canonical identity (JCS + framed hashing) | Reference + parser-differential tests | **MEASURED** |
| Single-use scoped credential broker | 39 gateway tests + nine E2E demos | **MEASURED** |
| MCP interception → gateway enforcement | 43 tests + fifteen scenarios | **MEASURED** |
| Exact-action + isolated-broker beats RBAC/admission/JIT | Isolated experiment, 27/27 executed | **MEASURED** (within stated threat model) |
| Kubernetes control-plane enforcement | 14 tests pass; 18 cluster demos | **REFERENCE-VALIDATED** (cluster demos skip without infra) |
| Independent architectural validation | N1–N11 remediated + re-executed | **MEASURED** → `SUPPORTED_WITH_LIMITATIONS` |
| Optional evidence inputs (behavioral / semantic / attestation / model-risk) | Interface implemented; can only raise scrutiny | **IMPLEMENTED, UNVALIDATED** (separate research track) |
| Cross-host distributed enforcement | Not built | **NOT STARTED** |
| Third-party external red-team / audit | Not run | **NOT STARTED** |

*Classification key: **MEASURED** = supported by this repo's tests/experiments;
**REFERENCE-VALIDATED** = demonstrated against a real reference system, with
some demonstrations requiring infrastructure not present in CI;
**IMPLEMENTED, UNVALIDATED** = code exists, not yet validated as adding value;
**RESEARCH** = open question, off the product path; **NOT STARTED** = not yet built.*

### Honest limitations

| Limitation | Why it exists | Status |
|---|---|---|
| Single-host durable store | No cross-host distributed transaction implemented | By scope; Stage 4 |
| Trusted broker / signing-root / cluster | Trust anchored in the broker and its roots | By scope; hardening across stages |
| File-permission key custody, pure-Python crypto | No HSM/audited-AEAD dependency in the environment | By scope; Stage 3 productionization |
| Unverified build-time supply chain | Trust roots pinned (N8) but build provenance unverified | Stage 4 |
| Race coverage on the update path only | Concurrency measured for `update`, not all verbs | By scope; Stage 2 |
| No third-party external red-team | Only internal, fully-executed experiments so far | Stage 1–2 |
| Optional evidence unvalidated | Interface exists; value not yet demonstrated | Research track |

### Representative use cases (by connector-availability status)

The enforcement *mechanism* is domain-agnostic, but each use case also
requires a connector. We distinguish mechanism portability from connector
availability:

- **Reference-validated (Kubernetes / infrastructure actions).** Resource
  creation/deletion and config changes against a real control plane, with
  server-side dry-run and commit-time state verification — the strongest
  validated surface today.
- **Implemented through generic / mock adapters.** Filesystem, HTTP-tool,
  and Terraform-style pathways exist as mock adapters (no real egress),
  exercising the enforcement lifecycle without a production backend.
- **Target use case / roadmap (not yet a connector).** Payments, email,
  databases, IAM, and broader cloud actions — e.g. a refund gated by
  exact-action approval + single-use credential. These illustrate the
  *mechanism*; the connectors are on the roadmap, not shipped.

Two capabilities are mechanism-level and available today regardless of
connector: **human-in-the-loop for irreversible actions** (ESCALATE_TO_HUMAN
with an approval bound to the exact action hash, non-replayable) and
**compromised-agent containment** (an agent holding no durable credential
cannot act even if its process is hijacked), plus a tamper-evident,
replayable audit record of every admissibility decision.

### Roadmap — a maturity timeline, not a coding schedule

A candid note on timelines. AI compressed the *prototype-construction* phase
dramatically: the reference model, real enforcement paths, tests, mock
integrations, and a Kubernetes reference environment already exist. It did
**not** compress the work that turns a prototype into a deployable security
platform — hardening, integration, operational reliability, independent
assurance, and customer acceptance. Those are mostly *boundary* work
(key custody, workload identity, credential rotation/revocation, multi-host
replay protection, HA, durable audit, egress control, incident response,
external penetration testing) and *calendar* work (a customer's architecture,
threat-model, penetration, legal, and privacy reviews plus a controlled
rollout) — neither of which is eliminated by generating more application
code. The stages below are therefore stated as maturity milestones with
realistic durations for a focused team, not as quarters of coding.

| Maturity target | Realistic duration (focused 3–5 person team) | What it means |
|---|---|---|
| **Demo / research prototype** | **Already achieved** | Real enforcement paths, 274 tests, mock integrations, Kubernetes reference environment, isolated red-team, independent validation at `SUPPORTED_WITH_LIMITATIONS`. |
| **Design-partner pilot** | ~1 month (4–8 weeks) | One environment, one cluster, one MCP client, a small policy set, one hardened broker, KMS-backed signing, persistent audit/replay storage, supervised single workflow. |
| **Internal production beta** | 2–3 months | Multi-host deployment, HA, failure recovery, monitoring, key management, incident handling; runs continuously without per-action engineering supervision. |
| **Enterprise production v1** | 4–6 months | Customer identity integration, SIEM/OpenTelemetry export, durable audit retention, upgrade/rollback, a second connector, external security remediation, first reference customer. |
| **Regulated-enterprise platform** | 9–15 months | Multiple connectors, distributed enforcement, policy administration, compliance evidence, tenant isolation, scale, customer security reviews. |

**Stage 1 — Pilot-ready vertical (~month 1).** Deliberately narrow scope to a
single, supervised, credible pilot — *not* a broadly deployable platform:
production-infrastructure agent actions on Kubernetes/MCP, one hardened
broker, KMS-backed asymmetric signing, persistent PostgreSQL (or equivalent)
replay/audit storage, basic metrics and incident logging, a small
administrative approval surface, and deployment automation. **Goal:** one
design partner can safely run one supervised workflow. Honest label:
*pilot-ready, single-workflow, supervised reference deployment* — not yet a
production security platform.

**Stage 2 — Internal beta (months 2–3).** Multi-host deployment, high
availability, failure recovery, operational dashboards, policy-backend
integration, an **external penetration test**, latency and false-escalation
measurement, and stronger Kubernetes policy coverage. Also: extend measured
race coverage beyond the update path to all decision verbs, and broker
rotation/revocation. **Goal:** operate continuously without engineering
supervision of every action.

**Stage 3 — Enterprise v1 (months 4–6).** Hardened deployment packaging,
customer identity integration, SIEM/OpenTelemetry export, production audit
retention, upgrade/rollback procedures, a second connector driven by customer
demand, external-security remediation, audited key custody (HSM / audited
AEAD) replacing file-permission custody, and support runbooks. **Goal:** first
production reference customer.

**Stage 4 — Platformization (months 6–15).** Multiple cloud/tool connectors
(each with its own action mapping, credential scoping, simulation/preview,
state hashing, conditional-commit and rollback semantics — Kubernetes is only
one), distributed enforcement across hosts, policy administration, a
compliance program, tenant isolation, scale, verified build-time supply chain,
and broader deployments. **Goal:** a repeatable enterprise product rather than
a bespoke pilot.

*A solo-founder path would run roughly 12–24 months to the same milestones,
because engineering, security, operations, integration, documentation, sales,
and compliance would compete for one person's time.*

**Parallel research track (separate from the product roadmap)**
- Evaluate optional evidence inputs — behavioral, semantic, attestation, and
  model-risk signals — for whether they measurably improve escalation
  decisions on held-out data. These signals return to the product path **only**
  if they earn it on evidence, and can only ever *raise* scrutiny. The product
  roadmap above does not depend on this outcome.

### The ask

We are raising to take ActionGate from a tested reference implementation and
runnable enforcement gateway through the maturity stages above to an
externally-validated, production-hardened enforcement layer. The mechanism is
implemented and measured today — 274 tests across a stdlib reference core, a
credential-brokering gateway, an MCP adapter, a real Kubernetes control-plane
reference, and a fully-executed compromised-agent experiment — and an
independent architectural validation places it at `SUPPORTED_WITH_LIMITATIONS`
after N1–N11 remediation. Capital is earmarked for a supervised design-partner
pilot, then the hardening, integration, external red-teaming, distribution,
audited key custody, and compliance work that turn a validated prototype into
a deployable product.

We are deliberate about what each timeframe buys. **One month** is realistic
for a narrow, supervised, single-workflow design-partner pilot — a legitimate
product pilot, not merely a demo, but not yet a broadly deployable platform.
**Three to six months**, with a focused 3–5 person team, is realistic for the
first serious production deployment. **Nine to fifteen months** is realistic
for a repeatable enterprise-grade product with multiple integrations and
security/compliance evidence. The fast prototype compressed the *construction*
phase; the remaining time is mostly hardening, integration, external
validation, operationalization, and customer deployment — calendar work that
generating more code does not remove.

Enforcement — not monitoring — is becoming a precondition for putting
autonomous agents in front of money, infrastructure, and customers. ActionGate
is building the deterministic, credential-enforced, exact-action boundary that
gap requires, and is honest about what is proved, what is reference-validated,
and what realistically remains — in engineering *and* in calendar time —
before it is a production security platform.

---

*Contact: Rakesh Mohan — Ugence Labs*
*Repo: `rasaha/symbolu` · Modules: `cyber_security/action_gate_reference/`, `action_gateway/`, `action_gateway_mcp/`, `action_gateway_k8s/`, `action_gateway_isolated/`*
*v1.0.0 · 274 internal tests · isolated red-team 27/27 executed · independent validation `SUPPORTED_WITH_LIMITATIONS` (N1–N11 remediated)*
