"""An in-process test issuer: runtime-generated keys, a JWKS served over plain HTTP on
127.0.0.1 only, and tokens signed in-test. It exists so the adapter can be proven
without egress. It is a test fixture and lives only under ``tests/``; no Ugence
package is an issuer (adapter ADR §5, prohibitions)."""

from __future__ import annotations

import base64
import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa
from jwt.algorithms import ECAlgorithm, OKPAlgorithm, RSAAlgorithm

__all__ = ["InProcessIssuer", "b64url"]


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _pem(private_key) -> bytes:
    return private_key.private_bytes(serialization.Encoding.PEM,
                                     serialization.PrivateFormat.PKCS8,
                                     serialization.NoEncryption())


class InProcessIssuer:
    """Keys, a JWKS endpoint and a signer, all in this process."""

    def __init__(self, *, issuer: str = "https://issuer.test", audience: str = "aud") -> None:
        self.issuer = issuer
        self.audience = audience
        self._keys: Dict[str, dict] = {}   # kid -> {alg, pem, jwk}
        self.published: set = set()
        self.fetches = 0
        self.fail_next = 0            # serve this many 503s before answering again
        self.serve_malformed = False  # answer with a body that is not a JWKS
        self.serve_symmetric = False  # include an 'oct' key in the JWKS
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    # -- keys --------------------------------------------------------------------
    def add_key(self, alg: str, *, kid: Optional[str] = None, publish: bool = True) -> str:
        kid = kid or f"{alg.lower()}-{uuid.uuid4().hex[:8]}"
        if alg == "RS256":
            private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            jwk = RSAAlgorithm.to_jwk(private.public_key(), as_dict=True)
        elif alg == "ES256":
            private = ec.generate_private_key(ec.SECP256R1())
            jwk = ECAlgorithm.to_jwk(private.public_key(), as_dict=True)
        elif alg == "EdDSA":
            private = ed25519.Ed25519PrivateKey.generate()
            jwk = OKPAlgorithm.to_jwk(private.public_key(), as_dict=True)
        else:
            raise ValueError(alg)
        jwk = dict(jwk, kid=kid, alg=alg, use="sig")
        self._keys[kid] = {"alg": alg, "pem": _pem(private), "jwk": jwk}
        if publish:
            self.published.add(kid)
        return kid

    def unpublish(self, kid: str) -> None:
        self.published.discard(kid)

    def jwks(self) -> dict:
        keys = [self._keys[k]["jwk"] for k in sorted(self.published)]
        if self.serve_symmetric:
            keys.append({"kty": "oct", "kid": "oct-1", "alg": "HS256", "k": b64url(b"secret")})
        return {"keys": keys}

    # -- signing ------------------------------------------------------------------
    def mint(self, claims: Dict[str, Any], *, kid: str, alg: Optional[str] = None,
             typ: Optional[str] = "at+jwt", headers: Optional[dict] = None,
             pem: Optional[bytes] = None) -> str:
        """Sign ``claims`` with the key ``kid`` (or ``pem``, to forge with a foreign
        key under a published kid). ``alg`` defaults to the key's own."""

        entry = self._keys[kid]
        hdr = {"kid": kid}
        if typ is not None:
            hdr["typ"] = typ
        hdr.update(headers or {})
        return jwt.encode(claims, pem or entry["pem"], algorithm=alg or entry["alg"], headers=hdr)

    def mint_unsigned(self, claims: Dict[str, Any], *, kid: str, typ: str = "at+jwt") -> str:
        header = {"alg": "none", "typ": typ, "kid": kid}
        return ".".join((b64url(json.dumps(header).encode()), b64url(json.dumps(claims).encode()), ""))

    def mint_hmac(self, claims: Dict[str, Any], *, kid: str, typ: str = "at+jwt") -> str:
        return jwt.encode(claims, "shared-secret", algorithm="HS256", headers={"kid": kid, "typ": typ})

    def foreign_pem(self, alg: str = "RS256") -> bytes:
        """A key this issuer never publishes."""

        kid = self.add_key(alg, publish=False)
        return self._keys.pop(kid)["pem"]

    # -- the endpoint ------------------------------------------------------------
    @property
    def jwks_url(self) -> str:
        assert self._server is not None, "issuer not started"
        return f"http://127.0.0.1:{self._server.server_port}/jwks.json"

    def start(self) -> None:
        issuer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_GET(self):
                issuer.fetches += 1
                if self.path != "/jwks.json":
                    return self._send(404, b'{"detail":"unknown"}')
                if issuer.fail_next > 0:
                    issuer.fail_next -= 1
                    return self._send(503, b'{"detail":"issuer unavailable"}')
                if issuer.serve_malformed:
                    return self._send(200, b"<html>not a jwks</html>")
                return self._send(200, json.dumps(issuer.jwks()).encode())

            def _send(self, status, body):
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self._server = HTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
