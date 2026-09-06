"""A deliberately small client for the governed review service (GAS-7, HR-D).

The same two choices as the console client, for the same reasons: it reaches the
review service over HTTP, never by import (``ugence_governed_review_service`` imports
the durable-execution adapter and a database driver, both prohibited in the studio),
and it uses the standard library.

The route restriction is the real content. ``REVIEW_ALLOWED_ROUTES`` is a closed set of
seven — five reads and two relays — and :meth:`ReviewServiceClient._request` refuses
anything outside it *before* opening a connection. Owner ruling HR-1
(``DISPLAY_AND_TRANSMIT``, amended by FD-10.4): the studio renders what the review
service holds, relays a human's decision verbatim to it and, since front-door seam 6,
asks it to start the worker's own shadow run (FD-10.1 ``START_IS_A_RELAY``). It holds
no approver identity, computes no eligibility, consumes nothing, signals nothing and
resumes nothing; the review service exposes no route for any of those, and this client
could not reach one if it did. On the start relay nothing of the studio's crosses: no
workflow, task, provider, digest or mode choice (FD-10.3); the mode word is pinned to
``shadow`` here and the worker refuses any other. Since front-door seam 7 (FD-11.3)
the fifth read, ``GET /review/audit/{correlation_id}``, returns the worker's own
tenant's audit-ledger rows for one correlation id, raw, with the worker's own chain
verification; the studio names no tenant and re-derives nothing.

Owner ruling ID-1 (``PASS_THROUGH_OPAQUE_TOKEN``, AI-B): the one thing the studio may
carry besides the body is a single opaque proof the operator's request presented,
audience-bound to the review service, forwarded in ``PROOF_HEADER`` on the decision
relay and on no other route. This client treats it as bytes: it never decodes,
inspects, logs, stores or reuses it, and :meth:`_request` refuses to attach it to any
template but ``POST /review/decisions``.
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
    "PROOF_HEADER",
    "PROOF_ROUTE",
    "START_ROUTE",
    "SHADOW_RUN_MODE",
    "AUDIT_ROUTE",
]

#: The complete set of review-service routes the studio may reach. Five reads and two
#: relays: the decision (HR-1) and the start of the worker's own shadow run (FD-10.2);
#: the fifth read is the worker's own ledger by correlation id (FD-11.3).
#: Nothing that grants, authorizes, clears, executes, signals or resumes appears here,
#: and nothing may be added without an owner ruling that revisits HR-1.
REVIEW_ALLOWED_ROUTES: Tuple[Tuple[str, str], ...] = (
    ("GET", "/review/queue"),
    ("GET", "/review/runs/{instance_id}"),
    ("GET", "/review/runs/{instance_id}/events"),
    ("GET", "/review/approvals/{approval_id}"),
    ("POST", "/review/decisions"),
    ("POST", "/review/runs"),
    ("GET", "/review/audit/{correlation_id}"),
)

#: FD-11.3: the ledger read. A read, tenant-less on the wire: the worker reads its own.
AUDIT_ROUTE: Tuple[str, str] = ("GET", "/review/audit/{correlation_id}")

#: FD-10.2: the start relay, and the one mode word it ever sends. The worker's route
#: starts its own shadow workflow and refuses any other mode; the studio has no other
#: word to send, so LIVE is not expressible on this path.
START_ROUTE: Tuple[str, str] = ("POST", "/review/runs")
SHADOW_RUN_MODE = "shadow"

_ALLOWED_TEMPLATES = {(m, p) for m, p in REVIEW_ALLOWED_ROUTES}

#: ID-1: the one header the opaque approver proof travels in, and the one route it may
#: travel on. The name is the review service's (``ugence_governed_review_service.
#: PROOF_HEADER``), spelled here rather than imported because the studio never imports
#: that package.
PROOF_HEADER = "X-Ugence-Approver-Proof"
PROOF_ROUTE: Tuple[str, str] = ("POST", "/review/decisions")

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

    # -- the seven permitted operations ---------------------------------------
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

    def submit_decision(self, body: Dict[str, Any], *, proof: str = "") -> Any:
        """``POST /review/decisions`` — relay a human's decision, verbatim.

        The body is forwarded exactly as the studio received it. Nothing is added: no
        identity, no session, no computed eligibility. ``proof`` is the opaque value
        the operator's request presented in ``PROOF_HEADER``, if any; it is forwarded
        in the same header, unread, and only here (ID-1). The answer is the service's
        typed outcome, whether it recorded, replayed or refused.
        """
        return self._request(*PROOF_ROUTE, body=body, proof=proof)

    def start_shadow_run(self, correlation_id: Optional[str] = None) -> Any:
        """``POST /review/runs`` — ask the worker to start its own shadow run (FD-10).

        The body is the typed correlation id the operator supplied, if any, and the
        pinned mode word. Nothing else exists to send: no workflow, task, provider or
        digest parameter is offered by this method (FD-10.3), and no proof accompanies
        it (ID-1). The answer is the worker's typed outcome, whether it started,
        replayed or refused.
        """
        body: Dict[str, Any] = {"mode": SHADOW_RUN_MODE}
        if correlation_id is not None:
            body["correlation_id"] = correlation_id
        return self._request(*START_ROUTE, body=body)

    def read_audit(self, correlation_id: str) -> Any:
        """``GET /review/audit/{correlation_id}`` — the worker's own tenant's ledger rows
        for one correlation id, raw, with the worker's chain verification (FD-11.3).

        No tenant, no filter and no proof is sent: the worker reads its own tenant and
        the studio names none. The answer is returned as the worker gave it: read,
        or its typed refusal (a chain that does not verify, another schema version, no
        composed reader). An unknown id is the worker's 404, surfaced as not found.
        """
        return self._request(*AUDIT_ROUTE, path_params={"correlation_id": correlation_id})

    # -- internals ------------------------------------------------------------
    def _request(
        self,
        method: str,
        template: str,
        *,
        path_params: Optional[Dict[str, str]] = None,
        query: Optional[Dict[str, str]] = None,
        body: Optional[Dict[str, Any]] = None,
        proof: str = "",
    ) -> Any:
        if proof and (method, template) != PROOF_ROUTE:
            # The proof rides the decision relay and nothing else. A read carrying it
            # is refused here, before a connection is opened, whatever the caller did.
            raise ReviewServiceUnavailable(
                f"an approver proof may only accompany {PROOF_ROUTE[0]} {PROOF_ROUTE[1]}, "
                f"never {method} {template}"
            )
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

        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if proof:
            headers[PROOF_HEADER] = proof
        request = urllib.request.Request(
            url=self._base + path,
            method=method,
            data=json.dumps(body).encode("utf-8") if body is not None else None,
            headers=headers,
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
