"""Tests for the replay-framework design proposal (`REPLAY_FRAMEWORK_DESIGN.md`).

The roadmap §9 row #3 (replay / record-and-replay framework)
lands as a design-doc + thin-shim implementation pair, mirroring
the maturation pattern from ``SAFETY_STATE_MACHINE_DESIGN.md``
and ``ROS2_DDS_SBOM_DESIGN.md``. These tests pin:

1. The doc ships in the package at the documented path.
2. The doc contains the load-bearing section headers a reviewer
   uses to navigate it (§1 through §10).
3. The §2 bundle-contract table names every required field.
4. The §5 divergence taxonomy names all three classes (kernel
   diverged / config drift / host non-determinism).
5. The §9 ship-when-ready criteria are present (five gates).

Implementation-grade behaviour tests live in dedicated test
modules; this file pins the doc only.
"""

from __future__ import annotations

from pathlib import Path

import symbolu_robotics.bcvf_autonomous as bcvf


DOC_PATH = Path(bcvf.__file__).parent / "REPLAY_FRAMEWORK_DESIGN.md"


def test_design_doc_ships_with_the_package():
    assert DOC_PATH.exists(), (
        f"missing design doc at {DOC_PATH} — the replay framework "
        "must ship as a doc paired with the implementation"
    )


def test_design_doc_has_required_section_headers():
    text = DOC_PATH.read_text(encoding="utf-8")
    for header in (
        "Replay / record-and-replay framework",
        "§1 Why this exists",
        "§2 The bundle contract",
        "§3 Capture path",
        "§4 Reconstruction",
        "§5 What divergence means",
        "§6 Strict round-trip discipline",
        "§7 Composition with existing surfaces",
        "§8 What this is NOT",
        "§9 Ship-when-ready criteria",
        "§10 API sketch",
    ):
        assert header in text, f"design doc missing section: {header!r}"


def test_design_doc_names_required_bundle_fields():
    """§2 must enumerate every required ReplayBundle field so a
    reader skimming the doc can audit the bundle contents."""
    text = DOC_PATH.read_text(encoding="utf-8")
    for field in (
        "bundle_version",
        "package_version",
        "recorded_at",
        "episode_id",
        "run_config",
        "recorded_record",
        "metadata",
    ):
        assert field in text, f"§2 must name bundle field: {field!r}"


def test_design_doc_names_three_divergence_classes():
    """§5 names three divergence classes (kernel diverged, config
    drift, host non-determinism). Pinned so a future edit retains
    the taxonomy."""
    text = DOC_PATH.read_text(encoding="utf-8")
    for cls in (
        "Class A",
        "Class B",
        "Class C",
    ):
        assert cls in text, f"§5 must name divergence class: {cls!r}"
    # And the taxonomy labels.
    text_lower = text.lower()
    assert "kernel diverged" in text_lower
    assert "config drift" in text_lower
    assert "host non-determinism" in text_lower


def test_design_doc_lists_five_ship_when_ready_criteria():
    text = DOC_PATH.read_text(encoding="utf-8")
    for marker in ("1. **", "2. **", "3. **", "4. **", "5. **"):
        assert marker in text, f"§9 must enumerate criterion {marker!r}"


def test_design_doc_states_what_this_is_not():
    text = DOC_PATH.read_text(encoding="utf-8").lower()
    assert "not a recording protocol" in text
    assert "not a binary trace format" in text
    assert "not a substitute" in text
    assert "not host-non-determinism robust" in text


def test_design_doc_names_strict_validation_discipline():
    """§6 must explicitly name the strict-validation discipline so
    a reader can compare against analysis/io.py:episode_record_from_dict."""
    text = DOC_PATH.read_text(encoding="utf-8")
    assert "ReplayBundleError" in text
    assert "episode_record_from_dict" in text


def test_design_doc_names_composition_with_existing_surfaces():
    """§7 composition must name TrustShapedEpisodeRecord, Runner,
    SafetyStateMachine, StreamingFleetMonitor, and the SOTIF
    matrix so the integration story stays auditable."""
    text = DOC_PATH.read_text(encoding="utf-8")
    for surface in (
        "TrustShapedEpisodeRecord",
        "Runner",
        "SafetyStateMachine",
        "StreamingFleetMonitor",
        "SOTIF",
        "ISO 26262",
    ):
        assert surface in text, f"§7 must name surface: {surface!r}"


def test_design_doc_names_bit_identity_contract():
    """§4 must name the bit-identity contract — a future
    contributor refactoring the reconstructor mustn't loosen the
    contract to "approximately equal" without the doc reflecting it."""
    text = DOC_PATH.read_text(encoding="utf-8")
    assert "bit-identical" in text or "bit-identity" in text
    assert "np.array_equal" in text


def test_design_doc_lists_the_two_capture_paths():
    """§3 names two capture paths: end-of-episode by the runner +
    post-hoc construction from a recorded record. Pinned so a
    future edit retains both."""
    text = DOC_PATH.read_text(encoding="utf-8").lower()
    assert "end-of-episode capture" in text
    assert "post-hoc construction" in text or "post-hoc capture" in text or "build_replay_bundle" in text
