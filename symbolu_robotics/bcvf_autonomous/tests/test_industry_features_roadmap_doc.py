"""Tests for the industry-features roadmap doc (`INDUSTRY_FEATURES_ROADMAP.md`).

The roadmap is research-tier — it enumerates the gap between
"interesting research stack" and "production safety-critical
software a Tier 1 ships," ranked by deal-unlock value. These
tests pin:

1. The doc ships at the documented path.
2. The load-bearing section headers are present (a future edit
   can't quietly delete a roadmap section).
3. The nine ranking rows in §9 are present (deletion of a row
   without acknowledgement fails CI).
4. Roadmap names have not leaked into ``STABLE_API`` /
   ``PROVISIONAL_API`` — research-tier items carry no integration
   commitment until a design-doc + implementation pair ships.

The tests are deliberately minimal — implementation-grade pins
land alongside each item's eventual implementation commit.
"""

from __future__ import annotations

from pathlib import Path

import symbolu_robotics.bcvf_autonomous as bcvf
from symbolu_robotics.bcvf_autonomous._api import (
    PROVISIONAL_API,
    STABLE_API,
)


DOC_PATH = Path(bcvf.__file__).parent / "INDUSTRY_FEATURES_ROADMAP.md"


def test_roadmap_doc_ships_with_the_package():
    """Lives next to ``__init__.py`` so a buyer / new engineer reading
    the source tree finds the technical roadmap alongside the code."""
    assert DOC_PATH.exists(), (
        f"missing roadmap doc at {DOC_PATH} — research-tier roadmaps "
        "ship as docs even though they have no implementation yet"
    )


def test_roadmap_has_required_section_headers():
    """A reader navigating the doc relies on these anchors. Pinned
    so a future edit can't quietly delete a load-bearing section.
    """
    text = DOC_PATH.read_text(encoding="utf-8")
    for header in (
        "Industry-features roadmap",
        "§1 Why this exists",
        "§2 Real-time / determinism gaps",
        "§3 ROS 2 / DDS / SBOM integration contracts",
        "§4 Functional-safety state machine",
        "§5 Replay / record-and-replay framework",
        "§6 Calibration parameter management",
        "§7 Sensor attestation / data provenance",
        "§8 Domain-specific predictors",
        "§9 Ranking by deal-unlock value",
        "§9.1 Recommendation",
        "§10 What this is NOT",
        "§11 Maturation path",
        "§12 Test pin",
        "§13 Implementation prompt",
        "§13.1 Prompt",
        "§13.2 Why the prompt lives in this doc",
        "§13.3 Prompt template for future top-ranked items",
    ):
        assert header in text, f"roadmap missing section: {header!r}"


def test_roadmap_marks_itself_as_no_implementation():
    """Skim-reader protection — anyone reading the headers should not
    be misled into thinking the surface is callable today."""
    text = DOC_PATH.read_text(encoding="utf-8").lower()
    assert "no implementation" in text, (
        "roadmap doc must explicitly mark itself as no-implementation"
    )


def test_roadmap_lists_all_nine_ranking_rows():
    """§9 is the load-bearing section. The rows must be present so a
    buyer reading the doc sees the full deal-unlock ranking.
    Pinned by per-row-rank-marker check."""
    text = DOC_PATH.read_text(encoding="utf-8")
    for rank in range(1, 10):
        # Each row has a bolded rank marker like "**1**" or "**9**".
        assert f"**{rank}**" in text, f"roadmap §9 missing rank {rank}"


def test_roadmap_names_explicit_recommendation():
    """§9.1 names the single-pick recommendation (functional-safety
    state machine). Pinned so a future edit retains the explicit
    "what to do next" guidance."""
    text = DOC_PATH.read_text(encoding="utf-8").lower()
    assert "functional-safety state machine" in text


def test_roadmap_acknowledges_existing_shipped_surfaces():
    """§1 establishes context by enumerating what's already shipped.
    Pinned so a future edit doesn't lose the "here's what's done"
    framing — the roadmap is meaningless without it."""
    text = DOC_PATH.read_text(encoding="utf-8")
    for shipped in (
        "StreamingFleetMonitor",
        "STABLE_API",
        "PROVISIONAL_API",
        "1560 cells",
        "Wilson 95% CI",
        "SOTIF",
    ):
        assert shipped in text, f"roadmap §1 must mention shipped surface: {shipped}"


# --------------------------------------------------------------------------- #
# Non-promotion gate — roadmap names must not leak into the API registry
# --------------------------------------------------------------------------- #


# Tokens drawn from the §2-§8 vocabulary. A future contributor who
# adds (e.g.) ``runtime.RealTimeBudget`` to PROVISIONAL_API without
# first promoting the roadmap row to a real design doc would trip
# one of these checks.
#
# Notes on removed tokens:
# * ``SafetyStateMachine`` was on this list in v0.7 — removed
#   post-v0.7 once the §4 / §9.1-recommended-pick design-doc +
#   thin-shim implementation pair landed in ``safety_state/``.
# * ``BCVFNode`` was on this list in v0.7.x — removed post-v0.7.x
#   once the §3 / §9-row-#2 design-doc + thin-shim implementation
#   pair landed in ``bcvf_ros2/`` + ``ROS2_DDS_SBOM_DESIGN.md``.
# * ``ReplayBundle`` was on this list in v0.7.x — removed
#   post-v0.7.x once the §5 / §9-row-#3 design-doc + thin-shim
#   implementation pair landed in ``replay/`` +
#   ``REPLAY_FRAMEWORK_DESIGN.md``.
# * ``RealTimeBudget`` was on this list in v0.7.x — removed
#   post-v0.7.x once the §2 / §9-row-#4 design-doc + thin-shim
#   implementation pair landed in ``realtime/`` +
#   ``REAL_TIME_BUDGET_DESIGN.md``.
# * ``CalibrationSet`` was on this list in v0.7.x — removed
#   post-v0.7.x once the §6 / §9-row-#6 design-doc + thin-shim
#   implementation pair landed in ``calibration/`` +
#   ``CALIBRATION_DESIGN.md``.
# * ``SensorAttestation`` was on this list in v0.7.x — removed
#   post-v0.7.x once the §7 / §9-row-#8 design-doc + thin-shim
#   implementation pair landed in ``attestation/`` +
#   ``SENSOR_ATTESTATION_DESIGN.md``. This was the LAST token —
#   every six §9-shippable rows (#1, #2, #3, #4, #6, #8) now
#   landed; rows #5 (HD-map predictor) and #9 (domain-specific
#   predictors) are hardware-adjacent + need real predictor-
#   stack data, not sandbox-implementable. Row #7 (SBOM) shipped
#   absorbed into row #2 (CycloneDX 1.5 manifest under
#   ``safety_case/SBOM.cdx.json``).
# All six surfaces are now provisional (tracked by
# ``test_api_stability.py``); their §9 roadmap rows are struck
# through with pointers to the corresponding design docs per the
# §11 maturation path.
#
# The empty tuple is intentional: a future contributor adding a
# new roadmap row should add a new token here. The non-promotion
# gate tests (test_roadmap_surfaces_not_in_stable_api +
# test_roadmap_surfaces_not_in_provisional_api) still run and
# trivially pass when the tuple is empty — same discipline,
# zero pending tokens.
_ROADMAP_TOKENS: tuple = ()


def test_roadmap_surfaces_not_in_stable_api():
    """The §2-§8 candidate-surface tokens must not appear in
    ``STABLE_API``. Per ``API_STABILITY.md`` §2, research-tier names
    carry no commitment until the implementation ships; promoting a
    roadmap candidate before its design-doc + implementation pair
    lands skips the gate.
    """
    for q in STABLE_API:
        for token in _ROADMAP_TOKENS:
            assert token not in q, (
                f"stable API contains roadmap-tier surface {q!r} "
                f"(token {token!r}) — promote the roadmap row to a "
                "design doc + implementation before adding to STABLE_API"
            )


def test_roadmap_surfaces_not_in_provisional_api():
    """Same gate against PROVISIONAL_API — provisional means
    *shipped, supported, may evolve*; a roadmap candidate isn't
    shipped."""
    for q in PROVISIONAL_API:
        for token in _ROADMAP_TOKENS:
            assert token not in q, (
                f"provisional API contains roadmap-tier surface {q!r} "
                f"(token {token!r}) — research-tier surfaces stay out "
                "of the API registry until implementation ships"
            )


def test_roadmap_prompt_appendix_names_recommended_pick():
    """§13.1 captures the implementation prompt for §9.1's
    recommended next pick. The prompt must name SafetyStateMachine
    + SAFETY_STATE_MACHINE_DESIGN.md so a contributor pasting the
    prompt into a fresh session targets the right surface.
    """
    text = DOC_PATH.read_text(encoding="utf-8")
    assert "SafetyStateMachine" in text
    assert "SAFETY_STATE_MACHINE_DESIGN.md" in text


def test_roadmap_prompt_appendix_enumerates_four_states():
    """The four named safety states (NORMAL / DEGRADED / FAULT /
    FAILSAFE) must all appear in §13.1 so a future contributor
    reading the prompt can't accidentally drop one when adapting
    the prompt for the implementation."""
    text = DOC_PATH.read_text(encoding="utf-8")
    for state in ("NORMAL", "DEGRADED", "FAULT", "FAILSAFE"):
        assert state in text, f"prompt §13.1 must name state: {state}"


def test_roadmap_prompt_template_documents_eleven_workflow_steps():
    """§13.3 documents the prompt template for future top-ranked
    items. The template names the load-bearing discipline pieces
    a future contributor would otherwise drop (audit pass, design
    doc first, ship-when-ready criteria, etc.)."""
    text = DOC_PATH.read_text(encoding="utf-8")
    for piece in (
        "Design doc first",
        "ship-when-ready criteria",
        "Safety-case integration",
        "API stability",
        "Audit pass",
    ):
        assert piece in text, (
            f"prompt template §13.3 must name: {piece!r}"
        )


def test_roadmap_test_pin_section_documents_invariants():
    """§12 is the meta-doc that names the invariants this very test
    file enforces. Pinned so a future contributor adding a roadmap
    row also adds (or considers adding) a test pin for it."""
    text = DOC_PATH.read_text(encoding="utf-8")
    assert "§12 Test pin" in text
    # The invariants the test file enforces are named.
    for invariant in (
        "doc ships",
        "ranking rows",
        "STABLE_API",
        "PROVISIONAL_API",
    ):
        assert invariant in text, (
            f"roadmap §12 must name the test-pin invariant: {invariant}"
        )
