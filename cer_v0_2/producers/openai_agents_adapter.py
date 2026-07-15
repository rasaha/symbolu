"""OpenAI Agents SDK CER V0.2 adapter — REAL agents runtime, both profiles.

Integration:
  * a deterministic model stub emits a real ``ResponseFunctionToolCall`` for the
    requested profile's tool (no live model API);
  * the REAL ``Runner`` loop runs, parses it, and creates a real ``ToolCallItem``
    (the runtime's pending action object);
  * the governed tools are shadow no-ops (they never actuate);
  * the adapter reads the pending ToolCallItem and normalizes it to CER.

The real event loop executes, the real tool-call interception mechanism runs, and
the runtime genuinely creates the pending action object — not a hand-authored
object. No OpenAI-Agents-specific logic in CER/ActionGate/ACP.
"""
from __future__ import annotations

import asyncio
import json
from typing import Union

from agents import Agent, Runner, RunConfig, function_tool
from agents.items import ModelResponse
from agents.models.interface import Model
from agents.usage import Usage
from openai.types.responses import (ResponseFunctionToolCall, ResponseOutputMessage,
                                     ResponseOutputText)

from ..actuation import (EnvelopeContext, RolloutActuation, ScaleActuation,
                         actuation_block_from_tool_args, assemble_cer)

Actuation = Union[ScaleActuation, RolloutActuation]


@function_tool
def k8s_scale(namespace: str, deployment: str, replicas: int) -> str:
    """Scale a deployment (governed; shadow no-op)."""
    return "PENDING_GOVERNANCE"


@function_tool
def k8s_rollout(namespace: str, deployment: str, image_digest: str) -> str:
    """Roll out a new image to a deployment (governed; shadow no-op)."""
    return "PENDING_GOVERNANCE"


class _StubModel(Model):
    """Deterministic model: emits the requested tool call once, then a final message."""

    def __init__(self, tool_name: str, tool_args: dict):
        self._tool_name = tool_name
        self._tool_args = tool_args
        self._calls = 0

    async def get_response(self, *a, **k):
        self._calls += 1
        if self._calls == 1:
            tc = ResponseFunctionToolCall(
                name=self._tool_name, arguments=json.dumps(self._tool_args),
                call_id="call_1", type="function_call", id="fc_1")
            return ModelResponse(output=[tc], usage=Usage(), response_id="r1")
        msg = ResponseOutputMessage(
            id="m1", role="assistant", status="completed",
            content=[ResponseOutputText(text="done", type="output_text", annotations=[])],
            type="message")
        return ModelResponse(output=[msg], usage=Usage(), response_id="r2")

    async def stream_response(self, *a, **k):  # pragma: no cover - not used
        raise NotImplementedError


class OpenAIAgentsCERAdapter:
    RUNTIME = "openai-agents"
    RUNTIME_VERSION = "0.18.2"
    MODEL = "stub-deterministic"
    MODEL_PROVIDER = "openai-agents-sdk"

    def _tool_call_args(self, act: Actuation) -> dict:
        # the physically-varying fields the model puts in the tool call
        if isinstance(act, ScaleActuation):
            return {"namespace": act.namespace, "deployment": act.deployment,
                    "replicas": act.to_replicas}
        return {"namespace": act.namespace, "deployment": act.deployment,
                "image_digest": act.image_digest}

    def propose(self, ctx: EnvelopeContext, act: Actuation) -> dict:
        tool_name = "k8s_scale" if isinstance(act, ScaleActuation) else "k8s_rollout"
        model = _StubModel(tool_name, self._tool_call_args(act))
        agent = Agent(name="k8s-agent", tools=[k8s_scale, k8s_rollout], model=model)
        res = asyncio.run(Runner.run(agent, input=f"execute {act.PROFILE}",
                                     run_config=RunConfig(tracing_disabled=True)))
        # read the REAL pending tool call the runtime created
        pending = None
        for item in res.new_items:
            if item.__class__.__name__ == "ToolCallItem":
                raw = item.raw_item
                pending = {"name": raw.name, "args": json.loads(raw.arguments)}
                break
        if pending is None:
            raise RuntimeError("openai-agents runtime produced no tool call")
        # merge full identity args (context supplies fields not in the tool call)
        args = dict(pending["args"])
        full = act.tool_args()
        for k, v in full.items():
            args.setdefault(k, v)
        block = actuation_block_from_tool_args(act.PROFILE, args)
        provenance = {
            "runtime": self.RUNTIME, "runtime_version": self.RUNTIME_VERSION,
            "model_provider": self.MODEL_PROVIDER, "model": self.MODEL,
            "planner": "openai-agents.runner",
            "objective": f"agent requested {act.PROFILE} via {pending['name']}",
            "reasoning_trace_ref": "openai-agents://run", "adapter_version": "cer-oai/0.2",
            "explanation": f"Runner dispatched {pending['name']}.",
        }
        return assemble_cer(act.PROFILE, ctx, block, provenance)
