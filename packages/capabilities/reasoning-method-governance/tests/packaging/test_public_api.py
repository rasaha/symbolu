"""The curated API resolves and the error vocabularies are exactly the §11 lists."""

from __future__ import annotations

import importlib

from ugence_reasoning_method_governance import api
from ugence_reasoning_method_governance.api import ContractErrorCode, RefusalCode

CONTRACT_CODES = {
    "REF_BLANK_FIELD", "DIGEST_MALFORMED", "CATALOG_DUPLICATE_ENTRY", "CATALOG_UNSORTED", "SIGNAL_TOKEN_UNKNOWN",
    "SCALAR_LABEL_FIELD_PRESENT", "STATUS_DECLARED_NOT_DERIVED", "REVERSIBILITY_UNDETERMINED_ON_CLASS",
    "ADMISSION_REF_REQUIRED", "DIMENSIONS_EMPTY", "DIMENSIONS_UNSORTED", "TELEMETRY_INVARIANT", "ARTIFACT_KIND_UNKNOWN",
    "DECIMAL_UNPARSEABLE", "DATETIME_NAIVE", "LINEAGE_SELF_REFERENCE", "EVIDENCE_AXIS_SET_BY_PRODUCER",
    "ASSESSOR_ENGINE_MISMATCH",
}
REFUSAL_CODES = {
    "UNSUPPORTED_SCHEMA_VERSION", "UNSUPPORTED_COMPARATOR", "UNIT_MISMATCH", "SCALE_UNSUPPORTED", "AGGREGATION_UNDECLARED",
    "RESOURCE_AGGREGATION_UNDECLARED", "DIMENSION_UNAVAILABLE", "TASK_CLASS_MISMATCH", "BASELINE_ABSENT",
    "METHOD_RECORDS_ABSENT", "QUALITY_RESULT_ABSENT", "QUALITY_CLAIM_NOT_INDEPENDENT", "THRESHOLD_UNRESOLVABLE",
    "THRESHOLD_ONLY_NOT_ADMITTED", "LINEAGE_UNRESOLVED", "SELF_ATTESTATION", "SELF_VERIFICATION",
    "VERIFICATION_WITHOUT_ATTESTATION", "ENVELOPE_ORPHAN", "CANDIDATES_EMPTY",
}


def test_all_exports_resolve():
    for name in api.__all__:
        assert hasattr(api, name), name


def test_error_vocabularies_match_spec():
    assert {m.value for m in ContractErrorCode} == CONTRACT_CODES
    assert {m.value for m in RefusalCode} == REFUSAL_CODES


def test_schema_version_literals():
    assert api.CATALOG_SCHEMA_VERSION == "reasoning_method.catalog.v1"
    assert api.TASK_CLASS_SCHEMA_VERSION == "reasoning_method.task_class.v1"
    assert api.RECORD_SCHEMA_VERSION == "reasoning_method.execution_record.v1"
    assert api.FIT_SCHEMA_VERSION == "reasoning_method.fit_assessment.v1"
    assert api.COMPARISON_REQUEST_SCHEMA_VERSION == "readiness_comparison.request.v1"
    assert api.COMPARISON_RESULT_SCHEMA_VERSION == "readiness_comparison.result.v1"
    assert api.RESEARCH_PLAN_SCHEMA_VERSION == "reasoning_method.research_plan.v1"


def test_fit_outcomes_are_exactly_the_ratified_four():
    assert [m.value for m in api.FitOutcome] == [
        "INSUFFICIENT_QUALITY", "SUFFICIENT_RESOURCE_DOMINATED", "SUFFICIENT_PARETO_EFFICIENT", "COMPARISON_EVIDENCE_ABSENT",
    ]


def test_no_numeric_defaults_in_any_contract_field():
    import dataclasses

    for name in api.__all__:
        obj = getattr(api, name)
        if isinstance(obj, type) and dataclasses.is_dataclass(obj):
            for f in dataclasses.fields(obj):
                if f.default is not dataclasses.MISSING:
                    assert f.default is None or f.default == () or isinstance(f.default, str), f"{name}.{f.name} default {f.default!r} is not an empty/None/string default"


def test_package_imports_cleanly():
    importlib.import_module("ugence_reasoning_method_governance")
