#!/usr/bin/env python3
"""Fresh public-API adversarial probe harness for M-3R.3.

Deliberately **independent** of ``tests/`` and of every package fixture: it
imports nothing but the curated public API, builds every artifact from scratch,
and asserts the milestone's trust boundaries the way an external integrator
would discover them. If the package tests and this harness ever disagree, one of
them is wrong — that is the point of keeping them separate.

Run in-tree::

    python packages/capabilities/agent-value-readiness/m3r3_adversarial_probes.py

or against an installed wheel, from any directory::

    python m3r3_adversarial_probes.py

Every probe answers a question an untrusted caller would ask. Exit status is 0
only when every probe holds.
"""

from __future__ import annotations

import dataclasses
import hashlib
import pathlib
import sys
from datetime import datetime, timezone

# In-tree convenience: resolve the four sibling src trees when the package is
# not installed. A wheel install needs none of this.
_HERE = pathlib.Path(__file__).resolve().parent
_PACKAGES = _HERE.parents[1]
for _candidate in (
    _HERE / "src",
    _PACKAGES / "governance-contracts" / "src",
    _PACKAGES / "uvi-policy-contracts" / "src",
    _PACKAGES / "policy-authority" / "src",
):
    if _candidate.is_dir() and str(_candidate) not in sys.path:
        sys.path.insert(0, str(_candidate))

import ugence_agent_value_readiness as R  # noqa: E402
from ugence_agent_value_readiness import api  # noqa: E402

_PASSED: list[str] = []
_FAILED: list[str] = []


def probe(description):
    def decorate(fn):
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 - a probe failure is reported, not raised
            _FAILED.append(f"{description}: {type(exc).__name__}: {exc}")
            print(f"  FAIL  {description}")
        else:
            _PASSED.append(description)
            print(f"  ok  {description}")
        return fn

    return decorate


def _raises(exc_types, fn, *args, **kwargs) -> bool:
    try:
        fn(*args, **kwargs)
    except exc_types:
        return True
    except Exception:  # noqa: BLE001
        return False
    return False


DIGEST_A = hashlib.sha256(b"a").hexdigest()
DIGEST_B = hashlib.sha256(b"b").hexdigest()
T_FROM = datetime(2026, 1, 1, tzinfo=timezone.utc)
T_MID = datetime(2026, 6, 1, tzinfo=timezone.utc)
T_TO = datetime(2027, 1, 1, tzinfo=timezone.utc)


def make_binding(**kw):
    base = dict(
        binding_id="probe-binding",
        tenant_id="tenant-a",
        subject_id="subject-a",
        context_id="ctx-a",
        context_digest=DIGEST_A,
        system_id="sys",
        system_version="1.0.0",
        configuration_id="cfg",
        configuration_digest=DIGEST_A,
    )
    base.update(kw)
    return api.AssessedSystemBinding(**base)


def make_catalog(**kw):
    base = dict(
        catalog_id="probe-catalog",
        catalog_version="1.0.0",
        entries=(
            api.IntelligenceFitnessIndicatorDefinition(
                indicator_id="ind-1",
                dimension=api.IntelligenceDimension.ACCURACY,
                metric_id="accuracy",
            ),
        ),
    )
    base.update(kw)
    return api.IntelligenceFitnessCatalog(**base)


print(f"M-3R.3 adversarial probes — {R.__version__} / {api.READINESS_ORCHESTRATOR_VERSION}\n")

# --------------------------------------------------------------------------- #
# Identity and versioning
# --------------------------------------------------------------------------- #


@probe("the package version is exactly 0.4.0")
def _version():
    assert R.__version__ == "0.4.1", R.__version__


@probe("the orchestrator version advanced to v0.2 and names no milestone")
def _orchestrator_version():
    value = api.READINESS_ORCHESTRATOR_VERSION
    assert value == "ugence.readiness-orchestration/v0.2", value
    lowered = value.lower()
    for token in ("m-3r", "m3r", "gv-3r", "gv3r", "milestone", "phase"):
        assert token not in lowered, token


@probe("the evaluator formula version did NOT move")
def _formula_version():
    from ugence_agent_value_readiness.evaluation.codes import EVALUATOR_FORMULA_VERSION

    assert EVALUATOR_FORMULA_VERSION == "GV-3R-b.3", EVALUATOR_FORMULA_VERSION


@probe("every new trust-gap code carries the neutral namespace and is unique")
def _gap_namespace():
    members = list(api.ReadinessTrustGapCode)
    for member in members:
        assert member.value.startswith("READINESS_ORCHESTRATION_"), member.value
        assert "GV3RC" not in member.value and "M3R3" not in member.value, member.value
    assert len({m.value for m in members}) == len(members)
    assert len({m.name for m in members}) == len(members)


@probe("the moved binding is owned by governance-contracts, not re-implemented")
def _binding_ownership():
    import ugence_governance_contracts as G
    from ugence_governance_contracts import api as gapi

    # Exactly one class identity across both public APIs.
    assert api.AssessedSystemBinding is gapi.AssessedSystemBinding
    assert api.SystemBindingAuthenticityStatus is gapi.SystemBindingAuthenticityStatus
    assert api.SystemIdentityContractError is gapi.SystemIdentityContractError
    assert (
        api.AssessedSystemBinding.__module__
        == "ugence_governance_contracts.contracts.system_identity"
    )
    # No copy, subclass, adapter or parallel schema anywhere.
    assert api.AssessedSystemBinding.__subclasses__() == []
    readiness_root = pathlib.Path(R.__file__).resolve().parent
    assert not (readiness_root / "contracts" / "binding.py").exists()
    # Readiness errors stay readiness-owned; the binding's error does not.
    assert api.ReadinessContractError is not api.SystemIdentityContractError
    # One-way arrow.
    assert not hasattr(G, "assess_readiness")


@probe("the binding digest is byte-identical to the pre-move implementation")
def _digest_invariance():
    pinned = "cdbafaaba667b4496f309d01ba7c75788033f68f93d8042ab311f39ddc50b43d"
    moved = api.AssessedSystemBinding(
        binding_id="bind-1", tenant_id="t1", subject_id="a1", context_id="ctx1",
        context_digest="baba834176cee0f39f8dc6e4a29d7c5afe1861e6b410c3ed9acb538a795d2fdf",
        system_id="agent-sys-1", system_version="1.4.2", configuration_id="cfg-prod-a",
        configuration_digest="b8d582270bcab6ca49bc8ef3b9916fa6f77fd84a35be1c1d884eec31746a29a6",
    )
    assert moved.canonical_digest() == pinned, moved.canonical_digest()


@probe("the M-3R.3 semantic categories all exist as stable codes")
def _gap_coverage():
    required = {
        "SYSTEM_BINDING_REQUIRED",
        "SYSTEM_BINDING_CONTEXT_MISMATCH",
        "SYSTEM_BINDING_TENANT_MISMATCH",
        "SYSTEM_BINDING_SUBJECT_MISMATCH",
        "SYSTEM_BINDING_NOT_EFFECTIVE_AT_EVALUATION_TIME",
        "INDICATOR_CATALOG_MISSING",
        "INDICATOR_CATALOG_FAMILY_MISMATCH",
        "INDICATOR_CATALOG_REFERENCE_MISMATCH",
        "INDICATOR_NOT_CATALOGED",
        "INDICATOR_CATALOG_DIMENSION_MISMATCH",
        "INDICATOR_CATALOG_METRIC_MISMATCH",
        "INDICATOR_CATALOG_TARGET_MISMATCH",
        "INDICATOR_RESULT_SYSTEM_BINDING_MISMATCH",
        "INDICATOR_RESULT_DUPLICATE",
    }
    names = {m.name for m in api.ReadinessTrustGapCode}
    assert required <= names, sorted(required - names)


# --------------------------------------------------------------------------- #
# The binding proves structure, never authenticity
# --------------------------------------------------------------------------- #


@probe("a structurally perfect fabricated binding is still STRUCTURAL_UNVERIFIED")
def _binding_is_structural():
    fabricated = make_binding(system_id="never-deployed")
    assert fabricated.authenticity_verified is False
    assert (
        fabricated.authenticity_status
        is api.SystemBindingAuthenticityStatus.STRUCTURAL_UNVERIFIED
    )


@probe("authenticity is a property, not a settable field")
def _authenticity_not_a_field():
    names = {f.name for f in dataclasses.fields(api.AssessedSystemBinding)}
    assert "authenticity_status" not in names
    assert "authenticity_verified" not in names
    assert _raises(TypeError, make_binding, authenticity_status="AUTHORITY_VERIFIED")
    assert _raises(TypeError, make_binding, authenticity_verified=True)


@probe("the authenticity enum admits no verified value")
def _authenticity_enum_closed():
    values = [m.value for m in api.SystemBindingAuthenticityStatus]
    assert values == ["STRUCTURAL_UNVERIFIED"], values
    assert _raises(ValueError, api.SystemBindingAuthenticityStatus, "AUTHORITY_VERIFIED")


@probe("two system versions cannot share a binding digest")
def _version_replay():
    a = make_binding(system_version="1.0.0")
    b = make_binding(system_version="1.0.1")
    assert a.canonical_digest() != b.canonical_digest()


@probe("two configurations of one system cannot share a binding digest")
def _configuration_replay():
    a = make_binding(configuration_id="cfg-a", configuration_digest=DIGEST_A)
    b = make_binding(configuration_id="cfg-b", configuration_digest=DIGEST_B)
    assert a.system_id == b.system_id
    assert a.canonical_digest() != b.canonical_digest()


@probe("cross-tenant and cross-subject bindings cannot share a digest")
def _tenant_subject_replay():
    base = make_binding()
    assert base.canonical_digest() != make_binding(tenant_id="tenant-b").canonical_digest()
    assert base.canonical_digest() != make_binding(subject_id="subject-b").canonical_digest()


@probe("a manifest reference must be digest-bound, and vice versa")
def _manifest_pair():
    assert _raises(api.SystemIdentityContractError, make_binding, system_manifest_ref="m")
    assert _raises(
        api.SystemIdentityContractError, make_binding, system_manifest_digest=DIGEST_A
    )
    both = make_binding(system_manifest_ref="m", system_manifest_digest=DIGEST_A)
    assert both.system_manifest_ref == "m"


@probe("no SystemManifest type was invented")
def _no_system_manifest():
    for name in api.__all__:
        assert "systemmanifest" not in name.lower().replace("_", ""), name


@probe("the binding rejects naive timestamps and inverted intervals")
def _binding_time():
    naive = datetime(2026, 6, 1)
    assert _raises(api.SystemIdentityContractError, make_binding, effective_from=naive)
    assert _raises(api.SystemIdentityContractError, make_binding, effective_to=naive)
    assert _raises(
        api.SystemIdentityContractError, make_binding, effective_from=T_TO, effective_to=T_FROM
    )


@probe("the binding effective period is half-open [from, to)")
def _binding_half_open():
    b = make_binding(effective_from=T_FROM, effective_to=T_TO)
    assert b.is_effective_at(T_FROM) is True
    assert b.is_effective_at(T_MID) is True
    assert b.is_effective_at(T_TO) is False


@probe("the binding is frozen and holds no caller-owned collection")
def _binding_frozen():
    b = make_binding()
    assert _raises(dataclasses.FrozenInstanceError, setattr, b, "system_version", "9")
    for field in dataclasses.fields(api.AssessedSystemBinding):
        value = getattr(b, field.name)
        assert value is None or isinstance(value, (str, datetime)), field.name


# --------------------------------------------------------------------------- #
# Catalogs define vocabulary, never requirements
# --------------------------------------------------------------------------- #


@probe("all three catalog families exist and are distinct types")
def _three_families():
    families = {
        api.IntelligenceFitnessCatalog(catalog_id="k", catalog_version="1").family,
        api.CapabilityReadinessCatalog(catalog_id="k", catalog_version="1").family,
        api.AdoptionReadinessCatalog(catalog_id="k", catalog_version="1").family,
    }
    assert families == set(api.ReadinessIndicatorClass), families


@probe("a definition from one family cannot enter another family's catalog")
def _no_family_mixing():
    adoption_def = api.AdoptionReadinessIndicatorDefinition(
        indicator_id="a", dimension=api.AdoptionDimension.TRUST_READINESS, metric_id="m"
    )
    assert _raises(
        api.ReadinessContractError, make_catalog, entries=(adoption_def,)
    )


@probe("a dimension from another family is rejected")
def _no_foreign_dimension():
    assert _raises(
        api.ReadinessContractError,
        api.IntelligenceFitnessIndicatorDefinition,
        indicator_id="x",
        dimension=api.AdoptionDimension.TRUST_READINESS,
        metric_id="m",
    )


@probe("an arbitrary dimension value cannot be introduced at runtime")
def _closed_dimension_enum():
    for bad in ("ACCURACY", 1, None):
        assert _raises(
            api.ReadinessContractError,
            api.IntelligenceFitnessIndicatorDefinition,
            indicator_id="x",
            dimension=bad,
            metric_id="m",
        )


@probe("domain extension goes through the governed metric_id")
def _metric_extension():
    definition = api.IntelligenceFitnessIndicatorDefinition(
        indicator_id="x",
        dimension=api.IntelligenceDimension.ACCURACY,
        metric_id="acme.domain.custom-metric",
    )
    assert definition.metric_id == "acme.domain.custom-metric"


@probe("no catalog shape can state a requirement, weight, score or money")
def _no_requirement_vocabulary():
    banned = (
        "required",
        "mandatory",
        "requirement",
        "weight",
        "multiplier",
        "score",
        "threshold",
        "benchmark",
        "tier",
        "classification",
        "money",
        "currency",
        "cost",
        "benefit",
        "revenue",
        "roi",
        "evidence",
        "verification",
        "attestation",
        "attribution",
    )
    for cls in (
        api.IntelligenceFitnessIndicatorDefinition,
        api.CapabilityReadinessIndicatorDefinition,
        api.AdoptionReadinessIndicatorDefinition,
        api.IntelligenceFitnessCatalog,
        api.CapabilityReadinessCatalog,
        api.AdoptionReadinessCatalog,
        api.ReadinessIndicatorCatalogSet,
    ):
        for field in dataclasses.fields(cls):
            for token in banned:
                assert token not in field.name.lower(), (cls.__name__, field.name)


@probe("a catalog entry cannot be marked required")
def _no_required_flag():
    assert _raises(
        TypeError,
        api.IntelligenceFitnessIndicatorDefinition,
        indicator_id="x",
        dimension=api.IntelligenceDimension.ACCURACY,
        metric_id="m",
        required=True,
    )


@probe("duplicate indicator ids are rejected within and across a catalog set")
def _duplicate_ids():
    duplicate = api.IntelligenceFitnessIndicatorDefinition(
        indicator_id="ind-1", dimension=api.IntelligenceDimension.RELIABILITY, metric_id="m"
    )
    assert _raises(
        api.ReadinessContractError,
        make_catalog,
        entries=(make_catalog().entries[0], duplicate),
    )
    shared = api.AdoptionReadinessCatalog(
        catalog_id="other",
        catalog_version="1",
        entries=(
            api.AdoptionReadinessIndicatorDefinition(
                indicator_id="ind-1",
                dimension=api.AdoptionDimension.TRUST_READINESS,
                metric_id="m",
            ),
        ),
    )
    assert _raises(
        api.ReadinessContractError,
        api.ReadinessIndicatorCatalogSet,
        intelligence=make_catalog(),
        adoption=shared,
    )


@probe("catalog entry order is canonicalized and not digest-significant")
def _order_canonicalized():
    a = api.IntelligenceFitnessIndicatorDefinition(
        indicator_id="a", dimension=api.IntelligenceDimension.ACCURACY, metric_id="m"
    )
    b = api.IntelligenceFitnessIndicatorDefinition(
        indicator_id="b", dimension=api.IntelligenceDimension.RELIABILITY, metric_id="m"
    )
    forward = make_catalog(entries=(a, b))
    backward = make_catalog(entries=(b, a))
    assert forward == backward
    assert forward.canonical_digest() == backward.canonical_digest()
    assert forward.indicator_ids == ("a", "b")


@probe("a caller list cannot mutate a catalog after construction")
def _catalog_mutation():
    entries = [make_catalog().entries[0]]
    catalog = make_catalog(entries=entries)
    before = catalog.canonical_digest()
    entries.clear()
    assert catalog.indicator_ids == ("ind-1",)
    assert catalog.canonical_digest() == before


@probe("scalar, bytes and mapping substitutes for catalog entries are rejected")
def _catalog_substitutes():
    for substitute in ("x", b"x", bytearray(b"x"), {"a": 1}, 7, None):
        assert _raises(api.ReadinessContractError, make_catalog, entries=substitute), substitute


@probe("a generator of entries is materialized exactly once")
def _catalog_generator():
    catalog = make_catalog(entries=(e for e in make_catalog().entries))
    assert catalog.indicator_ids == ("ind-1",)
    assert catalog.indicator_ids == ("ind-1",)


@probe("an empty catalog set is valid — no family is globally mandatory")
def _no_all_three_requirement():
    empty = api.ReadinessIndicatorCatalogSet()
    assert empty.is_empty
    assert empty.families_present == ()
    single = api.ReadinessIndicatorCatalogSet(intelligence=make_catalog())
    assert single.families_present == (api.ReadinessIndicatorClass.INTELLIGENCE,)


@probe("a catalog cannot be bound under another family's slot")
def _no_slot_confusion():
    assert _raises(
        api.ReadinessContractError,
        api.ReadinessIndicatorCatalogSet,
        intelligence=api.AdoptionReadinessCatalog(catalog_id="k", catalog_version="1"),
    )


@probe("lookup returns the definition or None — never a fabricated default")
def _lookup_honesty():
    catalog = make_catalog()
    assert catalog.lookup("ind-1").indicator_id == "ind-1"
    assert catalog.lookup("nope") is None
    assert catalog.lookup("") is None
    assert catalog.lookup(None) is None


# --------------------------------------------------------------------------- #
# Indicator results, and the absence of a permissive path
# --------------------------------------------------------------------------- #


@probe("an indicator result's binding reference and digest are co-required")
def _result_binding_pair():
    import ugence_governance_contracts.api as gc

    claim = gc.MetricClaim(
        claim_id="c",
        tenant_id="tenant-a",
        subject_id="subject-a",
        metric_id="accuracy",
        value="0.9",
        governed_unit="ratio",
        source_basis=gc.SourceBasis.REPORTED,
        transformation_method=gc.TransformationMethod.DIRECT,
        assessment_window=gc.AssessmentWindow(start=T_FROM, end=T_MID),
    )
    common = dict(
        result_id="r1",
        tenant_id="tenant-a",
        subject_id="subject-a",
        context_id="ctx-a",
        task_or_outcome_ref="task",
        dimension=api.IntelligenceDimension.ACCURACY,
        claim=claim,
        requirement_class=api.RequirementClass.MANDATORY,
        applicable_targets=(api.ReadinessTarget.PRODUCTION,),
        status=api.GateStatus.PASS,
    )
    assert _raises(
        api.ReadinessContractError,
        api.IntelligenceFitnessResult,
        **common,
        system_binding_ref="b",
    )
    assert _raises(
        api.ReadinessContractError,
        api.IntelligenceFitnessResult,
        **common,
        system_binding_digest=DIGEST_A,
    )
    unbound = api.IntelligenceFitnessResult(**common)
    assert unbound.system_bound is False
    assert unbound.catalog_bound is False
    bound = api.IntelligenceFitnessResult(
        **common, indicator_id="ind-1", system_binding_ref="b", system_binding_digest=DIGEST_A
    )
    assert bound.system_bound is True and bound.catalog_bound is True


@probe("assess_readiness denies with no binding and no configured boundary")
def _deny_by_default():
    import inspect

    signature = inspect.signature(api.assess_readiness)
    for name in ("policy_resolver", "gate_verifier", "condition_verifier"):
        assert signature.parameters[name].default is None, name


@probe("no allow-all resolver, verifier or system-binding verifier is exported")
def _no_permissive_boundary():
    for name in api.__all__:
        lowered = name.lower()
        for banned in ("allowall", "permissive", "testing", "fake", "stub", "trustall"):
            assert banned not in lowered.replace("_", ""), name
    # And no binding verifier of any kind exists, permissive or otherwise.
    assert not any("bindingverifier" in n.lower().replace("_", "") for n in api.__all__)


@probe("no Benchmark Registry or evidence verifier ships")
def _no_deferred_capability():
    for name in api.__all__:
        flattened = name.lower().replace("_", "")
        for banned in ("benchmarkregistry", "evidenceverifier", "tapverifier"):
            assert banned not in flattened, name


@probe("no financial or authorization vocabulary is on the public surface")
def _no_financial_vocabulary():
    # "valuation" is deliberately absent from this list: it is a substring of
    # "evaluation", which is core readiness vocabulary. Financial valuation is
    # excluded structurally instead — see the FinancialValuation check below.
    banned = ("money", "currency", "cost", "benefit", "revenue", "roi", "authoriz", "profit")
    for name in api.__all__:
        flattened = name.lower().replace("_", "")
        for token in banned:
            assert token not in flattened, (name, token)
    for banned_type in ("FinancialValuation", "ValuationEvidenceManifest", "ValuationPolicy"):
        assert banned_type not in api.__all__, banned_type


@probe("the outcome's deployment-authorization property is permanently False")
def _no_deployment_authorization():
    names = {f.name for f in dataclasses.fields(api.ReadinessAssessmentOutcome)}
    assert "authorizes_deployment" not in names
    assert isinstance(
        api.ReadinessAssessmentOutcome.authorizes_deployment, property
    )


@probe("the trace separates structural binding acceptance from authenticity")
def _trace_separation():
    names = [f.name for f in dataclasses.fields(api.ReadinessAssessmentTrace)]
    assert "system_binding_accepted" in names
    assert "system_binding_authenticity_verified" not in names
    assert isinstance(
        api.ReadinessAssessmentOutcome.system_binding_authenticity_verified, property
    )
    assert api.SYSTEM_BINDING_AUTHENTICITY_ADVISORY.startswith("READINESS_ORCHESTRATION_")


@probe("an admission summary cannot be admitted and untrusted at once")
def _admission_summary_honesty():
    assert _raises(
        api.ReadinessAssessmentError,
        api.IndicatorAdmissionSummary,
        result_id="r",
        indicator_class=api.ReadinessIndicatorClass.INTELLIGENCE,
        indicator_id="i",
        admission_status=api.ReadinessIndicatorAdmissionStatus.NOT_CATALOGED,
        admitted=True,
        catalog_id="k",
        catalog_version="1",
    )
    assert _raises(
        api.ReadinessAssessmentError,
        api.IndicatorAdmissionSummary,
        result_id="r",
        indicator_class=api.ReadinessIndicatorClass.INTELLIGENCE,
        indicator_id="i",
        admission_status=api.ReadinessIndicatorAdmissionStatus.NOT_CATALOGED,
        admitted=False,
    )


@probe("the package reads no clock, randomness, uuid, environment or network")
def _no_hidden_input():
    import ast

    root = pathlib.Path(R.__file__).resolve().parent
    banned_modules = {"time", "random", "secrets", "uuid", "os", "socket", "urllib", "requests"}
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            roots: set[str] = set()
            if isinstance(node, ast.Import):
                roots = {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                roots = {node.module.split(".")[0]}
            assert not (roots & banned_modules), (path.name, sorted(roots & banned_modules))


@probe("the package imports no other capability, product or authority internal")
def _dependency_boundary():
    import ast

    root = pathlib.Path(R.__file__).resolve().parent
    prohibited = {
        "governed_value",
        "risk_authority",
        "decision_governance",
        "actiongate_provider",
        "tap_provider",
        "platform_freeze",
    }
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            names: set[str] = set()
            if isinstance(node, ast.Import):
                names = {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                names = {node.module.split(".")[0]}
                if node.module.startswith("ugence_policy_authority"):
                    assert node.module in {
                        "ugence_policy_authority",
                        "ugence_policy_authority.api",
                    }, node.module
            assert not (names & prohibited), (path.name, sorted(names & prohibited))


# --------------------------------------------------------------------------- #
print()
print(f"{len(_PASSED)} probe(s) held.")
if _FAILED:
    print(f"{len(_FAILED)} probe(s) FAILED:")
    for failure in _FAILED:
        print(f"  - {failure}")
    sys.exit(1)
print("All M-3R.3 adversarial probes held.")
