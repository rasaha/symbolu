"""Translate neutral Agent Runtime attempt telemetry into token-accounting records.

The Agent Runtime emits a neutral :class:`ProviderAttempt` per actual provider
invocation and forwards a provider's *opaque* usage mapping without interpreting it.
Context Minimization owns the typed :class:`ApiCallTokenRecord`. This module is the
one-way bridge between them:

    ProviderAttempt  --(injected UsageNormalizer)-->  ProviderTokenUsage
                     --(a linked PreparedApiCall)-->  ApiCallTokenRecord  --> TokenAccountingSink

The provider-specific step — turning ``{"prompt_tokens": ...}`` into typed fields — is an
**injected** :class:`UsageNormalizer`. This package ships only a configurable, mechanical
:class:`MappingUsageNormalizer`; a real vendor SDK normalizer lives OUTSIDE this package.
The runtime attempt carries only a per-task ``attempt_number``, so this module derives a
deterministic, globally-unique ``attempt_id`` from the workflow/instance/task identity — no
wall clock, no random id — keeping deterministic replay exact.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Protocol, runtime_checkable

from ugence_agent_runtime.observability.attempts import (
    ProviderAttempt,
    ProviderAttemptStatus,
)
from ugence_context_minimization.api import (
    ApiCallTokenRecord,
    AttemptStatus,
    PreparedApiCall,
    ProviderTokenUsage,
    UsageAvailability,
    reconcile_api_call_measurement,
)

# Runtime status -> accounting status (both neutral enums; a total, explicit mapping).
_STATUS_MAP: Dict[ProviderAttemptStatus, AttemptStatus] = {
    ProviderAttemptStatus.SUCCEEDED: AttemptStatus.SUCCEEDED,
    ProviderAttemptStatus.FAILED: AttemptStatus.FAILED,
    ProviderAttemptStatus.TIMEOUT: AttemptStatus.TIMEOUT,
    ProviderAttemptStatus.EXCEPTION: AttemptStatus.EXCEPTION,
}


@runtime_checkable
class UsageNormalizer(Protocol):
    """Turns a provider's OPAQUE neutral usage mapping into typed :class:`ProviderTokenUsage`.

    Provider-specific by nature. Return ``None`` when the mapping carries no usable usage
    (the attempt is then recorded as usage-unavailable — never fabricated as zero). MUST
    NOT invent counts the provider did not report.
    """

    def normalize(self, neutral_usage: Mapping[str, Any]) -> Optional[ProviderTokenUsage]: ...


class MappingUsageNormalizer:
    """A mechanical, configurable normalizer — NOT a provider SDK.

    Maps neutral-mapping keys to :class:`ProviderTokenUsage` fields by an explicit
    field map (e.g. ``{"input_tokens": "prompt_tokens", "output_tokens": "completion_tokens"}``).
    Missing keys stay ``None`` (unknown, never zero); a present value flows through the
    strict :class:`ProviderTokenUsage` validators (bool/float/NaN/inf/str rejected).
    ``schema_name`` / ``adapter_id`` / ``adapter_version`` label the provenance.
    """

    _FIELDS = (
        "input_tokens",
        "cached_input_tokens",
        "cache_write_input_tokens",
        "output_tokens",
        "reasoning_tokens",
        "total_tokens",
    )

    def __init__(
        self,
        field_map: Mapping[str, str],
        *,
        schema_name: Optional[str] = None,
        adapter_id: Optional[str] = None,
        adapter_version: Optional[str] = None,
        request_id_key: Optional[str] = None,
    ) -> None:
        unknown = set(field_map) - set(self._FIELDS)
        if unknown:
            raise ValueError(f"MappingUsageNormalizer: unknown target fields {sorted(unknown)}")
        self._map = dict(field_map)
        self._schema = schema_name
        self._adapter_id = adapter_id
        self._adapter_version = adapter_version
        self._request_id_key = request_id_key

    def normalize(self, neutral_usage: Mapping[str, Any]) -> Optional[ProviderTokenUsage]:
        kwargs: Dict[str, Any] = {}
        for target, source in self._map.items():
            if source in neutral_usage and neutral_usage[source] is not None:
                kwargs[target] = neutral_usage[source]
        if not kwargs:
            return None  # nothing usable -> unknown, not zero
        req_id = None
        if self._request_id_key and neutral_usage.get(self._request_id_key) is not None:
            req_id = str(neutral_usage[self._request_id_key])
        return ProviderTokenUsage(
            provider_request_id=req_id,
            usage_schema=self._schema,
            adapter_id=self._adapter_id,
            adapter_version=self._adapter_version,
            **kwargs,
        )


def derive_attempt_id(attempt: ProviderAttempt) -> str:
    """A deterministic, globally-unique attempt id from runtime identity (no clock/random)."""
    inst = attempt.instance_id or "?"
    task = attempt.task_id or "?"
    return f"{inst}:{task}:{attempt.attempt_number}"


def translate_attempt(
    prepared: PreparedApiCall,
    attempt: ProviderAttempt,
    *,
    normalizer: Optional[UsageNormalizer] = None,
    attempt_id: Optional[str] = None,
    sink=None,
) -> ApiCallTokenRecord:
    """Translate one Agent Runtime :class:`ProviderAttempt` into an :class:`ApiCallTokenRecord`.

    * Uses the injected ``normalizer`` to type the attempt's opaque ``neutral_usage``; a
      ``None`` result (or no usage, or no normalizer) records the attempt as usage-unavailable
      with a status-derived reason — never fabricated zero usage.
    * Preserves the runtime-authoritative ``attempt_number`` and links a retry to its
      predecessor (``retry_of_attempt_id``) deterministically.
    * Delegates to :func:`reconcile_api_call_measurement`, so all strict token-count and
      attempt-identity validation (and the byte-identical idempotent-replay contract on the
      ``sink``) applies unchanged.
    """
    status = _STATUS_MAP.get(attempt.status)
    if status is None:  # defensive: an unknown runtime status is never silently mapped
        raise ValueError(f"unmapped ProviderAttemptStatus {attempt.status!r}")

    usage: Optional[ProviderTokenUsage] = None
    unavailable_reason: Optional[str] = None
    if attempt.neutral_usage is not None and normalizer is not None:
        usage = normalizer.normalize(attempt.neutral_usage)
    if usage is None or not usage.has_any:
        usage = None
        if attempt.status is ProviderAttemptStatus.SUCCEEDED:
            unavailable_reason = "provider reported no usage"
        else:
            unavailable_reason = f"attempt {attempt.status.value.lower()}; no usage evidence"

    aid = attempt_id or derive_attempt_id(attempt)
    retry_of = None
    if attempt.attempt_number > 1:
        retry_of = f"{attempt.instance_id or '?'}:{attempt.task_id or '?'}:{attempt.attempt_number - 1}"

    return reconcile_api_call_measurement(
        prepared,
        attempt_id=aid,
        attempt_number=attempt.attempt_number,
        status=status,
        provider_invoked=attempt.provider_invoked,
        provider_usage=usage,
        usage_unavailable_reason=unavailable_reason,
        retry_of_attempt_id=retry_of,
        sink=sink,
    )
