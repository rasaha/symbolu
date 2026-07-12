# Action Gateway — Runtime Enforcement Path

The first **runnable enforcement gateway** for the frozen agent-action
admissibility gate. It sits between an autonomous AI agent and external tools,
consumes proposed actions, asks the frozen Stage-1 reference gate whether each
action is admissible, and **enforces that decision at the point of execution** —
nothing runs without a verified, single-use execution token and a scoped,
broker-minted credential.

This is not another specification and not another library of primitives. It is
the wiring that turns the reference contracts into an actual chokepoint.

> **Transport-agnostic.** This gateway is transport-agnostic. MCP, HTTP, gRPC, or
> any future protocol can sit above this gateway. The included CLI is one such
> shell; none of them contain policy logic — admissibility is decided only by the
> frozen gate.

## What it is / is not

- **Is:** a deterministic, in-process runtime that canonicalizes → hashes →
  evaluates → mints an execution token → issues a scoped credential → invokes a
  tool adapter → audits, with fail-closed enforcement at every stage.
- **Is not:** an AI system (no BCVF/USE/SCC, no LLM reasoning), a simulation or
  blast-radius engine, a real credential vault, or a real cloud / Kubernetes /
  Terraform integration. Those are later stages (see **Limitations**).

## Architecture

```
        Agent (any transport: MCP / HTTP / gRPC / CLI)
          │   submit_action / evaluate_action / execute_action
          ▼
     ┌───────────────────────────────────────────────┐
     │                  Gateway                        │
     │  receive → validate → canonicalize → hash       │
     │        → EVALUATE (frozen reference gate)        │
     │        → mint execution token (on ALLOW)         │
     │        → issue scoped credential (broker)        │
     │        → invoke tool adapter                     │
     │        → append audit record (verify chain)      │
     └───────────────────────────────────────────────┘
          │                 │                    │
          ▼                 ▼                    ▼
   Reference Gate     CredentialBroker      ToolAdapter
  (action_gate_ref)   (scoped, short-lived)  (mock backends)
          │
      Decision ── Allow / Allow+Constraints / Simulate&Retry /
                  Request-Evidence / Escalate / Deny
```

The gateway **consumes** `action_gate_ref` (the frozen Stage-1 harness in the
sibling directory `../action_gate_reference`); it never reimplements
canonicalization, hashing, projection, evaluation, tokens, or auditing.

## Runtime flow

1. **`submit_action(req)`** — maps a transport-neutral `ToolRequest` to a canonical
   24-field envelope (`mapping.py`), validates + hashes it via the harness, and
   stores a `PENDING` record. Returns `request_id` + `action_hash`.
2. **`evaluate_action(request_id, evidence?, approvals?)`** — invokes
   `gate.evaluate`. The decision is recorded to the audit chain and drives the
   runtime state. **A token is minted only for `ALLOW` / `ALLOW_WITH_CONSTRAINTS`.**
   Re-evaluation with added evidence/simulation can advance a `PENDING` request.
3. **`execute_action(request_id, …)`** — requires an execution token. The token is
   re-verified against the *actual* call (`token.verify_token`): any expiry,
   replay, action-hash change, retarget, scope change, policy change, or TOCTOU
   state drift is rejected **before** the adapter runs. On success the broker
   issues a scoped credential, the adapter performs the (mock) action, the nonce
   is burned (single-use), and execution + result records are appended.

Every stage appends to a tamper-evident audit chain that is re-verified after
each append.

### Runtime states

`PENDING → APPROVED → EXECUTING → COMPLETED` on the happy path; terminal branches
are `DENIED`, `ESCALATED`, `EXPIRED`, `FAILED`. These are **runtime lifecycle**
states only — they are distinct from, and never modify, the frozen
specification's decision state machine (that trace is recorded verbatim inside
each decision record). See `state.py`.

## Adapter model

A `ToolAdapter` (`adapters.py`) exposes verbs and performs a side-effect **only
after** validating a broker-minted `ScopedCredential` through the broker. Included
adapters (mock unless noted):

| adapter | verbs | backend |
|---------|-------|---------|
| `FilesystemTool` | write / delete / read | **real, but confined to a sandbox root** |
| `ShellCommandTool` | run | mocked (never spawns a process) |
| `HTTPTool` | request | mocked (no network egress) |
| `TerraformTool` | apply / plan | mocked (no terraform/provider calls) |
| `KubernetesTool` | delete / apply | mocked (no cluster contact) |

Tool verbs are mapped onto the frozen operation taxonomy by `mapping.py` (see
`IMPLEMENTATION_FINDINGS.md#G1`): e.g. `filesystem.delete → DB_DELETE`,
`terraform.apply → DEPLOY`. Adapters contain no policy logic and cannot execute
without a valid capability — a forged credential (not minted by the broker) is
rejected by identity check.

## Credential broker

Adapters never hold standing credentials. The `CredentialBroker` interface mints a
short-lived `ScopedCredential` bound to a *specific verified token hash*, refusing
to widen scope beyond what the token permits and expiring no later than the token.
`MockCredentialBroker` mints an opaque capability handle — **no real secret
material**. Production key custody / real short-lived credentials are out of scope.

## Enforcement guarantees (all covered by tests)

| Guarantee | Where proven |
|-----------|--------------|
| No tool executes without an execution token | `test_no_bypass.py` |
| Adapters cannot execute directly / forged capability rejected | `test_no_bypass.py` |
| Token expiry enforced | `test_enforcement.py::test_expired_token_sets_expired_state` |
| Replay rejected (single-use nonce, survives restart) | `test_enforcement.py`, `test_determinism_and_state.py` |
| Argument / action modification rejected | `test_enforcement.py::test_modified_action_rejected` |
| Credential scope expansion rejected | `test_enforcement.py::test_scope_expansion_rejected` |
| Policy mismatch rejected | `test_enforcement.py::test_policy_mismatch_rejected` |
| TOCTOU state mismatch rejected | `test_enforcement.py::test_toctou_rejected` |
| Every execution path traverses the gate | `test_no_bypass.py`, `test_pipeline.py` |
| Audit complete + tamper-evident | `test_audit.py` |
| Deterministic decisions | `test_determinism_and_state.py` |

## Requirements & running

- **Python 3.11+**, standard library only. Requires the sibling reference harness
  at `../action_gate_reference` (imported automatically by `_ref.py`).
- **`pytest`** to run tests.

```bash
cd cyber_security/action_gateway

# integration tests
python3 -m pytest -q

# nine end-to-end enforcement demonstrations
python3 demos/run_demos.py

# CLI (file-backed session)
python3 -m action_gateway.cli --session /tmp/gw.json start --sandbox-root /tmp/gw-sb
python3 -m action_gateway.cli --session /tmp/gw.json submit --tool filesystem \
    --verb delete --target file://x.txt --args '{"last_replica": false}'
python3 -m action_gateway.cli --session /tmp/gw.json evaluate req-1     # -> DENY
python3 -m action_gateway.cli --session /tmp/gw.json execute  req-1     # -> E_NO_EXECUTION_TOKEN
python3 -m action_gateway.cli --session /tmp/gw.json audit
python3 -m action_gateway.cli --session /tmp/gw.json verify
```

CLI commands: `start, submit, evaluate, execute, status, audit, verify`. Output is
single-line JSON; no secret material is ever printed (there is none — signatures
and tokens carry no secrets).

## Demonstrations

`demos/run_demos.py` runs nine scenarios end-to-end and asserts the enforcement
outcome: safe filesystem write (allow), denied filesystem delete, terraform apply
requiring simulation, kubernetes delete requiring escalation, expired approval,
replay attempt, modified action after approval, credential scope expansion, and
TOCTOU state mismatch.

## Package layout

```
action_gateway/
  _ref.py        locate + import the frozen reference harness
  clock.py       injectable ms-precision UTC clock (Real/Fixed)
  errors.py      gateway error codes (+ re-export of harness GateError)
  state.py       runtime lifecycle states + legal transitions
  broker.py      CredentialBroker interface + MockCredentialBroker + ScopedCredential
  adapters.py    ToolAdapter interface + five mock adapters
  mapping.py     ToolRequest -> canonical envelope; (tool,verb) -> operation table
  gateway.py     the enforcement engine: submit/evaluate/execute, audit, snapshot
  cli.py         file-backed JSON CLI
demos/           scenarios.py (shared) + run_demos.py
tests/           pipeline, no-bypass, enforcement, audit, determinism/state, adapters/cli
IMPLEMENTATION_FINDINGS.md   gaps vs. the frozen specs (notably the taxonomy mapping)
```

## Limitations (out of scope — later stages)

- **No real execution backends.** Shell, HTTP, Terraform, and Kubernetes adapters
  are mocked; only the filesystem adapter touches disk, and only inside a sandbox.
- **No real credentials or key custody.** The broker mints opaque capability
  handles; signatures use the harness's HMAC *test* keys. Production requires
  asymmetric signing and hardware-backed key custody.
- **No real state oracle.** `MockStateOracle` exists to demonstrate the TOCTOU
  path; a production gateway must query live infrastructure state.
- **No simulation engine, blast-radius engine, or consequence reasoning.**
  Evidence and simulation are supplied as bound envelopes; the gateway does not
  produce them.
- **No transport server.** The gateway is an in-process object with an in-process
  API and a file-backed CLI; a network server (see below) is not included.

## Future MCP / transport integration

Because the gateway is transport-agnostic, a protocol server can wrap the same
three-call API without changing any enforcement logic:

- **MCP:** an MCP server whose tool-invocation handler calls `submit_action` →
  `evaluate_action` → `execute_action`, returning the decision (and, on
  non-allow, the reason) to the agent. The gateway becomes the admissibility
  layer for every MCP tool call.
- **HTTP / gRPC:** thin request handlers mapping endpoints to the same three
  calls; the execution token and audit chain are unchanged.

In every case the rule holds: **no execution path may bypass evaluation**, and the
frozen reference gate remains the sole authority on admissibility.
