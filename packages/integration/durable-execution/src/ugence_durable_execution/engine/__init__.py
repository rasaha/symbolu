"""Engine implementations of :class:`DurableExecutionAdapter`.

DBOS today (ADR §2 R-1); Temporal later, behind the same Protocols and with no change
to anything under ``packages/runtime/agent-runtime`` (ADR §7).
"""
from .dbos_engine import DbosExecutionAdapter, DbosRuntimeHost, StepOutcome

__all__ = ["DbosExecutionAdapter", "DbosRuntimeHost", "StepOutcome"]
