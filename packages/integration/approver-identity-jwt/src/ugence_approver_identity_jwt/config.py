"""Explicit configuration (IA-3, IA-4). Nothing here has a discovered or inferred
default: the issuer, the audience the review service is bound to, the JWKS URL, and
the two claim names that decide tenant and actor type are all the composition root's
statements, and the adapter refuses to start without the first three.

One issuer profile beyond the RFC 9068 default exists, and only one: the Cloudflare
Access profile the owner ratified for the designated AP-3 issuer (rulings AP3-D1 to
AP3-D3, ``ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md`` §20.7). It is selected by name, it
is structurally limited to a ``https://<team>.cloudflareaccess.com`` issuer, and it
changes nothing about any other issuer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlsplit

from .errors import AdapterConfigurationError

__all__ = ["AdapterConfig", "LOOPBACK_HOSTS", "RFC9068_PROFILE", "CLOUDFLARE_ACCESS_PROFILE",
           "ISSUER_PROFILES"]

#: The only hosts a plain-HTTP JWKS URL is accepted for, and only outside production:
#: the in-process test issuer. Everything else is HTTPS with default verification.
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})

#: The default profile: IA-1 as ratified, an RFC 9068 ``at+jwt`` access token.
RFC9068_PROFILE = "rfc9068"

#: AP3-D1 to AP3-D3: the one narrowly scoped enterprise-issuer profile. ``typ: JWT``;
#: the tenant is a static issuer-and-audience binding corroborated by the verified
#: email's domain; the actor type is the ratified claim-shape mapping. Nothing about
#: it applies to any other profile.
CLOUDFLARE_ACCESS_PROFILE = "cloudflare-access"

ISSUER_PROFILES = (RFC9068_PROFILE, CLOUDFLARE_ACCESS_PROFILE)

#: What an issuer under the Cloudflare Access profile must look like, exactly: the
#: team's own Access domain, https, no path, no port. Anything else is not that profile.
_CLOUDFLARE_ISSUER = re.compile(r"^https://[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.cloudflareaccess\.com$")
_CLOUDFLARE_CERTS_PATH = "/cdn-cgi/access/certs"
_DOMAIN = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


@dataclass(frozen=True)
class AdapterConfig:
    """What the adapter is told, once, by whoever composes it.

    ``tenant_claim`` names the claim carrying the tenant; unset, no tenant is ever
    recorded and the service's ID-4 rule sees an empty claim. ``actor_type_claim``
    and ``human_actor_type_value`` are set together or not at all; unset, every
    proven subject is ``SYSTEM`` and can never decide (IA-4). ``production`` refuses
    the loopback exception below.

    ``issuer_profile`` is ``rfc9068`` unless the composition root names the Cloudflare
    Access profile, in which case ``bound_tenant`` and ``verified_email_domain`` are
    required and the three claim-name fields above must stay unset: under that
    profile the tenant and the actor type come from the owner's ratified mapping
    (AP3-D2, AP3-D3), never from a configured claim name.
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
    issuer_profile: str = RFC9068_PROFILE
    bound_tenant: Optional[str] = None
    verified_email_domain: Optional[str] = None

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
        for name in ("tenant_claim", "actor_type_claim", "human_actor_type_value",
                     "bound_tenant", "verified_email_domain"):
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
        if self.issuer_profile not in ISSUER_PROFILES:
            raise AdapterConfigurationError(
                f"AdapterConfig.issuer_profile must be one of {list(ISSUER_PROFILES)}")
        if self.issuer_profile == RFC9068_PROFILE:
            if self.bound_tenant is not None or self.verified_email_domain is not None:
                raise AdapterConfigurationError(
                    "AdapterConfig.bound_tenant and verified_email_domain belong to the "
                    "cloudflare-access profile only; the rfc9068 profile reads a configured "
                    "tenant claim (IA-4) and binds nothing statically"
                )
            return
        self._check_cloudflare_profile(parts)

    def _check_cloudflare_profile(self, jwks_parts) -> None:
        """AP3-D1 to AP3-D3: the profile is structurally tied to one Access team and
        carries its own two mappings; the IA-4 claim names must not also be set."""
        if not _CLOUDFLARE_ISSUER.match(self.issuer):
            raise AdapterConfigurationError(
                "the cloudflare-access profile requires issuer exactly "
                "https://<team>.cloudflareaccess.com"
            )
        issuer_host = urlsplit(self.issuer).hostname
        loopback = jwks_parts.scheme == "http" and jwks_parts.hostname in LOOPBACK_HOSTS
        if not loopback and not (jwks_parts.scheme == "https"
                                 and jwks_parts.hostname == issuer_host
                                 and jwks_parts.path == _CLOUDFLARE_CERTS_PATH
                                 and not jwks_parts.query and not jwks_parts.fragment):
            raise AdapterConfigurationError(
                "the cloudflare-access profile requires jwks_url exactly "
                f"{self.issuer}{_CLOUDFLARE_CERTS_PATH} (IA-3: configured, never discovered); "
                "a loopback URL is accepted only outside production, for the conformance harness"
            )
        for name in ("tenant_claim", "actor_type_claim", "human_actor_type_value"):
            if getattr(self, name) is not None:
                raise AdapterConfigurationError(
                    f"AdapterConfig.{name} must be unset under the cloudflare-access profile: "
                    "the tenant is a static issuer-and-audience binding (AP3-D2) and the actor "
                    "type is the ratified claim-shape mapping (AP3-D3)"
                )
        if self.bound_tenant is None or self.verified_email_domain is None:
            raise AdapterConfigurationError(
                "the cloudflare-access profile requires bound_tenant and verified_email_domain: "
                "the binding is a configured statement, never a derivation"
            )
        domain = self.verified_email_domain
        if domain != domain.strip().lower() or not _DOMAIN.match(domain):
            raise AdapterConfigurationError(
                "AdapterConfig.verified_email_domain must be a lower-case DNS domain "
                "(compared case-insensitively against the verified email's domain)"
            )
        if any(ch.isspace() for ch in self.bound_tenant) or self.bound_tenant != self.bound_tenant.strip():
            raise AdapterConfigurationError("AdapterConfig.bound_tenant must be a typed token")
