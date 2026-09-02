"""§11 rows C1–C24 (constructible examples) and R41 (digest stability).

Every example constructs, and every self-digesting object yields the same
digest across two independent constructions while any field change yields a
different one.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

import matrix_fixtures as fx
from ugence_governance_contracts.api import AttestationStatus, SourceBasis, VerificationStatus
from ugence_reasoning_method_governance.api import (
    ConsequenceClass,
    ImplementationStatus,
    ReasoningMethodExecutionRecord,
    ResourceDimension,
    TaskReversibility,
    compatible,
)


def test_c1_c2_refs():
    ref = fx.c2_ref()
    assert ref.catalog == fx.c1_catalog_ref()
    assert ref.sort_key == ("tree_of_thought", "1")


def test_c3_entry_status_derives_to_executable_tested():
    assert fx.c3_entry().implementation_status is ImplementationStatus.EXECUTABLE_TESTED


def test_c4_catalog_seven_entries_and_refs():
    cat = fx.c4_catalog()
    assert len(cat.entries) == 7
    assert [e.method_id for e in cat.entries] == sorted(fx.SEVEN_METHODS)
    assert all(e.implementation_status is ImplementationStatus.EXECUTABLE_TESTED for e in cat.entries)
    ref = cat.ref()
    assert ref.catalog_digest == cat.catalog_digest
    assert cat.method_ref("debate", "1").catalog == ref


def test_c5_vocabularies_by_value():
    assert {m.value for m in TaskReversibility} == {"OUTCOME_REVERSIBLE", "OUTCOME_COMPENSATABLE", "OUTCOME_IRREVERSIBLE", "UNDETERMINED"}
    assert {m.value for m in ConsequenceClass} == {"NEGLIGIBLE", "RECOVERABLE", "MATERIAL", "SEVERE"}


def test_c6_c7_c8_c24_policy_objects():
    assert fx.c6_rule().supporting_evidence_admission is None
    assert fx.c7_rule_hc().supporting_evidence_admission is not None
    assert fx.c8_policy().quality_aggregation is None
    assert fx.c24_policy_agg().quality_aggregation == fx.research_aggregation()


def test_c9_profile_allows_undetermined_and_reports():
    p = fx.c9_profile()
    assert p.assertion_basis == "DEVELOPER_REPORTED"
    from ugence_reasoning_method_governance.api import PROFILE_SCHEMA_VERSION, TaskProfile

    TaskProfile(PROFILE_SCHEMA_VERSION, "p2", "d", "o", ConsequenceClass.NEGLIGIBLE, TaskReversibility.UNDETERMINED, (), (), (), "pop")


def test_c10_c11_task_classes_and_compatibility():
    a, b = fx.c10_class(), fx.c10_class()
    assert compatible(a, b)
    hc = fx.c11_class_hc()
    assert hc.consequence_class is ConsequenceClass.SEVERE
    assert not compatible(a, hc)


def test_c12_c13_telemetry():
    assert fx.c12_telemetry().resource_value(ResourceDimension.LLM_CALLS) == 4
    assert fx.c12_telemetry().resource_value(ResourceDimension.TOTAL_TOKENS) is None
    assert fx.c13_telemetry_tokens().resource_value(ResourceDimension.TOTAL_TOKENS) == 812


def test_c14_binding():
    assert fx.c14_binding().binding_digest == fx.HEX_D


def test_c15_record_axes_are_constants():
    r = fx.c15_record()
    assert r.source_basis is SourceBasis.OBSERVED
    assert r.attestation_status is AttestationStatus.UNATTESTED
    assert r.verification_status is VerificationStatus.UNVERIFIED
    assert ReasoningMethodExecutionRecord.attestation_status is AttestationStatus.UNATTESTED
    import dataclasses

    assert "attestation_status" not in {f.name for f in dataclasses.fields(r)}


def test_c16_child_record_carries_lineage_only():
    parent = fx.c15_record()
    child = fx.c16_child(parent)
    assert child.parent_record_digest == parent.record_digest
    assert child.record_digest != parent.record_digest


def test_c17_c18_quality_results():
    assert fx.c17_quality().aggregation is None
    assert fx.c18_quality_agg().aggregation == fx.research_aggregation()


def test_c19_c20_envelopes():
    rec = fx.c15_record()
    att = fx.c19_attestation(rec)
    ver = fx.c20_verification(rec, att)
    assert att.record_digest == rec.record_digest
    assert ver.attestation_envelope_digest == att.envelope_digest


def test_c21_request_and_c23_plan_construct():
    req = fx.two_method_request()
    assert len(req.candidates) == 2 and len(req.records) == 2
    plan = fx.c23_plan()
    assert plan.recommended == () and plan.usage_scope == "RESEARCH_ONLY"


@pytest.mark.parametrize(
    "build",
    [
        lambda: fx.c4_catalog(),
        lambda: fx.c10_class(),
        lambda: fx.c11_class_hc(),
        lambda: fx.c15_record(),
        lambda: fx.c19_attestation(fx.c15_record()),
        lambda: fx.c20_verification(fx.c15_record(), fx.c19_attestation(fx.c15_record())),
        lambda: fx.c23_plan(),
    ],
)
def test_r41_digests_stable_across_constructions(build):
    a, b = build(), build()
    digest_field = next(f for f in a.__dataclass_fields__ if f.endswith("_digest") and getattr(a, f) and f not in ("record_digest_parent",) and f in ("catalog_digest", "task_class_digest", "record_digest", "envelope_digest", "plan_digest"))
    assert getattr(a, digest_field) == getattr(b, digest_field)


def test_r41_any_field_change_changes_digest():
    base = fx.c15_record()
    changed = fx.c15_record(captured_at=datetime(2026, 9, 3, tzinfo=timezone.utc))
    assert base.record_digest != changed.record_digest
    cls_a = fx.c10_class()
    cls_b = fx.c10_class(policy=fx.c8_policy(rule=fx.c6_rule(thr=fx.threshold(literal="0.8"))))
    assert cls_a.task_class_digest != cls_b.task_class_digest, "threshold content is inside the class digest (§3 digest payload rule)"


def test_supplied_digest_must_match_computed():
    from ugence_reasoning_method_governance.api import ContractError, ContractErrorCode

    import dataclasses

    r = fx.c15_record()
    kwargs = {f.name: getattr(r, f.name) for f in dataclasses.fields(r)}
    with pytest.raises(ContractError) as ei:
        ReasoningMethodExecutionRecord(**{**kwargs, "record_digest": fx.HEX_A})
    assert ei.value.code is ContractErrorCode.DIGEST_MALFORMED
    same = ReasoningMethodExecutionRecord(**kwargs)
    assert same.record_digest == r.record_digest
