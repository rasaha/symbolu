# Agentic Framework Component Deep Dive

## Status: TECHNICAL REFERENCE

**Author**: Claude (Architecture Design)
**Date**: February 2026
**Version**: 1.0.0

---

This document provides an in-depth technical exploration of each component in the Agentic LLM Framework. For each component, we cover:
- Core concepts and design rationale
- Internal algorithms and data flows
- Configuration options and tuning
- Extension points and customization
- Testing strategies
- Performance considerations

---

## Table of Contents

1. [Reflective Loop Component](#1-reflective-loop-component)
2. [Memory Store Component](#2-memory-store-component)
3. [Coherence Engine Component](#3-coherence-engine-component)
4. [Goal Decomposition Component](#4-goal-decomposition-component)
5. [Safety Contract Component](#5-safety-contract-component)
6. [Component Integration](#6-component-integration)

---

## 1. Reflective Loop Component

### 1.1 Core Concept

The Reflective Loop implements **self-evaluation and iterative refinement** without requiring model fine-tuning. It wraps any LLM in a generate-evaluate-revise cycle.

**Key Insight**: LLMs often produce suboptimal outputs on first attempt, but can significantly improve when given feedback about what's wrong. The reflective loop automates this feedback process.

### 1.2 Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      REFLECTIVE LOOP                                │
│                                                                     │
│  ┌───────────────┐                                                  │
│  │   Generator   │────────────────────────────────────────┐        │
│  │   (LLM API)   │                                        │        │
│  └───────┬───────┘                                        │        │
│          │ response                                       │        │
│          ▼                                                │        │
│  ┌───────────────┐                                        │        │
│  │    Critic     │                                        │        │
│  │  (Quality     │                                        │        │
│  │   Estimator)  │                                        │        │
│  └───────┬───────┘                                        │        │
│          │ QualityCritique                                │        │
│          ▼                                                │        │
│  ┌───────────────┐     quality >= θ_high                  │        │
│  │   Decision    │─────────────────────────────────▶ OUTPUT       │
│  │     Gate      │                                        │        │
│  └───────┬───────┘                                        │        │
│          │ quality < θ_high AND revisions < max           │        │
│          ▼                                                │        │
│  ┌───────────────┐                                        │        │
│  │   Revision    │                                        │        │
│  │   Encoder     │────────────────────────────────────────┘        │
│  │               │          revision_context                        │
│  └───────────────┘                                                  │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.3 Quality Critic Deep Dive

The Critic is the heart of the reflective loop. It evaluates responses across multiple dimensions:

#### Dimension Scores

| Dimension | What It Measures | Computation Method |
|-----------|------------------|-------------------|
| **Coherence** | Logical consistency, structure | Check for contradictions, flow |
| **Correctness** | Factual accuracy | Fact-checking heuristics |
| **Completeness** | Addresses full request | Coverage of keywords/topics |
| **Relevance** | On-topic, focused | Similarity to goal |

#### Critic Implementations

**1. Rule-Based Critic** (`RuleBasedCritic`)
- **Pros**: Fast, deterministic, no API calls
- **Cons**: Limited depth of analysis
- **Use when**: Cost-sensitive, simple quality checks

```python
# Key heuristics:
- Length checks (min/max)
- Non-informative phrase detection
- Keyword coverage vs goal
- Repetition detection
- Formatting analysis
```

**2. LLM-Based Critic** (`LLMBasedCritic`)
- **Pros**: Deep analysis, catches subtle issues
- **Cons**: Slower, additional API cost
- **Use when**: Quality is critical, budget allows

```python
# Uses prompt to ask LLM to evaluate:
- Rate each dimension 0.0-1.0
- List specific issues found
- Suggest improvements
```

**3. Hybrid Critic** (`HybridCritic`)
- **Pros**: Best of both worlds
- **Cons**: More complex setup
- **Use when**: Balanced performance needed

```python
# Strategy:
1. Run rule-based first (fast)
2. If score < threshold, run LLM-based (thorough)
3. Combine insights from both
```

### 1.4 Decision Gate Logic

```python
def decision_gate(quality_score, revision_count, thresholds):
    """
    Decision matrix:

    | Quality      | Revisions  | Action      |
    |--------------|------------|-------------|
    | >= θ_high    | any        | OUTPUT      |
    | >= θ_low     | < max      | MINOR_REVISE|
    | < θ_low      | < max      | MAJOR_REVISE|
    | any          | >= max     | OUTPUT      |
    """
    if quality_score >= thresholds.high:
        return "OUTPUT"
    if revision_count >= thresholds.max_revisions:
        return "OUTPUT"  # with uncertainty flag
    if quality_score >= thresholds.low:
        return "MINOR_REVISE"
    return "MAJOR_REVISE"
```

### 1.5 Revision Prompt Construction

The revision prompt is critical for improvement:

```python
revision_prompt = f"""
Your previous response needs improvement.

Original request: {original_prompt}

Your previous response:
{previous_response}

Quality score: {quality:.2f}

Issues identified:
{formatted_issues}

Suggestions for improvement:
{formatted_suggestions}

Please provide an improved response that addresses these issues.
Focus on: coherence ({coherence:.2f}), correctness ({correctness:.2f}),
completeness ({completeness:.2f}), and relevance ({relevance:.2f}).
"""
```

**Key elements**:
- Original context (what user asked)
- Previous attempt (what you said)
- Specific issues (what's wrong)
- Concrete suggestions (how to fix)
- Dimension scores (where to focus)

### 1.6 Tuning Guidelines

| Parameter | Default | Low Value Effect | High Value Effect |
|-----------|---------|-----------------|-------------------|
| `threshold_high` | 0.85 | More revisions | Accepts more easily |
| `threshold_low` | 0.50 | Major revisions rare | More major revisions |
| `max_revisions` | 3 | Faster but lower quality | Higher quality but slower |

**Recommended configurations**:

```python
# Speed-first (low latency)
ReflectiveGenerator(threshold_high=0.70, max_revisions=1)

# Quality-first (best output)
ReflectiveGenerator(threshold_high=0.90, max_revisions=5)

# Balanced (default)
ReflectiveGenerator(threshold_high=0.85, max_revisions=3)
```

### 1.7 Extension Points

1. **Custom Critics**: Implement `QualityCritic` abstract class
2. **Domain-Specific Evaluation**: Add checks for your domain
3. **Revision Strategies**: Override `_build_revision_prompt`
4. **Quality Dimensions**: Add new scoring dimensions

---

## 2. Memory Store Component

### 2.1 Core Concept

The Memory Store maintains **persistent conversation state external to the LLM's context window**. This enables:
- Long conversations without context overflow
- Semantic retrieval of relevant history
- Session continuity across interactions

**Key Insight**: LLMs have finite context windows. By storing and selectively retrieving history, we can maintain coherent conversations of unlimited length.

### 2.2 Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        MEMORY STORE                                 │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    AgentMemory                               │   │
│  │  ┌───────────────────────────────────────────────────────┐  │   │
│  │  │  history: List[TurnSnapshot]  (append-only)           │  │   │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │  │   │
│  │  │  │  Turn 0  │ │  Turn 1  │ │  Turn 2  │ │  Turn N  │  │  │   │
│  │  │  │ input    │ │ input    │ │ input    │ │ input    │  │  │   │
│  │  │  │ output   │ │ output   │ │ output   │ │ output   │  │  │   │
│  │  │  │ metrics  │ │ metrics  │ │ metrics  │ │ metrics  │  │  │   │
│  │  │  │ embedding│ │ embedding│ │ embedding│ │ embedding│  │  │   │
│  │  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │  │   │
│  │  └───────────────────────────────────────────────────────┘  │   │
│  │                                                              │   │
│  │  ┌───────────────────────────────────────────────────────┐  │   │
│  │  │  embedding_cache: Dict[turn_id -> embedding]          │  │   │
│  │  └───────────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    MemoryStore                               │   │
│  │                                                              │   │
│  │  append_turn()     → Add new turn (immutable pattern)       │   │
│  │  get_relevant()    → Semantic retrieval (embedding-based)   │   │
│  │  get_summary()     → Compressed summary for LLM injection   │   │
│  │  search_keyword()  → Keyword-based search                   │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.3 TurnSnapshot Data Model

```python
@dataclass
class TurnSnapshot:
    # Identifiers
    turn_id: int
    timestamp: datetime

    # Content
    user_input: str
    assistant_output: str

    # Context
    goal_state: Optional[GoalState]
    actions_taken: List[ActionItem]

    # Quality
    quality_score: float
    revision_count: int

    # Coherence (computed externally)
    coherence_metrics: Dict[str, float]

    # Retrieval
    embedding: Optional[List[float]]
```

### 2.4 Append-Only Semantics

**Critical Invariant**: Memory is never mutated in place.

```python
def append_turn(memory: AgentMemory, turn: TurnSnapshot) -> AgentMemory:
    """
    Creates NEW AgentMemory with turn appended.
    NEVER modifies the input memory object.

    This pattern:
    - Enables time-travel debugging
    - Prevents accidental corruption
    - Supports functional programming style
    """
    new_history = list(memory.history)  # Copy
    new_history.append(turn)

    # Sliding window
    if len(new_history) > memory.window_size:
        new_history = new_history[-memory.window_size:]

    return AgentMemory(
        session_id=memory.session_id,
        history=new_history,
        # ... other fields
    )
```

### 2.5 Semantic Retrieval Algorithm

```python
def get_relevant_context(memory, query, k=5):
    """
    Retrieve k most relevant turns for query.

    Algorithm:
    1. Embed query using embedding model
    2. Compute cosine similarity with each turn's embedding
    3. Return top-k by similarity

    Complexity: O(n) where n = history length
    """
    query_embedding = embedding_model.embed(query)

    scores = []
    for turn in memory.history:
        if turn.turn_id in memory.embedding_cache:
            emb = memory.embedding_cache[turn.turn_id]
            similarity = cosine_similarity(query_embedding, emb)
            scores.append((turn, similarity))

    scores.sort(key=lambda x: -x[1])  # Descending
    return [turn for turn, _ in scores[:k]]
```

### 2.6 Summary Generation for LLM

Instead of dumping raw history, generate a compressed summary:

```python
def get_summary_for_llm(memory, max_turns=5):
    """
    Generate context-aware summary.

    Includes:
    - Session statistics (turns, quality)
    - Coherence trend (improving/stable/degrading)
    - Recent turn summaries (truncated)
    """
    summary = f"""
Session State:
- Total turns: {len(memory.history)}
- Average quality: {memory.get_average_quality():.2f}
- Coherence trend: {compute_trend(memory)}

Recent conversation:
{format_recent_turns(memory.history[-max_turns:])}
"""
    return summary
```

### 2.7 Embedding Strategies

| Strategy | When to Use | Trade-offs |
|----------|-------------|------------|
| **OpenAI** | Best quality | API cost |
| **Local** | Privacy, cost | Lower quality |
| **None** | Simple apps | No semantic retrieval |

```python
# With OpenAI embeddings
embedder = OpenAIEmbeddingAdapter(model="text-embedding-ada-002")
memory_store = MemoryStore(embedding_model=embedder)

# Without embeddings (recency-based only)
memory_store = MemoryStore(embedding_model=None)
```

### 2.8 Performance Considerations

| Operation | Complexity | Notes |
|-----------|------------|-------|
| `append_turn` | O(1) | List append |
| `window_trim` | O(n) | List slice |
| `get_relevant` | O(n) | Linear scan |
| `embedding` | API call | ~100-500ms |

**Optimization strategies**:
1. **Lazy embedding**: Compute on-demand, cache aggressively
2. **Batch embedding**: Embed multiple turns together
3. **Index structures**: For large histories, use ANN (approximate nearest neighbor)

---

## 3. Coherence Engine Component

### 3.1 Core Concept

The Coherence Engine **tracks conversation-level metrics externally** to the LLM. It detects:
- Consistency degradation
- Goal drift
- Identity instability
- Reversal risks

**Key Insight**: LLMs don't inherently track their own coherence. External monitoring enables early intervention.

### 3.2 Metrics Deep Dive

#### Internal Consistency
**What it measures**: Is reasoning logically sound?

```python
def compute_internal_consistency(prev_state, turn):
    """
    Heuristic: Use quality score as proxy.

    Rationale: High quality responses tend to be consistent.

    Improvement ideas:
    - Check for contradictions with previous turns
    - Verify logical flow
    - Semantic similarity analysis
    """
    quality = turn.quality_score
    return min(1.0, quality + 0.1)
```

#### Prediction Reversal Risk
**What it measures**: How likely is the next turn to contradict this one?

```python
def compute_reversal_risk(prev_state, turn):
    """
    Detects patterns that predict reversals:
    - Declining consistency trend
    - High uncertainty markers
    - Topic shifting

    Algorithm:
    1. Get recent consistency scores
    2. Compute trend (slope)
    3. If declining, higher risk
    """
    if len(prev_state.internal_consistency_history) < 2:
        return 0.2  # Low default

    recent = prev_state.internal_consistency_history[-3:]
    trend = recent[-1] - recent[0]

    if trend < -0.1:  # Declining
        return min(1.0, 0.3 + abs(trend))
    return 0.2
```

#### Volatility Index
**What it measures**: How much is state changing between turns?

```python
def compute_volatility(prev_state, turn):
    """
    High volatility = unstable conversation.

    Algorithm:
    1. Get recent coherence scores
    2. Compute variance
    3. Scale to [0, 1]
    """
    recent = prev_state.overall_coherence_history[-5:]

    if len(recent) < 2:
        return 0.1

    mean = sum(recent) / len(recent)
    variance = sum((x - mean) ** 2 for x in recent) / len(recent)

    return min(1.0, variance * 5)  # Scale factor
```

#### Goal Alignment
**What it measures**: Does response serve the stated goal?

```python
def compute_goal_alignment(turn, goal_state):
    """
    Simple but effective: keyword overlap.

    More sophisticated options:
    - Semantic similarity (embeddings)
    - Intent matching
    - Task completion detection
    """
    if goal_state is None:
        return 0.7  # Default

    goal_words = set(goal_state.purpose.lower().split())
    response_words = set(turn.assistant_output.lower().split())

    # Filter short words
    goal_words = {w for w in goal_words if len(w) > 3}

    overlap = len(goal_words & response_words) / max(len(goal_words), 1)
    return min(1.0, overlap + 0.3)  # Add baseline
```

### 3.3 Overall Coherence Computation

```python
# Weights for weighted average
weights = {
    "internal_consistency": 0.20,
    "prediction_reversal_risk": 0.15,  # Inverted
    "volatility_index": 0.15,          # Inverted
    "goal_alignment": 0.20,
    "factual_alignment": 0.15,
    "identity_stability": 0.15,
}

overall = (
    weights["internal_consistency"] * internal_consistency +
    weights["prediction_reversal_risk"] * (1 - reversal_risk) +
    weights["volatility_index"] * (1 - volatility) +
    weights["goal_alignment"] * goal_alignment +
    weights["factual_alignment"] * factual_alignment +
    weights["identity_stability"] * identity_stability
)
```

### 3.4 Intervention Detection

```python
def should_intervene(state) -> Tuple[bool, str]:
    """
    Detect when conversation needs intervention.

    Triggers:
    - Sustained high volatility (3+ turns > 0.5)
    - Consistency degrading below 0.5
    - Reversal risk > 0.7
    - Overall coherence < 0.4
    """
    # Check volatility trend
    recent_vol = state.volatility_index_history[-3:]
    if all(v > 0.5 for v in recent_vol):
        return True, "High sustained volatility"

    # Check consistency degradation
    recent_cons = state.internal_consistency_history[-3:]
    if recent_cons[-1] < 0.5 and recent_cons[-1] < recent_cons[0]:
        return True, "Consistency degrading"

    # Check reversal risk
    if state.prediction_reversal_risk_history[-1] > 0.7:
        return True, "High reversal risk"

    # Check overall coherence
    if state.overall_coherence_history[-1] < 0.4:
        return True, "Overall coherence too low"

    return False, "Coherence stable"
```

### 3.5 State History Management

```python
class CoherenceState:
    """
    Maintains sliding window of metric histories.

    Pattern from Symbolu:
    - Append-only during turn
    - Window trim after turn
    - Never mutate in place
    """

    def window_trim(self, window: int = 10):
        """Keep only last `window` values."""
        self.internal_consistency_history = self.internal_consistency_history[-window:]
        self.prediction_reversal_risk_history = self.prediction_reversal_risk_history[-window:]
        # ... all other histories
```

---

## 4. Goal Decomposition Component

### 4.1 Core Concept

Goal Decomposition **extracts structured intent** from natural language. Maps to 12D Ontology layers:

| Layer | What it Represents | Example |
|-------|-------------------|---------|
| O8_PURPOSE | High-level goal | "Write a Python function" |
| O7_REASONING | Strategy/approach | "Use recursion for elegance" |
| O6_AGENCY | Autonomy level | "CONFIRM before executing" |
| O3_EXECUTION | Concrete actions | "generate", "validate", "execute" |

### 4.2 Decomposition Algorithm

```python
def decompose_goal(user_input: str, llm_client) -> GoalState:
    """
    Two-phase decomposition:

    Phase 1: LLM extraction (if available)
    - Use prompt to extract structured info
    - Parse JSON response

    Phase 2: Rule-based fallback
    - Pattern matching for common intents
    - Heuristic agency level detection
    """
    try:
        # LLM-based extraction
        prompt = DECOMPOSITION_PROMPT.format(user_input=user_input)
        response = llm_client.call(prompt)
        parsed = extract_json(response)
        return build_goal_state(parsed)
    except:
        # Rule-based fallback
        return decompose_goal_simple(user_input)
```

### 4.3 Agency Level Detection

```python
def detect_agency_level(user_input: str) -> str:
    """
    Heuristic agency detection:

    INFORM (just provide information):
    - Questions: "what", "who", "where", "when", "why", "how", "?"
    - Explanation requests: "explain", "describe"

    CONFIRM (propose actions, await approval):
    - Creation: "create", "write", "generate", "make", "build"
    - Modification: "update", "change", "modify", "fix"
    - Analysis: "analyze", "evaluate", "compare"

    FULL (act autonomously):
    - Simple, low-risk, clear intent
    - Explicit permission: "go ahead", "just do it"
    """
    user_lower = user_input.lower()

    # Questions → INFORM
    question_words = ["what", "who", "where", "when", "why", "how"]
    if "?" in user_input or any(w in user_lower for w in question_words):
        return "INFORM"

    # Action words → CONFIRM
    action_words = ["create", "write", "generate", "make", "build",
                    "update", "change", "modify", "fix", "analyze"]
    if any(w in user_lower for w in action_words):
        return "CONFIRM"

    # Default to CONFIRM (safe)
    return "CONFIRM"
```

### 4.4 Action Extraction

```python
def extract_actions(parsed: dict) -> List[ActionItem]:
    """
    Convert parsed actions to ActionItem objects.

    Action types:
    - "search": Find information
    - "compute": Calculate/process
    - "generate": Create content
    - "validate": Check/verify
    - "execute": Run/perform
    """
    actions = []
    for i, action_data in enumerate(parsed.get("actions", [])):
        actions.append(ActionItem(
            action_id=f"action_{i}",
            description=action_data.get("description", f"Action {i}"),
            action_type=action_data.get("type", "generate"),
            status="pending",
            parameters=action_data.get("parameters", {}),
        ))
    return actions
```

### 4.5 Complexity Estimation

```python
def estimate_complexity(user_input: str, actions: List[ActionItem]) -> float:
    """
    Estimate task complexity [0.0, 1.0].

    Factors:
    - Input length (more words = more complex)
    - Number of actions (more = more complex)
    - Action types (execute > generate > search)
    """
    # Length factor
    word_count = len(user_input.split())
    length_factor = min(1.0, word_count / 50)

    # Action factor
    action_count = len(actions)
    action_factor = min(1.0, action_count / 5)

    # Type factor
    type_weights = {"execute": 0.3, "compute": 0.2, "generate": 0.2, "validate": 0.15, "search": 0.15}
    type_factor = sum(type_weights.get(a.action_type, 0.1) for a in actions) / max(len(actions), 1)

    return (length_factor + action_factor + type_factor) / 3
```

---

## 5. Safety Contract Component

### 5.1 Core Concept

The Safety Contract implements a **fail-closed gate** before any action execution. Inspired by Phase 55 AHSC (Agent-Handoff Safety Contract).

**Key Principle**: Default deny. Explicit approval required.

### 5.2 Contract Structure

```python
@dataclass(frozen=True)  # IMMUTABLE
class SafetyContract:
    """
    Frozen dataclass ensures:
    - Cannot be modified after creation
    - Deterministic hashing
    - Thread-safe
    """
    eligible: bool = False  # FAIL-CLOSED DEFAULT

    satisfied_preconditions: Tuple[str, ...] = ()
    violated_preconditions: Tuple[str, ...] = ()
    blocking_reasons: Tuple[str, ...] = ()

    # Metrics used
    internal_consistency: float = 0.0
    goal_alignment: float = 0.0
    prediction_reversal_risk: float = 1.0  # Worst case
    identity_stability: float = 0.0

    # Forbidden capabilities (always blocked)
    forbidden_capabilities: Tuple[str, ...] = (
        "destructive_file_operations",
        "network_attacks",
        "credential_access",
        "privilege_escalation",
        "system_modification",
    )
```

### 5.3 Precondition Evaluation

```
┌──────────────────────────────────────────────────────────────────┐
│                 PRECONDITION EVALUATION                          │
│                                                                  │
│  Precondition 1: Internal Consistency >= 0.60     ✓ / ✗         │
│  Precondition 2: Goal Alignment >= 0.60           ✓ / ✗         │
│  Precondition 3: Reversal Risk <= 0.40            ✓ / ✗         │
│  Precondition 4: Identity Stability >= 0.60       ✓ / ✗         │
│  Precondition 5: No Recent Blocked States         ✓ / ✗         │
│  Precondition 6: Agency Level Permits             ✓ / ✗         │
│                                                                  │
│  ALL must pass → eligible = True                                 │
│  ANY fails → eligible = False                                    │
└──────────────────────────────────────────────────────────────────┘
```

### 5.4 Threshold Configuration

| Threshold | Default | Strict | Permissive |
|-----------|---------|--------|------------|
| `consistency_threshold` | 0.60 | 0.75 | 0.50 |
| `alignment_threshold` | 0.60 | 0.75 | 0.50 |
| `reversal_risk_threshold` | 0.40 | 0.25 | 0.50 |
| `stability_threshold` | 0.60 | 0.75 | 0.50 |

```python
# For high-security applications
evaluator = create_strict_evaluator()

# For development/testing
evaluator = create_permissive_evaluator()

# Default balanced
evaluator = create_default_evaluator()
```

### 5.5 Action Filtering

```python
def evaluate_action(contract: SafetyContract, action_type: str) -> Tuple[bool, str]:
    """
    Two-level check:
    1. Is contract eligible? (coherence metrics)
    2. Is action type allowed? (not in forbidden list)
    """
    if not contract.eligible:
        return False, f"Contract not eligible: {contract.blocking_reasons}"

    if action_type in contract.forbidden_capabilities:
        return False, f"Action type '{action_type}' is forbidden"

    return True, "Action allowed"
```

### 5.6 Safety Gate Pattern

```python
class SafetyGate:
    """
    High-level safety orchestration.

    Tracks blocked state history for "no recent blocked" check.
    """

    def __init__(self, evaluator=None):
        self.evaluator = evaluator or SafetyContractEvaluator()
        self._recent_blocked = False
        self._blocked_count = 0

    def check(self, coherence_state, goal_state, action_types):
        # Evaluate contract
        contract = self.evaluator.evaluate(
            coherence_state=coherence_state,
            goal_state=goal_state,
            recent_blocked=self._recent_blocked,
        )

        # Update tracking
        if not contract.eligible:
            self._blocked_count += 1
            self._recent_blocked = True
        else:
            self._blocked_count = 0
            self._recent_blocked = False

        # Filter actions
        allowed = [a for a in action_types if not contract.is_action_forbidden(a)]

        return contract, allowed
```

---

## 6. Component Integration

### 6.1 Full Pipeline Flow

```
User Input
    │
    ▼
┌───────────────────┐
│ Goal Decomposition│ ─── Purpose, Reasoning, Agency, Actions
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│   Memory Store    │ ─── Retrieve relevant context
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Reflective Loop   │ ─── Generate → Evaluate → Revise
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Coherence Engine  │ ─── Track metrics, detect degradation
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  Safety Contract  │ ─── Evaluate preconditions, gate actions
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Action Execution  │ ─── Execute allowed actions
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Memory Persist    │ ─── Append turn to history
└─────────┬─────────┘
          │
          ▼
    Response
```

### 6.2 Data Flow

```
GoalState
    │
    ├──▶ ReflectiveGenerator.generate(goal_state=...)
    │
    ├──▶ CoherenceEngine.update(goal_state=...)
    │
    └──▶ SafetyContractEvaluator.evaluate(goal_state=...)

TurnSnapshot
    │
    ├──▶ CoherenceEngine.update(turn=...)
    │
    └──▶ MemoryStore.append_turn(turn=...)

CoherenceState
    │
    └──▶ SafetyContractEvaluator.evaluate(coherence_state=...)
```

### 6.3 Error Handling

```python
class AgenticLLMWrapper:
    def run(self, user_input: str) -> AgentResult:
        try:
            # ... normal flow
        except LLMError as e:
            # LLM API failure
            return self._handle_llm_error(e)
        except EmbeddingError as e:
            # Embedding failure - continue without retrieval
            context = ""
        except SafetyViolation as e:
            # Safety contract denied
            return self._handle_safety_block(e)
        except Exception as e:
            # Unexpected error - fail safe
            return self._handle_unexpected_error(e)
```

### 6.4 Testing Strategy

| Component | Unit Test Focus | Integration Test Focus |
|-----------|-----------------|----------------------|
| Reflective Loop | Critic accuracy, revision triggers | Full generation loop |
| Memory Store | Append semantics, retrieval | Multi-turn persistence |
| Coherence Engine | Metric computation, intervention | State tracking across turns |
| Goal Decomposition | Parsing, agency detection | LLM extraction accuracy |
| Safety Contract | Precondition evaluation | Action gating |

---

## Summary

The Agentic LLM Framework provides a modular, extensible architecture for building agentic systems on top of existing LLMs. Key design decisions:

1. **LLM as Black Box**: The framework wraps any LLM API without modification
2. **External State**: All memory/coherence/safety state is managed externally
3. **Immutable Patterns**: Append-only memory, frozen contracts
4. **Fail-Closed Safety**: Actions require explicit approval
5. **Self-Improvement**: Reflective loop enables quality improvement without fine-tuning

Each component is designed to be:
- **Independent**: Can be used separately
- **Configurable**: Thresholds and behaviors are adjustable
- **Extensible**: Clear extension points for customization
- **Testable**: Pure functions and clear interfaces

---

**END OF DEEP DIVE DOCUMENT**
