"""H2 — evidence-synthesis tests."""

from __future__ import annotations

import pytest

from ugence_ai_hiring.errors import (
    CrossTenantHiringAccessError,
    ProhibitedAttributeError,
    StaleRubricVersionError,
)
from ugence_ai_hiring.intake.intake import EvidenceProvenance, IntakeSource
from ugence_ai_hiring.synthesis import MinimizationPolicy
from .h2_helpers import application_in_assessment, build_h2_env, sysctx


def test_synthesis_bounds_and_records_exact_evidence_set():
    env = build_h2_env(); c = sysctx()
    application_in_assessment(env, c)
    pkg = env.synthesis_service.synthesize(c, application_id="a1", rubric_version=1)
    assert pkg.evidence_refs == ("intk_code_sample", "intk_resume")
    assert not pkg.missing_evidence_types
    assert pkg.job_definition_version >= 1 and pkg.rubric_version == 1


def test_synthesis_is_deterministic_for_same_inputs():
    env = build_h2_env(); c = sysctx()
    application_in_assessment(env, c)
    p1 = env.synthesis_service.synthesize(c, application_id="a1", rubric_version=1)
    p2 = env.synthesis_service.synthesize(c, application_id="a1", rubric_version=1)
    assert p1.fingerprint == p2.fingerprint


def test_synthesis_detects_missing_evidence():
    env = build_h2_env(); c = sysctx()
    application_in_assessment(env, c, required=("resume", "code_sample"), provided=("resume",))
    # application stays in SCREENING (incomplete); synthesis still reports the gap
    pkg = env.synthesis_service.synthesize(c, application_id="a1", rubric_version=1)
    assert pkg.missing_evidence_types == ("code_sample",)


def test_stale_rubric_version_fails_safe():
    env = build_h2_env(); c = sysctx()
    application_in_assessment(env, c)
    with pytest.raises(StaleRubricVersionError):
        env.synthesis_service.synthesize(c, application_id="a1", rubric_version=2)


def test_prohibited_attribute_supply_rejected():
    env = build_h2_env(); c = sysctx()
    application_in_assessment(env, c)
    with pytest.raises(ProhibitedAttributeError):
        env.synthesis_service.synthesize(
            c, application_id="a1", rubric_version=1, supplied_attribute_keys=("age", "skills"))


def test_quarantined_evidence_excluded_and_reported():
    env = build_h2_env(); c = sysctx()
    application_in_assessment(env, c)
    policy = MinimizationPolicy(quarantined_hashes=("hash_code_sample",))
    pkg = env.synthesis_service.synthesize(c, application_id="a1", rubric_version=1, policy=policy)
    assert "intk_code_sample" in pkg.quarantined_refs
    assert "code_sample" in pkg.missing_evidence_types  # quarantined does not count as coverage


def test_adverse_evidence_never_omitted_under_minimization():
    env = build_h2_env(); c = sysctx()
    application_in_assessment(env, c, required=("resume",), provided=("resume", "code_sample"))
    # limit to 1 item, but mark the extra as adverse — it must be retained
    policy = MinimizationPolicy(max_items=1)
    pkg = env.synthesis_service.synthesize(
        c, application_id="a1", rubric_version=1, policy=policy, adverse_refs=("intk_code_sample",))
    assert pkg.minimization_applied
    assert any(i.adverse and i.evidence_ref == "intk_code_sample" for i in pkg.items)


def test_synthesis_tenant_isolation():
    env = build_h2_env()
    owner, intruder = sysctx(tenant="t1"), sysctx(tenant="t2")
    application_in_assessment(env, owner)
    with pytest.raises(CrossTenantHiringAccessError):
        env.synthesis_service.synthesize(intruder, application_id="a1", rubric_version=1)
