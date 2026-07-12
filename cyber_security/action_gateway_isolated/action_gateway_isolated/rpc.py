"""Length-prefixed JSON RPC over Unix sockets (agent->gateway) and mTLS TCP
(gateway->broker). No third-party deps; TLS via stdlib ``ssl``.

N4 remediation — BOUNDED TRANSPORT (deterministic failure under overload)
------------------------------------------------------------------------
The prior server was single-threaded with an unbounded 4-byte length prefix and no
socket timeouts: one slow or oversized client stalled every caller, and a 4 GiB
length prefix invited an allocation bomb. This transport is now bounded on every
axis and sheds load deterministically:
  * MAX_FRAME_BYTES      — request/response frames above the cap are rejected before
                           allocation (memory bound);
  * READ_TIMEOUT         — idle/slow-loris connections time out (idle+read timeout);
  * MAX_CONCURRENCY      — a fixed worker pool + a bounded semaphore cap in-flight
                           work; excess connections get an immediate E_OVERLOADED
                           (back-pressure), never an unbounded queue;
  * ACCEPT_BACKLOG       — bounded listen backlog.

N10 remediation — SAN-BASED WORKLOAD IDENTITY
---------------------------------------------
The broker no longer trusts the certificate CommonName. It extracts the client
certificate's subjectAltName set and requires the gateway's SAN identity. The
gateway, in turn, verifies the broker with ``check_hostname=True`` against the
broker cert's DNS SAN.
"""

from __future__ import annotations

import json
import os
import socket
import ssl
import struct
import threading
from concurrent.futures import ThreadPoolExecutor

MAX_FRAME_BYTES = int(os.environ.get("AGW_MAX_FRAME", 1 << 20))       # 1 MiB
READ_TIMEOUT = float(os.environ.get("AGW_READ_TIMEOUT", 10))          # seconds
MAX_CONCURRENCY = int(os.environ.get("AGW_MAX_CONCURRENCY", 16))
ACCEPT_BACKLOG = int(os.environ.get("AGW_ACCEPT_BACKLOG", 64))


def _send(sock, obj):
    data = json.dumps(obj).encode("utf-8")
    if len(data) > MAX_FRAME_BYTES:
        raise ValueError(f"response frame too large: {len(data)} > {MAX_FRAME_BYTES}")
    sock.sendall(struct.pack(">I", len(data)) + data)


def _recvn(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("connection closed")
        buf += chunk
    return buf


def _recv(sock, max_frame=MAX_FRAME_BYTES):
    (n,) = struct.unpack(">I", _recvn(sock, 4))
    if n > max_frame:
        raise ValueError(f"frame too large: {n} > {max_frame}")  # allocation bound
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
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(path)
    grp_name = os.environ.get("AGW_SOCK_GROUP")
    if grp_name:
        try:
            os.chown(path, -1, grp.getgrnam(grp_name).gr_gid)
        except (KeyError, PermissionError):
            pass
    os.chmod(path, 0o660)
    srv.listen(ACCEPT_BACKLOG)
    _bounded_serve(srv, handler)


# ---- mTLS TCP (gateway -> broker) ----

def mtls_client_ctx(ca_cert, client_cert, client_key):
    ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=ca_cert)
    ctx.check_hostname = True  # N10: verify the broker's SAN (server_hostname="broker")
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
    srv.listen(ACCEPT_BACKLOG)
    _bounded_serve(srv, handler, tls_ctx=ctx)


# ---- bounded concurrent serve loop (shared by both transports) ----

def _bounded_serve(srv, handler, *, tls_ctx=None):  # pragma: no cover - long-running
    sem = threading.BoundedSemaphore(MAX_CONCURRENCY)
    pool = ThreadPoolExecutor(max_workers=MAX_CONCURRENCY)
    while True:
        raw, _ = srv.accept()
        if not sem.acquire(blocking=False):
            _shed_load(raw, tls_ctx)          # deterministic back-pressure
            continue
        pool.submit(_serve_one, raw, handler, tls_ctx, sem)


def _serve_one(raw, handler, tls_ctx, sem):
    try:
        raw.settimeout(READ_TIMEOUT)          # idle/read timeout (slow-loris bound)
        conn = raw
        peer_san = None
        if tls_ctx is not None:
            try:
                conn = tls_ctx.wrap_socket(raw, server_side=True)
            except ssl.SSLError:
                raw.close()
                return                        # rejected client (no/invalid cert)
            peer_san = _peer_san(conn)
        try:
            req = _recv(conn)
            if tls_ctx is not None and isinstance(req, dict):
                req["_peer_san"] = peer_san
            _send(conn, handler(req))
        except Exception as e:  # noqa: BLE001
            try:
                _send(conn, {"error": "E_BAD_REQUEST", "message": str(e)})
            except Exception:
                pass
        finally:
            conn.close()
    finally:
        sem.release()


def _shed_load(raw, tls_ctx):
    """At capacity: reply E_OVERLOADED (best effort) and close — no unbounded queue."""
    try:
        raw.settimeout(READ_TIMEOUT)
        conn = tls_ctx.wrap_socket(raw, server_side=True) if tls_ctx is not None else raw
        try:
            _send(conn, {"error": "E_OVERLOADED"})
        finally:
            conn.close()
    except Exception:  # noqa: BLE001
        try:
            raw.close()
        except Exception:
            pass


# ---- SAN-based peer identity (N10) ----

def _peer_san(conn):
    """Return the peer certificate's subjectAltName entries as 'TYPE:value' strings."""
    cert = conn.getpeercert() or {}
    return [f"{typ}:{val}" for (typ, val) in cert.get("subjectAltName", ())]


def peer_has_identity(peer_san, *identities) -> bool:
    """True iff the peer SAN set contains any of the required identity strings."""
    have = set(peer_san or [])
    return any(i in have for i in identities)
