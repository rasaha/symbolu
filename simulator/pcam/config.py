"""
PCAM KV-cache policy configuration — Phase 1 public surface.

A small, explicit config object that mirrors the constructor parameters
of ``simulator.pcam.kv_policy.KVCachePolicy``. This is the entry point
that lets a consumer build a runtime PCAM policy from a dict, an
environment block, or (optionally) a YAML file, without having to know
the internal module layout.

Scope is intentionally narrow:

- One frozen dataclass that mirrors the KVCachePolicy constructor.
- ``from_dict`` and ``from_env`` factories.
- ``from_yaml`` is available iff PyYAML is importable; otherwise it
  raises ``RuntimeError`` with a clear message. No hard PyYAML
  dependency.
- ``build_policy()`` constructs a ``KVCachePolicy`` instance.

What this is NOT (Phase 1 non-goals):

- Not a full product configuration system.
- Not a CLI parser.
- Not a tier policy for the CXL pool (that lives elsewhere).
- Not a runtime backend selector.
- Not a metrics or observability config.

If you need any of those, they belong to a later phase.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, fields
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from .kv_policy import KVCachePolicy


__all__ = ["PCAMConfig"]


@dataclass(frozen=True)
class PCAMConfig:
    """
    Public configuration for ``KVCachePolicy``.

    Mirrors the runtime policy's constructor parameters one-to-one.
    Defaults match the canonical reference at
    ``simulator/pcam/reference/attention_evictor_vendored.py`` and
    must not drift from the runtime policy without an ADR amendment.
    """

    max_blocks: int
    block_size: int = 16
    sink_tokens: int = 4
    recent_window: int = 256
    entity_attention_threshold: float = 0.02
    attention_ema_alpha: float = 0.1

    # ---- Factories ---------------------------------------------------------

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PCAMConfig":
        """
        Build a config from a plain dict. Unknown keys raise ``TypeError``
        rather than being silently dropped — this is intentional, so a
        typo in a config file fails loudly instead of producing a
        misconfigured policy.
        """
        known = {f.name for f in fields(cls)}
        unknown = set(data.keys()) - known
        if unknown:
            raise TypeError(
                f"PCAMConfig.from_dict: unknown keys {sorted(unknown)}; "
                f"valid keys are {sorted(known)}"
            )
        if "max_blocks" not in data:
            raise TypeError("PCAMConfig.from_dict: 'max_blocks' is required")
        return cls(**data)

    @classmethod
    def from_env(cls, prefix: str = "PCAM_") -> "PCAMConfig":
        """
        Build a config from environment variables.

        Each field is read as ``{prefix}{FIELD_NAME_UPPER}`` with type
        coercion via the field's annotation (``int`` or ``float``). Only
        ``max_blocks`` is required; the rest fall back to defaults.

        Example:
            PCAM_MAX_BLOCKS=4096 PCAM_SINK_TOKENS=8 python ...
        """
        kwargs: Dict[str, Any] = {}
        for f in fields(cls):
            env_key = f"{prefix}{f.name.upper()}"
            if env_key in os.environ:
                raw = os.environ[env_key]
                if f.type in ("int", int):
                    kwargs[f.name] = int(raw)
                elif f.type in ("float", float):
                    kwargs[f.name] = float(raw)
                else:
                    kwargs[f.name] = raw
        if "max_blocks" not in kwargs:
            raise TypeError(
                f"PCAMConfig.from_env: required env var {prefix}MAX_BLOCKS is unset"
            )
        return cls(**kwargs)

    @classmethod
    def from_yaml(cls, path: str) -> "PCAMConfig":
        """
        Build a config from a YAML file. Soft dependency on PyYAML — if
        PyYAML is not importable, this raises ``RuntimeError`` with a
        clear install hint rather than silently failing.
        """
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "PCAMConfig.from_yaml requires PyYAML. "
                "Install with `pip install pyyaml`, or use from_dict / from_env."
            ) from exc
        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            raise TypeError(
                f"PCAMConfig.from_yaml: top-level YAML value must be a mapping, "
                f"got {type(data).__name__}"
            )
        return cls.from_dict(data)

    # ---- Conversion --------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Return the config as a plain dict (round-trips with from_dict)."""
        return asdict(self)

    # ---- Convenience -------------------------------------------------------

    def build_policy(self) -> "KVCachePolicy":
        """
        Construct a fresh ``KVCachePolicy`` from this config. Imported
        lazily to avoid a top-level circular import between config.py
        and kv_policy.py.
        """
        from .kv_policy import KVCachePolicy

        return KVCachePolicy(
            max_blocks=self.max_blocks,
            block_size=self.block_size,
            sink_tokens=self.sink_tokens,
            recent_window=self.recent_window,
            entity_attention_threshold=self.entity_attention_threshold,
            attention_ema_alpha=self.attention_ema_alpha,
        )
