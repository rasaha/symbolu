"""Provider execution with deterministic retry and timeout accounting.

This isolates the "invoke a provider, honoring retry and timeout" mechanics from the
engine's coordination logic. It performs NO governance evaluation — by the time it
runs, the governance boundary has already returned CLEAR for this transition.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from ..models.results import FailureCategory, RuntimeFailure
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


def execute_with_policy(
    registry: ProviderRegistry,
    invocation: ToolInvocation,
    retry_policy: RetryPolicy,
    clock: Callable[[], float],
    timeout: Optional[float],
    task_id: str,
) -> ExecutionOutcome:
    """Invoke the selected provider, applying retry and timeout deterministically.

    Timeouts are not retried (fail closed). Provider errors are retried up to the
    policy's ``max_attempts`` when marked retriable.
    """
    provider: Provider
    try:
        provider = registry.get(invocation.provider_id)
    except ProviderNotFoundError as exc:
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
            if exc.retriable and retry_policy.should_retry(attempts):
                continue
            return ExecutionOutcome(ok=False, attempts=attempts, failure=last_failure)
        except Exception as exc:  # noqa: BLE001 - wrap raw backend errors
            last_failure = RuntimeFailure(
                category=FailureCategory.PROVIDER_ERROR,
                message=f"{type(exc).__name__}: {exc}",
                task_id=task_id,
            )
            if retry_policy.should_retry(attempts):
                continue
            return ExecutionOutcome(ok=False, attempts=attempts, failure=last_failure)

        # Timeout accounting (deterministic via injected clock). Not retried.
        if timeout is not None and _timeout_exceeded(started_at, clock(), timeout):
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
            return ExecutionOutcome(ok=True, attempts=attempts, result=result)

        # Expected provider failure reported by value.
        last_failure = RuntimeFailure(
            category=FailureCategory.PROVIDER_ERROR,
            message=result.error or "provider reported failure",
            task_id=task_id,
            detail={"failure_category": result.failure_category} if result.failure_category else {},
        )
        if retry_policy.should_retry(attempts):
            continue
        return ExecutionOutcome(ok=False, attempts=attempts, result=result, failure=last_failure)
