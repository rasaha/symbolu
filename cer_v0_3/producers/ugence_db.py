"""Native Ugence CER V0.3 producer for database.mutation.v1.

Runtime-owned reasoning (understand -> plan -> select tool -> propose); emits the
CER before execution; owns no authorization/token/execution.
"""
from __future__ import annotations

from ..db_actuation import DbActuation, DbContext, assemble_cer


class UgenceDbProducer:
    RUNTIME = "ugence-agent-runtime"
    RUNTIME_VERSION = "0.3.0"
    MODEL = "mistral-cg"
    MODEL_PROVIDER = "ugence"

    def _objective(self, act: DbActuation) -> str:
        return (f"apply {act.sql_operation} to {act.schema}.{act.table} "
                f"on {act.connection_ref} (~{act.estimated_rows} rows)")

    def propose(self, ctx: DbContext, act: DbActuation) -> dict:
        provenance = {
            "runtime": self.RUNTIME, "runtime_version": self.RUNTIME_VERSION,
            "model_provider": self.MODEL_PROVIDER, "model": self.MODEL,
            "planner": "ugence.deterministic.htn", "objective": self._objective(act),
            "reasoning_trace_ref": "ugence://trace", "adapter_version": "native",
            "explanation": f"Proposed {act.PROFILE} on {act.schema}.{act.table}.",
        }
        return assemble_cer(ctx, act.actuation_block(), provenance)
