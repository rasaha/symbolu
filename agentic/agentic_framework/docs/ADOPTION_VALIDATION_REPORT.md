# Adoption Validation Report

**Date:** 2026-04-06
**Validation mode:** Simulated second-developer (fresh-start self-validation)
**Validator:** Not a real external developer. This is an honest simulated
second-developer exercise where the validator followed only the public docs,
examples, and API surface — no hidden project history knowledge was used.

---

## 1. Setup path followed

1. Read `docs/QUICKSTART.md` — found the "fastest path" and "governed agent with custom tools" snippets
2. Read `docs/FIRST_GOVERNED_AGENT.md` — understood the five-layer mental model and progressive feature additions
3. Read `examples/minimal_governed_agent.py` — smallest runnable example (54 lines)
4. Read `examples/pilot_internal_copilot.py` — approval-gated copilot with multi-phase workflow
5. Ran all quickstart code snippets verbatim — all worked
6. Ran `minimal_governed_agent.py` — worked, produced clear trace output
7. Built a new use case (alert triage assistant) following only the above docs

**Install path:** `pip install -e .` from repo root (documented in quickstart). Worked.

---

## 2. What worked smoothly

| Area | Details |
|------|---------|
| **Quickstart snippets** | Both snippets ran correctly on first try. Copy-paste worked. |
| **`build_agent()` factory** | One-call composition is genuinely ergonomic. A new dev can get a governed agent in ~10 lines. |
| **`ToolSpec` design** | Bundling handler + risk level + description in one object is intuitive. No two-step registration needed. |
| **`format_trace()` output** | Clear, readable trace timeline. A new dev immediately sees what happened in their run. |
| **Top-level exports** | `build_agent`, `ToolSpec`, `ToolRiskLevel`, `ApprovalController`, `ApprovalPolicy`, `BudgetPolicy`, `TraceCollector`, `format_trace`, all event types — all importable from `agentic.agentic_framework`. |
| **Approval system** | `ApprovalPolicy` + `ApprovalController` + callback pattern is simple and works. Selective per-action-type approval is clear. |
| **Budget enforcement** | `BudgetPolicy` with token/cost caps works out of the box. |
| **Streaming events** | 17 event types are well-named and cover the full lifecycle. Event payloads are consistent. |
| **Mental model diagram** | The quickstart's ASCII diagram (`adapter → wrapper → safety gate → action loop → trace`) is immediately clarifying. |
| **Progressive disclosure** | Minimal example → pilots → advanced features is a natural learning curve. |

---

## 3. What required source-code spelunking

| What I needed | Where I had to look | Should have been in docs |
|---------------|--------------------|-----------------------|
| **`MockLLMAdapter` import path** | `llm_adapters.py` | `__init__.py` top-level exports (**fixed**) |
| **`SequentialMockAdapter` existence** | `pilot_internal_copilot.py` source | Quickstart or examples overview |
| **`action_type_to_tool` behavior** | `agent_builder.py` source, `agent.py` source | Quickstart (**fixed**: added section) |
| **Decomposition JSON format** | `goal_decomposition.py:DECOMPOSITION_PROMPT` | Quickstart or first-governed-agent |
| **How `MockLLMAdapter` interacts with decomposition** | `goal_decomposition.py:_extract_json()` and `_simple_extraction()` | Quickstart (**fixed**: added note) |
| **What happens when action type doesn't match any tool** | `agent.py:_execute_single_action()` | Error message is now clear (from Task 1 hardening), but not documented |

---

## 4. What was confusing in docs/examples/API naming

### Documentation confusion

| Issue | Severity | Details |
|-------|----------|---------|
| **Import path inconsistency** | Medium | Quickstart showed `from agentic.agentic_framework.agent_builder import build_agent` but `build_agent` is also in `__init__.py`. New devs don't know which to use. **Fixed:** quickstart now uses top-level imports. |
| **`action_type_to_tool` not explained** | High | The most confusing concept for a new developer. You need to understand goal decomposition, the LLM's action vocabulary, and tool registration — all before you can wire a non-trivial agent. **Fixed:** added explanatory section to quickstart. |
| **No "how mock adapters work" section** | Medium | New devs need to understand that `MockLLMAdapter` returns a fixed string, and whether that string is parsed as JSON affects what actions are produced. **Fixed:** added note to quickstart. |

### API naming confusion

| Issue | Severity | Details |
|-------|----------|---------|
| **`allow_stub=True`** | Low | Required when using `MockLLMAdapter` but the name suggests it's about stub *tools*, not stub *adapters*. The warning message clarifies, but the name is slightly misleading. |
| **`CGToolDispatcher`** | Low | "CG" prefix suggests it requires CG-capable adapters, but `build_agent()` uses it for all adapters (including plain MockLLMAdapter). The naming creates unnecessary apprehension. |
| **`mcp_gateway.py` as home for `ToolSpec`** | Low | `ToolSpec` is a developer-facing type that new devs use constantly. Its home module (`mcp_gateway`) sounds like an internal implementation detail. The top-level export mitigates this. |
| **`run_with_trace` vs `run_stream` + `TraceCollector`** | Low | Two ways to do the same thing. The docs explain both clearly, but a new dev may wonder which to prefer. (Answer: `run_with_trace` for simple cases, `run_stream` when you need live event handling.) |

### Example gaps

| Issue | Severity | Details |
|-------|----------|---------|
| **No example with custom action_type_to_tool** | High | All existing examples either use identity mapping (minimal) or internal copilot-style mapping that's buried in a large script. A small focused example would help. The adoption validation example (`adoption_validation_alert_triage.py`) now serves this role. |
| **No example with real LLM + custom tools** | Medium | The live validation example uses real LLM but is a validation script, not a user-facing tutorial. A simple "swap MockLLMAdapter for OpenAIAdapter" example with one tool would be valuable. |

---

## 5. Friction categorization

| # | Friction point | Category | Severity | Fixed? |
|---|---------------|----------|----------|--------|
| F1 | `MockLLMAdapter` not in top-level exports | **Packaging/setup** | Medium | **Yes** — added to `__init__.py` |
| F2 | `SequentialMockAdapter` not in top-level exports | **Packaging/setup** | Low | **Yes** — added to `__init__.py` |
| F3 | `OpenAIAdapter`/`AnthropicAdapter` not in top-level exports | **Packaging/setup** | Medium | **Yes** — added to `__init__.py` |
| F4 | `action_type_to_tool` mapping unexplained | **Documentation issue** | High | **Yes** — added quickstart section |
| F5 | Decomposition JSON format undocumented | **Documentation issue** | Medium | **Partially** — quickstart now mentions it; full reference deferred |
| F6 | Import paths inconsistent between docs and __init__.py | **Documentation issue** | Medium | **Yes** — quickstart updated to use top-level imports |
| F7 | No focused example with custom action mapping | **Example gap** | High | **Yes** — `adoption_validation_alert_triage.py` |
| F8 | `allow_stub` naming slightly misleading | **Naming/API ergonomics** | Low | Not fixed — low impact, clear from warning message |
| F9 | `CGToolDispatcher` name implies CG requirement | **Naming/API ergonomics** | Low | Not fixed — would require rename across codebase |
| F10 | No "swap to real LLM" focused example | **Example gap** | Medium | Not fixed — deferred to next adoption cycle |

---

## 6. Small fixes made

### Fix 1: Adapter exports in `__init__.py`
Added `MockLLMAdapter`, `SequentialMockAdapter`, `OpenAIAdapter`, `AnthropicAdapter`
to top-level imports and `__all__`.

**Justification:** Every quickstart snippet and every example needs
`MockLLMAdapter`. Requiring a submodule import for the single most
common type is unnecessary friction.

### Fix 2: Action type mapping section in QUICKSTART.md
Added "How action types map to tools" section explaining:
- Default identity mapping behavior
- When explicit mapping is needed
- How context-aware normalization works
- How MockLLMAdapter interacts with decomposition

**Justification:** This was the highest-friction concept for a new
developer. Without understanding this mapping, building anything
beyond the minimal example is blocked.

### Fix 3: Updated quickstart import paths
Changed quickstart code snippets from submodule imports
(`from agentic.agentic_framework.agent_builder import build_agent`)
to top-level imports (`from agentic.agentic_framework import build_agent, ...`).

**Justification:** Top-level imports are cleaner and now that all
commonly-used types are exported, there's no reason to teach
submodule paths first.

---

## 7. Final adoption verdict

### Is the framework ready for external technical users?

**Yes, with caveats.**

A technically strong developer can successfully build a governed agent
from the current docs and examples. The core path works:

1. Install (`pip install -e .`) — works
2. Run quickstart snippets — works (both snippets copy-paste correctly)
3. Run minimal example — works, produces clear output
4. Build a new use case with tools + approval + budget + tracing — works (9/9 checks pass)
5. Understand what happened — trace viewer provides clear visibility

### What still blocks wider adoption

| Blocker | Type | Impact |
|---------|------|--------|
| **No pip-installable package** | Packaging | External devs must clone the repo. No `pip install agentic-framework`. |
| **No "swap to real LLM" tutorial** | Documentation | The jump from mock to real adapter is undocumented beyond a one-liner in the quickstart. |
| **Decomposition prompt is opaque** | Documentation | New devs don't understand why the LLM produces certain action types. The decomposition prompt format should be documented or at least referenced. |
| **`agentic.agentic_framework` double-nesting** | Packaging | The import path is verbose. `import agentic_framework` or `import sentinel` would be cleaner. |

### Recommendation

The framework is **ready for guided adoption** — a developer with
access to the docs and one walkthrough session can build real governed
agents. It is **not yet ready for unguided cold-start adoption** —
the action_type_to_tool mapping and decomposition prompt concepts
require either documentation reading or source-code inspection that
a cold-start developer might not find.

**Top 3 actions for the next adoption cycle:**
1. Publish a pip-installable package (removes the clone-and-install barrier)
2. Write a "from mock to real LLM" tutorial (the biggest gap after the quickstart)
3. Add a one-page "concepts" doc explaining goal decomposition, action types, and tool routing

---

## Appendix: Validation evidence

### Validation example
- **File:** `examples/adoption_validation_alert_triage.py`
- **Use case:** Governed alert triage assistant
- **Tools:** `check_alerts` (read), `acknowledge_alert` (write), `escalate_alert` (write)
- **Result:** 9/9 checks passed (3 phases: read, approved write, denied write)

### Quickstart verification
- Snippet 1 (stub agent): `Status: completed, Events: 16, Tokens: 5`
- Snippet 2 (governed agent): `Status: completed, Actions: 1, Safety: passed`
- `minimal_governed_agent.py`: 18 events, 1 action, completed

### Import verification
- Top-level imports verified for: `build_agent`, `ToolSpec`, `ToolRiskLevel`,
  `MockLLMAdapter`, `SequentialMockAdapter`, `OpenAIAdapter`, `AnthropicAdapter`,
  `ApprovalController`, `ApprovalPolicy`, `BudgetPolicy`, `TraceCollector`,
  `format_trace`, all 17 event types
- Existing tests: 58 passed, 2 skipped (unchanged)
