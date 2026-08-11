"""Provider execution with deterministic retry and timeout accounting.

This isolates the "invoke a provider, honoring retry and timeout" mechanics from the
engine's coordination logic. It performs NO governance evaluation — by the time it
runs, the governance boundary has already returned CLEAR for this transition.

Attempt telemetry (additive): every actual ``provider.execute`` invocation — success,
expected failure, timeout, provider error, or raw exception — emits exactly one neutral
:class:`~ugence_agent_runtime.observability.attempts.ProviderAttempt` to the optional
observer, carrying the runtime-authoritative attempt number. Retried attempts are never
collapsed into the final attempt. The runtime forwards a provider's opaque usage mapping
verbatim and never interprets provider-specific token fields.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional

from ..models.results import FailureCategory, RuntimeFailure
from ..observability.attempts import (
    PROVIDER_USAGE_METADATA_KEY,
    AttemptContext,
    AttemptObserver,
    ProviderAttempt,
    ProviderAttemptStatus,
)
from ..providers.interfaces import Provider, ToolInvocation, ToolResult
from ..providers.registry import ProviderRegistry
from .errors import ProviderExecutionError, ProviderNotFoundError
from .retry import RetryPolicy
from .timeout import exceeded as _timeout_exceeded


@dataclass(frozen=True)
class ExecutionOutcome:
    ok: bool
    attempts: int
    result: Optional[ToolResult] = None
    failure: Optional[RuntimeFailure] = None


def _neutral_usage(result: Optional[ToolResult]) -> Optional[Mapping[str, Any]]:
    """Extract the provider's OPAQUE usage mapping from a result's metadata, if any.

    The runtime never interprets the contents; it only checks the value is a mapping so
    a malformed usage blob is dropped (treated as unknown) rather than forwarded as a
    non-mapping. Absence means unknown — never fabricated as empty usage.
    """
    if result is None:
        return None
    usage = result.metadata.get(PROVIDER_USAGE_METADATA_KEY) if result.metadata else None
    if isinstance(usage, Mapping):
        return usage
    return None


def _observe(
    observer: Optional[AttemptObserver],
    context: Optional[AttemptContext],
    invocation: ToolInvocation,
    attempt_number: int,
    status: ProviderAttemptStatus,
    *,
    ok: bool,
    result: Optional[ToolResult] = None,
    failure_category: Optional[str] = None,
) -> None:
    """Emit one neutral attempt record. A raising observer never breaks execution."""
    if observer is None:
        return
    ctx = context or AttemptContext()
    attempt = ProviderAttempt(
        provider_id=invocation.provider_id,
        operation=invocation.operation,
        attempt_number=attempt_number,
        status=status,
        ok=ok,
        provider_invoked=True,
        workflow_id=ctx.workflow_id,
        instance_id=ctx.instance_id,
        task_id=ctx.task_id or invocation.correlation_id,
        correlation_id=ctx.correlation_id or invocation.correlation_id,
        neutral_usage=_neutral_usage(result),
        failure_category=failure_category,
    )
    try:
        observer.on_attempt(attempt)
    except Exception:  # noqa: BLE001 - telemetry must never break execution
        pass


def execute_with_policy(
    registry: ProviderRegistry,
    invocation: ToolInvocation,
    retry_policy: RetryPolicy,
    clock: Callable[[], float],
    timeout: Optional[float],
    task_id: str,
    *,
    attempt_observer: Optional[AttemptObserver] = None,
    attempt_context: Optional[AttemptContext] = None,
) -> ExecutionOutcome:
    """Invoke the selected provider, applying retry and timeout deterministically.

    Timeouts are not retried (fail closed). Provider errors are retried up to the
    policy's ``max_attempts`` when marked retriable. Every actual invocation emits one
    neutral attempt to ``attempt_observer`` (when supplied) with the runtime's
    authoritative ``attempt_number``; a provider-not-found emits none (the provider was
    never invoked).
    """
    provider: Provider
    try:
        provider = registry.get(invocation.provider_id)
    except ProviderNotFoundError as exc:
        # No attempt: the provider was never invoked.
        return ExecutionOutcome(
            ok=False,
            attempts=0,
            failure=RuntimeFailure(
                category=FailureCategory.PROVIDER_NOT_FOUND,
                message=str(exc),
                task_id=task_id,
            ),
        )

    attempts = 0
    last_failure: Optional[RuntimeFailure] = None
    while True:
        attempts += 1
        started_at = clock()
        try:
            result = provider.execute(invocation)
        except ProviderExecutionError as exc:
            last_failure = RuntimeFailure(
                category=FailureCategory.PROVIDER_ERROR,
                message=str(exc),
                task_id=task_id,
            )
            _observe(attempt_observer, attempt_context, invocation, attempts,
                     ProviderAttemptStatus.EXCEPTION, ok=False,
                     failure_category=FailureCategory.PROVIDER_ERROR.value)
            if exc.retriable and retry_policy.should_retry(attempts):
                continue
            return ExecutionOutcome(ok=False, attempts=attempts, failure=last_failure)
        except Exception as exc:  # noqa: BLE001 - wrap raw backend errors
            last_failure = RuntimeFailure(
                category=FailureCategory.PROVIDER_ERROR,
                message=f"{type(exc).__name__}: {exc}",
                task_id=task_id,
            )
            _observe(attempt_observer, attempt_context, invocation, attempts,
                     ProviderAttemptStatus.EXCEPTION, ok=False,
                     failure_category=FailureCategory.PROVIDER_ERROR.value)
            if retry_policy.should_retry(attempts):
                continue
            return ExecutionOutcome(ok=False, attempts=attempts, failure=last_failure)

        # Timeout accounting (deterministic via injected clock). Not retried.
        if timeout is not None and _timeout_exceeded(started_at, clock(), timeout):
            _observe(attempt_observer, attempt_context, invocation, attempts,
                     ProviderAttemptStatus.TIMEOUT, ok=False, result=result,
                     failure_category=FailureCategory.TIMEOUT.value)
            return ExecutionOutcome(
                ok=False,
                attempts=attempts,
                result=result,
                failure=RuntimeFailure(
                    category=FailureCategory.TIMEOUT,
                    message=f"task {task_id} exceeded timeout {timeout}",
                    task_id=task_id,
                ),
            )

        if result.ok:
            _observe(attempt_observer, attempt_context, invocation, attempts,
                     ProviderAttemptStatus.SUCCEEDED, ok=True, result=result)
            return ExecutionOutcome(ok=True, attempts=attempts, result=result)

        # Expected provider failure reported by value.
        last_failure = RuntimeFailure(
            category=FailureCategory.PROVIDER_ERROR,
            message=result.error or "provider reported failure",
            task_id=task_id,
            detail={"failure_category": result.failure_category} if result.failure_category else {},
        )
        _observe(attempt_observer, attempt_context, invocation, attempts,
                 ProviderAttemptStatus.FAILED, ok=False, result=result,
                 failure_category=FailureCategory.PROVIDER_ERROR.value)
        if retry_policy.should_retry(attempts):
            continue
        return ExecutionOutcome(ok=False, attempts=attempts, result=result, failure=last_failure)
