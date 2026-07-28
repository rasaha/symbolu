"""
Multi-Agent Orchestration & Handoff for the Agentic Framework
=============================================================

The base framework governs a **single** agent's execution path — there is
no agent-to-agent handoff or orchestration.  This module adds a thin
orchestration layer on top of the public agent API so several governed
agents can collaborate on one query.

Design principle: **compose, don't replace.**  Each participating agent is
an ordinary ``AgenticLLMWrapper`` with its own tools, safety gate, memory
and tracing.  The orchestrator only decides *who runs next* and threads
context between them — it never bypasses any agent's governance.  Every
turn is a full ``run_with_trace()`` call, so per-agent safety gating,
approvals, budgets and audit all still apply.

Two safety bounds keep orchestration terminating:

* ``max_handoffs`` — a hard cap on the number of agent transfers.
* an optional shared :class:`BudgetPolicy` applied to every turn.

Routing is pluggable:

* :class:`KeywordRouter` — deterministic, dependency-free, great for tests
  and for demonstrating handoff behaviour without an API key.
* :class:`LLMRouter` — a supervisor model chooses the next agent from the
  team roster (the genuine "let the model orchestrate" path).

Quickstart
----------
::

    from agentic.agentic_framework import (
        build_agent, MockLLMAdapter,
        AgentRegistry, KeywordRouter, MultiAgentOrchestrator,
    )

    registry = AgentRegistry()
    registry.register("researcher", research_agent, "Finds facts")
    registry.register("writer", writer_agent, "Writes prose")

    router = KeywordRouter(
        routes={"researcher": ["research", "find"], "writer": ["write", "draft"]},
        default="researcher",
        done_markers=["[final]"],
    )
    team = MultiAgentOrchestrator(registry, router, max_handoffs=3)
    result = team.run("Research topic X then write a summary")
    print(result.final_response, result.handoff_path())
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from agentic.agentic_framework.iterate_loop import _response_from_trace
from agentic.agentic_framework.tracing import AgentRunTrace
from agentic.agentic_framework.run_budget import (
    RunBudget,
    BudgetExhausted,
    attach_run_budget,
)

__all__ = [
    "RegisteredAgent",
    "AgentRegistry",
    "AgentTurn",
    "Handoff",
    "RouteDecision",
    "Router",
    "KeywordRouter",
    "LLMRouter",
    "MultiAgentResult",
    "MultiAgentOrchestrator",
]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
@dataclass
class RegisteredAgent:
    """An agent enrolled in a team, with a routing description."""

    name: str
    agent: Any  # AgenticLLMWrapper
    description: str = ""


class AgentRegistry:
    """A named collection of governed agents."""

    def __init__(self) -> None:
        self._agents: Dict[str, RegisteredAgent] = {}

    def register(self, name: str, agent: Any, description: str = "") -> "AgentRegistry":
        if name in self._agents:
            raise ValueError(f"agent '{name}' already registered")
        self._agents[name] = RegisteredAgent(name=name, agent=agent, description=description)
        return self

    def get(self, name: str) -> RegisteredAgent:
        if name not in self._agents:
            raise KeyError(f"no agent named '{name}' (have: {sorted(self._agents)})")
        return self._agents[name]

    def has(self, name: str) -> bool:
        return name in self._agents

    def names(self) -> List[str]:
        return list(self._agents)

    def roster(self) -> str:
        """Human-readable roster for LLM routing prompts."""
        return "\n".join(
            f"- {a.name}: {a.description or '(no description)'}"
            for a in self._agents.values()
        )

    def __len__(self) -> int:
        return len(self._agents)


# ---------------------------------------------------------------------------
# Transcript model
# ---------------------------------------------------------------------------
@dataclass
class AgentTurn:
    """One agent's governed turn within an orchestration run."""

    agent_name: str
    instruction: str
    response: str
    trace: Optional[AgentRunTrace] = None

    @property
    def actions_executed(self) -> int:
        return self.trace.actions_executed if self.trace is not None else 0

    @property
    def total_tokens(self) -> int:
        return self.trace.total_tokens if self.trace is not None else 0


@dataclass
class Handoff:
    """A transfer of control from one agent to another."""

    from_agent: str
    to_agent: str
    reason: str = ""


@dataclass
class MultiAgentResult:
    """Outcome of an orchestration run."""

    query: str
    stop_reason: str  # "completed" | "max_handoffs" | "budget_exceeded" | "budget_exhausted" | "error" | "empty"
    turns: List[AgentTurn] = field(default_factory=list)
    handoffs: List[Handoff] = field(default_factory=list)
    #: Deterministic RunBudget termination reason (H11), when the shared
    #: run budget stopped the orchestration (e.g. "HANDOFF_LIMIT").
    termination_reason: Optional[str] = None
    #: The shared RunBudget (H11), when one was supplied.
    run_budget: Optional["RunBudget"] = None
    #: Per-turn RunBudget snapshots for cumulative reconstruction.
    budget_timeline: List[dict] = field(default_factory=list)

    @property
    def final_response(self) -> str:
        return self.turns[-1].response if self.turns else ""

    @property
    def final_agent(self) -> Optional[str]:
        return self.turns[-1].agent_name if self.turns else None

    @property
    def total_tokens(self) -> int:
        return sum(t.total_tokens for t in self.turns)

    def handoff_path(self) -> str:
        """Render the sequence of agents that handled the query."""
        if not self.turns:
            return "(none)"
        return " -> ".join(t.agent_name for t in self.turns)

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "stop_reason": self.stop_reason,
            "final_agent": self.final_agent,
            "final_response": self.final_response,
            "total_tokens": self.total_tokens,
            "termination_reason": self.termination_reason,
            "run_budget": self.run_budget.snapshot() if self.run_budget is not None else None,
            "budget_timeline": self.budget_timeline,
            "handoff_path": self.handoff_path(),
            "turns": [
                {
                    "agent": t.agent_name,
                    "instruction": t.instruction,
                    "response": t.response,
                    "actions_executed": t.actions_executed,
                }
                for t in self.turns
            ],
            "handoffs": [
                {"from": h.from_agent, "to": h.to_agent, "reason": h.reason}
                for h in self.handoffs
            ],
        }


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------
@dataclass
class RouteDecision:
    """Where control goes next."""

    #: Name of the agent to run next.  None when ``done`` is True.
    target: Optional[str] = None
    done: bool = False
    reason: str = ""


class Router(Protocol):
    """Selects the next agent (or signals completion).

    Called once to pick the starting agent (``current=None``, empty
    ``turns``) and again after every turn to decide the next hop.
    """

    def route(
        self,
        query: str,
        turns: List[AgentTurn],
        registry: AgentRegistry,
        current: Optional[str],
    ) -> RouteDecision:
        ...


class KeywordRouter:
    """Deterministic keyword-based supervisor.

    Scores each agent by how many of its keywords appear in the routing
    text (the original query plus the most recent agent response), then
    routes to the best match.  Completion is signalled when the latest
    response contains a *done marker*, or when no agent other than the
    current one has any remaining keyword match.

    This is fully deterministic (no LLM), so handoff behaviour is
    reproducible in tests and demos.
    """

    def __init__(
        self,
        routes: Dict[str, List[str]],
        *,
        default: Optional[str] = None,
        done_markers: Optional[List[str]] = None,
    ) -> None:
        self.routes = {name: [k.lower() for k in kws] for name, kws in routes.items()}
        self.default = default
        self.done_markers = [m.lower() for m in (done_markers or ["[final]", "[done]"])]

    def _score(self, agent_name: str, text: str) -> int:
        return sum(1 for kw in self.routes.get(agent_name, []) if kw in text)

    def route(
        self,
        query: str,
        turns: List[AgentTurn],
        registry: AgentRegistry,
        current: Optional[str],
    ) -> RouteDecision:
        latest_response = turns[-1].response if turns else ""

        # 1. Explicit completion marker in the latest response.
        low_resp = latest_response.lower()
        if turns and any(m in low_resp for m in self.done_markers):
            return RouteDecision(done=True, reason="done marker in response")

        # Starting hop: route on the query alone.
        if current is None:
            search_text = query.lower()
            best = self._best_agent(search_text, registry, exclude=None)
            if best is not None:
                return RouteDecision(target=best, reason="initial keyword match")
            if self.default and registry.has(self.default):
                return RouteDecision(target=self.default, reason="default agent")
            return RouteDecision(done=True, reason="no matching agent")

        # Subsequent hop: route on query + latest response, so an agent can
        # "request" another specialist by mentioning its keywords.
        search_text = f"{query}\n{latest_response}".lower()
        best = self._best_agent(search_text, registry, exclude=current)
        if best is not None:
            return RouteDecision(target=best, reason="handoff keyword match")

        # No other specialist is needed → the current agent settled it.
        return RouteDecision(done=True, reason="no further handoff signalled")

    def _best_agent(
        self,
        text: str,
        registry: AgentRegistry,
        exclude: Optional[str],
    ) -> Optional[str]:
        best_name: Optional[str] = None
        best_score = 0
        for name in registry.names():
            if name == exclude:
                continue
            score = self._score(name, text)
            if score > best_score:
                best_score = score
                best_name = name
        return best_name


class LLMRouter:
    """Supervisor router backed by an LLM.

    Presents the team roster and asks the model to name the next agent, or
    reply ``DONE``.  The adapter only needs ``call(prompt) -> str``.
    """

    PROMPT_TEMPLATE = (
        "You are a supervisor routing a user request to a team of agents.\n"
        "TEAM:\n{roster}\n\n"
        "USER REQUEST:\n{query}\n\n"
        "CONVERSATION SO FAR:\n{transcript}\n\n"
        "Reply with EXACTLY one line, one of:\n"
        "  ROUTE: <agent name>   (to send the next step to that agent)\n"
        "  DONE                  (the request is fully handled)\n"
    )

    def __init__(self, adapter: Any) -> None:
        self.adapter = adapter

    def route(
        self,
        query: str,
        turns: List[AgentTurn],
        registry: AgentRegistry,
        current: Optional[str],
    ) -> RouteDecision:
        transcript = "\n".join(
            f"[{t.agent_name}] {t.response}" for t in turns
        ) or "(nothing yet)"
        prompt = self.PROMPT_TEMPLATE.format(
            roster=registry.roster(),
            query=query,
            transcript=transcript,
        )
        raw = (self.adapter.call(prompt) or "").strip()
        upper = raw.upper()

        route_idx = upper.find("ROUTE")
        done_idx = upper.find("DONE")

        if route_idx != -1 and (done_idx == -1 or route_idx <= done_idx):
            remainder = raw[route_idx + len("ROUTE"):].lstrip(" :\t-").strip()
            # Match the named agent (first token that is a known agent).
            for token in [remainder] + remainder.split():
                token = token.strip(".,:;")
                if registry.has(token):
                    return RouteDecision(target=token, reason="supervisor route")
            # Named agent not found → complete rather than loop.
            return RouteDecision(done=True, reason="supervisor named unknown agent")
        if done_idx != -1:
            return RouteDecision(done=True, reason="supervisor done")

        return RouteDecision(done=True, reason="supervisor unparsed")


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
class MultiAgentOrchestrator:
    """Coordinate a team of governed agents with handoff.

    Args:
        registry: The team of agents.
        router: Selects the next agent / signals completion.
        max_handoffs: Hard cap on agent transfers (terminal, non-optional).
        budget_policy: Optional per-turn ``BudgetPolicy`` (resets each turn).
        run_budget: Optional shared :class:`RunBudget` (H11).  Created once
            by the caller; every agent consumes from it cumulatively, so a
            handoff never resets accounting.  When a limit is hit the run
            terminates with ``stop_reason="budget_exhausted"`` and a
            deterministic ``termination_reason``.
        fresh_sessions: When True (default) each agent starts a fresh
            session at the beginning of the run.
        context_window: Number of most-recent turns whose output is passed
            forward as context on a handoff.
    """

    def __init__(
        self,
        registry: AgentRegistry,
        router: Router,
        *,
        max_handoffs: int = 4,
        budget_policy: Optional[Any] = None,
        run_budget: Optional[RunBudget] = None,
        fresh_sessions: bool = True,
        context_window: int = 3,
    ) -> None:
        if max_handoffs < 0:
            raise ValueError("max_handoffs must be >= 0")
        if len(registry) == 0:
            raise ValueError("registry has no agents")
        self.registry = registry
        self.router = router
        self.max_handoffs = max_handoffs
        self.budget_policy = budget_policy
        #: Shared cumulative RunBudget (H11).  Every agent in the team
        #: consumes from this same object — handoffs never reset it.
        self.run_budget = run_budget
        self.fresh_sessions = fresh_sessions
        self.context_window = context_window

    def _instruction_for_handoff(self, query: str, turns: List[AgentTurn]) -> str:
        """Build the instruction the receiving agent sees on a handoff."""
        recent = turns[-self.context_window:]
        context = "\n".join(f"[{t.agent_name}] {t.response}" for t in recent)
        return (
            f"Original request: {query}\n\n"
            f"Work done by other agents so far:\n{context}\n\n"
            "Continue from here with your specialty."
        )

    def run(self, query: str) -> MultiAgentResult:
        """Route the query through the team until done or a bound is hit."""
        result = MultiAgentResult(query=query, stop_reason="empty")
        result.run_budget = self.run_budget

        if self.fresh_sessions:
            for name in self.registry.names():
                reg = self.registry.get(name)
                if hasattr(reg.agent, "new_session"):
                    reg.agent.new_session()

        # H11: install the ONE shared budget on every agent (idempotent) and
        # mark the workflow start.  Agent A and Agent B consume the same
        # object — a handoff never resets it.
        if self.run_budget is not None:
            for name in self.registry.names():
                attach_run_budget(self.registry.get(name).agent, self.run_budget)
            self.run_budget.start()

        # Pick the starting agent.
        decision = self.router.route(query, result.turns, self.registry, current=None)
        if decision.done or decision.target is None:
            result.stop_reason = "completed" if decision.done else "empty"
            self._finish_budget(result)
            return result

        current = decision.target
        instruction = query
        # One initial turn + up to max_handoffs additional turns.
        max_turns = self.max_handoffs + 1

        for _ in range(max_turns):
            # H11: gate before the turn runs — a budget already exhausted by
            # earlier agents/turns blocks this one before execution.
            if self.run_budget is not None:
                gate = self.run_budget.can_afford()
                if not gate.ok:
                    result.stop_reason = "budget_exhausted"
                    result.termination_reason = gate.reason
                    self._finish_budget(result)
                    return result

            reg = self.registry.get(current)
            # H11: a model-call reservation may reject mid-turn -> BudgetExhausted.
            try:
                trace = reg.agent.run_with_trace(instruction, budget_policy=self.budget_policy)
            except BudgetExhausted as exc:
                result.stop_reason = "budget_exhausted"
                result.termination_reason = exc.reason
                self._finish_budget(result)
                return result

            turn = AgentTurn(
                agent_name=current,
                instruction=instruction,
                response=_response_from_trace(trace),
                trace=trace,
            )
            result.turns.append(turn)

            # H11: record post-hoc tool-call consumption from the governed trace.
            if self.run_budget is not None:
                self.run_budget.record_usage(tool_calls=trace.actions_executed)
                self.run_budget.tick()
                result.budget_timeline.append(self.run_budget.snapshot())
                if self.run_budget.is_exhausted():
                    result.stop_reason = "budget_exhausted"
                    result.termination_reason = self.run_budget.termination_reason
                    self._finish_budget(result)
                    return result

            if trace.budget_exceeded:
                result.stop_reason = "budget_exceeded"
                self._finish_budget(result)
                return result
            if trace.error_occurred:
                result.stop_reason = "error"
                self._finish_budget(result)
                return result

            decision = self.router.route(query, result.turns, self.registry, current)
            if decision.done or decision.target is None:
                result.stop_reason = "completed"
                self._finish_budget(result)
                return result
            if decision.target != current:
                # H11: reserve the handoff BEFORE switching agents.
                if self.run_budget is not None:
                    res = self.run_budget.reserve(handoffs=1)
                    if not res.ok:
                        result.stop_reason = "budget_exhausted"
                        result.termination_reason = res.reason
                        self._finish_budget(result)
                        return result
                result.handoffs.append(
                    Handoff(from_agent=current, to_agent=decision.target, reason=decision.reason)
                )
                current = decision.target
                instruction = self._instruction_for_handoff(query, result.turns)
            else:
                # Router asked for the same agent again — treat as settled to
                # avoid an unbounded self-loop.
                result.stop_reason = "completed"
                self._finish_budget(result)
                return result

        result.stop_reason = "max_handoffs"
        self._finish_budget(result)
        return result

    def _finish_budget(self, result: MultiAgentResult) -> None:
        """Mark the shared budget complete unless it terminated the run."""
        if self.run_budget is not None and not self.run_budget.is_exhausted():
            self.run_budget.complete()
