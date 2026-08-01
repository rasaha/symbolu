"""S4 — legacy/canonical import compatibility (identity-preserving).

Proves that every pre-migration ``composite_threat_detector`` import resolves to
the SAME object exposed by the canonical ``ugence_storygraph`` package, that no
public symbol disappeared, and that public dataclass/enum serialization is
unchanged across the two import paths.
"""

from __future__ import annotations

import dataclasses

import ugence_storygraph as canon
import composite_threat_detector as legacy


def test_top_level_reexports_are_identical_objects():
    # Every public symbol on the legacy surface is the *same object* as canonical.
    assert set(legacy.__all__) == set(canon.__all__)
    for name in canon.__all__:
        assert getattr(legacy, name) is getattr(canon, name), name


def test_version_matches():
    assert legacy.__version__ == canon.__version__ == "2.0.0"


def test_submodule_redirect_preserves_identity():
    from composite_threat_detector import storygraph as legacy_sg
    from ugence_storygraph import storygraph as canon_sg
    assert legacy_sg is canon_sg

    from composite_threat_detector import storyverdict as legacy_sv
    from ugence_storygraph import storyverdict as canon_sv
    assert legacy_sv is canon_sv


def test_deep_submodule_redirect_preserves_identity():
    from composite_threat_detector.policypack import compiler as legacy_c
    from ugence_storygraph.policypack import compiler as canon_c
    assert legacy_c is canon_c

    import composite_threat_detector.policypack.replay as legacy_r
    import ugence_storygraph.policypack.replay as canon_r
    assert legacy_r is canon_r


def test_lazy_submodule_redirect_resolves():
    # cli / replay are not eagerly imported by __init__ — the redirect must still
    # resolve them lazily to the canonical module.
    from composite_threat_detector import cli as legacy_cli
    from ugence_storygraph import cli as canon_cli
    assert legacy_cli is canon_cli


def test_compat_metadata_declares_itself():
    assert legacy.__compatibility__ is True
    assert legacy.__canonical_package__ == "ugence_storygraph"
    assert legacy.__removal_review_version__ == "3.0.0"


def test_public_dataclass_serialization_identical():
    # Build an ObservedEvent via each path; asdict output must match exactly.
    L = legacy.ObservedEvent
    C = canon.ObservedEvent
    assert L is C  # same class → same serialization by construction
    from ugence_storygraph import financial as F
    ev_canon = C(F.CRED_RESET, "e1", 1, 1, "u1", {"account": "a1"})
    ev_legacy = legacy.ObservedEvent(F.CRED_RESET, "e1", 1, 1, "u1", {"account": "a1"})
    assert dataclasses.asdict(ev_canon) == dataclasses.asdict(ev_legacy)


def test_no_public_symbol_disappeared():
    # The canonical full namespace must still expose the entire legacy surface.
    legacy_expected = {
        "SequenceRiskAnalyzer", "StoryGraph", "story_match", "story_evaluate",
        "evaluate_proposed_action", "to_advisory_evidence", "PolicyBinding",
        "ACCOUNT_TAKEOVER_TRANSFER", "DIGITAL_ONTOLOGY", "FINANCIAL_ONTOLOGY",
        "OBSERVE", "ESCALATE", "UNAVAILABLE",
    }
    assert legacy_expected <= set(canon.__all__)
