# Request Envelope Specification (v1)

*Phase 4. The versioned object passed through the control plane. Carries references + metadata,
never unrestricted payloads, never credentials.*

## Field classification

R=required · O=optional · D=derived · IM=immutable (once set, fixed for the trace) · C=confidential
(redact in artifacts) · NP=prohibited from persistence.

| Field | Class | Notes |
|---|---|---|
| `envelope_version` | R, IM | e.g. `"1"`; consumers check compatibility |
| `request_id` | R, IM | unique per request |
| `trace_id` | R, IM | spans the whole control-plane trace |
| `parent_trace_id` | O, IM | for nested/derived requests |
| `tenant_ref` | R, C | anonymized tenant reference (not raw tenant identity) |
| `task_type` | R | e.g. extraction, qa, summarization, agentic |
| `task_risk_class` | R | informational / advisory / decision-bearing / irreversible |
| `domain` | O | legal / health / finance / general |
| `input_classification` | R | public / internal / confidential / regulated |
| `data_sensitivity` | R | drives residency + partner-data rules |
| `residency_requirements` | O, IM | e.g. `"eu"`; critical fail-closed in ExecutionGate |
| `provider_allowlist` | O, IM | enterprise-approved providers |
| `provider_denylist` | O, IM | explicitly prohibited providers |
| `model_constraints` | O | e.g. min tier, frozen-version-required |
| `required_capabilities` | O | structured_output, tool_use, modalities |
| `context_length_requirement` | D | from input reference size |
| `structured_output_requirement` | O | strict/preferred/none |
| `tool_use_requirement` | O | bool |
| `latency_budget_ms` | O | hard SLA (EXEC) vs objective (MP) distinguished |
| `cost_budget_usd` | O | hard ceiling (EXEC) vs objective (MP) |
| `quality_floor` | O | ModelPolicy hard-quality gate input |
| `assertion_policy` | R | permitted claims, qualification/disclosure rules |
| `action_policy` | R | permitted actions, scope, approval requirements |
| `approval_requirements` | O | which actions require human approval |
| `human_authority_ref` | O, C | attributable approver reference (not PII) |
| `policy_versions` | R, IM | pinned per trace (assertion/action/enterprise policy) |
| `registry_version` | R, IM | pinned per trace |
| `timestamp` | R, IM | request receipt (passed in; not system clock in tests) |
| `deadline` | O, IM | absolute deadline |
| `mode` | R, IM | REPLAY / MOCK / SHADOW / ADVISORY / ENFORCEMENT (default MOCK) |
| `replay_flag` / `shadow_flag` | D | derived from `mode` |
| `content_ref` | R, C | reference/hash to input; **not** the raw payload |
| `redaction_state` | R | redacted / raw-permitted (raw-permitted requires explicit policy) |
| `provenance` | R | source + how the envelope was assembled |

## Rules

- **No credentials** in the envelope (NP). Credentials live only in the credential boundary.
- **Raw content is not carried**; `content_ref` + `redaction_state` govern access under policy. Fields
  marked C are redacted in decision records/artifacts; NP fields never persist.
- **Immutable fields** (IM) are pinned at layer 1 and cannot change mid-trace (invariant 10); a fallback
  is a *new decision* under the *same pinned versions*, not a version change.
- **Derived fields** (D) are computed by RequestNormalizer from other fields/refs and recorded as derived
  (auditable), never authoritative policy.
- **Compatibility:** a consumer receiving an unknown `envelope_version` fails closed
  (`POLICY.CONTRACT_VERSION_UNSUPPORTED`), never guesses.

## Minimal schema (illustrative)

```json
{
  "envelope_version": "1", "request_id": "...", "trace_id": "...", "tenant_ref": "t_****",
  "task_type": "qa", "task_risk_class": "decision-bearing", "input_classification": "confidential",
  "data_sensitivity": "regulated", "residency_requirements": "eu",
  "provider_allowlist": ["anthropic","google"], "required_capabilities": ["tool_use"],
  "latency_budget_ms": 4000, "cost_budget_usd": 0.5, "quality_floor": 0.7,
  "assertion_policy": {"require_qualification_below_confidence": 0.6, "prohibited_claims": []},
  "action_policy": {"permitted": ["notify"], "require_approval": ["payment","db_write"]},
  "policy_versions": {"assertion": "v1", "action": "v1", "enterprise": "v1"},
  "registry_version": "reg_v1", "mode": "MOCK", "content_ref": "sha256:...",
  "redaction_state": "redacted", "provenance": "gateway", "timestamp": 1000000
}
```
