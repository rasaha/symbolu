"""Tests for the sensor-attestation design proposal (`SENSOR_ATTESTATION_DESIGN.md`).

The roadmap §9 row #8 (sensor attestation interface) lands as
a design-doc + thin-shim implementation pair, mirroring the
maturation pattern of the prior five landings (state machine,
ROS 2 / DDS / SBOM, replay, real-time budget, calibration).
This is the LAST roadmap gate token to be removed —
``SensorAttestation`` is the only entry left in
``_ROADMAP_TOKENS`` after the calibration framework shipped.

These tests pin:

1. The doc ships in the package at the documented path.
2. Required §1–§9 section headers are present.
3. §2 enumerates every required SensorAttestation field.
4. §3 enumerates every required SensorAttestationPolicy field.
5. §4 enumerates the seven verification checks in order.
6. §6 names every "what this is NOT" scope-creep guard.
7. §7 names the existing surfaces this composes with —
   adversarial family / SOTIF clause 8 / TrustWeightComputer /
   SafetyStateMachine / CalibrationSet / BCVFNodeBehaviour.
8. §8 ship-when-ready criteria — five gates.
"""

from __future__ import annotations

from pathlib import Path

import symbolu_robotics.bcvf_autonomous as bcvf


DOC_PATH = Path(bcvf.__file__).parent / "SENSOR_ATTESTATION_DESIGN.md"


def test_design_doc_ships_with_the_package():
    assert DOC_PATH.exists(), (
        f"missing design doc at {DOC_PATH} — the sensor-attestation "
        "framework must ship as a doc paired with the implementation"
    )


def test_design_doc_has_required_section_headers():
    text = DOC_PATH.read_text(encoding="utf-8")
    for header in (
        "Sensor attestation interface",
        "§1 Why this exists",
        "§2 The attestation contract",
        "§3 The verification policy",
        "§4 The verification gate",
        "§5 Composition with the existing exclusion path",
        "§6 What this is NOT",
        "§7 Composition with existing surfaces",
        "§8 Ship-when-ready criteria",
        "§9 API sketch",
    ):
        assert header in text, f"design doc missing section: {header!r}"


def test_design_doc_names_attestation_record_fields():
    """§2 must enumerate every SensorAttestation field a
    reader needs to know about — the load-bearing typed
    record."""
    text = DOC_PATH.read_text(encoding="utf-8")
    for field in (
        "predictor_name",
        "firmware_version",
        "signature",
        "nonce",
        "issued_at",
        "data_digest",
        "metadata",
    ):
        assert field in text, f"§2 must name attestation field: {field!r}"


def test_design_doc_names_policy_fields():
    """§3 must enumerate every SensorAttestationPolicy field."""
    text = DOC_PATH.read_text(encoding="utf-8")
    for field in (
        "accepted_firmware_versions",
        "freshness_window_seconds",
        "replay_window_seconds",
        "key_id",
        "enabled",
    ):
        assert field in text, f"§3 must name policy field: {field!r}"


def test_design_doc_names_un_ece_r155_motivation():
    """§1 must surface the UN ECE R155 cybersecurity loop +
    the Lemma-1 trapdoor framing — the deal-unlock motivation
    the roadmap names."""
    text = DOC_PATH.read_text(encoding="utf-8")
    assert "UN ECE R155" in text
    assert "Lemma-1 trapdoor" in text or "Lemma 1 trapdoor" in text


def test_design_doc_names_the_seven_verification_checks():
    """§4 enumerates the verification checks as a numbered list.
    Pinned so a future refactor that drops a check (replay,
    freshness, etc.) breaks loud."""
    text = DOC_PATH.read_text(encoding="utf-8").lower()
    for check in (
        "policy lookup",
        "policy-disabled short-circuit",
        "firmware allowlist",
        "freshness",
        "replay",
        "data binding",
        "hmac signature",
    ):
        assert check in text, f"§4 must name check: {check!r}"


def test_design_doc_states_what_this_is_not():
    text = DOC_PATH.read_text(encoding="utf-8").lower()
    assert "not a pki implementation" in text
    assert "not a key-management system" in text
    assert "not a dds-security replacement" in text
    assert "not a kernel-rule rewrite" in text
    assert "not a substitute" in text
    assert "not a fleet-management interface" in text


def test_design_doc_acknowledges_stdlib_only_constraint():
    """§2 + §6 must explicitly name the stdlib-only constraint
    (HMAC-SHA256, no `cryptography` lib, no PKI). The sandbox
    discipline + the realistic within-vehicle deployment model."""
    text = DOC_PATH.read_text(encoding="utf-8")
    assert "HMAC-SHA256" in text
    assert "stdlib-only" in text or "stdlib only" in text


def test_design_doc_names_composition_with_existing_surfaces():
    """§7 composition must name the five existing surfaces this
    is the in-scope mitigation for."""
    text = DOC_PATH.read_text(encoding="utf-8")
    for surface in (
        "adversarial_consistent_bias",
        "TrustWeightComputer",
        "SafetyStateMachine",
        "CalibrationSet",
        "BCVFNodeBehaviour",
        "SOTIF",
        "Insufficiency #3",
    ):
        assert surface in text, f"§7 must name composition surface: {surface!r}"


def test_design_doc_names_three_exclusion_sources():
    """§5 must name all three exclusion sources (deadline /
    attestation / state machine) so a reader sees how the new
    surface composes with the existing exclusion mask."""
    text = DOC_PATH.read_text(encoding="utf-8").lower()
    for source in (
        "deadline",
        "attestation",
        "state machine",
    ):
        assert source in text, f"§5 must name exclusion source: {source!r}"


def test_design_doc_lists_five_ship_when_ready_criteria():
    text = DOC_PATH.read_text(encoding="utf-8")
    for marker in ("1. **", "2. **", "3. **", "4. **", "5. **"):
        assert marker in text, f"§8 must enumerate criterion {marker!r}"
