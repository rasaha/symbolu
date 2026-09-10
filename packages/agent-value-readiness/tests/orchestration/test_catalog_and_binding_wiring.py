"""M-3R.3 wiring: one binding, catalog-admitted indicators, fail-closed (§8, §9, §12).

Every test here asks the same adversarial question in a different shape: *can an
untrusted caller get something into a readiness assessment that does not belong
to the exact system, tenant, subject, context and governed vocabulary this
assessment is about?*

The two boundaries under test are deliberately different:

* **binding** failures are self-contradictions about *what is being assessed*, so
  they are ``NOT_EVALUATED`` — no headline of any kind exists;
* **catalog** failures exclude the offending indicator record and nothing else,
  because indicator records are diagnostics under the ratified precedence and an
  excluded one must influence readiness in no direction whatsoever.
"""

from __future__ import annotations

import hashlib

import pytest

from ugence_agent_value_readiness.api import (
    CapabilityReadinessCatalog,
    CapabilityReadinessIndicatorDefinition,
    IntelligenceDimension,
    IntelligenceFitnessCatalog,
    IntelligenceFitnessIndicatorDefinition,
    GateStatus,
    ReadinessAssessmentStatus,
    ReadinessClassification,
    ReadinessIndicatorAdmissionStatus,
    ReadinessIndicatorCatalogSet,
    ReadinessIndicatorClass,
    ReadinessTrustGapCode,
    assess_readiness,
)

from _orchestration_fixtures import (  # noqa: E402
    BOTH,
    CONFIG_DIGEST_B,
    MANDATORY,
    StubConditionVerifier,
    StubGateVerifier,
    binding,
    catalogs,
    context,
    gate,
    gate_result,
    indicators,
    issued_resolver,
    readiness_policy,
    request,
)

_G = ReadinessTrustGapCode
_I = ReadinessIndicatorAdmissionStatus


def _wired(req, policy):
    return assess_readiness(
        req,
        policy_resolver=issued_resolver(policy),
        gate_verifier=StubGateVerifier(),
        condition_verifier=StubConditionVerifier(),
    )


def _passing_policy():
    return readiness_policy(gates=(gate("g1", MANDATORY, BOTH),))


def _passing_gates(policy):
    return (gate_result(policy, "g1", GateStatus.PASS),)


def _outcome(**kwargs):
    policy = kwargs.pop("policy", None) or _passing_policy()
    req = request(policy=policy, gate_results=_passing_gates(policy), **kwargs)
    return _wired(req, policy), req


# --------------------------------------------------------------------------- #
# The happy path: one binding, three catalogs, three admitted indicators
# --------------------------------------------------------------------------- #
def test_a_bound_catalogued_assessment_evaluates_and_admits_every_indicator():
    outcome, _ = _outcome(with_indicators=True)

    assert outcome.status is ReadinessAssessmentStatus.EVALUATED
    assert outcome.classification is ReadinessClassification.DEPLOYMENT_READY
    assert outcome.system_binding_accepted is True
    assert outcome.trace.system_binding_ref == "bind-1"
    assert outcome.trace.system_binding_digest
    assert outcome.trace.admitted_indicator_result_ids == ("ar1", "cr1", "ir1")
    assert outcome.trace.excluded_indicator_result_ids == ()
    assert all(s.admitted for s in outcome.indicator_admissions)
    assert {s.admission_status for s in outcome.indicator_admissions} == {_I.ADMITTED}
    assert outcome.trace.catalog_families_bound == ("INTELLIGENCE", "CAPABILITY", "ADOPTION")


def test_every_admitted_summary_names_the_exact_catalog_identity_and_version():
    outcome, _ = _outcome(with_indicators=True)
    by_class = {s.indicator_class: s for s in outcome.indicator_admissions}
    assert by_class[ReadinessIndicatorClass.INTELLIGENCE].catalog_id == "cat-int"
    assert by_class[ReadinessIndicatorClass.CAPABILITY].catalog_id == "cat-cap"
    assert by_class[ReadinessIndicatorClass.ADOPTION].catalog_id == "cat-ado"
    assert {s.catalog_version for s in outcome.indicator_admissions} == {"1.0.0"}


def test_admission_preserves_the_metric_claim_and_its_evidence_axes_exactly():
    """Catalog membership is not evidence verification (ADR §12, D-8)."""

    policy = _passing_policy()
    req = request(policy=policy, gate_results=_passing_gates(policy), with_indicators=True)
    supplied = req.intelligence_results[0]

    outcome = _wired(req, policy)
    evaluated = outcome.evaluation.determination.intelligence_results[0]

    assert evaluated.claim == supplied.claim
    assert evaluated.claim.source_basis is supplied.claim.source_basis
    assert evaluated.claim.attestation_status is supplied.claim.attestation_status
    assert evaluated.claim.attribution_status is supplied.claim.attribution_status
    assert evaluated.claim.verification_status is supplied.claim.verification_status
    assert evaluated.canonical_digest() == supplied.canonical_digest()


# --------------------------------------------------------------------------- #
# The binding is required, and binding failure is NOT_EVALUATED
# --------------------------------------------------------------------------- #
def test_a_missing_binding_is_not_evaluated_not_a_headline():
    outcome, _ = _outcome(system_binding=None)
    assert outcome.status is ReadinessAssessmentStatus.NOT_EVALUATED
    assert outcome.classification is None
    assert outcome.evaluation is None
    assert _G.SYSTEM_BINDING_REQUIRED.value in outcome.trust_gap_codes
    assert outcome.system_binding_accepted is False
    assert outcome.trace.system_binding_ref == ""
    assert outcome.trace.system_binding_digest == ""


def test_there_is_no_second_unbound_entry_point():
    """One path only — a bypass would be an anti-gaming hole, not compatibility."""

    import ugence_agent_value_readiness.api as api

    entry_points = [
        n for n in api.__all__ if n.startswith("assess") or n.endswith("_readiness")
    ]
    assert entry_points == ["evaluate_readiness", "assess_readiness"] or set(entry_points) == {
        "evaluate_readiness",
        "assess_readiness",
    }


def test_a_cross_tenant_binding_fails_closed():
    policy = _passing_policy()
    ctx = context(policy)
    outcome, _ = _outcome(
        policy=policy, ctx=ctx, system_binding=binding(ctx=ctx, tenant="other-tenant")
    )
    assert outcome.status is ReadinessAssessmentStatus.NOT_EVALUATED
    assert _G.SYSTEM_BINDING_TENANT_MISMATCH.value in outcome.trust_gap_codes


def test_a_cross_subject_binding_fails_closed():
    policy = _passing_policy()
    ctx = context(policy)
    outcome, _ = _outcome(
        policy=policy, ctx=ctx, system_binding=binding(ctx=ctx, subject="other-subject")
    )
    assert outcome.status is ReadinessAssessmentStatus.NOT_EVALUATED
    assert _G.SYSTEM_BINDING_SUBJECT_MISMATCH.value in outcome.trust_gap_codes


def test_a_context_digest_mismatch_fails_closed():
    """A same-named context with different content cannot carry the binding."""

    policy = _passing_policy()
    ctx = context(policy)
    forged = binding(ctx=ctx)
    forged = type(forged)(
        **{
            **{f: getattr(forged, f) for f in forged.__dataclass_fields__},
            "context_digest": hashlib.sha256(b"a different context").hexdigest(),
        }
    )
    outcome, _ = _outcome(policy=policy, ctx=ctx, system_binding=forged)
    assert outcome.status is ReadinessAssessmentStatus.NOT_EVALUATED
    assert _G.SYSTEM_BINDING_CONTEXT_MISMATCH.value in outcome.trust_gap_codes


def test_a_context_identity_mismatch_fails_closed():
    policy = _passing_policy()
    ctx = context(policy)
    other_ctx = context(policy, context_id="ctx-other")
    outcome, _ = _outcome(policy=policy, ctx=ctx, system_binding=binding(ctx=other_ctx))
    assert outcome.status is ReadinessAssessmentStatus.NOT_EVALUATED
    assert _G.SYSTEM_BINDING_CONTEXT_MISMATCH.value in outcome.trust_gap_codes


def test_a_binding_outside_its_effective_period_fails_closed():
    from datetime import datetime, timezone

    policy = _passing_policy()
    ctx = context(policy)
    expired = binding(
        ctx=ctx,
        effective_from=datetime(2020, 1, 1, tzinfo=timezone.utc),
        effective_to=datetime(2021, 1, 1, tzinfo=timezone.utc),
    )
    outcome, _ = _outcome(policy=policy, ctx=ctx, system_binding=expired)
    assert outcome.status is ReadinessAssessmentStatus.NOT_EVALUATED
    assert (
        _G.SYSTEM_BINDING_NOT_EFFECTIVE_AT_EVALUATION_TIME.value in outcome.trust_gap_codes
    )


def test_a_binding_failure_can_never_produce_a_ready_tier():
    for kwargs in (
        {"system_binding": None},
        {"system_binding": binding(ctx=context(_passing_policy()), tenant="other")},
    ):
        outcome, _ = _outcome(with_indicators=False, **kwargs)
        assert outcome.classification is None
        assert outcome.evaluated is False


# --------------------------------------------------------------------------- #
# Result → binding: replay from another system is refused
# --------------------------------------------------------------------------- #
def _with_intel(policy, ctx, bind, intel, catalog_set):
    req = request(
        policy=policy,
        ctx=ctx,
        gate_results=_passing_gates(policy),
        system_binding=bind,
        indicator_catalogs=catalog_set,
    )
    return type(req)(
        **{
            **{f: getattr(req, f) for f in req.__dataclass_fields__},
            "intelligence_results": intel,
        }
    )


def _rebind(result, **kw):
    fields = {f: getattr(result, f) for f in result.__dataclass_fields__}
    fields.update(kw)
    return type(result)(**fields)


def test_an_indicator_result_from_another_system_binding_is_excluded():
    policy = _passing_policy()
    ctx = context(policy)
    this_binding = binding(ctx=ctx)
    other_binding = binding(ctx=ctx, binding_id="bind-2", system_version="9.9.9")

    intel, cap, ado = indicators(context_id=ctx.context_id, system_binding=other_binding)
    req = request(
        policy=policy,
        ctx=ctx,
        gate_results=_passing_gates(policy),
        system_binding=this_binding,
        indicator_catalogs=catalogs(),
    )
    req = type(req)(
        **{**{f: getattr(req, f) for f in req.__dataclass_fields__}, "intelligence_results": intel}
    )

    outcome = _wired(req, policy)
    assert _G.INDICATOR_RESULT_SYSTEM_BINDING_MISMATCH.value in outcome.trust_gap_codes
    assert outcome.trace.excluded_indicator_result_ids == ("ir1",)
    assert outcome.evaluation.determination.intelligence_results == ()


def test_the_same_system_id_with_a_different_configuration_is_a_different_binding():
    """Version A's favourable result cannot be replayed under configuration B."""

    policy = _passing_policy()
    ctx = context(policy)
    config_a = binding(ctx=ctx)
    config_b = binding(
        ctx=ctx,
        binding_id="bind-2",
        configuration_id="cfg-b",
        configuration_digest=CONFIG_DIGEST_B,
    )

    # Same system, same version — only the configuration moved — and the
    # bindings are still distinguishable by digest.
    assert config_a.system_id == config_b.system_id
    assert config_a.system_version == config_b.system_version
    assert config_a.canonical_digest() != config_b.canonical_digest()

    intel, _cap, _ado = indicators(context_id=ctx.context_id, system_binding=config_a)
    tampered_variants = (
        # The whole of B's identity.
        _rebind(
            intel[0],
            system_binding_ref=config_b.binding_id,
            system_binding_digest=config_b.canonical_digest(),
        ),
        # Only the digest — A's reference kept, so a reference check alone would
        # have admitted a result produced against a different configuration.
        _rebind(intel[0], system_binding_digest=config_b.canonical_digest()),
        # Only the reference — B's id kept, so a digest check alone would have
        # admitted a result claiming to belong to a different binding.
        _rebind(intel[0], system_binding_ref=config_b.binding_id),
    )
    for tampered in tampered_variants:
        outcome = _wired(
            _with_intel(policy, ctx, config_a, (tampered,), catalogs()), policy
        )
        assert _G.INDICATOR_RESULT_SYSTEM_BINDING_MISMATCH.value in outcome.trust_gap_codes
        assert outcome.evaluation.determination.intelligence_results == ()


def test_a_result_declaring_no_system_binding_is_excluded():
    policy = _passing_policy()
    ctx = context(policy)
    intel, _c, _a = indicators(context_id=ctx.context_id, system_binding=None)
    assert intel[0].system_bound is False

    req = request(
        policy=policy,
        ctx=ctx,
        gate_results=_passing_gates(policy),
        indicator_catalogs=catalogs(),
    )
    req = type(req)(
        **{**{f: getattr(req, f) for f in req.__dataclass_fields__}, "intelligence_results": intel}
    )
    outcome = _wired(req, policy)
    assert _G.INDICATOR_RESULT_SYSTEM_BINDING_MISMATCH.value in outcome.trust_gap_codes
    assert outcome.evaluation.determination.intelligence_results == ()


# --------------------------------------------------------------------------- #
# Result → catalog admission
# --------------------------------------------------------------------------- #
def test_an_uncataloged_indicator_is_excluded_with_a_stable_typed_gap():
    policy = _passing_policy()
    ctx = context(policy)
    bind = binding(ctx=ctx)
    intel, _c, _a = indicators(context_id=ctx.context_id, system_binding=bind)
    unknown = _rebind(intel[0], indicator_id="ind-not-in-any-catalog")

    outcome = _wired(_with_intel(policy, ctx, bind, (unknown,), catalogs()), policy)
    assert _G.INDICATOR_NOT_CATALOGED.value in outcome.trust_gap_codes
    assert outcome.indicator_admissions[0].admission_status is _I.NOT_CATALOGED
    assert outcome.evaluation.determination.intelligence_results == ()


def test_an_indicator_supplied_for_a_family_with_no_bound_catalog_is_excluded():
    policy = _passing_policy()
    ctx = context(policy)
    bind = binding(ctx=ctx)
    intel, _c, _a = indicators(context_id=ctx.context_id, system_binding=bind)

    outcome = _wired(
        _with_intel(policy, ctx, bind, intel, catalogs(intelligence=False)), policy
    )
    assert _G.INDICATOR_CATALOG_MISSING.value in outcome.trust_gap_codes
    assert outcome.indicator_admissions[0].admission_status is _I.CATALOG_MISSING
    assert outcome.evaluation.determination.intelligence_results == ()


def test_no_catalog_set_at_all_excludes_every_supplied_indicator():
    policy = _passing_policy()
    ctx = context(policy)
    bind = binding(ctx=ctx)
    intel, _c, _a = indicators(context_id=ctx.context_id, system_binding=bind)

    outcome = _wired(_with_intel(policy, ctx, bind, intel, None), policy)
    assert _G.INDICATOR_CATALOG_MISSING.value in outcome.trust_gap_codes
    assert outcome.evaluation.determination.intelligence_results == ()
    assert outcome.trace.indicator_catalog_set_digest == ""


def test_a_dimension_disagreeing_with_the_cataloged_definition_is_excluded():
    policy = _passing_policy()
    ctx = context(policy)
    bind = binding(ctx=ctx)
    intel, _c, _a = indicators(context_id=ctx.context_id, system_binding=bind)
    wrong = _rebind(intel[0], dimension=IntelligenceDimension.RELIABILITY)

    outcome = _wired(_with_intel(policy, ctx, bind, (wrong,), catalogs()), policy)
    assert _G.INDICATOR_CATALOG_DIMENSION_MISMATCH.value in outcome.trust_gap_codes
    assert outcome.indicator_admissions[0].admission_status is _I.DEFINITION_MISMATCH
    assert outcome.evaluation.determination.intelligence_results == ()


def test_a_metric_disagreeing_with_the_cataloged_definition_is_excluded():
    policy = _passing_policy()
    ctx = context(policy)
    bind = binding(ctx=ctx)
    intel, _c, _a = indicators(context_id=ctx.context_id, system_binding=bind)

    outcome = _wired(
        _with_intel(policy, ctx, bind, intel, catalogs(metric_id="a-different-metric")), policy
    )
    assert _G.INDICATOR_CATALOG_METRIC_MISMATCH.value in outcome.trust_gap_codes
    assert outcome.evaluation.determination.intelligence_results == ()


def test_a_definition_that_does_not_apply_to_the_requested_target_is_excluded():
    from ugence_uvi_policy_contracts.api import ReadinessTarget

    policy = _passing_policy()
    ctx = context(policy)
    bind = binding(ctx=ctx)
    intel, _c, _a = indicators(context_id=ctx.context_id, system_binding=bind)
    pilot_only = catalogs(target=ReadinessTarget.PILOT)

    outcome = _wired(_with_intel(policy, ctx, bind, intel, pilot_only), policy)
    assert _G.INDICATOR_CATALOG_TARGET_MISMATCH.value in outcome.trust_gap_codes
    assert outcome.evaluation.determination.intelligence_results == ()


def test_a_tenant_scoped_catalog_from_another_tenant_recognizes_nothing():
    policy = _passing_policy()
    ctx = context(policy)
    bind = binding(ctx=ctx)
    intel, _c, _a = indicators(context_id=ctx.context_id, system_binding=bind)
    foreign = catalogs(tenant="another-tenant")

    outcome = _wired(_with_intel(policy, ctx, bind, intel, foreign), policy)
    assert _G.INDICATOR_CATALOG_REFERENCE_MISMATCH.value in outcome.trust_gap_codes
    assert _G.INDICATOR_CATALOG_MISSING.value in outcome.trust_gap_codes
    assert outcome.evaluation.determination.intelligence_results == ()


def test_a_global_catalog_is_always_admissible():
    outcome, _ = _outcome(with_indicators=True)
    assert outcome.trace.admitted_indicator_result_ids == ("ar1", "cr1", "ir1")


def test_duplicate_indicator_identities_exclude_every_copy():
    policy = _passing_policy()
    ctx = context(policy)
    bind = binding(ctx=ctx)
    intel, _c, _a = indicators(context_id=ctx.context_id, system_binding=bind)
    twin = _rebind(intel[0], result_id="ir2")

    outcome = _wired(_with_intel(policy, ctx, bind, (intel[0], twin), catalogs()), policy)
    assert _G.INDICATOR_RESULT_DUPLICATE.value in outcome.trust_gap_codes
    assert outcome.trace.admitted_indicator_result_ids == ()
    assert outcome.trace.excluded_indicator_result_ids == ("ir1", "ir2")
    assert outcome.evaluation.determination.intelligence_results == ()


def test_one_indicator_id_cannot_be_claimed_in_two_families():
    """Cross-family duplicate identity is refused at the catalog set itself."""

    from ugence_agent_value_readiness.api import ReadinessContractError

    with pytest.raises(ReadinessContractError):
        ReadinessIndicatorCatalogSet(
            intelligence=IntelligenceFitnessCatalog(
                catalog_id="k1",
                catalog_version="1",
                entries=(
                    IntelligenceFitnessIndicatorDefinition(
                        indicator_id="shared", dimension=IntelligenceDimension.ACCURACY,
                        metric_id="m",
                    ),
                ),
            ),
            capability=CapabilityReadinessCatalog(
                catalog_id="k2",
                catalog_version="1",
                entries=(
                    CapabilityReadinessIndicatorDefinition(
                        indicator_id="shared",
                        dimension=__import__(
                            "ugence_agent_value_readiness.api", fromlist=["x"]
                        ).CapabilityDimension.TOOL_READINESS,
                        metric_id="m",
                    ),
                ),
            ),
        )


# --------------------------------------------------------------------------- #
# Precedence and anti-gaming
# --------------------------------------------------------------------------- #
def test_policy_resolution_failure_prevents_all_binding_and_catalog_processing():
    """Stage 1 dominates: no binding or catalog code may appear alongside it."""

    policy = _passing_policy()
    req = request(
        policy=policy,
        gate_results=_passing_gates(policy),
        with_indicators=True,
        system_binding=None,
    )
    outcome = assess_readiness(req)  # every boundary omitted → deny

    assert outcome.status is ReadinessAssessmentStatus.NOT_EVALUATED
    assert _G.POLICY_RESOLVER_NOT_CONFIGURED.value in outcome.trust_gap_codes
    binding_or_catalog = [
        code
        for code in outcome.trust_gap_codes
        if "SYSTEM_BINDING" in code or "INDICATOR" in code or "CATALOG" in code
    ]
    assert binding_or_catalog == []
    assert outcome.indicator_admissions == ()


def test_a_verified_mandatory_fail_is_unchanged_by_a_favourable_catalog():
    policy = readiness_policy(gates=(gate("g1", MANDATORY, BOTH),))
    req = request(
        policy=policy,
        gate_results=(gate_result(policy, "g1", GateStatus.FAIL),),
        with_indicators=True,
    )
    outcome = _wired(req, policy)

    assert outcome.classification is ReadinessClassification.NOT_READY
    # Every indicator was recognized and still changed nothing.
    assert outcome.trace.admitted_indicator_result_ids == ("ar1", "cr1", "ir1")


def test_an_uncataloged_indicator_cannot_satisfy_a_gate():
    """A missing required gate result stays missing whatever the indicators say."""

    policy = readiness_policy(gates=(gate("g1", MANDATORY, BOTH),))
    req = request(policy=policy, gate_results=(), with_indicators=True)
    outcome = _wired(req, policy)

    assert outcome.classification is ReadinessClassification.NOT_ASSESSABLE
    assert outcome.classification is not ReadinessClassification.DEPLOYMENT_READY


def test_catalog_order_cannot_change_a_classification():
    policy = _passing_policy()
    ctx = context(policy)
    bind = binding(ctx=ctx)
    intel, _c, _a = indicators(context_id=ctx.context_id, system_binding=bind)

    ordered = catalogs()
    reordered = ReadinessIndicatorCatalogSet(
        adoption=ordered.adoption, capability=ordered.capability, intelligence=ordered.intelligence
    )
    a = _wired(_with_intel(policy, ctx, bind, intel, ordered), policy)
    b = _wired(_with_intel(policy, ctx, bind, intel, reordered), policy)

    assert a.classification is b.classification
    assert a.trace.canonical_digest() == b.trace.canonical_digest()
    assert a.canonical_digest() == b.canonical_digest()


def test_admission_never_elevates_evidence_status():
    """A recognized indicator's verification axis is exactly what it was."""

    policy = _passing_policy()
    req = request(policy=policy, gate_results=_passing_gates(policy), with_indicators=True)
    supplied = {r.result_id: r for r in req.intelligence_results}
    outcome = _wired(req, policy)

    for evaluated in outcome.evaluation.determination.intelligence_results:
        before = supplied[evaluated.result_id]
        assert evaluated.claim.verification_status is before.claim.verification_status
        assert evaluated.claim.attribution_status is before.claim.attribution_status


# --------------------------------------------------------------------------- #
# Trace honesty and determinism
# --------------------------------------------------------------------------- #
def test_the_trace_distinguishes_structural_acceptance_from_authenticity():
    outcome, _ = _outcome(with_indicators=True)

    assert outcome.system_binding_accepted is True
    assert outcome.system_binding_authenticity_verified is False

    authenticity = [
        d
        for d in outcome.dispositions
        if d.advisory_code.endswith("SYSTEM_BINDING_AUTHENTICITY_NOT_VERIFIED")
    ]
    assert len(authenticity) == 1
    assert authenticity[0].state.value == "OUT_OF_SCOPE"
    assert "structural" in authenticity[0].detail


def test_the_authenticity_disposition_is_present_even_when_the_binding_was_refused():
    outcome, _ = _outcome(system_binding=None)
    codes = [d.advisory_code for d in outcome.dispositions]
    assert any(c.endswith("SYSTEM_BINDING_AUTHENTICITY_NOT_VERIFIED") for c in codes)


def test_a_reordered_request_yields_an_identical_trace_and_digest():
    policy = _passing_policy()
    ctx = context(policy)
    bind = binding(ctx=ctx)
    intel, cap, ado = indicators(context_id=ctx.context_id, system_binding=bind)

    base = request(
        policy=policy,
        ctx=ctx,
        gate_results=_passing_gates(policy),
        system_binding=bind,
        indicator_catalogs=catalogs(),
    )
    fields = {f: getattr(base, f) for f in base.__dataclass_fields__}
    forward = type(base)(**{**fields, "intelligence_results": intel})
    reordered = type(base)(**{**fields, "intelligence_results": tuple(reversed(intel))})

    assert forward.canonical_digest() == reordered.canonical_digest()
    assert (
        _wired(forward, policy).canonical_digest() == _wired(reordered, policy).canonical_digest()
    )


def test_gap_codes_are_emitted_in_declaration_order_not_input_order():
    policy = _passing_policy()
    ctx = context(policy)
    outcome, _ = _outcome(policy=policy, ctx=ctx, system_binding=binding(ctx=ctx, tenant="x", subject="y"))

    declared = [m.value for m in ReadinessTrustGapCode]
    emitted = list(outcome.trust_gap_codes)
    assert emitted == [v for v in declared if v in set(emitted)]


def test_the_request_digest_separates_two_system_configurations():
    policy = _passing_policy()
    ctx = context(policy)
    a = request(policy=policy, ctx=ctx, system_binding=binding(ctx=ctx))
    b = request(
        policy=policy,
        ctx=ctx,
        system_binding=binding(
            ctx=ctx, configuration_id="cfg-b", configuration_digest=CONFIG_DIGEST_B
        ),
    )
    assert a.canonical_digest() != b.canonical_digest()


def test_a_caller_list_mutation_cannot_reach_the_request_after_construction():
    policy = _passing_policy()
    ctx = context(policy)
    bind = binding(ctx=ctx)
    intel, _c, _a = indicators(context_id=ctx.context_id, system_binding=bind)
    supplied = list(intel)

    req = _with_intel(policy, ctx, bind, supplied, catalogs())
    before = req.canonical_digest()
    supplied.clear()

    assert req.intelligence_results == intel
    assert req.canonical_digest() == before
