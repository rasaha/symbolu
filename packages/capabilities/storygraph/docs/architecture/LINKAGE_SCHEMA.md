# Entity-Linkage Schema

Schema version: **`ctd.linkage/1.0.0`** (`ugence_storygraph/linkage.py`).

Groups events into assemblies by **explicit identifiers**, never inferred intent.
No embeddings, no LLM — a pure function of an event's structured fields.

## Entity dimensions

Normalized (trim + lowercase + whitespace-collapse) from both flat events and
ActionGate canonical envelopes:

| Dim | Source (first non-empty) |
|-----|--------------------------|
| `actor` | `actor`, `credential_scope.principal`, `delegator.id` |
| `agent` | `agent`, `agent_identity.id` |
| `workflow` | `workflow_id`, `case_id`, `arguments.workflow_id`/`case_id` |
| `target_family` | coarsened first `target_resource` (scheme + first segments) |
| `credential` | `credential`, `arguments.credential`/`secret_id`, principal |
| `dataset` | `dataset`, `arguments.dataset` |
| `destination` | `destination`, `arguments.destination`/`sink`/`cidr` |
| `device` | `device`, `arguments.device` |
| `tool` | `tool.tool_name`/`tool.name` |
| `environment` | `environment`, `arguments.environment` |
| `correlation` | `correlation_id` (legacy/synthetic grouping only) |

`tenant_id` is normalized separately; absent ⇒ `__untenanted__`.

## Assembly key

`AssemblyKeySpec{key_id, version, dims}` → `assembly_key =
digest("CTD-ASM", {tenant, spec_ref, {dim: value for present dims}})`.

- Keys are **always tenant-scoped** ⇒ cross-tenant linkage is impossible.
- A spec with **no** present dim for an event ⇒ `AMBIGUOUS` (the event is not
  grouped; the run report counts it).
- Linkage **confidence** is a deterministic rule output: `EXACT` (all spec dims
  present), `PARTIAL` (a non-empty subset), `AMBIGUOUS` (none). Not a probability.
- An event may link into **multiple** candidate assemblies (one per configured
  spec) where policy permits.
- Each `AssemblyLink` records `link_dims` — the exact identifiers that formed the
  key — so a finding can show *why* two events were linked.

## Shipped specs

| Name | Dims | Use |
|------|------|-----|
| `by_actor` | actor | one actor across sessions |
| `by_case` | workflow | one workflow/case across actors & sessions |
| `by_target` | target_family | actions converging on one resource family |
| `by_actor_target` | actor, target_family | actor operating on a resource family |
| `by_correlation` | correlation | **legacy/synthetic only** (not a default) |

The analyzer runs a **tuple** of specs simultaneously; the default is
`(by_case, by_actor)`. `by_correlation` is provided only for the synthetic
firearm illustration and legacy compatibility — §4 of the spec forbids
`correlation_id` as the sole default assembly boundary.
