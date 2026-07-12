# Action Gateway MCP — Protocol-Facing Enforcement Integration

The first **protocol-facing** enforcement layer for the agent-action
admissibility gate. An MCP-compatible tool gateway that intercepts every tool
invocation, converts it into the canonical action envelope, runs it through the
runtime gateway (`action_gateway`, which consumes the frozen reference gate
`action_gate_ref`), and permits execution **only** through a valid execution
token and a broker-issued, single-use scoped capability.

> **This is a reference enforcement integration.** Mock adapters are not
> production cloud integrations. Mock capabilities are not production credential
> custody. **Protocol interception without network and credential isolation is
> bypassable** — interception without credential control is *monitoring*, not
> *enforcement*. **MCP is an adapter here, not an architectural dependency:** the
> same server core is reusable by an HTTP/gRPC adapter.

No AI reasoning. No BCVF/USE/SCC. No production cloud credentials.

## Architecture

```
   Agent  ──MCP (JSON-RPC-ish: tools/list, tools/call)──►  McpGateway (server.py)
                                                              │
        parse ─ identity reconcile ─ registry map ─ guards    │  protocol boundary
                                                              ▼
                            ┌───────────────────────────────────────────┐
                            │  action_gateway.Gateway (runtime core)     │
                            │  validate → canonicalize → hash → EVALUATE │
                            │  → mint token → issue scoped capability     │
                            │  → invoke adapter → audit                   │
                            └───────────────────────────────────────────┘
                                          │
                            action_gate_ref (frozen gate: six outcomes)
```

Layer reuse (nothing re-implemented): `action_gateway_mcp` → `action_gateway` →
`action_gate_ref`. Canonicalization, hashing, policy, tokens, approvals, and
audit are all imported from the frozen harness.

## Protocol boundary

`server.McpGateway` speaks a minimal MCP-style envelope (`protocol.py`;
`method` = `tools/list` | `tools/call`). Every intercepted call runs the
pipeline: parse → identify agent/runtime/session/delegator → construct canonical
envelope → submit → evaluate → return one of the six frozen outcomes → (only if a
token was issued) obtain a scoped capability → invoke the adapter → append
decision + execution audit records → return a structured response. **No handler
invokes a tool adapter directly.**

### Phases (kept distinct)

| Phase | Method(s) | Authority |
|-------|-----------|-----------|
| Discovery / read-only | `list_tools`, `read` | schemas + non-sensitive metadata; **no execution** |
| Evaluation | `prepare`, `evaluate`, `simulate`, `provide_evidence`, `attach_approval` | build/hash/evaluate an action; **cannot execute** |
| Execution | `execute` | requires token + action-hash + policy-hash + state-freshness + unused nonce + broker capability + adapter verification |

A protocol request alone is never execution authority.

## Exposed tools (mock production-infrastructure surface)

`filesystem.write`, `filesystem.delete`, `terraform.plan`, `terraform.apply`,
`kubernetes.get`, `kubernetes.apply`, `kubernetes.delete`, `iam.inspect`,
`iam.grant`, `monitoring.disable` — three read-only (`kubernetes.get`,
`iam.inspect`, `terraform.plan`) and seven mutating.

## Canonical mapping

`registry.py` is the single explicit mapping from MCP tool → frozen operation,
runtime (tool, verb), target-resource builder, credential scope, reversibility,
required evidence/simulation/rollback, and a strict argument schema. **Unknown
tools, verbs, targets, or argument shapes fail closed** — nothing is coerced into
a generic "safe" operation. Machine-readable metadata (`registry.metadata()`) is
served by `tools/list` and covered by a completeness test. Numeric arguments must
be typed strings (Action Profile: no bare JSON numbers).

## Credential broker

Adapters never hold durable credentials. On an admissible decision the runtime
broker mints an opaque `ScopedCredential` bound to the verified token's hash,
scope, and expiry; it is **single-use**, cannot be widened by the client, and is
rejected if forged (identity check) or replayed. *Interception without this
credential control is monitoring, not enforcement* — the mock still demonstrates
the property (a broader-scope request or a reused capability is rejected).

## Simulation & approval flows

- **Simulation** (`simulation.py`): Terraform plan, Kubernetes dry-run, and IAM
  permission-delta previews produce **structured** frozen evidence envelopes
  (`is_simulation=True`) bound to the exact action hash, producer version,
  validity interval, and state hash — never a bare `safe: true`. Changing the
  proposed action changes the hash and unbinds the evidence.
- **Escalation & approval** (`escalation.py`): an escalated request carries the
  action hash, canonical summary, dispositive rules, requested approval scope,
  consequence/reversibility, required approver roles, expiry, and correlation id.
  `create_test_approval` builds an exact-action, exact-policy approval via the
  frozen approval-binding implementation (dual-control test keys). There is no
  automatic or AI approval.

## Audit & observability

Two independently-verifiable, tamper-evident chains (both frozen primitives): the
**protocol** chain (`audit.py`) records the full lifecycle (receipt, envelope
construction, evidence/simulation, approval, decision, execution attempt/result),
and the **enforcement** chain (in `action_gateway`) records decisions/executions.
Sensitive argument values (`content`, secrets, tokens) are redacted; raw secrets
and broker capabilities are never logged. `Metrics` are **observational only** —
counters (requests by outcome, rejected bypass attempts, token/capability
replays, stale-state rejections, executed actions, audit-verification failures)
never affect authorization.

## Local usage (CLI)

`python3 -m action_gateway_mcp.cli <command>` — file-backed session, single-line
JSON output, no secrets/capabilities printed.

```bash
cd cyber_security/action_gateway_mcp
SESS=/tmp/mcp.json
python3 -m action_gateway_mcp.cli --session $SESS start --sandbox-root /tmp/mcp-sb
python3 -m action_gateway_mcp.cli --session $SESS list-tools
python3 -m action_gateway_mcp.cli --session $SESS submit --tool kubernetes.get \
    --args '{"namespace":"prod","kind":"pod","name":"web"}'            # read-only ALLOW
python3 -m action_gateway_mcp.cli --session $SESS submit --tool filesystem.write \
    --args '{"path":"a.txt","content":"hi"}'                            # -> SIMULATE_AND_RETRY (req-1)
python3 -m action_gateway_mcp.cli --session $SESS simulate req-1        # -> ALLOW_WITH_CONSTRAINTS
python3 -m action_gateway_mcp.cli --session $SESS execute  req-1        # -> COMPLETED
python3 -m action_gateway_mcp.cli --session $SESS escalations
python3 -m action_gateway_mcp.cli --session $SESS approve  req-2        # attach exact-action approval
python3 -m action_gateway_mcp.cli --session $SESS audit
python3 -m action_gateway_mcp.cli --session $SESS verify
python3 -m action_gateway_mcp.cli --session $SESS metrics
python3 -m action_gateway_mcp.cli --session $SESS demos
```

Commands: `start, list-tools, submit, status, simulate, provide-evidence,
escalations, approve, execute, audit, verify, metrics, demos`.

## Demonstrations

`python3 demos/run_demos.py` runs fifteen scenarios end-to-end and asserts the
enforcement outcome: read-only k8s query allowed; safe constrained filesystem
write; denied filesystem delete; terraform apply requiring simulation; kubernetes
delete escalate-then-approve-then-execute; IAM self-grant denied; modified
action; modified arguments after token; credential scope expansion; replayed
execution token; replayed broker capability; TOCTOU state mismatch; direct
adapter bypass; unknown MCP tool; and parallel duplicate execution (at most one
commit). All 15 pass.

## Tests

`python3 -m pytest -q` — 43 tests: protocol parsing, registry coverage + mapping,
identity reconciliation, phase separation, simulation/approval binding, constraint
enforcement, all bypass scenarios, audit integrity + redaction, metrics
neutrality, persistence/restart, concurrency, deterministic evaluation, and the
demo scenarios. Run the full stack (nothing previously green regresses):

```bash
(cd ../action_gate_reference && python3 -m pytest -q)   # 123
(cd ../action_gateway        && python3 -m pytest -q)   # 39
python3 -m pytest -q                                     # 43
```

## Package layout

```
action_gateway_mcp/
  _core.py       locate + re-export runtime gateway + frozen harness
  errors.py      MCP-layer error codes (re-exports harness GateError)
  context.py     RequestContext + declared/authenticated identity reconciliation
  registry.py    MCP-tool -> canonical-action mapping (fail-closed) + metadata
  protocol.py    JSON-RPC-ish parsing + outcome -> response mapping
  simulation.py  mocked structured simulation-evidence producers (bound)
  escalation.py  reference escalation queue + exact-action approval helper
  audit.py       protocol audit chain + redaction + observational metrics
  readonly.py    read-only handlers (no execution authority)
  server.py      McpGateway: phases, guards, enforcement, snapshot/restore
  clientkit.py   reference client session (monotonic sequence + fresh nonces)
  cli.py         file-backed JSON CLI
demos/           scenarios.py (15) + run_demos.py
tests/           protocol/mapping, identity, flows, bypass, audit/persistence/concurrency
IMPLEMENTATION_FINDINGS.md
```

## Limitations (out of scope — later stages)

- **Mock adapters, not production integrations.** No real filesystem-outside-
  sandbox, shell, network, Terraform, Kubernetes, or IAM/monitoring calls.
- **Mock capabilities, not credential custody.** The broker mints opaque handles;
  signing uses the frozen HMAC *test* keys. Production needs real short-lived
  credentials, asymmetric signing, and hardware-backed key custody.
- **No network/egress isolation.** This is in-process; without real transport
  authentication and egress control, protocol interception is bypassable.
- **Mock state oracle & simulation.** TOCTOU and simulation are demonstrated with
  deterministic mocks; production needs real state oracles and simulators.
- **No transport server.** In-process API + file-backed CLI; a real MCP/HTTP/gRPC
  server is not included.

## How a non-MCP (HTTP/gRPC) adapter reuses this gateway

`McpGateway` contains no MCP-specific enforcement — only `protocol.parse_request`
and the response shape are MCP-flavored. An HTTP/gRPC adapter maps its endpoints
to the same methods (`prepare` / `evaluate` / `simulate` / `execute` / `read`),
supplies a `RequestContext` from its own transport-authenticated identity, and
gets identical enforcement: the frozen gate decides admissibility, the runtime
gateway mints and verifies tokens, and the broker controls capabilities. The rule
is invariant across transports: **no execution path bypasses evaluation**, and a
protocol request is never, by itself, execution authority.
