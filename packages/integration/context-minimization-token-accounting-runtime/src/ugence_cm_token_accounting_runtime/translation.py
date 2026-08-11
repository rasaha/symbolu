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


def _require_identity(value: object, name: str) -> str:
    """Require a stable, non-ambiguous identity component (F3).

    Rejects ``None``, non-str, empty, and whitespace-only values rather than falling
    back to a placeholder that would collide across distinct requests. Deterministic —
    reads no clock and generates no random id.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"{name} must be a non-empty, non-whitespace str for deterministic "
            f"attempt-id derivation (got {value!r}); an accounting attempt id must never "
            "be derived from missing or ambiguous runtime identity"
        )
    return value


def _attempt_id_for(
    logical_request_id: object, instance_id: object, task_id: object, attempt_number: object
) -> str:
    """Deterministic, collision-resistant attempt id from the FULL logical-request identity.

    Binds ``logical_request_id`` (not just instance/task) so two distinct logical requests
    can never produce the same id even if instance/task identity coincides. Components are
    length-prefixed (a prefix-free encoding), so no two distinct identity tuples can map to
    the same string regardless of which characters the ids contain. No wall-clock, no
    randomness, no provider-controlled request id is used as internal attempt authority.
    """
    lr = _require_identity(logical_request_id, "logical_request_id")
    inst = _require_identity(instance_id, "instance_id")
    task = _require_identity(task_id, "task_id")
    if isinstance(attempt_number, bool) or not isinstance(attempt_number, int) or attempt_number < 1:
        raise ValueError(f"attempt_number must be an int >= 1 (got {attempt_number!r})")

    def _seg(s: str) -> str:
        return f"{len(s)}|{s}"

    return "cmta1/" + "".join(_seg(x) for x in (lr, inst, task, str(attempt_number)))


def derive_attempt_id(attempt: ProviderAttempt, *, logical_request_id: str) -> str:
    """A deterministic, collision-resistant attempt id from runtime + logical-request identity.

    ``logical_request_id`` is REQUIRED (the minimum stable business identity); ``attempt``
    must carry non-empty ``instance_id`` and ``task_id``. Missing/empty/whitespace identity
    is rejected — never replaced with a placeholder. No clock, no randomness.
    """
    return _attempt_id_for(
        logical_request_id, attempt.instance_id, attempt.task_id, attempt.attempt_number
    )


def translate_attempt(
    prepared: PreparedApiCall,
    attempt: ProviderAttempt,
    *,
    normalizer: Optional[UsageNormalizer] = None,
    attempt_id: Optional[str] = None,
    retry_of_attempt_id: Optional[str] = None,
    sink=None,
) -> ApiCallTokenRecord:
    """Translate one Agent Runtime :class:`ProviderAttempt` into an :class:`ApiCallTokenRecord`.

    * Uses the injected ``normalizer`` to type the attempt's opaque ``neutral_usage``; a
      ``None`` result (or no usage, or no normalizer) records the attempt as usage-unavailable
      with a status-derived reason — never fabricated zero usage.
    * Attempt identity (F3): when ``attempt_id`` is omitted, both the attempt id and — for a
      retry (``attempt_number > 1``) — its ``retry_of_attempt_id`` are derived from the SAME
      scheme (bound to ``prepared.logical_request_id`` + instance/task), rejecting missing or
      ambiguous identity. When ``attempt_id`` is supplied explicitly, ``retry_of_attempt_id``
      is NEVER reconstructed from the derivation scheme (it would cross identity schemes): a
      retry then REQUIRES an explicit ``retry_of_attempt_id``, and a non-retry must not carry
      one. Supplying ``retry_of_attempt_id`` while deriving ``attempt_id`` is rejected.
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

    is_retry = attempt.attempt_number > 1
    if attempt_id is None:
        # Derived scheme: id + retry_of both come from the same derivation.
        if retry_of_attempt_id is not None:
            raise ValueError(
                "retry_of_attempt_id may only be supplied with an explicit attempt_id; "
                "when deriving, retry linkage is derived from the same scheme"
            )
        aid = derive_attempt_id(attempt, logical_request_id=prepared.logical_request_id)
        retry_of = (
            _attempt_id_for(
                prepared.logical_request_id, attempt.instance_id, attempt.task_id,
                attempt.attempt_number - 1,
            )
            if is_retry
            else None
        )
    else:
        # Explicit id: never cross identity schemes to reconstruct retry linkage.
        aid = _require_identity(attempt_id, "attempt_id")
        if is_retry and retry_of_attempt_id is None:
            raise ValueError(
                "an explicit attempt_id for a retry (attempt_number > 1) requires an explicit "
                "retry_of_attempt_id — the derivation scheme must not be used to reconstruct it"
            )
        if not is_retry and retry_of_attempt_id is not None:
            raise ValueError(
                "attempt_number 1 is not a retry; retry_of_attempt_id must be None"
            )
        retry_of = retry_of_attempt_id

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
