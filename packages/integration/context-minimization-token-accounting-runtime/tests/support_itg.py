"""Neutral test doubles for the CM-TA1 integration suite.

Self-contained fakes — none imports a provider SDK. A `UsageProvider` attaches an
OPAQUE, provider-specific usage mapping to its ToolResult metadata exactly as a real
provider would; the runtime forwards it uninterpreted and the integration's injected
normalizer types it.
"""

from __future__ import annotations

from ugence_agent_runtime.observability.attempts import PROVIDER_USAGE_METADATA_KEY
from ugence_agent_runtime.providers.interfaces import Provider, ToolInvocation, ToolResult
from ugence_agent_runtime.runtime.errors import ProviderExecutionError

from ugence_context_minimization.api import (
    MinimizationMode,
    minimize_context,
)
from ugence_context_minimization.models import (
    Context,
    ContextUnit,
    OracleEvaluation,
)

# A provider-specific neutral usage shape (deliberately NOT the CM field names).
DEFAULT_VENDOR_USAGE = {"prompt_tokens": 2337, "cache_read_tokens": 1500, "completion_tokens": 428}

#: A MappingUsageNormalizer field map for the vendor shape above.
VENDOR_FIELD_MAP = {
    "input_tokens": "prompt_tokens",
    "cached_input_tokens": "cache_read_tokens",
    "output_tokens": "completion_tokens",
    "total_tokens": "total_tokens",
}


class _KeywordOracle:
    KW = ("deploy", "backup", "credential")

    def __init__(self, oracle_id="itg-oracle"):
        self.oracle_id = oracle_id

    def evaluate(self, context, *, evaluation_time=None):
        present = sorted({k for u in context.units for k in self.KW if k in (u.text or "").lower()})
        return OracleEvaluation(
            equivalence_key="kw:" + ",".join(present),
            oracle_id=self.oracle_id,
            contract_version="1.0",
            correlation_id=context.correlation_id,
        )


def sample_minimization_result():
    ctx = Context(
        id="ctx-itg",
        correlation_id="corr-itg",
        units=(
            ContextUnit(id="crit", text="deploy credential anchor", source_type="state_fact"),
            ContextUnit(id="f1", text="filler one two three", source_type="log_event"),
            ContextUnit(id="f2", text="filler four five six", source_type="log_event"),
        ),
    )
    return minimize_context(ctx, oracle=_KeywordOracle(), target_reduction=0.5, evaluation_time=1.0)


class UsageProvider(Provider):
    """Succeeds and attaches an opaque vendor usage mapping."""

    def __init__(self, provider_id="vendor", *, usage=None, ok=True, error=None):
        self.provider_id = provider_id
        self.version = "1.0.0"
        self.calls = 0
        self._usage = DEFAULT_VENDOR_USAGE if usage is None else usage
        self._ok = ok
        self._error = error

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        self.calls += 1
        return ToolResult(
            provider_id=self.provider_id,
            operation=invocation.operation,
            ok=self._ok,
            output={"op": invocation.operation} if self._ok else None,
            error=None if self._ok else (self._error or "declined"),
            metadata={PROVIDER_USAGE_METADATA_KEY: dict(self._usage)},
        )


class FlakyUsageProvider(Provider):
    """Raises for the first ``fail_times`` attempts (no usage), then succeeds with usage."""

    def __init__(self, provider_id="vendor", *, fail_times=1, usage=None):
        self.provider_id = provider_id
        self.version = "1.0.0"
        self.calls = 0
        self._fail_times = fail_times
        self._usage = DEFAULT_VENDOR_USAGE if usage is None else usage

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        self.calls += 1
        if self.calls <= self._fail_times:
            raise ProviderExecutionError("transient", retriable=True)
        return ToolResult(
            provider_id=self.provider_id,
            operation=invocation.operation,
            ok=True,
            output="ok",
            metadata={PROVIDER_USAGE_METADATA_KEY: dict(self._usage)},
        )
