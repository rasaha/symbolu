"""Deployment middleware (P3E §14, §15, §16).

Trusted-host validation, cross-origin request constraints (Origin + a deployment
request header on mutating requests), security headers, and a hard request-body cap.
Implemented as deployment middleware only — the frozen OpenAPI request schemas are
untouched.
"""
from __future__ import annotations

from typing import List

from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .config import DeploymentConfig

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; "
    "frame-ancestors 'none'; form-action 'self'"
)
PERMISSIONS_POLICY = "geolocation=(), microphone=(), camera=(), payment=(), usb=(), interest-cohort=()"

_API_PREFIX = "/api/"


def _host_only(value: str) -> str:
    return value.split(":")[0].strip().lower()


class TrustedHostMiddleware:
    """Reject requests whose Host is not in the allowlist."""

    def __init__(self, app: ASGIApp, allowed_hosts: List[str]):
        self.app = app
        self.allowed = {_host_only(h) for h in allowed_hosts}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self.allowed:
            return await self.app(scope, receive, send)
        if scope.get("path", "") in ("/healthz", "/readyz"):
            return await self.app(scope, receive, send)  # health probes are host-agnostic
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        host = _host_only(headers.get("host", ""))
        if host not in self.allowed:
            resp = PlainTextResponse("Bad Request", status_code=400)
            return await resp(scope, receive, send)
        return await self.app(scope, receive, send)


class ForwardedProtoGuardMiddleware:
    """Enforce HTTPS when the platform, not this process, terminates TLS.

    In the container deployment the TLS handshake happens here, so a plaintext
    request is impossible by construction. Where a hosting platform terminates TLS
    in front of this process there is no certificate to check, and the only signal
    that the client leg was encrypted is the forwarded protocol. This middleware
    makes that signal load-bearing: anything that is not ``https`` is refused.

    It fails closed. A missing header is refused rather than assumed secure, so a
    misconfigured proxy cannot silently serve the studio over plaintext. It is only
    installed when the configuration says the platform terminates TLS AND the proxy
    is trusted, because reading this header from an untrusted peer would let a
    client assert its own transport security.
    """

    HEADER = "x-forwarded-proto"

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        # A comma-joined chain means several proxies appended to it; the client leg
        # is the first entry, and that is the one that has to have been TLS.
        proto = headers.get(self.HEADER, "").split(",")[0].strip().lower()
        if proto != "https":
            resp = PlainTextResponse("HTTPS required", status_code=400)
            return await resp(scope, receive, send)
        return await self.app(scope, receive, send)


class OriginGuardMiddleware:
    """Same-origin constraint for mutating requests + a deployment request header.

    This is NOT an authorization mechanism; it is an additional cross-origin request
    constraint layered on top of authentication.
    """

    def __init__(self, app: ASGIApp, config: DeploymentConfig):
        self.app = app
        self.config = config

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        method = scope.get("method", "GET").upper()
        path = scope.get("path", "")
        if method in SAFE_METHODS or not path.startswith(_API_PREFIX):
            return await self.app(scope, receive, send)

        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        # deployment request header required on mutating API requests
        if headers.get(self.config.request_header_name.lower()) != self.config.request_header_value:
            return await PlainTextResponse("Forbidden", status_code=403)(scope, receive, send)
        # if an Origin is present it must match an allowed host (reject cross-origin browsers)
        origin = headers.get("origin")
        if origin:
            origin_host = _host_only(origin.split("://")[-1])
            allowed = {_host_only(h) for h in self.config.allowed_hosts} or {_host_only(headers.get("host", ""))}
            if origin_host not in allowed:
                return await PlainTextResponse("Forbidden", status_code=403)(scope, receive, send)
        return await self.app(scope, receive, send)


class SecurityHeadersMiddleware:
    """Attach the deployment security-header policy to every response."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope.get("path", "")

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                existing = {k.decode().lower() for k, _ in headers}

                def add(name: str, value: str) -> None:
                    if name.lower() not in existing:
                        headers.append((name.encode("latin-1"), value.encode("latin-1")))

                add("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
                add("Content-Security-Policy", CSP)
                add("X-Content-Type-Options", "nosniff")
                add("Referrer-Policy", "no-referrer")
                add("Permissions-Policy", PERMISSIONS_POLICY)
                add("Cross-Origin-Opener-Policy", "same-origin")
                add("Cross-Origin-Resource-Policy", "same-origin")
                add("X-Frame-Options", "DENY")
                # API + auth responses must not be cached; versioned assets may be immutable
                if path.startswith(_API_PREFIX) or path in ("/", "/index.html"):
                    add("Cache-Control", "no-store")
                elif path.startswith("/assets/"):
                    add("Cache-Control", "public, max-age=31536000, immutable")
                else:
                    add("Cache-Control", "no-store")
            await send(message)

        return await self.app(scope, receive, send_wrapper)


class BodySizeLimitMiddleware:
    """Reject over-large request bodies without buffering them (P3E §16)."""

    def __init__(self, app: ASGIApp, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        cl = headers.get("content-length")
        if cl and cl.isdigit() and int(cl) > self.max_bytes:
            return await PlainTextResponse("Payload Too Large", status_code=413)(scope, receive, send)

        seen = 0

        async def limited_receive() -> Message:
            nonlocal seen
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > self.max_bytes:
                    return {"type": "http.disconnect"}
            return message

        return await self.app(scope, limited_receive, send)
