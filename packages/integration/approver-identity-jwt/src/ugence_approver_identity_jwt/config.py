"""Explicit configuration (IA-3, IA-4). Nothing here has a discovered or inferred
default: the issuer, the audience the review service is bound to, the JWKS URL, and
the two claim names that decide tenant and actor type are all the composition root's
statements, and the adapter refuses to start without the first three."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlsplit

from .errors import AdapterConfigurationError

__all__ = ["AdapterConfig", "LOOPBACK_HOSTS"]

#: The only hosts a plain-HTTP JWKS URL is accepted for, and only outside production:
#: the in-process test issuer. Everything else is HTTPS with default verification.
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


@dataclass(frozen=True)
class AdapterConfig:
    """What the adapter is told, once, by whoever composes it.

    ``tenant_claim`` names the claim carrying the tenant; unset, no tenant is ever
    recorded and the service's ID-4 rule sees an empty claim. ``actor_type_claim``
    and ``human_actor_type_value`` are set together or not at all; unset, every
    proven subject is ``SYSTEM`` and can never decide (IA-4). ``production`` refuses
    the loopback exception below.
    """

    issuer: str
    audience: str
    jwks_url: str
    tenant_claim: Optional[str] = None
    actor_type_claim: Optional[str] = None
    human_actor_type_value: Optional[str] = None
    max_proof_bytes: int = 8192
    fetch_timeout_s: float = 5.0
    production: bool = False

    def __post_init__(self) -> None:
        for name in ("issuer", "audience", "jwks_url"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise AdapterConfigurationError(f"AdapterConfig.{name} must be a non-empty string")
        parts = urlsplit(self.jwks_url)
        if not parts.hostname:
            raise AdapterConfigurationError("AdapterConfig.jwks_url must name a host")
        if parts.scheme == "https":
            pass
        elif parts.scheme == "http" and parts.hostname in LOOPBACK_HOSTS and not self.production:
            pass  # the in-process test issuer, and nothing else
        else:
            raise AdapterConfigurationError(
                "AdapterConfig.jwks_url must be https; plain http is accepted only for a "
                "loopback host outside production"
            )
        for name in ("tenant_claim", "actor_type_claim", "human_actor_type_value"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise AdapterConfigurationError(f"AdapterConfig.{name} must be unset or non-empty")
        if (self.actor_type_claim is None) != (self.human_actor_type_value is None):
            raise AdapterConfigurationError(
                "AdapterConfig.actor_type_claim and human_actor_type_value are set together "
                "or not at all: HUMAN is an exact configured match, never an inference"
            )
        if not isinstance(self.max_proof_bytes, int) or self.max_proof_bytes <= 0:
            raise AdapterConfigurationError("AdapterConfig.max_proof_bytes must be positive")
        if not isinstance(self.fetch_timeout_s, (int, float)) or self.fetch_timeout_s <= 0:
            raise AdapterConfigurationError("AdapterConfig.fetch_timeout_s must be positive")
