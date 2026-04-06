# Pilot: Real-LLM Validation — Internal Copilot

Third adoption pilot for the Agentic Framework. Validates the governed
runtime against non-deterministic LLM output by running the internal
copilot through a real adapter (or a realistic mock that simulates
real LLM formatting variations).

**Script:** [`examples/pilot_internal_copilot_real_llm.py`](../../examples/pilot_internal_copilot_real_llm.py)

---

## Purpose

The first two pilots used `MockLLMAdapter` and `SequentialMockAdapter`,
which return exact, predictable strings. This pilot answers the
question: **does the governed runtime still work when the LLM output
is non-deterministic?**

Specifically:

| ID | Validation question |
|----|---------------------|
| V1 | Does goal decomposition parse reliably from real LLM output? |
| V2 | Do parsed action types land in the `action_type_to_tool` mapping? |
| V3 | Does the approval gate fire for write/execute actions? |
| V4 | Does tool dispatch succeed through the full MCP path? |
| V5 | Does usage accounting work with real adapter responses? |
| V6 | Does the trace capture everything end-to-end? |

---

## Adapter modes

The pilot auto-selects the best available adapter:

| Priority | Adapter | Env var required |
|----------|---------|-----------------|
| 1 | `AnthropicAdapter` | `ANTHROPIC_API_KEY` |
| 2 | `OpenAIAdapter` | `OPENAI_API_KEY` |
| 3 | `RealisticMockAdapter` | None |

The `RealisticMockAdapter` simulates 5 formatting variations that
real LLMs produce:

| Variation | What it adds |
|-----------|-------------|
| `clean` | Raw JSON, no wrapping |
| `markdown_fenced` | Preamble + `` ```json `` code fence |
| `preamble` | "I'll analyze this…" followed by JSON |
| `trailing` | JSON followed by explanatory paragraph |
| `mixed` | Preamble + code fence + trailing commentary |

---

## Phases

| Phase | What it tests | Expected outcome |
|-------|--------------|-----------------|
| P1 (×5) | Parsing fragility — all 5 variations | All parse correctly |
| P2 | Free read path (search) | No approval, tool dispatched |
| P3 | Approved write (save_draft) | Approval triggered → approved |
| P4 | Denied write (send_update) | Approval triggered → denied |
| P5 | Denied escalation | Approval triggered → denied |

---

## Framework fragility points discovered

### FP1: Goal alignment safety gate (critical)

`CoherenceEngine._compute_goal_alignment()` uses keyword overlap
between `GoalState.purpose` and the assistant's response. If the
LLM uses different vocabulary in the generation than the
decomposition specified, `goal_alignment` drops below 0.60 and the
safety gate blocks ALL actions — even perfectly valid ones.

**Impact:** A real LLM that paraphrases (e.g., "service health"
instead of "status") could have all actions blocked.

**Recommendation:** Consider semantic similarity (embedding cosine)
instead of keyword overlap, or lower the goal_alignment threshold
for the first turn.

### FP2: Action type vocabulary mismatch (critical)

The `DECOMPOSITION_PROMPT` asks the LLM for action types from a
fixed vocabulary: `"search|compute|generate|validate|execute"`. But
the copilot's `action_type_to_tool` mapping uses domain-specific
types like `save_draft`, `send_update`, `escalate`.

A real LLM following the prompt's instructions would return
`"execute"` for a save operation — which does NOT map to the
`save_draft` tool.

**Impact:** With a real LLM, most non-search actions would fall
through to placeholder execution, bypassing MCP governance,
approval gates, and tool handlers entirely.

**Recommendation:** Either:
1. Extend the decomposition prompt vocabulary to include
   domain-specific types, or
2. Add a secondary mapping layer from prompt vocabulary to tool
   names (e.g., `"execute" + keywords → "save_draft"`).

### FP3: `_extract_json()` greedy regex

The regex `r"\{[\s\S]*\}"` uses greedy matching. It works for all
5 tested formatting variations, but could fail if the LLM produces
multiple JSON objects in one response (the regex would capture
everything from the first `{` to the last `}`).

**Impact:** Low risk with current LLMs, but fragile for edge cases.

**Recommendation:** Consider matching the _first_ complete JSON
object (balanced braces) rather than the largest span.

### FP4: Real adapters don't implement `get_last_usage()`

`AnthropicAdapter`, `OpenAIAdapter`, and `MistralAdapter` all
inherit the base `get_last_usage()` which returns `None`. Token
and cost accounting falls back to character-length estimation.

**Impact:** Budget enforcement uses estimated values, not actual
API-reported usage. Production budget caps may be inaccurate.

**Recommendation:** Override `get_last_usage()` in each real
adapter to return the usage data from the API response.

---

## Results

With `RealisticMockAdapter` (no API key):

```
  Results: 54/54 checks passed
```

All 5 formatting variations parse correctly. Approval gates fire
for write actions. Tool dispatch works through the full MCP path.
Traces capture all events.

---

## Running

```bash
# No API key needed (realistic mock mode)
python examples/pilot_internal_copilot_real_llm.py

# With real LLM
ANTHROPIC_API_KEY=sk-ant-... python examples/pilot_internal_copilot_real_llm.py
```

---

## See also

- [Pilot: Internal Copilot](PILOT_INTERNAL_COPILOT.md) — base pilot
  (mock adapters)
- [Pilot: Research Assistant](PILOT_RESEARCH_ASSISTANT.md) — first
  pilot
- [Framework Status](FRAMEWORK_STATUS.md) — what is proved
- [Quickstart](QUICKSTART.md) — two approval layers
