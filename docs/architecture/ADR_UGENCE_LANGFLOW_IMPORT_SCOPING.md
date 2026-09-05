# ADR — Langflow import: scoping

**Status:** scoping, 2026-09-05, under owner ruling `ENTER_LANGFLOW_IMPORT_FIRST`
(roadmap §11.3, superseding `DEFER_LANGFLOW_CUSTOMER_GATED`). **Contract-only.** No
importer, route, dependency or test exists; nothing here is implemented. Owner
decisions LI-1 to LI-5 in §7 are open. Labels: `[V]` verified, `[I]` inferred, `[R]`
requires ratification, `[G]` gap.

## 1 — The question

What can an exported Langflow flow become inside Ugence without violating GAS-R4, and
what must be refused? **It can become the shape of an agent: a task graph with tool
touchpoints and a draft governance pack around it. It cannot become a runnable prompt
chain**, because the runtime has no LLM, prompt or API node and the roadmap's
non-goals forbid adding one `[V]` (§11.2). The importer maps structure, refuses
content, and executes nothing.

## 2 — GAS-R4, preserved in full

Langflow is an import source only. Its exported JSON is untrusted input: validate,
never execute, compile to Workflow IR, enter as an ordinary unapproved policy pack,
confer no maturity `[V]` (roadmap §11.0 GAS-R4). One-way: nothing is exported back.
The importer imports no Langflow package and evaluates no code from the file.

## 3 — The Langflow export shape `[I]`

The public documentation site is unreachable from this environment (egress blocked
at `docs.langflow.org`), so the shape below is recorded from general knowledge of the
format and **must be verified against Langflow's published schema and a real export as
the first implementation step** (LI-5). As understood:

- top level: `name`, `description`, `data`, `is_component`, and version markers such
  as `last_tested_version`;
- `data.nodes[]`: `id`, `type` (typically `"genericNode"`), `position`, and `data`
  carrying `type` (the component class name, e.g. a prompt, model, tool or agent
  component) and `node` with `template` (the component's fields: each a typed value,
  some marked required or advanced), `base_classes`, `display_name`, `description`
  and `outputs`;
- `data.edges[]`: `source`, `target`, `sourceHandle`, `targetHandle`, with handle
  metadata naming the field and data type each end carries;
- custom components carry their Python source in a `template.code` field.

Two properties follow regardless of exact spelling: the graph is a directed graph of
typed components, and **some nodes embed executable source**. The second is the
reason GAS-R4 exists.

## 4 — Mapping: what is accepted and what it becomes

The runtime's executable shape is `WorkflowDefinition(tasks=(TaskDefinition(task_id,
operation, provider_id, consequential, arguments, depends_on), ...))` `[V]`
(`packages/runtime/agent-runtime/.../models/task.py:45-62`), and the studio's Simulate
route already accepts exactly that dict shape `[V]` (`services/studio_v2.py`,
`SimulateService.run`). The compiler's `compile_policy_pack` takes a `PolicyPack`
(decision rules, evidence, authority, approvals, connector mappings, action
constraints) and emits a governance `WorkflowIR` of authority nodes and dispositions
`[V]` (`compiler/compiler.py:222`, `compiler/workflow_ir.py`). **A flow graph is not a
policy pack.** GAS-5 as written names `compile_policy_pack` as the target; the honest
target is two artifacts, produced together:

| Langflow element | Becomes | Rule |
|---|---|---|
| a tool, API, database or integration component | one `TaskDefinition` with `operation` = component name, `provider_id` = a placeholder the operator must bind to a registered provider, `consequential = True` | never a real credential or endpoint; `template` values that look like secrets or URLs are dropped, not carried |
| an agent or chain component that invokes tools | one `TaskDefinition` per tool it reaches, `depends_on` from the edge order | the agent's reasoning interior is not represented |
| an edge | `depends_on` on the target task | cycles are refused (§5) |
| a model, prompt, memory, text or embedding component | **not a task**: recorded in a `source_map` diagnostic as "reasoning interior, not governed as a step" | GAS-R4 and §11.2: no generic LLM, prompt or API node |
| every external touchpoint | one `ConnectorMapping` (`policy_concept`, `target_system`, `target_field`, empty `credential_handle`) and one `ActionConstraint` with `requires_clearance = True` in a `PolicyPack` with `status = DRAFT` | the draft pack then goes through validate, synthesize and `compile_policy_pack` like any other |
| the flow's `name` and `description` | `WorkflowDefinition.metadata` and the pack's `name` and `description`, plus a digest of the accepted subset as provenance | the file itself is never stored |

Everything not in the table is unmapped and **refuses the import** rather than
degrading (GAS-5 exit criterion), unless the owner rules LI-3 otherwise.

## 5 — Refused with typed errors, zero evaluation

| Condition | Error |
|---|---|
| not JSON, not an object, missing `data.nodes` or `data.edges` | `MALFORMED_EXPORT` |
| bytes above a fixed cap, or node or edge count above a fixed cap | `EXPORT_TOO_LARGE` |
| nesting depth above a fixed cap | `EXPORT_TOO_DEEP` |
| any node whose template carries a `code` field, or any string that parses as Python or shell | `CODE_BEARING_NODE` (the source is never read past detection) |
| an edge referencing an unknown node, a duplicate node id, or a cycle | `GRAPH_INVALID` |
| a node type outside the allowlist | `UNMAPPED_NODE_TYPE`, naming the type |
| a template value matching a credential, token or private-key pattern | `SECRET_IN_EXPORT` (the value is never echoed) |
| a version marker the allowlist was not verified against | `UNVERIFIED_FORMAT_VERSION` |

The adversarial corpus is these rows as fixtures: malformed, oversized, cyclic, deeply
nested, code-bearing, secret-bearing, unmapped, mis-versioned. Exit criterion: every
fixture is refused with its typed error and the importer's evaluation counter is zero.

## 6 — Where it lives

- Route: `POST /api/v2/policy/from-langflow` in the additive v2 contract, already
  reserved by the v1 screen audit `[V]` (`GOVERNED_AGENT_STUDIO_V1_SCREEN_AUDIT.md:151`);
  the frozen v1 contract is untouched. The route delegates to the importer and returns
  the two artifacts plus the diagnostics; it grants, authorizes and executes nothing.
- Package: a new tooling package, `packages/tooling/langflow-import`, importing the
  compiler's models and stdlib only; no Langflow dependency (GAS-5 exit).
- Studio: the Policy screen gains an "import" action feeding the existing validate,
  synthesize and compile flow; Simulate can run the imported `WorkflowDefinition`
  against fixture providers once `provider_id` placeholders are bound.
- Maturity flag `langflow_import_implemented` flips only at the GAS-5 exit.

## 7 — Owner decisions `[R]`

| # | Decision | Options | Recommendation |
|---|---|---|---|
| LI-1 | The compile target | `TWO_ARTIFACTS` (WorkflowDefinition + draft PolicyPack, §4) \| `POLICY_PACK_ONLY` (as GAS-5 text says) | `TWO_ARTIFACTS`; a flow graph is not a policy pack |
| LI-2 | Reasoning-interior components (model, prompt, memory) | `RECORD_AS_DIAGNOSTIC` \| `REFUSE_IMPORT` | `RECORD_AS_DIAGNOSTIC`; refusing every flow with a model node would refuse every flow |
| LI-3 | Unmapped node types | `REFUSE` (GAS-5 exit as written) \| `DIAGNOSTIC_AND_DROP` | `REFUSE` |
| LI-4 | Provider binding for imported tools | `PLACEHOLDER_BOUND_BY_OPERATOR` \| `REFUSE_UNTIL_REGISTERED` | `PLACEHOLDER_BOUND_BY_OPERATOR`; Simulate refuses an unbound placeholder |
| LI-5 | Format verification | `PIN_ONE_VERIFIED_VERSION` (allowlist verified against one real export, others `UNVERIFIED_FORMAT_VERSION`) \| `BEST_EFFORT_ANY_VERSION` | `PIN_ONE_VERIFIED_VERSION` |

## 8 — Next step

Ruling on LI-1 to LI-5. No implementation prompt is issued while they are open. The
first implementation step after ruling is obtaining one real Langflow export from a
reachable environment and verifying §3 against it, before any parser is written.
