"""Local HTTP server round-trip (real sockets, ephemeral port)."""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request

import pytest

from cyber_security.behavioral_biometrics.collector_app import fixtures, server
from cyber_security.behavioral_biometrics.version import ORIGIN_REAL


@pytest.fixture()
def live_server(tmp_path):
    srv = server.build_server(str(tmp_path), "127.0.0.1", 0)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    time.sleep(0.2)
    yield f"http://127.0.0.1:{port}"
    srv.shutdown()


def _get(base, path):
    return urllib.request.urlopen(base + path, timeout=5).read()


def _post(base, path, obj):
    req = urllib.request.Request(base + path, data=json.dumps(obj).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=5).read())


def test_serves_static_and_consent(live_server):
    assert b"Behavioral Instrumentation Pilot" in _get(live_server, "/")
    assert b"KeyClass" in _get(live_server, "/static/app.js")
    assert "<p>" in json.loads(_get(live_server, "/api/consent-summary"))["html"]


def test_ingest_neutral_and_no_leaks(live_server):
    res = _post(live_server, "/api/session", fixtures.sample_browser_session(session_id="s0"))
    assert res["ok"] and res["raw_content_leaks"] == []
    assert "identity" not in res["completion_message"].lower()
    assert res["instrumentation_verdict"].startswith("INSTRUMENTATION_")


def test_real_without_consent_rejected(live_server):
    with pytest.raises(urllib.error.HTTPError) as ei:
        _post(live_server, "/api/session",
              fixtures.sample_browser_session(origin=ORIGIN_REAL, with_consent=False, session_id="x"))
    assert ei.value.code == 400


def test_list_and_delete(live_server):
    _post(live_server, "/api/session", fixtures.sample_browser_session(session_id="s1"))
    sessions = json.loads(_get(live_server, "/api/sessions"))["sessions"]
    assert any(s["session_id"] == "s1" for s in sessions)
    d = _post(live_server, "/api/delete", {"participant": "demo_p", "session_id": "s1"})
    assert d["deleted"]


def test_non_local_bind_refused(tmp_path):
    with pytest.raises(ValueError):
        server.build_server(str(tmp_path), "0.0.0.0", 0)


def test_bad_json_rejected(live_server):
    req = urllib.request.Request(live_server + "/api/session", data=b"{bad",
                                 headers={"Content-Type": "application/json"}, method="POST")
    with pytest.raises(urllib.error.HTTPError) as ei:
        urllib.request.urlopen(req, timeout=5)
    assert ei.value.code == 400
