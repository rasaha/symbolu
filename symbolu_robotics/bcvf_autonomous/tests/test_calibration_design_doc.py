"""Tests for the calibration-management design proposal (`CALIBRATION_DESIGN.md`).

The roadmap §9 row #6 (calibration parameter management +
drift detection) lands as a design-doc + thin-shim
implementation pair, mirroring the maturation pattern of the
prior four landings (state machine, ROS 2 / DDS / SBOM,
replay, real-time budget). These tests pin:

1. The doc ships in the package at the documented path.
2. Required §1–§9 section headers are present.
3. §2 enumerates every required CalibrationSet bundle field.
4. §3 names both the digest (identity) + kernel_version
   (version-binding) discipline pieces.
5. §5 strict-validation discipline mentions every documented
   error class.
6. §8 ship-when-ready criteria — five gates.

Implementation-grade behaviour tests live in dedicated test
modules; this file pins the doc only.
"""

from __future__ import annotations

from pathlib import Path

import symbolu_robotics.bcvf_autonomous as bcvf


DOC_PATH = Path(bcvf.__file__).parent / "CALIBRATION_DESIGN.md"


def test_design_doc_ships_with_the_package():
    assert DOC_PATH.exists(), (
        f"missing design doc at {DOC_PATH} — the calibration "
        "framework must ship as a doc paired with the implementation"
    )


def test_design_doc_has_required_section_headers():
    text = DOC_PATH.read_text(encoding="utf-8")
    for header in (
        "Calibration parameter management + drift detection",
        "§1 Why this exists",
        "§2 The CalibrationSet bundle contract",
        "§3 Versioning + identity",
        "§4 Drift detection",
        "§5 Strict round-trip discipline",
        "§6 Composition with existing surfaces",
        "§7 What this is NOT",
        "§8 Ship-when-ready criteria",
        "§9 API sketch",
    ):
        assert header in text, f"design doc missing section: {header!r}"


def test_design_doc_names_all_required_bundle_fields():
    """§2 must enumerate every CalibrationSet field a reader
    needs to know about — bundle integrity + per-config
    coverage + the expected_metrics for drift detection."""
    text = DOC_PATH.read_text(encoding="utf-8")
    for field in (
        "calibration_id",
        "kernel_version",
        "created_at",
        "bcvf_config",
        "consumer_v2_config",
        "bicycle_config",
        "realtime_budget",
        "dds_qos_profile",
        "safety_state_config",
        "per_predictor_failure_thresholds",
        "expected_metrics",
        "metadata",
        "digest",
    ):
        assert field in text, f"§2 must name bundle field: {field!r}"


def test_design_doc_names_identity_and_versioning_discipline():
    """§3 must explicitly name both the SHA-256 digest (identity)
    and the kernel_version validation (version-binding) — they
    are orthogonal disciplines but both load-bearing."""
    text = DOC_PATH.read_text(encoding="utf-8")
    assert "SHA-256" in text
    assert "kernel_version" in text
    assert "CalibrationVersionError" in text


def test_design_doc_names_drift_detector_alert_fields():
    """§4 must enumerate every CalibrationDriftAlert field so a
    reader skimming the doc can audit the alert surface."""
    text = DOC_PATH.read_text(encoding="utf-8")
    for field in (
        "observed_value",
        "expected_min",
        "expected_max",
        "direction",
        "calibration_id",
    ):
        assert field in text, f"§4 must name alert field: {field!r}"


def test_design_doc_strict_validation_names_error_classes():
    """§5 must name CalibrationSetError, CalibrationVersionError,
    and CalibrationDigestError — the three documented error
    paths a corrupt / tampered / drifted bundle takes."""
    text = DOC_PATH.read_text(encoding="utf-8")
    assert "CalibrationSetError" in text
    assert "CalibrationVersionError" in text
    assert "CalibrationDigestError" in text


def test_design_doc_lists_five_ship_when_ready_criteria():
    text = DOC_PATH.read_text(encoding="utf-8")
    for marker in ("1. **", "2. **", "3. **", "4. **", "5. **"):
        assert marker in text, f"§8 must enumerate criterion {marker!r}"


def test_design_doc_states_what_this_is_not():
    text = DOC_PATH.read_text(encoding="utf-8").lower()
    assert "not a runtime config loader" in text
    assert "not a signing implementation" in text
    assert "not a fleet-management dashboard" in text
    assert "not a substitute" in text


def test_design_doc_names_composition_with_existing_surfaces():
    """§6 composition must name the existing surfaces — the
    nine bundled configs, StreamingFleetMonitor, the safety
    state machine, ReplayBundle, the SBOM, SOTIF clause 12."""
    text = DOC_PATH.read_text(encoding="utf-8")
    for surface in (
        "BCVFConfig",
        "ConsumerV2Config",
        "RealTimeBudget",
        "DDSQoSProfile",
        "SafetyStateMachineConfig",
        "StreamingFleetMonitor",
        "AlertRule",
        "ReplayBundle",
        "SBOM",
        "clause 12",
    ):
        assert surface in text, f"§6 must name composition surface: {surface!r}"


def test_design_doc_names_fleet_size_motivation():
    """§1 must surface the roadmap's "fleet > 10 vehicles"
    motivation so a reader skimming the headline understands
    why this matters."""
    text = DOC_PATH.read_text(encoding="utf-8")
    assert "10 vehicles" in text or "10+ vehicles" in text
