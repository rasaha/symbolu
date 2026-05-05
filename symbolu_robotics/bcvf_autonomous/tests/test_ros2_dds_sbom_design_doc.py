"""Tests for the ROS 2 / DDS / SBOM design proposal (`ROS2_DDS_SBOM_DESIGN.md`).

The roadmap §9 row #2 (ROS 2 / DDS / SBOM integration contracts)
lands as a design-doc + thin-shim implementation pair, mirroring
the maturation pattern from ``SAFETY_STATE_MACHINE_DESIGN.md`` and
``MULTI_MODAL_PREDICTORS_DESIGN.md``. These tests pin:

1. The doc ships in the package at the documented path.
2. The doc contains the load-bearing section headers a reviewer
   uses to navigate it (§1 through §10).
3. The three first-call questions (ROS 2 / DDS QoS / SBOM) are
   each answered explicitly.
4. The §3 message contract names both PredictorTrajectory.msg
   and ConsensusOutput.msg.
5. The §4 DDS QoS profile names the
   RELIABLE / VOLATILE / 10ms / 100ms quad.
6. The §6 SBOM section names CycloneDX 1.5 + the on-disk
   snapshot path.
7. The §9 ship-when-ready criteria are present.

Implementation-grade behaviour tests live in dedicated test
modules; this file pins the doc only.
"""

from __future__ import annotations

from pathlib import Path

import symbolu_robotics.bcvf_autonomous as bcvf


DOC_PATH = Path(bcvf.__file__).parent / "ROS2_DDS_SBOM_DESIGN.md"


def test_design_doc_ships_with_the_package():
    """The doc lives next to ``__init__.py`` so a buyer reading the
    source tree finds the integration contract alongside the code."""
    assert DOC_PATH.exists(), (
        f"missing design doc at {DOC_PATH} — the ROS 2 / DDS / SBOM "
        "integration contract must ship as a doc paired with the "
        "implementation"
    )


def test_design_doc_has_required_section_headers():
    """A reviewer navigating the doc relies on these anchors."""
    text = DOC_PATH.read_text(encoding="utf-8")
    for header in (
        "ROS 2 / DDS / SBOM integration contracts",
        "§1 Why this exists",
        "§2 The three first-call questions",
        "§3 ROS 2 message contract",
        "§3.1 PredictorTrajectory.msg",
        "§3.2 ConsensusOutput.msg",
        "§3.3 BCVFNode wiring",
        "§4 DDS QoS profile",
        "§5 Rate-limiting + deadline awareness",
        "§6 CycloneDX SBOM",
        "§7 Composition with existing surfaces",
        "§8 What this is NOT",
        "§9 Ship-when-ready criteria",
        "§10 API sketch",
    ):
        assert header in text, f"design doc missing section: {header!r}"


def test_design_doc_answers_three_first_call_questions():
    """Every Tier 1 / OEM customer's first three questions —
    ROS 2 / DDS QoS / SBOM — must each be named explicitly so a
    reader skimming the doc can match the question to its answer."""
    text = DOC_PATH.read_text(encoding="utf-8")
    for phrase in (
        "Does it speak ROS 2",
        "DDS QoS profile",
        "SBOM",
    ):
        assert phrase in text, (
            f"design doc must answer first-call question: {phrase!r}"
        )


def test_design_doc_names_both_msg_files():
    """§3 names both .msg files. A reader can't be misled into
    thinking the schema is asymmetric."""
    text = DOC_PATH.read_text(encoding="utf-8")
    assert "PredictorTrajectory.msg" in text
    assert "ConsensusOutput.msg" in text


def test_design_doc_names_dds_qos_quad():
    """§4 must explicitly name the
    RELIABLE / VOLATILE / 10ms / 100ms quad an integrator copies
    into their config."""
    text = DOC_PATH.read_text(encoding="utf-8")
    for value in ("RELIABLE", "VOLATILE", "10 ms", "100 ms"):
        assert value in text, f"§4 must name DDS QoS value: {value!r}"


def test_design_doc_dds_qos_table_documents_per_knob_rationale():
    """§4 must include a per-knob rationale table. A reader
    looking up *why* the deadline is 10 ms (and not 5 or 50)
    should find the answer in the doc."""
    text = DOC_PATH.read_text(encoding="utf-8")
    for knob in (
        "reliability",
        "durability",
        "deadline",
        "liveliness lease",
        "history",
        "depth",
    ):
        assert knob in text, f"§4 rationale table missing knob: {knob!r}"


def test_design_doc_names_cyclonedx_format_and_snapshot_path():
    """§6 must name CycloneDX 1.5 (the format) + the snapshot
    path a future contributor diffs against."""
    text = DOC_PATH.read_text(encoding="utf-8")
    assert "CycloneDX 1.5" in text
    assert "SBOM.cdx.json" in text


def test_design_doc_states_what_this_is_not():
    """§8 protects against scope-creep claims."""
    text = DOC_PATH.read_text(encoding="utf-8").lower()
    assert "not a real-time runtime" in text
    assert "not a replacement" in text
    assert "not a substitute" in text


def test_design_doc_lists_five_ship_when_ready_criteria():
    """§9 enumerates five explicit gates that promote the surface
    to STABLE_API. Pinned so a future edit retains all five."""
    text = DOC_PATH.read_text(encoding="utf-8")
    # Each criterion has a numbered list entry; the doc renders
    # them as "1." through "5." in §9.
    for marker in ("1. **", "2. **", "3. **", "4. **", "5. **"):
        assert marker in text, (
            f"§9 must enumerate criterion marker {marker!r}"
        )


def test_design_doc_names_composition_with_existing_surfaces():
    """§7 composition must name the existing surfaces so a reader
    can audit the integration story."""
    text = DOC_PATH.read_text(encoding="utf-8")
    for surface in (
        "BCVFTrustBridge",
        "SafetyStateMachine",
        "StreamingFleetMonitor",
        "AlertRule",
        "PROVISIONAL_API",
    ):
        assert surface in text, (
            f"§7 must name existing surface: {surface!r}"
        )


def test_design_doc_names_rate_limit_and_deadline_invariants():
    """§5 must spell out the three timing invariants — bounded
    publish rate, per-predictor deadline, stale-on-resume
    protection — so a future contributor refactoring the node
    behaviour doesn't drop one silently."""
    text = DOC_PATH.read_text(encoding="utf-8").lower()
    assert "publish rate" in text
    assert "predictor's deadline" in text or "predictor deadline" in text or "per-predictor deadline" in text
    assert "stale-on-resume" in text or "stale on resume" in text
