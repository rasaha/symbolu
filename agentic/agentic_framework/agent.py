"""
Agentic LLM Wrapper - Main Agent Implementation

Complete agentic framework wrapping any LLM API.
Orchestrates all components:
1. Goal Decomposition - Extract structured intent
2. Memory Store - Persistent context management
3. Reflective Generation - Self-revising responses
4. Coherence Engine - Track conversation coherence
5. Safety Contract - Fail-closed action gating

Usage:
    from agentic.agentic_framework import AgenticLLMWrapper
    from agentic.agentic_framework.llm_adapters import OpenAIAdapter

    llm = OpenAIAdapter(api_key="...")
    agent = AgenticLLMWrapper(llm)
    agent.new_session()

    result = agent.run("What is the capital of France?")
    print(result["response"])
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol

from agentic.agentic_framework.goal_decomposition import (
    GoalState,
    ActionItem,
    decompose_goal,
    decompose_goal_simple,
)
from agentic.agentic_framework.memory_store import (
    AgentMemory,
    TurnSnapshot,
    MemoryStore,
    create_memory,
    create_turn_snapshot,
)
from agentic.agentic_framework.reflective_loop import (
    ReflectiveGenerator,
    QualityCritic,
    RuleBasedCritic,
    GenerationResult,
)
from agentic.agentic_framework.coherence_tracker import (
    CoherenceState,
    CoherenceEngine,
    create_initial_state,
)
from agentic.agentic_framework.safety_contract import (
    SafetyContract,
    SafetyContractEvaluator,
    SafetyGate,
)


class LLMClient(Protocol):
    """Protocol for LLM client interface."""

    def call(self, prompt: str) -> str:
        """Call LLM with prompt and return response."""
        ...


class EmbeddingModel(Protocol):
    """Protocol for embedding model interface."""

    def embed(self, text: str) -> List[float]:
        """Generate embedding for text."""
        ...


@dataclass
class AgentResult:
    """
    Result from agent run.

    Contains response, quality metrics, actions, and safety contract.
    """

    # Response
    response: str
    quality_score: float
    revision_count: int

    # Actions
    actions_executed: List[str]
    actions_blocked: bool
    blocking_reasons: List[str]

    # Coherence
    coherence: Dict[str, Any]
    intervention_needed: bool
    intervention_reason: str

    # Session info
    session_id: str
    turn_id: int

    # Safety contract
    safety_contract: SafetyContract

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "response": self.response,
            "quality_score": self.quality_score,
            "revision_count": self.revision_count,
            "actions_executed": self.actions_executed,
            "actions_blocked": self.actions_blocked,
            "blocking_reasons": self.blocking_reasons,
            "coherence": self.coherence,
            "intervention_needed": self.intervention_needed,
            "intervention_reason": self.intervention_reason,
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "safety_contract": self.safety_contract.to_dict(),
        }


class AgenticLLMWrapper:
    """
    Complete agentic framework wrapping any LLM API.

    Components:
    1. Goal Decomposition - Extract structured intent
    2. Memory Store - Persistent context management
    3. Reflective Generation - Self-revising responses
    4. Coherence Engine - Track conversation coherence
    5. Safety Contract - Fail-closed action gating

    All components work together to create an agentic system
    with persistent memory, self-revision, and safety gating.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        embedding_model: Optional[EmbeddingModel] = None,
        critic: Optional[QualityCritic] = None,
        max_revisions: int = 3,
        quality_threshold: float = 0.85,
        memory_window: int = 20,
        coherence_window: int = 10,
        use_llm_for_decomposition: bool = True,
    ):
        """
        Initialize agentic wrapper.

        Args:
            llm_client: LLM client implementing call() method
            embedding_model: Optional embedding model for memory retrieval
            critic: Quality critic (defaults to RuleBasedCritic)
            max_revisions: Maximum revision attempts
            quality_threshold: Quality threshold for acceptance
            memory_window: Memory sliding window size
            coherence_window: Coherence history window size
            use_llm_for_decomposition: Whether to use LLM for goal decomposition
        """
        # LLM client (black-box)
        self.llm = llm_client
        self.use_llm_for_decomposition = use_llm_for_decomposition

        # Components
        self.memory_store = MemoryStore(embedding_model)
        self.generator = ReflectiveGenerator(
            llm_client=llm_client,
            critic=critic or RuleBasedCritic(),
            threshold_high=quality_threshold,
            max_revisions=max_revisions,
        )
        self.coherence_engine = CoherenceEngine(window=coherence_window)
        self.safety_gate = SafetyGate()

        # Configuration
        self.memory_window = memory_window

        # State (mutable)
        self._memory: Optional[AgentMemory] = None
        self._coherence_state: Optional[CoherenceState] = None
        self._goal_state: Optional[GoalState] = None

    def new_session(self, session_id: Optional[str] = None) -> str:
        """
        Initialize new session.

        Resets all state for a fresh conversation.

        Args:
            session_id: Optional session ID (generated if not provided)

        Returns:
            Session ID
        """
        session_id = session_id or str(uuid.uuid4())

        self._memory = create_memory(
            session_id=session_id,
            window_size=self.memory_window,
        )
        self._coherence_state = create_initial_state(session_id)
        self._goal_state = None
        self.safety_gate.reset()

        return session_id

    def run(self, user_input: str) -> AgentResult:
        """
        Process user input through full agentic pipeline.

        Pipeline:
        1. Goal Decomposition
        2. Memory Enrichment
        3. Reflective Generation
        4. Coherence Tracking
        5. Safety Contract Evaluation
        6. Action Execution (if eligible)
        7. Memory Persistence

        Args:
            user_input: User's input text

        Returns:
            AgentResult with response, metrics, and actions
        """
        # Ensure session exists
        if self._memory is None:
            self.new_session()

        turn_id = self._memory.get_turn_count()

        # 1. Goal Decomposition
        self._goal_state = self._decompose_goal(user_input)

        # 2. Memory Enrichment
        context = self._build_context(user_input)

        # 3. Reflective Generation
        generation_result = self.generator.generate(
            prompt=user_input,
            context=context,
            goal_state=self._goal_state,
        )

        # 4. Create turn snapshot
        turn = create_turn_snapshot(
            turn_id=turn_id,
            user_input=user_input,
            assistant_output=generation_result.final_output,
            quality_score=generation_result.quality_score,
            revision_count=generation_result.revision_count,
        )

        # 5. Update Coherence
        self._coherence_state = self.coherence_engine.update(
            prev_state=self._coherence_state,
            turn=turn,
            goal_state=self._goal_state,
        )

        # Update turn with coherence metrics
        turn = TurnSnapshot(
            turn_id=turn.turn_id,
            timestamp=turn.timestamp,
            user_input=turn.user_input,
            assistant_output=turn.assistant_output,
            goal_state=self._goal_state,
            actions_taken=[],
            quality_score=turn.quality_score,
            revision_count=turn.revision_count,
            coherence_metrics={
                "internal_consistency": self._coherence_state.current_metrics.internal_consistency,
                "goal_alignment": self._coherence_state.current_metrics.goal_alignment,
                "overall_coherence": self._coherence_state.current_metrics.overall_coherence,
            },
        )

        # 6. Safety Contract Evaluation
        action_types = [a.action_type for a in self._goal_state.actions] if self._goal_state else []
        contract, allowed_actions = self.safety_gate.check(
            coherence_state=self._coherence_state,
            goal_state=self._goal_state,
            action_types=action_types,
        )

        # 7. Execute actions if eligible
        actions_executed: List[str] = []
        if contract.eligible and self._goal_state:
            actions_executed = self._execute_actions(
                self._goal_state.actions,
                allowed_actions,
            )
            # Update turn with executed actions
            executed_items = [a for a in self._goal_state.actions if a.status == "completed"]
            turn = TurnSnapshot(
                turn_id=turn.turn_id,
                timestamp=turn.timestamp,
                user_input=turn.user_input,
                assistant_output=turn.assistant_output,
                goal_state=turn.goal_state,
                actions_taken=executed_items,
                quality_score=turn.quality_score,
                revision_count=turn.revision_count,
                coherence_metrics=turn.coherence_metrics,
            )

        # 8. Update Memory
        self._memory = self.memory_store.append_turn(self._memory, turn)

        # 9. Check for intervention needs
        should_intervene, reason = self.coherence_engine.should_intervene(
            self._coherence_state
        )

        return AgentResult(
            response=generation_result.final_output,
            quality_score=generation_result.quality_score,
            revision_count=generation_result.revision_count,
            actions_executed=actions_executed,
            actions_blocked=not contract.eligible,
            blocking_reasons=list(contract.blocking_reasons),
            coherence={
                "internal_consistency": self._coherence_state.current_metrics.internal_consistency,
                "goal_alignment": self._coherence_state.current_metrics.goal_alignment,
                "overall": self._coherence_state.current_metrics.overall_coherence,
                "drift_direction": self._coherence_state.current_metrics.drift_direction,
            },
            intervention_needed=should_intervene,
            intervention_reason=reason,
            session_id=self._memory.session_id,
            turn_id=turn_id,
            safety_contract=contract,
        )

    def run_simple(self, user_input: str) -> str:
        """
        Simple run that just returns response string.

        Convenience method for basic usage.
        """
        result = self.run(user_input)
        return result.response

    def _decompose_goal(self, user_input: str) -> GoalState:
        """Decompose user input into structured goal."""
        if self.use_llm_for_decomposition:
            try:
                return decompose_goal(user_input, self.llm)
            except Exception:
                # Fall back to simple decomposition
                return decompose_goal_simple(user_input)
        else:
            return decompose_goal_simple(user_input)

    def _build_context(self, query: str) -> str:
        """Build context from memory for LLM."""
        if self._memory is None or not self._memory.history:
            return ""

        # Get relevant past turns
        relevant = self.memory_store.get_relevant_context(
            self._memory, query, k=3
        )

        # Get session summary
        summary = self.memory_store.get_summary_for_llm(self._memory)

        # Combine
        context_parts = [summary]
        for turn in relevant:
            user_preview = turn.user_input[:100] + ("..." if len(turn.user_input) > 100 else "")
            assistant_preview = turn.assistant_output[:200] + (
                "..." if len(turn.assistant_output) > 200 else ""
            )
            context_parts.append(
                f"Previous exchange:\nUser: {user_preview}\n"
                f"Assistant: {assistant_preview}"
            )

        return "\n\n".join(context_parts)

    def _execute_actions(
        self,
        actions: List[ActionItem],
        allowed_types: List[str],
    ) -> List[str]:
        """
        Execute eligible actions.

        Filters out forbidden capabilities and executes allowed actions.
        """
        executed = []

        for action in actions:
            if action.status != "pending":
                continue

            # Check if action type is allowed
            if action.action_type not in allowed_types:
                action.status = "blocked"
                action.error = f"Action type '{action.action_type}' not allowed"
                continue

            # Execute based on action type
            try:
                if action.action_type == "generate":
                    # Already handled by main generation
                    action.status = "completed"
                    executed.append(action.description)
                elif action.action_type == "search":
                    # Placeholder for search implementation
                    action.status = "completed"
                    action.result = f"Search completed for: {action.parameters.get('query', '')}"
                    executed.append(action.description)
                elif action.action_type == "compute":
                    # Placeholder for compute implementation
                    action.status = "completed"
                    action.result = "Computation completed"
                    executed.append(action.description)
                elif action.action_type == "validate":
                    # Placeholder for validation
                    action.status = "completed"
                    action.result = "Validation passed"
                    executed.append(action.description)
                else:
                    action.status = "skipped"
                    action.error = f"Unknown action type: {action.action_type}"

            except Exception as e:
                action.status = "failed"
                action.error = str(e)

        return executed

    # --- State Access Methods ---

    @property
    def memory(self) -> Optional[AgentMemory]:
        """Get current memory state."""
        return self._memory

    @property
    def coherence_state(self) -> Optional[CoherenceState]:
        """Get current coherence state."""
        return self._coherence_state

    @property
    def goal_state(self) -> Optional[GoalState]:
        """Get current goal state."""
        return self._goal_state

    @property
    def session_id(self) -> Optional[str]:
        """Get current session ID."""
        return self._memory.session_id if self._memory else None

    @property
    def turn_count(self) -> int:
        """Get current turn count."""
        return self._memory.get_turn_count() if self._memory else 0

    def get_session_summary(self) -> Dict[str, Any]:
        """Get summary of current session."""
        if self._memory is None:
            return {"status": "no_session"}

        return {
            "session_id": self._memory.session_id,
            "turn_count": self._memory.get_turn_count(),
            "average_quality": self._memory.get_average_quality(),
            "coherence_trend": self._coherence_state.get_recent_trend() if self._coherence_state else "unknown",
            "current_coherence": (
                self._coherence_state.current_metrics.overall_coherence
                if self._coherence_state
                else 0.0
            ),
            "blocked_count": self.safety_gate.get_blocked_count(),
        }

    def export_conversation(self) -> List[Dict[str, Any]]:
        """Export full conversation history."""
        if self._memory is None:
            return []

        return [turn.to_dict() for turn in self._memory.history]
