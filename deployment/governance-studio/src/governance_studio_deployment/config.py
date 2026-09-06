"""Deployment configuration (P3E §9, §12, §13, §14).

All configuration is explicit. Production fails closed when credentials, TLS material,
or allowed hosts are absent. Secrets are never logged. The only two runtime modes are
``production`` (default) and ``test`` (loopback-only local testing).
"""
from __future__ import annotations

import os
import unicodedata
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from urllib.parse import urlsplit

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
#: The only value that enables front-door seam 3 (FD-7.4: one boolean, no list).
SIMULATION_PROVIDER_ENABLED = "1"


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
    trusted_proxy: bool = False
    bind_host: str = "0.0.0.0"
    port: int = APP_PORT
    runtime_dir: str = "/var/run/ugence-studio"
    max_request_bytes: int = MAX_REQUEST_BYTES
    request_header_name: str = REQUEST_HEADER_NAME
    request_header_value: str = REQUEST_HEADER_VALUE
    enable_access_log: bool = False
    #: CR-2: the governed review service (the governed runtime worker's private TLS
    #: listener). Unset means the review screens report a typed gap; nothing else in the
    #: deployment reads it. It is the profile's one permitted outbound destination.
    review_service_url: str = ""
    #: Front-door seam 1 (FD-1, FD-5): the durable sqlite policy registry the studio's
    #: activation root is composed over. Unset means the Constitution screen reports
    #: its typed gap. Read here, handed to build_studio_context(activation_root=...)
    #: and nowhere else. Must lie under the writable runtime volume.
    constitution_registry_path: str = ""
    #: Front-door seam 2 (FD-6): the one tenant this deployment displays, and the typed
    #: policy identities the Authority screen may enumerate, each
    #: ``<policy_family>|<policy_id>|<scope>``. No discovery, no default; both require
    #: the registry path. Read here and handed to build_studio_context only.
    tenant_id: str = ""
    policy_identities: Tuple[str, ...] = ()
    #: Front-door seam 3 (FD-7): the raw value of ``UGENCE_STUDIO_SIMULATION_PROVIDER``.
    #: Exactly ``"1"`` enables the one pinned in-package simulation provider handed to
    #: build_studio_context(provider_registry=...); unset leaves the Simulate screen on
    #: its typed gap; any other value is refused. No provider list is read (FD-4).
    simulation_provider: str = ""
    _errors: List[str] = field(default_factory=list, compare=False)

    @property
    def is_production(self) -> bool:
        return self.mode == "production"

    @property
    def deployment_name(self) -> str:
        return DEPLOYMENT_NAME

    @property
    def review_service_configured(self) -> bool:
        return bool(self.review_service_url)

    @property
    def constitution_registry_configured(self) -> bool:
        return bool(self.constitution_registry_path)

    @property
    def authority_reads_configured(self) -> bool:
        return bool(self.policy_identities)

    @property
    def simulation_provider_enabled(self) -> bool:
        return self.simulation_provider == SIMULATION_PROVIDER_ENABLED

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
            allowed_hosts=overrides.get("allowed_hosts") or _split_hosts(_env("UGENCE_STUDIO_ALLOWED_HOSTS")),
            frontend_dir=overrides.get("frontend_dir") or _env("UGENCE_STUDIO_FRONTEND_DIR") or "",
            scenarios_root=overrides.get("scenarios_root") or _env("UGENCE_STUDIO_SCENARIOS_ROOT") or "",
            manifest_path=overrides.get("manifest_path") or _env("UGENCE_STUDIO_MANIFEST") or "",
            trusted_proxy=overrides.get("trusted_proxy", _env("UGENCE_STUDIO_TRUSTED_PROXY") == "1"),
            bind_host=overrides.get("bind_host") or ("127.0.0.1" if loopback else "0.0.0.0"),
            port=int(overrides.get("port") or _env("UGENCE_STUDIO_PORT") or APP_PORT),
            runtime_dir=overrides.get("runtime_dir") or _env("UGENCE_STUDIO_RUNTIME_DIR") or "/var/run/ugence-studio",
            enable_access_log=bool(overrides.get("enable_access_log", _env("UGENCE_STUDIO_ACCESS_LOG") == "1")),
            review_service_url=(overrides.get("review_service_url")
                                or _env("UGENCE_STUDIO_REVIEW_SERVICE_URL") or "").strip().rstrip("/"),
            constitution_registry_path=(overrides.get("constitution_registry_path")
                                        or _env("UGENCE_STUDIO_CONSTITUTION_REGISTRY_PATH") or "").strip(),
            tenant_id=(overrides.get("tenant_id") or _env("UGENCE_STUDIO_TENANT_ID") or ""),
            policy_identities=tuple(overrides["policy_identities"]) if overrides.get("policy_identities") is not None
            else _split_identities(_env("UGENCE_STUDIO_POLICY_IDENTITIES")),
            simulation_provider=(overrides.get("simulation_provider")
                                 if overrides.get("simulation_provider") is not None
                                 else (_env("UGENCE_STUDIO_SIMULATION_PROVIDER") or "")),
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

        # TLS material
        for label, path in (("cert", self.tls_cert_file), ("key", self.tls_key_file)):
            if not path:
                errors.append(f"UGENCE_STUDIO_TLS_{label.upper()}_FILE is required")
            elif not os.path.isfile(path):
                errors.append(f"TLS {label} file not found: {path}")
            elif not os.access(path, os.R_OK):
                errors.append(f"TLS {label} file not readable: {path}")

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

        # review service relay (CR-2): optional; when set it is one https origin
        if self.review_service_url:
            errors.extend(_review_url_errors(self.review_service_url, self.is_production))

        # constitution registry (front-door seam 1): optional; a file under the runtime volume
        if self.constitution_registry_path:
            errors.extend(_registry_path_errors(self.constitution_registry_path, self.runtime_dir))

        # authority reads (front-door seam 2): typed identities, one tenant, registry required
        if self.policy_identities or self.tenant_id:
            errors.extend(_authority_errors(self.policy_identities, self.tenant_id,
                                            bool(self.constitution_registry_path)))

        # simulation provider (front-door seam 3): one boolean, typed; "1" or unset
        if self.simulation_provider not in ("", SIMULATION_PROVIDER_ENABLED):
            errors.append("UGENCE_STUDIO_SIMULATION_PROVIDER must be '1' to enable the simulation "
                          "provider or unset; no other value is accepted")

        return errors


def _split_identities(raw: Optional[str]) -> Tuple[str, ...]:
    """The raw comma-separated value, split only; validation is ``validate``'s."""
    return tuple(part for part in (raw or "").split(",") if part != "") if raw else ()


def _is_typed_token(value: str) -> bool:
    return (isinstance(value, str) and value != "" and value == value.strip()
            and not any(ch.isspace() for ch in value)
            and unicodedata.is_normalized("NFC", value))


def _authority_errors(identities: Tuple[str, ...], tenant_id: str, registry_configured: bool) -> List[str]:
    """Why ``UGENCE_STUDIO_POLICY_IDENTITIES`` and ``UGENCE_STUDIO_TENANT_ID`` must not be
    used, or nothing. Every identity is exactly ``<policy_family>|<policy_id>|<scope>``,
    each part non-empty, NFC, without whitespace; no duplicates; the tenant likewise;
    neither is admissible without the registry path (nothing to read)."""
    errors: List[str] = []
    if not registry_configured:
        errors.append("UGENCE_STUDIO_POLICY_IDENTITIES and UGENCE_STUDIO_TENANT_ID require "
                      "UGENCE_STUDIO_CONSTITUTION_REGISTRY_PATH; there is no registry to read")
    if identities and not tenant_id:
        errors.append("UGENCE_STUDIO_TENANT_ID is required with UGENCE_STUDIO_POLICY_IDENTITIES")
    if tenant_id and not _is_typed_token(tenant_id):
        errors.append("UGENCE_STUDIO_TENANT_ID must be non-empty, NFC and without whitespace")
    if tenant_id and "|" in tenant_id:
        errors.append("UGENCE_STUDIO_TENANT_ID must not contain '|'")
    seen = set()
    for entry in identities:
        if not _is_typed_token(entry) or entry.count("|") != 2 or any(part == "" for part in entry.split("|")):
            errors.append("UGENCE_STUDIO_POLICY_IDENTITIES entry must be '<policy_family>|<policy_id>|<scope>', "
                          "each part non-empty, NFC and without whitespace")
            continue
        if entry in seen:
            errors.append("UGENCE_STUDIO_POLICY_IDENTITIES has a duplicate entry")
        seen.add(entry)
    return errors


def _registry_path_errors(path: str, runtime_dir: str) -> List[str]:
    """Why ``UGENCE_STUDIO_CONSTITUTION_REGISTRY_PATH`` must not be used, or nothing.

    The registry is a sqlite file (Posture B) and lives only under the writable
    runtime volume: an absolute path below ``runtime_dir``, never in memory, never a
    directory. Whether it is writable is the startup-integrity gate's question.
    """
    if path in (":memory:",) or path.startswith("file:"):
        return ["UGENCE_STUDIO_CONSTITUTION_REGISTRY_PATH must be a file path; an in-memory "
                "registry is not durable and is refused"]
    if not os.path.isabs(path):
        return ["UGENCE_STUDIO_CONSTITUTION_REGISTRY_PATH must be an absolute path"]
    root = os.path.realpath(runtime_dir) if runtime_dir else ""
    candidate = os.path.realpath(path)
    if not root or not (candidate == root or candidate.startswith(root + os.sep)) or candidate == root:
        return ["UGENCE_STUDIO_CONSTITUTION_REGISTRY_PATH must lie under the writable runtime "
                "volume (UGENCE_STUDIO_RUNTIME_DIR); no other path is writable"]
    if os.path.isdir(candidate):
        return ["UGENCE_STUDIO_CONSTITUTION_REGISTRY_PATH names a directory, not a file"]
    return []


def _review_url_errors(url: str, production: bool) -> List[str]:
    """Why ``UGENCE_STUDIO_REVIEW_SERVICE_URL`` must not be used, or nothing.

    The relay speaks to the governed runtime worker's private TLS listener and nothing
    else: an https origin (http only on loopback, only in test mode), no credential in
    the URL, no query, no fragment. The value is never logged.
    """
    errors: List[str] = []
    try:
        parts = urlsplit(url)
    except ValueError:
        return ["UGENCE_STUDIO_REVIEW_SERVICE_URL is not a valid URL"]
    if parts.scheme not in ("https", "http") or not parts.hostname:
        return ["UGENCE_STUDIO_REVIEW_SERVICE_URL must be an http(s) URL with a host"]
    loopback = parts.hostname in ("localhost", "127.0.0.1", "::1")
    if parts.scheme == "http" and (production or not loopback):
        errors.append("UGENCE_STUDIO_REVIEW_SERVICE_URL must use https (plain http is "
                      "allowed only on loopback in test mode)")
    if parts.username or parts.password:
        errors.append("UGENCE_STUDIO_REVIEW_SERVICE_URL must not carry a credential")
    if parts.query or parts.fragment:
        errors.append("UGENCE_STUDIO_REVIEW_SERVICE_URL must not carry a query or fragment")
    return errors
