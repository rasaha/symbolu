"""§8 rows A7–A11, A16 (validation side), A19 (labels), and the evaluator rows A20."""

from __future__ import annotations

import dataclasses
from datetime import timedelta

import pytest

import pilot_fixtures as pf
from ugence_governance_contracts.api import MetricClaim, SourceBasis, TransformationMethod
from ugence_reasoning_method_governance.api import AttestationEnvelope, QualityResult
from ugence_workflow_fit_pilot.api import (
    EvaluatorKind,
    PilotError,
    PilotErrorCode as E,
    PilotObservation,
    QualityEvaluationRecord,
    QualityEvaluatorDeclaration,
    ValidatedManifest,
    render,
    run_pilot,
    validate_observation,
)


def refuses(code, fn):
    with pytest.raises(PilotError) as ei:
        fn()
    assert ei.value.code is code, f"expected {code.value}, got {ei.value.code.value}: {ei.value.detail}"


@pytest.fixture(scope="module")
def pilot():
    m = pf.manifest()
    adv = pf.advisory(m.plan.task_class)
    res = run_pilot(m, catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=adv, cases=pf.cases(), executor=pf.FakeExecutor(pf.DEFAULT_CALLS), scorer=pf.KeywordScorer(),
                    identity=pf.IDENTITY, provider_factory="stub_provider:make_provider", now=pf.clock(), boundary_env=pf.boundary_env())
    return m, adv, res


def _objs(pilot, method_id="map_reduce"):
    m, adv, res = pilot
    run = next(r for r in res.runs if r.method.method_id == method_id)
    return dict(observation=run.observation, validated=res.validated, manifest=m, plan=m.plan, record=run.record, benchmark=m.benchmark, evaluation=run.evaluation,
                quality_claim=run.quality_claim, quality_result=run.quality_result, advisory=adv, attestation=run.attestation)


def _re(obs, **patch):
    kw = {f.name: getattr(obs, f.name) for f in dataclasses.fields(obs) if f.name != "observation_digest"}
    kw.update(patch)
    return PilotObservation(**kw)


def test_a7_manifest_mismatch_and_not_prior(pilot):
    o = _objs(pilot)
    validate_observation(**o)
    other = pf.manifest(manifest_id="manifest.other")
    refuses(E.MANIFEST_NOT_VALIDATED, lambda: validate_observation(**{**o, "manifest": other, "plan": other.plan}))
    refuses(E.MANIFEST_MISMATCH, lambda: validate_observation(**{**o, "observation": _re(o["observation"], manifest_digest="a" * 64)}))
    early = pf.NOW - timedelta(days=1)  # an observation instant before the manifest's preregistration
    refuses(E.MANIFEST_NOT_PRIOR, lambda: validate_observation(**{**o, "observation": _re(o["observation"], observed_at=early)}))
    assert "preregistration_status=DECLARED_UNVERIFIED" in render(pilot[2])


def test_a8_benchmark_case_set_mismatch(pilot):
    o = _objs(pilot)
    refuses(E.BENCHMARK_MANIFEST_MISMATCH, lambda: validate_observation(**{**o, "observation": _re(o["observation"], case_set_digest="b" * 64)}))
    refuses(E.BENCHMARK_MANIFEST_MISMATCH, lambda: validate_observation(**{**o, "observation": _re(o["observation"], case_count=o["observation"].case_count + 1)}))


def test_a9_roles_and_advisory_membership(pilot):
    from ugence_workflow_fit_pilot.api import PilotRole

    o = _objs(pilot)
    refuses(E.ROLE_INCONSISTENT, lambda: validate_observation(**{**o, "observation": _re(o["observation"], roles=(PilotRole.CHALLENGER,))}))
    refuses(E.ADVISORY_REQUIRED, lambda: validate_observation(**{**o, "advisory": None}))
    other = pf.advisory(tokens=("causal_reasoning",))
    refuses(E.ADVISORY_MISMATCH, lambda: validate_observation(**{**o, "advisory": other}))


def test_a10_omission_or_record_mismatch_never_passes(pilot):
    o = _objs(pilot)
    for name in ("validated", "manifest", "plan", "record", "benchmark", "evaluation", "quality_claim", "quality_result"):
        with pytest.raises(TypeError):
            validate_observation(**{**o, name: None})
    other = _objs(pilot, "debate")
    refuses(E.RECORD_MISMATCH, lambda: validate_observation(**{**o, "record": other["record"]}))
    refuses(E.RECORD_MISMATCH, lambda: validate_observation(**{**o, "observation": _re(o["observation"], model_ref="model:other")}))
    refuses(E.MANIFEST_NOT_VALIDATED, lambda: validate_observation(**{**o, "validated": dataclasses.replace(o["validated"], advisory_digest="c" * 64, validation_digest="")}))


def test_a11_quality_evaluation_and_result_binding(pilot):
    o = _objs(pilot)
    ev = o["evaluation"]
    for patch in ({"evaluator_declaration_digest": "d" * 64}, {"scoring_instruction_digest": "d" * 64}, {"evaluated_by": "someone-else"}, {"claim_digest": "d" * 64}):
        bad = dataclasses.replace(ev, evaluation_digest="", **patch)
        refuses(E.QUALITY_EVALUATION_MISMATCH, lambda: validate_observation(**{**o, "evaluation": bad, "observation": _re(o["observation"], quality_evaluation_digest=bad.evaluation_digest)}))
    claim = o["quality_claim"]
    no_ref = dataclasses.replace(claim, evidence_refs=("unrelated",))
    refuses(E.QUALITY_EVALUATION_MISMATCH, lambda: validate_observation(**{**o, "quality_claim": no_ref}))
    qr = o["quality_result"]
    refuses(E.QUALITY_RESULT_MISMATCH, lambda: validate_observation(**{**o, "quality_result": QualityResult(qr.method, qr.claim_ref, qr.governed_unit, "0.1", qr.aggregation)}))
    refuses(E.QUALITY_RESULT_MISMATCH, lambda: validate_observation(**{**o, "quality_result": QualityResult(qr.method, "other-claim", qr.governed_unit, qr.value, qr.aggregation)}))
    assert claim.source_basis is SourceBasis.REPORTED and claim.transformation_method is TransformationMethod.CALCULATED


def test_a16_attestation_validation_side(pilot):
    o = _objs(pilot)
    att = o["attestation"]
    def env(**patch):
        kw = {f.name: getattr(att, f.name) for f in dataclasses.fields(att) if f.name != "envelope_digest"}
        kw.update(patch)
        e = AttestationEnvelope(**kw)
        return {**o, "attestation": e, "observation": _re(o["observation"], attestation_envelope_digest=e.envelope_digest)}
    refuses(E.ATTESTATION_MISMATCH, lambda: validate_observation(**env(attested_fields=("telemetry.duration_ms",))))
    refuses(E.ATTESTATION_MISMATCH, lambda: validate_observation(**env(attested_fields=("telemetry.token_usage.total_tokens",))))
    refuses(E.ATTESTATION_MISMATCH, lambda: validate_observation(**env(record_digest="e" * 64)))
    refuses(E.ATTESTATION_MISMATCH, lambda: validate_observation(**env(capture_boundary_ref="e" * 64)))
    refuses(E.ATTESTATION_MISMATCH, lambda: validate_observation(**env(attester_identity="someone-else")))
    refuses(E.ATTESTATION_MISMATCH, lambda: validate_observation(**{**o, "attestation": None}))


def test_a19_every_field_unverified_and_every_judgment_labelled(pilot):
    m, adv, res = pilot
    assert all(v.verification_status.value == "UNVERIFIED" for v in res.result.evidence_status)
    text = render(res)
    low = text.lower()
    assert "verified=" not in low.replace("verification=unverified", "") and " trusted" not in low
    for line in text.splitlines():
        if "quality=" in line:
            assert "independence_status=DECLARED_UNVERIFIED" in line and "calibration_blank=" in line
        if any(f": {o}" in line for o in ("INSUFFICIENT_QUALITY", "SUFFICIENT_RESOURCE_DOMINATED", "SUFFICIENT_PARETO_EFFICIENT", "COMPARISON_EVIDENCE_ABSENT")):
            assert "[RESEARCH_ONLY" in line and "non-authoritative" in line


def test_a20_evaluator_kind_self_loop_and_shared_model():
    refuses(E.EVALUATOR_KIND_INCONSISTENT, lambda: pf.evaluator_decl(kind=EvaluatorKind.LLM))
    refuses(E.EVALUATOR_KIND_INCONSISTENT, lambda: pf.evaluator_decl(kind=EvaluatorKind.HUMAN, model_ref="model:x"))
    llm = pf.evaluator_decl(kind=EvaluatorKind.LLM, model_ref="model:stub")
    assert llm.model_ref == "model:stub" and llm.independence_status == "DECLARED_UNVERIFIED"
    from ugence_workflow_fit_pilot.contracts.evaluator import INDEPENDENCE_DECLARED_UNVERIFIED
    from ugence_reasoning_method_governance.api import ContractError

    with pytest.raises(ContractError):
        dataclasses.replace(llm, independence_status="INDEPENDENT", declaration_digest="")
    # self-loop and shared-model checks are applied by the runner's identity policy: an evaluator
    # identity equal to the record issuer, requester or boundary is refused before any run.
    from ugence_workflow_fit_pilot.runner import check_evaluator_identity

    refuses(E.EVALUATOR_SELF_LOOP, lambda: check_evaluator_identity(pf.evaluator_decl(identity="requester:pilot"), pf.IDENTITY, "boundary:pilot-gateway"))
    refuses(E.EVALUATOR_SELF_LOOP, lambda: check_evaluator_identity(pf.evaluator_decl(identity="boundary:pilot-gateway"), pf.IDENTITY, "boundary:pilot-gateway"))
    assert check_evaluator_identity(llm, pf.IDENTITY, "boundary:pilot-gateway") == ("EVALUATOR_SHARES_MODEL",)
    assert check_evaluator_identity(pf.evaluator_decl(), pf.IDENTITY, "boundary:pilot-gateway") == ()
