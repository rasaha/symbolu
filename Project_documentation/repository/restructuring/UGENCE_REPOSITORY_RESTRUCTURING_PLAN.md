# Ugence Repository-Structure Audit & Restructuring Plan

**Continues:** `UGENCE_MODULARITY_AND_PACKAGING_AUDIT.md` and
`UGENCE_INTERMODULE_IO_AND_AUTHORITY_AUDIT.md`
(branch `claude/ugence-modularity-audit-uujl0h`; reference commits
`e7cb8d35f5d667174d4278c36229d34354869cc9`, `2adb2b9c6de6cea165ab495bc3cef2f891b7f6bc`).

**Problem:** the logical architecture is now clear (federated capabilities, distributed
authority), but the **physical codebase does not reflect it** — capabilities are spread across
unrelated directories, duplicate implementations, research folders, console reimplementations,
provider packages, and documentation-only folders.

**Central question:** how should the repository be reorganized so each capability has **one
canonical implementation, one public interface, one test boundary, one documentation home, and
one deployment boundary** — while preserving shared contracts and allowing modules to be migrated
safely one at a time?

**Phase discipline:** this is an **audit + plan** phase. **No production code is moved, renamed,
deleted, or changed.** All findings were verified against the live repository at commit
`2adb2b9c`, not taken from the prior audit summaries.

---

> ## Terminology update — Ugence Decision Governance (2026-08-01)
>
> *Canonical vocabulary per
> [`docs/architecture/ADR_UGENCE_DECISION_GOVERNANCE_TERMINOLOGY_AND_BOUNDARIES.md`](../docs/architecture/ADR_UGENCE_DECISION_GOVERNANCE_TERMINOLOGY_AND_BOUNDARIES.md).
> Documentation-only; no package, API, or freeze artifact is renamed here.*
>
> - **Ugence Decision Governance** is the umbrella (platform + product family). The capability
>   previously called "Decision Governance" in this plan is now the **Decision Authority**
>   capability, still implemented under the **`decision_governance`** package (name unchanged
>   this phase). Read "Decision Governance" headings in §2/§3/§9 below as *the Decision
>   Authority capability / its `decision_governance` kernel*.
> - The **capability inventory is ten, not nine**: **Model Selection** is a distinct capability,
>   separated from Hybrid LLM (§4).
> - The **AI Control Plane** and the **orchestrator** are **optional, bypassable** platform
>   services — never the umbrella and never a universal authority.
> - **Conceptual Model-C target** (directories are *not* created/renamed this phase):
>   ```text
>   packages/
>   ├── governance-contracts/
>   ├── capabilities/
>   │   ├── tap/  ├── decision-authority/  ├── actiongate/  ├── acp/  ├── storygraph/
>   │   ├── agent-runtime/  ├── context-minimization/  ├── model-selection/
>   │   ├── hybrid-llm/  └── llm-steering/
>   ├── platform/
>   │   ├── shared-services/  └── optional-ai-control-plane/
>   ├── products/  (assert/ · decide/ · act/ · sequence/)
>   └── adapters/
>   ```
> - **Migration roadmap (conceptual):** Completed — (1) StoryGraph canonical-package migration,
>   (2) StoryGraph documentation canonicalization, (3) Governance Contracts canonical-package
>   migration. Next — (4) integrate completed branches, (5) **Decision Authority** capability
>   migration, (6) Governance Provider Framework migration, (7) Model Selection focused
>   classification & migration, (8) ActionGate consolidation & migration, (9) ACP migration,
>   (10) Agent Runtime migration, (11) TAP migration, (12) Context Minimization migration,
>   (13) Hybrid LLM research relocation, (14) LLM Steering research relocation, (15) Optional AI
>   Control Plane & product-composition implementation. The **next capability migration concerns
>   the bounded Decision Authority engine, not the umbrella Ugence Decision Governance product
>   family.**

---

## 1. Verified baseline (current repository state)

| Item | Verified value |
|---|---|
| Branch / commit | `claude/ugence-modularity-audit-uujl0h` @ `2adb2b9c6de6cea165ab495bc3cef2f891b7f6bc` |
| Top-level directories | **100** |
| Root-level `*.md` docs | **123** |
| Test files in root `tests/` | **209** (capability tests scattered here, e.g. `test_hybrid_handover*`, `test_csr_*`) |
| Loose root-level `*.py` scripts | **39** |
| CER lineage directories | **5** (`cer_v0_1`, `cer_v0_2`, `cer_v0_3`, `cer_public_draft`, `cer_open_standard`) |
| Control-plane-named dirs | `control_plane/`, `control_plane_shadow/`, `ai_control_plane_v3/` (+ doc-only `acp/`, `ACP/`) |
| Doc-only dirs (0 `.py`) | `acp/`, `ACP/`, `agent_runtime_v2/` |
| Wheel/distribution units (`packaging/`) | **11** pyproject packages + 5 `verify_*_distribution.py` harnesses |
| Freeze artifacts | `platform/PLATFORM_FREEZE_V1.json` + 4 `api-snapshots/*.api.json` + `platform_freeze/` tooling — **preserved, untouched** |

### Verified test counts (run at `2adb2b9c`)

| Package | Result | Notes |
|---|---|---|
| `decision_governance/tests` | **29 passed** | frozen kernel |
| `governance_providers/tests` | **42 passed** | provider framework |
| `tap_provider/tests` | **38 passed** | adapter over mock |
| `actiongate_provider/tests` | **30 passed** | adapter over mock |
| `agent_runtime_migration/tests` | **74 passed** | clean proposer |
| `minimal_evidence_policy/tests` | **64 passed** | evidence-obligation engine (≠ Context-Min) |
| `ugence_console_api/tests` | **4 passed** | governed-loop integration |
| `cyber_security/composite_threat_detector/tests` (StoryGraph) | **289 passed** | self-contained engine |
| `cyber_security/action_gate_reference/tests` | **195 passed** | path-sensitive (run from its dir) |
| `cyber_security/action_gateway/tests` | **49 passed** | path-sensitive |
| `cyber_security/action_gateway_mcp/tests` | **51 passed** | path-sensitive |
| `cyber_security/action_gateway_k8s/tests` | **14 passed, 16 skipped** | skips = live-cluster e2e |
| `cyber_security/action_gate_policy_schemas/tests` | **13 passed, 1 skipped** | policy-as-code |
| `symbolu_robotics/autonomous_control_plane/tests` (ACP engine) | **112 passed** | frozen, shadow-only |
| `tests/test_csr_match_filter.py` + `test_csr_answer_audit.py` (LLM Steering) | **50 passed** | tests in **root** `tests/` |
| `tests/test_hybrid_handover.py` (Hybrid LLM) | **14 passed** | tests in **root** `tests/`; full research suite larger |
| `model_selection_pilot/tests` | **17 passed** | credential-blocked pilot |
| `experiments/actiongate_context_ablation/tests/test_compressor.py` (Context-Min) | **11 passed** (47s) | full suite has GPU/model tests that hang |

**Aggregate governance-relevant passing: ~1,096 tests (+17 skipped, infra/GPU-gated).** Two
structural facts already visible: (a) **tests are not co-located** — Steering/Hybrid/router tests
live in root `tests/`; (b) **engine suites are path-sensitive** (require running from their own
directory), because they are source trees, not installed packages.

### Packaging / freeze status (verified)

- **Independent wheels that build + pass isolation** (`packaging/`): `decision-governance`,
  `dgm-provider-framework`, `dgm-tap-provider`, `dgm-actiongate-provider` (+ baseline providers,
  benchmark, pilots, freeze tooling). Each package dir is a **symlink to canonical root source**
  (this symlink mechanism is the key enabler for safe migration — §9).
- **`platform_freeze` pins**: component versions, 4 public-API snapshot hashes, core-tree hashes,
  conformance hashes, dependency direction, and F1–F20 invariants. **Any physical move of a frozen
  package changes its tree paths/hashes and therefore requires an explicit, reviewed re-baseline**
  (§9). These artifacts are preserved unchanged in this phase.

---

## 2. Capability-to-code map

Candidate status ∈ `CANONICAL_IMPLEMENTATION` · `CANONICAL_ADAPTER` · `REFERENCE_IMPLEMENTATION`
· `COMPATIBILITY_LAYER` · `MOCK_OR_FIXTURE` · `EXPERIMENTAL` · `DOCUMENTATION_ONLY` ·
`DUPLICATE_IMPLEMENTATION` · `DEPRECATED_CANDIDATE` · `UNCLEAR`.

### Shared contracts / platform

| Capability | Directory | Impl type | Maturity | Publicly used | Tests | Candidate status |
|---|---|---|---|---|---|---|
| Provider framework | `governance_providers/` | contracts + registry + resolution + conformance + fingerprint | Frozen 0.1.0 | Yes (TAP, ActionGate) | 42 | **CANONICAL_IMPLEMENTATION** |
| Governance kernel + identity/audit/CER ports | `decision_governance/` (`api/`, `identity/`, `audit/`, `actions/cer.py`) | hexagonal kernel; ports are the shared contract | Frozen 1.0.0 | Yes | 29 | **CANONICAL_IMPLEMENTATION** (kernel) / contract source |
| CER — Canonical Execution Request | `cer_v0_3/` | clean-room impl + `run_control_plane` composer | current | Yes (agent_runtime) | via cer tests | **REFERENCE_IMPLEMENTATION** |
| CER older lines | `cer_v0_1/`, `cer_v0_2/` | superseded | — | v0_2 = frozen baseline of v0_3 | — | **COMPATIBILITY_LAYER / DEPRECATED_CANDIDATE** |
| CER spec | `cer_public_draft/`, `cer_open_standard/` | markdown spec/standard | — | — | — | **DOCUMENTATION_ONLY** |
| Freeze/release tooling | `platform_freeze/`, `platform/` | verify + classify + manifest + snapshots | — | Yes (CI) | — | **CANONICAL_IMPLEMENTATION** (tooling) |

### TAP

| Capability | Directory | Impl type | Maturity | Publicly used | Tests | Candidate status |
|---|---|---|---|---|---|---|
| TAP | `tap_provider/` (`provider.py`, `mapping/`, `api/`) | provider adapter | Frozen 0.1.0 | Yes (console) | 38 | **CANONICAL_ADAPTER** |
| TAP engine (shipped) | `tap_provider/core/__init__.py` | deterministic mock | — | Yes | (in 38) | **MOCK_OR_FIXTURE** |
| Real assertion engine | `assertion_governance/engine.py` | grounding/claim-strength engine, "NOT integrated" | Experimental | No | — | **REFERENCE_IMPLEMENTATION / EXPERIMENTAL** |
| Assertion research | `assertion_gate_robustness/`, `truth_assurance_pipeline/` | corpora/harnesses | Research | No | scattered | **EXPERIMENTAL** |
| Baseline provider | `baseline_assertion_provider/` | validation provider | — | test-only | — | **MOCK_OR_FIXTURE** |
| Console surface | `ugence_console_api/capabilities/truth_evidence.py` | fail-safe wrapper (EMERGING) | — | Yes | — | **COMPATIBILITY_LAYER** |

### Decision Governance

| Capability | Directory | Impl type | Maturity | Publicly used | Tests | Candidate status |
|---|---|---|---|---|---|---|
| DG kernel | `decision_governance/` | hexagonal kernel | Frozen 1.0.0 | Yes | 29 | **CANONICAL_IMPLEMENTATION** |
| Domain layers | `domains/{hiring,procurement}/`, `applications/` | app composition on kernel | — | Yes | in kernel/app tests | product/domain layer (not the capability) |
| Hiring impls | `ai_hiring/` | domain impls re-exported by `domains/hiring/` | — | Yes | large | **DUPLICATE_IMPLEMENTATION** (physical home of domain code) |

### ActionGate (TWO families)

| Capability | Directory | Impl type | Maturity | Publicly used | Tests | Candidate status |
|---|---|---|---|---|---|---|
| ActionGate provider | `actiongate_provider/` | provider adapter | Frozen 0.1.0 | Yes (console) | 30 | **CANONICAL_ADAPTER** |
| ActionGate provider engine | `actiongate_provider/core.py` | deterministic mock | — | Yes | (in 30) | **MOCK_OR_FIXTURE** |
| Reference gate core | `cyber_security/action_gate_reference/` | 6-outcome state machine | frozen ref | pilots (read-only) | 195 | **REFERENCE_IMPLEMENTATION** |
| Enforcement gateway | `cyber_security/action_gateway/` | real submit→evaluate→execute + token | Impl | pilots | 49 | **CANONICAL_IMPLEMENTATION** (engine) |
| MCP surface | `cyber_security/action_gateway_mcp/` | real MCP tools | Impl | — | 51 | **CANONICAL_ADAPTER** |
| K8s gateway | `cyber_security/action_gateway_k8s/` | real etcd+apiserver gateway | Impl | — | 14/16skip | **CANONICAL_ADAPTER** (deployment) |
| Isolated network service | `cyber_security/action_gateway_isolated/` | mTLS/Unix-socket service + ledger | Impl | — | path-issue | **REFERENCE_IMPLEMENTATION** (deployment) |
| Policy-as-code | `cyber_security/action_gate_policy_schemas/` | JSON-Schema policy pack | Impl | — | 13/1skip | **CANONICAL_IMPLEMENTATION** (schema) |
| Console surface | `ugence_console_api/capabilities/action_control.py` | wraps the **mock** (docstring claims "real") | — | Yes | — | **COMPATIBILITY_LAYER** (defect: mislabeled) |
| Execution eligibility | `execution_gate/`, `execution_gate_shadow/`, `execution_proposal_engine/` | separate "can-execute" capability | mixed | — | scattered | **EXPERIMENTAL** (distinct capability) |
| Baseline provider | `baseline_action_provider/` | validation provider | — | test-only | — | **MOCK_OR_FIXTURE** |

### ACP (TWO tracks)

| Capability | Directory | Impl type | Maturity | Publicly used | Tests | Candidate status |
|---|---|---|---|---|---|---|
| ACP engine | `symbolu_robotics/autonomous_control_plane/` (+ `cloud/`) | frozen, shadow-only, never-actuating | frozen research | via cer_v0_3/pilots | 112 | **REFERENCE_IMPLEMENTATION** |
| Cloud adapter | `cloud_controller/` | k8s scaling readiness/policy | Impl | ACP cloud track | scattered | **CANONICAL_ADAPTER** (infra) |
| Console gate | `ugence_console_api/capabilities/operational_safety.py` | 63-LOC threshold reimpl | — | Yes | in console 4 | **DUPLICATE_IMPLEMENTATION** |
| ACP spec/research | `acp/`, `ACP/` | markdown (0 `.py`) | — | — | — | **DOCUMENTATION_ONLY** |
| ACP DB profile | `cer_v0_3/acp_db/` | DB shadow adapter | — | via cer | in cer | **CANONICAL_ADAPTER** |

### StoryGraph

| Capability | Directory | Impl type | Maturity | Publicly used | Tests | Candidate status |
|---|---|---|---|---|---|---|
| StoryGraph | `cyber_security/composite_threat_detector/` | frozen-but-working matcher + policy pack + CLI | v2.0.0 | self-contained | 289 | **CANONICAL_IMPLEMENTATION** |

### Agent Runtime (THREE artifacts)

| Capability | Directory | Impl type | Maturity | Publicly used | Tests | Candidate status |
|---|---|---|---|---|---|---|
| Runtime (proposer) | `agent_runtime_migration/` | clean proposer, delegates to cer_v0_3 | partial | — | 74 | **CANONICAL_IMPLEMENTATION** (after hardening) |
| Framework | `agentic/agentic_framework/` | mature but embeds authority | 1.22.0 | README/examples | 2,260 collected | **DEPRECATED_CANDIDATE** (authority-confused) |
| V2 design | `agent_runtime_v2/` | markdown (0 `.py`) | — | — | — | **DOCUMENTATION_ONLY** |
| Broader research | `agentic/` (sovereign, guna, entropy, …) | research constructs | research | — | scattered | **EXPERIMENTAL** |

### Hybrid LLM

| Capability | Directory | Impl type | Maturity | Publicly used | Tests | Candidate status |
|---|---|---|---|---|---|---|
| Handover scaffold | `agentic/hybrid_handover/` | mock in-house + mock frontier | scaffold | — | 14 (root tests) | **EXPERIMENTAL** |
| Model selection | `model_selection_pilot/` (+ `_experiment/`, `_reconciliation/`) | real adapters, credential-blocked | pilot | — | 17 | **EXPERIMENTAL** |
| Governed inference | `governed_inference_pilot/` | orchestrator pilot | pilot | — | scattered | **EXPERIMENTAL** |
| Neural model | `symbolu/phase_transformer.py`, `train_hybrid_7b.py`, `symbolu_training/…/mistral_hybrid_wrapper.py` | training (falsified: 0% needle) | research | — | — | **EXPERIMENTAL** |
| Intra-model router | `symbolu/hybrid/router.py` | MoE phoneme router (unrelated) | research | — | `test_hybrid_router` | **EXPERIMENTAL** |

### Context Minimization

| Capability | Directory | Impl type | Maturity | Publicly used | Tests | Candidate status |
|---|---|---|---|---|---|---|
| Compressor (token core) | `experiments/actiongate_context_ablation/` | real extractive compressor, ActionGate-coupled full path | research prototype | via console (partial) | 11 (+GPU-gated) | **REFERENCE_IMPLEMENTATION / EXPERIMENTAL** |
| Console gateway | `ugence_console_api/capabilities/context_gateway.py` | wires lossless dedup via `sys.path` hack | — | Yes | in console 4 | **CANONICAL_ADAPTER** (weak slice) |
| Evidence-obligation engine | `minimal_evidence_policy/` | policy engine + frozen corpus (**≠ Context-Min**) | impl | — | 64 | separate capability — **REFERENCE_IMPLEMENTATION** |
| Siblings | `evidence_obligation/`, `scope_integrity/` | research | research | — | scattered | **EXPERIMENTAL** |

### LLM Steering

| Capability | Directory | Impl type | Maturity | Publicly used | Tests | Candidate status |
|---|---|---|---|---|---|---|
| CRS controller (core) | `scripts/cg_wrapper_ablation/csr_match_filter/` | real deterministic C×R×S + answer-audit | research core | — | 50 (root tests) | **REFERENCE_IMPLEMENTATION / EXPERIMENTAL** |
| Training-time steering | `agentic/sovereign/reasoning_kernel.py`, `symbolu/mechanical/olm/`, `guna_modulation/`, `symbolu_training/…` | torch hidden-state / Sanskrit-ontology | research | — | scattered | **EXPERIMENTAL** |

### Orchestrators / console / audit / deployment

| Concern | Directory | Impl type | Candidate status |
|---|---|---|---|
| Governed-loop orchestrator | `ugence_console_api/orchestrator.py` | 5-stage advisory loop (real modules) | **CANONICAL_IMPLEMENTATION** (optional orchestrator) |
| CER control-plane composer | `cer_v0_3/control_plane.py` | ActionGate+ACP composer | **REFERENCE_IMPLEMENTATION** |
| Invariant eval harness | `control_plane/` | Phase-10 orchestrator over **mocks** | **EXPERIMENTAL** (harness) |
| Other control planes | `control_plane_shadow/`, `ai_control_plane_v3/` | shadow/experimental | **EXPERIMENTAL** |
| Console / API | `ugence_console_api/` | FastAPI gateway + loop | **CANONICAL_IMPLEMENTATION** (integration layer) |
| Console UI | `apps/console/`, `frontend/` | React/Vite UI | product UI |
| Audit (contract) | `decision_governance/audit/` | AuditRepository port + service | **CANONICAL_IMPLEMENTATION** (contract) |
| Audit (console) | `ugence_console_api/audit.py` | in-memory prototype seam | **COMPATIBILITY_LAYER** |
| Deployment | `Procfile` (research server), `nixpacks.toml`, `deploy/` (Cloud-Scaling rigs), `.mcp.json` (alpaca) | research/unrelated | not governance deployment |

---

## 3. Canonical implementation per module

| Module | Canonical choice | Basis | Caveat |
|---|---|---|---|
| **Provider framework** | `governance_providers/` | frozen, tested, boundary-enforced, used by both providers | — |
| **Decision Governance** | `decision_governance/` | frozen v1.0.0, zero Ugence coupling, tenant on records, ports for IAM/audit | domain code physically under `ai_hiring/` should move under `domains/` |
| **StoryGraph** | `cyber_security/composite_threat_detector/` | 289 tests, zero coupling, real policy-as-code, advisory boundary | needs packaging + rename only |
| **Agent Runtime** | `agent_runtime_migration/` | clean proposer, delegates authority, forbidden-import test | **hardening required** (3 profiles, no service); framework is deprecated-candidate |
| **ActionGate** | **No single canonical yet — consolidation required.** Engine = `cyber_security/action_gateway` + `action_gate_reference` + `action_gate_policy_schemas`; adapter = `actiongate_provider/`. | engine is real & uncoupled; adapter is the packaged shell — but wired to a **mock** | **Consolidate:** point the adapter at the real engine; unify the two families |
| **ACP** | **No implementation ready to become canonical without consolidation.** Prefer promoting the digital/cloud track of `symbolu_robotics/autonomous_control_plane` | engine is real but shadow-only research; console gate is a 63-LOC divergent reimpl | resolve the two-track split; retire the console reimpl |
| **TAP** | `tap_provider/` as the **adapter**, but **no canonical engine** — `assertion_governance/engine.py` is unintegrated and the shipped core is a mock | adapter is clean; engine value is research | **Consolidation required** to wire a real engine behind the seam |
| **Context Minimization** | **No implementation ready.** Token core = `experiments/actiongate_context_ablation` (research, ActionGate-coupled); console wires only the lossless slice | real algorithm, wrong home, coupled | extract from `experiments/`, decouple from ActionGate ref |
| **Hybrid LLM** | **None ready** — scaffold + blocked pilot + falsified model | research only | keep in `research/` until validated |
| **LLM Steering** | **None ready as a product** — `scripts/cg_wrapper_ablation/csr_match_filter` is a productizable research core | real, model-agnostic, but under `scripts/`, unpackaged | promote to `research/` then productize |

> **Do not select by directory name.** E.g. the top-level `acp/` and `ACP/` (doc-only) and
> `agent_runtime_v2/` (doc-only) carry the product names but contain **no implementation**; the
> real engines live under `symbolu_robotics/` and `agent_runtime_migration/`.

---

## 4. Capabilities vs commercial products

**Capabilities** (internal, reusable engines — **ten**; see the Terminology update above and the
ADR): TAP, **Decision Authority** (implemented under the `decision_governance` package), ActionGate,
ACP, StoryGraph, Agent Runtime, Context Minimization, **Model Selection**, Hybrid LLM, LLM Steering.
*(Model Selection was previously folded under Hybrid LLM; it is a distinct capability.)*

**Products** (customer-facing compositions over capability **public contracts** — never new
copies of the engines):

| Product | Composes (capabilities) | Business outcome |
|---|---|---|
| **Ugence Assert** | TAP (+ audit) | governed assertion/evidence |
| **Ugence Decide** | Decision Authority (`decision_governance`) + TAP (+ audit) | accountable business decisions |
| **Ugence Act** | ActionGate + ACP + Agent Runtime (+ audit) | governed agent action |
| **Ugence Sequence** | StoryGraph + ActionGate (+ audit) | sequence-risk governance |
| **(future) Private-Model Governance** | Hybrid LLM + Context Minimization + LLM Steering | private-model efficiency & steering |

**Rule:** a capability is implemented **once** and appears in `capabilities/`; each product under
`products/` is **composition + configuration only** and imports capabilities through their public
APIs. Today this rule is violated — the console **re-implements** the ACP gate and computes an
**ad-hoc CER**, and `ai_hiring/` embeds domain logic re-exported by `domains/hiring/`.

---

## 5. Target repository models

| Criterion | **Model A** capability monorepo (`packages/<cap>/`) | **Model B** domain/application/infrastructure | **Model C** contracts/platform/capabilities/products/adapters/research |
|---|---|---|---|
| Independent packaging | **Excellent** (one wheel per package) | Poor (layers cut across capabilities) | **Excellent** |
| Code ownership | Clear per capability | Blurred | **Clear** per capability + layer |
| Dependency direction | Good (flat) | Good (DDD) but capability-agnostic | **Best** (explicit layer DAG) |
| Test isolation | **Excellent** | Medium | **Excellent** |
| Product composition | Needs a convention for products | Products implicit | **Explicit `products/`** |
| Connector reuse | Ad-hoc | Ad-hoc | **Explicit `adapters/`** |
| Deployment flexibility | Good | Medium | **Good** (platform services separable) |
| Ease of understanding | Good | Medium (abstract) | **Good** (names match logical model) |
| Migration risk | Low–medium | High (re-slices everything) | Low–medium |
| Long-term maintainability | Good | Medium | **Best** |

**Recommendation: Model C — as a superset of Model A.** Model C keeps A's "one package per
capability" (its strongest property) but adds explicit **contracts / platform / products /
adapters / research** layers that match the federated-governance conclusion of Audit 2. Reject
Model B: layer-first slicing hides capability boundaries and breaks independent packaging/sale,
which is the entire commercial premise. **The recommended structure is the §6 candidate layout,
validated below.**

---

## 6. Validation of the candidate layout

**Adopt with the refinements below.** Layer-by-layer verdict:

### `packages/governance-contracts/` — **ADOPT**
- **Belongs:** pure contracts only — `identity/`, `tenancy/`, `policy/`, `evidence/`, `results/`
  (the common result envelope from Audit 2 §10), `errors/`, `audit/`. Source today:
  `governance_providers/contracts/*`, `decision_governance` identity/audit **ports** +
  `ContextEnvelopeRecord`, the CER identity from `cer_v0_3` (as a contract, not the engine).
- **Must NOT belong:** any engine/business logic, any provider implementation, any product code.
- **Refinement:** this package must be **importable with zero heavy deps** (today
  `governance_providers.api` transitively drags `decision_governance`+`pydantic` via
  `adapters/__init__` — split contracts from adapters so contracts are a leaf).

### `packages/capabilities/<module>/` — **ADOPT**
- **Belongs:** exactly one canonical implementation per capability (§3), its ports/adapters,
  schemas, tests, docs.
- **Must NOT belong:** product composition, vendor-specific connectors, another capability's code.

### `packages/platform/` — **ADOPT (with independent deployability)**
- **Belongs:** shared runtime **services** — `policy-registry/`, `evidence-registry/`,
  `audit-reconstruction/`, `connector-registry/`, `control-plane/` (the optional composer =
  today's `cer_v0_3.run_control_plane`), `optional-orchestrator/` (today's
  `ugence_console_api.orchestrator`).
- **Must NOT belong:** capability business logic. The control-plane/orchestrator must **compose**
  capabilities via contracts, never re-implement them (fixes the console ACP reimpl + ad-hoc CER).
- **Control-plane services SHOULD be independently deployable** (each its own process/wheel), and
  **optional** — a single-capability customer deploys none of them.

### `packages/products/` — **ADOPT (composition/config ONLY)**
- **products/ must contain only composition + configuration** — wiring capabilities through public
  APIs, product-level policy defaults, packaging manifests. **No capability implementation may live
  under products/.**

### `packages/adapters/` — **ADOPT as a HYBRID**
- **Central `adapters/`** for cross-capability connectors: `kubernetes/`, `mcp/`, `http/`,
  `microsoft/`, `servicenow/`, `customer-specific/`.
- **Capability-native adapters stay in-package** (a capability's own `ports/`+`adapters/`, e.g.
  TAP's evidence resolver, DG's IdentityProvider impls). Rule: **adapters depend on capability
  *public APIs*, never internals.** So: generic connectors central; capability-intrinsic adapters
  local. Do not force every adapter centrally.

### `research/` — **ADOPT**
- **Research MAY import production public APIs; production MUST NOT import research.** Today this is
  violated: `ugence_console_api` imports the Context-Min compressor from `experiments/…` via a
  `sys.path` hack. That import must be inverted (productize the compressor into
  `capabilities/context-minimization/`, leave the ablation study in `research/`).

### `examples/`, `deployment/`, `docs/`, `tools/` — **ADOPT**
- Absorb the **123 root `.md` files** into `docs/` (per-capability docs move into each package's
  `docs/`; cross-cutting into top-level `docs/`). Absorb the **39 loose root scripts** into
  `tools/` or `research/`. Absorb the **209 root `tests/`** into each capability's `tests/`.

---

## 7. Strict dependency rules

**Direction (machine-enforceable):**
```
products  →  adapters / platform-services  →  capabilities  →  governance-contracts
research  →  (production public APIs only)                    [one-way]
```

### Allowed-import matrix (row MAY import column)

| Importer ↓ \ Target → | contracts | capability (public API) | capability (internals) | platform svc | adapter | product | research |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| **governance-contracts** | ✅(self) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **capability** | ✅ | ⚠️ approved-only¹ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **platform service** | ✅ | ✅ | ❌ | ✅ | ⚠️² | ❌ | ❌ |
| **adapter** | ✅ | ✅ | ❌ | ⚠️² | ✅(self) | ❌ | ❌ |
| **product** | ✅ | ✅ | ❌ | ✅ | ✅ | ✅(self) | ❌ |
| **research** | ✅ | ✅ | ❌ | ✅ | ✅ | ⚠️ | ✅ |

¹ A capability may import another capability **only** through its public API and **only** when the
dependency is explicit and unavoidable (today: none required — providers never import each other;
Agent Runtime reaches ActionGate/ACP via the `cer_v0_3` control-plane **port**, not imports).
² platform↔adapter coupling only via published interfaces.

### Prohibited-import matrix (hard failures)

| Prohibited edge | Why | Enforced by (target) |
|---|---|---|
| contracts → anything | contracts are a leaf | extend `platform_freeze` dep check |
| capability → another capability's **internals** | breaks independence (F16/F17) | AST import test (like `test_forbidden_imports.py`) |
| advisory capability → an authority module | advisory produces evidence via contracts (TAP/StoryGraph/Context-Min/Steering must not import ActionGate/DG) | AST test |
| product → capability internals | products compose via public API only | AST test |
| adapter → capability internals | adapters use public API | AST test |
| production → research | research is downstream only | AST test (invert the console→experiments hack) |
| Agent Runtime → self-authorization | must delegate (`ensure_not_self_authorized`) | existing runtime guard + test |
| ACP → authorize | ACP holds/clears, never permits | `compose()` invariants + test |
| StoryGraph → binding effect | advisory only (`AUTHORITY="ADVISORY"`) | evidence-ceiling test |
| ActionGate → assertions/decisions/routing/context | stays a bounded exact-action authority | contract-scope test (F7) |
| console/API → re-implemented capability logic | console composes, never re-implements (fixes ACP reimpl + ad-hoc CER) | review + AST test |

These extend the **already-existing** enforcement: `platform_freeze` dependency-direction check,
`governance_providers/conformance` AST import-boundary check, and
`agent_runtime_migration/tests/test_forbidden_imports.py`.

---

## 8. Standard internal module structure

Every production capability adopts one identical shape (one canonical impl, one API, one test
boundary, one doc home, one deploy boundary):

```
packages/capabilities/<capability>/
├── pyproject.toml            # one wheel; pinned dep on governance-contracts only
├── README.md                 # what it is, its authority level, quickstart
├── CHANGELOG.md              # SemVer history; compat statements
├── src/
│   └── ugence_<capability>/
│       ├── __init__.py       # curated public exports only
│       ├── api/              # THE public interface (the only thing others import)
│       ├── domain/           # pure domain types/logic (no I/O)
│       ├── application/      # use-case services (stateless coordinators)
│       ├── ports/            # Protocols for identity/persistence/audit/etc.
│       ├── adapters/         # reference/in-proc adapters for the ports
│       ├── schemas/          # request/result envelopes (+ result-envelope extension)
│       ├── conformance/      # self-conformance kit (like governance_providers)
│       └── version.py        # __version__, CONTRACT_VERSION, compat majors
├── tests/                    # co-located; independent; no cross-capability deps
├── docs/                     # capability's single documentation home
└── deploy/                   # optional Dockerfile / manifest = its deploy boundary
```

Rules: `api/` is the sole import surface; `domain/` has no I/O; external systems reach the
capability only through `ports/` (dependency injection, not imports); `schemas/` carries the
**common result envelope** (`correlation_id, module_id, module_version, authority_type,
advisory_or_binding, result_category, result_digest, unavailable_controls, required_next_step`)
plus module-specific extensions (Audit 2 §10). This generalizes the pattern **already proven** by
`decision_governance/` and `governance_providers/`.

---

## 9. Migration plan (safe, one capability at a time)

**Enabling mechanism — reuse the existing symlink pattern.** `packaging/` already symlinks
distribution dirs to canonical root source. Migration inverts this: move canonical source into
`packages/…/`, then leave a **compatibility symlink** at the old path so every existing import,
test, and the freeze verifier keep working until each consumer is cut over. This makes each move
behavior-preserving and independently revertible.

**Per-capability migration recipe (identical each time):**
1. Create `packages/<layer>/<capability>/` with the §8 skeleton.
2. `git mv` the canonical source in; leave a symlink (or re-export shim) at the old path.
3. Co-locate its tests (pull the capability's files out of root `tests/`); its docs (from the 123
   root `.md`); its deploy manifest.
4. Run that capability's suite + `python -m platform_freeze.verify` + the relevant
   `verify_*_distribution.py`. Green = proceed.
5. Update `platform_freeze` **paths/hashes** as a reviewed **APPLICATION_LOCAL/MAJOR** re-baseline
   (a physical move changes `core_tree_hashes` and api-snapshot paths — this must be an explicit,
   classified change, never silent).
6. One capability = one PR. Merge before starting the next.

**Recommended sequence (lowest risk / highest clarity first):**

| Order | Capability | Why first/last | Risk |
|---|---|---|---|
| 1 | **StoryGraph** | zero coupling, self-contained, 289 tests — proves the target structure end-to-end | **LOW** |
| 2 | **governance-contracts** | extract the shared contract package (split contracts from adapters to remove the transitive-DG bleed) | **MEDIUM** (touches frozen APIs → re-baseline) |
| 3 | **Decision Governance** | frozen, clean; move `ai_hiring/` domain code under `domains/` in the same pass | **MEDIUM** (freeze re-baseline) |
| 4 | **ActionGate** | consolidate the two families: adapter (`actiongate_provider`) + engine (`action_gateway`/`action_gate_reference`/`policy_schemas`); wire adapter to real engine | **HIGH** (two families, freeze, security) |
| 5 | **TAP** | move adapter; decide engine strategy (integrate `assertion_governance` or keep mock explicitly) | **MEDIUM–HIGH** |
| 6 | **Agent Runtime** | promote `agent_runtime_migration`; mark `agentic_framework` deprecated; docs from `agent_runtime_v2` | **MEDIUM** |
| 7 | **ACP** | resolve two-track split; promote engine; delete console reimpl | **HIGH** (shadow research → productize) |
| 8 | **Context Minimization** | extract compressor from `experiments/`; invert the console→research import; keep `minimal_evidence_policy` as its own capability | **MEDIUM** |
| 9 | **Hybrid LLM**, **LLM Steering** | move to `research/` first (not `capabilities/`); productize only after validation | **LOW** (research relocation) |
| — | **platform / products / adapters** | stand up `optional-orchestrator` + `control-plane` as platform services; convert the console into a thin `products/` composition that stops re-implementing capability logic | **MEDIUM** |

**Preserve throughout:** freeze manifest, API snapshots, and all evidence reports are **carried
forward and re-baselined explicitly**, never dropped. The two prior audit reports and this plan
are the migration's acceptance record.

**Migration risk register:**

| Risk | Mitigation |
|---|---|
| Physical move breaks freeze hashes | Re-baseline `platform_freeze` per PR; classify as MAJOR/APPLICATION_LOCAL with review |
| Path-sensitive engine tests (ActionGate family) break when moved | Package them (add `pyproject`), replace `sys.path`/conftest hacks with installed-package imports |
| Console loses behavior when it stops re-implementing ACP/CER | Cut over to the real capability + platform control-plane behind a feature flag; keep the reimpl as a temporary shim |
| Two-family/two-track consolidation (ActionGate, ACP) changes behavior | Do consolidation as a **separate** behavior-changing PR **after** the pure move; gate on parity tests |
| Research relocation breaks root `tests/` collection | Move tests with code; update `pyproject` `testpaths`/`norecursedirs` |

---

## 10. Deliverables summary

1. **Baseline** — §1 (verified counts, wheels, freeze artifacts).
2. **Capability-to-code map** — §2 (candidate status per directory, all 9 modules + shared).
3. **Canonical selection** — §3 (with explicit "no implementation ready" calls for ActionGate,
   ACP, TAP-engine, Context-Min, Hybrid, Steering).
4. **Capabilities vs products** — §4.
5. **Target-model comparison** — §5 (recommend Model C ⊃ Model A).
6. **Candidate-layout validation** — §6 (adopt with the contracts-leaf, hybrid-adapters, and
   invert-research-import refinements).
7. **Dependency rules + import matrices** — §7.
8. **Standard module structure** — §8.
9. **Safe one-at-a-time migration plan + risk register** — §9.

### Unsupported claims (structure)

- "Each product name maps to an implementation" — false: `acp/`, `ACP/`, `agent_runtime_v2/` are
  doc-only; real engines live elsewhere (`symbolu_robotics/`, `agent_runtime_migration/`).
- "The console is the platform" — the deployed process (`Procfile`) is the **research** server;
  the console is manual and re-implements capability logic.
- "One CER / one audit exists" — three CER schemes (`cer_v0_3`, kernel `ContextEnvelopeRecord`,
  console ad-hoc) and three audit shapes coexist.

### Final verdict

**Adopt Model C (capability packages under explicit contracts/capabilities/platform/products/
adapters/research layers).** The repository is *logically* federated but *physically* scattered
across 100 dirs, 123 root docs, and 209 misplaced tests, with duplicate/mock/reference/doc-only
copies of most capabilities. Migrate **one capability at a time** using the existing symlink
mechanism as a compatibility shim, re-baselining the freeze per move, in the risk order of §9
(StoryGraph first; ActionGate and ACP — the two multi-implementation modules — hardest and last
among the productizable set; Hybrid LLM and LLM Steering to `research/` until validated). Behavior
changes (two-family/two-track consolidation, console de-duplication) are **separate** PRs *after*
the pure moves. **No code is moved in this phase.**
