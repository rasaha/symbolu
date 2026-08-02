# Agent Runtime — Package Boundary & Ownership Map

This document is the authoritative ownership map for the `ugence-agent-runtime`
package. It distinguishes what the runtime **owns** from what it **must not own**, and
records the enforced dependency direction.

## Agent Runtime OWNS

- agent and workflow execution state;
- task lifecycle; workflow lifecycle; step coordination;
- provider and tool invocation **interfaces**;
- retry, timeout, cancellation mechanics;
- pause / resume mechanics;
- checkpoints; runtime recovery;
- execution-result propagation (opaque);
- runtime correlation and tracing identifiers;
- deterministic runtime state transitions;
- runtime events;
- runtime-level failure classification;
- optional persistence **interfaces** (+ an in-memory reference);
- runtime extension points (injected clock, id generator, sinks, hooks).

## Agent Runtime DOES NOT OWN

- assertion governance; evidence admissibility;
- policy authorship; binding business decisions; DecisionRecord authority;
- ActionGate authorization; Action Clearance decisions; compliance policy;
- product-specific workflow semantics;
- GitHub-specific behavior; customer-specific routing;
- execution-provider credentials;
- enterprise product UI;
- sequence-risk policy; cross-workflow composite-threat policy.

## Enforced dependency direction

```
applications and products
        ↓
optional integration adapters   (concrete providers, concrete governance)
        ↓
ugence-agent-runtime            (this package — neutral, stdlib-only)
        ↓
neutral contracts and utilities (Python standard library only)
```

**Prohibited edges** (verified by `tests/test_import_boundaries.py` and
`artifacts/agent_runtime_dependency_rules.json`):

- `ugence-agent-runtime → Code Governance`
- `ugence-agent-runtime → product packages`
- `ugence-agent-runtime → robotics`
- `ugence-agent-runtime → concrete governance implementations`
  (TAP, Decision Authority, ActionGate, Action Clearance, StoryGraph, `cer_v0_*`)
- `ugence-agent-runtime → application entry points`
- `ugence-agent-runtime → monorepo test fixtures`
- `ugence-agent-runtime → any third-party runtime dependency`

## Why the boundary matters (evidence from the audit)

The legacy runtime (`agent_runtime_migration`) reaches concrete governance via
`cer_v0_3`, which transitively imports `cer_v0_1 → symbolu_robotics → numpy`. That
chain couples a "neutral" runtime to robotics and a heavy numeric dependency. The
independent package severs that chain: the core speaks the neutral governance
vocabulary **by value** and never imports a concrete governance or robotics module.

## Module layout

```
ugence_agent_runtime/
├── api.py            curated public API (single supported entry point)
├── config.py         immutable AgentRuntimeConfig (injected dependencies)
├── version.py
├── models/           agent, workflow, task, transitions, events, results
├── runtime/          engine, lifecycle, execution, retry, timeout, cancellation, errors
├── providers/        neutral provider interface + registry
├── persistence/      interfaces, checkpoints, recovery, in-memory reference
├── governance/       neutral hook interface, disposition mapping, fail-closed default + unsafe test hook
├── observability/    events, tracing, metrics
├── compat/           migration guidance (honest coexistence; NOT legacy aliases)
└── py.typed
```

Modules exist only where existing runtime behavior supports them; no empty module was
created merely to match a diagram.
