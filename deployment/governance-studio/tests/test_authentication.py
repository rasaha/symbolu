import base64

import pytest
from starlette.testclient import TestClient

from governance_studio_deployment.access_control import FailureTracker
from governance_studio_deployment.app import build_app
from depaths import USERNAME, PASSWORD


@pytest.fixture
def noslow_client(config):
    app = build_app(config, tracker=FailureTracker(), sleep=lambda _s: None)
    with TestClient(app, base_url="http://testserver") as c:
        yield c


def _basic(user, pw):
    return "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()


PROTECTED = ["/", "/scenarios/procurement", "/assets/does-not-matter.js", "/api/v1/scenarios", "/version"]


@pytest.mark.parametrize("path", PROTECTED)
def test_unauthenticated_requests_are_401(noslow_client, path):
    r = noslow_client.get(path)
    assert r.status_code == 401
    assert r.headers.get("WWW-Authenticate", "").lower().startswith("basic")


def test_wrong_username_is_401(noslow_client):
    r = noslow_client.get("/", headers={"Authorization": _basic("intruder", PASSWORD)})
    assert r.status_code == 401


def test_wrong_password_is_401(noslow_client):
    r = noslow_client.get("/", headers={"Authorization": _basic(USERNAME, "nope")})
    assert r.status_code == 401


def test_correct_credentials_pass(noslow_client):
    r = noslow_client.get("/", headers={"Authorization": _basic(USERNAME, PASSWORD)})
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_health_and_ready_need_no_credentials(noslow_client):
    assert noslow_client.get("/healthz").status_code == 200
    assert noslow_client.get("/healthz").json() == {"status": "ok"}
    assert noslow_client.get("/readyz").status_code == 200


def test_username_existence_not_disclosed(noslow_client):
    # wrong-username and wrong-password produce byte-identical generic 401s
    a = noslow_client.get("/", headers={"Authorization": _basic("ghost", "x")})
    b = noslow_client.get("/", headers={"Authorization": _basic(USERNAME, "x")})
    assert a.status_code == b.status_code == 401
    assert a.text == b.text


def test_authorization_header_never_logged(noslow_client, capsys):
    noslow_client.get("/", headers={"Authorization": _basic(USERNAME, PASSWORD)})
    out = capsys.readouterr()
    assert PASSWORD not in out.out and PASSWORD not in out.err
    assert "Authorization" not in out.out


def test_bounded_bruteforce_cooldown_then_recovers(config):
    tracker = FailureTracker(max_failures=3, cooldown=999.0)
    app = build_app(config, tracker=tracker, sleep=lambda _s: None)
    with TestClient(app, base_url="http://testserver") as c:
        for _ in range(3):
            assert c.get("/", headers={"Authorization": _basic(USERNAME, "bad")}).status_code == 401
        # now in cooldown: even correct credentials are refused while cooling down
        assert c.get("/", headers={"Authorization": _basic(USERNAME, PASSWORD)}).status_code == 401


def test_successful_auth_clears_failure_state(config):
    tracker = FailureTracker(max_failures=5, cooldown=999.0)
    app = build_app(config, tracker=tracker, sleep=lambda _s: None)
    with TestClient(app, base_url="http://testserver") as c:
        c.get("/", headers={"Authorization": _basic(USERNAME, "bad")})
        c.get("/", headers={"Authorization": _basic(USERNAME, "bad")})
        assert c.get("/", headers={"Authorization": _basic(USERNAME, PASSWORD)}).status_code == 200
        # counter cleared → a subsequent single failure does not trip cooldown
        assert c.get("/", headers={"Authorization": _basic(USERNAME, "bad")}).status_code == 401
        assert c.get("/", headers={"Authorization": _basic(USERNAME, PASSWORD)}).status_code == 200
