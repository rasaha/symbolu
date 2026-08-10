# R1.5 — Runtime Integration (Gateway + MCP)

Integrates the R1 remediation projection into the runtime Gateway and MCP surfaces.
**Opt-in, advisory only. ActionGate's decision logic is unchanged; nothing here can make the
system more permissive.** Default is OFF → responses are byte-identical to pre-R1.5.

## 1. Runtime architecture
```
Action → gateway.submit_action → gateway.evaluate_action
             │
             ├─ gate.evaluate(...)              # FROZEN, unchanged
             ├─ decision finalized + audited (audit chain written)
             ├─ token minted on ALLOW           # unchanged
             └─ IF remediation enabled:          # AFTER finalize, no feedback into evaluate()
                    remediation.project_remediation(decision, envelope, signed_policy, …)
                    remediation_runtime.apply_limits(...)
                    resp.update(remediation_fields)   # additive
MCP: server.evaluate → resolve trust from RequestContext → gateway.evaluate_action(mode,trusted)
     → protocol.decision_response(remediation=…)      # additive passthrough
```
The projection runs strictly after the finalized decision and audit write, reads only the same
inputs the gate read, and feeds nothing back into `gate.evaluate`.

## 2. Trust resolution — where trust comes from
`gate.evaluate` and the gateway are libraries; **the transport establishes trust**, not the
gate. R1's reference `--trusted-admin` flag is replaced at runtime by the MCP
`RequestContext`:
- **Authenticated identity** (`ctx.authenticated_agent_id`) — transport-established (mTLS /
  signed session). The self-declared `declared_agent_id` is never used for trust.
- **Capabilities** (`ctx.client_capabilities`) — must be bound to the authenticated session.

`McpGateway._resolve_remediation(ctx, requested)` returns `(mode, trusted)`:
- `OFF/MINIMAL/STANDARD` → `trusted=False`, always allowed.
- `TRUSTED_PLANNER/HUMAN_ONLY/FULL` → `trusted` only if **authenticated AND** the matching
  capability is present (`remediation:trusted_planner` / `:human` / `:full`; `:full` grants all).
- The gateway then **clamps**: a privileged mode without trust is downgraded to `STANDARD`
  (`remediation_runtime.clamp_mode`). **FULL is never granted by request alone** — it requires
  an authenticated caller plus an authenticated capability.

Production note: `client_capabilities` MUST be established by the authenticated transport, not
self-asserted in the payload (documented; the reference models it as a context field).

## 3. Gateway integration
`gateway.evaluate_action(request_id, *, evidence, approvals, remediation_mode="OFF",
remediation_trusted=False, remediation_limits=None)`. New keyword-only args with
backward-compatible defaults. When `remediation_mode` resolves to non-OFF, the six advisory
fields (`response_schema_version`, `all_unmet_conditions`, `required_changes`, `retryability`,
`disclosure`, `retry_budget`) are appended to the existing response; existing keys are
unchanged. `remediation_runtime.py` (new) provides mode clamping and payload bounding.

## 4. MCP integration
- `protocol.decision_response(..., remediation=None)` — optional; merges the advisory fields
  (no key collides with existing protocol fields). The response still carries
  `execution_token: None` — never authority.
- `server.evaluate(ctx, request_id, *, evidence, approvals, remediation_mode="off")` — resolves
  trust from `ctx`, forwards `(mode, trusted)` to `gateway.evaluate_action`, and passes the
  attached fields to `_respond`. Default `off` → byte-identical passthrough. The
  evidence/simulate/approval helper methods inherit the default and are unaffected.

## 5. Runtime controls (`remediation_runtime.py`)
- `max_required_changes` (default 32) — caps the list.
- `max_payload_bytes` (default 16384) — sheds `all_unmet_conditions`, then trims
  `required_changes`, until under budget.
- Truncation is marked honestly: `disclosure.truncated = true` and markers in
  `disclosure.redacted_fields` (`required_changes[>N]`, `all_unmet_conditions:size`).
- Safe defaults: mode OFF; unknown mode → OFF; privileged-without-trust → STANDARD.

## 6. Compatibility results
- **Reference 161**, **Gateway 49** (39 pre-existing + 10 new), **MCP 51** (43 + 8), **k8s 14
  pass / 16 skip**, **conformance 24/24** — all green.
- Default OFF responses are byte-identical (asserted for both gateway and MCP). No existing
  client requires modification. No existing test changed.
- k8s serializes its own response shape and is unaffected (no remediation surface added there
  in R1.5).

## 7. Security findings (verified by tests)
- **Decision unchanged.** `outcome`, `dispositive_rules`, `action_hash`, and `token_hash` are
  identical with remediation OFF vs FULL (gateway + MCP).
- **Hashes unchanged.** The audit-chain head is identical OFF vs ON — remediation is attached
  after the audit write and is in no hashed payload.
- **No authority.** The remediation block contains no token, credential, signature, or key
  material; the protocol response still carries `execution_token: None`. It cannot authorize
  execution (a non-ALLOW outcome still mints no token; execution still requires token verify →
  scoped credential).
- **Approval / action binding intact.** The ALLOW path mints the identical token with
  remediation on, and the request still executes only via token verification + scoped
  credential. Enabling remediation changes no binding.
- **Disclosure safe.** FULL is unreachable without an authenticated capability; STANDARD/
  MINIMAL never reveal exact thresholds; MINIMAL omits policy structure.
- **Bounded payload.** Size limiting truncates and marks honestly.

## 8. Contradictions discovered
**None.** The R1 schema, outcomes, and retry classes were sufficient for runtime integration;
no redesign was required. The only additive runtime signal is `disclosure.truncated` (a bounded
transport concern), which extends — not redesigns — the R1 disclosure object.

## 9. Remaining roadmap
- Optional gateway/MCP CLI `--remediation-mode` surfacing (the library + MCP API paths are
  done; CLI is a thin follow-up).
- Broker-side **retry governance** (attempt caps, budgets, timeouts, loop/duplicate detection)
  — the `retry_budget` container is present but null in R1.5; enforcement is a later phase.
- k8s transport passthrough (compatibility-only in R1.5).
- Production trust binding: wire `client_capabilities` to the authenticated transport session
  (mTLS/OIDC), replacing the reference context field.

## Files changed
- `action_gateway/action_gateway/_ref.py` — export `remediation` (additive).
- `action_gateway/action_gateway/remediation_runtime.py` — **new** (clamp + limits).
- `action_gateway/action_gateway/gateway.py` — `evaluate_action` attaches remediation after finalize.
- `action_gateway_mcp/action_gateway_mcp/_core.py` — export `ref_remediation` (additive).
- `action_gateway_mcp/action_gateway_mcp/protocol.py` — `decision_response(remediation=…)`.
- `action_gateway_mcp/action_gateway_mcp/server.py` — trust resolution + `evaluate(remediation_mode=…)`.
- Tests: `action_gateway/tests/test_remediation_integration.py` (10),
  `action_gateway_mcp/tests/test_remediation_integration.py` (8).
