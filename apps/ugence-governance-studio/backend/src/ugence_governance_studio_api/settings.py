"""Typed application settings (§23).

Configuration comes from explicit constructor arguments, then environment
variables (``UGS_API_*``), then safe defaults. Domain behaviour never depends on
mutable environment configuration — policy and workflow behaviour come only from
pinned request / scenario artifacts. These settings control the presentation and
security seams (CORS, request limits, docs, seams for rate-limit / auth), the
read-only fixture roots and operational build metadata.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional

_TRUE = {"1", "true", "yes", "on"}


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUE


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_list(name: str, default: List[str]) -> List[str]:
    raw = os.environ.get(name)
    if raw is None:
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]


# Default request-body ceiling: 2 MiB is comfortably above the largest committed
# scenario fixture and far below anything that would stress the process.
DEFAULT_MAX_REQUEST_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class ApiSettings:
    """Immutable settings snapshot for one application instance."""

    environment: str = "local"
    log_level: str = "INFO"
    cors_allowed_origins: List[str] = field(default_factory=list)
    max_request_bytes: int = DEFAULT_MAX_REQUEST_BYTES
    max_json_depth: int = 64
    max_collection_items: int = 10_000
    enable_docs: bool = True
    enable_rate_limit: bool = False
    enable_authentication: bool = False
    scenario_root: Optional[str] = None
    expected_output_root: Optional[str] = None
    build_commit: Optional[str] = None
    build_id: Optional[str] = None

    @classmethod
    def from_env(cls, **overrides) -> "ApiSettings":
        """Build settings from environment variables, then apply explicit
        keyword overrides (which always win). Unknown environments default to the
        safe ``local`` profile."""
        base = dict(
            environment=os.environ.get("UGS_API_ENVIRONMENT", "local"),
            log_level=os.environ.get("UGS_API_LOG_LEVEL", "INFO"),
            cors_allowed_origins=_env_list("UGS_API_CORS_ALLOWED_ORIGINS", []),
            max_request_bytes=_env_int("UGS_API_MAX_REQUEST_BYTES", DEFAULT_MAX_REQUEST_BYTES),
            max_json_depth=_env_int("UGS_API_MAX_JSON_DEPTH", 64),
            max_collection_items=_env_int("UGS_API_MAX_COLLECTION_ITEMS", 10_000),
            enable_docs=_env_bool("UGS_API_ENABLE_DOCS", True),
            enable_rate_limit=_env_bool("UGS_API_ENABLE_RATE_LIMIT", False),
            enable_authentication=_env_bool("UGS_API_ENABLE_AUTHENTICATION", False),
            scenario_root=os.environ.get("UGS_API_SCENARIO_ROOT"),
            expected_output_root=os.environ.get("UGS_API_EXPECTED_OUTPUT_ROOT"),
            build_commit=os.environ.get("UGS_API_BUILD_COMMIT"),
            build_id=os.environ.get("UGS_API_BUILD_ID"),
        )
        base.update(overrides)
        return cls(**base)

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}
