"""DDS QoS profile for the ``bcvf_ros2`` integration contract.

Every Tier 1 / OEM customer's second-call question is *"what's
your DDS QoS profile?"*. This module ships the answer:

  RELIABLE / VOLATILE / 10 ms deadline / 100 ms liveliness /
  KEEP_LAST / depth 1.

See ``ROS2_DDS_SBOM_DESIGN.md`` §4 for the per-knob rationale.

The profile is exposed as the typed frozen dataclass
:class:`DDSQoSProfile` plus the singleton constant
:data:`DDS_QOS_PROFILE`. Both are pure data — no rclpy import.
A real ``rclpy.qos.QoSProfile`` is built from the dataclass at
the rclpy boundary by :func:`build_rclpy_qos_profile` (lazy
import, raises if rclpy is not installed).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# Allowed enumerator values. Centralised so a typo in user code
# fails loud at construction time rather than as a silent QoS
# mismatch at runtime.
_RELIABILITY_VALUES = frozenset({"RELIABLE", "BEST_EFFORT"})
_DURABILITY_VALUES = frozenset({
    "VOLATILE",
    "TRANSIENT_LOCAL",
    "TRANSIENT",
    "PERSISTENT",
})
_HISTORY_VALUES = frozenset({"KEEP_LAST", "KEEP_ALL"})


@dataclass(frozen=True)
class DDSQoSProfile:
    """Six-knob DDS QoS profile for ``BCVFNode`` topics.

    Defaults are the documented production profile per
    ``ROS2_DDS_SBOM_DESIGN.md`` §4. Every field is validated at
    construction time so an integrator copying values into their
    config catches typos immediately.

    Fields:
      reliability           "RELIABLE" | "BEST_EFFORT"
      durability            "VOLATILE" | "TRANSIENT_LOCAL" | ...
      deadline_ms           int — per-message deadline in ms
      liveliness_lease_ms   int — liveliness lease in ms
      history               "KEEP_LAST" | "KEEP_ALL"
      depth                 int — queue depth for KEEP_LAST
    """

    reliability: str = "RELIABLE"
    durability: str = "VOLATILE"
    deadline_ms: int = 10
    liveliness_lease_ms: int = 100
    history: str = "KEEP_LAST"
    depth: int = 1

    def __post_init__(self) -> None:
        if self.reliability not in _RELIABILITY_VALUES:
            raise ValueError(
                f"reliability must be one of {sorted(_RELIABILITY_VALUES)}; "
                f"got {self.reliability!r}"
            )
        if self.durability not in _DURABILITY_VALUES:
            raise ValueError(
                f"durability must be one of {sorted(_DURABILITY_VALUES)}; "
                f"got {self.durability!r}"
            )
        if self.history not in _HISTORY_VALUES:
            raise ValueError(
                f"history must be one of {sorted(_HISTORY_VALUES)}; "
                f"got {self.history!r}"
            )
        if self.deadline_ms <= 0:
            raise ValueError(
                f"deadline_ms must be positive; got {self.deadline_ms}"
            )
        if self.liveliness_lease_ms <= 0:
            raise ValueError(
                f"liveliness_lease_ms must be positive; "
                f"got {self.liveliness_lease_ms}"
            )
        if self.liveliness_lease_ms < self.deadline_ms:
            raise ValueError(
                "liveliness_lease_ms must be >= deadline_ms — a "
                "liveliness window tighter than the deadline trips "
                "false-positives on every legitimately-deadlined "
                "message; see ROS2_DDS_SBOM_DESIGN.md §4"
            )
        if self.depth <= 0:
            raise ValueError(f"depth must be positive; got {self.depth}")

    def to_dict(self) -> dict:
        """Plain-dict view for JSON serialisation / YAML round-trip."""
        return {
            "reliability": self.reliability,
            "durability": self.durability,
            "deadline_ms": int(self.deadline_ms),
            "liveliness_lease_ms": int(self.liveliness_lease_ms),
            "history": self.history,
            "depth": int(self.depth),
        }


#: The default production QoS profile. An integrator copies this
#: into their rclpy node config (or builds an
#: ``rclpy.qos.QoSProfile`` via :func:`build_rclpy_qos_profile`).
DDS_QOS_PROFILE: DDSQoSProfile = DDSQoSProfile()


def build_rclpy_qos_profile(profile: DDSQoSProfile = DDS_QOS_PROFILE) -> Any:
    """Build a real ``rclpy.qos.QoSProfile`` from a
    :class:`DDSQoSProfile`. Lazy-imports ``rclpy``; raises
    :class:`ImportError` with installation guidance if rclpy is
    not present.

    Returns: a ``rclpy.qos.QoSProfile`` instance the integrator
    passes to ``Node.create_publisher(...)`` /
    ``Node.create_subscription(...)``.
    """
    try:
        from rclpy.duration import Duration
        from rclpy.qos import (
            DurabilityPolicy,
            HistoryPolicy,
            QoSProfile,
            ReliabilityPolicy,
        )
    except ImportError as exc:  # pragma: no cover — sandbox path
        raise ImportError(
            "rclpy is not installed in this environment. "
            "build_rclpy_qos_profile requires a ROS 2 Humble or newer "
            "installation. The DDSQoSProfile dataclass itself is "
            "usable without rclpy — read its fields directly to feed "
            "another DDS implementation (RTI Connext, eProsima FastDDS)."
        ) from exc

    reliability = (
        ReliabilityPolicy.RELIABLE
        if profile.reliability == "RELIABLE"
        else ReliabilityPolicy.BEST_EFFORT
    )
    durability_map = {
        "VOLATILE": DurabilityPolicy.VOLATILE,
        "TRANSIENT_LOCAL": DurabilityPolicy.TRANSIENT_LOCAL,
    }
    durability = durability_map.get(profile.durability, DurabilityPolicy.VOLATILE)
    history = (
        HistoryPolicy.KEEP_LAST
        if profile.history == "KEEP_LAST"
        else HistoryPolicy.KEEP_ALL
    )
    return QoSProfile(
        reliability=reliability,
        durability=durability,
        history=history,
        depth=profile.depth,
        deadline=Duration(seconds=profile.deadline_ms / 1000.0),
        liveliness_lease_duration=Duration(
            seconds=profile.liveliness_lease_ms / 1000.0
        ),
    )
