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
    print(result.response)
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional, Protocol

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
from agentic.agentic_framework.cancellation import CancellationToken
from agentic.agentic_framework.tracing import (
    AgentRunTrace,
    TraceCollector,
    _build_trace,
)
from agentic.agentic_framework.structured_output import (
    SchemaTarget,
    StructuredRunResult,
    build_schema_prompt,
    extract_json,
    schema_name as _schema_name,
    validate_and_construct,
)
from agentic.agentic_framework.approval import (
    ApprovalController,
    PendingApproval,
)
from agentic.agentic_framework.token_budget import (
    BudgetPolicy,
    UsageStats,
)
from agentic.agentic_framework.streaming_events import (
    AgentRunEvent,
    make_event,
    RUN_STARTED,
    GENERATION_STARTED,
    TEXT_CHUNK,
    GENERATION_COMPLETED,
    SAFETY_GATE_RESULT,
    ACTION_STARTED,
    ACTION_COMPLETED,
    RUN_COMPLETED,
    RUN_ERROR,
    RUN_CANCELLED,
    REVISION_STARTED,
    REVISION_COMPLETED,
    STRUCTURED_VALIDATION,
    APPROVAL_REQUESTED,
    APPROVAL_RESOLVED,
    USAGE_UPDATED,
    BUDGET_EXCEEDED,
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
        dispatcher: Optional[Any] = None,
        action_type_to_tool: Optional[Dict[str, str]] = None,
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
            dispatcher: Optional ``CGToolDispatcher`` for MCP-governed tool
                execution. When provided together with an
                ``action_type_to_tool`` entry for an action's type, that
                action is routed through MCP governance (entropy/vritti/
                confidence gating + real handler execution). When absent,
                the existing placeholder execution path is preserved
                unchanged. ``SafetyGate`` always runs first either way.
            action_type_to_tool: Optional mapping from ``ActionItem.action_type``
                strings (e.g. "search", "compute") to MCP tool names
                registered on the dispatcher's gateway. Only action types
                present in this mapping are routed through the dispatcher;
                all others fall through to placeholder execution.
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

        # Optional MCP tool dispatcher (layered BEHIND SafetyGate — see
        # docs/REQUEST_BOUNDARY_CONVENTION.md and the architecture note
        # on Inference CG Metadata <-> MCP Gateway).
        self.dispatcher = dispatcher
        self.action_type_to_tool: Dict[str, str] = dict(action_type_to_tool or {})

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

    def run_with_trace(
        self,
        user_input: str,
        cancellation_token: Optional[CancellationToken] = None,
        approval_controller: Optional[ApprovalController] = None,
        budget_policy: Optional[BudgetPolicy] = None,
    ) -> AgentRunTrace:
        """
        One-shot helper: run the full pipeline and return a complete
        ``AgentRunTrace`` containing every emitted event plus a
        derived summary.

        The ``run_completed`` event's payload contains the serialised
        ``AgentResult``; use ``trace.get_events(RUN_COMPLETED)`` to
        access it.
        """
        collector = TraceCollector()
        for _evt in self.run_stream(
            user_input,
            cancellation_token=cancellation_token,
            trace_collector=collector,
            approval_controller=approval_controller,
            budget_policy=budget_policy,
        ):
            pass  # consume the generator; events are recorded by collector
        return collector.build_trace()

    # ------------------------------------------------------------------
    # Structured Output (R6)
    # ------------------------------------------------------------------

    def run_structured(
        self,
        user_input: str,
        schema: SchemaTarget,
    ) -> StructuredRunResult:
        """
        Run the agent pipeline with schema-enforced output.

        The *user_input* is augmented with a schema instruction, the
        response is parsed as JSON, and the result is validated against
        *schema*.

        .. note::

            This method uses the non-streaming ``run()`` path.
            Cancellation, approval, budget enforcement, and tracing
            are not available here.  Use
            :meth:`run_structured_with_trace` for access to those
            runtime primitives.

        Args:
            user_input: User's input text.
            schema: Target schema — a dataclass type, Pydantic model
                class, or ``dict`` mapping field names to types.

        Returns:
            ``StructuredRunResult`` with ``success=True`` and a
            populated ``parsed_output`` field on success, or
            ``success=False`` with ``validation_error`` on failure.
        """
        augmented = build_schema_prompt(user_input, schema)
        result = self.run(augmented)
        sname = _schema_name(schema)

        raw_text = result.response
        data = extract_json(raw_text)

        if data is None:
            return StructuredRunResult(
                success=False,
                raw_text=raw_text,
                validation_error="Could not extract JSON from response",
                schema_name=sname,
                quality_score=result.quality_score,
                revision_count=result.revision_count,
            )

        try:
            parsed = validate_and_construct(data, schema)
        except (ValueError, TypeError, Exception) as exc:
            return StructuredRunResult(
                success=False,
                raw_text=raw_text,
                validation_error=str(exc),
                schema_name=sname,
                quality_score=result.quality_score,
                revision_count=result.revision_count,
            )

        return StructuredRunResult(
            success=True,
            raw_text=raw_text,
            parsed_output=parsed,
            schema_name=sname,
            quality_score=result.quality_score,
            revision_count=result.revision_count,
        )

    def run_structured_with_trace(
        self,
        user_input: str,
        schema: SchemaTarget,
        cancellation_token: Optional[CancellationToken] = None,
        approval_controller: Optional[ApprovalController] = None,
        budget_policy: Optional[BudgetPolicy] = None,
    ) -> tuple[StructuredRunResult, AgentRunTrace]:
        """
        Like :meth:`run_structured` but also returns a full
        ``AgentRunTrace`` including a ``structured_validation`` event.

        Supports all streaming runtime primitives (cancellation,
        approval, budget) because the underlying execution uses
        :meth:`run_stream`.
        """
        augmented = build_schema_prompt(user_input, schema)
        sname = _schema_name(schema)

        collector = TraceCollector()
        for _evt in self.run_stream(
            augmented,
            cancellation_token=cancellation_token,
            trace_collector=collector,
            approval_controller=approval_controller,
            budget_policy=budget_policy,
        ):
            pass

        # Extract result from the run_completed event
        raw_text = ""
        quality_score = 0.0
        revision_count = 0
        for evt in collector.events:
            if evt.event_type == RUN_COMPLETED and "result" in evt.payload:
                rd = evt.payload["result"]
                raw_text = rd.get("response", "")
                quality_score = rd.get("quality_score", 0.0)
                revision_count = rd.get("revision_count", 0)
                break
            if evt.event_type in (RUN_ERROR, RUN_CANCELLED, BUDGET_EXCEEDED):
                raw_text = ""
                break

        # Parse and validate
        data = extract_json(raw_text)
        if data is None:
            sr = StructuredRunResult(
                success=False,
                raw_text=raw_text,
                validation_error="Could not extract JSON from response",
                schema_name=sname,
                quality_score=quality_score,
                revision_count=revision_count,
            )
        else:
            try:
                parsed = validate_and_construct(data, schema)
                sr = StructuredRunResult(
                    success=True,
                    raw_text=raw_text,
                    parsed_output=parsed,
                    schema_name=sname,
                    quality_score=quality_score,
                    revision_count=revision_count,
                )
            except (ValueError, TypeError, Exception) as exc:
                sr = StructuredRunResult(
                    success=False,
                    raw_text=raw_text,
                    validation_error=str(exc),
                    schema_name=sname,
                    quality_score=quality_score,
                    revision_count=revision_count,
                )

        # Record validation event in trace
        session_id = self._memory.session_id if self._memory else ""
        turn_id = (self._memory.get_turn_count() - 1) if self._memory else 0
        validation_evt = make_event(
            STRUCTURED_VALIDATION,
            turn_id,
            session_id,
            {
                "success": sr.success,
                "schema_name": sname,
                "validation_error": sr.validation_error,
            },
        )
        collector.record(validation_evt)

        trace = collector.build_trace()
        return sr, trace

    # ------------------------------------------------------------------
    # Streaming API (R1) + Cancellation (R2) + Tracing (R11)
    # ------------------------------------------------------------------

    def run_stream(
        self,
        user_input: str,
        cancellation_token: Optional[CancellationToken] = None,
        trace_collector: Optional[TraceCollector] = None,
        approval_controller: Optional[ApprovalController] = None,
        budget_policy: Optional[BudgetPolicy] = None,
    ) -> Iterator[AgentRunEvent]:
        """
        Streaming variant of :meth:`run`.

        Yields ``AgentRunEvent`` instances as the agent progresses
        through its pipeline.  The final event is always
        ``run_completed``, ``run_cancelled``, ``run_error``, or
        ``budget_exceeded``.

        Args:
            user_input: User's input text.
            cancellation_token: Optional token checked at each pipeline
                boundary.  Call ``token.cancel()`` from any thread to
                stop the run cooperatively.
            trace_collector: Optional collector that records every
                emitted event for post-run inspection.
            approval_controller: Optional controller that gates action
                execution.  When supplied, actions matching the
                controller's policy emit ``approval_requested`` events
                and pause until the callback approves or denies.
            budget_policy: Optional token/cost budget.  When supplied,
                usage is checked after generation and before each
                action.  Exceeding the budget emits ``budget_exceeded``
                and stops the run.
        """
        # Ensure session exists
        if self._memory is None:
            self.new_session()

        turn_id = self._memory.get_turn_count()
        session_id = self._memory.session_id
        token = cancellation_token
        _tc = trace_collector

        def _evt(event_type: str, payload: dict | None = None) -> AgentRunEvent:
            return make_event(event_type, turn_id, session_id, payload)

        def _emit(event: AgentRunEvent) -> AgentRunEvent:
            if _tc is not None:
                _tc.record(event)
            return event

        def _cancelled_payload() -> dict:
            return {"reason": token.reason if token else None}

        yield _emit(_evt(RUN_STARTED, {"user_input": user_input}))

        try:
            # --- checkpoint: before goal decomposition ---
            if token and token.is_cancelled:
                yield _emit(_evt(RUN_CANCELLED, _cancelled_payload()))
                return

            # 1. Goal Decomposition
            self._goal_state = self._decompose_goal(user_input)

            # 2. Memory Enrichment
            context = self._build_context(user_input)

            # --- checkpoint: before generation ---
            if token and token.is_cancelled:
                yield _emit(_evt(RUN_CANCELLED, _cancelled_payload()))
                return

            # 3. Reflective Generation (streamed)
            yield _emit(_evt(GENERATION_STARTED))

            generation_result: GenerationResult | None = None

            for item in self.generator.generate_stream(
                prompt=user_input,
                context=context,
                goal_state=self._goal_state,
            ):
                if isinstance(item, GenerationResult):
                    generation_result = item
                elif isinstance(item, tuple):
                    tag, rev_num = item
                    if tag == "revision_started":
                        # --- checkpoint: before revision ---
                        if token and token.is_cancelled:
                            yield _emit(_evt(RUN_CANCELLED, _cancelled_payload()))
                            return
                        yield _emit(_evt(REVISION_STARTED, {"revision": rev_num}))
                    elif tag == "revision_completed":
                        yield _emit(_evt(REVISION_COMPLETED, {"revision": rev_num}))
                elif isinstance(item, str):
                    # --- checkpoint: between chunks ---
                    if token and token.is_cancelled:
                        yield _emit(_evt(RUN_CANCELLED, _cancelled_payload()))
                        return
                    yield _emit(_evt(TEXT_CHUNK, {"text": item}))

            assert generation_result is not None

            yield _emit(_evt(
                GENERATION_COMPLETED,
                {
                    "quality_score": generation_result.quality_score,
                    "revision_count": generation_result.revision_count,
                    "quality_trajectory": generation_result.quality_trajectory,
                },
            ))

            # --- usage tracking (R9) ---
            _usage = UsageStats()
            _adapter_usage = (
                self.llm.get_last_usage()
                if hasattr(self.llm, "get_last_usage")
                else None
            )
            _usage.record_generation(
                prompt_text=user_input,
                output_text=generation_result.final_output,
                exact_input=(_adapter_usage or {}).get("input_tokens"),
                exact_output=(_adapter_usage or {}).get("output_tokens"),
                cost=(_adapter_usage or {}).get("cost"),
                model=(_adapter_usage or {}).get("model")
                or getattr(self.llm, "model", ""),
            )
            yield _emit(_evt(USAGE_UPDATED, _usage.to_dict()))

            # --- budget check: after generation ---
            _bp = budget_policy
            if _bp is not None:
                _exceeded = _bp.is_exceeded(_usage)
                if _exceeded:
                    yield _emit(_evt(BUDGET_EXCEEDED, {
                        "reason": _exceeded,
                        **_usage.to_dict(),
                    }))
                    return

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

            # --- checkpoint: before safety gate ---
            if token and token.is_cancelled:
                yield _emit(_evt(RUN_CANCELLED, _cancelled_payload()))
                return

            # 6. Safety Contract Evaluation
            action_types = [a.action_type for a in self._goal_state.actions] if self._goal_state else []
            contract, allowed_actions = self.safety_gate.check(
                coherence_state=self._coherence_state,
                goal_state=self._goal_state,
                action_types=action_types,
            )

            yield _emit(_evt(
                SAFETY_GATE_RESULT,
                {
                    "eligible": contract.eligible,
                    "blocking_reasons": list(contract.blocking_reasons),
                },
            ))

            # 7. Execute actions if eligible
            actions_executed: List[str] = []
            _ac = approval_controller
            if contract.eligible and self._goal_state:
                for action in self._goal_state.actions:
                    if action.status != "pending":
                        continue
                    if action.action_type not in allowed_actions:
                        action.status = "blocked"
                        action.error = f"Action type '{action.action_type}' not allowed"
                        continue

                    # --- checkpoint: before each action ---
                    if token and token.is_cancelled:
                        yield _emit(_evt(RUN_CANCELLED, _cancelled_payload()))
                        return

                    # --- budget check: before each action (R9) ---
                    if _bp is not None:
                        _exceeded = _bp.is_exceeded(_usage)
                        if _exceeded:
                            yield _emit(_evt(BUDGET_EXCEEDED, {
                                "reason": _exceeded,
                                **_usage.to_dict(),
                            }))
                            return

                    # --- approval gate (R4) ---
                    if _ac and _ac.needs_approval(action.action_type):
                        pending = PendingApproval(
                            action_id=action.action_id,
                            action_type=action.action_type,
                            description=action.description,
                            parameters=action.parameters or {},
                            turn_id=turn_id,
                            session_id=session_id,
                            reason=f"Action type '{action.action_type}' requires approval",
                        )
                        yield _emit(_evt(APPROVAL_REQUESTED, {
                            "action_id": action.action_id,
                            "action_type": action.action_type,
                            "description": action.description,
                            "reason": pending.reason,
                        }))
                        response = _ac.request_approval(pending)
                        yield _emit(_evt(APPROVAL_RESOLVED, {
                            "action_id": action.action_id,
                            "action_type": action.action_type,
                            "approved": response.approved,
                            "reason": response.reason,
                        }))
                        if not response.approved:
                            action.status = "denied"
                            action.error = response.reason or "Denied by human approval"
                            yield _emit(_evt(ACTION_COMPLETED, {
                                "action_id": action.action_id,
                                "status": action.status,
                                "error": action.error,
                            }))
                            continue

                    yield _emit(_evt(ACTION_STARTED, {
                        "action_id": action.action_id,
                        "action_type": action.action_type,
                        "description": action.description,
                    }))

                    try:
                        # NOTE: once _execute_single_action begins, the
                        # action runs to completion.  Cancellation does
                        # NOT preempt an already-started action or MCP
                        # tool handler — it only prevents the *next*
                        # action from starting.
                        self._execute_single_action(action)
                        if action.status == "completed":
                            actions_executed.append(action.description)
                    except Exception as exc:
                        action.status = "failed"
                        action.error = str(exc)

                    yield _emit(_evt(ACTION_COMPLETED, {
                        "action_id": action.action_id,
                        "status": action.status,
                        "error": action.error,
                    }))

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

            # --- checkpoint: before completion ---
            if token and token.is_cancelled:
                yield _emit(_evt(RUN_CANCELLED, _cancelled_payload()))
                return

            # 8. Update Memory
            self._memory = self.memory_store.append_turn(self._memory, turn)

            # 9. Check for intervention needs
            should_intervene, reason = self.coherence_engine.should_intervene(
                self._coherence_state
            )

            agent_result = AgentResult(
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

            yield _emit(_evt(RUN_COMPLETED, {"result": agent_result.to_dict()}))

        except Exception as exc:
            yield _emit(_evt(RUN_ERROR, {"error": str(exc), "error_type": type(exc).__name__}))

    # ------------------------------------------------------------------
    # Async Streaming API (R2) + Tracing (R11)
    # ------------------------------------------------------------------

    async def run_stream_async(
        self,
        user_input: str,
        cancellation_token: Optional[CancellationToken] = None,
        trace_collector: Optional[TraceCollector] = None,
        approval_controller: Optional[ApprovalController] = None,
        budget_policy: Optional[BudgetPolicy] = None,
    ) -> AsyncIterator[AgentRunEvent]:
        """
        Async streaming variant of :meth:`run_stream`.

        Yields ``AgentRunEvent`` asynchronously.  Accepts the same
        optional ``CancellationToken`` for cooperative cancellation,
        an optional ``TraceCollector`` for in-memory tracing,
        an optional ``ApprovalController`` for human-in-the-loop
        approval gating, and an optional ``BudgetPolicy`` for
        token/cost budget enforcement.
        """
        if self._memory is None:
            self.new_session()

        turn_id = self._memory.get_turn_count()
        session_id = self._memory.session_id
        token = cancellation_token
        _tc = trace_collector

        def _evt(event_type: str, payload: dict | None = None) -> AgentRunEvent:
            return make_event(event_type, turn_id, session_id, payload)

        def _emit(event: AgentRunEvent) -> AgentRunEvent:
            if _tc is not None:
                _tc.record(event)
            return event

        def _cancelled_payload() -> dict:
            return {"reason": token.reason if token else None}

        yield _emit(_evt(RUN_STARTED, {"user_input": user_input}))

        try:
            if token and token.is_cancelled:
                yield _emit(_evt(RUN_CANCELLED, _cancelled_payload()))
                return

            self._goal_state = await asyncio.to_thread(
                self._decompose_goal, user_input,
            )
            context = self._build_context(user_input)

            if token and token.is_cancelled:
                yield _emit(_evt(RUN_CANCELLED, _cancelled_payload()))
                return

            yield _emit(_evt(GENERATION_STARTED))

            generation_result: GenerationResult | None = None

            async for item in self.generator.generate_stream_async(
                prompt=user_input,
                context=context,
                goal_state=self._goal_state,
            ):
                if isinstance(item, GenerationResult):
                    generation_result = item
                elif isinstance(item, tuple):
                    tag, rev_num = item
                    if tag == "revision_started":
                        if token and token.is_cancelled:
                            yield _emit(_evt(RUN_CANCELLED, _cancelled_payload()))
                            return
                        yield _emit(_evt(REVISION_STARTED, {"revision": rev_num}))
                    elif tag == "revision_completed":
                        yield _emit(_evt(REVISION_COMPLETED, {"revision": rev_num}))
                elif isinstance(item, str):
                    if token and token.is_cancelled:
                        yield _emit(_evt(RUN_CANCELLED, _cancelled_payload()))
                        return
                    yield _emit(_evt(TEXT_CHUNK, {"text": item}))

            assert generation_result is not None

            yield _emit(_evt(
                GENERATION_COMPLETED,
                {
                    "quality_score": generation_result.quality_score,
                    "revision_count": generation_result.revision_count,
                    "quality_trajectory": generation_result.quality_trajectory,
                },
            ))

            # --- usage tracking (R9) ---
            _usage = UsageStats()
            _adapter_usage = (
                self.llm.get_last_usage()
                if hasattr(self.llm, "get_last_usage")
                else None
            )
            _usage.record_generation(
                prompt_text=user_input,
                output_text=generation_result.final_output,
                exact_input=(_adapter_usage or {}).get("input_tokens"),
                exact_output=(_adapter_usage or {}).get("output_tokens"),
                cost=(_adapter_usage or {}).get("cost"),
                model=(_adapter_usage or {}).get("model")
                or getattr(self.llm, "model", ""),
            )
            yield _emit(_evt(USAGE_UPDATED, _usage.to_dict()))

            # --- budget check: after generation ---
            _bp = budget_policy
            if _bp is not None:
                _exceeded = _bp.is_exceeded(_usage)
                if _exceeded:
                    yield _emit(_evt(BUDGET_EXCEEDED, {
                        "reason": _exceeded,
                        **_usage.to_dict(),
                    }))
                    return

            turn = create_turn_snapshot(
                turn_id=turn_id,
                user_input=user_input,
                assistant_output=generation_result.final_output,
                quality_score=generation_result.quality_score,
                revision_count=generation_result.revision_count,
            )

            self._coherence_state = self.coherence_engine.update(
                prev_state=self._coherence_state,
                turn=turn,
                goal_state=self._goal_state,
            )

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

            if token and token.is_cancelled:
                yield _emit(_evt(RUN_CANCELLED, _cancelled_payload()))
                return

            action_types = [a.action_type for a in self._goal_state.actions] if self._goal_state else []
            contract, allowed_actions = self.safety_gate.check(
                coherence_state=self._coherence_state,
                goal_state=self._goal_state,
                action_types=action_types,
            )

            yield _emit(_evt(
                SAFETY_GATE_RESULT,
                {
                    "eligible": contract.eligible,
                    "blocking_reasons": list(contract.blocking_reasons),
                },
            ))

            actions_executed: List[str] = []
            _ac = approval_controller
            if contract.eligible and self._goal_state:
                for action in self._goal_state.actions:
                    if action.status != "pending":
                        continue
                    if action.action_type not in allowed_actions:
                        action.status = "blocked"
                        action.error = f"Action type '{action.action_type}' not allowed"
                        continue

                    if token and token.is_cancelled:
                        yield _emit(_evt(RUN_CANCELLED, _cancelled_payload()))
                        return

                    # --- budget check: before each action (R9) ---
                    if _bp is not None:
                        _exceeded = _bp.is_exceeded(_usage)
                        if _exceeded:
                            yield _emit(_evt(BUDGET_EXCEEDED, {
                                "reason": _exceeded,
                                **_usage.to_dict(),
                            }))
                            return

                    # --- approval gate (R4) ---
                    if _ac and _ac.needs_approval(action.action_type):
                        pending = PendingApproval(
                            action_id=action.action_id,
                            action_type=action.action_type,
                            description=action.description,
                            parameters=action.parameters or {},
                            turn_id=turn_id,
                            session_id=session_id,
                            reason=f"Action type '{action.action_type}' requires approval",
                        )
                        yield _emit(_evt(APPROVAL_REQUESTED, {
                            "action_id": action.action_id,
                            "action_type": action.action_type,
                            "description": action.description,
                            "reason": pending.reason,
                        }))
                        response = await asyncio.to_thread(
                            _ac.request_approval, pending,
                        )
                        yield _emit(_evt(APPROVAL_RESOLVED, {
                            "action_id": action.action_id,
                            "action_type": action.action_type,
                            "approved": response.approved,
                            "reason": response.reason,
                        }))
                        if not response.approved:
                            action.status = "denied"
                            action.error = response.reason or "Denied by human approval"
                            yield _emit(_evt(ACTION_COMPLETED, {
                                "action_id": action.action_id,
                                "status": action.status,
                                "error": action.error,
                            }))
                            continue

                    yield _emit(_evt(ACTION_STARTED, {
                        "action_id": action.action_id,
                        "action_type": action.action_type,
                        "description": action.description,
                    }))

                    try:
                        await asyncio.to_thread(self._execute_single_action, action)
                        if action.status == "completed":
                            actions_executed.append(action.description)
                    except Exception as exc:
                        action.status = "failed"
                        action.error = str(exc)

                    yield _emit(_evt(ACTION_COMPLETED, {
                        "action_id": action.action_id,
                        "status": action.status,
                        "error": action.error,
                    }))

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

            if token and token.is_cancelled:
                yield _emit(_evt(RUN_CANCELLED, _cancelled_payload()))
                return

            self._memory = self.memory_store.append_turn(self._memory, turn)

            should_intervene, reason = self.coherence_engine.should_intervene(
                self._coherence_state
            )

            agent_result = AgentResult(
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

            yield _emit(_evt(RUN_COMPLETED, {"result": agent_result.to_dict()}))

        except Exception as exc:
            yield _emit(_evt(RUN_ERROR, {"error": str(exc), "error_type": type(exc).__name__}))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _execute_single_action(self, action: "ActionItem") -> None:
        """Execute a single action (used by both run and run_stream)."""
        if (
            self.dispatcher is not None
            and action.action_type in self.action_type_to_tool
        ):
            tool_name = self.action_type_to_tool[action.action_type]
            mcp_result = self._dispatch_via_mcp(
                tool_name=tool_name,
                parameters=action.parameters or {},
            )
            if getattr(mcp_result, "success", False):
                action.status = "completed"
                action.result = getattr(mcp_result, "result", None)
            else:
                action.status = "blocked"
                decision = getattr(mcp_result, "decision", None)
                decision_val = (
                    decision.value if decision is not None
                    and hasattr(decision, "value") else str(decision)
                )
                reason = getattr(mcp_result, "blocked_reason", None) \
                    or getattr(mcp_result, "error", None) \
                    or f"MCP decision={decision_val}"
                action.error = f"MCP: {reason}"
            return

        if action.action_type == "generate":
            action.status = "completed"
        elif action.action_type == "search":
            action.status = "completed"
            action.result = f"Search completed for: {action.parameters.get('query', '')}"
        elif action.action_type == "compute":
            action.status = "completed"
            action.result = "Computation completed"
        elif action.action_type == "validate":
            action.status = "completed"
            action.result = "Validation passed"
        else:
            action.status = "skipped"
            orig = getattr(action, "original_action_type", None)
            if orig:
                action.error = (
                    f"Unmapped action type: '{action.action_type}' "
                    f"(normalized from '{orig}'). "
                    f"Add it to action_type_to_tool to route through MCP."
                )
            else:
                action.error = (
                    f"Unmapped action type: '{action.action_type}'. "
                    f"Add it to action_type_to_tool to route through MCP."
                )

    def _decompose_goal(self, user_input: str) -> GoalState:
        """Decompose user input into structured goal.

        When ``action_type_to_tool`` is configured, it is passed to
        ``decompose_goal()`` as the action-type alias table so that
        generic LLM action labels (e.g. "execute") can be normalized
        to the canonical runtime types the developer registered
        (e.g. "save_draft").
        """
        aliases = self.action_type_to_tool if self.action_type_to_tool else None
        if self.use_llm_for_decomposition:
            try:
                return decompose_goal(user_input, self.llm, action_type_aliases=aliases)
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
                # Dispatcher routing (layered BEHIND SafetyGate). When a
                # dispatcher is configured AND this action_type maps to a
                # registered MCP tool, route the call through MCP
                # governance. Actions without a mapping fall through to
                # the existing placeholder branches unchanged.
                if (
                    self.dispatcher is not None
                    and action.action_type in self.action_type_to_tool
                ):
                    tool_name = self.action_type_to_tool[action.action_type]
                    mcp_result = self._dispatch_via_mcp(
                        tool_name=tool_name,
                        parameters=action.parameters or {},
                    )
                    if getattr(mcp_result, "success", False):
                        action.status = "completed"
                        action.result = getattr(mcp_result, "result", None)
                        executed.append(action.description)
                    else:
                        action.status = "blocked"
                        decision = getattr(mcp_result, "decision", None)
                        decision_val = (
                            decision.value if decision is not None
                            and hasattr(decision, "value") else str(decision)
                        )
                        reason = getattr(mcp_result, "blocked_reason", None) \
                            or getattr(mcp_result, "error", None) \
                            or f"MCP decision={decision_val}"
                        action.error = f"MCP: {reason}"
                    continue

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

    def _dispatch_via_mcp(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
    ) -> Any:
        """
        Run ``self.dispatcher.dispatch(...)`` synchronously by driving
        the coroutine on a fresh event loop.

        A fresh loop (rather than ``asyncio.run``) is used because this
        method may be invoked from inside an outer event loop (e.g. a
        FastAPI handler that calls ``AgenticLLMWrapper.run``). A fresh,
        isolated loop is safe in both contexts. The loop is closed
        after use; the caller receives the ``MCPToolResult`` directly.
        """
        import asyncio

        assert self.dispatcher is not None, "dispatcher required"
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                self.dispatcher.dispatch(
                    tool_name=tool_name,
                    parameters=parameters,
                )
            )
        finally:
            loop.close()

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
