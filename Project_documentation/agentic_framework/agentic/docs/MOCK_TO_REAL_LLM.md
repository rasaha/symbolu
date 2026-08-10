# From Mock to Real LLM

How to move a governed agent from `MockLLMAdapter` (no API key) to a
real LLM adapter (OpenAI, Anthropic) — and what changes when you do.

---

## 1. Start with the mock

Every example in this repo starts with a mock adapter so you can
validate your governance wiring without spending API credits:

```python
from agentic.agentic_framework import (
    build_agent, MockLLMAdapter, ToolSpec, ToolRiskLevel, format_trace,
)

def my_search(params):
    return {"results": [f"Result for: {params.get('query', '')}"], "count": 1}

agent = build_agent(
    adapter=MockLLMAdapter(default_response="The answer is 42."),
    tools={
        "search": ToolSpec(
            handler=my_search,
            description="Search for information",
            risk_level=ToolRiskLevel.READ_ONLY,
        ),
    },
)
agent.new_session()
trace = agent.run_with_trace("What is the meaning of life?")
print(format_trace(trace))
```

This runs instantly, with no network calls.

---

## 2. Switch to a real adapter

### Option A: OpenAI (GPT-4, GPT-4o, etc.)

**Install the SDK:**
```bash
pip install openai
```

**Set your API key** (choose one):
```bash
# Environment variable (recommended)
export OPENAI_API_KEY="sk-..."

# Or pass it directly in code
adapter = OpenAIAdapter(api_key="sk-...")
```

**Swap the adapter — nothing else changes:**
```python
from agentic.agentic_framework import (
    build_agent, OpenAIAdapter, ToolSpec, ToolRiskLevel, format_trace,
)

agent = build_agent(
    adapter=OpenAIAdapter(model="gpt-4"),  # uses OPENAI_API_KEY env var
    tools={
        "search": ToolSpec(
            handler=my_search,
            description="Search for information",
            risk_level=ToolRiskLevel.READ_ONLY,
        ),
    },
)
agent.new_session()
trace = agent.run_with_trace("What is the meaning of life?")
print(format_trace(trace))
```

### Option B: Anthropic (Claude)

**Install the SDK:**
```bash
pip install anthropic
```

**Set your API key:**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

**Swap the adapter:**
```python
from agentic.agentic_framework import (
    build_agent, AnthropicAdapter, ToolSpec, ToolRiskLevel, format_trace,
)

agent = build_agent(
    adapter=AnthropicAdapter(model="claude-sonnet-4-20250514"),
    tools={
        "search": ToolSpec(
            handler=my_search,
            description="Search for information",
            risk_level=ToolRiskLevel.READ_ONLY,
        ),
    },
)
agent.new_session()
trace = agent.run_with_trace("What is the meaning of life?")
print(format_trace(trace))
```

`AnthropicAdapter` also accepts `auth_token=` for session/OAuth
tokens as an alternative to `api_key`.

---

## 3. What stays the same

When you switch adapters, the entire governed runtime path is
unchanged:

| Feature | Mock | Real | Same? |
|---------|------|------|-------|
| Tool registration (`ToolSpec`) | Yes | Yes | Same |
| Safety gate (turn-level) | Yes | Yes | Same |
| Approval gates (`ApprovalPolicy`) | Yes | Yes | Same |
| Budget enforcement (`BudgetPolicy`) | Yes | Yes | Same |
| Streaming events (`run_stream()`) | Yes | Yes | Same |
| Tracing (`run_with_trace()`) | Yes | Yes | Same |
| Structured output (`run_structured()`) | Yes | Yes | Same |
| Tool discovery (`ToolCatalog`) | Yes | Yes | Same |

The governance pipeline treats the adapter as a black box. It only
cares about `adapter.call(prompt) -> str`.

---

## 4. What changes with a real LLM

### Token accounting mode

| Adapter | `trace.accounting_mode` | How |
|---------|------------------------|-----|
| `MockLLMAdapter` | `"estimated"` | `len(text) / 4` heuristic |
| `OpenAIAdapter` | `"exact"` | Real token counts from API response |
| `AnthropicAdapter` | `"exact"` | Real token counts from API response |

Both real adapters implement `get_last_usage()` which returns:
```python
{"input_tokens": 152, "output_tokens": 87, "model": "gpt-4"}
```

This means budget enforcement uses real token counts, not estimates.

### Goal decomposition output

`MockLLMAdapter` returns a fixed string. The goal decomposition
module either parses it as JSON (if it's valid) or falls back to
rule-based extraction (`_simple_extraction()`).

A real LLM receives the full `DECOMPOSITION_PROMPT` and produces
structured JSON with action types like `"search"`, `"execute"`,
`"generate"`, `"compute"`, or `"validate"`. These are the generic
types from the prompt vocabulary.

**This is the main behavioral difference.** With a mock, you control
exactly what actions are produced. With a real LLM, you need the
`action_type_to_tool` mapping to route generic action types to your
domain tools:

```python
agent = build_agent(
    adapter=OpenAIAdapter(model="gpt-4"),
    tools={
        "check_alerts": ToolSpec(handler=check_fn, ...),
        "save_draft": ToolSpec(handler=save_fn, ...),
    },
    action_type_to_tool={
        "check_alerts": "check_alerts",  # identity
        "save_draft": "save_draft",      # identity
        "search": "check_alerts",        # LLM generic → domain tool
        "execute": "save_draft",         # LLM generic → domain tool
        "compute": "check_alerts",       # LLM generic → domain tool
    },
)
```

The framework also has context-aware normalization: when `"execute"`
appears and the action's description mentions "send" or "escalate",
it routes to the matching domain tool automatically. See
[QUICKSTART.md](QUICKSTART.md#how-action-types-map-to-tools) for
details.

### New failure modes

| Failure | Cause | What you see |
|---------|-------|-------------|
| **API auth error** | Missing or invalid API key | `ImportError` or HTTP 401 in trace |
| **Rate limiting** | Too many requests | HTTP 429, retry needed |
| **Unexpected action types** | LLM produces action types not in your mapping | `"Unmapped action type: '...'. Add it to action_type_to_tool."` in trace |
| **JSON parse failure** | LLM output doesn't match decomposition format | Falls back to `_simple_extraction()`, produces generic `"generate"` action |
| **Quality score variance** | Real LLM quality scores fluctuate | `trace.quality_score` may differ between runs |
| **Higher latency** | Network round-trip | `run_stream()` takes seconds instead of milliseconds |

### Reflective generation behavior

With `MockLLMAdapter`, every revision returns the same fixed string,
so the quality critic may trigger max revisions. With a real LLM,
each revision is a genuine attempt to improve, so revision counts
are typically lower.

---

## 5. Recommended development workflow

1. **Build with mock** — wire up tools, approval, budget, tracing.
   Validate that the governance path works end-to-end.

2. **Test with mock JSON responses** — use `MockLLMAdapter` with a
   JSON string matching the decomposition format to test specific
   action routing:
   ```python
   import json
   response = json.dumps({
       "purpose": "Search for information",
       "purpose_type": "task",
       "reasoning_strategy": "Direct search",
       "reasoning_steps": ["Search the database"],
       "agency_level": "CONFIRM",
       "actions": [
           {"description": "Search for X", "type": "search", "parameters": {}}
       ],
       "dependencies": {},
       "complexity": 0.3,
   })
   adapter = MockLLMAdapter(default_response=response)
   ```

3. **Switch to real adapter** — set the environment variable, swap
   the adapter class, add `action_type_to_tool` if your tool names
   don't match the LLM's generic vocabulary.

4. **Verify with tracing** — run `format_trace(trace)` and check:
   - `accounting_mode` should be `"exact"`
   - Action types should be your domain types (not generic)
   - Approval/budget gates should fire as expected

---

## 6. Environment variable reference

| Adapter | Env var | Purpose |
|---------|---------|---------|
| `OpenAIAdapter` | `OPENAI_API_KEY` | API key (used if `api_key=` not passed) |
| `AnthropicAdapter` | `ANTHROPIC_API_KEY` | API key (used if `api_key=` not passed) |
| `MistralAdapter` | `MISTRAL_API_KEY` | API key |

All adapters accept the key directly as a constructor parameter.
Environment variables are a convenience for keeping secrets out of
code.

---

## See also

- [Quickstart](QUICKSTART.md) — first agent + API orientation
- [First Governed Agent](FIRST_GOVERNED_AGENT.md) — feature-by-feature build guide
- [Examples Overview](EXAMPLES_OVERVIEW.md) — all runnable examples
- [Framework Status](FRAMEWORK_STATUS.md) — what is proved and tested
