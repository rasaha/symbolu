"""Delivery transports for the Phase 3C relay.

The port is content-free BY CONSTRUCTION (invariant I7): a transport receives
push tokens and nothing else — no message id, sender, sequence, or body can
reach it, because the interface cannot carry them. The user-visible text is
the single ratified constant below (D3C-2): generic, no sender name, no body,
no relationship/astrology/safety information.

Acknowledgement contract (what PUBLISHED means, per ratification): a transport
returning normally has accepted the batch under ITS OWN acknowledgement
semantics — for Expo, HTTP 200 with per-token tickets. That never implies the
handset displayed anything; push is advisory and non-authoritative (I5).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

NOTIFICATION_TITLE = "DilChat"
NOTIFICATION_BODY = "You have a new message."


class TransportError(Exception):
    """Transient transport failure: the batch was NOT accepted; retry later.

    The message must be a machine-style code/phrase only — it may end up in
    ``last_error_code`` — never provider free text, a token, or content.
    """


@dataclass(frozen=True)
class TokenResult:
    token: str
    accepted: bool
    # True when the provider says this token is permanently dead
    # (e.g. Expo "DeviceNotRegistered"): the device registration is deactivated.
    permanently_rejected: bool = False


class DeliveryTransport(Protocol):
    async def send_new_message(self, tokens: list[str]) -> list[TokenResult]:
        """Deliver the generic new-message notification to each token.

        Returns one result per token. Raises TransportError when the batch as a
        whole was not accepted (the caller retries with backoff, at-least-once).
        """
        ...


class NullTransport:
    """Dev/test default: accepts everything, sends nothing, keeps no state."""

    async def send_new_message(self, tokens: list[str]) -> list[TokenResult]:
        return [TokenResult(token=t, accepted=True) for t in tokens]


class ExpoPushTransport:
    """Expo push service client (pilot transport, D3C-1).

    Production APNs/FCM credentials remain a separate launch gate; the pilot
    uses Expo's service. Requests carry tokens and the ratified generic text
    only. Nothing from the HTTP exchange is logged here.
    """

    _BATCH = 100  # Expo's documented per-request maximum

    def __init__(self, url: str, *, timeout_seconds: float = 10.0) -> None:
        self._url = url
        self._timeout = timeout_seconds

    async def send_new_message(self, tokens: list[str]) -> list[TokenResult]:
        import httpx

        results: list[TokenResult] = []
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                for start in range(0, len(tokens), self._BATCH):
                    chunk = tokens[start : start + self._BATCH]
                    resp = await client.post(
                        self._url,
                        json=[
                            {
                                "to": token,
                                "title": NOTIFICATION_TITLE,
                                "body": NOTIFICATION_BODY,
                                "priority": "default",
                            }
                            for token in chunk
                        ],
                    )
                    if resp.status_code != 200:
                        raise TransportError("EXPO_HTTP_STATUS")
                    tickets = resp.json().get("data")
                    if not isinstance(tickets, list) or len(tickets) != len(chunk):
                        raise TransportError("EXPO_TICKET_SHAPE")
                    for token, ticket in zip(chunk, tickets, strict=True):
                        ok = isinstance(ticket, dict) and ticket.get("status") == "ok"
                        dead = (
                            isinstance(ticket, dict)
                            and ticket.get("status") == "error"
                            and isinstance(ticket.get("details"), dict)
                            and ticket["details"].get("error") == "DeviceNotRegistered"
                        )
                        results.append(
                            TokenResult(token=token, accepted=ok, permanently_rejected=dead)
                        )
        except TransportError:
            raise
        except Exception as exc:
            # Timeout, connect error, bad JSON, … — transient, retry later.
            raise TransportError("EXPO_UNAVAILABLE") from exc
        return results


def build_transport(name: str, *, expo_url: str) -> DeliveryTransport:
    if name == "null":
        return NullTransport()
    if name == "expo":
        return ExpoPushTransport(expo_url)
    # Settings validation refuses unknown names at construction; this is the
    # defence-in-depth backstop (fail closed, never a silent no-op).
    raise ValueError(f"unknown push transport: {name!r}")
