"""Minimal length-prefixed JSON RPC over Unix sockets (agent->gateway) and
mTLS TCP (gateway->broker). No third-party deps; TLS via stdlib ``ssl``."""

from __future__ import annotations

import json
import socket
import ssl
import struct


def _send(sock, obj):
    data = json.dumps(obj).encode("utf-8")
    sock.sendall(struct.pack(">I", len(data)) + data)


def _recvn(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("connection closed")
        buf += chunk
    return buf


def _recv(sock):
    (n,) = struct.unpack(">I", _recvn(sock, 4))
    return json.loads(_recvn(sock, n).decode("utf-8"))


# ---- Unix socket (agent -> gateway) ----

def unix_call(path, obj, timeout=30):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect(path)
    try:
        _send(s, obj)
        return _recv(s)
    finally:
        s.close()


def serve_unix(path, handler):  # pragma: no cover - long-running
    import grp
    import os
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(path)
    # the agent user reaches the gateway ONLY through this group-restricted socket;
    # the broker mTLS port is not reachable from the agent's network namespace.
    grp_name = os.environ.get("AGW_SOCK_GROUP")
    if grp_name:
        try:
            os.chown(path, -1, grp.getgrnam(grp_name).gr_gid)
        except (KeyError, PermissionError):
            pass
    os.chmod(path, 0o660)
    srv.listen(64)
    while True:
        conn, _ = srv.accept()
        try:
            req = _recv(conn)
            _send(conn, handler(req))
        except Exception as e:  # noqa: BLE001
            try:
                _send(conn, {"error": str(e)})
            except Exception:
                pass
        finally:
            conn.close()


# ---- mTLS TCP (gateway -> broker) ----

def mtls_client_ctx(ca_cert, client_cert, client_key):
    ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=ca_cert)
    ctx.check_hostname = False
    ctx.load_cert_chain(certfile=client_cert, keyfile=client_key)
    return ctx


def mtls_server_ctx(ca_cert, server_cert, server_key):
    ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH, cafile=ca_cert)
    ctx.verify_mode = ssl.CERT_REQUIRED  # require + verify the client certificate
    ctx.load_cert_chain(certfile=server_cert, keyfile=server_key)
    return ctx


def mtls_call(host, port, ctx, obj, timeout=30):
    raw = socket.create_connection((host, port), timeout=timeout)
    s = ctx.wrap_socket(raw, server_hostname="broker")
    try:
        _send(s, obj)
        return _recv(s)
    finally:
        s.close()


def serve_mtls(host, port, ctx, handler):  # pragma: no cover - long-running
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen(64)
    while True:
        raw, _ = srv.accept()
        try:
            conn = ctx.wrap_socket(raw, server_side=True)
        except ssl.SSLError:
            raw.close()
            continue  # rejected client (no/invalid cert)
        try:
            peer = _peer_cn(conn)
            req = _recv(conn)
            req["_peer_cn"] = peer
            _send(conn, handler(req))
        except Exception as e:  # noqa: BLE001
            try:
                _send(conn, {"error": str(e)})
            except Exception:
                pass
        finally:
            conn.close()


def _peer_cn(conn):
    cert = conn.getpeercert() or {}
    for tup in cert.get("subject", ()):
        for k, v in tup:
            if k == "commonName":
                return v
    return None
