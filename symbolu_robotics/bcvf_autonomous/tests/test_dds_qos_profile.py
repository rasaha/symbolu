"""Tests for the DDS QoS profile module (``bcvf_ros2.qos``).

Pinned contracts:

* The default :data:`DDS_QOS_PROFILE` is the documented
  ``RELIABLE / VOLATILE / 10 ms / 100 ms / KEEP_LAST / 1`` quad
  per ``ROS2_DDS_SBOM_DESIGN.md`` §4.
* :class:`DDSQoSProfile` validates every knob at construction
  time — typo'd values fail loud.
* The liveliness lease is required to be ≥ deadline (a tighter
  liveliness window trips false-positives on every legitimately-
  deadlined message).
* The lazy-rclpy adapter raises a clear ImportError when rclpy
  is not present.
"""

from __future__ import annotations

import pytest

from symbolu_robotics.bcvf_ros2 import (
    DDS_QOS_PROFILE,
    DDSQoSProfile,
    build_rclpy_qos_profile,
)


# --------------------------------------------------------------------------- #
# Default profile
# --------------------------------------------------------------------------- #


def test_default_dds_qos_profile_is_documented_quad():
    """The §4 documented profile: RELIABLE / VOLATILE / 10ms / 100ms /
    KEEP_LAST / 1."""
    assert DDS_QOS_PROFILE.reliability == "RELIABLE"
    assert DDS_QOS_PROFILE.durability == "VOLATILE"
    assert DDS_QOS_PROFILE.deadline_ms == 10
    assert DDS_QOS_PROFILE.liveliness_lease_ms == 100
    assert DDS_QOS_PROFILE.history == "KEEP_LAST"
    assert DDS_QOS_PROFILE.depth == 1


def test_dds_qos_profile_is_frozen_dataclass():
    """The profile is a frozen dataclass — an integrator can hash
    it / use it as a dict key without worrying about mutation."""
    with pytest.raises((AttributeError, Exception)):
        DDS_QOS_PROFILE.deadline_ms = 999  # type: ignore[misc]


def test_dds_qos_profile_to_dict_round_trip_keys():
    d = DDS_QOS_PROFILE.to_dict()
    assert set(d.keys()) == {
        "reliability", "durability", "deadline_ms",
        "liveliness_lease_ms", "history", "depth",
    }
    assert d["deadline_ms"] == 10
    assert d["liveliness_lease_ms"] == 100


# --------------------------------------------------------------------------- #
# Validation — typo'd values fail loud
# --------------------------------------------------------------------------- #


def test_qos_rejects_unknown_reliability():
    with pytest.raises(ValueError, match="reliability"):
        DDSQoSProfile(reliability="MOSTLY_RELIABLE")


def test_qos_rejects_unknown_durability():
    with pytest.raises(ValueError, match="durability"):
        DDSQoSProfile(durability="EVENTUAL")


def test_qos_rejects_unknown_history():
    with pytest.raises(ValueError, match="history"):
        DDSQoSProfile(history="KEEP_FIRST")


def test_qos_rejects_non_positive_deadline_ms():
    with pytest.raises(ValueError, match="deadline_ms"):
        DDSQoSProfile(deadline_ms=0)
    with pytest.raises(ValueError, match="deadline_ms"):
        DDSQoSProfile(deadline_ms=-5)


def test_qos_rejects_non_positive_liveliness_lease_ms():
    with pytest.raises(ValueError, match="liveliness_lease_ms"):
        DDSQoSProfile(liveliness_lease_ms=0, deadline_ms=1)


def test_qos_rejects_liveliness_lease_below_deadline():
    """A liveliness lease tighter than the deadline is a
    misconfiguration that trips false-positives on every
    deadlined message — see ROS2_DDS_SBOM_DESIGN.md §4."""
    with pytest.raises(ValueError, match="deadline_ms"):
        DDSQoSProfile(deadline_ms=10, liveliness_lease_ms=5)


def test_qos_rejects_non_positive_depth():
    with pytest.raises(ValueError, match="depth"):
        DDSQoSProfile(depth=0)


def test_qos_accepts_alternate_valid_combinations():
    """Custom-but-valid profiles must succeed (don't over-restrict)."""
    p = DDSQoSProfile(
        reliability="BEST_EFFORT",
        durability="TRANSIENT_LOCAL",
        deadline_ms=50,
        liveliness_lease_ms=500,
        history="KEEP_ALL",
        depth=10,
    )
    assert p.reliability == "BEST_EFFORT"
    assert p.durability == "TRANSIENT_LOCAL"
    assert p.history == "KEEP_ALL"


# --------------------------------------------------------------------------- #
# Lazy rclpy adapter
# --------------------------------------------------------------------------- #


def test_build_rclpy_qos_profile_raises_clear_error_without_rclpy():
    """In the sandbox + most CI environments, rclpy isn't
    installed. The adapter must surface a clear ImportError with
    installation guidance — not a vague AttributeError or
    ModuleNotFoundError."""
    try:
        import rclpy  # noqa: F401
    except ImportError:
        rclpy_present = False
    else:
        rclpy_present = True

    if rclpy_present:
        pytest.skip("rclpy is available; the lazy-import error path is not exercised here")
    with pytest.raises(ImportError, match="rclpy"):
        build_rclpy_qos_profile()
