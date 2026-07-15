"""LangGraph CER adapter — REAL langgraph execution boundary.

Integration (milestone §4 preferred path):
  * build a real ``langgraph.graph.StateGraph`` with a planner node that emits a
    ``k8s_scale`` tool call (as an LLM-driven agent would) and a ``ToolNode`` for
    the tool;
  * INTERCEPT the pending tool call *before* ``ToolNode`` executes;
  * normalize it to CER V0.1 (stamping LangGraph provenance + its own objective);
  * hand the CER to the control plane; resume / replan / stop on the composed
    result (the governed loop lives in control_plane.py; this module produces the
    CER and exposes the graph).

No LLM/API key is required: the planner node deterministically emits the tool
call, but the graph, message types, tool binding, and ToolNode boundary are all
REAL langgraph/langchain-core objects — the interception happens at the genuine
execution boundary, not a mock of it.

There is NO LangGraph-specific logic in ActionGate or ACP; all LangGraph coupling
is confined to this adapter (verified by the ownership test).
"""
from __future__ import annotations

import operator
from typing import Annotated, Callable, Dict, List, Optional, TypedDict

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from ..actuation import ActuationRequest


@tool
def k8s_scale(namespace: str, deployment: str, replicas: int) -> str:
    """Scale a kubernetes deployment to the given replica count (governed)."""
    # Body never runs in governed mode — the adapter intercepts before ToolNode.
    return f"scaled {namespace}/{deployment} to {replicas}"


class _GraphState(TypedDict):
    messages: Annotated[list, operator.add]
    request: dict
    cer: Optional[dict]
    verdict: Optional[dict]
    control: Optional[str]  # RESUME / REPLAN / STOP


class LangGraphCERAdapter:
    """Runs a real LangGraph agent and intercepts the tool call as a CER."""

    RUNTIME = "langgraph"
    RUNTIME_VERSION = "1.2.9"
    MODEL = "gpt-4o-mini"
    MODEL_PROVIDER = "openai"
    ADAPTER_VERSION = "cer-langgraph/0.1"

    def __init__(self, *, submit_cer: Optional[Callable[[dict], dict]] = None) -> None:
        # submit_cer: control-plane callback CER -> composed result dict (Stage 4).
        # If None, the graph just produces the CER (Stage-3 producer behavior).
        self._submit_cer = submit_cer
        self._tool_node = ToolNode([k8s_scale])  # real ToolNode we intercept BEFORE
        self._app = self._build_graph()

    # --- the REAL graph ---
    def _planner(self, state: _GraphState) -> dict:
        """Emit the scale tool call (as an agent LLM would)."""
        req = state["request"]
        tc = {
            "name": "k8s_scale",
            "args": {"namespace": req["namespace"], "deployment": req["deployment"],
                     "replicas": int(req["to_replicas"])},
            "id": "call_scale_1",
        }
        return {"messages": [AIMessage(content="", tool_calls=[tc])]}

    def _intercept(self, state: _GraphState) -> dict:
        """Intercept the pending tool call BEFORE ToolNode; normalize to CER."""
        last = state["messages"][-1]
        tool_calls = getattr(last, "tool_calls", None) or []
        if not tool_calls:
            return {"control": "STOP"}
        tc = tool_calls[0]
        cer = self._tool_call_to_cer(tc, state["request"])
        if self._submit_cer is None:
            return {"cer": cer, "control": "STOP"}  # producer-only mode
        result = self._submit_cer(cer)
        # governed loop: resume/replan/stop on the composed control-plane result
        control = "RESUME" if result.get("eligible") else (
            "REPLAN" if result.get("retryable") else "STOP")
        return {"cer": cer, "verdict": result, "control": control}

    def _build_graph(self):
        g = StateGraph(_GraphState)
        g.add_node("planner", self._planner)
        g.add_node("intercept", self._intercept)
        # ToolNode is bound but only reached on RESUME (an authorized token path);
        # in shadow governance it is never executed — the intercept routes to END.
        g.add_node("tools", self._tool_node)
        g.set_entry_point("planner")
        g.add_edge("planner", "intercept")

        def _route(state: _GraphState) -> str:
            # In this shadow harness, never execute the real tool: governed
            # eligibility is hypothetical (no cluster). RESUME would, in a live
            # system with a minted token, proceed to "tools".
            return END
        g.add_conditional_edges("intercept", _route, {END: END, "tools": "tools"})
        g.add_edge("tools", END)
        return g.compile()

    # --- normalization: intercepted tool call + request context -> CER ---
    def _tool_call_to_cer(self, tool_call: dict, req: dict) -> dict:
        args = tool_call["args"]
        # tool-call-carried identity facts come from the REAL intercepted call;
        # authority/state/policy come from the runtime's shared request context.
        target = {"cluster": req["cluster"], "namespace": args["namespace"],
                  "deployment": args["deployment"]}
        identity = {
            "operation": req["operation"],
            "actuation_interface": "kubernetes.scale",
            "target": target,
            "arguments": {"replicas": str(args["replicas"])},
            "requested_state_transition": {
                "replicas": {"from": str(req["from_replicas"]), "to": str(args["replicas"])}},
            "authority": {
                "principal": req["principal"], "permissions": list(req["permissions"]),
                "delegator": {"id": req["delegator_id"], "type": "HUMAN"},
                "delegation_chain": [{"grant": "*"}],
            },
            "external_state_binding": {
                "resource_version": req["resource_version"], "state_hash": req["state_hash"],
                "as_of": req["as_of"], "source": "kubernetes",
                "correlation_id": req["correlation_id"], "sequence_id": req["sequence_id"],
                "rollback_ref": req.get("rollback_ref", ""),
                "operational": dict(req["operational"]),
            },
            "policy_ref": {"version": req["policy_version"], "digest": req["policy_digest"]},
            "reversibility": req["reversibility"],
        }
        cer = {
            "cer_version": "0.1", "profile": "cer.k8s.scale/0.1",
            "risk_tier": req["risk_tier"],
            "identity": identity,
            "provenance": {
                "runtime": self.RUNTIME, "runtime_version": self.RUNTIME_VERSION,
                "model_provider": self.MODEL_PROVIDER, "model": self.MODEL,
                "planner": "langgraph.stategraph",
                "objective": (  # deliberately different prose than Ugence
                    f"please bring {args['deployment']} up to {args['replicas']} pods"),
                "reasoning_trace_ref": "langgraph://thread/scale",
                "adapter_version": self.ADAPTER_VERSION,
                "explanation": (
                    f"Graph selected k8s_scale({args['namespace']}/{args['deployment']}"
                    f" -> {args['replicas']})."),
            },
        }
        if req.get("attach_evidence"):
            cer["evidence"] = {"kinds": ["signed_artifact", "simulation"]}
        return cer

    @staticmethod
    def _req_to_state_dict(req: ActuationRequest) -> dict:
        return {
            "cluster": req.cluster, "namespace": req.namespace, "deployment": req.deployment,
            "from_replicas": req.from_replicas, "to_replicas": req.to_replicas,
            "principal": req.principal, "permissions": list(req.permissions),
            "delegator_id": req.delegator_id, "resource_version": req.resource_version,
            "state_hash": req.state_hash, "as_of": req.as_of, "operational": dict(req.operational),
            "policy_version": req.policy_version, "policy_digest": req.policy_digest,
            "correlation_id": req.correlation_id, "sequence_id": req.sequence_id,
            "risk_tier": req.risk_tier, "operation": req.operation,
            "reversibility": req.reversibility, "rollback_ref": req.rollback_ref,
            "attach_evidence": req.attach_evidence,
        }

    def run(self, req: ActuationRequest) -> Dict:
        """Invoke the REAL graph; return the final state (incl. cer, verdict, control)."""
        state = self._app.invoke({
            "messages": [HumanMessage(content=f"scale {req.deployment} to {req.to_replicas}")],
            "request": self._req_to_state_dict(req),
            "cer": None, "verdict": None, "control": None,
        })
        return state

    def propose(self, req: ActuationRequest) -> Dict:
        """Producer interface: run the graph, return the intercepted CER."""
        return self.run(req)["cer"]
