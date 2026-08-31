"""Configuration loading, environment separation, and the astrology provider policy.

Provider/environment policy (Area A hardening):

| Environment       | Permitted providers                    |
|-------------------|----------------------------------------|
| test              | fake                                   |
| development       | fake or Swiss development adapter      |
| qa (internal QA)  | approved Swiss development adapter      |
| staging           | approved real provider only            |
| production        | approved licensed real provider only   |

``fake`` is a synthetic, non-astronomical stub: it is permitted only in ``test`` and
``development`` (and in ``qa`` only if explicitly opted in). It is never permitted in
``staging`` or ``production``. A missing/invalid production provider causes a safe
startup failure — it never falls back to ``fake``.
"""

from __future__ import annotations

import enum
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, enum.Enum):
    TEST = "test"
    DEVELOPMENT = "development"
    QA = "qa"
    STAGING = "staging"
    PRODUCTION = "production"

    @property
    def is_production_like(self) -> bool:
        return self in (Environment.STAGING, Environment.PRODUCTION)

    @property
    def allows_dev_ephemeris(self) -> bool:
        """The Swiss development (AGPL) adapter may run only in dev/test/qa."""
        return self in (Environment.DEVELOPMENT, Environment.TEST, Environment.QA)


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

    # --- Secure chat (Phase 3A) policy constants --------------------------- #
    # Single source of truth for the message body bound and page limits so no
    # layer duplicates the value. Body length is measured in Unicode code points.
    chat_message_max_code_points: int = 4000
    chat_page_default: int = 50
    chat_page_max: int = 100

    # --- Chat safety (Phase 3B) policy constants --------------------------- #
    # Operational defaults (not legal/behavioural judgements). Env-overridable via
    # DILCHAT_* like every other setting; centralised so no layer hardcodes them.
    safety_report_description_max_code_points: int = 1000
    safety_evidence_window_default: int = 50
    safety_evidence_window_max: int = 50
    # A former participant may report only their own ended conversation for this
    # many days after unpair/block/account deletion. Requires future legal review.
    chat_report_after_revocation_days: int = 30
    # PostgreSQL-backed fixed-window rate limits (concurrency-safe; no Redis).
    ratelimit_send_per_minute: int = 30
    ratelimit_send_per_hour: int = 300
    ratelimit_report_per_day: int = 10
    ratelimit_block_mutations_per_hour: int = 60
    # Retention / purge seam. Destructive scheduled purging is NOT run in Phase 3B.
    retention_purge_enabled: bool = False

    # --- Outbox relay / push delivery (Phase 3C, DILCHAT-D3C-1..4) ---------- #
    # Transport: "null" (accepts everything, sends nothing; dev/test default)
    # or "expo" (Expo push service; pilot transport per D3C-1 — production
    # APNs/FCM credentials remain a separate launch gate). Unknown values are
    # refused at construction (fail closed).
    push_transport: str = "null"
    expo_push_url: str = "https://exp.host/--/api/v2/push/send"
    relay_batch_size: int = 50
    relay_poll_interval_seconds: float = 2.0
    # At-least-once bookkeeping: bounded exponential backoff, then parked.
    relay_max_attempts: int = 8
    relay_backoff_base_seconds: int = 30
    relay_backoff_cap_seconds: int = 3600
    # D3C-3: PUBLISHED outbox rows only, this many days after published_at.
    # Message retention is untouched; unpublished work is never pruned (I8).
    outbox_prune_after_days: int = 30
    relay_prune_interval_seconds: int = 3600

    # Birth-time confidence defaults (propagate to calculation provenance).
    confidence_exact: float = 1.0
    confidence_approximate: float = 0.5
    confidence_unknown: float = 0.2

    # --- Astrology provider selection & policy ----------------------------- #
    # Provider id: "fake" (synthetic; test/dev only) or "swiss" (real ephemeris via
    # pyswisseph). NOTE: the default is fake for local development, but the policy
    # below refuses fake in qa/staging/production, so a production deployment MUST
    # set an approved real provider or startup fails (no silent fake fallback).
    astrology_provider: str = "fake"
    swiss_ephemeris_mode: str = "moshier"  # "swieph" | "moshier"; no silent fallback
    swiss_ephemeris_path: str | None = None
    enable_swiss_ephemeris: bool = False
    # Explicit, recorded approval that a compatible Swiss production licensing
    # decision exists (Professional License or an accepted AGPL-compliance decision).
    # Required before the Swiss adapter may run in staging/production.
    swiss_production_licensed: bool = False
    # Explicit opt-in to permit the synthetic fake provider in internal QA.
    allow_fake_in_qa: bool = False

    # ---------------------------------------------------------------------- #
    def permitted_providers(self) -> set[str]:
        """The provider ids permitted for the current environment (policy matrix)."""
        env = self.environment
        if env is Environment.TEST:
            return {"fake"}
        if env is Environment.DEVELOPMENT:
            return {"fake", "swiss"}
        if env is Environment.QA:
            return {"swiss"} | ({"fake"} if self.allow_fake_in_qa else set())
        # staging / production: real providers only.
        return {"swiss"} if self.swiss_production_licensed else set()

    @model_validator(mode="after")
    def _guard(self) -> Settings:
        if self.push_transport not in {"null", "expo"}:
            raise ValueError(
                f"push_transport={self.push_transport!r} is not permitted; allowed: "
                "null, expo (fail closed — no silent no-op transport)."
            )
        permitted = self.permitted_providers()
        if self.astrology_provider not in permitted:
            allowed = sorted(permitted) or "none"
            raise ValueError(
                f"astrology_provider={self.astrology_provider!r} is not permitted in "
                f"environment {self.environment.value!r}. Permitted: {allowed}. "
                "See DEC-029 (provider/environment policy)."
            )
        if self.environment.is_production_like:
            if self.astrology_provider == "swiss" and not self.swiss_production_licensed:
                raise ValueError(
                    "Swiss Ephemeris requires swiss_production_licensed=true in "
                    "staging/production (DEC-007 licensing decision)."
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
