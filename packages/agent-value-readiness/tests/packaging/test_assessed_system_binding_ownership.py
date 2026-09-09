"""Ownership guards for the neutral assessed-system identity contract (ADR §20).

``AssessedSystemBinding`` is owned by ``ugence-governance-contracts``. This
package **consumes** it and owns only the readiness-specific parts: the indicator
catalogs, the admission rules, the adapter that compares a binding against an
``AssessmentContext``, the orchestration gap codes and the trace.

The failure mode these guards exist to prevent is the one that makes shared
contracts worthless: a second, drifting copy. Two implementations of "which
system was assessed" would eventually disagree about a digest, and a result
bound under one would silently verify under the other. So the tests below assert
**one class identity**, **one definition site**, and **one direction of
dependency** — structurally, over the source tree, not by convention.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import pathlib

import pytest

import ugence_agent_value_readiness as R
import ugence_governance_contracts as G
from ugence_agent_value_readiness import api as readiness_api
from ugence_governance_contracts import api as governance_api

READINESS_ROOT = pathlib.Path(R.__file__).resolve().parent
GOVERNANCE_ROOT = pathlib.Path(G.__file__).resolve().parent

#: Everything this leaf must never reach for, in either direction.
UVI_AND_HIGHER = {
    "ugence_agent_value_readiness",
    "ugence_uvi_policy_contracts",
    "ugence_policy_authority",
    "risk_authority",
    "ugence_risk_authority",
    "governed_value",
    "ugence_governed_value",
    "ugence_decision_authority",
}


def _import_roots(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue
            if node.module:
                roots.add(node.module.split(".")[0])
    return roots


def _sources(root: pathlib.Path):
    return [p for p in root.rglob("*.py") if "__pycache__" not in p.parts]


def _class_defs(root: pathlib.Path, name: str) -> list[str]:
    hits = []
    for path in _sources(root):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == name:
                hits.append(str(path))
    return hits


# --------------------------------------------------------------------------- #
# 1-2. Defined only in governance-contracts
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "name", ["AssessedSystemBinding", "SystemBindingAuthenticityStatus"]
)
def test_the_moved_type_is_defined_only_in_governance_contracts(name):
    assert _class_defs(GOVERNANCE_ROOT, name), f"{name} is not defined in governance-contracts"
    assert _class_defs(READINESS_ROOT, name) == [], (
        f"{name} has a second definition under the readiness source tree"
    )


def test_the_moved_types_report_the_governance_module_as_their_home():
    assert (
        governance_api.AssessedSystemBinding.__module__
        == "ugence_governance_contracts.contracts.system_identity"
    )
    assert (
        governance_api.SystemBindingAuthenticityStatus.__module__
        == "ugence_governance_contracts.contracts.system_identity"
    )


def test_no_readiness_module_file_is_named_for_the_moved_contract():
    """The old readiness-owned module is gone, not merely unimported."""

    assert not (READINESS_ROOT / "contracts" / "binding.py").exists()


# --------------------------------------------------------------------------- #
# 3. Any readiness export is the identical governance object
# --------------------------------------------------------------------------- #
def test_the_readiness_exports_are_the_identical_governance_objects():
    assert readiness_api.AssessedSystemBinding is governance_api.AssessedSystemBinding
    assert (
        readiness_api.SystemBindingAuthenticityStatus
        is governance_api.SystemBindingAuthenticityStatus
    )
    assert (
        readiness_api.SystemIdentityContractError
        is governance_api.SystemIdentityContractError
    )
    # ...and identical on the top-level namespaces too, not just the curated APIs.
    assert R.AssessedSystemBinding is G.AssessedSystemBinding
    assert R.SystemBindingAuthenticityStatus is G.SystemBindingAuthenticityStatus


def test_no_compatibility_subclass_or_translation_model_exists():
    """A subclass would be a second identity wearing the same name."""

    binding = governance_api.AssessedSystemBinding
    assert binding.__subclasses__() == [], binding.__subclasses__()
    assert governance_api.SystemBindingAuthenticityStatus.__subclasses__() == []


def test_a_binding_built_through_either_api_is_indistinguishable():
    """Same type, equality, canonical bytes and digest — through both doors."""

    digest = hashlib.sha256(b"cfg").hexdigest()
    kwargs = dict(
        binding_id="b",
        tenant_id="t",
        subject_id="s",
        context_id="c",
        context_digest=digest,
        system_id="sys",
        system_version="1",
        configuration_id="cfg",
        configuration_digest=digest,
    )
    via_readiness = readiness_api.AssessedSystemBinding(**kwargs)
    via_governance = governance_api.AssessedSystemBinding(**kwargs)

    assert type(via_readiness) is type(via_governance)
    assert via_readiness == via_governance
    assert dataclasses.asdict(via_readiness) == dataclasses.asdict(via_governance)
    assert via_readiness.canonical_digest() == via_governance.canonical_digest()
    assert isinstance(via_readiness, governance_api.AssessedSystemBinding)


# --------------------------------------------------------------------------- #
# 4-6. Dependency direction and the cycle proof
# --------------------------------------------------------------------------- #
def test_governance_contracts_imports_no_uvi_readiness_authority_or_risk_package():
    offenders = {}
    for path in _sources(GOVERNANCE_ROOT):
        bad = _import_roots(path) & UVI_AND_HIGHER
        if bad:
            offenders[str(path.relative_to(GOVERNANCE_ROOT))] = sorted(bad)
    assert not offenders, offenders


def test_the_system_identity_module_imports_only_the_standard_library():
    """Neutrality is what makes the shared placement cycle-free."""

    module = GOVERNANCE_ROOT / "contracts" / "system_identity.py"
    import sys

    stdlib = set(getattr(sys, "stdlib_module_names", set()))
    strays = _import_roots(module) - stdlib - {"__future__"}
    assert not strays, strays


def test_every_binding_field_is_a_platform_neutral_primitive():
    """No UVI type is embedded, so no cycle can ever be introduced by a field."""

    from datetime import datetime
    from typing import get_args, get_origin, get_type_hints

    hints = get_type_hints(governance_api.AssessedSystemBinding)
    allowed = {str, datetime, type(None)}
    for field in dataclasses.fields(governance_api.AssessedSystemBinding):
        annotation = hints[field.name]
        parts = set(get_args(annotation)) if get_origin(annotation) is not None else {annotation}
        assert parts <= allowed, (field.name, annotation)


def test_readiness_consumes_only_the_governance_public_api():
    """No governance internal is reached into from the readiness tree."""

    offenders = {}
    for path in _sources(READINESS_ROOT):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and not node.level:
                if node.module.split(".")[0] != "ugence_governance_contracts":
                    continue
                if node.module not in {
                    "ugence_governance_contracts",
                    "ugence_governance_contracts.api",
                }:
                    offenders.setdefault(
                        str(path.relative_to(READINESS_ROOT)), []
                    ).append(node.module)
    assert not offenders, offenders


def test_no_dependency_cycle_exists_between_the_two_packages():
    """One arrow: readiness -> governance. Nothing points back."""

    readiness_imports_governance = any(
        "ugence_governance_contracts" in _import_roots(p) for p in _sources(READINESS_ROOT)
    )
    governance_imports_readiness = any(
        "ugence_agent_value_readiness" in _import_roots(p) for p in _sources(GOVERNANCE_ROOT)
    )
    assert readiness_imports_governance
    assert not governance_imports_readiness


# --------------------------------------------------------------------------- #
# 7-8. Nothing unratified was pulled in by the move
# --------------------------------------------------------------------------- #
def test_no_system_manifest_was_added_to_either_package():
    for root in (GOVERNANCE_ROOT, READINESS_ROOT):
        for path in _sources(root):
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    assert "systemmanifest" not in node.name.lower(), (path.name, node.name)
    for surface in (governance_api.__all__, readiness_api.__all__):
        for name in surface:
            assert "systemmanifest" not in name.lower().replace("_", ""), name


def test_no_risk_authority_or_pr1432_contract_is_imported_by_either_package():
    """The RA subject binding stays additive: an opaque token, never an import."""

    banned_roots = {"risk_authority", "ugence_risk_authority"}
    banned_names = ("subjectcontext", "subjectbinding", "subjectriskevaluationrequest")
    for root in (GOVERNANCE_ROOT, READINESS_ROOT):
        for path in _sources(root):
            assert not (_import_roots(path) & banned_roots), path.name
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    flat = node.name.lower().replace("_", "")
                    for banned in banned_names:
                        assert banned not in flat, (path.name, node.name)


def test_the_subject_context_reference_remains_an_opaque_string_token():
    hints = {f.name: f for f in dataclasses.fields(governance_api.AssessedSystemBinding)}
    assert "canonical_subject_context_ref" in hints
    digest = hashlib.sha256(b"x").hexdigest()
    b = governance_api.AssessedSystemBinding(
        binding_id="b", tenant_id="t", subject_id="s", context_id="c",
        context_digest=digest, system_id="sys", system_version="1",
        configuration_id="cfg", configuration_digest=digest,
        canonical_subject_context_ref="risk-subject-context-1:opaque",
    )
    assert isinstance(b.canonical_subject_context_ref, str)


# --------------------------------------------------------------------------- #
# 9-10. The evaluator and the RA-01 ruling are untouched by the move
# --------------------------------------------------------------------------- #
def test_the_evaluator_source_mentions_no_binding_catalog_or_cardinality():
    for name in ("evaluator.py", "case.py", "codes.py", "trace.py", "errors.py"):
        text = (READINESS_ROOT / "evaluation" / name).read_text().lower()
        assert "catalog" not in text, name
        assert "assessedsystembinding" not in text.replace("_", ""), name
        assert "system_binding" not in text, name


def test_no_family_count_heuristic_exists_in_either_package():
    for root in (GOVERNANCE_ROOT, READINESS_ROOT):
        for path in _sources(root):
            text = path.read_text()
            assert "len(self.families_present)" not in text, path.name
            assert "len(catalogs.catalogs)" not in text, path.name
            tree = ast.parse(text, filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Compare):
                    for comparator in node.comparators:
                        if isinstance(comparator, ast.Constant) and comparator.value == 3:
                            raise AssertionError(f"{path.name}:{node.lineno} compares against 3")


# --------------------------------------------------------------------------- #
# 11-12. Replay and authenticity survive the move
# --------------------------------------------------------------------------- #
def _binding(**kw):
    digest = hashlib.sha256(b"cfg").hexdigest()
    base = dict(
        binding_id="b", tenant_id="t", subject_id="s", context_id="c",
        context_digest=digest, system_id="sys", system_version="1",
        configuration_id="cfg", configuration_digest=digest,
    )
    base.update(kw)
    return governance_api.AssessedSystemBinding(**base)


@pytest.mark.parametrize(
    "kw",
    [
        {"system_version": "2"},
        {"configuration_id": "cfg-b"},
        {"configuration_digest": hashlib.sha256(b"other").hexdigest()},
        {"tenant_id": "other-tenant"},
        {"subject_id": "other-subject"},
        {"context_digest": hashlib.sha256(b"other-ctx").hexdigest()},
    ],
)
def test_cross_system_and_cross_tenant_replay_remains_detectable(kw):
    assert _binding().canonical_digest() != _binding(**kw).canonical_digest()


def test_binding_authenticity_remains_non_forgeable():
    b = _binding()
    assert b.authenticity_verified is False
    assert (
        b.authenticity_status
        is governance_api.SystemBindingAuthenticityStatus.STRUCTURAL_UNVERIFIED
    )
    field_names = {f.name for f in dataclasses.fields(governance_api.AssessedSystemBinding)}
    assert "authenticity_status" not in field_names
    assert "authenticity_verified" not in field_names
    with pytest.raises(TypeError):
        _binding(authenticity_status="AUTHORITY_VERIFIED")
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        setattr(b, "authenticity_verified", True)
    assert [m.value for m in governance_api.SystemBindingAuthenticityStatus] == [
        "STRUCTURAL_UNVERIFIED"
    ]


# --------------------------------------------------------------------------- #
# 13. Moving the type changed neither its canonical bytes nor its digest
# --------------------------------------------------------------------------- #
#: Captured from PR #1439 head 4582cec4, where the class still lived at
#: ``ugence_agent_value_readiness.contracts.binding``. The move must not perturb
#: one byte of the serialization.
PRE_CORRECTION_CANONICAL_BYTES = (
    '{"binding_id":"bind-1","canonical_subject_context_ref":"","configuration_digest":'
    '"b8d582270bcab6ca49bc8ef3b9916fa6f77fd84a35be1c1d884eec31746a29a6","configuration_id":'
    '"cfg-prod-a","context_digest":'
    '"baba834176cee0f39f8dc6e4a29d7c5afe1861e6b410c3ed9acb538a795d2fdf","context_id":"ctx1",'
    '"deployment_environment_ref":"","effective_from":null,"effective_to":null,"subject_id":'
    '"a1","system_id":"agent-sys-1","system_manifest_digest":"","system_manifest_ref":"",'
    '"system_version":"1.4.2","tenant_id":"t1"}'
)
PRE_CORRECTION_DIGEST = "cdbafaaba667b4496f309d01ba7c75788033f68f93d8042ab311f39ddc50b43d"
PRE_CORRECTION_FIELD_ORDER = [
    "binding_id",
    "tenant_id",
    "subject_id",
    "context_id",
    "context_digest",
    "system_id",
    "system_version",
    "configuration_id",
    "configuration_digest",
    "canonical_subject_context_ref",
    "system_manifest_ref",
    "system_manifest_digest",
    "deployment_environment_ref",
    "effective_from",
    "effective_to",
]


def _pre_correction_binding():
    return governance_api.AssessedSystemBinding(
        binding_id="bind-1",
        tenant_id="t1",
        subject_id="a1",
        context_id="ctx1",
        context_digest="baba834176cee0f39f8dc6e4a29d7c5afe1861e6b410c3ed9acb538a795d2fdf",
        system_id="agent-sys-1",
        system_version="1.4.2",
        configuration_id="cfg-prod-a",
        configuration_digest="b8d582270bcab6ca49bc8ef3b9916fa6f77fd84a35be1c1d884eec31746a29a6",
    )


def test_the_canonical_bytes_are_byte_identical_to_the_pre_correction_head():
    import json

    payload = dataclasses.asdict(_pre_correction_binding())
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    assert encoded == PRE_CORRECTION_CANONICAL_BYTES


def test_the_digest_is_byte_identical_to_the_pre_correction_head():
    assert _pre_correction_binding().canonical_digest() == PRE_CORRECTION_DIGEST


def test_the_dataclass_field_order_is_unchanged_by_the_move():
    assert [
        f.name for f in dataclasses.fields(governance_api.AssessedSystemBinding)
    ] == PRE_CORRECTION_FIELD_ORDER


# --------------------------------------------------------------------------- #
# 14. No behavioural orchestration field moved
# --------------------------------------------------------------------------- #
#: Captured from the same pre-correction head, over a full orchestrated
#: assessment (see the PR body's digest-invariance table). If the move had
#: perturbed any behavioural field, one of these would differ.
PRE_CORRECTION_ORCHESTRATION = {
    "request_digest": "7467b74b7f49613ced3133f1c61a05a81969cfe3238056bfc35efe652a67f6a1",
    "outcome_digest": "60f76504b3288a095d5a069e4c1a0e05dda63ac06ab789c0456373c468ff5974",
    "orchestration_trace_digest": (
        "7bd339df77280cc767517b083479c95e5845186758f6b4ea6941b8f413d64aeb"
    ),
    "evaluation_digest": "e969275c62a241503894b9efcc6aa0eb5df206f5afaf169243856e206b2db0f8",
    "determination_digest": (
        "43674272f2451917e1a93d93a5bc7dad5eeb2243aea97bbb93174d90b1056b74"
    ),
    "catalog_set_digest": "4ce633279c004f7bebd527d51ccf7905c10ceda476d25d41c9537356259a663d",
    "classification": "DEPLOYMENT_READY",
}


def test_a_full_orchestrated_assessment_is_unchanged_in_every_behavioural_field():
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "orchestration"))
    from _orchestration_fixtures import (  # noqa: E402
        BOTH,
        MANDATORY,
        StubConditionVerifier,
        StubGateVerifier,
        binding,
        context,
        gate,
        gate_result,
        issued_resolver,
        readiness_policy,
        request,
    )
    from ugence_agent_value_readiness.api import GateStatus, assess_readiness

    policy = readiness_policy(gates=(gate("g1", MANDATORY, BOTH),))
    ctx = context(policy)
    req = request(
        policy=policy,
        ctx=ctx,
        system_binding=binding(ctx=ctx),
        gate_results=(gate_result(policy, "g1", GateStatus.PASS),),
        with_indicators=True,
    )
    outcome = assess_readiness(
        req,
        policy_resolver=issued_resolver(policy),
        gate_verifier=StubGateVerifier(),
        condition_verifier=StubConditionVerifier(),
    )

    actual = {
        "request_digest": req.canonical_digest(),
        "outcome_digest": outcome.canonical_digest(),
        "orchestration_trace_digest": outcome.trace.canonical_digest(),
        "evaluation_digest": outcome.evaluation.canonical_digest(),
        "determination_digest": outcome.evaluation.determination.canonical_digest(),
        "catalog_set_digest": req.indicator_catalogs.canonical_digest(),
        "classification": outcome.classification.value,
    }
    assert actual == PRE_CORRECTION_ORCHESTRATION
