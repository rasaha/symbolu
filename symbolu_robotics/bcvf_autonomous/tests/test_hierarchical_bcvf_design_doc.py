"""Tests for the hierarchical-BCVF design proposal (`HIERARCHICAL_BCVF_DESIGN.md`).

The brief's *"research / scope expansion — longer horizon"* line item
landed as a design doc, **not** an implementation. These tests pin:

1. The doc ships in the package.
2. The doc contains the load-bearing section headers a reviewer
   uses to navigate it.
3. The hierarchical surface is **not** prematurely promoted to
   `STABLE_API` or `PROVISIONAL_API` — design-only artifacts
   carry no commitment until the §13 ship-when-ready criteria
   are met.

The tests are deliberately minimal — implementation-grade
behaviour tests land with the implementation commit, not with the
design doc.
"""

from __future__ import annotations

from pathlib import Path

import symbolu_robotics.bcvf_autonomous as bcvf
from symbolu_robotics.bcvf_autonomous._api import (
    PROVISIONAL_API,
    STABLE_API,
)


DOC_PATH = Path(bcvf.__file__).parent / "HIERARCHICAL_BCVF_DESIGN.md"


def test_design_doc_ships_with_the_package():
    """The doc lives next to ``__init__.py`` so a buyer reading the
    source tree finds the architecture proposal alongside the code."""
    assert DOC_PATH.exists(), (
        f"missing design doc at {DOC_PATH} — hierarchical BCVF must "
        "ship as a doc even though it has no implementation yet"
    )


def test_design_doc_has_required_section_headers():
    """A reviewer navigating the doc relies on these anchors. The
    test pins the structure so a future edit can't quietly delete
    a load-bearing section.
    """
    text = DOC_PATH.read_text(encoding="utf-8")
    for header in (
        "Hierarchical / group-level BCVF",
        "§1 Why this exists",
        "§2 Current design",
        "§3 Proposed structure",
        "§4 Level 1 — within-group BCVF",
        "§5 Group representative",
        "§6 Level 2 — across-group BCVF",
        "§7 Total cost composition",
        "§8 Per-predictor attribution",
        "§9 Lemma 1 carry-through",
        "§10 Failure modes",
        "§11 Certification implications",
        "§12 Backward compatibility",
        "§13 Ship-when-ready criteria",
        "§14 API sketch",
        "§15 Open questions",
        "§16 What this is NOT",
    ):
        assert header in text, f"design doc missing section: {header!r}"


def test_design_doc_states_no_implementation():
    """The doc must explicitly say there is no implementation yet —
    a reader skimming the section headers should not be misled into
    thinking the surface is callable today."""
    text = DOC_PATH.read_text(encoding="utf-8")
    assert "design only" in text.lower() or "not yet implemented" in text.lower(), (
        "design doc must explicitly mark itself as design-only / "
        "not-yet-implemented"
    )


def test_design_doc_lists_ship_when_ready_criteria():
    """§13 enumerates the three triggers that promote the doc to an
    implementation. The test pins that all three appear so the
    promotion gate stays explicit."""
    text = DOC_PATH.read_text(encoding="utf-8")
    # Triggers (paraphrased):
    #   1. Real fleet data shows M > 6
    #   2. Flat-BCVF attribution dilution observed
    #   3. Certification-grid extension passes
    assert "M > 6" in text or "M ≥ 7" in text or "M > 4" in text
    assert "attribution dilution" in text.lower()
    assert "certification" in text.lower() and "grid" in text.lower()


def test_hierarchical_surface_not_in_stable_api():
    """The design doc names a hypothetical
    ``compute_hierarchical_bcvf_cost`` API. Per ``API_STABILITY.md``
    §2, design-only surfaces are *internal* — they carry no
    commitment until the implementation ships. Pinned to catch a
    premature promotion.
    """
    for q in STABLE_API:
        assert "hierarchical" not in q.lower(), (
            f"stable API must not include hierarchical surface "
            f"{q!r} — design-only artifacts carry no commitment"
        )


def test_hierarchical_surface_not_in_provisional_api():
    """Same gate against ``PROVISIONAL_API``. Provisional means
    *shipped, supported, may evolve* — a design doc isn't shipped."""
    for q in PROVISIONAL_API:
        assert "hierarchical" not in q.lower(), (
            f"provisional API must not include hierarchical surface "
            f"{q!r} — design-only artifacts carry no commitment"
        )


def test_design_doc_acknowledges_lemma_1_carry_through():
    """Critical correctness property — §9 must address how Lemma 1
    invariance survives the hierarchy. Without this, hierarchical
    can't reuse the existing `constant_bias` / `linear_drift`
    nominal families and the certification grid extension is
    implicitly broken.
    """
    text = DOC_PATH.read_text(encoding="utf-8")
    assert "Lemma 1" in text or "Lemma-1" in text or "lemma 1" in text.lower()
    # The carry-through argument must explicitly mention both levels.
    assert "within-group" in text.lower()
    assert "across-group" in text.lower()


def test_design_doc_lists_three_representative_options():
    """§5 must enumerate the three options (trust-weighted mean,
    arithmetic mean, winner-take-all). Pinned because the
    design's recommendation depends on the tradeoffs across all
    three.
    """
    text = DOC_PATH.read_text(encoding="utf-8")
    for option in ("trust-weighted", "arithmetic mean", "winner-take-all"):
        assert option.lower() in text.lower(), (
            f"design doc must enumerate the {option!r} representative option"
        )


def test_design_doc_calls_out_correlated_within_group_failure():
    """One of the explicit failure modes the hierarchy *can't*
    fully solve (two of three sensors share a clock). The doc must
    name it as a known limit so a future implementer doesn't
    over-promise."""
    text = DOC_PATH.read_text(encoding="utf-8")
    assert "correlated" in text.lower()
    assert "within-group" in text.lower() or "within_group" in text.lower()
