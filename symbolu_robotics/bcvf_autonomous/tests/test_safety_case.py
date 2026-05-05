"""Tests for the SOTIF / ISO 26262 traceability template.

Three invariants:

1. Every evidence artifact in the matrix is importable + the named
   symbol exists. A renamed module or removed symbol surfaces as a
   test failure rather than silently invalidating a clause.
2. Every clause has ≥1 evidence artifact + every evidence artifact
   is referenced by ≥1 clause — no orphaned clauses, no orphaned
   artifacts.
3. The on-disk ``SOTIF_TRACEABILITY.md`` snapshot is byte-identical
   to ``render_markdown(build_traceability_matrix())``. A drift
   between matrix + doc fails the suite loudly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from symbolu_robotics.bcvf_autonomous.safety_case import (
    Clause,
    EvidenceArtifact,
    Standard,
    TraceabilityMatrix,
    build_traceability_matrix,
    iso_21448_clauses,
    iso_26262_part6_clauses,
    render_markdown,
)


SNAPSHOT_PATH = (
    Path(__file__).parent.parent
    / "safety_case"
    / "SOTIF_TRACEABILITY.md"
)


# --------------------------------------------------------------------------- #
# Matrix structure
# --------------------------------------------------------------------------- #


def test_iso_21448_covers_clauses_5_through_10():
    clause_ids = [c.clause_id for c in iso_21448_clauses()]
    assert clause_ids == ["5", "6", "7", "8", "9", "10"]


def test_iso_26262_part6_covers_software_clauses():
    clause_ids = [c.clause_id for c in iso_26262_part6_clauses()]
    assert clause_ids == [
        "Part 6 §7",
        "Part 6 §8",
        "Part 6 §9",
        "Part 6 §9.4.4",
        "Part 6 §10",
        "Part 6 §11",
    ]


def test_matrix_groups_by_standard():
    matrix = build_traceability_matrix()
    assert set(matrix.entries_by_standard.keys()) == {
        Standard.SOTIF_21448, Standard.ISO_26262_PART_6,
    }
    assert len(matrix.entries_by_standard[Standard.SOTIF_21448]) == 6
    assert len(matrix.entries_by_standard[Standard.ISO_26262_PART_6]) == 6


# --------------------------------------------------------------------------- #
# Per-clause hygiene
# --------------------------------------------------------------------------- #


def test_every_clause_has_at_least_one_evidence_artifact():
    matrix = build_traceability_matrix()
    for clause in matrix.all_clauses():
        assert len(clause.evidence) >= 1, (
            f"clause {clause.standard.name}::{clause.clause_id} has no evidence"
        )


def test_every_clause_has_non_empty_requirement_and_title():
    matrix = build_traceability_matrix()
    for clause in matrix.all_clauses():
        assert clause.title.strip(), clause.clause_id
        assert clause.requirement.strip(), clause.clause_id


# --------------------------------------------------------------------------- #
# Artifact resolution — every evidence reference must be live
# --------------------------------------------------------------------------- #


def test_every_evidence_artifact_is_importable_and_symbol_exists():
    """Resolves every (module_path, symbol) in the matrix. A renamed
    module or removed symbol fails this test instead of silently
    leaving the safety-case mapping pointing at a ghost."""
    matrix = build_traceability_matrix()
    for art in matrix.all_artifacts():
        # Resolve raises ImportError / AttributeError on drift.
        art.resolve()


def test_every_artifact_is_referenced_by_at_least_one_clause():
    matrix = build_traceability_matrix()
    reverse = matrix.reverse_index()
    for art in matrix.all_artifacts():
        assert art.reference in reverse, (
            f"artifact {art.reference} is defined but no clause references it"
        )
        assert len(reverse[art.reference]) >= 1


def test_no_duplicate_evidence_within_a_clause():
    """Defensive pin: an evidence artifact must appear at most once
    in any single clause's evidence tuple. A copy-paste error that
    listed the same artifact twice would silently double-count it
    in the reverse index ("this artifact serves clause X twice")
    and inflate evidence-count metrics; the test catches the
    malformed clause loudly."""
    matrix = build_traceability_matrix()
    for clause in matrix.all_clauses():
        refs = [a.reference for a in clause.evidence]
        assert len(refs) == len(set(refs)), (
            f"clause {clause.standard.name}::{clause.clause_id} lists "
            f"a duplicate evidence artifact: {refs}"
        )


def test_artifact_resolve_failure_is_explicit():
    art = EvidenceArtifact(
        module_path="symbolu_robotics.bcvf_autonomous.core",
        symbol="this_symbol_does_not_exist",
    )
    with pytest.raises(AttributeError) as exc_info:
        art.resolve()
    assert "stale" in str(exc_info.value)


def test_artifact_reference_renders_module_and_symbol():
    art = EvidenceArtifact(
        module_path="symbolu_robotics.bcvf_autonomous.core",
        symbol="BCVFConfig",
    )
    assert art.reference == "symbolu_robotics.bcvf_autonomous.core::BCVFConfig"


def test_artifact_reference_falls_back_to_module_when_no_symbol():
    art = EvidenceArtifact(
        module_path="symbolu_robotics.bcvf_autonomous.core",
        symbol=None,
    )
    assert art.reference == "symbolu_robotics.bcvf_autonomous.core"


# --------------------------------------------------------------------------- #
# Audit-priority coverage — pin the brief's claimed mapping
# --------------------------------------------------------------------------- #


def _evidence_refs_for(matrix: TraceabilityMatrix, clause_id: str) -> set:
    for c in matrix.all_clauses():
        if c.clause_id == clause_id:
            return {a.reference for a in c.evidence}
    raise KeyError(clause_id)


def test_sotif_clause_6_grounds_the_seven_family_taxonomy():
    """The brief says the seven characterization families are the
    HA inputs (SOTIF clause 6). Pin that ``generate_trace`` is the
    evidence artifact, so a future refactor that hides the family
    taxonomy fails this assertion loudly."""
    matrix = build_traceability_matrix()
    refs = _evidence_refs_for(matrix, "6")
    assert any("characterization.traces::generate_trace" in r for r in refs)


def test_sotif_clause_7_grounds_the_triggering_condition_table():
    """FAMILY_MAGNITUDES + the 1320-cell primary grid are the
    triggering-condition table (SOTIF clause 7)."""
    matrix = build_traceability_matrix()
    refs = _evidence_refs_for(matrix, "7")
    assert any("FAMILY_MAGNITUDES" in r for r in refs)
    assert any("run_primary_grid" in r for r in refs)


def test_sotif_clause_8_grounds_v2_chatter_immunity():
    """V2 Schmitt-trigger + V2 promotion-decision sweep are the
    functional-insufficiency mitigation (SOTIF clause 8)."""
    matrix = build_traceability_matrix()
    refs = _evidence_refs_for(matrix, "8")
    assert any("ConsumerV2Config" in r for r in refs)
    assert any("run_v2_promotion_decision" in r for r in refs)


def test_sotif_clause_9_grounds_certification_grid_and_pilot():
    """V&V evidence: certification grid + Wilson CI primitive +
    apples-to-apples baseline shootout + §6.2 pilot (SOTIF clause 9)."""
    matrix = build_traceability_matrix()
    refs = _evidence_refs_for(matrix, "9")
    assert any("run_primary_grid" in r for r in refs)
    assert any("wilson_ci" in r for r in refs)
    assert any("baselines::run_shootout" in r for r in refs)
    assert any("pilot::run_pilot" in r for r in refs)


def test_sotif_clause_10_grounds_post_incident_trace_and_fleet_harness():
    """Per-step diagnostic record + FleetSummary + near-veto detector
    are the field-monitoring evidence (SOTIF clause 10)."""
    matrix = build_traceability_matrix()
    refs = _evidence_refs_for(matrix, "10")
    assert any("TrustShapedEpisodeRecord" in r for r in refs)
    assert any("FleetSummary" in r for r in refs)
    assert any("find_near_vetoes" in r for r in refs)


def test_iso_26262_part6_section_9_4_4_grounds_certification_grid():
    """The unit-verification clause must point at the 1320-cell
    primary grid + Wilson CI floor — that's the structural-coverage
    + statistical-bound argument the certification grid was designed
    for."""
    matrix = build_traceability_matrix()
    refs = _evidence_refs_for(matrix, "Part 6 §9.4.4")
    assert any("run_primary_grid" in r for r in refs)
    assert any("summarize_grid" in r for r in refs)
    assert any("wilson_ci" in r for r in refs)


# --------------------------------------------------------------------------- #
# Snapshot parity — the on-disk markdown must match render_markdown()
# --------------------------------------------------------------------------- #


def test_snapshot_file_exists():
    assert SNAPSHOT_PATH.exists(), (
        f"missing snapshot: {SNAPSHOT_PATH}. Run the snapshot generator "
        "(see safety_case/DESIGN.md §4)."
    )


def test_snapshot_matches_rendered_matrix():
    """The on-disk SOTIF_TRACEABILITY.md must be byte-identical to
    ``render_markdown(build_traceability_matrix())``. A drift means
    either (a) the matrix changed without re-rendering the doc, or
    (b) the doc was hand-edited. Either way, the doc is no longer
    a faithful snapshot of the matrix.
    """
    matrix = build_traceability_matrix()
    rendered = render_markdown(matrix)
    on_disk = SNAPSHOT_PATH.read_text(encoding="utf-8")
    assert on_disk == rendered, (
        "SOTIF_TRACEABILITY.md is out of sync with the matrix. "
        "Re-render via the snippet in safety_case/DESIGN.md §4."
    )


def test_render_markdown_is_deterministic():
    """Same matrix in, same string out — snapshot parity depends on
    deterministic rendering."""
    matrix = build_traceability_matrix()
    a = render_markdown(matrix)
    b = render_markdown(matrix)
    assert a == b


def test_render_markdown_includes_reverse_index():
    matrix = build_traceability_matrix()
    md = render_markdown(matrix)
    assert "Reverse index" in md
    # Spot-check: the BCVF kernel artifact appears in the reverse index.
    assert "compute_bcvf_cost" in md
