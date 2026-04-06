# Validating AgenticLLMWrapper with MistralAdapter

**Version:** 1.0.0 | **Adapter:** `MistralAdapter` (hosted Mistral API)

This guide walks through validating every AgenticLLMWrapper feature using the
basic Mistral adapter. Each section targets one pipeline component, explains
what to look for, and provides runnable code.

---

## Prerequisites

```bash
pip install mistralai
```

You need a Mistral API key. Set it as an environment variable or pass directly:

```bash
export MISTRAL_API_KEY="your-key-here"
```

---

## Table of Contents

1. [Basic Wiring](#1-basic-wiring)
2. [Session Lifecycle](#2-session-lifecycle)
3. [Goal Decomposition](#3-goal-decomposition)
4. [Memory Store](#4-memory-store)
5. [Reflective Generation](#5-reflective-generation)
6. [Coherence Tracking](#6-coherence-tracking)
7. [Safety Contract](#7-safety-contract)
8. [Action Execution](#8-action-execution)
9. [Intervention Detection](#9-intervention-detection)
10. [Full Pipeline Validation](#10-full-pipeline-validation)
11. [Session Export and Summary](#11-session-export-and-summary)
12. [Cost-Optimized Validation with Local Critic](#12-cost-optimized-validation-with-local-critic)
13. [Factory Function Shortcut](#13-factory-function-shortcut)
14. [Troubleshooting](#14-troubleshooting)

---

## 1. Basic Wiring

Verify MistralAdapter connects to AgenticLLMWrapper and produces a response.

```python
from symbolu.agentic_framework import AgenticLLMWrapper
from symbolu.agentic_framework.llm_adapters import MistralAdapter

llm = MistralAdapter(api_key="your-key", model="mistral-large-latest")
agent = AgenticLLMWrapper(llm)

agent.new_session()
result = agent.run("What is the capital of France?")

# Validate basic wiring
assert isinstance(result.response, str), "Response must be a string"
assert len(result.response) > 0, "Response must not be empty"
assert result.session_id is not None, "Session ID must be assigned"
assert result.turn_id >= 1, "Turn ID must be at least 1"

print(f"Response: {result.response}")
print(f"Session:  {result.session_id}")
print(f"Turn:     {result.turn_id}")
```

**What to look for:**
- Non-empty response from Mistral
- Session ID is a valid UUID
- Turn ID starts at 1

---

## 2. Session Lifecycle

Validate session creation, reset, and multi-session isolation.

```python
from symbolu.agentic_framework import AgenticLLMWrapper
from symbolu.agentic_framework.llm_adapters import MistralAdapter

llm = MistralAdapter(api_key="your-key", model="mistral-large-latest")
agent = AgenticLLMWrapper(llm)

# --- Session creation ---
sid = agent.new_session("validation-session-001")
assert sid == "validation-session-001"
assert agent.session_id == "validation-session-001"
assert agent.turn_count == 0

# --- Auto-increment turns ---
agent.run("Hello")
assert agent.turn_count == 1
agent.run("How are you?")
assert agent.turn_count == 2

# --- Session reset ---
old_turns = agent.turn_count
agent.new_session("validation-session-002")
assert agent.session_id == "validation-session-002"
assert agent.turn_count == 0, "Turn count must reset on new session"

# --- Auto-session creation ---
agent2 = AgenticLLMWrapper(llm)
result = agent2.run("Test auto-session")
assert agent2.session_id is not None, "Session auto-created on first run()"

print("Session lifecycle: PASS")
```

**What to look for:**
- Custom session IDs are preserved
- Turn count increments per `run()` call
- `new_session()` resets all state
- First `run()` auto-creates session if none exists

---

## 3. Goal Decomposition

Validate that user intent is extracted into structured GoalState.

### 3a. LLM-Based Decomposition (default)

```python
from symbolu.agentic_framework import AgenticLLMWrapper
from symbolu.agentic_framework.llm_adapters import MistralAdapter

llm = MistralAdapter(api_key="your-key", model="mistral-large-latest")
agent = AgenticLLMWrapper(llm, use_llm_for_decomposition=True)

agent.new_session()
result = agent.run("Search for the latest Python release and summarize the changelog")

goal = agent.goal_state
assert goal is not None, "GoalState must be populated after run()"
assert goal.purpose_type is not None, "Purpose type must be set"
assert len(goal.actions) >= 1, "At least one action should be decomposed"

print(f"Purpose:  {goal.purpose_type}")
print(f"Agency:   {goal.agency_level}")
print(f"Actions:  {len(goal.actions)}")
for action in goal.actions:
    print(f"  - [{action.status}] {action.action_type}: {action.description}")
```

**What to look for:**
- `purpose_type` classifies the request (e.g., "task", "informational")
- `agency_level` reflects authorization needed (NONE / INFORM / CONFIRM / EXECUTE)
- Actions decompose multi-step requests into discrete items

### 3b. Simple Decomposition (fallback)

```python
agent_simple = AgenticLLMWrapper(llm, use_llm_for_decomposition=False)
agent_simple.new_session()
result = agent_simple.run("Delete the old backup files")

goal = agent_simple.goal_state
assert goal is not None
assert goal.purpose_type is not None

print(f"Simple decomposition purpose: {goal.purpose_type}")
print(f"Simple decomposition agency:  {goal.agency_level}")
```

**What to look for:**
- Rule-based extraction still produces valid GoalState
- Keywords like "delete" should elevate agency level

---

## 4. Memory Store

Validate that conversation context persists across turns and enriches prompts.

```python
from symbolu.agentic_framework import AgenticLLMWrapper
from symbolu.agentic_framework.llm_adapters import MistralAdapter

llm = MistralAdapter(api_key="your-key", model="mistral-large-latest")
agent = AgenticLLMWrapper(llm, memory_window=20)

agent.new_session()

# Turn 1: establish context
r1 = agent.run("My name is Alice and I work at Acme Corp.")
assert agent.turn_count == 1

# Turn 2: ask about prior context
r2 = agent.run("What company do I work at?")
assert agent.turn_count == 2

# Check memory state
mem = agent.memory
assert mem is not None, "Memory must be populated"
assert mem.get_turn_count() == 2, "Memory must contain both turns"

# The response should reference Acme Corp from memory context
print(f"Turn 1: {r1.response[:100]}...")
print(f"Turn 2: {r2.response[:100]}...")
print(f"Memory turns: {mem.get_turn_count()}")
```

**What to look for:**
- Turn 2 response references "Acme Corp" — memory context was injected
- `memory.get_turn_count()` matches number of `run()` calls

### 4a. Memory with Embedding Model (semantic retrieval)

```python
from symbolu.agentic_framework.llm_adapters import (
    MistralAdapter,
    OpenAIEmbeddingAdapter,
)

llm = MistralAdapter(api_key="your-key")
embedder = OpenAIEmbeddingAdapter(api_key="openai-key")  # optional

agent = AgenticLLMWrapper(llm, embedding_model=embedder)
agent.new_session()

# Build up history
agent.run("Python 3.12 introduced improvements to error messages.")
agent.run("Rust is known for memory safety without garbage collection.")
agent.run("JavaScript runs in web browsers and Node.js.")

# Semantic retrieval should find the Python turn
r = agent.run("Tell me more about Python error messages.")
print(f"Response: {r.response[:150]}...")
```

**What to look for:**
- With embeddings, the agent retrieves semantically relevant turns (not just recent ones)
- Without embeddings, the agent uses recent turns only (still works, less targeted)

---

## 5. Reflective Generation

Validate the generate-critique-revise loop with different quality thresholds.

### 5a. Default Critic (RuleBasedCritic)

```python
from symbolu.agentic_framework import AgenticLLMWrapper
from symbolu.agentic_framework.llm_adapters import MistralAdapter

llm = MistralAdapter(api_key="your-key", model="mistral-large-latest")

# Strict threshold — may trigger revisions
agent = AgenticLLMWrapper(
    llm,
    max_revisions=3,
    quality_threshold=0.95,  # very strict
)

agent.new_session()
result = agent.run("Explain quantum entanglement in one sentence.")

assert 0.0 <= result.quality_score <= 1.0, "Quality score must be in [0, 1]"
assert result.revision_count >= 0, "Revision count must be non-negative"
assert result.revision_count <= 3, "Must not exceed max_revisions"

print(f"Quality:   {result.quality_score:.3f}")
print(f"Revisions: {result.revision_count}")
print(f"Response:  {result.response[:150]}...")
```

**What to look for:**
- High `quality_threshold` (0.95) may trigger 1-3 revisions
- Quality score reflects the final (post-revision) assessment
- Revision count never exceeds `max_revisions`

### 5b. Relaxed Threshold (no revisions expected)

```python
agent_relaxed = AgenticLLMWrapper(
    llm,
    max_revisions=3,
    quality_threshold=0.10,  # very lenient
)
agent_relaxed.new_session()
result = agent_relaxed.run("What is 2 + 2?")

assert result.revision_count == 0, "Lenient threshold should not trigger revisions"
print(f"Quality: {result.quality_score:.3f}, Revisions: {result.revision_count}")
```

### 5c. Zero Revisions (disable reflective loop)

```python
agent_no_revise = AgenticLLMWrapper(llm, max_revisions=0)
agent_no_revise.new_session()
result = agent_no_revise.run("Write a haiku about the moon.")

assert result.revision_count == 0, "No revisions when max_revisions=0"
print(f"Single-shot response: {result.response}")
```

---

## 6. Coherence Tracking

Validate that coherence metrics are computed and tracked across turns.

```python
from symbolu.agentic_framework import AgenticLLMWrapper
from symbolu.agentic_framework.llm_adapters import MistralAdapter

llm = MistralAdapter(api_key="your-key", model="mistral-large-latest")
agent = AgenticLLMWrapper(llm, coherence_window=10)

agent.new_session()

# Run multiple turns to build coherence history
topics = [
    "Explain how photosynthesis works.",
    "What role does chlorophyll play in photosynthesis?",
    "How does light intensity affect the rate of photosynthesis?",
    "Summarize the key steps of photosynthesis.",
]

coherence_history = []
for topic in topics:
    result = agent.run(topic)
    coherence_history.append(result.coherence)

    # Validate coherence dict structure
    assert "internal_consistency" in result.coherence
    assert "goal_alignment" in result.coherence
    assert "overall" in result.coherence
    assert "drift_direction" in result.coherence

    print(f"Turn {result.turn_id}: "
          f"consistency={result.coherence['internal_consistency']:.3f}, "
          f"alignment={result.coherence['goal_alignment']:.3f}, "
          f"overall={result.coherence['overall']:.3f}, "
          f"drift={result.coherence['drift_direction']}")

# Coherence state accessible via property
state = agent.coherence_state
assert state is not None, "CoherenceState must be populated after multi-turn"
print(f"\nFinal coherence state turn count: {state.current_turn}")
```

**What to look for:**
- Staying on-topic (photosynthesis) should maintain high coherence
- `drift_direction` should be "stable" or "improving" for consistent topics
- `internal_consistency` should remain high (>0.7) for related questions

### 6a. Coherence Degradation (topic drift)

```python
agent.new_session()

# Start on-topic, then drift
agent.run("Tell me about machine learning algorithms.")
r1 = agent.run("What is gradient descent?")  # on-topic

agent.run("What's the best recipe for chocolate cake?")  # off-topic drift
r2 = agent.run("How do I train a sourdough starter?")    # continued drift

print(f"On-topic coherence:  {r1.coherence['overall']:.3f}")
print(f"Off-topic coherence: {r2.coherence['overall']:.3f}")
```

**What to look for:**
- Coherence should decrease when topics shift dramatically
- `drift_direction` may change to "degrading"

---

## 7. Safety Contract

Validate that the safety gate blocks actions when coherence is low or conditions
are unsafe.

```python
from symbolu.agentic_framework import AgenticLLMWrapper
from symbolu.agentic_framework.llm_adapters import MistralAdapter

llm = MistralAdapter(api_key="your-key", model="mistral-large-latest")
agent = AgenticLLMWrapper(llm)

agent.new_session()

# Normal request — should not be blocked
result = agent.run("What is the speed of light?")
assert isinstance(result.actions_blocked, bool)
print(f"Actions blocked: {result.actions_blocked}")
print(f"Blocking reasons: {result.blocking_reasons}")

# Safety contract is always available
contract = result.safety_contract
assert contract is not None
print(f"Eligible: {contract.eligible}")
print(f"Satisfied: {contract.satisfied_preconditions}")
print(f"Violated:  {contract.violated_preconditions}")
```

**What to look for:**
- Simple informational queries should have `actions_blocked=False` or minimal blocking
- `safety_contract` always present with precondition details
- Blocking reasons are human-readable strings

### 7a. Safety Evaluator Variants

```python
from symbolu.agentic_framework.safety_contract import (
    create_strict_evaluator,
    create_permissive_evaluator,
    SafetyGate,
)

# Strict evaluator — higher thresholds, more blocking
strict_gate = SafetyGate(evaluator=create_strict_evaluator())
agent_strict = AgenticLLMWrapper(llm)
# You can inject a custom safety gate after construction if needed

# Permissive evaluator — lower thresholds
permissive_gate = SafetyGate(evaluator=create_permissive_evaluator())

print(f"Strict consistency threshold:    {strict_gate.evaluator.consistency_threshold}")
print(f"Permissive consistency threshold: {permissive_gate.evaluator.consistency_threshold}")
```

---

## 8. Action Execution

Validate that decomposed actions are executed when safe, and blocked when not.

```python
from symbolu.agentic_framework import AgenticLLMWrapper
from symbolu.agentic_framework.llm_adapters import MistralAdapter

llm = MistralAdapter(api_key="your-key", model="mistral-large-latest")
agent = AgenticLLMWrapper(llm, use_llm_for_decomposition=True)

agent.new_session()
result = agent.run("Search for recent news about AI safety and summarize the findings.")

# Check if any actions were decomposed and executed
print(f"Actions executed: {result.actions_executed}")
print(f"Actions blocked:  {result.actions_blocked}")

if result.actions_executed:
    for action_desc in result.actions_executed:
        print(f"  Executed: {action_desc}")
else:
    print("  No actions executed (may be informational-only goal)")

# Inspect goal state for action details
goal = agent.goal_state
if goal and goal.actions:
    for action in goal.actions:
        print(f"  Action: {action.action_type} | "
              f"Status: {action.status} | "
              f"Desc: {action.description}")
```

**What to look for:**
- Action types: "generate", "search", "compute", "validate"
- Actions only execute when `safety_contract.eligible == True`
- Blocked actions appear in `blocking_reasons`

---

## 9. Intervention Detection

Validate that the framework detects when conversation quality degrades enough
to recommend intervention.

```python
from symbolu.agentic_framework import AgenticLLMWrapper
from symbolu.agentic_framework.llm_adapters import MistralAdapter

llm = MistralAdapter(api_key="your-key", model="mistral-large-latest")
agent = AgenticLLMWrapper(llm, coherence_window=5)

agent.new_session()

# Run several turns
for i in range(5):
    result = agent.run(f"Random topic number {i}: tell me something new.")
    print(f"Turn {result.turn_id}: "
          f"intervention_needed={result.intervention_needed}, "
          f"reason='{result.intervention_reason}'")

# Intervention fields are always present
assert isinstance(result.intervention_needed, bool)
assert isinstance(result.intervention_reason, str)
```

**What to look for:**
- `intervention_needed` becomes `True` when coherence degrades significantly
- `intervention_reason` provides a human-readable explanation
- Rapid topic changes across turns are more likely to trigger intervention

---

## 10. Full Pipeline Validation

End-to-end test exercising all components in a realistic multi-turn scenario.

```python
from symbolu.agentic_framework import AgenticLLMWrapper
from symbolu.agentic_framework.llm_adapters import MistralAdapter

llm = MistralAdapter(
    api_key="your-key",
    model="mistral-large-latest",
    max_tokens=1024,
)

agent = AgenticLLMWrapper(
    llm,
    max_revisions=2,
    quality_threshold=0.70,
    memory_window=20,
    coherence_window=10,
    use_llm_for_decomposition=True,
)

agent.new_session("full-validation-session")

conversation = [
    "I'm building a REST API in Python using FastAPI. Where should I start?",
    "How should I structure the project directory?",
    "Can you show me how to add authentication with JWT?",
    "What about rate limiting? How do I add that?",
    "Summarize everything we've discussed so far.",
]

print("=" * 70)
print("FULL PIPELINE VALIDATION")
print("=" * 70)

for user_msg in conversation:
    result = agent.run(user_msg)

    print(f"\n--- Turn {result.turn_id} ---")
    print(f"User:         {user_msg}")
    print(f"Response:     {result.response[:120]}...")
    print(f"Quality:      {result.quality_score:.3f}")
    print(f"Revisions:    {result.revision_count}")
    print(f"Coherence:    {result.coherence['overall']:.3f} "
          f"({result.coherence['drift_direction']})")
    print(f"Blocked:      {result.actions_blocked}")
    print(f"Intervention: {result.intervention_needed}")

    # Validate every field on every turn
    assert isinstance(result.response, str) and len(result.response) > 0
    assert 0.0 <= result.quality_score <= 1.0
    assert 0 <= result.revision_count <= 2
    assert "overall" in result.coherence
    assert isinstance(result.actions_blocked, bool)
    assert isinstance(result.intervention_needed, bool)
    assert result.safety_contract is not None
    assert result.session_id == "full-validation-session"

print("\n" + "=" * 70)
print("ALL ASSERTIONS PASSED")
print("=" * 70)
```

**What to look for:**
- All 5 turns complete without error
- Quality scores stay in [0, 1] range
- Coherence remains high for this focused conversation
- Revisions do not exceed `max_revisions=2`
- The final "summarize" turn demonstrates memory working (references prior context)

---

## 11. Session Export and Summary

Validate session metadata retrieval and conversation export.

```python
# (continuing from Section 10)

# --- Session summary ---
summary = agent.get_session_summary()
assert "session_id" in summary
assert "turn_count" in summary
assert "average_quality" in summary
assert "coherence_trend" in summary
assert summary["turn_count"] == 5

print(f"\nSession Summary:")
print(f"  ID:              {summary['session_id']}")
print(f"  Turns:           {summary['turn_count']}")
print(f"  Avg Quality:     {summary['average_quality']:.3f}")
print(f"  Coherence Trend: {summary['coherence_trend']}")
print(f"  Blocked Count:   {summary['blocked_count']}")

# --- Conversation export ---
history = agent.export_conversation()
assert isinstance(history, list)
assert len(history) == 5, "Export must contain all turns"

for turn in history:
    assert "user_input" in turn
    assert "assistant_output" in turn
    assert "quality_score" in turn

print(f"\nExported {len(history)} turns")
for i, turn in enumerate(history):
    print(f"  Turn {i+1}: Q={turn['quality_score']:.3f} | "
          f"{turn['user_input'][:50]}...")
```

**What to look for:**
- Summary captures aggregate metrics over the session
- Export contains every turn with user input, assistant output, and quality score
- `blocked_count` tracks how many times the safety contract denied action execution

---

## 12. Cost-Optimized Validation with Local Critic

Replace the default RuleBasedCritic with a local model for cheaper reflection.

```python
from symbolu.agentic_framework import (
    AgenticLLMWrapper,
    create_ollama_critic,
    create_cost_aware_critic,
    SelectionStrategy,
)
from symbolu.agentic_framework.llm_adapters import MistralAdapter

llm = MistralAdapter(api_key="your-key", model="mistral-large-latest")

# Option A: Ollama-based local critic
# Requires: ollama running locally with phi3:mini model
try:
    local_critic = create_ollama_critic(model="phi3:mini")
    agent = AgenticLLMWrapper(llm, critic=local_critic)
    print("Using Ollama local critic")
except Exception:
    print("Ollama not available, using default RuleBasedCritic")
    agent = AgenticLLMWrapper(llm)

# Option B: Cost-aware critic selector (auto-routes by complexity)
# smart_critic = create_cost_aware_critic(
#     local_model="phi3:mini",
#     strategy=SelectionStrategy(
#         max_cost_per_eval=0.005,
#         complexity_threshold_api=0.8,
#     ),
# )
# agent = AgenticLLMWrapper(llm, critic=smart_critic)

agent.new_session()
result = agent.run("Explain the difference between TCP and UDP.")
print(f"Quality: {result.quality_score:.3f}, Revisions: {result.revision_count}")
```

---

## 13. Factory Function Shortcut

Use `create_adapter` for quick setup.

```python
from symbolu.agentic_framework import AgenticLLMWrapper
from symbolu.agentic_framework.llm_adapters import create_adapter

# Factory creates the right adapter by provider name
llm = create_adapter("mistral", api_key="your-key", model="mistral-large-latest")
agent = AgenticLLMWrapper(llm)

agent.new_session()
result = agent.run("Hello from the factory!")
print(result.response)
```

---

## 14. Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ImportError: mistralai package required` | Missing dependency | `pip install mistralai` |
| `401 Unauthorized` | Invalid API key | Check `MISTRAL_API_KEY` env var |
| `quality_score` always 1.0 | RuleBasedCritic is lenient for long responses | Lower `quality_threshold` or use LLM-based critic |
| `revision_count` always 0 | Threshold too low or responses already pass | Raise `quality_threshold` to 0.90+ to force revisions |
| `actions_blocked` always True | Safety contract thresholds too strict | Use `create_permissive_evaluator()` for testing |
| `coherence['overall']` always same | Single turn or very similar turns | Run 4+ varied turns to observe coherence dynamics |
| `intervention_needed` never True | Conversation is healthy | Deliberately inject topic drift to trigger it |
| Goal decomposition returns 0 actions | Simple query with no task component | Try task-oriented prompts ("search for...", "compute...") |
| `call_with_messages` not using chat context | Base class fallback concatenates messages | This is expected; Mistral adapter overrides with proper chat API |

---

## Validation Checklist

Use this checklist to confirm all features work end-to-end:

- [ ] **Wiring**: `MistralAdapter` connects and returns responses
- [ ] **Sessions**: Create, reset, auto-create, custom IDs
- [ ] **Goal Decomposition (LLM)**: Extracts purpose, agency level, actions
- [ ] **Goal Decomposition (Simple)**: Fallback works without LLM
- [ ] **Memory**: Context persists across turns, referenced in responses
- [ ] **Reflective Loop**: Revision count respects `max_revisions`
- [ ] **Quality Threshold**: High threshold triggers revisions, low threshold skips them
- [ ] **Coherence Metrics**: All 4 fields present (`internal_consistency`, `goal_alignment`, `overall`, `drift_direction`)
- [ ] **Coherence Tracking**: Stable for on-topic, degrades for off-topic
- [ ] **Safety Contract**: Present on every result with precondition details
- [ ] **Action Execution**: Decomposed actions execute when eligible
- [ ] **Action Blocking**: Actions blocked when safety contract denies
- [ ] **Intervention**: `intervention_needed` triggers on degradation
- [ ] **Session Summary**: Returns aggregate metrics
- [ ] **Conversation Export**: Returns all turns with metadata
- [ ] **Factory Function**: `create_adapter("mistral", ...)` works
- [ ] **AgentResult.to_dict()**: Serialization includes all fields

---

## Model Recommendations

| Mistral Model | Best For | Cost |
|---------------|----------|------|
| `mistral-large-latest` | Full validation, complex decomposition | Higher |
| `mistral-medium-latest` | Balanced quality and cost | Medium |
| `mistral-small-latest` | Quick smoke tests, high-volume runs | Lower |
| `open-mistral-nemo` | Budget testing, simple queries | Lowest |

For initial validation, `mistral-large-latest` gives the most accurate picture
of framework behavior. Switch to smaller models once you have confirmed the
pipeline works correctly.
