# Operations

Operational tasks for `ugence-ai-hiring` are exposed through the CLI. All of
them run deterministically and offline.

## Commands

```bash
# Assert safety/governance invariants; prints PASS/FAIL
python -m ugence_ai_hiring verify

# Run the canonical offline safe demo
python -m ugence_ai_hiring demo

# Print a sample accountability report
python -m ugence_ai_hiring report

# Distribution + product metadata (--json for JSON)
python -m ugence_ai_hiring version
```

A console script `ugence-ai-hiring` provides the same subcommands.

## verify

`verify` asserts the package's safety and governance invariants and prints
PASS/FAIL. Use it as a health/gate check before and during a controlled pilot.
It covers, among others: recommendations remaining advisory, binding decisions
requiring an authorized human actor, and record separation being preserved.

## demo

`demo` runs the canonical offline safe flow:

> evidence -> assessment -> advisory recommendation -> authorized human decision

and **stops before any enterprise action is executed**. It is a safe way to
observe the governed lifecycle without touching any external system.

## report

`report` prints a sample accountability report drawn from the distinct
accountability records the platform maintains.

## Audit records

The platform keeps evidence, assessment, recommendation, decision, override,
action request, authorization response, and execution as **distinct** records.
Authorization outcomes are recorded separately from the decisions and executions
they relate to. This record separation is what makes the accountability report
meaningful and is enforced as a governance invariant.

## Determinism

Because the package is deterministic and offline, operational runs are
reproducible: the same inputs yield the same outputs and the same audit trail.
Local timing is not a production benchmark. See
[KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md).
