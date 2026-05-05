"""Tests for the real-time-budget design proposal (`REAL_TIME_BUDGET_DESIGN.md`).

The roadmap §9 row #4 (real-time / no-allocation hot path +
p999 budget) lands as a design-doc + thin-shim implementation
pair, mirroring the maturation pattern from
``SAFETY_STATE_MACHINE_DESIGN.md`` /
``ROS2_DDS_SBOM_DESIGN.md`` /
``REPLAY_FRAMEWORK_DESIGN.md``. These tests pin:

1. The doc ships in the package at the documented path.
2. The doc contains the load-bearing section headers a reviewer
   uses to navigate it (§1 through §10).
3. The §2 budget contract names every required field.
4. The §4 percentile reporting contract names the
   percentile-availability discipline (p999 / p9999 require
   sample-count thresholds).
5. The §9 ship-when-ready criteria are present (five gates).

Implementation-grade behaviour tests live in dedicated test
modules; this file pins the doc only.
"""

from __future__ import annotations

from pathlib import Path

import symbolu_robotics.bcvf_autonomous as bcvf


DOC_PATH = Path(bcvf.__file__).parent / "REAL_TIME_BUDGET_DESIGN.md"


def test_design_doc_ships_with_the_package():
    assert DOC_PATH.exists(), (
        f"missing design doc at {DOC_PATH} — the real-time-budget "
        "framework must ship as a doc paired with the implementation"
    )


def test_design_doc_has_required_section_headers():
    text = DOC_PATH.read_text(encoding="utf-8")
    for header in (
        "Real-time / no-allocation hot path + p999 budget",
        "§1 Why this exists",
        "§2 The budget contract",
        "§3 Per-tick observation",
        "§4 Percentile reporting",
        "§5 The over-budget audit trail",
        "§6 No-allocation discipline",
        "§7 Composition with existing surfaces",
        "§8 What this is NOT",
        "§9 Ship-when-ready criteria",
        "§10 API sketch",
    ):
        assert header in text, f"design doc missing section: {header!r}"


def test_design_doc_names_required_budget_fields():
    """§2 must enumerate every RealTimeBudget field so a reader
    skimming the doc can audit the contract surface."""
    text = DOC_PATH.read_text(encoding="utf-8")
    for field in (
        "target_hz",
        "p99_budget_ms",
        "p999_budget_ms",
        "p9999_budget_ms",
        "max_budget_ms",
        "min_samples_for_p999",
        "min_samples_for_p9999",
        "over_budget_log_capacity",
    ):
        assert field in text, f"§2 must name budget field: {field!r}"


def test_design_doc_names_percentile_availability_discipline():
    """§4 must explicitly state that p999 / p9999 are not
    reported below the documented sample-count threshold —
    a fake-percentile-on-small-n is a real risk the doc
    protects against."""
    text = DOC_PATH.read_text(encoding="utf-8")
    assert "min_samples_for_p999" in text
    assert "min_samples_for_p9999" in text
    # The doc must explain why a small-sample p999 is rejected.
    assert "statistical noise" in text.lower() or "noise, not a contract" in text.lower()


def test_design_doc_names_three_target_tier_examples():
    """§2 should name the three deployment tiers (drone /
    industrial / automotive) so a reader can map their tier to
    the default knobs."""
    text = DOC_PATH.read_text(encoding="utf-8").lower()
    for tier in ("drone", "industrial", "automotive"):
        assert tier in text, f"§2 must name tier example: {tier!r}"


def test_design_doc_lists_five_ship_when_ready_criteria():
    text = DOC_PATH.read_text(encoding="utf-8")
    for marker in ("1. **", "2. **", "3. **", "4. **", "5. **"):
        assert marker in text, f"§9 must enumerate criterion {marker!r}"


def test_design_doc_states_what_this_is_not():
    text = DOC_PATH.read_text(encoding="utf-8").lower()
    assert "not a real-time guarantee" in text
    assert "not a replacement" in text
    assert "not a no-allocation enforcer" in text
    assert "not a thread-safety enforcer" in text


def test_design_doc_acknowledges_python_gil_limitation():
    """§6 + §8 must explicitly acknowledge the CPython GIL +
    pure-Python "zero allocations" impossibility — a reader
    must not be misled into thinking the framework delivers
    hard real-time."""
    text = DOC_PATH.read_text(encoding="utf-8")
    assert "GIL" in text
    assert "tracemalloc" in text


def test_design_doc_names_composition_with_existing_surfaces():
    """§7 composition must name the existing surfaces so the
    integration story stays auditable."""
    text = DOC_PATH.read_text(encoding="utf-8")
    for surface in (
        "benchmark_planner",
        "benchmarks/latency.py",
        "EpisodeDiagnostics",
        "SafetyStateMachine",
        "ReplayBundle",
        "SOTIF",
        "ISO 26262 Part 6 §10",
    ):
        assert surface in text, f"§7 must name surface: {surface!r}"


def test_design_doc_names_autosar_motivation():
    """§1 must explicitly name AUTOSAR — the deal-unlock
    framing in the roadmap. A reader skimming should see why
    this matters for the integration partner."""
    text = DOC_PATH.read_text(encoding="utf-8")
    assert "AUTOSAR" in text
