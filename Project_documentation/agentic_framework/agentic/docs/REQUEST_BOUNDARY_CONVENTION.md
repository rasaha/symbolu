# Request-Boundary Enrichment Convention

**Scope:** this is the production rule every request-builder crossing
the governance boundary should follow. It is the operational companion
to `request_enrichment.py` and the "Inference CG Metadata ↔ MCP Gateway"
section of `AGENTIC_ARCHITECTURE.md`.

**TL;DR:** attach what you truly have, omit what you don't, never
fabricate.

---

## The contract, in one paragraph

A request-boundary caller (e.g. `SafeMCPGateway.call_tool_simple`,
`CGToolDispatcher.dispatch`, a future `AuthorizationRequest` builder)
owns three signal-attachment decisions on every call:

1. **`entropy_result`** — attach iff the caller holds live sovereign
   state.
2. **`vritti_result`** — attach iff the caller holds live sovereign
   state.
3. **`sovereign_projection_metadata`** — attach iff the caller holds
   an actual `SovereignProjectionResult`. Never derive it from 32D
   state alone.

All three must follow neutral-when-absent: the governance consumer
must handle the unattached case without branching differently, and
the absence of a signal must never be silently replaced with a
fabricated value.

---

## When to attach `entropy_result`

**Attach when:** the caller has CG-capable adapter metadata carrying
a 32D sovereign `state` (and optionally `delta_S`) produced by the
current request's inference step.

**Canonical path:**

```python
from agentic.agentic_framework.request_enrichment import (
    build_governance_enrichment_kwargs,
)
kwargs = build_governance_enrichment_kwargs(
    cg_metadata=adapter.last_cg_metadata, tier=tier,
)
if "entropy_result" in kwargs:
    call.entropy_result = kwargs["entropy_result"]
```

**Do not attach when:**
- The adapter has not generated yet (`last_cg_metadata == {}`).
- The sovereign state comes from a different request (stale).
- The caller only holds approximations or scalar heuristics. In that
  case let the governance consumer run its built-in fallback — that
  is what the fallback is for.

**Audit signal:** when `entropy_result` is attached, the audit record
reports `entropy_available=True` and the signal source is "real".

---

## When to attach `vritti_result`

**Attach when:** same condition as `entropy_result`. The two signals
are derived from the same 32D state in a single bridge call
(`governance_inputs_from_cg_metadata`) and are always attached as a
pair.

**Attachment contract is duck-typed.** `vritti_result` is not a formal
field on `MCPToolCall`; the governance consumer reads it via
`getattr(tool_call, "vritti_result", None)`. Use `setattr` / direct
attribute assignment; do not widen the dataclass.

**Audit signal:** `vritti_signal_source="real"`.

---

## When `sovereign_projection_metadata` is omitted

**Honest absence is the default.** `MistralCGAdapter.last_cg_metadata`
carries the 32D state only — it does not carry a
`SovereignProjectionResult`. Therefore no request-builder whose only
inference signal is CG metadata may attach
`sovereign_projection_metadata`. It is better to be silent than to
invent one.

**When it MAY be attached:** only when the caller holds a real
`SovereignProjectionResult` from an upstream producer. In that case
the caller uses:

```python
from agentic.agentic_framework.sovereign_bridge import (
    projection_metadata_from_sovereign_result,
)
projection_md = projection_metadata_from_sovereign_result(result)
request.sovereign_projection_metadata = projection_md
```

**What this means today:** no production request-builder currently
attaches this field. That is correct — the producer path does not
yet exist. Adding a fabricated value to close the "gap" would be
worse than leaving it absent.

---

## Neutral-when-absent rule

All three signals MUST be splatted through a helper that returns `{}`
when the input is absent. The canonical helper is
`build_governance_enrichment_kwargs`. Callers must not add a second
"if None" branch on top; that defeats the neutrality contract.

```python
# correct
kwargs = build_governance_enrichment_kwargs(cg_metadata=md, tier=t)
for key, val in kwargs.items():
    setattr(call, key, val)

# wrong — double branch, diverging paths
if md is not None:
    if md.get("state") is not None:
        call.entropy_result = ...
```

---

## Summary table

| Signal                            | Attach when                        | Never fabricate from |
|-----------------------------------|------------------------------------|----------------------|
| `entropy_result`                  | live 32D state for this request    | scalar heuristics    |
| `vritti_result`                   | live 32D state for this request    | scalar heuristics    |
| `sovereign_projection_metadata`   | real `SovereignProjectionResult`   | 32D state alone      |

---

## See also

- `agentic/agentic_framework/request_enrichment.py` — the helper.
- `agentic/agentic_framework/sovereign_bridge.py` — the translators.
- `agentic/agentic_framework/cg_tool_dispatcher.py` — the owner
  component that applies this convention for MCP tool calls.
- `Project_documentation/agentic_framework/agentic/AGENTIC_ARCHITECTURE.md` § "Inference CG Metadata ↔ MCP
  Gateway: Enrichment Seam" — the architectural frame.
