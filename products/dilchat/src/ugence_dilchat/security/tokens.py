"""Access and refresh token handling.

- **Access token:** short-lived ES256 (ECDSA P-256) JWT, stateless.
- **Refresh token:** opaque high-entropy random string. Only its SHA-256 hash is
  stored server-side (as a ``user_sessions`` row) so any session can be revoked
  immediately and reuse can be detected.

In development/test an ephemeral EC key is generated if none is configured. A
production-like environment must supply ``DILCHAT_ACCESS_TOKEN_PRIVATE_KEY_PEM``
(enforced in :mod:`ugence_dilchat.config`).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import secrets
import uuid

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from ..config import Settings
from ..errors import DilChatError, ErrorCode

_ALG = "ES256"


class TokenService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._issuer = settings.token_issuer
        self._access_ttl = settings.access_token_ttl_seconds
        priv_pem = settings.access_token_private_key_pem
        pub_pem = settings.access_token_public_key_pem
        if priv_pem:
            self._private_key = serialization.load_pem_private_key(
                priv_pem.encode(), password=None
            )
        else:
            # Dev/test only: ephemeral key (config guards production).
            self._private_key = ec.generate_private_key(ec.SECP256R1())
        if pub_pem:
            self._public_key = serialization.load_pem_public_key(pub_pem.encode())
        else:
            self._public_key = self._private_key.public_key()

    # --- access token ------------------------------------------------------ #
    def issue_access_token(self, user_id: uuid.UUID, session_id: uuid.UUID) -> str:
        now = dt.datetime.now(dt.UTC)
        claims = {
            "sub": str(user_id),
            "sid": str(session_id),
            "iss": self._issuer,
            "iat": int(now.timestamp()),
            "exp": int((now + dt.timedelta(seconds=self._access_ttl)).timestamp()),
            "jti": uuid.uuid4().hex,
        }
        return jwt.encode(claims, self._sign_key_pem(), algorithm=_ALG)

    def verify_access_token(self, token: str) -> dict:
        try:
            return jwt.decode(
                token,
                self._verify_key_pem(),
                algorithms=[_ALG],
                issuer=self._issuer,
                options={"require": ["exp", "sub", "sid", "iss"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise DilChatError(ErrorCode.AUTH_TOKEN_EXPIRED, "Access token expired") from exc
        except jwt.InvalidTokenError as exc:
            raise DilChatError(ErrorCode.AUTH_TOKEN_INVALID, "Invalid access token") from exc

    def _sign_key_pem(self) -> bytes:
        return self._private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )

    def _verify_key_pem(self) -> bytes:
        return self._public_key.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )


# --- refresh token (opaque) ----------------------------------------------- #
def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
