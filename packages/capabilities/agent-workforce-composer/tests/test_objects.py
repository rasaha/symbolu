"""Object-integrity tests (§24 — Object integrity)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from ugence_agent_workforce_composer.agents import (
    AgentProfile,
    build_registry_snapshot,
)
from ugence_agent_workforce_composer.workflow import Provenance
from ._helpers import NOW, SYNTH, make_evidence, make_profile, make_snapshot


def test_models_are_frozen():
    p = make_profile()
    with pytest.raises((ValidationError, TypeError, AttributeError)):
        p.agent_id = "mutated"


def test_unknown_fields_rejected():
    with pytest.raises(ValidationError):
        AgentProfile(agent_id="a", agent_version="1.0.0", provider_id="anthropic",
                     provenance=SYNTH, not_a_real_field=123)


def test_duplicate_agent_identity_rejected():
    p1 = make_profile("dup", "1.0.0")
    p2 = make_profile("dup", "1.0.0")
    with pytest.raises(ValueError):
        build_registry_snapshot(snapshot_id="s", registry_version="v", logical_time=NOW,
                                agent_profiles=[p1, p2], capability_evidence=[], provenance=SYNTH)


def test_duplicate_evidence_id_rejected():
    p = make_profile("a", "1.0.0")
    e = make_evidence("a", "1.0.0", "evidence_extraction", "MEASURED")
    with pytest.raises(ValueError):
        build_registry_snapshot(snapshot_id="s", registry_version="v", logical_time=NOW,
                                agent_profiles=[p], capability_evidence=[e, e], provenance=SYNTH)


def test_unresolved_evidence_reference_rejected():
    p = make_profile("a", "1.0.0")
    e = make_evidence("ghost", "9.9.9", "evidence_extraction", "MEASURED")
    with pytest.raises(ValueError):
        build_registry_snapshot(snapshot_id="s", registry_version="v", logical_time=NOW,
                                agent_profiles=[p], capability_evidence=[e], provenance=SYNTH)


def test_snapshot_digest_stable_under_ordering():
    profiles = [make_profile("a", "1.0.0"), make_profile("b", "1.0.0"), make_profile("c", "1.0.0")]
    ev = [make_evidence("a", "1.0.0", "evidence_extraction", "MEASURED"),
          make_evidence("b", "1.0.0", "evidence_extraction", "MEASURED")]
    s1 = make_snapshot(profiles, ev)
    s2 = make_snapshot(list(reversed(profiles)), list(reversed(ev)))
    assert s1.snapshot_digest == s2.snapshot_digest
    assert s1.snapshot_digest == s1.logical_digest()


def test_changing_a_profile_changes_the_digest():
    base = make_snapshot([make_profile("a", "1.0.0")], [])
    changed = make_snapshot([make_profile("a", "1.0.0", security_classification=1)], [])
    assert base.snapshot_digest != changed.snapshot_digest


def test_content_digest_and_fingerprints_present():
    p = make_profile()
    assert p.content_digest().startswith("sha256:")
    snap = make_snapshot([p], [])
    assert snap.snapshot_digest.startswith("sha256:")
