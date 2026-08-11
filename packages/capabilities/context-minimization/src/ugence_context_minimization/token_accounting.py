"""Neutral, deterministic token-accounting contracts (stdlib-only).

Context Minimization measures **how much context was safely removed**. This module
adds the two *other* measurements a token-accounting audit needs, keeping all three
distinct so a single field is never overloaded with two meanings:

    A. Context measurement          — MinimizationResult.original_tokens /
                                      resulting_tokens / achieved_reduction (owned by
                                      the minimizer; NOT re-derived here).
    B. Complete-request estimate    — RequestTokenEstimate: the estimated input-token
                                      size of the *complete serialized model request*
                                      (system + messages + minimized context + tool
                                      definitions + schemas + provider wrappers), as
                                      counted by an INJECTED counter. The core never
                                      implements a provider tokenizer.
    C. Provider-reported usage      — ProviderTokenUsage: what the provider reported
                                      consuming *after* an attempt. Authoritative for
                                      the API response being reconciled; it never
                                      overwrites the pre-call estimate, and it is NOT
                                      an invoice.

An :class:`ApiCallTokenRecord` binds one *actual provider attempt* to all three,
plus the business/attempt attribution, with a domain-separated deterministic
fingerprint over its stable auditable fields. A :class:`LogicalRequestTokenSummary`
aggregates every attempt of one logical (business) request.

Boundary discipline (unchanged): this module is stdlib-only, domain-neutral, and
extractive of *facts already measured elsewhere*. It implements NO provider
tokenizer, NO network / database / filesystem persistence, NO model SDK, and NO
pricing authority. It reads no wall clock and generates no random ids — every id is
caller-supplied so deterministic replay is exact.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Optional, Protocol, Sequence, runtime_checkable

from .errors import InvalidRequestError, InvalidUnitError
from .models import MinimizationResult, default_token_count
from .numeric import is_token_count

# --------------------------------------------------------------------------- #
# Domain separators (each its own versioned namespace; never collides).
# --------------------------------------------------------------------------- #
_RECORD_DOMAIN = b"ugence-context-minimization/api-call/1\x00"
_SUMMARY_DOMAIN = b"ugence-context-minimization/logical-request/1\x00"


def _canonical_json(payload: Any) -> bytes:
    """Canonical JSON for fingerprinting: sorted keys, no whitespace, non-finite
    numbers REJECTED (``allow_nan=False``) so a digest can never contain NaN/Infinity."""
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _digest(domain: bytes, payload: Any) -> str:
    return "sha256:" + hashlib.sha256(domain + _canonical_json(payload)).hexdigest()


def _opt_token(value: Any, name: str) -> Optional[int]:
    """Validate an OPTIONAL provider-reported token field.

    ``None`` means *unknown* and is preserved verbatim — never fabricated as zero. A
    present value must be a non-negative ``int`` (never ``bool``, ``float``, NaN,
    ``inf``, or ``str``); anything else fails closed with :class:`InvalidUnitError`.
    """
    if value is None:
        return None
    if not is_token_count(value):
        raise InvalidUnitError(
            f"{name} must be a non-negative int or None (unknown), got {value!r}"
        )
    return value


def _req_token(value: Any, name: str) -> int:
    if not is_token_count(value):
        raise InvalidRequestError(f"{name} must be a non-negative int, got {value!r}")
    return value


def _opt_str(value: Any, name: str) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise InvalidRequestError(f"{name} must be a non-empty str or None, got {value!r}")
    return value


def _req_str(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise InvalidRequestError(f"{name} must be a non-empty str, got {value!r}")
    return value


# --------------------------------------------------------------------------- #
# Enumerations.
# --------------------------------------------------------------------------- #
class TokenCountBasis(str, Enum):
    """How a token count was obtained — its provenance, never assumed exact.

    The default word/punctuation counter is ``DEFAULT_APPROXIMATE`` and MUST NOT be
    presented as exact provider tokenization.
    """

    #: The caller supplied the count directly (e.g. from its own tokenizer).
    CALLER_SUPPLIED = "CALLER_SUPPLIED"
    #: An injected :class:`RequestTokenCounter` produced the count.
    INJECTED_COUNTER = "INJECTED_COUNTER"
    #: The neutral stdlib word/punctuation counter produced the count. APPROXIMATE.
    DEFAULT_APPROXIMATE = "DEFAULT_APPROXIMATE"
    #: Some components caller-supplied, others counted by an injected/default counter.
    MIXED = "MIXED"
    #: The provider reported the count after an attempt (post-call, authoritative for
    #: the response being reconciled).
    PROVIDER_REPORTED = "PROVIDER_REPORTED"
    #: The basis is not known.
    UNKNOWN = "UNKNOWN"


class AttemptStatus(str, Enum):
    """The disposition of ONE actual provider attempt."""

    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    EXCEPTION = "EXCEPTION"


class UsageAvailability(str, Enum):
    """Whether provider-reported usage exists for an attempt, and why not when absent.

    Missing usage is *unknown*, never zero. A failed/exception attempt with no usage
    is ``UNAVAILABLE_*`` — it must NOT be recorded as zero consumption.
    """

    AVAILABLE = "AVAILABLE"
    #: The attempt completed but the provider reported no usage.
    UNAVAILABLE_NOT_REPORTED = "UNAVAILABLE_NOT_REPORTED"
    #: The attempt errored/timed out and no trustworthy usage evidence exists.
    UNAVAILABLE_PROVIDER_ERROR = "UNAVAILABLE_PROVIDER_ERROR"
    #: Reason not otherwise classified.
    UNAVAILABLE_UNKNOWN = "UNAVAILABLE_UNKNOWN"


# --------------------------------------------------------------------------- #
# B. Complete-request estimate.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class RequestComponents:
    """A neutral, text-only description of the complete request to be estimated.

    The core applies NO provider tokenizer to these — an injected
    :class:`RequestTokenCounter` (or the transparent default) counts them. Callers who
    already know exact per-component counts should build a :class:`RequestTokenEstimate`
    directly instead.
    """

    system_text: str = ""
    message_texts: tuple[str, ...] = ()
    #: The minimized context. Supply EITHER its text (to be counted) or a precomputed
    #: token count (e.g. ``MinimizationResult.resulting_tokens``). If both are given the
    #: precomputed count wins and the text is ignored for counting.
    minimized_context_text: Optional[str] = None
    minimized_context_tokens: Optional[int] = None
    tool_definition_texts: tuple[str, ...] = ()
    schema_texts: tuple[str, ...] = ()
    #: Number of non-text inputs (images, audio, …). The stdlib counter cannot tokenize
    #: these, so their presence marks the estimate's coverage incomplete.
    image_count: int = 0
    other_non_text_note: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "message_texts", tuple(self.message_texts))
        object.__setattr__(self, "tool_definition_texts", tuple(self.tool_definition_texts))
        object.__setattr__(self, "schema_texts", tuple(self.schema_texts))
        if self.minimized_context_tokens is not None and not is_token_count(
            self.minimized_context_tokens
        ):
            raise InvalidRequestError("minimized_context_tokens must be a non-negative int or None")
        if not is_token_count(self.image_count):
            raise InvalidRequestError("image_count must be a non-negative int")


@dataclass(frozen=True)
class RequestTokenEstimate:
    """The estimated input-token size of the COMPLETE serialized model request.

    This is measurement (B): distinct from the minimized-context count (A) and from
    provider-reported usage (C). It is an *estimate*; whether it is exact depends
    entirely on ``basis`` and the injected counter.
    """

    estimated_input_tokens: int
    counter_id: str
    counter_version: str
    basis: TokenCountBasis
    model_id: Optional[str] = None
    provider_id: Optional[str] = None
    covers_tools: bool = False
    covers_schemas: bool = False
    covers_images: bool = False
    covers_non_text: bool = False
    #: Why coverage is incomplete (e.g. "images not tokenized by stdlib counter").
    incomplete_reason: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "estimated_input_tokens", _req_token(self.estimated_input_tokens, "estimated_input_tokens")
        )
        object.__setattr__(self, "counter_id", _req_str(self.counter_id, "counter_id"))
        object.__setattr__(self, "counter_version", _req_str(self.counter_version, "counter_version"))
        if not isinstance(self.basis, TokenCountBasis):
            raise InvalidRequestError("basis must be a TokenCountBasis")
        object.__setattr__(self, "model_id", _opt_str(self.model_id, "model_id"))
        object.__setattr__(self, "provider_id", _opt_str(self.provider_id, "provider_id"))
        for flag in ("covers_tools", "covers_schemas", "covers_images", "covers_non_text"):
            if not isinstance(getattr(self, flag), bool):
                raise InvalidRequestError(f"{flag} must be a bool")
        object.__setattr__(self, "incomplete_reason", _opt_str(self.incomplete_reason, "incomplete_reason"))

    @property
    def is_approximate(self) -> bool:
        """True unless the basis is an exact caller/injected count with full coverage."""
        if self.basis in (TokenCountBasis.DEFAULT_APPROXIMATE, TokenCountBasis.UNKNOWN):
            return True
        return not (self.covers_tools and self.covers_schemas and self.covers_non_text)

    def to_dict(self) -> dict[str, Any]:
        return {
            "estimated_input_tokens": self.estimated_input_tokens,
            "counter_id": self.counter_id,
            "counter_version": self.counter_version,
            "basis": self.basis.value,
            "model_id": self.model_id,
            "provider_id": self.provider_id,
            "covers_tools": self.covers_tools,
            "covers_schemas": self.covers_schemas,
            "covers_images": self.covers_images,
            "covers_non_text": self.covers_non_text,
            "incomplete_reason": self.incomplete_reason,
        }


# --------------------------------------------------------------------------- #
# C. Provider-reported usage.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ProviderTokenUsage:
    """Usage a provider reported for ONE attempt (measurement C).

    Every count is optional: ``None`` means *unknown* and is preserved verbatim, never
    fabricated as zero. Cached / cache-write / reasoning tokens are provider-specific
    subsets or details and are NOT blindly added to input/output totals. The
    provider-reported ``total_tokens`` is preserved separately from any derived total.
    Authoritative for the API response being reconciled — but NOT an invoice.
    """

    input_tokens: Optional[int] = None
    cached_input_tokens: Optional[int] = None
    cache_write_input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    reasoning_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    provider_request_id: Optional[str] = None
    usage_schema: Optional[str] = None
    adapter_id: Optional[str] = None
    adapter_version: Optional[str] = None

    def __post_init__(self) -> None:
        for name in (
            "input_tokens",
            "cached_input_tokens",
            "cache_write_input_tokens",
            "output_tokens",
            "reasoning_tokens",
            "total_tokens",
        ):
            object.__setattr__(self, name, _opt_token(getattr(self, name), name))
        for name in ("provider_request_id", "usage_schema", "adapter_id", "adapter_version"):
            object.__setattr__(self, name, _opt_str(getattr(self, name), name))

    @property
    def has_any(self) -> bool:
        """True if any numeric usage field is known."""
        return any(
            getattr(self, n) is not None
            for n in (
                "input_tokens",
                "cached_input_tokens",
                "cache_write_input_tokens",
                "output_tokens",
                "reasoning_tokens",
                "total_tokens",
            )
        )

    def derived_total(self) -> Optional[int]:
        """A DERIVED total = input + output when BOTH are known, else ``None``.

        This is explicitly *derived*, never a substitute for the provider-reported
        ``total_tokens``. Cached, cache-write and reasoning tokens are deliberately
        excluded from the derivation because they are provider-specific subsets/details
        of the input or output totals; adding them would double-count. Callers wanting
        the authoritative total must read ``total_tokens``.
        """
        if self.input_tokens is None or self.output_tokens is None:
            return None
        return self.input_tokens + self.output_tokens

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_tokens": self.input_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "cache_write_input_tokens": self.cache_write_input_tokens,
            "output_tokens": self.output_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "total_tokens": self.total_tokens,
            "derived_total": self.derived_total(),
            "provider_request_id": self.provider_request_id,
            "usage_schema": self.usage_schema,
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
        }


# --------------------------------------------------------------------------- #
# Attribution (who incurred the usage).
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class RequestAttribution:
    """Optional business/workflow attribution for an attempt. All fields optional."""

    tenant_id: Optional[str] = None
    workflow_id: Optional[str] = None
    agent_id: Optional[str] = None
    task_id: Optional[str] = None

    def __post_init__(self) -> None:
        for name in ("tenant_id", "workflow_id", "agent_id", "task_id"):
            object.__setattr__(self, name, _opt_str(getattr(self, name), name))

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "workflow_id": self.workflow_id,
            "agent_id": self.agent_id,
            "task_id": self.task_id,
        }


# --------------------------------------------------------------------------- #
# The per-attempt record.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ApiCallTokenRecord:
    """One actual provider attempt, bound to all three measurements + attribution.

    Contains NO prompt text, credentials, secrets, or provider response payloads. The
    ``record_fingerprint`` is a domain-separated deterministic digest over the stable
    auditable fields (identities, context counts, estimate, usage, status) — never over
    volatile or sensitive content.
    """

    logical_request_id: str
    attempt_id: str
    attempt_number: int
    context_id: str
    #: The minimization run's ``run_fingerprint`` — the link back to measurement A. The
    #: record NEVER mutates the MinimizationResult; it references it by fingerprint.
    minimization_run_fingerprint: str
    provider_id: str
    status: AttemptStatus
    provider_invoked: bool
    # -- context measurement (A), copied from the linked MinimizationResult ----
    context_tokens_before: int
    context_tokens_after: int
    context_tokens_eliminated: int
    # -- request estimate (B) --------------------------------------------------
    request_estimate: RequestTokenEstimate
    # -- provider-reported usage (C) ------------------------------------------
    usage_availability: UsageAvailability
    provider_usage: Optional[ProviderTokenUsage] = None
    usage_unavailable_reason: Optional[str] = None
    # -- attempt lineage + attribution ----------------------------------------
    retry_of_attempt_id: Optional[str] = None
    correlation_id: Optional[str] = None
    model_id: Optional[str] = None
    attribution: RequestAttribution = field(default_factory=RequestAttribution)

    def __post_init__(self) -> None:
        object.__setattr__(self, "logical_request_id", _req_str(self.logical_request_id, "logical_request_id"))
        object.__setattr__(self, "attempt_id", _req_str(self.attempt_id, "attempt_id"))
        if not is_token_count(self.attempt_number) or self.attempt_number < 1:
            raise InvalidRequestError("attempt_number must be an int >= 1")
        object.__setattr__(self, "context_id", _req_str(self.context_id, "context_id"))
        object.__setattr__(
            self, "minimization_run_fingerprint", _req_str(self.minimization_run_fingerprint, "minimization_run_fingerprint")
        )
        object.__setattr__(self, "provider_id", _req_str(self.provider_id, "provider_id"))
        if not isinstance(self.status, AttemptStatus):
            raise InvalidRequestError("status must be an AttemptStatus")
        if not isinstance(self.provider_invoked, bool):
            raise InvalidRequestError("provider_invoked must be a bool")

        before = _req_token(self.context_tokens_before, "context_tokens_before")
        after = _req_token(self.context_tokens_after, "context_tokens_after")
        eliminated = _req_token(self.context_tokens_eliminated, "context_tokens_eliminated")
        if after > before:
            raise InvalidRequestError("context_tokens_after must be <= context_tokens_before")
        if eliminated != before - after:
            raise InvalidRequestError(
                "context_tokens_eliminated must equal before - after "
                f"({before} - {after} = {before - after}), got {eliminated}"
            )
        object.__setattr__(self, "context_tokens_before", before)
        object.__setattr__(self, "context_tokens_after", after)
        object.__setattr__(self, "context_tokens_eliminated", eliminated)

        if not isinstance(self.request_estimate, RequestTokenEstimate):
            raise InvalidRequestError("request_estimate must be a RequestTokenEstimate")
        if not isinstance(self.usage_availability, UsageAvailability):
            raise InvalidRequestError("usage_availability must be a UsageAvailability")

        # Availability / usage consistency, fail closed.
        if self.usage_availability is UsageAvailability.AVAILABLE:
            if not isinstance(self.provider_usage, ProviderTokenUsage) or not self.provider_usage.has_any:
                raise InvalidRequestError(
                    "usage_availability AVAILABLE requires a ProviderTokenUsage with at least one known field"
                )
            if not self.provider_invoked:
                raise InvalidRequestError("usage cannot be AVAILABLE when the provider was not invoked")
        else:
            if self.provider_usage is not None:
                raise InvalidRequestError(
                    "provider_usage must be None when usage is unavailable (unknown is never fabricated)"
                )
        object.__setattr__(self, "usage_unavailable_reason", _opt_str(self.usage_unavailable_reason, "usage_unavailable_reason"))
        object.__setattr__(self, "retry_of_attempt_id", _opt_str(self.retry_of_attempt_id, "retry_of_attempt_id"))
        object.__setattr__(self, "correlation_id", _opt_str(self.correlation_id, "correlation_id"))
        object.__setattr__(self, "model_id", _opt_str(self.model_id, "model_id"))
        if not isinstance(self.attribution, RequestAttribution):
            raise InvalidRequestError("attribution must be a RequestAttribution")

    @property
    def is_retry(self) -> bool:
        return self.retry_of_attempt_id is not None or self.attempt_number > 1

    @property
    def reduction_pct(self) -> float:
        """Deterministic context reduction fraction in [0, 1] (0 when before is 0).

        This is the *context* reduction (A), NOT billed-token savings — those are
        different quantities and must never be conflated.
        """
        if not self.context_tokens_before:
            return 0.0
        return self.context_tokens_eliminated / self.context_tokens_before

    def stable_payload(self) -> dict[str, Any]:
        """The canonical view fingerprinted for audit. Excludes volatile/sensitive data.

        ``reduction_pct`` is deliberately excluded (it is derivable from the integer
        counts, and a float in the digest would be redundant); the integer counts ARE
        bound so the reduction is nonetheless fixed by the fingerprint.
        """
        return {
            "logical_request_id": self.logical_request_id,
            "attempt_id": self.attempt_id,
            "attempt_number": self.attempt_number,
            "retry_of_attempt_id": self.retry_of_attempt_id,
            "context_id": self.context_id,
            "minimization_run_fingerprint": self.minimization_run_fingerprint,
            "correlation_id": self.correlation_id,
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "status": self.status.value,
            "provider_invoked": self.provider_invoked,
            "context_tokens_before": self.context_tokens_before,
            "context_tokens_after": self.context_tokens_after,
            "context_tokens_eliminated": self.context_tokens_eliminated,
            "request_estimate": self.request_estimate.to_dict(),
            "usage_availability": self.usage_availability.value,
            "usage_unavailable_reason": self.usage_unavailable_reason,
            "provider_usage": self.provider_usage.to_dict() if self.provider_usage else None,
            "attribution": self.attribution.to_dict(),
        }

    @property
    def record_fingerprint(self) -> str:
        return _digest(_RECORD_DOMAIN, self.stable_payload())

    def to_dict(self) -> dict[str, Any]:
        d = self.stable_payload()
        d["reduction_pct"] = self.reduction_pct
        d["record_fingerprint"] = self.record_fingerprint
        return d


# --------------------------------------------------------------------------- #
# Logical-request aggregation.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class LogicalRequestTokenSummary:
    """Aggregate of every attempt for one logical (business) request.

    Sums are over the attempts whose provider usage is KNOWN; ``attempts_usage_unknown``
    counts the rest, and ``complete`` is False whenever any gap exists — so a reader
    never mistakes a measurement gap for zero consumption. Context savings are reported
    once for the request (from the linked minimization run), never multiplied per attempt.
    """

    logical_request_id: str
    attempt_count: int
    succeeded_count: int
    failed_count: int
    retry_count: int
    attempts_usage_unknown: int
    provider_input_tokens: int
    provider_output_tokens: int
    provider_total_tokens: int
    retry_input_tokens: int
    retry_output_tokens: int
    failed_attempt_input_tokens: int
    failed_attempt_output_tokens: int
    context_tokens_before: int
    context_tokens_after: int
    context_tokens_eliminated: int
    complete: bool
    record_fingerprints: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "logical_request_id": self.logical_request_id,
            "attempt_count": self.attempt_count,
            "succeeded_count": self.succeeded_count,
            "failed_count": self.failed_count,
            "retry_count": self.retry_count,
            "attempts_usage_unknown": self.attempts_usage_unknown,
            "provider_input_tokens": self.provider_input_tokens,
            "provider_output_tokens": self.provider_output_tokens,
            "provider_total_tokens": self.provider_total_tokens,
            "retry_input_tokens": self.retry_input_tokens,
            "retry_output_tokens": self.retry_output_tokens,
            "failed_attempt_input_tokens": self.failed_attempt_input_tokens,
            "failed_attempt_output_tokens": self.failed_attempt_output_tokens,
            "context_tokens_before": self.context_tokens_before,
            "context_tokens_after": self.context_tokens_after,
            "context_tokens_eliminated": self.context_tokens_eliminated,
            "complete": self.complete,
            "record_fingerprints": list(self.record_fingerprints),
        }

    @property
    def summary_fingerprint(self) -> str:
        return _digest(_SUMMARY_DOMAIN, self.to_dict())


# --------------------------------------------------------------------------- #
# Neutral protocols + deterministic in-memory implementations.
# --------------------------------------------------------------------------- #
@runtime_checkable
class RequestTokenCounter(Protocol):
    """Neutral counter for the COMPLETE serialized request (measurement B).

    An implementation MUST expose string ``counter_id`` and ``counter_version`` and
    return a :class:`RequestTokenEstimate` for a :class:`RequestComponents`. The core
    ships only :class:`DefaultApproximateRequestCounter`; a provider-BPE counter is
    injected from OUTSIDE this package.
    """

    counter_id: str
    counter_version: str

    def estimate_request(
        self,
        components: RequestComponents,
        *,
        model_id: Optional[str] = None,
        provider_id: Optional[str] = None,
    ) -> RequestTokenEstimate: ...


@runtime_checkable
class TokenAccountingSink(Protocol):
    """Where finished :class:`ApiCallTokenRecord`s are delivered.

    The core defines the protocol and an in-memory implementation only; it performs NO
    network / database / filesystem persistence.
    """

    def record(self, record: ApiCallTokenRecord) -> None: ...


#: Backwards-friendly alias — the task refers to it as either name.
TokenUsageSink = TokenAccountingSink


class DefaultApproximateRequestCounter:
    """The transparent stdlib word/punctuation request counter — ALWAYS approximate.

    It sums :func:`default_token_count` over the text components (and the precomputed
    minimized-context token count when supplied). It cannot tokenize images/audio, and
    it never claims exactness: the produced estimate is ``DEFAULT_APPROXIMATE`` with
    honest coverage flags. It is NOT a provider BPE tokenizer.
    """

    counter_id = "ugence.default_approximate"
    counter_version = "1"

    def estimate_request(
        self,
        components: RequestComponents,
        *,
        model_id: Optional[str] = None,
        provider_id: Optional[str] = None,
    ) -> RequestTokenEstimate:
        total = default_token_count(components.system_text)
        for m in components.message_texts:
            total += default_token_count(m)
        if components.minimized_context_tokens is not None:
            total += components.minimized_context_tokens
        elif components.minimized_context_text is not None:
            total += default_token_count(components.minimized_context_text)
        covers_tools = bool(components.tool_definition_texts)
        for t in components.tool_definition_texts:
            total += default_token_count(t)
        covers_schemas = bool(components.schema_texts)
        for s in components.schema_texts:
            total += default_token_count(s)
        non_text = components.image_count > 0 or components.other_non_text_note is not None
        reason = None
        if non_text:
            reason = "non-text inputs (images/other) are not tokenized by the stdlib counter"
        return RequestTokenEstimate(
            estimated_input_tokens=total,
            counter_id=self.counter_id,
            counter_version=self.counter_version,
            basis=TokenCountBasis.DEFAULT_APPROXIMATE,
            model_id=model_id,
            provider_id=provider_id,
            covers_tools=covers_tools,
            covers_schemas=covers_schemas,
            covers_images=False,
            covers_non_text=not non_text,
            incomplete_reason=reason,
        )


class InMemoryTokenAccountingSink:
    """A deterministic, in-memory :class:`TokenAccountingSink` (test/reference only).

    Enforces attempt-identity discipline: a duplicate ``attempt_id`` is REJECTED unless
    the replayed record is byte-identical (an explicitly idempotent replay). It performs
    no I/O and holds no external resource.
    """

    def __init__(self) -> None:
        self._records: list[ApiCallTokenRecord] = []
        self._by_attempt: dict[str, ApiCallTokenRecord] = {}

    def record(self, record: ApiCallTokenRecord) -> None:
        if not isinstance(record, ApiCallTokenRecord):
            raise InvalidRequestError("record must be an ApiCallTokenRecord")
        existing = self._by_attempt.get(record.attempt_id)
        if existing is not None:
            if existing.record_fingerprint != record.record_fingerprint:
                raise InvalidRequestError(
                    f"duplicate attempt_id {record.attempt_id!r} with conflicting content "
                    "(idempotent replay requires a byte-identical record)"
                )
            return  # identical replay — accepted, not double-stored
        self._by_attempt[record.attempt_id] = record
        self._records.append(record)

    @property
    def records(self) -> tuple[ApiCallTokenRecord, ...]:
        return tuple(self._records)

    def for_logical_request(self, logical_request_id: str) -> tuple[ApiCallTokenRecord, ...]:
        return tuple(r for r in self._records if r.logical_request_id == logical_request_id)


# --------------------------------------------------------------------------- #
# Pre-call / post-call / aggregation APIs.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class PreparedApiCall:
    """The immutable pre-call measurement for one logical request.

    Captures measurements A (context before/after, from the linked minimization run)
    and B (the full-request estimate), plus the identity that links every attempt back
    to the same minimization result via its ``run_fingerprint``. It holds NO provider
    usage — that is added, per attempt, by :func:`reconcile_api_call_measurement`.
    Reconciliation never replaces this estimate with actual usage.
    """

    logical_request_id: str
    context_id: str
    minimization_run_fingerprint: str
    context_tokens_before: int
    context_tokens_after: int
    context_tokens_eliminated: int
    request_estimate: RequestTokenEstimate
    provider_id: str
    model_id: Optional[str] = None
    correlation_id: Optional[str] = None
    attribution: RequestAttribution = field(default_factory=RequestAttribution)

    def to_dict(self) -> dict[str, Any]:
        return {
            "logical_request_id": self.logical_request_id,
            "context_id": self.context_id,
            "minimization_run_fingerprint": self.minimization_run_fingerprint,
            "context_tokens_before": self.context_tokens_before,
            "context_tokens_after": self.context_tokens_after,
            "context_tokens_eliminated": self.context_tokens_eliminated,
            "request_estimate": self.request_estimate.to_dict(),
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "correlation_id": self.correlation_id,
            "attribution": self.attribution.to_dict(),
        }


def prepare_api_call_measurement(
    *,
    minimization_result: MinimizationResult,
    logical_request_id: str,
    provider_id: str,
    request_components: Optional[RequestComponents] = None,
    request_counter: Optional[RequestTokenCounter] = None,
    request_estimate: Optional[RequestTokenEstimate] = None,
    model_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    attribution: Optional[RequestAttribution] = None,
) -> PreparedApiCall:
    """Build the pre-call measurement, linked to a specific :class:`MinimizationResult`.

    * Preserves the minimization ``run_fingerprint`` (the link to measurement A) and
      copies the context before/after/eliminated counts VERBATIM — it never re-runs or
      mutates the minimization.
    * Produces the full-request estimate (measurement B) from, in precedence order: an
      explicit ``request_estimate`` (caller-supplied), else an injected ``request_counter``
      over ``request_components``, else the transparent default counter (marked
      ``DEFAULT_APPROXIMATE``). Default or incomplete counting is labelled approximate.

    Exactly one estimate source is used; supplying both an explicit estimate and a
    counter is a contract error.
    """
    if not isinstance(minimization_result, MinimizationResult):
        raise InvalidRequestError("minimization_result must be a MinimizationResult")
    logical_request_id = _req_str(logical_request_id, "logical_request_id")
    provider_id = _req_str(provider_id, "provider_id")
    if request_estimate is not None and request_counter is not None:
        raise InvalidRequestError("supply either request_estimate or request_counter, not both")

    run_fp = minimization_result.run_fingerprint
    if not isinstance(run_fp, str) or not run_fp:
        raise InvalidRequestError(
            "minimization_result.run_fingerprint is required to link the measurement "
            "(regenerate the result on a contract that emits run_fingerprint)"
        )

    before = minimization_result.original_tokens
    after = minimization_result.resulting_tokens

    if request_estimate is not None:
        if not isinstance(request_estimate, RequestTokenEstimate):
            raise InvalidRequestError("request_estimate must be a RequestTokenEstimate")
        estimate = request_estimate
    else:
        components = request_components or RequestComponents(
            minimized_context_tokens=after,
        )
        counter: RequestTokenCounter = request_counter or DefaultApproximateRequestCounter()
        estimate = counter.estimate_request(components, model_id=model_id, provider_id=provider_id)
        if not isinstance(estimate, RequestTokenEstimate):
            raise InvalidRequestError("request_counter.estimate_request must return a RequestTokenEstimate")

    return PreparedApiCall(
        logical_request_id=logical_request_id,
        context_id=minimization_result.context_id,
        minimization_run_fingerprint=run_fp,
        context_tokens_before=before,
        context_tokens_after=after,
        context_tokens_eliminated=before - after,
        request_estimate=estimate,
        provider_id=provider_id,
        model_id=model_id or estimate.model_id,
        correlation_id=correlation_id,
        attribution=attribution or RequestAttribution(),
    )


def reconcile_api_call_measurement(
    prepared: PreparedApiCall,
    *,
    attempt_id: str,
    attempt_number: int,
    status: AttemptStatus,
    provider_invoked: bool = True,
    provider_usage: Optional[ProviderTokenUsage] = None,
    usage_unavailable_reason: Optional[str] = None,
    usage_availability: Optional[UsageAvailability] = None,
    retry_of_attempt_id: Optional[str] = None,
    sink: Optional[TokenAccountingSink] = None,
) -> ApiCallTokenRecord:
    """Record ONE and only one provider attempt against a prepared measurement.

    * Accepts provider-reported ``provider_usage`` OR an explicit unavailable reason —
      it NEVER fabricates zero usage and never replaces the pre-call estimate with actual
      usage (both are carried, distinctly, on the record).
    * Failed / retried attempts are preserved as their own records (a retry is a new
      ``attempt_id``; supply ``retry_of_attempt_id`` to link it to the prior attempt).
    * Rejects malformed token counts (negative / bool / float / NaN / inf / str) via the
      strict field validators, and — when a ``sink`` is given — rejects a duplicate
      ``attempt_id`` whose content differs (idempotent replay must be byte-identical).

    ``usage_availability`` is inferred when omitted: AVAILABLE if usage with any known
    field is supplied, else UNAVAILABLE_PROVIDER_ERROR for a non-success status, else
    UNAVAILABLE_NOT_REPORTED.
    """
    if not isinstance(prepared, PreparedApiCall):
        raise InvalidRequestError("prepared must be a PreparedApiCall")
    if not isinstance(status, AttemptStatus):
        raise InvalidRequestError("status must be an AttemptStatus")

    has_usage = isinstance(provider_usage, ProviderTokenUsage) and provider_usage.has_any
    if usage_availability is None:
        if has_usage:
            usage_availability = UsageAvailability.AVAILABLE
        elif status is AttemptStatus.SUCCEEDED:
            usage_availability = UsageAvailability.UNAVAILABLE_NOT_REPORTED
        else:
            usage_availability = UsageAvailability.UNAVAILABLE_PROVIDER_ERROR
    if usage_availability is UsageAvailability.AVAILABLE and not has_usage:
        raise InvalidRequestError(
            "usage_availability AVAILABLE requires provider_usage with at least one known field"
        )
    # Normalize: unavailable ⇒ carry no fabricated usage object.
    effective_usage = provider_usage if usage_availability is UsageAvailability.AVAILABLE else None

    record = ApiCallTokenRecord(
        logical_request_id=prepared.logical_request_id,
        attempt_id=attempt_id,
        attempt_number=attempt_number,
        context_id=prepared.context_id,
        minimization_run_fingerprint=prepared.minimization_run_fingerprint,
        provider_id=prepared.provider_id,
        status=status,
        provider_invoked=provider_invoked,
        context_tokens_before=prepared.context_tokens_before,
        context_tokens_after=prepared.context_tokens_after,
        context_tokens_eliminated=prepared.context_tokens_eliminated,
        request_estimate=prepared.request_estimate,
        usage_availability=usage_availability,
        provider_usage=effective_usage,
        usage_unavailable_reason=usage_unavailable_reason,
        retry_of_attempt_id=retry_of_attempt_id,
        correlation_id=prepared.correlation_id,
        model_id=prepared.model_id,
        attribution=prepared.attribution,
    )
    if sink is not None:
        sink.record(record)
    return record


def aggregate_logical_request_usage(
    records: Sequence[ApiCallTokenRecord] | Iterable[ApiCallTokenRecord],
    *,
    logical_request_id: Optional[str] = None,
) -> LogicalRequestTokenSummary:
    """Aggregate every attempt of one logical request into a summary.

    * Sums provider input/output/total ONLY over attempts whose usage is known;
      ``attempts_usage_unknown`` counts the rest and ``complete`` is False if any exist,
      so an unknown is never silently treated as zero.
    * Retry-attempt and failed-attempt token sums are reported separately (a failed
      attempt with KNOWN usage still contributes to consumption — its tokens are not
      zeroed just because it failed).
    * Context savings are taken ONCE from the shared minimization run (all attempts of a
      logical request reference the same ``run_fingerprint``); they are never multiplied
      per attempt. A divergent run fingerprint across attempts fails closed.
    """
    recs = list(records)
    if not recs:
        raise InvalidRequestError("aggregate_logical_request_usage requires at least one record")
    ids = {r.logical_request_id for r in recs}
    if logical_request_id is None:
        if len(ids) != 1:
            raise InvalidRequestError(
                f"records span multiple logical_request_ids {sorted(ids)}; pass logical_request_id to select one"
            )
        logical_request_id = next(iter(ids))
    recs = [r for r in recs if r.logical_request_id == logical_request_id]
    if not recs:
        raise InvalidRequestError(f"no records for logical_request_id {logical_request_id!r}")

    # All attempts of one logical request must reference the same minimization run.
    run_fps = {r.minimization_run_fingerprint for r in recs}
    if len(run_fps) != 1:
        raise InvalidRequestError(
            f"attempts of {logical_request_id!r} reference divergent minimization run fingerprints "
            f"{sorted(run_fps)} (context savings cannot be attributed once)"
        )
    # Attempt-id uniqueness (conflicting duplicates are a data error).
    by_attempt: dict[str, ApiCallTokenRecord] = {}
    for r in recs:
        prior = by_attempt.get(r.attempt_id)
        if prior is not None and prior.record_fingerprint != r.record_fingerprint:
            raise InvalidRequestError(
                f"duplicate attempt_id {r.attempt_id!r} with conflicting content in aggregation"
            )
        by_attempt[r.attempt_id] = r
    unique = list(by_attempt.values())

    succeeded = sum(1 for r in unique if r.status is AttemptStatus.SUCCEEDED)
    failed = sum(1 for r in unique if r.status is not AttemptStatus.SUCCEEDED)
    retries = sum(1 for r in unique if r.is_retry)
    unknown = sum(1 for r in unique if r.usage_availability is not UsageAvailability.AVAILABLE)

    def _in(r: ApiCallTokenRecord) -> int:
        return r.provider_usage.input_tokens or 0 if r.provider_usage else 0

    def _out(r: ApiCallTokenRecord) -> int:
        return r.provider_usage.output_tokens or 0 if r.provider_usage else 0

    def _tot(r: ApiCallTokenRecord) -> int:
        if not r.provider_usage:
            return 0
        if r.provider_usage.total_tokens is not None:
            return r.provider_usage.total_tokens
        derived = r.provider_usage.derived_total()
        return derived or 0

    known = [r for r in unique if r.usage_availability is UsageAvailability.AVAILABLE]
    provider_input = sum(_in(r) for r in known)
    provider_output = sum(_out(r) for r in known)
    provider_total = sum(_tot(r) for r in known)
    retry_input = sum(_in(r) for r in known if r.is_retry)
    retry_output = sum(_out(r) for r in known if r.is_retry)
    failed_input = sum(_in(r) for r in known if r.status is not AttemptStatus.SUCCEEDED)
    failed_output = sum(_out(r) for r in known if r.status is not AttemptStatus.SUCCEEDED)

    ref = unique[0]  # shared context measurement (identical across attempts)
    fingerprints = tuple(sorted(r.record_fingerprint for r in unique))

    return LogicalRequestTokenSummary(
        logical_request_id=logical_request_id,
        attempt_count=len(unique),
        succeeded_count=succeeded,
        failed_count=failed,
        retry_count=retries,
        attempts_usage_unknown=unknown,
        provider_input_tokens=provider_input,
        provider_output_tokens=provider_output,
        provider_total_tokens=provider_total,
        retry_input_tokens=retry_input,
        retry_output_tokens=retry_output,
        failed_attempt_input_tokens=failed_input,
        failed_attempt_output_tokens=failed_output,
        context_tokens_before=ref.context_tokens_before,
        context_tokens_after=ref.context_tokens_after,
        context_tokens_eliminated=ref.context_tokens_eliminated,
        complete=(unknown == 0),
        record_fingerprints=fingerprints,
    )


__all__ = [
    "TokenCountBasis",
    "AttemptStatus",
    "UsageAvailability",
    "RequestComponents",
    "RequestTokenEstimate",
    "ProviderTokenUsage",
    "RequestAttribution",
    "ApiCallTokenRecord",
    "LogicalRequestTokenSummary",
    "RequestTokenCounter",
    "TokenAccountingSink",
    "TokenUsageSink",
    "DefaultApproximateRequestCounter",
    "InMemoryTokenAccountingSink",
    "PreparedApiCall",
    "prepare_api_call_measurement",
    "reconcile_api_call_measurement",
    "aggregate_logical_request_usage",
]
