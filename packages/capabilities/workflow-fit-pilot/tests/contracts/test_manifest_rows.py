"""§8 rows A1–A6: manifest shape and pre-execution validation."""

from __future__ import annotations

import dataclasses

import pytest

import matrix_fixtures as fx
import pilot_fixtures as pf
import rule_fixtures as rf
from ugence_reasoning_method_governance.api import ContractError, ReasoningMethodRef
from ugence_workflow_fit_pilot.api import CaptureBoundaryDeclaration, PilotError, PilotErrorCode as E, PilotMethodAssignment, PilotRole, ValidatedManifest, validate_manifest


def refuses(code, fn):
    with pytest.raises(PilotError) as ei:
        fn()
    assert ei.value.code is code, f"expected {code.value}, got {ei.value.code.value}: {ei.value.detail}"


def _with_roles(adv, method_id, roles):
    out = []
    for a in pf.assignments(adv):
        out.append(PilotMethodAssignment(a.method, roles) if a.method.method_id == method_id else a)
    return tuple(out)


def test_a1_baseline_role_consistency():
    adv = pf.advisory()
    refuses(E.ROLE_INCONSISTENT, lambda: pf.manifest(adv=adv, methods=_with_roles(adv, "linear_chain", (PilotRole.CHALLENGER,))))
    refuses(E.ROLE_INCONSISTENT, lambda: pf.manifest(adv=adv, methods=_with_roles(adv, "debate", (PilotRole.GOVERNED_BASELINE, PilotRole.CHALLENGER))))
    two = tuple(PilotMethodAssignment(a.method, (PilotRole.GOVERNED_BASELINE,) + a.roles if a.method.method_id == "debate" else a.roles) for a in pf.assignments(adv))
    refuses(E.ROLE_INCONSISTENT, lambda: pf.manifest(adv=adv, methods=two))


def test_a2_advisory_required_and_empty_qualifying_set_constructs():
    adv = pf.advisory()
    m = pf.manifest(adv=adv)
    refuses(E.ADVISORY_REQUIRED, lambda: dataclasses.replace(m, advisory_digest=None, rule_set=None, manifest_digest=""))
    refuses(E.ADVISORY_REQUIRED, lambda: dataclasses.replace(m, advisory_digest=None, manifest_digest=""))
    refuses(E.ADVISORY_REQUIRED, lambda: validate_manifest(m, catalog=pf.catalog(), rule_set=pf.rule_set()))
    # Empty qualifying set: the profile carries no tokens, the advisory qualifies nothing, the manifest
    # still records the advisory digest and validates with both sets empty.
    tc = pf.task_class(tokens=())
    empty = pf.advisory(tc, tokens=())
    assert empty.qualifying == ()
    m0 = pf.manifest(adv=empty, tc=tc, methods=pf.assignments(empty))
    assert m0.advisory_digest == empty.advisory_digest and not m0.methods_with_role(PilotRole.ADVISOR_QUALIFIED)
    v = validate_manifest(m0, catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=empty)
    assert isinstance(v, ValidatedManifest) and v.advisory_digest == empty.advisory_digest


def test_a3_duplicate_method_and_attested_field_allow_set():
    adv = pf.advisory()
    dup = pf.assignments(adv) + (pf.assignments(adv)[0],)
    refuses(E.METHOD_DUPLICATE, lambda: pf.manifest(adv=adv, methods=tuple(sorted(dup, key=lambda a: a.method.sort_key))))
    refuses(E.ATTESTED_FIELDS_INVALID, lambda: CaptureBoundaryDeclaration("b", "0", "sep", "port", ("telemetry.duration_ms",)))
    refuses(E.ATTESTED_FIELDS_INVALID, lambda: CaptureBoundaryDeclaration("b", "0", "sep", "port", ("telemetry.token_usage.total_tokens",)))
    refuses(E.ATTESTED_FIELDS_INVALID, lambda: CaptureBoundaryDeclaration("b", "0", "sep", "port", ("telemetry.llm_calls", "telemetry.llm_calls")))


def test_a4_benchmark_manifest_must_equal_task_class_benchmark_set_digest():
    other = pf.benchmark(extra_case="f" * 64)
    refuses(E.BENCHMARK_MANIFEST_MISMATCH, lambda: pf.manifest(bm=other, tc=pf.task_class(pf.benchmark())))


def test_a5_benchmark_manifest_shape():
    from ugence_governance_contracts.api import BenchmarkReference
    from ugence_workflow_fit_pilot.api import BENCHMARK_MANIFEST_SCHEMA_VERSION, BenchmarkManifest, case_list_digest

    good = pf.benchmark()
    ds = good.case_digests
    head = lambda d: BenchmarkReference("b", "1", case_list_digest(d), "issuer")
    with pytest.raises(ContractError):
        BenchmarkManifest(BENCHMARK_MANIFEST_SCHEMA_VERSION, head(tuple(reversed(ds))), tuple(reversed(ds)), len(ds), "i", pf.NOW)
    with pytest.raises(ContractError):
        BenchmarkManifest(BENCHMARK_MANIFEST_SCHEMA_VERSION, head(ds + (ds[0],)), ds + (ds[0],), len(ds) + 1, "i", pf.NOW)
    with pytest.raises(ContractError):
        BenchmarkManifest(BENCHMARK_MANIFEST_SCHEMA_VERSION, head(()), (), 0, "i", pf.NOW)
    refuses(E.COUNT_INVALID, lambda: BenchmarkManifest(BENCHMARK_MANIFEST_SCHEMA_VERSION, head(ds), ds, len(ds) + 1, "i", pf.NOW))
    refuses(E.COUNT_INVALID, lambda: BenchmarkManifest(BENCHMARK_MANIFEST_SCHEMA_VERSION, head(ds), ds, 0, "i", pf.NOW))
    refuses(E.BENCHMARK_HEAD_MISMATCH, lambda: BenchmarkManifest(BENCHMARK_MANIFEST_SCHEMA_VERSION, BenchmarkReference("b", "1", "0" * 64, "issuer"), ds, len(ds), "i", pf.NOW))


def test_a6_validate_manifest_proves_composition_against_catalog_rule_set_and_advisory():
    adv = pf.advisory()
    m = pf.manifest(adv=adv)
    cat, rs = pf.catalog(), pf.rule_set()
    v = validate_manifest(m, catalog=cat, rule_set=rs, advisory=adv)
    assert v.manifest_digest == m.manifest_digest and len(v.admissible_methods) == 7
    other_adv = pf.advisory(tokens=("comparison_request",))  # different qualifying set
    refuses(E.ADVISORY_MISMATCH, lambda: validate_manifest(m, catalog=cat, rule_set=rs, advisory=other_adv))
    refuses(E.RULE_SET_MISMATCH, lambda: validate_manifest(m, catalog=cat, rule_set=rf.research_rules_v0(version="1"), advisory=adv))
    from ugence_reasoning_method_governance.api import CATALOG_SCHEMA_VERSION, ReasoningMethodCatalog

    smaller = ReasoningMethodCatalog(CATALOG_SCHEMA_VERSION, "cat.rm", "1", fx.c4_catalog().entries[:6], "issuer:test", fx.NOW)
    refuses(E.CATALOG_MISMATCH, lambda: validate_manifest(m, catalog=smaller, rule_set=rs, advisory=adv))
    # a manifest missing one admissible method fails composition (constructed by dropping a challenger)
    dropped = tuple(a for a in pf.assignments(adv) if a.method.method_id != "metacognitive")
    m2 = pf.manifest(adv=adv, methods=dropped)
    refuses(E.COMPOSITION_INCOMPLETE, lambda: validate_manifest(m2, catalog=cat, rule_set=rs, advisory=adv))
    # a CHALLENGER role on a qualified method
    m3 = pf.manifest(adv=adv, methods=_with_roles(adv, "map_reduce", (PilotRole.ADVISOR_QUALIFIED, PilotRole.CHALLENGER)))
    refuses(E.COMPOSITION_INCOMPLETE, lambda: validate_manifest(m3, catalog=cat, rule_set=rs, advisory=adv))
    with pytest.raises(TypeError):
        validate_manifest(m, catalog=cat, rule_set=None, advisory=adv)  # type: ignore[arg-type]
    # the validated artifact's digest changes with any input
    v2 = validate_manifest(pf.manifest(adv=adv, manifest_id="manifest.other"), catalog=cat, rule_set=rs, advisory=adv)
    assert v2.validation_digest != v.validation_digest
