"""A deliberately small client for ``ugence_console_api``.

Two design choices, both load-bearing.

**It reaches the console over HTTP, never by import.** The console is a separate
service with its own store; importing it would pull a second application's state into
the studio process and would put a database-shaped dependency behind the studio's
"no database" rule. Over HTTP the boundary stays a boundary.

**It uses the standard library.** ``urllib.request`` costs no new backend dependency,
which the studio's own architecture test enforces — adding ``requests`` or ``httpx`` to
serve four routes would be a dependency the product carries forever.

The route restriction is the real content of this module. ``CONSOLE_ALLOWED_ROUTES``
is a closed set of four, and :meth:`ConsoleClient._request` refuses anything outside it
*before* opening a connection. The console also exposes ``/v1/actions/authorize`` and
``/v1/actions/clear``; under owner ruling SD-2 those are permanently not the studio's to
call, so this client cannot reach them even by mistake or by a caller passing a crafted
path.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional, Tuple

__all__ = ["ConsoleClient", "ConsoleUnavailable", "CONSOLE_ALLOWED_ROUTES"]

#: The complete set of console routes the studio may reach. Two shadow-only writes and
#: two reads. Nothing that grants, authorizes, clears or executes appears here, and
#: nothing may be added without an owner ruling that revisits SD-2.
CONSOLE_ALLOWED_ROUTES: Tuple[Tuple[str, str], ...] = (
    ("POST", "/v1/governed-loop/shadow"),
    ("POST", "/v1/governed-loop/scenario/{scenario_id}"),
    ("GET", "/v1/audit"),
    ("GET", "/v1/audit/{correlation_id}"),
)

_ALLOWED_TEMPLATES = {(m, p) for m, p in CONSOLE_ALLOWED_ROUTES}


class ConsoleUnavailable(RuntimeError):
    """The console could not be reached, or answered unusably.

    Surfaced to the caller as a typed diagnostic. Never silently rendered as an empty
    result: "the console said nothing" and "the console is unreachable" must not look
    alike on an audit screen.
    """


class ConsoleClient:
    """Read/shadow access to ``ugence_console_api``."""

    def __init__(self, base_url: str, *, timeout_s: float = 10.0) -> None:
        self._base = base_url.rstrip("/")
        self._timeout = timeout_s

    # -- the four permitted operations ----------------------------------------
    def governed_loop_shadow(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """``POST /v1/governed-loop/shadow`` — the console's SHADOW governed loop."""
        return self._request("POST", "/v1/governed-loop/shadow", body=payload)

    def governed_loop_scenario(self, scenario_id: str) -> Dict[str, Any]:
        """``POST /v1/governed-loop/scenario/{scenario_id}`` — a frozen console scenario."""
        return self._request(
            "POST",
            "/v1/governed-loop/scenario/{scenario_id}",
            path_params={"scenario_id": scenario_id},
            body={},
        )

    def audit_ids(self) -> Any:
        """``GET /v1/audit`` — known correlation ids."""
        return self._request("GET", "/v1/audit")

    def audit_chain(self, correlation_id: str) -> Any:
        """``GET /v1/audit/{correlation_id}`` — one reconstructed decision chain."""
        return self._request(
            "GET",
            "/v1/audit/{correlation_id}",
            path_params={"correlation_id": correlation_id},
        )

    # -- internals ------------------------------------------------------------
    def _request(
        self,
        method: str,
        template: str,
        *,
        path_params: Optional[Dict[str, str]] = None,
        body: Optional[Dict[str, Any]] = None,
    ) -> Any:
        if (method, template) not in _ALLOWED_TEMPLATES:
            # Refused before a connection is opened. The restriction is a property of
            # the client, not of the caller's good behaviour.
            raise ConsoleUnavailable(
                f"route {method} {template} is not in the studio's permitted console "
                "route set; the studio never grants, authorizes, clears or executes"
            )

        path = template
        for key, value in (path_params or {}).items():
            # Quote with an empty safe set: a correlation id carrying a slash must not
            # become a different path than the one that was allowlisted.
            path = path.replace("{" + key + "}", urllib.parse.quote(str(value), safe=""))

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
            raise ConsoleUnavailable(
                f"console returned HTTP {exc.code} for {method} {path}"
            ) from exc
        except Exception as exc:  # noqa: BLE001 - URLError, socket timeout, DNS, ...
            raise ConsoleUnavailable(
                f"console unreachable for {method} {path}: {type(exc).__name__}"
            ) from exc

        try:
            return json.loads(raw.decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - a non-JSON body is unusable
            raise ConsoleUnavailable(
                f"console returned a non-JSON body for {method} {path}"
            ) from exc
