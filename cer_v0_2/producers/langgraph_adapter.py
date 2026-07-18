"""LangGraph CER V0.2 adapter — REAL langgraph, both profiles.

Two real tools (k8s_scale, k8s_rollout) bound in a real ToolNode; a planner node
emits the tool call for the requested profile; the adapter intercepts the pending
tool call before ToolNode executes and normalizes it to CER. No LangGraph-specific
logic in CER/ActionGate/ACP.
"""
from __future__ import annotations

import operator
from typing import Annotated, Optional, TypedDict, Union

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from ..actuation import (EnvelopeContext, RolloutActuation, ScaleActuation,
                         actuation_block_from_tool_args, assemble_cer)

Actuation = Union[ScaleActuation, RolloutActuation]


@tool
def k8s_scale(namespace: str, deployment: str, replicas: int) -> str:
    """Scale a deployment (governed; shadow no-op)."""
    return "scaled"


@tool
def k8s_rollout(namespace: str, deployment: str, image_digest: str) -> str:
    """Roll out a new image to a deployment (governed; shadow no-op)."""
    return "rolled out"


class _S(TypedDict):
    messages: Annotated[list, operator.add]
    request: dict
    cer: Optional[dict]


class LangGraphCERAdapter:
    RUNTIME = "langgraph"
    RUNTIME_VERSION = "1.2.9"
    MODEL = "gpt-4o-mini"
    MODEL_PROVIDER = "openai"

    def __init__(self):
        self._tool_node = ToolNode([k8s_scale, k8s_rollout])
        self._app = self._build()

    def _planner(self, state: _S) -> dict:
        req = state["request"]
        name = "k8s_scale" if req["profile"] == "kubernetes.scale.v1" else "k8s_rollout"
        args = req["tool_args"]
        # the tool call carries the physically-varying identity fields
        tc = {"name": name, "args": args, "id": "call_1"}
        return {"messages": [AIMessage(content="", tool_calls=[tc])]}

    def _intercept(self, state: _S) -> dict:
        last = state["messages"][-1]
        tcs = getattr(last, "tool_calls", None) or []
        if not tcs:
            return {"cer": None}
        return {"cer": self._to_cer(tcs[0], state["request"])}

    def _build(self):
        g = StateGraph(_S)
        g.add_node("planner", self._planner)
        g.add_node("intercept", self._intercept)
        g.add_node("tools", self._tool_node)
        g.set_entry_point("planner")
        g.add_edge("planner", "intercept")
        g.add_conditional_edges("intercept", lambda s: END, {END: END, "tools": "tools"})
        g.add_edge("tools", END)
        return g.compile()

    def _to_cer(self, tool_call: dict, req: dict) -> dict:
        profile = req["profile"]
        args = dict(tool_call["args"])
        # merge context-supplied identity fields the tool call doesn't carry
        for k in ("cluster", "from_replicas", "current_manifest_digest", "rollout_strategy",
                  "max_surge", "max_unavailable", "timeout_s", "rollback_ref", "reversibility"):
            if k in req["full_args"] and k not in args:
                args[k] = req["full_args"][k]
        block = actuation_block_from_tool_args(profile, args)
        act = req["_actuation_label"]
        provenance = {
            "runtime": self.RUNTIME, "runtime_version": self.RUNTIME_VERSION,
            "model_provider": self.MODEL_PROVIDER, "model": self.MODEL,
            "planner": "langgraph.stategraph",
            "objective": f"please execute {profile} on {args['namespace']}/{args['deployment']}",
            "reasoning_trace_ref": "langgraph://thread", "adapter_version": "cer-langgraph/0.2",
            "explanation": f"Graph selected {act} tool.",
        }
        return assemble_cer(profile, EnvelopeContext(**req["ctx"]), block, provenance)

    def propose(self, ctx: EnvelopeContext, act: Actuation) -> dict:
        req = {
            "profile": act.PROFILE, "tool_args": act.tool_args(),
            "full_args": act.tool_args(),
            "ctx": ctx.__dict__, "_actuation_label": type(act).__name__,
        }
        state = self._app.invoke({
            "messages": [HumanMessage(content=f"execute {act.PROFILE}")],
            "request": req, "cer": None})
        return state["cer"]
