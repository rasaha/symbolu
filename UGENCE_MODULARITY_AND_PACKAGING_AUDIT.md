# Ugence Modularity & Product-Packaging Audit

> **Terminology update — Ugence Decision Governance (2026-08-01).** Canonical vocabulary per
> [`docs/architecture/ADR_UGENCE_DECISION_GOVERNANCE_TERMINOLOGY_AND_BOUNDARIES.md`](docs/architecture/ADR_UGENCE_DECISION_GOVERNANCE_TERMINOLOGY_AND_BOUNDARIES.md).
> **Ugence Decision Governance** is the umbrella. The capability referred to below as "Decision
> Governance" is the **Decision Authority** capability, still implemented under the
> **`decision_governance`** package (name unchanged this phase). The capability inventory is
> **ten**: **Model Selection** is a distinct capability, separated from Hybrid LLM. The AI Control
> Plane and the orchestrator are **optional and bypassable**. Documentation-only; nothing is
> renamed here.

**Question:** Can a customer buy and deploy any one of TAP, Decision Governance, ActionGate,
ACP, StoryGraph, Agent Runtime, Hybrid LLM, Context Minimization, or LLM Steering
*independently* — without adopting the whole Ugence platform — and if so, what shared
core / common interface / router / integration layer is actually required?

**Method:** read-only inspection of the current repository (no production code modified).
Ten parallel deep-inspection passes (one per module + one for the shared core), each
required to cite `file:line` evidence and to separate **code evidence** from **doc/VC-brief
claims**. Findings were cross-checked against the frozen platform manifest, the neutral
provider contracts, the FastAPI console, the packaging/distribution verifiers, and the
company's own productization roadmap.

> **Scope honesty.** This repo is a large research monorepo (~100 top-level directories,
> most of it LLM/robotics research). The "Ugence governance platform" is a *minority* of
> it. Wherever a capability is research, mocked, frozen, or spec-only, this audit says so
> and does **not** fill the gap from documentation.

---

## 1. Executive summary

**Overall verdict: `MODULAR SALES VIABLE AFTER BOUNDARY HARDENING`.**

The codebase is **boundary-clean but not yet deployable as independent products.** Three
things are simultaneously true and must not be conflated:

1. **The decoupling is real.** A frozen "Decision Governance Platform v1.0.0" (1006 tests)
   ships **four** components as **separately-built wheels with enforced boundary isolation**:
   `decision-governance` (kernel), `dgm-provider-framework` (`governance_providers`),
   `dgm-tap-provider`, `dgm-actiongate-provider`. A distribution verifier builds each wheel,
   installs it into a clean venv with **no monorepo on the path**, and proves the app layers
   (`ai_hiring/domains/applications`) are absent and that TAP and ActionGate never reference
   each other (`packaging/verify_tap_provider_distribution.py`, `verify_independent_distribution.py`).
   Twenty frozen invariants (F1–F20) and an acyclic dependency rule set are machine-verified
   (`platform_freeze/verify.py`). The *most* self-contained modules (StoryGraph, ActionGate's
   real enforcement engine) import **zero** other Ugence packages. This is not an
   integrated monolith.

2. **Almost nothing is deployable or sellable as a plug-and-play product *today*.** Under the
   strict 8-part definition (install independently → connect via a documented API/SDK/event →
   configure without editing source → use customer identity/policy/observability → operate
   without unrelated Ugence capabilities → upgrade under a versioned contract → deliver
   standalone value → audit/support independently), **no module passes.** The recurring
   failures are identical across modules: **the only real interface is an in-process Python
   object** (the one network surface, `ugence_console_api`, is unauthenticated, CORS-`*`,
   in-memory-audit, shadow-only, and not even in the `Procfile`); **there is no `tenant_id`
   anywhere in the neutral contracts or the console**; there is **no durable/tamper-evident
   persistence**; and several "products" are wired to **deterministic mocks** while the real
   engine sits **unwired** beside them (TAP, ActionGate, ACP, Context Minimization all show
   this exact split).

3. **The barrier is productization, not coupling.** What blocks modular sales is a small,
   repeatable set of hardening tasks (a network/service surface, auth, tenant context,
   durable audit, packaging, and wiring the real engine in place of the reference mock) —
   **not** an architectural entanglement that forces whole-platform adoption.

**Consequently:** a customer *cannot today* buy-and-run any one module as a product. But the
architecture is genuinely modular, so this is reachable. The shared core that is **actually
required** is a **small embedded governance-contract SDK** (identity/tenant/correlation/
evidence-refs/result-envelope + registry + deterministic resolution) — which **already
exists in nascent form** as `governance_providers` — optionally fronted by a hosted control
plane for multi-tenant/hosted deployments. **No module router is required for independence,
and no workflow orchestrator is required except as an opinionated "governed-loop" product
that customers must be free to bypass.**

**Populations at a glance:**

| Population | Modules | State |
|---|---|---|
| **Frozen, boundary-clean, mock/reference engines** | Decision Governance, TAP-provider, ActionGate-provider, provider framework | Real independent *packaging*; in-process only; no tenant/auth/service; provider engines are deterministic mocks |
| **Real engines, zero Ugence coupling, unpackaged/unwired** | StoryGraph, ActionGate enforcement engine (`cyber_security/action_gate*`), Agent Runtime (migration) | Genuinely self-contained; need packaging + service surface + hardening |
| **Frozen/shadow research** | ACP (live-clearance engine), Hybrid LLM, LLM Steering, Context-Min token core | Not products; advisory boundaries correct; validation synthetic/GPU-gated |
| **Authority-confused / bundle** | Agentic Framework (the mature Agent Runtime) | Embeds policy authority; sell only as governed bundle |

---

## 2. Module maturity & standalone-readiness matrix

`I` = independently; interface "in-proc" = the only real caller interface is a Python object.

| Module | Impl. status (code, not docs) | Real interface today | Persistence | Tenant/Auth | Authority | Independent value today | Classification |
|---|---|---|---|---|---|---|---|
| **Decision Governance** | Implemented, v1.0.0 **frozen** (hexagonal kernel, 29 pkg-tests) | in-proc SDK (frozen API snapshot) | in-memory ports (pluggable) | `tenant_id` on every record; IdentityProvider **port** | Binding-decision **record** + evidentiary ledger | Full chain works in-proc w/ reference adapters | `INDEPENDENT_AFTER_BOUNDARY_HARDENING` |
| **TAP** | Adapter implemented (38 tests) over a **deterministic mock**; real engine `assertion_governance/engine.py` **not integrated** | in-proc SDK; REST only via console | none (stateless) | none | Advisory / Evidentiary | Weak (mock verdicts) | `INDEPENDENT_WITH_SHARED_CORE` (value RESEARCH-gated) |
| **ActionGate** | **Two disjoint families**: (A) provider adapter over a mock (30 tests); (B) real enforcement engine (~322 tests: ref/gateway/mcp/k8s/isolated/policy) | (A) in-proc SDK; (B) in-proc + real MCP + mTLS network svc (`_isolated`) + k8s gateway | (B) SQLite append-only ledger; etcd | (B) rich identity/SoD; per-namespace; (A) `tenant=""` | **Binding authorization + enforcement** (owns exact-action auth) | (B) real standalone enforcement | A: `INDEPENDENT_WITH_SHARED_CORE`; B: `INDEPENDENT_AFTER_BOUNDARY_HARDENING` |
| **ACP** | **Two tracks**: console gate (63 LOC threshold); robotics engine (~4,890 LOC, **frozen, shadow-only, OFF by default**, 112 tests) | console REST `/v1/actions/clear`; engine in-proc | in-memory ring buffers | none (content-identity only) | Advisory / operational-clearance recommendation | Shadow only; blocks nothing real | Engine `RESEARCH_CAPABILITY`; console gate `INDEPENDENT_AFTER_BOUNDARY_HARDENING` |
| **StoryGraph** | Implemented, **frozen-but-working** real matcher (v2.0.0, 289 tests) | in-proc SDK + JSON CLI + **real policy-as-code** (JSON-Schema) | stateless matcher; optional local sqlite | none (opaque strings) | **Advisory / Evidentiary** (never ALLOW/DENY) | Real advisory sequence-risk detection | `INDEPENDENT_AFTER_BOUNDARY_HARDENING` (most self-contained) |
| **Agent Runtime** | migration: clean proposer (74 tests); framework: mature but **embeds authority** (2,260 tests); v2: **docs only** | in-proc library (framework also `POST /authorize`) | in-memory (pluggable Protocol) | none (identity dir = persona classifier, not IAM) | migration: **Proposer/advisory**; framework: **binding (embedded)** | migration real but skeletal (3 CER profiles, shadow fixtures) | migration `INDEPENDENT_AFTER_BOUNDARY_HARDENING`; framework `BUNDLE_ONLY`; v2 `RESEARCH` |
| **Context Minimization** | Wired path = lossless dedup only (real); token-reducing extractive core = research prototype in `experiments/` (ActionGate-coupled) | in-proc fn + console REST `/v1/gateway/minimize` (via `sys.path` hack) | none | none | Advisory / Evidentiary (filters only) | Weak (dedup only) wired; token savings unwired | `INDEPENDENT_AFTER_BOUNDARY_HARDENING` (token core RESEARCH) |
| **Hybrid LLM** | Handover = **scaffold** (mock in-house + mock frontier); model-selection pilot **credential-blocked**; neural model **falsified** (0% needle) | library + demo CLI | none | none | Advisory (route/reduce/refuse) | No — scaffold + blocked pilot | `RESEARCH_CAPABILITY` |
| **LLM Steering** | Real deterministic C×R×S core (50 tests) but under `scripts/…/csr_match_filter/`, **unpackaged, unwired, console read-only** | internal Python API (not installable) | none | none | Advisory (detector/classifier) | Core works standalone on any model; not a product | `RESEARCH_CAPABILITY` (productizable core) |

---

## 3. Dependency matrix

The prompt asks to **distinguish code-import dependency from business-semantic dependency.**
They diverge sharply here, so both are given. Legend: `NONE` · `OPT`(optional) ·
`REC`(recommended) · `REQ`(required) · `CPL`(currently coupled but not conceptually required)
· `SI`(shared infrastructure).

### 3a. Code-import dependencies (row imports column) — verified by grep/AST

| ↓ depends on → | TAP | DG | ActionGate | ACP | StoryGraph | AgentRT | HybridLLM | CtxMin | Steering | gov_providers | cer_v0_3 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **TAP** (provider) | — | CPL¹ | NONE | NONE | NONE | NONE | NONE | NONE | NONE | **REQ/SI** | NONE |
| **Decision Governance** (kernel) | NONE | — | NONE | NONE | NONE | NONE | NONE | NONE | NONE | NONE | NONE |
| **ActionGate** A=provider / B=engine | NONE | A:REQ² | — | NONE | NONE | NONE | NONE | NONE | NONE | A:**REQ/SI** | NONE |
| **ACP** console / engine | NONE | NONE | CPL³ | — | NONE | NONE | NONE | NONE | NONE | NONE | NONE |
| **StoryGraph** | NONE | NONE | NONE⁴ | NONE | — | NONE | NONE | NONE | NONE | NONE | NONE |
| **Agent Runtime** (migration) | NONE | NONE | via cer⁵ | via cer⁵ | NONE | — | NONE | NONE | NONE | NONE | **REQ/SI** |
| **Agent Runtime** (framework) | NONE | NONE | NONE | NONE | NONE | — | NONE | NONE | NONE | NONE | NONE |
| **Hybrid LLM** (handover) | NONE | NONE | NONE | NONE | NONE | NONE | — | NONE | NONE | NONE | NONE |
| **Context Min** wired / full | NONE | NONE | CPL⁶ | NONE | NONE | NONE | NONE | — | NONE | NONE | NONE |
| **LLM Steering** | NONE | NONE | NONE | NONE | NONE | NONE | NONE | NONE | — | NONE | NONE |

Notes: ¹ importing `governance_providers.api` transitively pulls `decision_governance`+`pydantic`
via `adapters/__init__` (boundary bleed, not business need). ² `dgm-actiongate-provider` pins
`decision-governance==1.0.0`. ³ ACP consumes an ActionGate verdict as an *opaque enum*; imports
nothing (`composition.py`). ⁴ ActionGate appears in StoryGraph only as strings/`"CONTRACT ONLY —
not implemented"`. ⁵ Agent Runtime migration reaches ActionGate+ACP **only** through
`cer_v0_3.control_plane.run_control_plane`; no direct import. ⁶ only the un-wired full compressor
imports `action_gate_ref` for its invariance proof; the wired dedup path imports nothing.

**The Agentic Framework (mature Agent Runtime) is the one heavily-coupled node:** it imports
`agentic.ledger/safety/entropy/core` and `symbolu_core.*` and embeds policy authority — hence
`BUNDLE_ONLY`.

### 3b. Business-semantic dependencies (does module A's *outcome* need module B?)

| Relationship | Class | Evidence |
|---|---|---|
| Agent Runtime → ActionGate/ACP | `REQ` for *governed consequential* actions (optional for read-only) | migration runs `LOCAL_READ_ONLY` tools ungoverned; any `GOVERNED_CONSEQUENTIAL` tool requires the control plane |
| ActionGate → ACP | `REC` (orthogonal layers; an op should pass both) | `acp/ACP_ACTIONGATE_BOUNDARY.md` + `composition.py`: ActionGate authorizes, ACP clears live-safety; DENY final, ACP can only HOLD |
| Decision Governance ← TAP | `OPT/REC` (TAP assessment feeds a recommendation) | `tests/conftest.py`: coverage→advisory `ADVANCE/HOLD/REJECT` cited by `CaseRecommendationService` |
| StoryGraph → ActionGate | `OPT` (advisory evidence a gate *could* consume) | StoryGraph emits advisory records; ActionGate adapter is `CONTRACT ONLY` |
| Context Min → everything downstream | `OPT` (gateway that reduces context before other stages) | console loop runs it as first "Gateway" stage |
| TAP ↔ ActionGate | `NONE` (independent peers, enforced) | F16/F17; mutual-unawareness test |

### 3c. Shared infrastructure each module needs (business-semantic)

| Shared concern | Who owns it today | Who needs it | Status |
|---|---|---|---|
| Tenant identity / env | `decision_governance` kernel only (on CER + ActionRequest) | all, for multi-tenant | **MISSING** from neutral contracts, console, providers |
| User/service identity | `IdentityProvider` **port** (kernel) | all | port exists; only `StaticIdentityProvider` shipped |
| Authority / roles | kernel `AuthorityContext`/`AuthorityType`, 40+ `Permission` | DG, ActionGate | kernel-only; providers carry opaque `authority_context` string |
| Policy registry / versioning | per-module (`policy_refs` strings; StoryGraph policy-pack; kernel policy) | all | **fragmented**, no shared registry |
| Evidence registry / CER | **three** schemes: kernel `ContextEnvelopeRecord`, `cer_v0_3`, console ad-hoc CER | all | **fragmented**; `cer_v0_3` is the closest to a standard (open-standard draft exists) |
| Canonical IDs | `correlation_id` (string) is the only cross-layer primitive | all | present but thin; result envelope doesn't echo it |
| Audit / reconstruction | kernel `AuditRepository` port; console in-memory (not chained); control_plane hash-chain | all | **three** audit shapes; no shared durable ledger |
| Event ledger / bus | — | (async modules) | **MISSING** — no broker/pub-sub anywhere |
| Configuration / secrets | framework `configuration.py` (secret-**refs**) | all | good pattern, provider-scoped only |
| Model providers | per-module adapters (openai/anthropic/bedrock/ollama) | Hybrid, Agent RT, Steering | duplicated per module |
| Connector framework | — | ActionGate(k8s), ACP(cloud) | **MISSING** (k8s wired ad-hoc in `cyber_security`/`cloud_controller`) |
| Observability | per-layer logs; `correlation_id` only shared primitive | all | **no shared trace envelope, no OTel** |
| Persistence | in-memory everywhere | all | **no durable store shipped** |
| Human-review workflow | kernel decision/override records; StoryGraph ESCALATE | DG, TAP, StoryGraph, ACP | kernel-only; not exposed as a service |

---

## 4. Authority-boundary matrix

This is the strongest part of the codebase: authority separation is explicit and
**machine-frozen** as invariants F1–F16 in `platform/PLATFORM_FREEZE_V1.json`, each mapped to
an authoritative test. "Authority confusion" is actively prevented.

| Module | Result authority (verified in code) | May it authorize execution? | Evidence |
|---|---|---|---|
| **TAP** | **Advisory / Evidentiary** — coverage finding + obligations | **No** | `provider.py`: "no authorize/dispatch/execute surface"; F6 "assertion governance does not authorize execution" |
| **StoryGraph** | **Advisory / Evidentiary** — structural-assembly risk vector | **No** | `AUTHORITY="ADVISORY"`, effect ceiling `OBSERVE/ESCALATE`; "never emits ALLOW/DENY" |
| **ACP** | **Advisory / operational-clearance recommendation** — `CLEAR/HOLD` | **No** (can HOLD, never mint auth) | `compose(ALLOW,HOLD)=HELD_BY_ACP`; shadow-only, no token minted |
| **Decision Governance** | **Binding decision RECORD** + evidentiary authorization/execution ledger, by an authorized authority | Records/governs; **does not itself execute** | `DecisionRecord` immutable, AI structurally barred (`AuthorityType` has no AI); execution pushed to ports; F1–F3 |
| **ActionGate** (engine B) | **Binding authorization + enforcement authorization** — owns exact-action auth, mints single-use execution token | **Yes** (this is its job) | `gateway.execute` re-verifies token vs actual call; F5 |
| **ActionGate** (provider A) | Advisory authorization verdict, non-enforcing | No (adapter emits verdict) | provider "never executes" |
| **Agent Runtime** (migration) | **Proposer (Advisory)** — emits a CER proposal, consumes a separated decision | **No** ("NEVER makes its own authoritative allow/deny"; `ensure_not_self_authorized`) | runtime.py; `AGENT_RUNTIME_BYPASS_AUDIT.md` = 0 bypass paths |
| **Agent Runtime** (framework) | **Binding/enforcement (embedded)** — `SafeMCPGateway` ALLOWED/BLOCKED, `POST /authorize` | **Yes — authority confusion** | `safety_contract.py`; flagged `EXCLUDE_DUPLICATE_GOVERNANCE`; internal `ActionGate` name-collision |
| **Hybrid LLM** | **Advisory** — `SERVE_IN_HOUSE/ESCALATE/REFUSE` | **No** | `decide_escalation()` only routes/reduces/refuses |
| **Context Minimization** | **Advisory / Evidentiary** — filters/reduces context, reports withheld | **No** | emits `ADMITTED`; never in `would_execute` |
| **LLM Steering** | **Advisory** — detector/classifier/explainer, *recommends* rewrite | **No** | "not an automatic rewriter" |

**Authority-confusion finding:** the only violation is the **Agentic Framework**, which
silently *is* a policy authority (embedded allow/deny + a live `/authorize` service + an
internal class literally named `ActionGate`). The boundary-clean `agent_runtime_migration`
package was purpose-built to fix exactly this — it delegates all binding authority to the
frozen control plane and embeds none.

---

## 5. Public-interface audit

**A module is not plug-and-play when its only usable interface is an internal Python object.**
By that test, **every module fails today** — the governance stack is an in-process library set
with a single, unhardened FastAPI facade.

| Module | Python SDK | REST | gRPC | MCP | Event/MQ | Policy-as-code | CLI | Sidecar/Proxy | Network service | Versioning | Auth | Tenant iso. | Idempotency | Audit corr. |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Decision Governance | ✅ (frozen API snapshot) | ❌ | ❌ | ❌ | internal audit only | partial (grants) | ❌ | ❌ | ❌ | ✅ SemVer + freeze | via IdP port | ✅ `tenant_id` | exec dup-detect | ✅ correlation/causation |
| TAP | ✅ | via console only | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ (RemoteClient is a non-net stub) | ✅ contract ver. | ❌ | ❌ | deterministic | trace id, no echo |
| ActionGate A | ✅ | ❌ | ❌ | ❌ | ❌ | config frozensets | ❌ | ❌ | ❌ | ✅ | ❌ (`tenant=""`) | ❌ | key carried, unused | trace id + fingerprint |
| ActionGate B | ✅ | ❌ | ❌ | ✅ **real** (in-proc obj) | ❌ | ✅ **JSON-Schema pack** | ✅ | ✅ (`_isolated` mTLS) | ✅ (`_isolated` only) | ref frozen + policy `$id` | ✅ (mTLS/RBAC in `_isolated`/`_k8s`) | per-namespace | ✅ single-use nonce | ✅ hash-chained ledger |
| ACP | console REST | `/v1/actions/clear` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | console only | v0.1.0 | ❌ | ❌ | ❌ | correlation in loop |
| StoryGraph | ✅ (~50 exports) | ❌ | ❌ | ❌ | JSONL intake (consumer) | ✅ **JSON-Schema story pack** | ✅ (JSON out) | ❌ | ❌ | ✅ multi-axis (schema/matcher/pack) | ❌ | quota only | deterministic digests | self-contained evidence chain |
| Agent Runtime (mig.) | ✅ (narrow) | ❌ | ❌ | in-proc tools | in-proc trace | delegated to cer_v0_3 | ❌ | ❌ | ❌ | curated, no SemVer doc | ❌ | ❌ | in ActionGate | via control-plane trace_ref |
| Hybrid LLM | ✅ (scaffold) | ❌ | ❌ | ❌ | ❌ | partial (route policy) | demo | ❌ | ❌ | POLICY_VERSION const | ❌ | ❌ | ❌ | none |
| Context Min | ✅ | `/v1/gateway/minimize` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ (the ideal form — absent) | console only | `/v1` + fingerprints | ❌ | ❌ | pure fn | corr dropped on std endpoint |
| LLM Steering | internal only (not installable) | ❌ | ❌ | ❌ | ❌ | ❌ | eval scripts | ❌ | ❌ | none | ❌ | ❌ | pure fn | trace obj, unpersisted |

**Cross-cutting interface facts:**
- **One network surface exists** — `ugence_console_api` (FastAPI): `CORS allow_origins=["*"]`, **no
  auth**, **no `tenant_id`**, **in-memory non-chained audit**, **shadow-only** (never executes in
  any mode), and it computes an **ad-hoc CER** that bypasses the kernel authorization service. It is
  launched **manually** (port 8090) and is **not in the `Procfile`** (which serves the research app).
- The **neutral provider result envelope** lacks module-id/version, policy-version,
  advisory-vs-binding, required-next-action, and does **not echo `correlation_id`**; only
  `fingerprint` (result digest) is universal.
- **ActionGate engine B and StoryGraph are the only modules with a genuine external/enforceable
  interface** (mTLS service + real MCP + policy-as-code; and JSON CLI + policy-as-code, respectively).

---

## 6. Deployment-mode recommendations

| Module | In-proc lib | Sidecar | Independent service | Gateway/Proxy | Async/event | **Recommended mode** |
|---|---|---|---|---|---|---|
| Decision Governance | ✅ now | possible | **target** (needs REST + durable store + IdP) | ❌ | ❌ | **Embedded library now → hosted service** (it is the shared record-of-authority) |
| TAP | ✅ now | possible | after real engine wired | ❌ | could consume | **Embedded library / sidecar** behind a real grounding engine |
| ActionGate | ✅ (B) | **✅ (B, `_isolated`)** | **✅ (B mTLS)** | **✅ (k8s admission-style)** | ❌ | **Sidecar / gateway** at the execution target (its natural pre-commit chokepoint) |
| ACP | ✅ | possible | shadow service | ❌ | telemetry-driven | **Sidecar advisory** alongside ActionGate; live engine stays shadow until validated |
| StoryGraph | ✅ now | ✅ | **✅ (thin REST/gRPC over pure matcher)** | ❌ | **✅ (consume event stream)** | **Independent advisory service / stream consumer** (SIEM-adjacent) |
| Agent Runtime (mig.) | ✅ now | ❌ | target (needs service+auth) | ❌ | ❌ | **Embedded runtime library** that calls a governance control plane |
| Hybrid LLM | ✅ (scaffold) | the ideal form | after real extractor | proxy is the ideal | ❌ | **Model-proxy/sidecar** — but not until the engine is real |
| Context Minimization | ✅ | **the ideal form (absent)** | console only | **proxy is the ideal (absent)** | ❌ | **Model-proxy/sidecar** (once token core is wired + hardened) |
| LLM Steering | ✅ (core) | possible | after packaging | proxy possible | ❌ | **Embedded pre/post-generation library or sidecar** over the customer's own model |

Common answers: **shared state** required by none of the clean modules; **Agent Runtime**
required only by consequential-action orchestration; **Ugence audit ledger** required by
none (each has its own in-proc audit); **ActionGate decisions** required only by ACP/Agent-RT
by *design*, and always as an injected port. **Customer DB / IAM / SIEM**: ports exist in the
kernel, but **no shipped adapters** anywhere — this is uniform adapter-work.

---

## 7. Router / orchestrator decision

**Recommendation: Option B (common SDK/interface) as the baseline, with an *optional* Option C
(thin module gateway) for hosted/multi-tenant delivery. Do NOT mandate Option A's isolation
or Option D's orchestrator.**

| Option | Fit | Assessment |
|---|---|---|
| **A — no router, call each module directly** | Already true for the clean modules | Works for single-module sales; fails to give shared identity/correlation/evidence when modules are combined. |
| **B — common SDK / interface** ✅ **baseline** | **Already exists in nascent form** (`governance_providers`: registry + deterministic resolution + conformance + fingerprint + error taxonomy) | Standardizes request/result envelopes, identity, policy/evidence refs, decisions, errors, audit correlation while keeping each module directly callable. **This is the smallest sufficient shared abstraction.** Gap: the envelope must gain `tenant_id/environment_id/requested_at/result-correlation-echo`. |
| **C — thin module gateway** ✅ **optional (hosted)** | Partially exists as the console facade | Adds discovery, auth, tenant routing, version routing, rate-limit, observability — **without business orchestration**. Right shape for a hosted/SaaS offering; must not embed the governed-loop. |
| **D — governance-pipeline orchestrator** ⚠️ **product-only** | Exists **three times** (console loop, `control_plane/` harness, `cer_v0_3.run_control_plane`), all shadow/mock | Justified **only** as an opinionated "Full AI Control Plane" product with a required lifecycle. Customers buying one module must be able to **bypass it and call the module directly.** |

Per-axis: **coupling** — B lowest, D highest; **latency/failure propagation** — D adds a
single-point-of-failure the modules don't otherwise have; **independent deployability** — B/C
preserve it, D erodes it; **integration burden** — B lowest; **version/policy consistency** —
B (shared contracts) already delivers this via the freeze; **commercial packaging** — B lets
you sell one module and expand, D forces platform adoption.

**Verdict: a router is not required. A common SDK is. An orchestrator is a product option,
not an architectural necessity.**

---

## 8. Router-vs-orchestrator terminology — what actually exists vs. what's missing

| Abstraction | Exists today? | Evidence |
|---|---|---|
| **Module Registry** | ✅ **Strong** | `governance_providers/registry` + deterministic `resolution.py` (`EXPLICIT_ID→DOMAIN_DEFAULT→GLOBAL_DEFAULT→SINGLE_COMPATIBLE→UNRESOLVED`, never guesses, auditable `ResolutionRecord`) |
| **Data Plane** | ✅ Partial | the providers themselves — stateless capability evaluators |
| **API Gateway** | ⚠️ Facade only | console `app.py`, but CORS-`*`, no auth, no service routing |
| **Workflow Orchestrator** | ⚠️ Duplicated ×3, all mock/shadow | console loop, `control_plane/`, `cer_v0_3.run_control_plane` |
| **Policy Router** | ⚠️ Weak | provider resolution only; no tenant/env request routing |
| **Control Plane (service)** | ❌ Aspirational | the name labels 3 single-process code artifacts; no hosted, authenticated, tenant-aware, persistent plane |
| **Governance Fabric** | ❌ Missing | no shared identity/tenant/audit threading, no shared trace envelope |
| **Event Bus** | ❌ Missing | no broker/pub-sub anywhere |

**Smallest necessary abstraction = the Module Registry + a common contract SDK (Governance
Fabric contracts), not a Control Plane service and not an Event Bus.**

---

## 9. Shared-core recommendation

**Recommendation: `(e) Hybrid — embedded common SDK + optional hosted control plane.`**

- **What already exists** and should be the embedded core: `governance_providers` (registry,
  deterministic resolution, conformance kits, fingerprint, error taxonomy, lifecycle,
  secret-ref config) + the kernel's identity/audit **ports**. This is a real "embedded common
  SDK" (option b) — proven independently distributable.
- **What must be added to that SDK** (small, high-leverage): a **canonical envelope** carrying
  `tenant_id/environment_id/correlation_id/actor/authority_context/policy_refs/evidence_refs/
  cer_id/requested_at` and a **result envelope** carrying `module@version, policy_version,
  result_category, advisory|binding, requirements_satisfied/failed, required_next_action,
  evidence_refs, expiry, result_digest, correlation_id`. Today these fields are **fragmented
  and tenant-less** across three contract sets.
- **What is optional and hosted** (option d, but thin): a control plane / thin gateway that
  supplies tenant context, auth, durable tamper-evident audit (the kernel `AuditRepository`
  with hash-chaining, currently reserved), and module discovery — for customers who want SaaS
  rather than embedded.

**Do not** put module-specific business logic in the core. Candidate core responsibilities
(tenant/env context, service identity, authority resolution, policy versioning, canonical IDs,
evidence refs, correlation IDs, audit/reconstruction, connector registration, config/secrets,
observability, module discovery, licensing/entitlements) are all **cross-cutting** — and today
**most are missing or fragmented** (no shared tenant, no shared audit, no runtime entitlements,
three CER schemes, no shared trace envelope).

Trade-offs: an embedded-only SDK keeps modules independently deployable and low-latency but
leaves each customer to supply identity/audit/persistence adapters; a hosted control plane
centralizes those but reintroduces a single point of failure and pushes toward platform
adoption. The hybrid lets a customer **start embedded with one module** and **adopt the hosted
plane only when combining modules or requiring managed multi-tenancy** — matching the
land-and-expand goal.

---

## 10. Target architecture diagrams

### A. Standalone single-module deployment (minimum shared services)

```
        ┌─────────────────────────────────────────────┐
        │            Customer application               │
        │  (its own orchestration, identity, storage)   │
        └───────────────┬───────────────────────────────┘
                        │  canonical request envelope
                        │  (tenant, actor, correlation, policy/evidence refs)
                        ▼
        ┌─────────────────────────────────────────────┐
        │   ONE Ugence module (e.g. ActionGate engine)  │
        │   + Embedded Governance SDK (governance_       │
        │     providers: registry · resolution ·         │
        │     conformance · fingerprint · errors)        │
        └───────────────┬───────────────────────────────┘
                        │  canonical result envelope + evidence
                        ▼
        ┌─────────────────────────────────────────────┐
        │  Customer systems: IAM (adapter) · policy ·   │
        │  DB (adapter) · SIEM/audit sink (adapter)     │
        └─────────────────────────────────────────────┘
   Minimum shared services required: the embedded SDK only.
   Everything else = customer-owned via adapters (ports exist; adapters TBD).
```

### B. Multi-module, customer-orchestrated (no central Ugence orchestrator)

```
   ┌────────────────────────────────────────────────────────────┐
   │        Customer workflow / orchestrator (owns order)        │
   └───┬───────────┬──────────────┬──────────────┬───────────────┘
       │           │              │              │      each call carries the SAME
       ▼           ▼              ▼              ▼      canonical envelope + correlation_id
   ┌───────┐  ┌─────────┐   ┌───────────┐   ┌──────┐
   │  TAP  │  │Decision │   │ ActionGate│   │ ACP  │
   │(assert│  │Governance│  │(authorize)│   │(clear│
   │ -ory) │  │(record) │   │  BINDING  │   │ adv.)│
   └───┬───┘  └────┬────┘   └─────┬─────┘   └──┬───┘
       └───────────┴──────────────┴────────────┘
                        │  common result envelopes, shared correlation_id
                        ▼
             ┌────────────────────────────┐
             │  Shared evidence + audit     │  (kernel AuditRepository / customer SIEM)
             │  correlation-joined trail    │
             └────────────────────────────┘
   Modules are directly callable and independently deployable.
   No router in the path; consistency comes from the common contracts, not a central component.
```

### C. Full Ugence Control Plane (opinionated bundle)

```
        ┌───────────────────────── CONTROL PLANE (hosted, optional) ─────────────────────────┐
        │  Admin/console · tenant & env context · auth · module discovery · entitlements ·     │
        │  durable tamper-evident audit (hash-chained) · observability/trace envelope          │
        └───────────────┬───────────────────────────────────────────────┬─────────────────────┘
                        │ GOVERNANCE FABRIC (shared contracts: identity · policy · evidence · CER)
        ┌───────────────┴───────────────┐                 ┌─────────────┴──────────────┐
        │   Optional Module Gateway      │                 │   Governed-loop Orchestrator│  (Option D,
        │   (discovery · authN · tenant  │                 │   Ctx-Min→TAP→DecisionGov→  │   product-only,
        │    routing · versioning · rate) │                 │   StoryGraph→ActionGate→ACP │   bypassable)
        └───────────────┬───────────────┘                 └─────────────┬──────────────┘
                        ▼                                                ▼
   ┌──────────┬──────────┬────────────┬──────────┬───────────┬────────────────┐
   │ Ctx-Min  │   TAP    │  Decision  │ Story-   │ ActionGate│      ACP        │   ← Data Plane (modules)
   │ (gateway)│(evidence)│ Governance │ Graph    │ (enforce) │  (clearance)    │
   └────┬─────┴────┬─────┴─────┬──────┴────┬─────┴─────┬─────┴────────┬────────┘
        │          │           │           │           │              │
        ▼          ▼           ▼           ▼           ▼              ▼
   ┌─────────────────────────── Customer connectors ───────────────────────────┐
   │  runtime adapters (Agent Runtime / 3rd-party) · execution targets (k8s)     │
   └───────────────────────────────┬────────────────────────────────────────────┘
                                    ▼
                         ┌────────────────────────┐
                         │  Runtime execution +     │
                         │  reconciliation           │
                         └────────────────────────┘
   Shared audit & evidence span every layer via correlation_id / CER identity.
```

> Diagrams reflect the **target** once boundary hardening lands. **Today**, only the middle of
> diagram C exists — as a single-process, unauthenticated, in-memory, shadow-only console loop
> over reference-grade modules; the control-plane band (tenant, auth, durable audit, gateway,
> discovery, entitlements) is **absent in code**.

---

## 11. Gap-remediation backlog

Grouped by whether it blocks *independence* or *productization*. Complexity ∈ {SMALL, MEDIUM, LARGE}.

### Platform-wide (blocks every module)
| Gap | Class | Size |
|---|---|---|
| No `tenant_id/environment_id` in neutral contracts or console; tenant lives only on kernel records | Architectural-refactor | **LARGE** |
| One network surface (console) is unauthenticated, CORS-`*`, no auth/tenant | Boundary-hardening | **MEDIUM** |
| Audit is in-memory / not hash-chained at the integration layer (kernel hash-chain reserved, unbuilt) | Productization-work | **LARGE** |
| Three CER/identity schemes (kernel `ContextEnvelopeRecord`, `cer_v0_3`, console ad-hoc) — no single canonical envelope threaded | Architectural-refactor | **LARGE** |
| Result envelope omits module-id/version, policy-version, advisory/binding, next-action, correlation echo | Boundary-hardening | **MEDIUM** |
| No durable persistence adapter, no shipped IAM/SIEM adapters (only ports) | Adapter-work | **MEDIUM** (per adapter) |
| No shared observability/trace envelope (only `correlation_id` string; no OTel) | Adapter-work | **MEDIUM** |
| No runtime entitlement/licensing boundary (only per-package LICENSE) | Productization-work | **MEDIUM** |
| No per-module deployment manifests (no Dockerfile/helm anywhere in governance dirs) | Packaging-work | **SMALL–MEDIUM** |
| Exact-pin dist deps (`==1.0.0`) make provider upgrades lockstep | Packaging-work | **SMALL** |

### Per-module (highest-leverage only)
| Module | Gap | Class | Size |
|---|---|---|---|
| TAP | Ships a deterministic **mock**; real engine `assertion_governance/engine.py` "NOT integrated" | Research-validation + Adapter-work | **LARGE** |
| TAP | `governance_providers.api` transitively drags `decision_governance`+`pydantic` | Boundary-hardening | **MEDIUM** |
| ActionGate | **Two disjoint families** never composed; console wired to the **mock**, not the real engine (docstring falsely claims "real engine") | Architectural-refactor | **LARGE** |
| ActionGate | Real engine unpackaged; mock exec adapters + HMAC test keys outside `_isolated`; no helm/Docker | Packaging + Security | **LARGE** |
| ACP | Live-clearance engine is **shadow-only / OFF by default**; console gate is a separate 63-LOC reimpl of it | Productization + Architecture | **LARGE** |
| StoryGraph | No packaging (`pyproject`), no REST/gRPC over the pure matcher; source-system adapters `CONTRACT ONLY` | Packaging + Productization | **SMALL→MEDIUM** |
| Agent Runtime | migration limited to 3 CER profiles + shadow fixtures; no service/auth; framework embeds authority + `ActionGate` name collision | Coverage + Boundary | **LARGE** |
| Context Min | Only lossless dedup wired; token-reducing core in `experiments/`, reached via `sys.path` hack, ActionGate-coupled; no per-actor filtering | Architectural-refactor | **LARGE** |
| Hybrid LLM | In-house tier is a stand-in (neural model **falsified**, 0% needle); frontier is a mock; efficiency claims synthetic-only | Research-validation | **LARGE** |
| LLM Steering | Real core buried in `scripts/`, unpackaged, unwired, console read-only; config needs source edits; single-model evidence | Packaging + Research-validation | **MEDIUM→LARGE** |

---

## 12. Evidence references

- **Frozen platform / invariants:** `platform/PLATFORM_FREEZE_V1.json` (v1.0.0, 1006 tests, F1–F20,
  acyclic dep rules), `platform_freeze/verify.py`, `platform_freeze/classify_change.py`,
  `platform/api-snapshots/{decision_governance,governance_providers,actiongate_provider,tap_provider}.api.json`,
  `CHANGELOG_PLATFORM_V1.md`.
- **Independent distribution:** `packaging/verify_independent_distribution.py`,
  `packaging/verify_tap_provider_distribution.py`, `packaging/{decision-governance,dgm-provider-framework,
  dgm-tap-provider,dgm-actiongate-provider}/pyproject.toml`.
- **Shared framework / contracts:** `governance_providers/{registry,resolution,conformance,fingerprint,
  lifecycle,configuration,errors,metadata}.py`, `governance_providers/contracts/{base,action,assertion,execution}.py`,
  `governance_providers/adapters/action_to_control_plane.py`.
- **Decision Governance:** `decision_governance/{api,services,identity/provider,audit,actions/cer,decisions/authority,
  policy/access,conformance/dependency_rules}.py`; tests `decision_governance/tests/*` (29 pass).
- **TAP:** `tap_provider/{provider,core,client,configuration,mapping,conformance}.py`; unintegrated engine
  `assertion_governance/engine.py`; tests (38 pass).
- **ActionGate:** provider `actiongate_provider/{provider,core}.py` (30 pass); engine
  `cyber_security/action_gate_reference/`, `action_gateway/`, `action_gateway_mcp/`, `action_gateway_k8s/`,
  `action_gateway_isolated/`, `action_gate_policy_schemas/` (~322 pass); `acp/ACP_ACTIONGATE_BOUNDARY.md`.
- **ACP:** console `ugence_console_api/capabilities/operational_safety.py`; engine
  `symbolu_robotics/autonomous_control_plane/` (112 pass), `.../cloud/`; `acp/` (~60 markdown, 0 `.py`);
  `acp/ACP_V1_FREEZE.md`.
- **StoryGraph:** `cyber_security/composite_threat_detector/composite_threat_detector/{storygraph,storyverdict,
  contradictions,legitimate,matcher,analyzer,cli}.py`, `policypack/`, `evaluation/{freeze,evidence_chain}.py`
  (289 pass).
- **Agent Runtime:** `agent_runtime_migration/` (74 pass, `control_plane/client.py`, `proposal/cer_builder.py`,
  `tests/test_forbidden_imports.py`), `agentic/agentic_framework/` (2,260 collected, `governance_api.py`,
  `mcp_gateway.py`), `agent_runtime_v2/` (11 `.md`, 0 `.py`); `AGENT_RUNTIME_BYPASS_AUDIT.md`.
- **Hybrid LLM:** `agentic/hybrid_handover/{pipeline,faithfulness,redaction,inhouse,frontier}.py`,
  `model_selection_pilot/{policy,provider,PILOT_STATUS.md}`, `HYBRID_LLM_FALSIFICATION_ASSESSMENT.md`,
  `HYBRID_LLM_VC_CLAIM_LEDGER.json` (57 pass; mock/blocked).
- **Context Minimization:** `experiments/actiongate_context_ablation/.../compressor.py`,
  `ugence_console_api/capabilities/context_gateway.py`; separate engine `minimal_evidence_policy/`
  (64 pass) — a *different* capability the prompt mislabels.
- **LLM Steering:** `scripts/cg_wrapper_ablation/csr_match_filter/{match,answer_audit,registry}.py`
  (50 pass); research-steering `agentic/sovereign/reasoning_kernel.py`, `symbolu_training/…`.
- **Integration layer / control planes:** `ugence_console_api/{app,orchestrator,models,audit}.py`,
  `control_plane/{orchestrator,contracts,envelope,decisions,modes,shadow}.py`,
  `cer_v0_3/{cleanroom/cer,control_plane}.py`, `cer_public_draft/`, `cer_open_standard/`.
- **Deployment:** `Procfile` (serves `symbolu.service.api_server`, **not** the console), `nixpacks.toml`,
  `.mcp.json` (alpaca trading), `deploy/` (Cloud Scaling Controller rigs), `ugence_console_api/__main__.py`
  (manual, port 8090); `sdk/cohera/` (unrelated GPU/tensor SDK).
- **Company framing:** `UGENCE_PRODUCTIZATION_ROADMAP.md`, `UGENCE_AI_CONTROL_PLANE_FIRST_LOOK.md`,
  `MODULE_USE_CASES.md`, `ugence_console_api/capabilities/registry.py`.

---

## 13. Claims that cannot currently be supported by code

These appear in docs/VC-briefs/console but are **not** substantiated by the current implementation:

1. **"Six/nine consolidated modules deployable as one product."** No deployed integration layer
   exists; the console is manual, unauthenticated, in-memory, shadow-only, and not in the `Procfile`.
2. **TAP "controls what AI may assert."** Code = advisory classifier over a **deterministic mock**;
   the real grounding engine is explicitly *not integrated*.
3. **Console "wraps the real ActionGate engine."** Code wires the **mock** provider; the real engine
   (`cyber_security/action_gate*`) is a separate, unwired codebase.
4. **ACP "owns live operational clearance."** The engine that would do this is **shadow-only / OFF by
   default / never actuates**; the shipped console version is a 63-line threshold gate.
5. **Hybrid LLM efficiency (32–66% / ~427× reduction) and "governed reasoning substrate."** The neural
   model is **falsified** in the repo's own doc (0% needle); numbers are from synthetic fixtures; the
   in-house tier is a rules stand-in and the frontier tier is a mock.
6. **Context Minimization "restricts data to the minimum necessary subset per actor/purpose."** No
   per-actor/purpose need-to-know filtering exists; the wired path is exact-duplicate dedup only.
7. **LLM Steering as a deployable "controller."** The real core is an unpackaged, unwired research
   library under `scripts/`; the console surfaces it as read-only status.
8. **Multi-tenancy, durable tamper-evident audit, production readiness, regulatory compliance, ROI.**
   Explicitly disclaimed by the freeze manifest ("single-process, in-memory, synthetic validation")
   and the roadmap (all listed as *to-be-built*).
9. **Frozen-benchmark headline numbers** (Context-Min 3-real-model, Hybrid-LLM) are **GPU/credential-gated
   and not reproducible** in the repo environment.

---

## 14. Final verdict

### Overall: `MODULAR SALES VIABLE AFTER BOUNDARY HARDENING`

The architecture is boundary-clean and demonstrably modular (independent wheels with enforced
isolation, frozen public APIs, machine-checked authority invariants, real self-contained
engines) — so it is **not** "an integrated platform, not yet modular." But **no module is a
plug-and-play product today** (in-process-only interfaces, no tenant/auth, no durable audit,
mocks wired where real engines should be) — so it is **not** "modular sales ready" in any
router variant. The precise, evidence-backed verdict is: **the modularity is achievable and
the coupling is not the obstacle; a bounded set of hardening tasks is.**

### Per-module verdicts

| Module | Sell alone? | Deploy alone? | Verdict |
|---|---|---|---|
| **StoryGraph** | **Yes** (advisory) | after packaging + thin API | **Best standalone entry** — zero coupling, real engine, policy-as-code, 289 tests. `INDEPENDENT_AFTER_BOUNDARY_HARDENING` (small gaps). |
| **ActionGate** | **Yes** (real engine B) | as sidecar/gateway after joining A+B + hardening | Strong wedge (owns exact-action auth). `INDEPENDENT_AFTER_BOUNDARY_HARDENING`; blocked by two-family reconciliation + credential/deploy hardening. |
| **Decision Governance** | **As a bundle anchor** | after REST + durable store + IdP | `INDEPENDENT_AFTER_BOUNDARY_HARDENING`; better positioned as the shared record-of-authority than a lone product. |
| **Agent Runtime** | migration: **as governed bundle**; framework: **no** | after service+auth | migration `INDEPENDENT_AFTER_BOUNDARY_HARDENING`; framework `BUNDLE_ONLY`; v2 `RESEARCH`. |
| **TAP** | **Not yet** (mock engine) | after real engine wired | `INDEPENDENT_WITH_SHARED_CORE`; value gated on integrating the real grounding engine. |
| **ACP** | **Not yet** (shadow) | pairs with ActionGate | Engine `RESEARCH_CAPABILITY`; console gate `INDEPENDENT_AFTER_BOUNDARY_HARDENING`. Sell **with** ActionGate. |
| **Context Minimization** | **Not yet** (dedup only wired) | as proxy after wiring token core | `INDEPENDENT_AFTER_BOUNDARY_HARDENING`; token core is `RESEARCH`. |
| **Hybrid LLM** | **No** | no | `RESEARCH_CAPABILITY` — scaffold + blocked pilot + falsified model. |
| **LLM Steering** | **No** (as product) | no | `RESEARCH_CAPABILITY` with a genuinely productizable, model-agnostic core. |

### The eight required answers

1. **Can each module be sold alone?** Only **StoryGraph** and **ActionGate (real engine)** are
   credible near-term standalone sales; **Decision Governance / Agent Runtime** sell as bundle
   anchors; **TAP / ACP / Context-Min** need their real engine wired first; **Hybrid LLM / LLM
   Steering** are research, not sellable products yet.
2. **Can each module be deployed alone?** **Not today** — all fail the deployment criteria
   (no service artifact, no auth, no tenant, in-memory audit). After boundary hardening, yes for
   StoryGraph, ActionGate, Decision Governance, Agent Runtime, Context-Min.
3. **What minimum Ugence core is unavoidable?** A **small embedded governance-contract SDK** — the
   canonical request/result envelope + identity/tenant/correlation/evidence/policy refs + registry
   + deterministic resolution. This **already exists in nascent form** as `governance_providers`.
   StoryGraph, ActionGate-engine, LLM-Steering-core need **no** shared core at all.
4. **Is a router required?** **No.** Modules are independent and providers never invoke one another.
5. **Is an orchestrator required?** **No** — only as an optional, opinionated "Full AI Control Plane"
   product. The governed-loop must be bypassable.
6. **Should customers be able to bypass the orchestrator and call modules directly?** **Yes** —
   this is already the natural calling pattern and must remain first-class.
7. **Which modules should not be sold independently?** **Agentic Framework** (authority-confused →
   bundle), **Hybrid LLM** and **LLM Steering** (research), **ACP live engine** (shadow research);
   **Decision Governance** is best sold as a bundle anchor, not a lone SKU.
8. **Recommended land-and-expand model?**
   - **Land** on the **infrastructure-agent action-control wedge**: **ActionGate** (real engine, k8s
     sidecar/gateway) — concrete action, measurable blast radius, natural shadow mode. Optionally
     land on **StoryGraph** as a low-integration advisory sequence-risk product.
   - **Expand** to the paired governance stack via the common SDK: **+ACP** (live operational
     clearance) → **+Decision Governance** (accountability record) → **+TAP** (assertion governance)
     → **+Context Minimization** (cheaper governed context) → **+Governed Agent Runtime**, and finally
     the **Full AI Control Plane** bundle (with the optional hosted control plane for multi-tenant
     audit/identity).
   - **Never force a bundle** where one module delivers standalone value (StoryGraph, ActionGate).

---

## 15. Commercial packaging recommendation

- **Platform Core (embedded SDK + optional hosted plane):** identity/tenant context, policy/evidence
  refs, canonical envelope + result envelope, registry/resolution, audit/reconstruction, connector
  registration, observability. Ship the SDK embedded; offer the hosted plane for SaaS/multi-tenant.
- **Standalone modules (after hardening):** **StoryGraph** (advisory sequence-risk), **ActionGate**
  (agent action authorization/enforcement).
- **Bundles that the evidence supports:**
  - *Agent Action Governance*: **ActionGate + ACP + audit** (authorize + live-safety + record) — the
    two are orthogonal-by-design and code-composed.
  - *Decision Governance*: **TAP + Decision Governance + audit** (assertion → accountable decision).
  - *Governed Agent Runtime*: **Agent Runtime (migration) + ActionGate + ACP** via the CER control plane.
  - *Sequence-Risk Governance*: **StoryGraph + ActionGate + audit** (advisory evidence feeding the gate).
  - *Full AI Control Plane*: all applicable modules behind the optional hosted plane + governed loop.
- **Do not** bundle Hybrid LLM / LLM Steering into sellable governance packages until their engines
  are validated; position them as roadmap/accelerators.

---

## Appendix — decision principle applied throughout

> The customer should be able to start with **one governance outcome** without deploying unrelated
> capabilities, while independently-purchased modules still share **stable identity, policy, evidence,
> audit, and interoperability contracts** when combined.

This is exactly the hybrid recommendation: **modules stay directly callable and independently
deployable (no mandatory router/orchestrator); a small shared contract SDK — already begun as
`governance_providers` — provides the identity/policy/evidence/audit/interop consistency when they
are combined; and a hosted control plane is an optional convenience, not an architectural tax.**
