# Agentic LLM Framework Design Document

## Status: DESIGN SPECIFICATION

**Author**: Claude (Architecture Design)
**Date**: February 2026
**Version**: 1.0.0

---

## Executive Summary

This document specifies an **Agentic Framework** that wraps existing Large Language Models (ChatGPT, Gemini, Claude, etc.) to enable autonomous agent capabilities. The framework extracts key architectural patterns from Phase-Quad, CTM+, and PCAM designs and applies them as an **orchestration layer** around black-box LLM APIs.

### Key Insight

```
Traditional LLM Usage:
  User → Prompt → LLM API → Response → User
         (stateless, single-pass, no self-evaluation)

Agentic LLM Framework:
  User → Goal Decomposer → Memory Enrichment → LLM API → Critic →
       → Decision Gate → [Revise Loop or Output] → Safety Contract → Action/Response
         (stateful, self-revising, safety-gated)
```

### Design Principles

1. **LLM-Agnostic**: Works with any LLM API (OpenAI, Anthropic, Google, etc.)
2. **External State**: All memory/coherence tracking is outside the LLM
3. **Self-Revision**: Reflective loop enables quality improvement without fine-tuning
4. **Fail-Closed Safety**: Actions require explicit safety contract approval
5. **Deterministic Gates**: All safety checks are pure Python (no LLM calls)
6. **Append-Only Memory**: History is never deleted, only trimmed by sliding window

---

## Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AGENTIC LLM FRAMEWORK                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    1. GOAL DECOMPOSITION LAYER                       │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │   │
│  │  │   Purpose    │  │   Reasoning  │  │    Agency    │               │   │
│  │  │   (O8)       │  │   (O7)       │  │    Level     │               │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘               │   │
│  │                              │                                       │   │
│  │                    Goal State + Actions                              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                 │                                           │
│                                 ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    2. MEMORY ENRICHMENT LAYER                        │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │   │
│  │  │   Session    │  │   Semantic   │  │   Summary    │               │   │
│  │  │   History    │  │   Retrieval  │  │   Injection  │               │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘               │   │
│  │                              │                                       │   │
│  │                    Enriched Context                                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                 │                                           │
│                                 ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    3. REFLECTIVE GENERATION LAYER                    │   │
│  │                                                                      │   │
│  │   ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐         │   │
│  │   │Generator│───▶│ Critic  │───▶│Decision │───▶│ Reviser │         │   │
│  │   │(LLM API)│    │(Quality)│    │  Gate   │    │(if low) │         │   │
│  │   └────┬────┘    └─────────┘    └────┬────┘    └────┬────┘         │   │
│  │        │                             │              │               │   │
│  │        └─────────────────────────────┴──────────────┘               │   │
│  │                         (Revision Loop)                              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                 │                                           │
│                                 ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    4. COHERENCE TRACKING LAYER                       │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │   │
│  │  │ Consistency  │  │   Stability  │  │    Goal      │               │   │
│  │  │   Metrics    │  │   Tracking   │  │  Alignment   │               │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘               │   │
│  │                              │                                       │   │
│  │                    Coherence State                                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                 │                                           │
│                                 ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    5. SAFETY CONTRACT LAYER                          │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │   │
│  │  │ Precondition │  │   Eligibility│  │   Action     │               │   │
│  │  │    Checks    │  │    Verdict   │  │    Gate      │               │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘               │   │
│  │                              │                                       │   │
│  │                    eligible: True/False                              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                 │                                           │
│                                 ▼                                           │
│                          [ OUTPUT / ACTION ]                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Specifications

### Component 1: Goal Decomposition Layer

**Purpose**: Extract structured goal representation from user input.

**Inspired By**: 12D Ontology (O8_PURPOSE, O7_REASONING, O6_AGENCY, O3_EXECUTION)

#### Data Model

```python
@dataclass
class GoalState:
    """Structured representation of user intent."""

    # O8_PURPOSE: High-level goal
    purpose: str
    purpose_type: str  # "informational", "task", "creative", "analysis"

    # O7_REASONING: Approach/strategy
    reasoning_strategy: str
    reasoning_steps: List[str]

    # O6_AGENCY: Autonomy level
    agency_level: str  # "FULL", "CONFIRM", "INFORM"
    requires_confirmation: bool

    # O3_EXECUTION: Concrete actions
    actions: List[ActionItem]
    dependencies: Dict[str, List[str]]  # action_id -> prerequisite action_ids

    # Metadata
    complexity_estimate: float  # 0.0-1.0
    confidence: float  # 0.0-1.0
    decomposed_at: datetime

@dataclass
class ActionItem:
    """Single executable action."""
    action_id: str
    description: str
    action_type: str  # "search", "compute", "generate", "validate", "execute"
    status: str  # "pending", "in_progress", "completed", "failed", "blocked"
    parameters: Dict[str, Any]
    result: Optional[Any] = None
    error: Optional[str] = None
```

#### Decomposition Algorithm

```
FUNCTION decompose_goal(user_input: str, llm_client) -> GoalState:

    # Step 1: Use LLM to extract structure
    decomposition_prompt = """
    Analyze this request and extract:

    1. PURPOSE: What is the high-level goal?
       - Type: informational/task/creative/analysis

    2. REASONING: What approach should be used?
       - List the logical steps to achieve the goal

    3. AGENCY: What level of autonomy is appropriate?
       - FULL: Act without confirmation (simple, low-risk)
       - CONFIRM: Propose actions, wait for approval (moderate risk)
       - INFORM: Just provide information, no actions (high risk or unclear)

    4. ACTIONS: List concrete steps to execute
       - Each action should be atomic and verifiable
       - Include dependencies between actions

    5. COMPLEXITY: Estimate complexity (0.0-1.0)

    Request: {user_input}

    Respond in JSON format.
    """

    response = llm_client.call(decomposition_prompt)
    parsed = json.loads(response)

    # Step 2: Validate and construct GoalState
    actions = [
        ActionItem(
            action_id=f"action_{i}",
            description=a["description"],
            action_type=a.get("type", "generate"),
            status="pending",
            parameters=a.get("parameters", {})
        )
        for i, a in enumerate(parsed.get("actions", []))
    ]

    return GoalState(
        purpose=parsed["purpose"],
        purpose_type=parsed.get("purpose_type", "task"),
        reasoning_strategy=parsed.get("reasoning", ""),
        reasoning_steps=parsed.get("reasoning_steps", []),
        agency_level=parsed.get("agency", "CONFIRM"),
        requires_confirmation=parsed.get("agency", "CONFIRM") != "FULL",
        actions=actions,
        dependencies=parsed.get("dependencies", {}),
        complexity_estimate=parsed.get("complexity", 0.5),
        confidence=0.8,  # Initial confidence
        decomposed_at=datetime.utcnow()
    )
```

---

### Component 2: Memory Store Layer

**Purpose**: Maintain persistent conversation state external to LLM context window.

**Inspired By**: Phase 36 Identity Resonance Memory Store (append-only, deterministic)

#### Data Model

```python
@dataclass
class TurnSnapshot:
    """Immutable snapshot of a single turn."""
    turn_id: int
    timestamp: datetime

    # Input/Output
    user_input: str
    assistant_output: str

    # Goal state
    goal_state: Optional[GoalState]
    actions_taken: List[ActionItem]

    # Quality metrics
    quality_score: float
    revision_count: int

    # Coherence metrics (computed externally)
    coherence_metrics: Dict[str, float]

    # Embedding for retrieval
    embedding: Optional[List[float]] = None

@dataclass
class AgentMemory:
    """
    Append-only memory store for agent state.

    MEMORY RULES (from Phase 36):
    - Append new TurnSnapshot per turn
    - Never delete prior snapshots
    - Never overwrite history
    - Deterministic computation only
    """

    session_id: str
    created_at: datetime

    # Append-only history
    history: List[TurnSnapshot] = field(default_factory=list)

    # Sliding window size
    window_size: int = 20

    # Embedding cache for retrieval
    embedding_cache: Dict[int, List[float]] = field(default_factory=dict)
```

#### Memory Operations

```python
class MemoryStore:
    """Operations on agent memory."""

    def __init__(self, embedding_model=None):
        self.embedding_model = embedding_model

    def append_turn(
        self,
        memory: AgentMemory,
        turn: TurnSnapshot
    ) -> AgentMemory:
        """
        Append turn to memory (creates new memory, never modifies in-place).

        INVARIANT: memory.history is never mutated
        """
        # Create new history with turn appended
        new_history = list(memory.history)
        new_history.append(turn)

        # Apply sliding window (keep most recent)
        if len(new_history) > memory.window_size:
            new_history = new_history[-memory.window_size:]

        # Compute embedding for new turn
        new_cache = dict(memory.embedding_cache)
        if self.embedding_model:
            embedding = self.embedding_model.embed(
                f"{turn.user_input} {turn.assistant_output}"
            )
            new_cache[turn.turn_id] = embedding

        # Return new memory object (immutable pattern)
        return AgentMemory(
            session_id=memory.session_id,
            created_at=memory.created_at,
            history=new_history,
            window_size=memory.window_size,
            embedding_cache=new_cache
        )

    def get_relevant_context(
        self,
        memory: AgentMemory,
        query: str,
        k: int = 5
    ) -> List[TurnSnapshot]:
        """
        Retrieve k most relevant turns for query.

        Uses cosine similarity on embeddings.
        """
        if not self.embedding_model or not memory.history:
            return memory.history[-k:]  # Fall back to recent

        query_emb = self.embedding_model.embed(query)

        # Compute similarities
        scores = []
        for turn in memory.history:
            if turn.turn_id in memory.embedding_cache:
                emb = memory.embedding_cache[turn.turn_id]
                sim = cosine_similarity(query_emb, emb)
                scores.append((turn, sim))

        # Sort by similarity, return top k
        scores.sort(key=lambda x: -x[1])
        return [turn for turn, _ in scores[:k]]

    def get_summary_for_llm(
        self,
        memory: AgentMemory,
        max_tokens: int = 500
    ) -> str:
        """
        Generate compressed summary for LLM context injection.

        Instead of raw history, returns:
        - Session statistics
        - Recent turn summaries
        - Coherence trajectory
        """
        if not memory.history:
            return "New session, no history."

        recent = memory.history[-5:]

        # Compute statistics
        total_turns = len(memory.history)
        avg_quality = sum(t.quality_score for t in memory.history) / total_turns

        # Get coherence trend
        recent_coherence = [
            t.coherence_metrics.get("internal_consistency", 0.5)
            for t in recent
        ]
        coherence_trend = "stable"
        if len(recent_coherence) >= 3:
            if recent_coherence[-1] > recent_coherence[0] + 0.1:
                coherence_trend = "improving"
            elif recent_coherence[-1] < recent_coherence[0] - 0.1:
                coherence_trend = "degrading"

        # Build summary
        summary = f"""
Session State:
- Total turns: {total_turns}
- Average quality: {avg_quality:.2f}
- Coherence trend: {coherence_trend}

Recent context:
"""
        for turn in recent:
            summary += f"- User: {turn.user_input[:50]}...\n"
            summary += f"  Response quality: {turn.quality_score:.2f}\n"

        return summary
```

---

### Component 3: Reflective Generation Layer

**Purpose**: Generate responses with self-evaluation and revision loop.

**Inspired By**: Reflective Phase-Quad Architecture (generate → critic → revise)

#### Data Model

```python
@dataclass
class QualityCritique:
    """Quality assessment from critic."""
    overall_score: float  # [0.0, 1.0]

    # Dimension scores
    coherence: float
    correctness: float
    completeness: float
    relevance: float

    # Revision guidance
    revision_needed: bool
    revision_type: str  # "none", "minor", "major"
    issues: List[str]
    suggestions: List[str]

@dataclass
class GenerationResult:
    """Result from reflective generation."""
    final_output: str
    quality_score: float

    # Revision history
    revision_count: int
    quality_trajectory: List[float]

    # Metadata
    generation_time_ms: float
    token_count: int
```

#### Reflective Loop Implementation

```python
class ReflectiveGenerator:
    """
    Generator with self-revision capability.

    Loop:
    1. Generate initial response
    2. Evaluate quality with critic
    3. If quality < threshold and revisions < max:
       - Generate revision context
       - Loop back to step 1 with revision prompt
    4. Return best response
    """

    def __init__(
        self,
        llm_client,
        critic: Optional["QualityCritic"] = None,
        threshold_high: float = 0.85,
        threshold_low: float = 0.50,
        max_revisions: int = 3
    ):
        self.llm = llm_client
        self.critic = critic or RuleBasedCritic()
        self.threshold_high = threshold_high
        self.threshold_low = threshold_low
        self.max_revisions = max_revisions

    def generate(
        self,
        prompt: str,
        context: Optional[str] = None,
        goal_state: Optional[GoalState] = None,
    ) -> GenerationResult:
        """
        Generate response with optional self-revision.
        """
        start_time = time.time()

        # Build full prompt with context
        full_prompt = self._build_prompt(prompt, context, goal_state)

        # Initial generation
        response = self.llm.call(full_prompt)

        quality_trajectory = []
        revision_count = 0
        best_response = response
        best_quality = 0.0

        for revision in range(self.max_revisions + 1):
            # Evaluate quality
            critique = self.critic.evaluate(prompt, response, goal_state)
            quality = critique.overall_score
            quality_trajectory.append(quality)

            # Track best response
            if quality > best_quality:
                best_quality = quality
                best_response = response

            # Decision gate
            if quality >= self.threshold_high:
                # Good enough, output
                break

            if revision >= self.max_revisions:
                # Max revisions reached, output best
                break

            if not critique.revision_needed:
                # Critic says no revision needed
                break

            # Generate revision
            revision_count += 1
            revision_prompt = self._build_revision_prompt(
                original_prompt=prompt,
                previous_response=response,
                critique=critique
            )
            response = self.llm.call(revision_prompt)

        generation_time = (time.time() - start_time) * 1000

        return GenerationResult(
            final_output=best_response,
            quality_score=best_quality,
            revision_count=revision_count,
            quality_trajectory=quality_trajectory,
            generation_time_ms=generation_time,
            token_count=len(best_response.split())
        )

    def _build_prompt(
        self,
        prompt: str,
        context: Optional[str],
        goal_state: Optional[GoalState]
    ) -> str:
        """Build complete prompt with context and goal."""
        parts = []

        if context:
            parts.append(f"Context from previous conversation:\n{context}\n")

        if goal_state:
            parts.append(f"""
Current goal: {goal_state.purpose}
Approach: {goal_state.reasoning_strategy}
Agency level: {goal_state.agency_level}
""")

        parts.append(f"User request: {prompt}")

        return "\n".join(parts)

    def _build_revision_prompt(
        self,
        original_prompt: str,
        previous_response: str,
        critique: QualityCritique
    ) -> str:
        """Build prompt for revision."""
        return f"""
Your previous response needs improvement.

Original request: {original_prompt}

Your previous response:
{previous_response}

Quality score: {critique.overall_score:.2f}

Issues identified:
{chr(10).join(f'- {issue}' for issue in critique.issues)}

Suggestions:
{chr(10).join(f'- {s}' for s in critique.suggestions)}

Please provide an improved response that addresses these issues.
"""


class QualityCritic:
    """
    Evaluates response quality.

    Can be:
    1. Rule-based (deterministic checks)
    2. LLM-based (use smaller model to evaluate)
    3. Hybrid (rules + LLM)
    """

    def evaluate(
        self,
        prompt: str,
        response: str,
        goal_state: Optional[GoalState] = None
    ) -> QualityCritique:
        raise NotImplementedError


class RuleBasedCritic(QualityCritic):
    """Simple rule-based critic for basic quality checks."""

    def evaluate(
        self,
        prompt: str,
        response: str,
        goal_state: Optional[GoalState] = None
    ) -> QualityCritique:
        issues = []
        suggestions = []

        # Check length
        if len(response) < 50:
            issues.append("Response too short")
            suggestions.append("Provide more detail")

        # Check for common issues
        if "I don't know" in response and len(response) < 100:
            issues.append("Non-informative response")
            suggestions.append("Try to provide partial information or alternatives")

        # Check goal alignment
        if goal_state:
            keywords = goal_state.purpose.lower().split()
            response_lower = response.lower()
            missing = [k for k in keywords if k not in response_lower and len(k) > 4]
            if len(missing) > len(keywords) // 2:
                issues.append("Response may not address the goal")
                suggestions.append(f"Consider addressing: {', '.join(missing[:3])}")

        # Compute scores
        coherence = 0.8  # Assume coherent unless detected
        correctness = 0.7 if not issues else 0.5
        completeness = min(1.0, len(response) / 500)
        relevance = 0.8 if not issues else 0.6

        overall = (coherence + correctness + completeness + relevance) / 4

        return QualityCritique(
            overall_score=overall,
            coherence=coherence,
            correctness=correctness,
            completeness=completeness,
            relevance=relevance,
            revision_needed=overall < 0.7,
            revision_type="minor" if overall > 0.5 else "major",
            issues=issues,
            suggestions=suggestions
        )


class LLMBasedCritic(QualityCritic):
    """LLM-based critic using smaller/faster model."""

    def __init__(self, llm_client):
        self.llm = llm_client

    def evaluate(
        self,
        prompt: str,
        response: str,
        goal_state: Optional[GoalState] = None
    ) -> QualityCritique:
        eval_prompt = f"""
Evaluate this response quality on a scale of 0.0 to 1.0.

User request: {prompt}

Response to evaluate:
{response}

Rate the following dimensions:
1. Coherence: Is the response logically consistent?
2. Correctness: Is the information accurate?
3. Completeness: Does it fully address the request?
4. Relevance: Is it on-topic?

Also identify any issues and suggest improvements.

Respond in JSON format:
{{
  "coherence": 0.0-1.0,
  "correctness": 0.0-1.0,
  "completeness": 0.0-1.0,
  "relevance": 0.0-1.0,
  "issues": ["issue1", "issue2"],
  "suggestions": ["suggestion1", "suggestion2"]
}}
"""
        result = self.llm.call(eval_prompt)
        parsed = json.loads(result)

        overall = (
            parsed["coherence"] +
            parsed["correctness"] +
            parsed["completeness"] +
            parsed["relevance"]
        ) / 4

        return QualityCritique(
            overall_score=overall,
            coherence=parsed["coherence"],
            correctness=parsed["correctness"],
            completeness=parsed["completeness"],
            relevance=parsed["relevance"],
            revision_needed=overall < 0.7,
            revision_type="minor" if overall > 0.5 else "major",
            issues=parsed.get("issues", []),
            suggestions=parsed.get("suggestions", [])
        )
```

---

### Component 4: Coherence Tracking Layer

**Purpose**: Track conversation-level coherence metrics externally.

**Inspired By**: Symbolu Coherence Engine (37+ metrics, sliding window)

#### Data Model

```python
@dataclass
class CoherenceMetrics:
    """Coherence metrics for a single turn."""

    # Internal consistency
    internal_consistency: float  # [0.0, 1.0] - How consistent is reasoning?

    # Stability metrics
    prediction_reversal_risk: float  # [0.0, 1.0] - Risk of contradicting self
    volatility_index: float  # [0.0, 1.0] - How much is state changing?

    # Alignment metrics
    goal_alignment: float  # [0.0, 1.0] - Does response serve the goal?
    factual_alignment: float  # [0.0, 1.0] - Is it factually grounded?

    # Identity metrics
    identity_stability: float  # [0.0, 1.0] - Is persona consistent?

    # Drift metrics
    drift_magnitude: float  # [0.0, 1.0] - How far have we drifted?
    drift_direction: str  # "stable", "improving", "degrading"

    # Aggregate
    overall_coherence: float  # Weighted combination

@dataclass
class CoherenceState:
    """
    Full coherence state with history.

    Based on Symbolu CoherenceState pattern:
    - Append-only histories
    - Sliding window trim
    - Deterministic computation
    """

    session_id: str
    current_turn: int

    # Current metrics
    current_metrics: CoherenceMetrics

    # Histories (append-only, window-trimmed)
    internal_consistency_history: List[float] = field(default_factory=list)
    prediction_reversal_risk_history: List[float] = field(default_factory=list)
    volatility_index_history: List[float] = field(default_factory=list)
    goal_alignment_history: List[float] = field(default_factory=list)
    factual_alignment_history: List[float] = field(default_factory=list)
    identity_stability_history: List[float] = field(default_factory=list)
    drift_magnitude_history: List[float] = field(default_factory=list)
    overall_coherence_history: List[float] = field(default_factory=list)

    def window_trim(self, window: int = 10):
        """Trim all histories to sliding window size."""
        self.internal_consistency_history = self.internal_consistency_history[-window:]
        self.prediction_reversal_risk_history = self.prediction_reversal_risk_history[-window:]
        self.volatility_index_history = self.volatility_index_history[-window:]
        self.goal_alignment_history = self.goal_alignment_history[-window:]
        self.factual_alignment_history = self.factual_alignment_history[-window:]
        self.identity_stability_history = self.identity_stability_history[-window:]
        self.drift_magnitude_history = self.drift_magnitude_history[-window:]
        self.overall_coherence_history = self.overall_coherence_history[-window:]
```

#### Coherence Engine

```python
class CoherenceEngine:
    """
    Tracks and computes coherence metrics across turns.

    INVARIANTS (from Symbolu):
    - Observation-only: Never modifies LLM behavior
    - Deterministic: Same inputs → same outputs
    - Append-only: History never deleted
    """

    def __init__(self, window: int = 10):
        self.window = window

    def update(
        self,
        prev_state: Optional[CoherenceState],
        turn: TurnSnapshot,
        goal_state: Optional[GoalState] = None
    ) -> CoherenceState:
        """
        Update coherence state with new turn.

        Returns new CoherenceState (never modifies prev_state).
        """
        session_id = prev_state.session_id if prev_state else str(uuid.uuid4())
        current_turn = (prev_state.current_turn + 1) if prev_state else 1

        # Compute current metrics
        metrics = self._compute_metrics(prev_state, turn, goal_state)

        # Create new state with updated histories
        new_state = CoherenceState(
            session_id=session_id,
            current_turn=current_turn,
            current_metrics=metrics
        )

        # Copy and extend histories from prev_state
        if prev_state:
            new_state.internal_consistency_history = prev_state.internal_consistency_history.copy()
            new_state.prediction_reversal_risk_history = prev_state.prediction_reversal_risk_history.copy()
            new_state.volatility_index_history = prev_state.volatility_index_history.copy()
            new_state.goal_alignment_history = prev_state.goal_alignment_history.copy()
            new_state.factual_alignment_history = prev_state.factual_alignment_history.copy()
            new_state.identity_stability_history = prev_state.identity_stability_history.copy()
            new_state.drift_magnitude_history = prev_state.drift_magnitude_history.copy()
            new_state.overall_coherence_history = prev_state.overall_coherence_history.copy()

        # Append current metrics
        new_state.internal_consistency_history.append(metrics.internal_consistency)
        new_state.prediction_reversal_risk_history.append(metrics.prediction_reversal_risk)
        new_state.volatility_index_history.append(metrics.volatility_index)
        new_state.goal_alignment_history.append(metrics.goal_alignment)
        new_state.factual_alignment_history.append(metrics.factual_alignment)
        new_state.identity_stability_history.append(metrics.identity_stability)
        new_state.drift_magnitude_history.append(metrics.drift_magnitude)
        new_state.overall_coherence_history.append(metrics.overall_coherence)

        # Apply sliding window
        new_state.window_trim(self.window)

        return new_state

    def _compute_metrics(
        self,
        prev_state: Optional[CoherenceState],
        turn: TurnSnapshot,
        goal_state: Optional[GoalState]
    ) -> CoherenceMetrics:
        """Compute coherence metrics for current turn."""

        # Internal consistency: Check for contradictions
        internal_consistency = self._compute_internal_consistency(prev_state, turn)

        # Prediction reversal risk: How likely to contradict next turn?
        prediction_reversal_risk = self._compute_reversal_risk(prev_state, turn)

        # Volatility: How much is state changing?
        volatility = self._compute_volatility(prev_state, turn)

        # Goal alignment: Does response serve the goal?
        goal_alignment = self._compute_goal_alignment(turn, goal_state)

        # Factual alignment: Placeholder (would need fact-checking)
        factual_alignment = 0.7  # Default assumption

        # Identity stability: Is response style consistent?
        identity_stability = self._compute_identity_stability(prev_state, turn)

        # Drift magnitude
        drift_magnitude = self._compute_drift(prev_state, turn)

        # Drift direction
        drift_direction = self._compute_drift_direction(prev_state)

        # Overall coherence (weighted average)
        overall = (
            0.2 * internal_consistency +
            0.15 * (1 - prediction_reversal_risk) +
            0.15 * (1 - volatility) +
            0.2 * goal_alignment +
            0.15 * factual_alignment +
            0.15 * identity_stability
        )

        return CoherenceMetrics(
            internal_consistency=internal_consistency,
            prediction_reversal_risk=prediction_reversal_risk,
            volatility_index=volatility,
            goal_alignment=goal_alignment,
            factual_alignment=factual_alignment,
            identity_stability=identity_stability,
            drift_magnitude=drift_magnitude,
            drift_direction=drift_direction,
            overall_coherence=overall
        )

    def _compute_internal_consistency(
        self,
        prev_state: Optional[CoherenceState],
        turn: TurnSnapshot
    ) -> float:
        """Check if current turn is internally consistent."""
        if not prev_state or not prev_state.overall_coherence_history:
            return 0.8  # Default for first turn

        # Simple: if quality is high, assume consistent
        return min(1.0, turn.quality_score + 0.1)

    def _compute_reversal_risk(
        self,
        prev_state: Optional[CoherenceState],
        turn: TurnSnapshot
    ) -> float:
        """Estimate risk of contradicting next turn."""
        if not prev_state or len(prev_state.internal_consistency_history) < 2:
            return 0.2  # Low default

        # If recent consistency is declining, higher reversal risk
        recent = prev_state.internal_consistency_history[-3:]
        if len(recent) >= 2:
            trend = recent[-1] - recent[0]
            if trend < -0.1:
                return min(1.0, 0.3 + abs(trend))

        return 0.2

    def _compute_volatility(
        self,
        prev_state: Optional[CoherenceState],
        turn: TurnSnapshot
    ) -> float:
        """Compute state volatility."""
        if not prev_state or len(prev_state.overall_coherence_history) < 3:
            return 0.1  # Low default

        # Variance of recent coherence scores
        recent = prev_state.overall_coherence_history[-5:]
        if len(recent) < 2:
            return 0.1

        mean = sum(recent) / len(recent)
        variance = sum((x - mean) ** 2 for x in recent) / len(recent)
        return min(1.0, variance * 5)  # Scale variance

    def _compute_goal_alignment(
        self,
        turn: TurnSnapshot,
        goal_state: Optional[GoalState]
    ) -> float:
        """Check if response serves the goal."""
        if not goal_state:
            return 0.7  # Default

        # Simple keyword overlap check
        goal_words = set(goal_state.purpose.lower().split())
        response_words = set(turn.assistant_output.lower().split())

        if not goal_words:
            return 0.7

        overlap = len(goal_words & response_words) / len(goal_words)
        return min(1.0, overlap + 0.3)  # Add baseline

    def _compute_identity_stability(
        self,
        prev_state: Optional[CoherenceState],
        turn: TurnSnapshot
    ) -> float:
        """Check if response style is consistent."""
        if not prev_state or not prev_state.identity_stability_history:
            return 0.8  # Default

        # Simple: assume stable unless volatility is high
        if prev_state.volatility_index_history:
            recent_volatility = prev_state.volatility_index_history[-1]
            return max(0.3, 1.0 - recent_volatility)

        return 0.8

    def _compute_drift(
        self,
        prev_state: Optional[CoherenceState],
        turn: TurnSnapshot
    ) -> float:
        """Compute drift from initial state."""
        if not prev_state or len(prev_state.overall_coherence_history) < 3:
            return 0.0  # No drift yet

        initial = prev_state.overall_coherence_history[0]
        current = prev_state.overall_coherence_history[-1]
        return abs(current - initial)

    def _compute_drift_direction(
        self,
        prev_state: Optional[CoherenceState]
    ) -> str:
        """Determine drift direction."""
        if not prev_state or len(prev_state.overall_coherence_history) < 3:
            return "stable"

        recent = prev_state.overall_coherence_history[-3:]
        trend = recent[-1] - recent[0]

        if trend > 0.1:
            return "improving"
        elif trend < -0.1:
            return "degrading"
        return "stable"

    def should_intervene(self, state: CoherenceState) -> Tuple[bool, str]:
        """
        Detect if conversation is degrading and needs intervention.

        Returns (should_intervene, reason)
        """
        if not state.overall_coherence_history:
            return False, "No history"

        # Check volatility trend
        if len(state.volatility_index_history) >= 3:
            recent_vol = state.volatility_index_history[-3:]
            if all(v > 0.5 for v in recent_vol):
                return True, "High sustained volatility"

        # Check consistency degradation
        if len(state.internal_consistency_history) >= 3:
            recent = state.internal_consistency_history[-3:]
            if recent[-1] < 0.5 and recent[-1] < recent[0]:
                return True, "Consistency degrading"

        # Check high reversal risk
        if state.prediction_reversal_risk_history:
            if state.prediction_reversal_risk_history[-1] > 0.7:
                return True, "High reversal risk"

        return False, "Coherence stable"
```

---

### Component 5: Safety Contract Layer

**Purpose**: Fail-closed safety gate before any action execution.

**Inspired By**: Phase 55 Agent-Handoff Safety Contract (AHSC)

#### Data Model

```python
@dataclass(frozen=True)  # Immutable
class SafetyContract:
    """
    Fail-closed safety contract for action authorization.

    CRITICAL INVARIANTS (from Phase 55):
    - Immutable: Cannot be modified after creation
    - Deterministic: Same inputs → same contract
    - Zero-LLM: Pure Python logic
    - Fail-closed: eligible defaults to False
    """

    # Eligibility verdict
    eligible: bool = False  # Fail-closed default

    # Precondition results
    satisfied_preconditions: Tuple[str, ...] = ()
    violated_preconditions: Tuple[str, ...] = ()
    blocking_reasons: Tuple[str, ...] = ()

    # Metrics used for evaluation
    internal_consistency: float = 0.0
    goal_alignment: float = 0.0
    prediction_reversal_risk: float = 1.0  # Worst case default
    identity_stability: float = 0.0

    # Metadata
    contract_version: str = "1.0.0"
    evaluation_timestamp: str = ""
    session_id: str = ""
    turn_index: int = 0

    # Prohibited capabilities (always forbidden)
    forbidden_capabilities: Tuple[str, ...] = (
        "destructive_file_operations",
        "network_attacks",
        "credential_access",
        "privilege_escalation",
        "system_modification"
    )

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        from dataclasses import asdict
        return asdict(self)
```

#### Safety Contract Evaluation

```python
class SafetyContractEvaluator:
    """
    Evaluates safety contract preconditions.

    ALL preconditions must pass for eligible=True.
    Any failure → eligible=False (fail-closed).

    PRECONDITIONS:
    1. Internal consistency >= 0.60
    2. Goal alignment >= 0.60
    3. Prediction reversal risk <= 0.40
    4. Identity stability >= 0.60
    5. No recent blocked states
    6. Agency level permits action
    """

    def __init__(
        self,
        consistency_threshold: float = 0.60,
        alignment_threshold: float = 0.60,
        reversal_risk_threshold: float = 0.40,
        stability_threshold: float = 0.60
    ):
        self.consistency_threshold = consistency_threshold
        self.alignment_threshold = alignment_threshold
        self.reversal_risk_threshold = reversal_risk_threshold
        self.stability_threshold = stability_threshold

    def evaluate(
        self,
        coherence_state: CoherenceState,
        goal_state: Optional[GoalState] = None,
        recent_blocked: bool = False
    ) -> SafetyContract:
        """
        Evaluate all preconditions and return immutable contract.

        INVARIANT: Same inputs → same contract (deterministic)
        """
        satisfied = []
        violated = []
        blocking_reasons = []

        metrics = coherence_state.current_metrics

        # Precondition 1: Internal consistency
        if metrics.internal_consistency >= self.consistency_threshold:
            satisfied.append("precondition_1_internal_consistency")
        else:
            violated.append("precondition_1_internal_consistency")
            blocking_reasons.append(
                f"internal_consistency {metrics.internal_consistency:.2f} < {self.consistency_threshold}"
            )

        # Precondition 2: Goal alignment
        if metrics.goal_alignment >= self.alignment_threshold:
            satisfied.append("precondition_2_goal_alignment")
        else:
            violated.append("precondition_2_goal_alignment")
            blocking_reasons.append(
                f"goal_alignment {metrics.goal_alignment:.2f} < {self.alignment_threshold}"
            )

        # Precondition 3: Prediction reversal risk
        if metrics.prediction_reversal_risk <= self.reversal_risk_threshold:
            satisfied.append("precondition_3_reversal_risk")
        else:
            violated.append("precondition_3_reversal_risk")
            blocking_reasons.append(
                f"reversal_risk {metrics.prediction_reversal_risk:.2f} > {self.reversal_risk_threshold}"
            )

        # Precondition 4: Identity stability
        if metrics.identity_stability >= self.stability_threshold:
            satisfied.append("precondition_4_identity_stability")
        else:
            violated.append("precondition_4_identity_stability")
            blocking_reasons.append(
                f"identity_stability {metrics.identity_stability:.2f} < {self.stability_threshold}"
            )

        # Precondition 5: No recent blocked states
        if not recent_blocked:
            satisfied.append("precondition_5_no_recent_blocked")
        else:
            violated.append("precondition_5_no_recent_blocked")
            blocking_reasons.append("recent_blocked_state")

        # Precondition 6: Agency level permits action
        if goal_state:
            if goal_state.agency_level in ("FULL", "CONFIRM"):
                satisfied.append("precondition_6_agency_permits")
            else:
                violated.append("precondition_6_agency_permits")
                blocking_reasons.append(f"agency_level={goal_state.agency_level}")
        else:
            violated.append("precondition_6_agency_permits")
            blocking_reasons.append("no_goal_state")

        # All-or-nothing decision
        eligible = len(violated) == 0

        # Sort for determinism
        satisfied = tuple(sorted(satisfied))
        violated = tuple(sorted(violated))
        blocking_reasons = tuple(sorted(blocking_reasons))

        return SafetyContract(
            eligible=eligible,
            satisfied_preconditions=satisfied,
            violated_preconditions=violated,
            blocking_reasons=blocking_reasons,
            internal_consistency=metrics.internal_consistency,
            goal_alignment=metrics.goal_alignment,
            prediction_reversal_risk=metrics.prediction_reversal_risk,
            identity_stability=metrics.identity_stability,
            evaluation_timestamp=datetime.utcnow().isoformat(),
            session_id=coherence_state.session_id,
            turn_index=coherence_state.current_turn
        )
```

---

## Complete Agent Implementation

### AgenticLLMWrapper

```python
class AgenticLLMWrapper:
    """
    Complete agentic framework wrapping any LLM API.

    Components:
    1. Goal Decomposition - Extract structured intent
    2. Memory Store - Persistent context management
    3. Reflective Generation - Self-revising responses
    4. Coherence Engine - Track conversation coherence
    5. Safety Contract - Fail-closed action gating
    """

    def __init__(
        self,
        llm_client,
        embedding_model=None,
        critic: Optional[QualityCritic] = None,
        max_revisions: int = 3,
        quality_threshold: float = 0.85,
        memory_window: int = 20,
        coherence_window: int = 10
    ):
        # LLM client (black-box)
        self.llm = llm_client

        # Components
        self.memory_store = MemoryStore(embedding_model)
        self.generator = ReflectiveGenerator(
            llm_client=llm_client,
            critic=critic or RuleBasedCritic(),
            threshold_high=quality_threshold,
            max_revisions=max_revisions
        )
        self.coherence_engine = CoherenceEngine(window=coherence_window)
        self.safety_evaluator = SafetyContractEvaluator()

        # State
        self.memory: Optional[AgentMemory] = None
        self.coherence_state: Optional[CoherenceState] = None
        self.goal_state: Optional[GoalState] = None
        self.recent_blocked: bool = False

    def new_session(self, session_id: Optional[str] = None) -> str:
        """Initialize new session."""
        session_id = session_id or str(uuid.uuid4())
        self.memory = AgentMemory(
            session_id=session_id,
            created_at=datetime.utcnow()
        )
        self.coherence_state = None
        self.goal_state = None
        self.recent_blocked = False
        return session_id

    def run(self, user_input: str) -> Dict[str, Any]:
        """
        Process user input through full agentic pipeline.

        Returns:
            Dict with response, actions, metrics, contract
        """
        if self.memory is None:
            self.new_session()

        turn_id = len(self.memory.history)

        # 1. Goal Decomposition
        self.goal_state = self._decompose_goal(user_input)

        # 2. Memory Enrichment
        context = self._build_context(user_input)

        # 3. Reflective Generation
        generation_result = self.generator.generate(
            prompt=user_input,
            context=context,
            goal_state=self.goal_state
        )

        # 4. Create turn snapshot
        turn = TurnSnapshot(
            turn_id=turn_id,
            timestamp=datetime.utcnow(),
            user_input=user_input,
            assistant_output=generation_result.final_output,
            goal_state=self.goal_state,
            actions_taken=[],
            quality_score=generation_result.quality_score,
            revision_count=generation_result.revision_count,
            coherence_metrics={}
        )

        # 5. Update Coherence
        self.coherence_state = self.coherence_engine.update(
            prev_state=self.coherence_state,
            turn=turn,
            goal_state=self.goal_state
        )

        # Update turn with coherence metrics
        turn = TurnSnapshot(
            turn_id=turn.turn_id,
            timestamp=turn.timestamp,
            user_input=turn.user_input,
            assistant_output=turn.assistant_output,
            goal_state=turn.goal_state,
            actions_taken=turn.actions_taken,
            quality_score=turn.quality_score,
            revision_count=turn.revision_count,
            coherence_metrics={
                "internal_consistency": self.coherence_state.current_metrics.internal_consistency,
                "goal_alignment": self.coherence_state.current_metrics.goal_alignment,
                "overall_coherence": self.coherence_state.current_metrics.overall_coherence,
            }
        )

        # 6. Safety Contract Evaluation
        contract = self.safety_evaluator.evaluate(
            coherence_state=self.coherence_state,
            goal_state=self.goal_state,
            recent_blocked=self.recent_blocked
        )

        # 7. Execute actions if eligible
        actions_executed = []
        if contract.eligible and self.goal_state:
            actions_executed = self._execute_actions(
                self.goal_state.actions,
                contract
            )
            turn = TurnSnapshot(
                turn_id=turn.turn_id,
                timestamp=turn.timestamp,
                user_input=turn.user_input,
                assistant_output=turn.assistant_output,
                goal_state=turn.goal_state,
                actions_taken=actions_executed,
                quality_score=turn.quality_score,
                revision_count=turn.revision_count,
                coherence_metrics=turn.coherence_metrics
            )
        else:
            self.recent_blocked = not contract.eligible

        # 8. Update Memory
        self.memory = self.memory_store.append_turn(self.memory, turn)

        # 9. Check for intervention needs
        should_intervene, reason = self.coherence_engine.should_intervene(
            self.coherence_state
        )

        return {
            "response": generation_result.final_output,
            "quality_score": generation_result.quality_score,
            "revision_count": generation_result.revision_count,
            "actions_executed": [a.description for a in actions_executed],
            "actions_blocked": not contract.eligible,
            "blocking_reasons": list(contract.blocking_reasons),
            "coherence": {
                "internal_consistency": self.coherence_state.current_metrics.internal_consistency,
                "goal_alignment": self.coherence_state.current_metrics.goal_alignment,
                "overall": self.coherence_state.current_metrics.overall_coherence,
                "drift_direction": self.coherence_state.current_metrics.drift_direction,
            },
            "intervention_needed": should_intervene,
            "intervention_reason": reason,
            "session_id": self.memory.session_id,
            "turn_id": turn_id,
        }

    def _decompose_goal(self, user_input: str) -> GoalState:
        """Decompose user input into structured goal."""
        return decompose_goal(user_input, self.llm)

    def _build_context(self, query: str) -> str:
        """Build context from memory for LLM."""
        if not self.memory or not self.memory.history:
            return ""

        # Get relevant past turns
        relevant = self.memory_store.get_relevant_context(
            self.memory, query, k=3
        )

        # Get session summary
        summary = self.memory_store.get_summary_for_llm(self.memory)

        # Combine
        context_parts = [summary]
        for turn in relevant:
            context_parts.append(
                f"Previous exchange:\nUser: {turn.user_input[:100]}...\n"
                f"Assistant: {turn.assistant_output[:200]}..."
            )

        return "\n\n".join(context_parts)

    def _execute_actions(
        self,
        actions: List[ActionItem],
        contract: SafetyContract
    ) -> List[ActionItem]:
        """
        Execute eligible actions.

        Filters out any forbidden capabilities.
        """
        executed = []

        for action in actions:
            if action.status != "pending":
                continue

            # Check if action type is forbidden
            if action.action_type in contract.forbidden_capabilities:
                action.status = "blocked"
                action.error = "Forbidden capability"
                continue

            # Execute based on action type
            try:
                if action.action_type == "generate":
                    # Already handled by main generation
                    action.status = "completed"
                elif action.action_type == "search":
                    # Placeholder for search implementation
                    action.status = "completed"
                    action.result = f"Search results for: {action.parameters.get('query', '')}"
                elif action.action_type == "compute":
                    # Placeholder for compute implementation
                    action.status = "completed"
                    action.result = "Computation completed"
                else:
                    action.status = "skipped"
                    action.error = f"Unknown action type: {action.action_type}"

                executed.append(action)

            except Exception as e:
                action.status = "failed"
                action.error = str(e)

        return executed
```

---

## Usage Examples

### Basic Usage

```python
from openai import OpenAI
from agentic_llm_framework import AgenticLLMWrapper

# Initialize with OpenAI
client = OpenAI(api_key="...")

class OpenAIAdapter:
    def __init__(self, client):
        self.client = client

    def call(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content

# Create agent
llm = OpenAIAdapter(client)
agent = AgenticLLMWrapper(llm)

# Start session
agent.new_session()

# Run conversation
result = agent.run("What is the capital of France?")
print(result["response"])
print(f"Quality: {result['quality_score']:.2f}")
print(f"Coherence: {result['coherence']['overall']:.2f}")

# Multi-turn
result2 = agent.run("What's its population?")
print(result2["response"])
print(f"Goal alignment: {result2['coherence']['goal_alignment']:.2f}")
```

### With Claude API

```python
from anthropic import Anthropic

class ClaudeAdapter:
    def __init__(self, client):
        self.client = client

    def call(self, prompt: str) -> str:
        message = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text

client = Anthropic()
llm = ClaudeAdapter(client)
agent = AgenticLLMWrapper(llm)
```

### With Gemini API

```python
import google.generativeai as genai

class GeminiAdapter:
    def __init__(self, model_name="gemini-pro"):
        self.model = genai.GenerativeModel(model_name)

    def call(self, prompt: str) -> str:
        response = self.model.generate_content(prompt)
        return response.text

genai.configure(api_key="...")
llm = GeminiAdapter()
agent = AgenticLLMWrapper(llm)
```

---

## Testing Strategy

### Unit Tests

1. **Goal Decomposition Tests**
   - Test various input types (questions, tasks, creative)
   - Test agency level detection
   - Test action extraction

2. **Memory Store Tests**
   - Test append-only semantics
   - Test sliding window trim
   - Test relevant context retrieval

3. **Reflective Loop Tests**
   - Test single-pass (high quality)
   - Test revision loop (low quality → revision)
   - Test max revisions limit

4. **Coherence Engine Tests**
   - Test metric computation
   - Test history tracking
   - Test intervention detection

5. **Safety Contract Tests**
   - Test all preconditions pass → eligible
   - Test any precondition fails → not eligible
   - Test determinism (same inputs → same contract)

### Integration Tests

1. **End-to-end conversation flow**
2. **Multi-turn coherence tracking**
3. **Action execution with safety gating**
4. **Memory persistence across turns**

---

## Metrics and Monitoring

### Key Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| Quality Score | Average generation quality | > 0.80 |
| Revision Rate | % of turns requiring revision | < 30% |
| Coherence Score | Average overall coherence | > 0.70 |
| Safety Pass Rate | % of turns passing safety | > 95% |
| Action Success Rate | % of actions completed | > 90% |

### Logging

All operations should log:
- Turn ID and timestamp
- Quality scores and revision count
- Coherence metrics
- Safety contract verdict
- Actions attempted/executed

---

## Future Extensions

1. **Tool Integration**: Add tool calling capabilities
2. **Multi-Agent**: Support multiple agent collaboration
3. **Streaming**: Stream responses for better UX
4. **Persistence**: Database-backed memory for long sessions
5. **Fine-tuning**: Use collected data to improve critic model
6. **Multimodal**: Support image/audio inputs

---

## References

- Symbolu Phase 36: Identity Resonance Memory Store
- Symbolu Phase 55: Agent-Handoff Safety Contract
- Symbolu Coherence Engine: 37+ metrics tracking
- Reflective Phase-Quad Architecture
- 12D Ontological State Representation

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | Feb 2026 | Initial design specification |

---

**END OF DESIGN DOCUMENT**
