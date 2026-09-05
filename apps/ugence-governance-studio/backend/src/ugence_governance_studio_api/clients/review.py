"""A deliberately small client for the governed review service (GAS-7, HR-D).

The same two choices as the console client, for the same reasons: it reaches the
review service over HTTP, never by import (``ugence_governed_review_service`` imports
the durable-execution adapter and a database driver, both prohibited in the studio),
and it uses the standard library.

The route restriction is the real content. ``REVIEW_ALLOWED_ROUTES`` is a closed set of
five — four reads and one relay — and :meth:`ReviewServiceClient._request` refuses
anything outside it *before* opening a connection. Owner ruling HR-1
(``DISPLAY_AND_TRANSMIT``): the studio renders what the review service holds and relays a
human's decision verbatim to it. It holds no approver identity, computes no
eligibility, consumes nothing, signals nothing and resumes nothing; the review service
exposes no route for any of those, and this client could not reach one if it did.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional, Tuple

__all__ = [
    "ReviewServiceClient",
    "ReviewServiceUnavailable",
    "ReviewNotFound",
    "REVIEW_ALLOWED_ROUTES",
]

#: The complete set of review-service routes the studio may reach. Four reads and one
#: relay. Nothing that grants, authorizes, clears, executes, signals or resumes
#: appears here, and nothing may be added without an owner ruling that revisits HR-1.
REVIEW_ALLOWED_ROUTES: Tuple[Tuple[str, str], ...] = (
    ("GET", "/review/queue"),
    ("GET", "/review/runs/{instance_id}"),
    ("GET", "/review/runs/{instance_id}/events"),
    ("GET", "/review/approvals/{approval_id}"),
    ("POST", "/review/decisions"),
)

_ALLOWED_TEMPLATES = {(m, p) for m, p in REVIEW_ALLOWED_ROUTES}

#: Statuses whose JSON body is the review service's typed answer, not a transport
#: fault: a refused decision is 409 with the outcome and the standing record.
_ANSWER_STATUSES = frozenset({200, 409})


class ReviewServiceUnavailable(RuntimeError):
    """The review service could not be reached, or answered unusably.

    Never rendered as an empty queue: "no instance is parked" and "the review service is
    unreachable" must not look alike on a review screen.
    """


class ReviewNotFound(ReviewServiceUnavailable):
    """The review service answered 404: the instance or approval is unknown to it."""


class ReviewServiceClient:
    """Read and relay access to the governed review service."""

    def __init__(self, base_url: str, *, timeout_s: float = 10.0) -> None:
        self._base = base_url.rstrip("/")
        self._timeout = timeout_s

    # -- the five permitted operations ----------------------------------------
    def queue(self, required_role: str = "") -> Any:
        """``GET /review/queue`` — parked ESCALATE instances awaiting a decision."""
        query = {"required_role": required_role} if required_role else None
        return self._request("GET", "/review/queue", query=query)

    def run(self, instance_id: str) -> Any:
        """``GET /review/runs/{instance_id}`` — one instance's checkpoint view."""
        return self._request("GET", "/review/runs/{instance_id}",
                             path_params={"instance_id": instance_id})

    def run_events(self, instance_id: str) -> Any:
        """``GET /review/runs/{instance_id}/events`` — the full event log."""
        return self._request("GET", "/review/runs/{instance_id}/events",
                             path_params={"instance_id": instance_id})

    def approval(self, approval_id: str) -> Any:
        """``GET /review/approvals/{approval_id}`` — the record and its event chain."""
        return self._request("GET", "/review/approvals/{approval_id}",
                             path_params={"approval_id": approval_id})

    def submit_decision(self, body: Dict[str, Any]) -> Any:
        """``POST /review/decisions`` — relay a human's decision, verbatim.

        The body is forwarded exactly as the studio received it. Nothing is added: no
        identity, no session, no computed eligibility. The answer is the service's
        typed outcome, whether it recorded, replayed or refused.
        """
        return self._request("POST", "/review/decisions", body=body)

    # -- internals ------------------------------------------------------------
    def _request(
        self,
        method: str,
        template: str,
        *,
        path_params: Optional[Dict[str, str]] = None,
        query: Optional[Dict[str, str]] = None,
        body: Optional[Dict[str, Any]] = None,
    ) -> Any:
        if (method, template) not in _ALLOWED_TEMPLATES:
            # Refused before a connection is opened. The restriction is a property of
            # the client, not of the caller's good behaviour.
            raise ReviewServiceUnavailable(
                f"route {method} {template} is not in the studio's permitted review "
                "route set; the studio never grants, authorizes, clears, executes, "
                "signals or resumes"
            )

        path = template
        for key, value in (path_params or {}).items():
            # Quote with an empty safe set: an id carrying a slash must not become a
            # different path than the one that was allowlisted.
            path = path.replace("{" + key + "}", urllib.parse.quote(str(value), safe=""))
        if query:
            path = path + "?" + urllib.parse.urlencode(query)

        request = urllib.request.Request(
            url=self._base + path,
            method=method,
            data=json.dumps(body).encode("utf-8") if body is not None else None,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise ReviewNotFound(
                    f"review service has no record for {method} {path}"
                ) from exc
            if exc.code in _ANSWER_STATUSES:
                raw = exc.read()
            else:
                raise ReviewServiceUnavailable(
                    f"review service returned HTTP {exc.code} for {method} {path}"
                ) from exc
        except Exception as exc:  # noqa: BLE001 - URLError, socket timeout, DNS, ...
            raise ReviewServiceUnavailable(
                f"review service unreachable for {method} {path}: {type(exc).__name__}"
            ) from exc

        try:
            return json.loads(raw.decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - a non-JSON body is unusable
            raise ReviewServiceUnavailable(
                f"review service returned a non-JSON body for {method} {path}"
            ) from exc
