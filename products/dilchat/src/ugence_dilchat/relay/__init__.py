"""Phase 3C outbox relay: a standalone worker process with no HTTP surface.

Run as ``python -m ugence_dilchat.relay`` under the ``dilchat_worker`` database
posture (D3C-4). The web/API process never acquires the worker's outbox
privileges; if the relay is down, messaging stays correct, REST access and
mobile polling continue, and push delivery degrades independently (DEC-058).
"""

from .transports import (
    DeliveryTransport,
    ExpoPushTransport,
    NullTransport,
    TokenResult,
    TransportError,
    build_transport,
)
from .worker import RelayService

__all__ = [
    "DeliveryTransport",
    "ExpoPushTransport",
    "NullTransport",
    "RelayService",
    "TokenResult",
    "TransportError",
    "build_transport",
]
