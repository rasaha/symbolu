# Dependency Direction & Package Boundary Analysis

## How dependency direction is enforced in this repo

There is **no `import-linter`** configuration (`[tool.importlinter]` / `.importlinter`
absent; the "contract" matches in `pyproject.toml` are unrelated prose). Enforcement
is **static AST analysis + per-package boundary tests**:

- `platform_freeze/dependencies.py`
  - `FORBIDDEN_IMPORTS` — each frozen package → the top-level roots it must not import.
  - `PLATFORM` packages must never import `ai_hiring` / `domains` / `applications`.
  - `check_package_ownership` — every top-level package must have **exactly one
    canonical `__init__.py`** (single canonical owner).
- Per-package `tests/test_import_boundaries.py` + frozen `artifacts/*dependency_rules.json`.
- `python -m platform_freeze.verify` runs the `dependency_direction` and
  `package_ownership` checks as part of the freeze.

## Layering (enforced, from `AGENT_RUNTIME_PACKAGE_BOUNDARY.md`)

```
applications / products
        ↓
optional integration adapters (concrete providers, concrete governance)
        ↓
capability / runtime packages (neutral, stdlib-only leaves)
        ↓
neutral contracts / stdlib
```

Dependencies point **downward/inward only**. Upward or sideways edges (a leaf
importing an application, a platform package importing `ai_hiring`) are prohibited
and tested.

## Leaf-capability rule (governs AWC placement)

Capability packages under `packages/capabilities/` are declared **leaf, stdlib-only**
(Model Selection: "Python standard library ONLY … must not depend on applications,
domains, the control plane, the AI Control Plane, the optional orchestrator, Agent
Runtime, Hybrid LLM, the Governance Provider Framework, concrete providers…";
`governance-contracts`: "A leaf: no third-party runtime dependency and no other
Ugence package").

## Where AWC must sit (Phase 0 decision, consistent with the ADR)

- **Path:** `packages/capabilities/agent-workforce-composer/`
  (distribution `ugence-agent-workforce-composer`, namespace `ugence_agent_workforce_composer`).
  **Not created in Phase 0** — this is the frozen target location only.
- **Allowed dependencies:** Python stdlib, and at most the neutral
  `governance-contracts` leaf and the compiler's **data contract**
  (`ugence_policy_workflow_compiler` types consumed as data via the adapter).
- **Forbidden imports** (to be enforced by a P1 import-boundary test):
  Agent Runtime, H22 / `agentic` framework, Model Selection, Decision Authority,
  ActionGate, Action Clearance, StoryGraph, concrete providers, `ai_hiring`,
  `domains`, `applications`, control plane.

## Dependency-direction consequence for the H16 decision

Placing canonical selection in AWC keeps the arrow pointing the right way:

```
   H16 coordination (runtime, coupled tree)
        │  depends on / adapts
        ▼
   AWC (leaf, offline, stdlib-only)  ← consumes ← Policy Workflow Compiler (tooling, data)
```

The rejected Option C (H16 canonical, AWC an adapter over H16) would invert this:
AWC would depend **into** the coupled `agentic/` runtime tree, importing live
coordination, budget, and (via `LLMRouter`) nondeterministic runtime code — a
prohibited upward/sideways edge that also destroys AWC's offline determinism and
independent packaging. This is a primary reason the ADR selects Option A.

> Note: `docs/architecture/BOUNDARIES.md` is a *different* contract (the
> Core/Substrate ↔ Observer data-flow boundary for the `symbolu/` cognition
> pipeline) and does not govern package layering.
