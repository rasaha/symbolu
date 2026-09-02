"""§11 constructor refusals: rows R1–R20 and R50, each with the named code."""

from __future__ import annotations

from datetime import datetime

import pytest

import matrix_fixtures as fx
from ugence_governance_contracts.api import AttestationStatus
from ugence_reasoning_method_governance.api import (
    COMPARISON_RESULT_SCHEMA_VERSION,
    ArtifactRef,
    ContractError,
    ContractErrorCode as E,
    CountBasis,
    ExecutionTelemetry,
    ImplementationEvidence,
    ImplementationEvidenceKind,
    ImplementationStatus,
    ReadinessComparisonResult,
    ReasoningMethodCatalog,
    ReasoningMethodCatalogRef,
    ReasoningMethodEntry,
    ReasoningMethodRef,
    ResourceDimension,
    TaskReversibility,
    TokenUsageSnapshot,
    UsageAvailabilityToken,
    ConsequenceClass,
)


def refuses(code, fn):
    with pytest.raises(ContractError) as ei:
        fn()
    assert ei.value.code is code, f"expected {code.value}, got {ei.value.code.value}: {ei.value.detail}"


def test_r1_blank_method_id():
    refuses(E.REF_BLANK_FIELD, lambda: ReasoningMethodRef(fx.c1_catalog_ref(), "", "1"))


def test_r2_short_digest():
    refuses(E.DIGEST_MALFORMED, lambda: ReasoningMethodCatalogRef("cat.rm", "1", "a" * 63))


def test_r3_duplicate_entries():
    e = fx.c3_entry()
    refuses(E.CATALOG_DUPLICATE_ENTRY, lambda: ReasoningMethodCatalog(fx.CATALOG_SCHEMA_VERSION, "cat.rm", "1", (e, e), "issuer", fx.NOW))


def test_r4_unsorted_entries():
    entries = (fx.c3_entry("tree_of_thought"), fx.c3_entry("debate"))
    refuses(E.CATALOG_UNSORTED, lambda: ReasoningMethodCatalog(fx.CATALOG_SCHEMA_VERSION, "cat.rm", "1", entries, "issuer", fx.NOW))


def test_r5_unknown_signal_token():
    refuses(E.SIGNAL_TOKEN_UNKNOWN, lambda: fx.c3_entry(signals=("not_a_signal",)))


def test_r6_scalar_label_field_on_subclass_refused_at_class_definition():
    with pytest.raises(ContractError) as ei:

        class Priced(ReasoningMethodEntry):  # noqa: D401 — deliberately invalid
            cost: str = ""

    assert ei.value.code is E.SCALAR_LABEL_FIELD_PRESENT


def test_r7_declared_status_refused():
    refuses(
        E.STATUS_DECLARED_NOT_DERIVED,
        lambda: ReasoningMethodEntry("x", "1", "X", (), (), (), implementation_status="EXECUTABLE_TESTED"),
    )


def test_r8_tests_alone_are_not_execution_evidence():
    only_tests = (ImplementationEvidence(ImplementationEvidenceKind.UNIT_TESTS_PRESENT, "tests", fx.NOW),)
    assert fx.c3_entry(evidence=only_tests).implementation_status is ImplementationStatus.NO_IMPLEMENTATION_EVIDENCE


def test_r9_undetermined_reversibility_on_class():
    refuses(E.REVERSIBILITY_UNDETERMINED_ON_CLASS, lambda: fx.c10_class(reversibility=TaskReversibility.UNDETERMINED))


def test_r10_high_consequence_threshold_only_without_admission_ref():
    refuses(E.ADMISSION_REF_REQUIRED, lambda: fx.c10_class(policy=fx.c8_policy(rule=fx.c6_rule()), consequence=ConsequenceClass.SEVERE))


def test_r11_dimensions_empty():
    refuses(E.DIMENSIONS_EMPTY, lambda: fx.c8_policy(dims=()))


def test_r12_dimensions_unsorted():
    refuses(E.DIMENSIONS_UNSORTED, lambda: fx.c8_policy(dims=(ResourceDimension.TOTAL_TOKENS, ResourceDimension.LLM_CALLS)))


def test_r13_calls_none_with_counted_basis():
    refuses(E.TELEMETRY_INVARIANT, lambda: fx.c12_telemetry(calls=None, basis=CountBasis.INJECTED_COUNTER))


def test_r14_available_without_snapshot():
    refuses(
        E.TELEMETRY_INVARIANT,
        lambda: ExecutionTelemetry(4, CountBasis.INJECTED_COUNTER, UsageAvailabilityToken.AVAILABLE, None, CountBasis.PROVIDER_REPORTED, 12),
    )


def test_r14b_snapshot_without_available():
    refuses(
        E.TELEMETRY_INVARIANT,
        lambda: ExecutionTelemetry(4, CountBasis.INJECTED_COUNTER, UsageAvailabilityToken.UNAVAILABLE_UNKNOWN, TokenUsageSnapshot(total_tokens=1), CountBasis.PROVIDER_REPORTED, 12),
    )


def test_r15_negative_calls():
    refuses(E.TELEMETRY_INVARIANT, lambda: fx.c12_telemetry(calls=-1))


def test_r16_unknown_artifact_kind():
    refuses(E.ARTIFACT_KIND_UNKNOWN, lambda: ArtifactRef("REASONING_TRACE", "trace", fx.HEX_A))


def test_r17_unparseable_self_reported_quality():
    refuses(E.DECIMAL_UNPARSEABLE, lambda: fx.c15_record(self_quality="high"))


def test_r18_naive_captured_at():
    refuses(E.DATETIME_NAIVE, lambda: fx.c15_record(captured_at=datetime(2026, 9, 2)))


def _kwargs(record):
    import dataclasses

    return {f.name: getattr(record, f.name) for f in dataclasses.fields(record)}


def test_r19_self_referential_lineage():
    r = fx.c15_record()
    kwargs = _kwargs(r)
    kwargs["parent_record_digest"] = r.record_digest  # names itself as its own parent
    refuses(E.LINEAGE_SELF_REFERENCE, lambda: type(r)(**kwargs))
    # A child naming a real parent is lineage, not self-reference.
    assert fx.c16_child(r).parent_record_digest == r.record_digest


def test_r20_evidence_axis_set_by_producer():
    r = fx.c15_record()
    kwargs = _kwargs(r)
    kwargs["attestation_status"] = AttestationStatus.ATTESTED
    with pytest.raises(ContractError) as ei:
        type(r)(**kwargs)
    assert ei.value.code is E.EVIDENCE_AXIS_SET_BY_PRODUCER


def test_r50_assessment_not_bound_to_engine():
    from ugence_reasoning_method_governance.api import (
        EVIDENCE_STATUS_SOURCE_V1,
        FIT_SCHEMA_VERSION,
        USAGE_SCOPE_RESEARCH_ONLY,
        AUTHORITY_RESOLUTION_BASIS_V1,
        FitOutcome,
        ReasoningMethodFitAssessment,
    )

    tc = fx.c10_class()
    hand_built = ReasoningMethodFitAssessment(
        FIT_SCHEMA_VERSION, "a.1", tc.task_class_id, tc.task_class_digest, fx.HEX_D, "", fx.c2_ref(), fx.c2_ref("linear_chain"),
        FitOutcome.COMPARISON_EVIDENCE_ABSENT, None, None, (), (), (ResourceDimension.LLM_CALLS,), "pol.cmp", "1", "",
        (), EVIDENCE_STATUS_SOURCE_V1, USAGE_SCOPE_RESEARCH_ONLY, "someone-else", "0.1.0", fx.NOW, "hand built",
    )
    refuses(
        E.ASSESSOR_ENGINE_MISMATCH,
        lambda: ReadinessComparisonResult(
            COMPARISON_RESULT_SCHEMA_VERSION, "req.1", fx.HEX_A, (hand_built,), (), (), (), AUTHORITY_RESOLUTION_BASIS_V1,
            "ugence-readiness-comparison", "0.1.0", fx.NOW,
        ),
    )
