# Pilot: Approval-Gated Internal Copilot

**Status:** Complete (second adoption pilot)
**Script:** `examples/pilot_internal_copilot.py`
**Run:** `python examples/pilot_internal_copilot.py`

---

## What it does

An internal operations copilot with a clear read/write approval
boundary. The copilot can freely search and analyze internal data,
but requires human approval before any externally-visible or
state-changing action.

**Tools (6):**

| Tool | Risk | Approval |
|------|------|----------|
| `search` | read_only | auto-execute |
| `analyze` | read_only | auto-execute |
| `check_alerts` | read_only | auto-execute |
| `save_draft` | write | approval required |
| `send_update` | write | approval required |
| `escalate` | execute | approval required |

**Phases:**
1. Tool discovery — catalog all 6 tools, show approval coverage
2. Free read path — search executes without interruption
3. Approved write — save_draft triggers approval, approved, executes
4. Denied write — send_update triggers approval, denied, skipped
5. Structured output — typed OperationsSummary dataclass
6. Trace comparison — side-by-side trace table + full denied trace

---

## Why this is a good fit

The research-assistant pilot (pilot 1) exercised broad tool
composition and `require_all` approval. This pilot specifically
stresses the **per-action-type approval boundary**:

- Read actions flow through without interruption
- Write actions are gated by `ApprovalPolicy(require_approval_for=...)`
- The developer sees the approval boundary before running (Phase 1)
- Both approved and denied paths produce clear trace evidence
- The trace viewer renders approval events with decision + reason

This is the pattern most enterprise internal copilots need:
search/read freely, gate saves/sends/escalations.

---

## Runtime features exercised

| Feature | How it is used |
|---------|----------------|
| `build_agent()` + `ToolSpec` | Compose 6-tool governed agent |
| `ApprovalPolicy` | Per-action-type approval (not require-all) |
| `ApprovalController` | Callback with approve + deny paths |
| `BudgetPolicy` | Token + cost caps visible in traces |
| `TraceCollector` | Captures events from `run_stream()` |
| `format_trace()` | Human-readable trace output |
| `ToolCatalog` | Discovery + approval coverage preview |
| `StructuredRunResult` | `OperationsSummary` dataclass schema |
| `AgentRunEvent` | 17 event types streamed live |
| `AgentRunTrace` | Post-run summary with approval/budget counters |

---

## What the traces prove

**Read path (search):**
- Status: completed, 1 action executed, 0 approvals requested
- Proves: read-only actions bypass approval gate entirely

**Approved path (save_draft):**
- Status: completed, 1 action executed, 1 approval requested, 0 denied
- Proves: write action triggers approval, callback approves, action executes

**Denied path (send_update):**
- Status: completed, 0 actions executed, 1 approval requested, 1 denied
- Proves: write action triggers approval, callback denies, action skipped cleanly

**Structured output:**
- Status: completed, validates against `OperationsSummary` dataclass
- Proves: schema-enforced output works with budget policy

---

## Friction points discovered

### F1: Double approval gate (requires_confirmation + ApprovalPolicy)

`ToolSpec.requires_confirmation=True` triggers the MCP gateway's
`EscalationHandler` (which auto-denies by default) as a *separate*
gate from the R4 `ApprovalPolicy`/`ApprovalController`. If both
are set, a developer-approved action gets blocked by the gateway.

**Workaround:** Use one gate or the other, not both. This pilot
uses `ApprovalPolicy` (orchestration-level) and leaves
`requires_confirmation=False` on the ToolSpecs.

**Recommended fix:** Either pass R4 approval decisions through to
the gateway, or document the two-layer model explicitly.

### F2: Action mapping repetition

Building each phase required repeating the same 8-entry
`action_type_to_tool` dict. The pilot works around this by
calling `build_agent()` for each phase with the same mapping.

**Recommended fix:** Extract the mapping to a module-level constant
(as the pilot does), or allow the agent to be re-wired with a new
adapter without rebuilding the full stack.

### F3: One agent per adapter

The pilot creates a new `build_agent()` per phase because each
phase needs a different `SequentialMockAdapter` with different
scripted responses. With a real LLM, one agent would handle all
phases in a multi-turn conversation.

**Not a framework bug** — this is a mock-adapter limitation. Real
adapters would reuse one agent across all phases.

### F4: ToolCatalog shows requires_confirmation from ToolSpec, not ApprovalPolicy

The "Approval-required tools" display from
`catalog.find_tools(requires_confirmation=True)` shows tools where
`ToolSpec.requires_confirmation=True`, which is the gateway-level
flag. The R4 `ApprovalPolicy` is a separate object. There is no
single query that shows "which tools will trigger R4 approval?"

**Workaround:** The pilot manually iterates
`approval_policy.requires_approval(tool.name)` to show coverage.

**Recommended fix:** Consider a helper that merges ToolCatalog
and ApprovalPolicy into a unified "what needs approval?" view.

---

## What it does NOT prove

- Real LLM inference (uses mock adapters)
- Interactive human approval (callback is automated)
- Multi-turn conversation with evolving approval needs
- Async approval workflows
- Production deployment patterns
- Multiple approval levels (e.g. manager vs incident commander)

---

## Comparison with pilot 1 (research assistant)

| Dimension | Research assistant | Internal copilot |
|-----------|-------------------|-----------------|
| Approval mode | `require_all=True` | Per-action-type |
| Tools | 4 (search, compute, validate, save) | 6 (3 read, 3 write) |
| Approval paths | 1 (deny-all write) | 2 (approve + deny) |
| Trace viewer | Manual print loop | `format_trace()` utility |
| Structured output | ResearchAnswer | OperationsSummary |
| Primary stress | Broad tool composition | Approval boundary clarity |

---

## Final evaluation

1. **Was the framework usable?** Yes. The per-action-type approval
   policy worked as designed. The trace viewer made inspection
   trivial.

2. **Where was it smooth?**
   - `build_agent()` + `ToolSpec` composition (one call per agent)
   - `format_trace()` replaced ~40 lines of manual print code
   - `ApprovalPolicy` per-action-type selection
   - `ToolCatalog` discovery and filtering
   - Trace comparison table from `AgentRunTrace` fields

3. **Where was it awkward?**
   - Double approval gate (F1) — confusing, needs documentation
   - Action mapping repetition (F2) — verbose but not blocking
   - No unified "what needs approval?" query (F4)

4. **Top 3 adoption improvements:**
   1. Document and clarify the two approval layers (R4 vs gateway)
   2. Add a helper that merges ToolCatalog + ApprovalPolicy into
      a single approval-coverage view
   3. Allow agent adapter replacement without full rebuild (for
      multi-phase workflows)
