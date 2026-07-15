"""Generic minimal tool-runtime adapter for database.mutation.v1 (second producer).

Models an independent runtime path distinct from the native Ugence producer: a
deterministic tool-runtime executes a one-step plan that calls a ``db.mutation``
tool; the adapter INTERCEPTS the pending tool call before it executes, reconstructs
the CER actuation from the intercepted arguments, and emits the CER with its own
provenance. It never runs the tool (governed mode). This is runtime-producer
independence — a different code path stamping different provenance — separate from
the clean-room's implementation independence.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List

from ..db_actuation import DbActuation, DbContext, actuation_block_from_tool_args, assemble_cer


class _ToolCall:
    """A pending tool call the runtime produced but has NOT executed."""
    def __init__(self, name: str, args: Dict[str, Any]):
        self.name = name
        self.args = args


class _MiniToolRuntime:
    """A tiny deterministic tool-runtime: a plan is a list of tool calls; the runtime
    yields each pending call to an interceptor before it would execute."""
    def __init__(self, tools: Dict[str, Callable[[Dict[str, Any]], Any]]):
        self.tools = tools
        self.executed: List[str] = []

    def run(self, plan: List[_ToolCall], interceptor) -> Any:
        for call in plan:
            verdict = interceptor(call)          # governance hook (pre-execution)
            if verdict is not None:
                return verdict                    # intercepted -> tool NOT executed
            self.executed.append(call.name)       # (only reached in ungoverned mode)
            self.tools[call.name](call.args)
        return None


class ToolRuntimeDbAdapter:
    RUNTIME = "generic-tool-runtime"
    RUNTIME_VERSION = "1.0.0"
    MODEL = "planner-stub"
    MODEL_PROVIDER = "generic"

    def propose(self, ctx: DbContext, act: DbActuation) -> dict:
        captured: Dict[str, Any] = {}

        def _db_mutation_tool(args):  # the real tool — never called in governed mode
            raise AssertionError("db.mutation tool must not execute before governance")

        runtime = _MiniToolRuntime({"db.mutation": _db_mutation_tool})
        plan = [_ToolCall("db.mutation", act.tool_args())]

        def _intercept(call: _ToolCall):
            if call.name == "db.mutation":
                captured.update(call.args)
                return "INTERCEPTED"
            return None

        runtime.run(plan, _intercept)
        assert not runtime.executed, "tool executed before governance (bypass!)"

        actuation_block = actuation_block_from_tool_args(captured)
        provenance = {
            "runtime": self.RUNTIME, "runtime_version": self.RUNTIME_VERSION,
            "model_provider": self.MODEL_PROVIDER, "model": self.MODEL,
            "planner": "generic.toolcall.intercept",
            "objective": f"tool db.mutation on {act.schema}.{act.table}",
            "adapter_version": "tool-runtime-intercept",
            "explanation": "Intercepted pending db.mutation tool call before execution.",
        }
        return assemble_cer(ctx, actuation_block, provenance)
