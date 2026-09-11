"""Ugence Model Egress Provider — OpenAI Responses.

**This distribution cannot reach ``api.openai.com``.** It carries the adapter LP-3
designated, behind the Model Egress Unit's provider seam, with the exact destination
and request shape enforced at construction, the LP-5 ceiling enforced before dispatch,
the proof-gated single retry, and an injected transport of which the only shipped
implementation is a fake that never leaves the process and never keeps the bearer.
No HTTP client, no vendor SDK, no credential reader and no live network path exist
here; ``tests/test_boundaries.py`` fails the moment one is imported.

It depends on ``ugence-model-egress-unit`` and on nothing else; the unit never
depends on it. ``LIVE_VENDOR_EGRESS`` is ``False`` and ``genuine_call`` is ``False`` in
every record this package can produce. Commissioning a live transport is LP-6 step 7
and step 8 work, blocked on the owner's infrastructure designations
(``MEU_LIVE_PROVIDER_DESIGNATION.json`` beside the unit).
"""

from __future__ import annotations

from .provider import (
    ESTIMATED_CENTS_PER_CALL,
    GenuineResponseNotRecordable,
    OpenAIResponsesProvider,
    prepare,
)
from .transport import (
    FAKE_RESPONSE_MARKER,
    REQUEST_BODY_KEYS,
    FakeTransport,
    OutcomeKind,
    PreparedRequest,
    ResponsesTransport,
    TransportOutcome,
)
from .version import (
    ADAPTER_ID,
    DESIGNATED_MODEL,
    ENFORCEMENT_ENABLED,
    LIVE_VENDOR_EGRESS,
    MATURITY,
    VENDOR,
    __version__,
)

__all__ = [
    "__version__",
    "ADAPTER_ID",
    "VENDOR",
    "DESIGNATED_MODEL",
    "MATURITY",
    "ENFORCEMENT_ENABLED",
    "LIVE_VENDOR_EGRESS",
    "REQUEST_BODY_KEYS",
    "FAKE_RESPONSE_MARKER",
    "PreparedRequest",
    "OutcomeKind",
    "TransportOutcome",
    "ResponsesTransport",
    "FakeTransport",
    "ESTIMATED_CENTS_PER_CALL",
    "GenuineResponseNotRecordable",
    "prepare",
    "OpenAIResponsesProvider",
]
