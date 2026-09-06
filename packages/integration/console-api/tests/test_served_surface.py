"""CP-3 — the served surface is closed at five routes.

The ruling's sentence is *a capability does not become public API because the underlying
function exists*. That is not a property of the source; it is a property of the running
application, so these tests interrogate the application object rather than grepping the
file. A future contributor who adds a decorator to serve ``/v1/actions/authorize``
because the function is right there fails here, which is the point.
"""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi", reason="the console API is a FastAPI service")

from ugence_console_api.app import (  # noqa: E402
    SERVED_ROUTES,
    WITHHELD_ROUTES,
    create_app,
)


def _routes(app) -> set[tuple[str, str]]:
    """Every (method, path) the application actually serves, minus FastAPI's own
    documentation endpoints, which are framework furniture and not console API."""
    framework = {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}
    found = set()
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if path is None or methods is None or path in framework:
            continue
        for method in methods:
            if method in {"HEAD", "OPTIONS"}:
                continue
            found.add((method, path))
    return found


def test_the_application_serves_exactly_the_declared_five():
    assert _routes(create_app()) == set(SERVED_ROUTES)


def test_the_four_non_health_routes_are_the_studio_allowlist():
    """The four are not a coincidence of this file: they are the set the studio's
    frozen console allowlist names, and CP-3 packaged exactly them."""
    assert set(SERVED_ROUTES) - {("GET", "/health")} == {
        ("POST", "/v1/governed-loop/shadow"),
        ("POST", "/v1/governed-loop/scenario/{scenario_id}"),
        ("GET", "/v1/audit"),
        ("GET", "/v1/audit/{correlation_id}"),
    }


def test_no_withheld_route_is_served():
    served = _routes(create_app())
    assert set(WITHHELD_ROUTES).isdisjoint(served)


def test_the_withheld_set_is_the_six_the_ruling_names():
    assert set(WITHHELD_ROUTES) == {
        ("POST", "/v1/assertions/evaluate"),
        ("POST", "/v1/actions/authorize"),
        ("POST", "/v1/actions/clear"),
        ("GET", "/v1/modules"),
        ("GET", "/v1/scenarios"),
        ("POST", "/v1/gateway/minimize"),
    }


def test_nothing_that_grants_authorizes_clears_or_executes_is_served():
    """The stronger reading of CP-3, independent of the two literal lists above."""
    banned = ("authorize", "clear", "grant", "execute", "credential", "enforce")
    for _method, path in _routes(create_app()):
        assert not any(word in path.lower() for word in banned), path


def test_the_capabilities_still_exist_and_are_simply_not_served():
    """CP-3 withdrew six *surfaces*, not six functions: the loop needs all four
    capabilities, so a test that passed by deleting them would be the wrong fix."""
    from ugence_console_api.capabilities import (
        action_control,
        context_gateway,
        operational_safety,
        truth_evidence,
    )

    assert callable(action_control.authorize)
    assert callable(truth_evidence.evaluate)
    assert callable(operational_safety.clear)
    assert callable(context_gateway.minimize)
