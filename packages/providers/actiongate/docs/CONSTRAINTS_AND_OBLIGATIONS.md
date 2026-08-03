# Constraints & Obligations

ActionGate issues **authorization constraints** and **obligations**. It encodes each
typed native control as a `"type=value"` string in the neutral result; unknown
extension types are preserved as `"ext:type=value"` — **never silently discarded**.

## Known constraint types
`maximum_amount`, `execution_deadline`, `required_approval`, `allowed_region`,
`parameter_restriction`, `rate_limit`, `single_use`.

## Known obligation types
`notification`, `logging`, `human_review`.

## Guarantees
- supported constraint types remain deterministic; values remain intact;
- ordering does not change semantic meaning;
- unknown extensions are preserved as `ext:type=value`;
- `AUTHORIZED_WITH_CONSTRAINTS` never collapses to unrestricted `AUTHORIZED`;
- obligations remain **separate** from constraints; required `human_review` is an
  obligation, never represented as automatic approval;
- canonical and legacy imports produce **identical** encodings.

## Scope boundary (important)

ActionGate **issues** constraints and obligations. It does **not** itself execute or
necessarily enforce each one at runtime. Runtime enforcement of a constraint (e.g.
`maximum_amount`, `single_use`) and fulfilment of an obligation (e.g. `human_review`)
belong to **downstream** layers (the control plane / execution layer). An emitted
`single_use` constraint is **not** durable replay prevention on its own. See
`KNOWN_LIMITATIONS.md`.
