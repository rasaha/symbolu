"""Real HTTPS/TLS behavior over a live uvicorn server (P3E §12, §25).

Starts the packaged app under uvicorn with the test certificate on a loopback port
and drives it with a real TLS client, then asserts TLS-version policy and that no
plaintext application listener exists.
"""
import base64
import socket
import ssl
import threading
import time
from contextlib import closing

import pytest

from governance_studio_deployment.app import build_app
from governance_studio_deployment.access_control import FailureTracker
from depaths import CERTS, USERNAME, PASSWORD
import os

AUTH = "Basic " + base64.b64encode(f"{USERNAME}:{PASSWORD}".encode()).decode()


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def live_server(request):
    import uvicorn

    # module-scoped: build a config without the function-scoped fixtures
    from governance_studio_deployment.config import DeploymentConfig
    from governance_studio_deployment.passwords import hash_password
    from depaths import FRONTEND_DIR, SCENARIOS_ROOT, MANIFEST

    config = DeploymentConfig.from_env(
        mode="test", username=USERNAME, password_hash=hash_password(PASSWORD),
        tls_cert_file=os.path.join(CERTS, "server.crt"), tls_key_file=os.path.join(CERTS, "server.key"),
        allowed_hosts=["127.0.0.1", "localhost", "testserver"],
        frontend_dir=FRONTEND_DIR, scenarios_root=SCENARIOS_ROOT, manifest_path=MANIFEST,
    )
    port = _free_port()
    app = build_app(config, tracker=FailureTracker(), sleep=lambda _s: None)
    uconfig = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error",
                             ssl_certfile=config.tls_cert_file, ssl_keyfile=config.tls_key_file,
                             ssl_version=ssl.PROTOCOL_TLS_SERVER)
    server = uvicorn.Server(uconfig)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    assert server.started, "uvicorn TLS server did not start"
    yield port
    server.should_exit = True
    thread.join(timeout=5)


def _tls_get(port, path, *, headers=None, min_v=ssl.TLSVersion.TLSv1_2, max_v=None):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.minimum_version = min_v
    if max_v is not None:
        ctx.maximum_version = max_v
    raw = socket.create_connection(("127.0.0.1", port), timeout=5)
    with ctx.wrap_socket(raw, server_hostname="127.0.0.1") as tls:
        req = f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n"
        for k, v in (headers or {}).items():
            req += f"{k}: {v}\r\n"
        req += "\r\n"
        tls.sendall(req.encode())
        chunks = []
        while True:
            data = tls.recv(4096)
            if not data:
                break
            chunks.append(data)
    return b"".join(chunks).decode("latin-1")


def test_tls_connection_succeeds_and_requires_auth(live_server):
    resp = _tls_get(live_server, "/healthz")
    assert "200" in resp.split("\r\n")[0]
    # protected path unauthenticated -> 401 with HSTS header present
    resp = _tls_get(live_server, "/")
    assert "401" in resp.split("\r\n")[0]
    assert "strict-transport-security" in resp.lower()


def test_authenticated_tls_request_serves_app(live_server):
    resp = _tls_get(live_server, "/", headers={"Authorization": AUTH})
    assert "200" in resp.split("\r\n")[0]


def test_tls_1_0_and_1_1_are_rejected(live_server):
    for bad in (ssl.TLSVersion.TLSv1, ssl.TLSVersion.TLSv1_1):
        with pytest.raises((ssl.SSLError, OSError)):
            _tls_get(live_server, "/healthz", min_v=bad, max_v=bad)


def test_plaintext_http_does_not_serve_the_app(live_server):
    # a plaintext HTTP/1.1 request to the TLS port must not yield an application 200
    raw = socket.create_connection(("127.0.0.1", live_server), timeout=5)
    try:
        raw.sendall(b"GET /healthz HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
        data = raw.recv(4096)
    except OSError:
        data = b""
    finally:
        raw.close()
    assert b"200 OK" not in data  # TLS listener does not answer plaintext with an app response
