"""Tests for the safety-state-machine design proposal (`SAFETY_STATE_MACHINE_DESIGN.md`).

The roadmap §9.1's recommended next pick (functional-safety state
machine) lands as a design-doc + thin-shim implementation pair,
mirroring the maturation pattern from
``MULTI_MODAL_PREDICTORS_DESIGN.md``. These tests pin:

1. The doc ships in the package at the documented path.
2. The doc contains the load-bearing section headers a reviewer
   uses to navigate it (§1 through §10).
3. The four named states (NORMAL / DEGRADED / FAULT / FAILSAFE)
   are all named in the doc — a reader can't be misled into
   thinking the contract names a different set.
4. The §5 ASIL decomposition table names every transition with
   an ASIL classification (B or D) so a future edit can't quietly
   drop a row.
5. The §9 ship-when-ready criteria are present (three named
   gates).

Implementation-grade behaviour tests live in
``test_safety_state_machine.py``; this file pins the doc only.
"""

from __future__ import annotations

from pathlib import Path

import symbolu_robotics.bcvf_autonomous as bcvf


DOC_PATH = Path(bcvf.__file__).parent / "SAFETY_STATE_MACHINE_DESIGN.md"


def test_design_doc_ships_with_the_package():
    """The doc lives next to ``__init__.py`` so a buyer reading the
    source tree finds the architecture proposal alongside the code."""
    assert DOC_PATH.exists(), (
        f"missing design doc at {DOC_PATH} — the safety-state-machine "
        "design must ship as a doc paired with the implementation"
    )


def test_design_doc_has_required_section_headers():
    """A reviewer navigating the doc relies on these anchors. The
    test pins the structure so a future edit can't quietly delete
    a load-bearing section.
    """
    text = DOC_PATH.read_text(encoding="utf-8")
    for header in (
        "Functional-safety state machine",
        "§1 Why this exists",
        "§2 Four states",
        "§3 Trigger conditions",
        "§4 Recovery conditions",
        "§5 ASIL decomposition",
        "§6 Direct-jump prohibition",
        "§7 Composition with existing surfaces",
        "§8 What this is NOT",
        "§9 Ship-when-ready criteria",
        "§10 API sketch",
    ):
        assert header in text, f"design doc missing section: {header!r}"


def test_design_doc_names_four_states():
    """The four named safety states (NORMAL / DEGRADED / FAULT /
    FAILSAFE) must all appear in the doc — a reader can't be misled
    into thinking the contract names a different set."""
    text = DOC_PATH.read_text(encoding="utf-8")
    for state in ("NORMAL", "DEGRADED", "FAULT", "FAILSAFE"):
        assert state in text, f"design doc must name state: {state}"


def test_design_doc_names_six_legal_transitions():
    """The six legal transitions (four automatic + two manual-reset)
    must each appear in the doc as ``A → B`` or ``A -> B`` so a
    reader can enumerate the transition graph from the prose."""
    text = DOC_PATH.read_text(encoding="utf-8")
    for transition in (
        "NORMAL → DEGRADED",
        "DEGRADED → NORMAL",
        "DEGRADED → FAULT",
        "FAULT → FAILSAFE",
        "FAULT → DEGRADED",
        "FAILSAFE → FAULT",
    ):
        assert transition in text, (
            f"design doc must name legal transition: {transition!r}"
        )


def test_design_doc_lists_asil_decomposition_per_transition():
    """§5 names each transition's ASIL classification. The pin
    counts ASIL-B + ASIL-D occurrences — there must be at least
    four ASIL-B (NORMAL↔DEGRADED + 2 manual-reset paths) and at
    least two ASIL-D (DEGRADED → FAULT, FAULT → FAILSAFE)."""
    text = DOC_PATH.read_text(encoding="utf-8")
    assert text.count("ASIL-B") >= 4, (
        "§5 should name ASIL-B at least four times "
        "(NORMAL→DEGRADED, DEGRADED→NORMAL, FAULT→DEGRADED, FAILSAFE→FAULT)"
    )
    assert text.count("ASIL-D") >= 2, (
        "§5 should name ASIL-D at least twice "
        "(DEGRADED→FAULT, FAULT→FAILSAFE)"
    )


def test_design_doc_states_direct_jump_prohibition():
    """§6 must explicitly prohibit direct jumps from NORMAL to FAULT
    or FAILSAFE. A reader skimming §6 should see the prohibition
    named, not buried in implementation prose."""
    text = DOC_PATH.read_text(encoding="utf-8").lower()
    assert "direct jump" in text or "direct-jump" in text, (
        "§6 must explicitly use the term 'direct jump' / 'direct-jump'"
    )
    assert "prohibit" in text or "forbid" in text or "disallow" in text, (
        "§6 must name the prohibition explicitly"
    )


def test_design_doc_lists_three_ship_when_ready_criteria():
    """§9 enumerates the three explicit gates that promote the
    surface to STABLE_API. Pinned so a future edit retains the
    gates."""
    text = DOC_PATH.read_text(encoding="utf-8")
    assert "three deployment partners" in text.lower() or (
        "three deployment-partners" in text.lower()
    )
    assert "characterization grid" in text.lower()
    assert "auditor" in text.lower() or "TÜV" in text


def test_design_doc_names_trust_shaped_episode_record():
    """§3 trigger conditions must reference TrustShapedEpisodeRecord
    + the per-step fields the trigger predicates read. Pinned so a
    future refactor can't decouple the doc from the underlying
    record without surfacing the change."""
    text = DOC_PATH.read_text(encoding="utf-8")
    assert "TrustShapedEpisodeRecord" in text
    for field in (
        "per_step_is_excluded",
        "per_step_consec_suspect",
        "per_step_bcvf_total",
    ):
        assert field in text, f"§3 must name field: {field!r}"


def test_design_doc_names_streaming_fleet_monitor_composition():
    """§7 composition with existing surfaces names
    StreamingFleetMonitor + AlertRule + the SOTIF traceability
    matrix. Pinned so the composition story stays explicit."""
    text = DOC_PATH.read_text(encoding="utf-8")
    assert "StreamingFleetMonitor" in text
    assert "AlertRule" in text
    assert "SOTIF" in text
    assert "ISO 26262" in text


def test_design_doc_names_what_this_is_not():
    """§8 protects against scope-creep claims. The four named
    'NOT' items (planner replacement, generic library, OEM safety
    case substitute, V2 chatter replacement) must each be named."""
    text = DOC_PATH.read_text(encoding="utf-8").lower()
    assert "not a planner replacement" in text
    assert "not a generic state-machine library" in text
    assert "not a substitute" in text
    assert "consumerv2" in text or "consumer v2" in text
