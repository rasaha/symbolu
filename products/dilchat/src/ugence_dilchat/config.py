"""Configuration loading and environment separation.

Settings are loaded from environment variables (prefix ``DILCHAT_``) with safe
development defaults. Production-like environments MUST provide real secrets;
several guards in this module refuse to run with development defaults when
``environment == "production"``.
"""

from __future__ import annotations

import enum
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, enum.Enum):
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"

    @property
    def is_production_like(self) -> bool:
        return self in (Environment.STAGING, Environment.PRODUCTION)

    @property
    def allows_dev_ephemeris(self) -> bool:
        """Swiss/Moshier dev ephemeris may run only in development or test."""
        return self in (Environment.DEVELOPMENT, Environment.TEST)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DILCHAT_",
        env_file=".env",
        extra="ignore",
    )

    environment: Environment = Environment.DEVELOPMENT
    api_v1_prefix: str = "/v1"
    debug: bool = False

    # Database. asyncpg for PostgreSQL (primary); aiosqlite accepted for unit tests.
    database_url: str = "postgresql+asyncpg://postgres@/dilchat_dev?host=/tmp&port=5433"

    # Access-token signing (ES256). In dev/test an ephemeral key is generated if unset.
    access_token_private_key_pem: str | None = None
    access_token_public_key_pem: str | None = None
    access_token_ttl_seconds: int = 600  # 10 minutes
    refresh_token_ttl_seconds: int = 60 * 60 * 24 * 30  # 30 days
    token_issuer: str = "dilchat"

    # Birth-time confidence defaults (propagate to calculation provenance).
    confidence_exact: float = 1.0
    confidence_approximate: float = 0.5
    confidence_unknown: float = 0.2

    # --- Astrology provider selection -------------------------------------- #
    # Provider id: "fake" (deterministic, default & only production-safe stub) or
    # "swiss" (dev/test only, AGPL Swiss Ephemeris via pyswisseph).
    astrology_provider: str = "fake"
    # Explicit ephemeris mode for the Swiss provider: "swieph" (needs .se1 files;
    # fails explicitly if absent) or "moshier" (analytical, honest, dev/test only).
    # There is NO silent fallback between modes.
    swiss_ephemeris_mode: str = "moshier"
    swiss_ephemeris_path: str | None = None  # directory of .se1 files for swieph mode
    # Master switch. Must be explicitly enabled AND environment must allow it.
    enable_swiss_ephemeris: bool = False

    @model_validator(mode="after")
    def _guard_production(self) -> Settings:
        if self.environment.is_production_like:
            # DEC-007 / licensing: the AGPL Swiss provider is never permitted in a
            # production-like environment during this phase.
            if self.astrology_provider == "swiss" or self.enable_swiss_ephemeris:
                raise ValueError(
                    "Swiss Ephemeris (AGPL dev edition) is disabled in production-like "
                    "environments in this phase. See docs/DILCHAT_DECISION_LOG.md DEC-007."
                )
            if self.access_token_private_key_pem is None:
                raise ValueError(
                    "access_token_private_key_pem is required in production-like environments."
                )
        return self

    def confidence_for_precision(self, precision: str) -> float:
        return {
            "EXACT": self.confidence_exact,
            "APPROXIMATE": self.confidence_approximate,
            "UNKNOWN": self.confidence_unknown,
        }[precision]


@lru_cache
def get_settings() -> Settings:
    return Settings()
