"""Deployment configuration (P3E §9, §12, §13, §14).

All configuration is explicit. Production fails closed when credentials, TLS material,
or allowed hosts are absent. Secrets are never logged. The only two runtime modes are
``production`` (default) and ``test`` (loopback-only local testing).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional

from . import DEPLOYMENT_NAME
from .passwords import is_valid_hash_format

APP_PORT = 8443
REQUEST_HEADER_NAME = "X-Ugence-Request"
REQUEST_HEADER_VALUE = "GovernanceStudio"
MAX_REQUEST_BYTES = 1 * 1024 * 1024  # 1 MiB (§16)
MAX_FAILURES_PER_SOURCE = 10
FAILURE_COOLDOWN_SECONDS = 30.0
FAILED_AUTH_DELAY_SECONDS = 0.5
REQUEST_TIMEOUT_SECONDS = 30
IDLE_TIMEOUT_SECONDS = 60


class DeploymentConfigError(Exception):
    """Raised when deployment configuration is invalid (fail closed)."""

    code = "DEPLOYMENT_CONFIG_INVALID"


def _env(name: str) -> Optional[str]:
    v = os.environ.get(name)
    return v if v not in (None, "") else None


def _split_hosts(raw: Optional[str]) -> List[str]:
    return [h.strip() for h in (raw or "").split(",") if h.strip()]


@dataclass(frozen=True)
class DeploymentConfig:
    mode: str  # "production" | "test"
    username: str
    password_hash: str
    tls_cert_file: str
    tls_key_file: str
    allowed_hosts: List[str]
    frontend_dir: str
    scenarios_root: str
    manifest_path: str
    # "self": this process terminates TLS from tls_cert_file/tls_key_file (the container
# deployment). "platform": TLS is terminated by the hosting platform in front of this
# process, which then has no cert on disk; HTTPS is enforced per request from the
# forwarded protocol instead of from a certificate. It is never optional, only relocated.
    tls_termination: str = "self"
    trusted_proxy: bool = False
    bind_host: str = "0.0.0.0"
    port: int = APP_PORT
    runtime_dir: str = "/var/run/ugence-studio"
    max_request_bytes: int = MAX_REQUEST_BYTES
    request_header_name: str = REQUEST_HEADER_NAME
    request_header_value: str = REQUEST_HEADER_VALUE
    enable_access_log: bool = False
    _errors: List[str] = field(default_factory=list, compare=False)

    @property
    def terminates_tls(self) -> bool:
        """True when this process performs the TLS handshake itself."""
        return self.tls_termination == "self"

    @property
    def is_production(self) -> bool:
        return self.mode == "production"

    @property
    def deployment_name(self) -> str:
        return DEPLOYMENT_NAME

    @classmethod
    def from_env(cls, **overrides) -> "DeploymentConfig":
        mode = (overrides.get("mode") or _env("UGENCE_STUDIO_DEPLOYMENT_MODE") or "production").lower()
        loopback = mode == "test"
        cfg = cls(
            mode=mode,
            username=overrides.get("username") or _env("UGENCE_STUDIO_USERNAME") or "",
            password_hash=overrides.get("password_hash") or _env("UGENCE_STUDIO_PASSWORD_HASH") or "",
            tls_cert_file=overrides.get("tls_cert_file") or _env("UGENCE_STUDIO_TLS_CERT_FILE") or "",
            tls_key_file=overrides.get("tls_key_file") or _env("UGENCE_STUDIO_TLS_KEY_FILE") or "",
            tls_termination=(overrides.get("tls_termination")
                             or _env("UGENCE_STUDIO_TLS_TERMINATION") or "self").lower(),
            allowed_hosts=overrides.get("allowed_hosts") or _split_hosts(_env("UGENCE_STUDIO_ALLOWED_HOSTS")),
            frontend_dir=overrides.get("frontend_dir") or _env("UGENCE_STUDIO_FRONTEND_DIR") or "",
            scenarios_root=overrides.get("scenarios_root") or _env("UGENCE_STUDIO_SCENARIOS_ROOT") or "",
            manifest_path=overrides.get("manifest_path") or _env("UGENCE_STUDIO_MANIFEST") or "",
            trusted_proxy=overrides.get("trusted_proxy", _env("UGENCE_STUDIO_TRUSTED_PROXY") == "1"),
            bind_host=overrides.get("bind_host") or ("127.0.0.1" if loopback else "0.0.0.0"),
            port=int(overrides.get("port") or _env("UGENCE_STUDIO_PORT") or APP_PORT),
            runtime_dir=overrides.get("runtime_dir") or _env("UGENCE_STUDIO_RUNTIME_DIR") or "/var/run/ugence-studio",
            enable_access_log=bool(overrides.get("enable_access_log", _env("UGENCE_STUDIO_ACCESS_LOG") == "1")),
        )
        return cfg

    def validate(self) -> List[str]:
        """Return configuration errors (empty = valid). Never raises; never logs secrets."""
        errors: List[str] = []
        if self.mode not in ("production", "test"):
            errors.append(f"unknown deployment mode {self.mode!r}")

        # credentials
        if not self.username:
            errors.append("UGENCE_STUDIO_USERNAME is required (no default username)")
        if not self.password_hash:
            errors.append("UGENCE_STUDIO_PASSWORD_HASH is required (no default password)")
        elif not is_valid_hash_format(self.password_hash):
            errors.append("UGENCE_STUDIO_PASSWORD_HASH has an invalid format")

        # TLS material. HTTPS is mandatory either way; only the terminator differs.
        if self.tls_termination not in ("self", "platform"):
            errors.append(f"unknown UGENCE_STUDIO_TLS_TERMINATION {self.tls_termination!r}")
        elif self.terminates_tls:
            for label, path in (("cert", self.tls_cert_file), ("key", self.tls_key_file)):
                if not path:
                    errors.append(f"UGENCE_STUDIO_TLS_{label.upper()}_FILE is required")
                elif not os.path.isfile(path):
                    errors.append(f"TLS {label} file not found: {path}")
                elif not os.access(path, os.R_OK):
                    errors.append(f"TLS {label} file not readable: {path}")
        else:
            # Platform termination only makes sense behind a proxy whose forwarded
            # protocol header we are willing to read; without that we cannot tell
            # plaintext from TLS and must fail closed rather than assume HTTPS.
            if not self.trusted_proxy:
                errors.append("UGENCE_STUDIO_TLS_TERMINATION=platform requires "
                              "UGENCE_STUDIO_TRUSTED_PROXY=1")
            if self.tls_cert_file or self.tls_key_file:
                errors.append("TLS cert/key files must not be set when the platform "
                              "terminates TLS")

        # hosts
        if self.is_production and not self.allowed_hosts:
            errors.append("UGENCE_STUDIO_ALLOWED_HOSTS is required in production")
        if "*" in self.allowed_hosts and self.is_production:
            errors.append("wildcard allowed host is prohibited in production")

        # packaged assets
        if not self.frontend_dir or not os.path.isdir(self.frontend_dir):
            errors.append("frontend build directory is missing")
        elif not os.path.isfile(os.path.join(self.frontend_dir, "index.html")):
            errors.append("frontend build has no index.html")
        if not self.scenarios_root or not os.path.isdir(self.scenarios_root):
            errors.append("scenarios root is missing")
        if not self.manifest_path or not os.path.isfile(self.manifest_path):
            errors.append("synthetic scenarios manifest is missing")

        return errors
