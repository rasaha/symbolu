# Governed Agent Studio v1 — screen-to-package audit

**Read-only audit. No code, no contract change, no dependency is added by this
document.** It maps each of the six v1 screens onto the package types and entry points
that already exist, states what the studio backend would have to gain, and sketches
the additive `governance_studio.api.v2` contract. Sequenced as GAS-4 in
`Project_documentation/repository/ugence_platform/UGENCE_PRODUCTIZATION_ROADMAP.md`
§11.

`[V]` verified here; `[I]` inferred; `[R]` needs an owner ruling; `[G]` gap.

---

## The finding that shapes everything else

> **The studio backend is currently forbidden — by a passing CI test — from importing
> four of the six screens' packages.** `[V]`

`backend/tests/test_architecture.py` asserts the API is thin orchestration over
**one** public surface, `ugence_agent_workforce_composer.api`, and lists as prohibited
imports: `import ugence_policy_workflow_compiler`, `agent_runtime`, `action_clearance`,
`actiongate`, plus every private AWC submodule and any database driver `[V]`
(`_PROHIBITED_IMPORTS`, `_PERMITTED_AWC`).

Constitution, Policy, Authority and Observe all need packages on that list. So GAS-4 is
not "add screens"; it is **"widen a ratified architecture boundary, deliberately, and
re-state what thin still means."** That is owner decision **SD-1** below. The good
outcome is a boundary that grows by an explicit allowlist of *public* entry points —
one line per package, each a documented `api`-style surface — and keeps every private
submodule and every database driver prohibited. The bad outcome is deleting the test.

Everything else in this audit is comparatively mechanical.

---

## Screen → package map

Entry points below are verified symbols. "Studio owns" names the only logic the studio
may add; anything beyond it is re-implementation and is prohibited.

### 1 · Constitution

| | |
|---|---|
| **Purpose** | Author, preflight and issue an agent constitution; show what a constitution binds. |
| **Types** | `AgentConstitutionPolicy`, `AgentConstitutionPolicyMetadata` `[V]` (`packages/integration/agent-constitution-policy/.../policy.py:321,203`) |
| **Entry points** | `ActivationRoot.preflight_issuance`, `.issue_constitution`, `.activate_constitution`, `.constitution_resolver` `[V]` (`packages/integration/agent-constitution-activation/.../composition.py:98,122,155,202`); constructed via `build_activation_root` |
| **Studio owns** | Form state, diff rendering, and displaying the `PreflightReport`. |
| **Never** | Issue or activate from a browser action. The studio calls **`preflight_issuance` only** — it is documented as mutation-free `[V]` (same file: "Dry-run every pre-signing check"). Issuance is an authority act and stays outside the studio (SD-2). |
| **Gap** | The activation proof runs on ephemeral in-process keys; no signing key or trust root exists in the repository `[V]` (capability pipeline §B.4 row 9). The screen must show that state, not hide it behind a disabled button. |

### 2 · Policy

| | |
|---|---|
| **Purpose** | Author a `PolicyPack` on the React Flow canvas, validate it, compile it, show the four outputs and the digest. |
| **Types** | `PolicyPack` `[V]` (`packages/tooling/policy-workflow-compiler/.../models/policy_pack.py:76`); `CompilationResult` with `workflow_ir`, `assurance_manifest`, `audit_schema`, `compiled_package`, `logical_digest` `[V]` (`.../compiler/compiler.py:50`) |
| **Entry points** | `GovernedWorkflowCompiler.validate` (validate-only), `.synthesize` (preview, no approval), `compile_policy_pack(pack, approval, require_approval=True)` `[V]` (`.../compiler/compiler.py:222`) |
| **Studio owns** | Canvas node/edge state and its bidirectional mapping to `PolicyPack`. |
| **Never** | Set `require_approval=False`. The default is `True` `[V]`; the studio uses `validate` and `synthesize` for the live canvas and reaches `compile` only with a real `HumanApprovalRecord`. |
| **Note** | `synthesize` already raises `CompilationError` on an authority-boundary violation in the synthesized IR `[V]` — the canvas gets boundary feedback for free and must not re-derive it. |

### 3 · Authority

| | |
|---|---|
| **Purpose** | Show which policies are issued, resolvable, revoked; show the decision and risk artefacts a run rested on. |
| **Types** | `IssuedPolicyRecord`, `PolicyRevocationRecord`, `PolicyResolution` `[V]` (`packages/policy-authority/.../core/records.py:60,134,202`); `PolicyCoordinate` `[V]` (`.../core/adapters.py:64`); `AuthorityContext`, `DecisionRecord`, `ContextEnvelopeRecord` `[V]` (`packages/capabilities/decision-authority/.../authority.py:23`, `.../decision.py:25`, `.../actions/cer.py:62`); `RiskAuthorizationEnvelope` `[V]` (`packages/risk_authority/.../domain/envelope.py:92`) |
| **Entry points** | `issue_policy` `[V]` (`.../core/issuance.py:80`); the `PolicyRegistry` Protocol for resolve/revoke reads `[V]` (`.../core/registry.py:61`) |
| **Studio owns** | Read-only presentation and filtering. |
| **Never** | Call `issue_policy` or any revoke path. This screen is a **reader**. |
| **Gap** | The only registry implementation reachable today is `InMemoryPolicyRegistry` `[V]` (`.../core/registry.py:107`), so the screen shows one process's view and must say so. |

### 4 · Simulate

| | |
|---|---|
| **Purpose** | Run a compiled workflow against fixtures and show every governance decision, with nothing consequential reachable. |
| **Types** | `TransitionProposal` `[V]` (`packages/runtime/agent-runtime/.../models/proposal.py`); `GovernanceEvaluation`, `GovernanceDisposition` `[V]` (`.../governance/interfaces.py`); `RuntimeDirective` `[V]` (`.../governance/decisions.py`); `ExecutionMode.DRY_RUN` / `SIMULATION` / `SHADOW` `[V]` (`packages/capabilities/cloud-scaling-operations/.../contracts.py`) |
| **Entry points** | The Agent Runtime public API (`ugence_agent_runtime.api`) driving `advance_workflow`, against `AllowAllGovernanceHook` **or** the GAS-3 production hook, with a fixture provider registry. |
| **Studio owns** | Trace rendering: proposal → disposition → directive → outcome, per task. |
| **Never** | Reach `ExecutionMode.LIVE`. Never construct or mutate a `TransitionProposal`; read the ones the runtime built. Never render a disposition the runtime did not return. |
| **Note** | `AllowAllGovernanceHook` is explicitly unsafe and never a default `[V]` (`.../governance/hooks.py`). If Simulate uses it, the screen must label the run as CLEAR-by-construction, because otherwise a simulation that clears everything looks like a governance result. This is the single most misleading thing this screen could do. |

### 5 · Publish

| | |
|---|---|
| **Purpose** | Hand a compiled release package to the shadow governed loop and show what came back. |
| **Types** | `CompiledReleasePackage` `[V]` (`.../compiler/release.py:64`), `AssuranceManifest` `[V]` (`.../models/assurance.py:101`), `AuditSchema` `[V]` (`.../models/audit.py:64`) |
| **Entry points** | `ugence_console_api` over HTTP: `POST /v1/governed-loop/shadow` and `POST /v1/governed-loop/scenario/{scenario_id}` `[V]` (`ugence_console_api/app.py:111,118`) |
| **Studio owns** | The HTTP call and the result view. |
| **Never** | Import `ugence_console_api`. It is a separate service reached over HTTP, which also keeps the architecture test's no-database rule intact. Never call a non-shadow endpoint; `/v1/actions/authorize` and `/v1/actions/clear` exist `[V]` (`app.py:99,106`) and are **not** the studio's to call (SD-2). |

### 6 · Observe

| | |
|---|---|
| **Purpose** | Reconstruct a decision chain by correlation id. |
| **Entry points** | `GET /v1/audit` (ids) and `GET /v1/audit/{correlation_id}` → `AuditChain` `[V]` (`ugence_console_api/app.py:132,136`) |
| **Studio owns** | Chain rendering and correlation-id search. |
| **Never** | Re-derive, re-order or re-hash the chain client-side. Render what the endpoint returns. |
| **Gap** | `AuditStore` is the console's own store `[V]` (`ugence_console_api/audit.py:21`); this screen shows one console instance's audit, not a durable enterprise ledger, and must say so. |

---

## Studio backend additions required

1. **A widened, explicit architecture allowlist.** Extend `_PERMITTED_AWC` into a
   per-package allowlist of public entry points, keeping every private submodule and
   every database driver prohibited. Blocked on **SD-1**.
2. **Six thin services**, one per screen, alongside `services/orchestration.py`, each
   sequencing public calls and holding no domain logic — the pattern that module
   already documents and that `test_architecture.py` already enforces `[V]`.
3. **Frozen fixtures per screen**, extending `demo_data/` and `expected_outputs/`, with
   the existing determinism and fixture-bundle verification applied to them `[V]`
   (`backend/scripts/verify_fixture_bundle.py`, `tests/test_determinism.py`).
4. **A v2 router mounted at `/api/v2`**, leaving every `/api/v1` route untouched.
5. **No new backend dependency.** React Flow is a frontend dependency only; the
   frontend currently has none of it `[V]` (`frontend/package.json`).
6. **A read-only HTTP client for `ugence_console_api`**, restricted at the client level
   to the four read/shadow routes named above, so Publish and Observe cannot reach an
   authorize or clear endpoint even by mistake.

## Frontend additions

`reactflow` as a runtime dependency; a `features/canvas/` module owning node and edge
types; a bidirectional `PolicyPack` ↔ graph mapper with a round-trip property test.
Nodes are **governance types** — capability, role, obligation, policy clause. Generic
LLM, prompt and API nodes are out of scope, and the node registry must be closed
(unknown type refuses) so an imported graph cannot introduce one.

---

## Additive `governance_studio.api.v2` — contract sketch `[I]`

`v1` stays byte-frozen at `contracts/openapi.json` and keeps passing
`verify_openapi.py` and `test_freeze.py` `[V]`. `v2` is a **new document**, reusing the
existing `ApiResponse` envelope, its `maturity` / `SYNTHETIC_NOTICE` block and the
strict `extra="forbid"` request models unchanged `[V]`
(`contracts/envelope.py`). Every route is POST-for-evaluation, GET-for-read; none
grants, authorizes or executes.

| Screen | Route | Delegates to |
|---|---|---|
| Constitution | `POST /api/v2/constitution/validate` | constitution policy construction + structural checks |
| Constitution | `POST /api/v2/constitution/preflight` | `ActivationRoot.preflight_issuance` (mutation-free) |
| Policy | `POST /api/v2/policy/validate` | `GovernedWorkflowCompiler.validate` |
| Policy | `POST /api/v2/policy/synthesize` | `GovernedWorkflowCompiler.synthesize` |
| Policy | `POST /api/v2/policy/compile` | `compile_policy_pack` (`require_approval=True`) |
| Policy | `POST /api/v2/policy/from-langflow` | GAS-5 importer → `PolicyPack`, never executed |
| Authority | `GET /api/v2/authority/policies` | `PolicyRegistry` reads |
| Authority | `GET /api/v2/authority/policies/{coordinate}` | policy resolution |
| Authority | `GET /api/v2/authority/decisions/{decision_id}` | Decision Authority read |
| Simulate | `POST /api/v2/simulate/run` | Agent Runtime public API, fixture providers |
| Simulate | `GET /api/v2/simulate/{run_id}/trace` | recorded runtime events |
| Publish | `POST /api/v2/publish/shadow` | proxy to console `POST /v1/governed-loop/shadow` |
| Observe | `GET /api/v2/observe/audit` | proxy to console `GET /v1/audit` |
| Observe | `GET /api/v2/observe/audit/{correlation_id}` | proxy to console `GET /v1/audit/{id}` |

**Deliberately absent, and to stay absent:** any issue, activate, revoke, grant,
authorize, clear or execute route. The v1 description already states the posture —
synthetic data, planning only, no agent execution, permission granting or
business-action authorization `[V]` — and v2 inherits it verbatim.

Two properties should be CI-enforced from the first v2 commit: the v2 document
regenerates deterministically like v1, and **no v2 operation id contains** `issue`,
`activate`, `revoke`, `grant`, `authorize`, `clear` or `execute`. A prohibition that is
only prose drifts; this one can be a test.

---

## Owner decisions (ruled 2026-09-05)

Both were ruled by the repository owner. They are no longer open; GAS-4 may start on
them when it is reached.

| # | Ruling |
|---|---|
| **SD-1** | **`EXPLICIT_PUBLIC_ALLOWLIST`.** The studio backend boundary is widened **only** through an explicit per-package allowlist of public entry points. All private submodules and all database drivers stay prohibited, and `backend/tests/test_architecture.py` is **retained** — extended, never deleted or weakened. A package reaches the studio by having one documented public surface added to the allowlist, or it does not reach the studio at all. |
| **SD-2** | **`NON_AUTHORITY_STUDIO`.** The studio never issues, activates, revokes, grants, authorizes, clears or executes. Constitution **preflights only**; Publish reaches **shadow only**. This is enforced by the v2 operation-id prohibition test sketched above, not by prose. |

Under SD-1, the allowlist that GAS-4 must add is exactly the entry points named in the
screen map above and no others — `ActivationRoot.preflight_issuance`, the compiler's
`validate` / `synthesize` / `compile_policy_pack`, the `PolicyRegistry` read surface,
the Decision Authority read surface, and the Agent Runtime public API. Under SD-2,
`ActivationRoot.issue_constitution` and `.activate_constitution`, `issue_policy`, and
the console's `/v1/actions/authorize` and `/v1/actions/clear` are named here as
**permanently out of the allowlist**.

## Gaps carried into GAS-4 `[G]`

No signing key or trust root; `InMemoryPolicyRegistry` is the only reachable registry;
Risk Authority `production_mode` raises `ProductionContainmentError`; HOLD, DEFER,
ESCALATE and MANUAL_REVIEW have no sink, so a parked simulation has nowhere to go; the
console `AuditStore` is per-instance. Each screen displays the gap it stands on rather
than presenting a complete-looking surface over an incomplete one.
