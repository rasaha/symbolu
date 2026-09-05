"""Explicit configuration of the worker (ADR §3, rulings CR-3, CR-4, CR-5).

Every value comes from ``UGENCE_REVIEW_*`` or an explicit override; nothing is
discovered. ``deployment_mode`` has exactly two values. ``production`` fails closed on
everything ``validate`` lists; ``test`` is loopback development and is named as such
wherever it is used. Neither mode certifies anything or enables LIVE execution.
"""

from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .redaction import redact_dsn

__all__ = ["MODES", "ENV_PREFIX", "WorkerConfig", "WorkerConfigError", "is_private_bind"]

MODES = ("production", "test")
ENV_PREFIX = "UGENCE_REVIEW_"
DEFAULT_PORT = 8444


class WorkerConfigError(Exception):
    """The configuration is invalid; the worker refuses to compose (fail closed)."""

    code = "WORKER_CONFIG_INVALID"


def _env(name: str) -> Optional[str]:
    value = os.environ.get(ENV_PREFIX + name)
    return value if value not in (None, "") else None


def is_private_bind(host: str) -> bool:
    """CR-3: the listener binds the private segment only.

    Accepted: loopback, RFC 1918 and unique-local addresses, and the name
    ``localhost``. Refused: the unspecified address (every interface), public
    addresses, multicast, and any other hostname, whose resolution this process
    cannot vouch for.
    """

    if host == "localhost":
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    if address.is_loopback:
        return True
    if address.is_unspecified or address.is_multicast or address.is_reserved:
        return False
    return address.is_private


@dataclass(frozen=True)
class WorkerConfig:
    deployment_mode: str
    app_database_url: str
    system_database_url: str
    data_dir: str
    tenant_id: str
    required_role: str
    definition_digest: str
    bind_host: str = "127.0.0.1"
    port: int = DEFAULT_PORT
    tls_cert_file: str = ""
    tls_key_file: str = ""
    requester_ref: str = "governed-runtime-worker"
    worker_id: str = "worker-1"
    identity_issuer: str = ""
    identity_audience: str = ""
    identity_jwks_url: str = ""
    identity_tenant_claim: str = ""
    identity_actor_type_claim: str = ""
    identity_human_actor_value: str = ""

    # -- derived -------------------------------------------------------------------
    @property
    def is_production(self) -> bool:
        return self.deployment_mode == "production"

    @property
    def terminates_tls(self) -> bool:
        return bool(self.tls_cert_file and self.tls_key_file)

    @property
    def identity_configured(self) -> bool:
        return bool(self.identity_issuer and self.identity_audience and self.identity_jwks_url)

    # -- construction --------------------------------------------------------------
    @classmethod
    def from_env(cls, **overrides: Any) -> "WorkerConfig":
        def pick(name: str, default: Any = "") -> Any:
            if name in overrides and overrides[name] is not None:
                return overrides[name]
            return _env(name.upper()) or default

        port = pick("port", DEFAULT_PORT)
        try:
            port = int(port)
        except (TypeError, ValueError):
            port = -1
        return cls(
            deployment_mode=str(pick("deployment_mode", "production")).lower(),
            app_database_url=pick("app_database_url"),
            system_database_url=pick("system_database_url"),
            data_dir=pick("data_dir"),
            tenant_id=pick("tenant_id"),
            required_role=pick("required_role"),
            definition_digest=pick("definition_digest"),
            bind_host=pick("bind_host", "127.0.0.1"),
            port=port,
            tls_cert_file=pick("tls_cert_file"),
            tls_key_file=pick("tls_key_file"),
            requester_ref=pick("requester_ref", "governed-runtime-worker"),
            worker_id=pick("worker_id", "worker-1"),
            identity_issuer=pick("identity_issuer"),
            identity_audience=pick("identity_audience"),
            identity_jwks_url=pick("identity_jwks_url"),
            identity_tenant_claim=pick("identity_tenant_claim"),
            identity_actor_type_claim=pick("identity_actor_type_claim"),
            identity_human_actor_value=pick("identity_human_actor_value"),
        )

    # -- validation ----------------------------------------------------------------
    def validate(self) -> List[str]:
        """Every reason this configuration must not compose. Empty means admissible.

        The list is complete rather than first-failure, so an operator fixes one
        deployment in one pass; no entry ever contains a secret.
        """

        errors: List[str] = []
        if self.deployment_mode not in MODES:
            errors.append(f"{ENV_PREFIX}DEPLOYMENT_MODE must be one of {MODES}")
        for label, value in (("APP_DATABASE_URL", self.app_database_url),
                             ("SYSTEM_DATABASE_URL", self.system_database_url)):
            if not value:
                errors.append(f"{ENV_PREFIX}{label} is required")
            elif not value.startswith("postgresql"):
                errors.append(f"{ENV_PREFIX}{label} must be a PostgreSQL DSN")
        if self.app_database_url and self.app_database_url == self.system_database_url:
            errors.append("the application and system databases must differ")
        if not self.data_dir or self.data_dir == ":memory:" or self.data_dir.startswith("file::memory"):
            errors.append(f"{ENV_PREFIX}DATA_DIR must be a durable directory; in-memory stores are refused")
        elif self.is_production and not os.path.isdir(self.data_dir):
            errors.append(f"{ENV_PREFIX}DATA_DIR does not exist or is not a directory")
        for label, value in (("TENANT_ID", self.tenant_id), ("REQUIRED_ROLE", self.required_role),
                             ("DEFINITION_DIGEST", self.definition_digest),
                             ("WORKER_ID", self.worker_id), ("REQUESTER_REF", self.requester_ref)):
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{ENV_PREFIX}{label} is required")
        if not isinstance(self.port, int) or not 1 <= self.port <= 65535:
            errors.append(f"{ENV_PREFIX}PORT must be an integer between 1 and 65535")
        if not self.bind_host:
            errors.append(f"{ENV_PREFIX}BIND_HOST is required")
        elif self.is_production and not is_private_bind(self.bind_host):
            errors.append(f"{ENV_PREFIX}BIND_HOST must be a loopback or private address in "
                          "production; a public or unspecified bind is refused (CR-3)")

        # TLS: mandatory in production (CR-3); a plain listener exists only in test mode.
        if self.is_production:
            for label, path in (("CERT", self.tls_cert_file), ("KEY", self.tls_key_file)):
                if not path:
                    errors.append(f"{ENV_PREFIX}TLS_{label}_FILE is required in production; "
                                  "a plain-HTTP listener is refused (CR-3)")
                elif not os.path.isfile(path) or not os.access(path, os.R_OK):
                    errors.append(f"TLS {label.lower()} file not found or not readable")
        elif (self.tls_cert_file and not self.tls_key_file) or (self.tls_key_file and not self.tls_cert_file):
            errors.append("TLS cert and key files are set together or not at all")

        # Identity: mandatory in production (CR-3); the adapter refuses fixtures itself.
        if self.is_production and not self.identity_configured:
            errors.append(f"{ENV_PREFIX}IDENTITY_ISSUER, IDENTITY_AUDIENCE and IDENTITY_JWKS_URL "
                          "are required in production; an identity port is mandatory (CR-3)")
        if self.identity_configured and self.is_production \
                and not self.identity_jwks_url.startswith("https://"):
            errors.append(f"{ENV_PREFIX}IDENTITY_JWKS_URL must be https in production (CR-5)")
        if (self.identity_actor_type_claim == "") != (self.identity_human_actor_value == ""):
            errors.append(f"{ENV_PREFIX}IDENTITY_ACTOR_TYPE_CLAIM and IDENTITY_HUMAN_ACTOR_VALUE "
                          "are set together or not at all (IA-4)")
        return errors

    # -- rendering -----------------------------------------------------------------
    def redacted(self) -> Dict[str, Any]:
        """Every setting as text an operator may see. The two DSNs are the only
        secrets, and they are the only values rendered through ``redact_dsn``."""

        return {
            "deployment_mode": self.deployment_mode,
            "app_database_url": redact_dsn(self.app_database_url),
            "system_database_url": redact_dsn(self.system_database_url),
            "data_dir": self.data_dir,
            "tenant_id": self.tenant_id,
            "required_role": self.required_role,
            "definition_digest": self.definition_digest,
            "bind_host": self.bind_host,
            "port": self.port,
            "tls": "self" if self.terminates_tls else "none",
            "requester_ref": self.requester_ref,
            "worker_id": self.worker_id,
            "identity_issuer": self.identity_issuer,
            "identity_audience": self.identity_audience,
            "identity_jwks_url": self.identity_jwks_url,
            "identity_tenant_claim": self.identity_tenant_claim,
            "identity_actor_type_claim": self.identity_actor_type_claim,
            "identity_human_actor_value": self.identity_human_actor_value,
        }

    @property
    def secrets(self) -> tuple[str, ...]:
        return tuple(s for s in (self.app_database_url, self.system_database_url) if s)
