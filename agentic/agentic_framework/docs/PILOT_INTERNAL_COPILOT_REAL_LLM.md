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

## Framework fragility points discovered

### FP1: Goal alignment safety gate — RESOLVED

`CoherenceEngine._compute_goal_alignment()` previously used naive
keyword overlap between `GoalState.purpose` and the response.
Paraphrased but semantically aligned responses fell below the 0.60
threshold, blocking all actions.

**Fix applied:**
- Normalized/stemmed tokens (strips punctuation, splits hyphens,
  lightweight suffix stripping) for better paraphrase matching
- User's original input words included as goal vocabulary
- Purpose overlap and user-input overlap computed separately;
  the stronger signal wins
- Baseline raised from 0.3 → 0.4 (zero overlap still fails)
- 38 new tests validate the fix

### FP2: Action type vocabulary mismatch — RESOLVED

The `DECOMPOSITION_PROMPT` asks for generic types (`search`,
`compute`, `generate`, `validate`, `execute`), but domain tools
use types like `save_draft`, `send_update`, `escalate`.

**Fix applied:**
- `normalize_action_type()` added to `goal_decomposition.py`
- Uses the developer's `action_type_to_tool` dict as an alias
  table — e.g. `{"execute": "save_draft"}` remaps generic to domain
- `ActionItem.original_action_type` records the pre-normalization
  type for traceability
- Unmapped action types get explicit error messages in traces
- Phase 6 validates "execute" → "save_draft" end-to-end

### FP3: `_extract_json()` greedy regex — DEFERRED

The regex `r"\{[\s\S]*\}"` uses greedy matching. It works for all
5 tested formatting variations, but could fail with multiple JSON
objects. Low risk; deferred.

### FP4: Real adapters don't implement `get_last_usage()` — DEFERRED

Real adapters return `None`, so budget accounting uses estimated
values. Medium risk; deferred until live API validation.

---

## Phases

| Phase | What it tests | Expected outcome |
|-------|--------------|-----------------|
| P1 (×5) | Parsing fragility — all 5 variations | All parse correctly |
| P2 | Free read path (search) | No approval, tool dispatched |
| P3 | Approved write (save_draft) | Approval triggered → approved |
| P4 | Denied write (send_update) | Approval triggered → denied |
| P5 | Denied escalation | Approval triggered → denied |
| P6 | Normalization (execute → save_draft) | Generic type remapped, approval triggered → approved |

## Results

With `RealisticMockAdapter` (no API key), after hardening pass:

```
  Results: 60/60 checks passed
```

All 5 formatting variations parse correctly. Approval gates fire
for write actions. Tool dispatch works through the full MCP path.
Action type normalization remaps generic "execute" → "save_draft"
correctly. Traces capture all events including original_action_type.

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
