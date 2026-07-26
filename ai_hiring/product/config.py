"""Typed, fail-closed product configuration (H6 §8).

The configuration surface is intentionally small and **fail-closed**:

- Unknown keys are rejected (no silent typos).
- Invalid values are rejected with a typed error (no coercion into a default).
- The execution mode defaults to — and in this package is *restricted to* —
  deterministic simulation. Any attempt to select a production/live external
  effect fails closed with :class:`UnsupportedExecutionModeError`, because **no
  production external-effect adapter ships in this package** (only replaceable
  ports + deterministic adapters exist). This mirrors, at the configuration
  boundary, the same fail-safe posture the runtime enforces.

This module adds no governance, decision, or authorization semantics; it only
validates how the already-shipped, frozen-API-consuming services are assembled.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ProductConfigError(ValueError):
    """Base class for fail-closed configuration errors."""


class UnknownConfigKeyError(ProductConfigError):
    """A configuration mapping contained a key the product does not recognize."""


class InvalidConfigValueError(ProductConfigError):
    """A configuration value was of the wrong type or outside its allowed range."""


class UnsupportedExecutionModeError(ProductConfigError):
    """A production/live execution mode was requested but no such adapter ships here."""


class ExecutionMode(str, Enum):
    """How governed actions are externally executed.

    Only :attr:`DETERMINISTIC_SIMULATION` is supported by this package. The other
    members exist **solely** so the fail-closed boundary can name and reject them
    explicitly rather than failing with an opaque error — selecting either raises
    :class:`UnsupportedExecutionModeError`.
    """

    DETERMINISTIC_SIMULATION = "DETERMINISTIC_SIMULATION"
    PRODUCTION_LIVE = "PRODUCTION_LIVE"  # not shipped — reserved, always rejected
    PRODUCTION_DRY_RUN = "PRODUCTION_DRY_RUN"  # not shipped — reserved, always rejected


_SUPPORTED_MODES = frozenset({ExecutionMode.DETERMINISTIC_SIMULATION})

# The full set of keys ``load_config`` accepts. Anything else fails closed.
_ALLOWED_KEYS = frozenset(
    {"tenant", "execution_mode", "max_retries", "redact_pii", "extra_reviewers"}
)


@dataclass(frozen=True)
class ProductConfig:
    """Validated product configuration.

    All invariants are enforced in :meth:`__post_init__`, so an instance that
    exists is always valid and safe to compose from.
    """

    tenant: str = "demo-tenant"
    execution_mode: ExecutionMode = ExecutionMode.DETERMINISTIC_SIMULATION
    max_retries: int = 2
    redact_pii: bool = True
    extra_reviewers: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.tenant, str) or not self.tenant.strip():
            raise InvalidConfigValueError("tenant must be a non-empty string")

        # Coerce a string mode into the enum, failing closed on an unknown name.
        mode = self.execution_mode
        if isinstance(mode, str) and not isinstance(mode, ExecutionMode):
            try:
                mode = ExecutionMode(mode)
            except ValueError as exc:
                raise InvalidConfigValueError(
                    f"execution_mode {mode!r} is not a known mode"
                ) from exc
            object.__setattr__(self, "execution_mode", mode)
        if not isinstance(mode, ExecutionMode):
            raise InvalidConfigValueError("execution_mode must be an ExecutionMode")
        if mode not in _SUPPORTED_MODES:
            raise UnsupportedExecutionModeError(
                f"execution_mode {mode.value!r} is not shipped in this package; "
                "only DETERMINISTIC_SIMULATION is supported. No production "
                "external-effect adapter is available."
            )

        if not isinstance(self.max_retries, int) or isinstance(self.max_retries, bool):
            raise InvalidConfigValueError("max_retries must be an int")
        if not (0 <= self.max_retries <= 10):
            raise InvalidConfigValueError("max_retries must be in [0, 10]")

        if not isinstance(self.redact_pii, bool):
            raise InvalidConfigValueError("redact_pii must be a bool")

        reviewers = tuple(self.extra_reviewers)
        if not all(isinstance(r, str) and r.strip() for r in reviewers):
            raise InvalidConfigValueError("extra_reviewers must be non-empty strings")
        object.__setattr__(self, "extra_reviewers", reviewers)

    def to_dict(self) -> dict:
        return {
            "tenant": self.tenant,
            "execution_mode": self.execution_mode.value,
            "max_retries": self.max_retries,
            "redact_pii": self.redact_pii,
            "extra_reviewers": list(self.extra_reviewers),
        }


def load_config(mapping: dict | None = None) -> ProductConfig:
    """Build a :class:`ProductConfig` from an untrusted mapping, fail-closed.

    Unknown keys are rejected outright (rather than ignored), so a typo can never
    silently disable a safeguard. Missing keys fall back to the typed defaults.
    """
    mapping = dict(mapping or {})
    unknown = set(mapping) - _ALLOWED_KEYS
    if unknown:
        raise UnknownConfigKeyError(
            f"unknown configuration key(s): {sorted(unknown)}; "
            f"allowed keys are {sorted(_ALLOWED_KEYS)}"
        )
    kwargs = dict(mapping)
    if "extra_reviewers" in kwargs:
        kwargs["extra_reviewers"] = tuple(kwargs["extra_reviewers"])
    return ProductConfig(**kwargs)
