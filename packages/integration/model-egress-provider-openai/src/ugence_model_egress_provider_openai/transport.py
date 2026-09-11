"""The transport seam: what a dispatch *is*, what it may say back, and the fake.

Nothing in this module can open a socket. :class:`PreparedRequest` is the whole of what
would cross the wire — destination, method, canonical body — validated against LP-1/LP-3
(exact destination) and LP-3/LP-5 (exact request shape) at construction, so an
adapter cannot assemble a request the rulings did not describe. The bearer credential is
*not* part of it: the secret reaches a transport only as an argument to :meth:`send`,
inside :meth:`CredentialLease.use`, and never as state.

A transport answers with a :class:`TransportOutcome` in one of three kinds:

``RESPONDED``
    Bytes went out and a response came back. ``genuine`` says whether a vendor
    produced it; the fake shipped here can only ever say ``False``.
``TRANSIENT_BEFORE_DISPATCH``
    The transport *proves* no request bytes left the process (a refused connection,
    a failed TLS handshake, a DNS failure). LP-5 permits one retry for this kind only.
``DISPATCHED_NO_RESPONSE``
    Bytes may have left the process and nothing conclusive came back. No retry: a
    second call could bill twice. The adapter records ``OUTCOME_UNKNOWN``.

An outcome that *claims* to precede dispatch without the proof bit collapses to
``DISPATCHED_NO_RESPONSE`` in the constructor: ambiguity never earns a retry.
"""

from __future__ import annotations

import enum
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, List, Mapping, Optional, Protocol, Sequence

from ugence_model_egress_unit import (
    COMMISSIONING_LIMITS,
    OPENAI_RESPONSES,
    DestinationRefused,
    check_destination,
    is_pinned_snapshot,
)

__all__ = [
    "REQUEST_BODY_KEYS",
    "FAKE_RESPONSE_MARKER",
    "PreparedRequest",
    "OutcomeKind",
    "TransportOutcome",
    "ResponsesTransport",
    "FakeTransport",
]

#: LP-3 and LP-5, as the exact top-level keys of the Responses request body. Nothing
#: else is ever sent: no ``tools``, no ``stream: true``, no ``store: true``, no
#: ``background``, no ``previous_response_id``. The set is closed, not a minimum.
REQUEST_BODY_KEYS = frozenset({"model", "input", "max_output_tokens", "store", "stream"})

#: Prefixed to every answer the fake transport produces. Loud and not configurable.
FAKE_RESPONSE_MARKER = "[UGENCE-OPENAI-FAKE-TRANSPORT — NOT A MODEL RESPONSE]"


def _canonical(body: Mapping[str, Any]) -> bytes:
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


@dataclass(frozen=True)
class PreparedRequest:
    """Everything that would cross the wire, except the credential.

    Validated on construction: the URL is exactly the designated destination and the
    body has exactly :data:`REQUEST_BODY_KEYS`, a pinned model, ``store: false`` and
    ``stream: false``, and ``max_output_tokens`` within LP-5. A request that fails any
    of these is not "sent anyway with a warning"; it is not a :class:`PreparedRequest`.
    """

    url: str
    body: Mapping[str, Any]
    method: str = "POST"
    content_type: str = "application/json"

    def __post_init__(self) -> None:
        check_destination(self.url, OPENAI_RESPONSES)  # raises DestinationRefused
        if self.method != "POST":
            raise DestinationRefused("the Responses endpoint is reached by POST only")
        keys = set(self.body.keys()) if isinstance(self.body, Mapping) else None
        if keys != REQUEST_BODY_KEYS:
            raise ValueError(
                f"request body keys must be exactly {sorted(REQUEST_BODY_KEYS)}, "
                f"got {sorted(keys) if keys is not None else type(self.body).__name__}")
        if not is_pinned_snapshot(self.body["model"]):
            raise ValueError("the model in a prepared request must be a dated snapshot (LP-3)")
        if self.body["store"] is not False or self.body["stream"] is not False:
            raise ValueError("store and stream must both be exactly false (LP-3, LP-5)")
        out = self.body["max_output_tokens"]
        if (not isinstance(out, int) or isinstance(out, bool) or out < 1
                or out > COMMISSIONING_LIMITS.max_output_tokens):
            raise ValueError(
                f"max_output_tokens must be an integer in 1..{COMMISSIONING_LIMITS.max_output_tokens}")
        if not isinstance(self.body["input"], list) or not self.body["input"]:
            raise ValueError("input must be a non-empty list of messages")
        object.__setattr__(self, "body", dict(self.body))

    def encoded(self) -> bytes:
        """The canonical body bytes. Deterministic, so a digest of them is meaningful."""

        return _canonical(self.body)

    @property
    def body_digest(self) -> str:
        return hashlib.sha256(self.encoded()).hexdigest()

    def as_record(self) -> dict:
        """What may be written down about a dispatch: never the body's content."""

        return {"url": self.url, "method": self.method, "body_digest": self.body_digest,
                "model": self.body["model"], "max_output_tokens": self.body["max_output_tokens"],
                "input_units": len(self.body["input"])}


class OutcomeKind(str, enum.Enum):
    RESPONDED = "RESPONDED"
    TRANSIENT_BEFORE_DISPATCH = "TRANSIENT_BEFORE_DISPATCH"
    DISPATCHED_NO_RESPONSE = "DISPATCHED_NO_RESPONSE"


@dataclass(frozen=True)
class TransportOutcome:
    """What a transport reports about one attempt.

    ``no_bytes_dispatched`` is the transport's *proof* claim for a transient failure.
    Without it, a transient failure is reclassified as ``DISPATCHED_NO_RESPONSE`` — the
    conservative reading, which forbids the retry. ``genuine`` is whether a vendor
    produced ``body``; a fake transport may never set it.
    """

    kind: OutcomeKind
    status: Optional[int] = None
    body: Optional[Mapping[str, Any]] = None
    genuine: bool = False
    detail: str = ""
    no_bytes_dispatched: bool = False

    def __post_init__(self) -> None:
        kind = OutcomeKind(self.kind)
        object.__setattr__(self, "kind", kind)
        if kind is OutcomeKind.TRANSIENT_BEFORE_DISPATCH and not self.no_bytes_dispatched:
            object.__setattr__(self, "kind", OutcomeKind.DISPATCHED_NO_RESPONSE)
            object.__setattr__(self, "detail",
                               (self.detail + " " if self.detail else "")
                               + "[reclassified: no proof that request bytes were not dispatched]")
        if self.kind is not OutcomeKind.RESPONDED and (self.status is not None or self.body is not None):
            raise ValueError("only a RESPONDED outcome carries a status or a body")
        if self.kind is OutcomeKind.RESPONDED and (not isinstance(self.status, int) or self.body is None):
            raise ValueError("a RESPONDED outcome carries an integer status and a body")
        if self.genuine and self.kind is not OutcomeKind.RESPONDED:
            raise ValueError("only a response can be genuine")

    @classmethod
    def responded(cls, status: int, body: Mapping[str, Any], *, genuine: bool = False) -> "TransportOutcome":
        return cls(OutcomeKind.RESPONDED, status=status, body=dict(body), genuine=genuine)

    @classmethod
    def transient_before_dispatch(cls, detail: str, *, no_bytes_dispatched: bool) -> "TransportOutcome":
        return cls(OutcomeKind.TRANSIENT_BEFORE_DISPATCH, detail=detail,
                   no_bytes_dispatched=no_bytes_dispatched)

    @classmethod
    def dispatched_no_response(cls, detail: str) -> "TransportOutcome":
        return cls(OutcomeKind.DISPATCHED_NO_RESPONSE, detail=detail)

    @property
    def retryable(self) -> bool:
        return self.kind is OutcomeKind.TRANSIENT_BEFORE_DISPATCH and self.no_bytes_dispatched


class ResponsesTransport(Protocol):
    """What the adapter is handed. It is *injected*; the adapter has no default.

    ``NON_PRODUCTION`` is the transport's own declaration that it cannot reach a vendor.
    The adapter refuses, before dispatch, any transport that does not declare it while
    commissioning is not ``MET``.
    """

    NON_PRODUCTION: bool

    def send(self, prepared: PreparedRequest, *, bearer: str, now: datetime) -> TransportOutcome:
        ...


@dataclass
class FakeTransport:
    """Answers from a script, in order; never leaves the process; never keeps the bearer.

    The record it keeps of each dispatch is the :meth:`PreparedRequest.as_record` shape
    plus ``bearer_present`` — a boolean. The secret's value, length or prefix is not
    retained anywhere, and a scripted outcome that claims ``genuine`` is refused at
    construction: fake evidence cannot satisfy a live validation row (LP-4, LP-6).
    """

    NON_PRODUCTION = True
    maturity = "FIXTURE_ONLY"

    script: Sequence[TransportOutcome] = ()
    dispatches: List[dict] = field(default_factory=list, init=False)
    _cursor: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        self.script = tuple(self.script)
        for outcome in self.script:
            if not isinstance(outcome, TransportOutcome):
                raise TypeError("a fake transport is scripted with TransportOutcome values")
            if outcome.genuine:
                raise ValueError("a fake transport can never produce a genuine response")

    @staticmethod
    def fake_response(prepared: PreparedRequest) -> TransportOutcome:
        """The default answer: labelled, deterministic in the request, never genuine."""

        digest = prepared.body_digest
        return TransportOutcome.responded(200, {
            "id": f"resp_fake_{digest[:16]}",
            "model": prepared.body["model"],
            "output_text": f"{FAKE_RESPONSE_MARKER} adapter-input-digest={digest}",
            "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        })

    def send(self, prepared: PreparedRequest, *, bearer: str, now: datetime) -> TransportOutcome:
        if not isinstance(prepared, PreparedRequest):
            raise TypeError("only a PreparedRequest may be dispatched")
        if prepared.url != OPENAI_RESPONSES.url:  # already guaranteed; asserted again at the seam
            raise DestinationRefused("not the designated destination")
        record = prepared.as_record()
        record["bearer_present"] = isinstance(bearer, str) and bool(bearer)
        record["at"] = now.isoformat()
        self.dispatches.append(record)
        if self._cursor < len(self.script):
            outcome = self.script[self._cursor]
            self._cursor += 1
            return outcome
        return self.fake_response(prepared)
