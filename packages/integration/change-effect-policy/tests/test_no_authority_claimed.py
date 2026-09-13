"""What this package does not do, held by shapes rather than by discipline.

Carries three of the owner's nine required proofs: **the package never resolves
itself**, **no policy artifact is treated as authorization**, and **no closure,
classification, routing, projection or admission computation exists**.

The strongest available form of the last one is an *exhaustive* statement of the callable
surface rather than a list of banned words: a ban enumerates what someone thought of,
while an exhaustive inventory fails on anything added.
"""

from __future__ import annotations

import ast
import inspect
import pathlib

import pytest

import _change_effect_policy_fixtures as fx
import ugence_change_effect_policy as pkg

SRC = pathlib.Path(pkg.__file__).resolve().parent
MODULES = sorted(SRC.glob("*.py"))


def _trees() -> list[tuple[pathlib.Path, ast.Module]]:
    return [(path, ast.parse(path.read_text(encoding="utf-8"))) for path in MODULES]


# --------------------------------------------------------------------------------------
# Required proof: the package never resolves itself
# --------------------------------------------------------------------------------------


def test_nothing_imports_the_resolution_service() -> None:
    """Resolution is ``resolve_policy`` under configured trust, inside the authority.

    Not imported here, so self-resolution is not a thing the package declines to do; it
    is a thing it holds no means to do.
    """

    forbidden = {
        "resolve_policy",
        "issue_policy",
        "revoke_policy",
        "suspend_policy",
        "reinstate_policy",
        "PolicyRegistry",
        "InMemoryPolicyRegistry",
        "SqlitePolicyRegistry",
        "PolicySigner",
        "Ed25519PolicySigner",
        "PolicyKeyRing",
        "ApprovalVerifier",
        "issuance_signing_payload",
        "revocation_signing_payload",
    }
    offenders = []
    for path, tree in _trees():
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name in forbidden:
                        offenders.append(f"{path.name}:{node.lineno} {alias.name}")
    assert offenders == [], f"an issuance or resolution seam was imported: {offenders}"


def test_the_only_first_party_import_is_the_authoritys_public_api() -> None:
    """One dependency, through its public module. No ``...core`` reach-through."""

    modules = set()
    for _path, tree in _trees():
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                if node.module.startswith("ugence"):
                    modules.add(node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("ugence"):
                        modules.add(alias.name)
    assert modules == {"ugence_policy_authority.api"}


def test_the_package_imports_only_the_contract_types_it_needs() -> None:
    """Pinned by name, so a later widening is a visible edit to this list."""

    imported = set()
    for _path, tree in _trees():
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "ugence_policy_authority.api":
                imported.update(alias.name for alias in node.names)
    assert imported == {
        "PolicyArtifactDescriptor",
        "PolicyAuthorityRequestError",
        "PolicyCoordinate",
        "UnsupportedPolicyArtifactError",
        "to_canonical_obj",
    }


def test_nothing_registers_this_adapter_anywhere() -> None:
    """Wiring is a composition root's act, and Stage 1 performs it nowhere."""

    offenders = []
    for path, tree in _trees():
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = None
                if isinstance(node.func, ast.Attribute):
                    name = node.func.attr
                elif isinstance(node.func, ast.Name):
                    name = node.func.id
                if name in {"register", "register_adapter", "AdapterRegistry"}:
                    offenders.append(f"{path.name}:{node.lineno} {name}")
    assert offenders == [], f"the package registers itself: {offenders}"


def test_the_package_holds_no_store_clock_or_socket() -> None:
    banned = {"socket", "http", "httpx", "requests", "urllib", "sqlite3", "time", "os"}
    offenders = []
    for path, tree in _trees():
        for node in ast.walk(tree):
            roots = []
            if isinstance(node, ast.Import):
                roots += [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                roots.append(node.module.split(".")[0])
            offenders += [f"{path.name}:{node.lineno} {r}" for r in roots if r in banned]
    assert offenders == [], f"an ambient dependency exists: {offenders}"


def test_no_module_holds_mutable_state() -> None:
    """Nothing accumulates, caches or memoizes across calls.

    ``__all__`` is excluded: it is a list by language convention, it is read by the
    import machinery and never appended to, and requiring it to be a tuple would buy
    nothing. Every other module-level binding here is a string, a tuple or a frozenset.
    """

    def is_dunder_all(node) -> bool:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        return any(isinstance(t, ast.Name) and t.id == "__all__" for t in targets)

    offenders = []
    for path, tree in _trees():
        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)) and not is_dunder_all(node):
                value = node.value
                if isinstance(value, (ast.List, ast.Dict, ast.Set)):
                    offenders.append(f"{path.name}:{node.lineno}")
                if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
                    if value.func.id in {"list", "dict", "set"}:
                        offenders.append(f"{path.name}:{node.lineno}")
    assert offenders == [], f"module-level mutable state: {offenders}"


# --------------------------------------------------------------------------------------
# Required proof: no policy artifact is treated as authorization
# --------------------------------------------------------------------------------------


def test_no_exported_callable_claims_a_permission() -> None:
    """A cheap tripwire over callables. The real proof is the exhaustive surface below.

    Restricted to callables on purpose. Applied to every exported name it would flag
    ``ENFORCEMENT_ENABLED``, ``ADMITTED_LIFECYCLE_STATES`` and
    ``LIFECYCLE_APPROVED_ACTIVE`` — three constants that say accurately what they are,
    and one of which exists precisely to record that enforcement is **off**. A test
    answerable by renaming an honest constant is a test that degrades the package.
    """

    banned = (
        "authorize", "authorise", "permit", "grant", "allow", "approve", "admit",
        "enforce", "decide", "verify", "sign", "issue", "resolve", "revoke",
    )
    offenders = [
        name
        for name in pkg.__all__
        if callable(getattr(pkg, name))
        and any(word in name.lower() for word in banned)
    ]
    assert offenders == [], f"an exported callable claims a permission: {offenders}"


def test_the_artifact_exposes_no_decision_method() -> None:
    """An artifact answers about itself. It answers nothing about a change."""

    artifact = fx.operative_policy()
    public = sorted(n for n in dir(artifact) if not n.startswith("_"))
    assert public == [
        "constitution_ref",
        "delegation_table",
        "intent_specification_refs",
        "is_operative",
        "mapping_coordinate",
        "metadata",
        "protected_registries",
    ]


def test_is_operative_is_a_property_not_a_check_that_takes_a_subject() -> None:
    """A decision needs something to decide *about*. This takes nothing.

    A method accepting a delta, a target or a caller would be an authorization boundary
    however it was named; a zero-argument property over two of the artifact's own fields
    cannot be one.
    """

    descriptor = inspect.getattr_static(pkg.ChangeEffectClassificationPolicy, "is_operative")
    assert isinstance(descriptor, property)
    signature = inspect.signature(descriptor.fget)
    assert list(signature.parameters) == ["self"]


def test_an_operative_artifact_still_grants_nothing() -> None:
    """``is_operative is True`` is a property of two fields, not a permission.

    What the artifact yields is a descriptor: identity, a projection and a lifecycle
    label. No token, no capability, no grant, and no statement about any change.
    """

    descriptor = pkg.ChangeEffectPolicyFamilyAdapter().describe(fx.operative_policy())
    assert descriptor.lifecycle_is_active is True
    assert descriptor.lifecycle_label == pkg.ACTIVE_LIFECYCLE_STATE
    for absent in ("token", "grant", "capability", "permission", "decision", "signature"):
        assert not hasattr(descriptor, absent)


def test_an_artifact_is_not_comparable_to_a_permission_by_truthiness() -> None:
    """Both artifacts are truthy, so ``if policy:`` distinguishes nothing.

    Recorded rather than relied on: nothing here invites a truth test, and a caller
    reaching for one has already left the contract. The point is that an inert artifact
    and an operative one are indistinguishable that way, so truthiness can never stand in
    for a permission the package does not issue.
    """

    assert bool(fx.policy()) is True
    assert bool(fx.operative_policy()) is True
    assert fx.policy().is_operative is False


# --------------------------------------------------------------------------------------
# Required proof: no closure, classification, routing, projection or admission computation
# --------------------------------------------------------------------------------------


def test_the_entire_public_callable_surface_is_these_five_things() -> None:
    """Exhaustive, so anything added has to change this list and say what it is.

    * ``change_effect_coordinate`` — maps this family's envelope onto the family-neutral
      coordinate. Identity only.
    * ``ChangeEffectPolicyFamilyAdapter.adapter_id`` — a constant.
    * ``...recognizes`` — exact runtime type match.
    * ``...coordinate_for`` — identity, again.
    * ``...describe`` — identity, a canonical projection, a lifecycle label.

    None of the five takes a change, a delta, a record, a target or a caller. There is
    nothing for a classification, a route, an effect projection, a closure or an
    admission to be computed *from*.
    """

    functions = sorted(
        name for name in pkg.__all__ if inspect.isfunction(getattr(pkg, name))
    )
    assert functions == ["change_effect_coordinate"]

    adapter_methods = sorted(
        name
        for name, _ in inspect.getmembers(
            pkg.ChangeEffectPolicyFamilyAdapter, lambda v: callable(v) or isinstance(v, property)
        )
        if not name.startswith("_")
    )
    assert adapter_methods == ["adapter_id", "coordinate_for", "describe", "recognizes"]


def test_no_exported_callable_accepts_a_change_a_record_or_a_target() -> None:
    """Checked over parameter names across every module, exported or not."""

    banned = {
        "delta", "change", "record", "target", "candidate", "chain", "obligation",
        "closure", "classification", "route", "admission", "effect", "caller",
        "principal", "subject",
    }
    offenders = []
    for path, tree in _trees():
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = node.args
                every = (
                    args.posonlyargs + args.args + args.kwonlyargs
                    + ([args.vararg] if args.vararg else [])
                    + ([args.kwarg] if args.kwarg else [])
                )
                for arg in every:
                    if arg.arg.lower() in banned:
                        offenders.append(f"{path.name}:{node.lineno} {node.name}({arg.arg})")
    assert offenders == [], f"a callable takes a governed subject: {offenders}"


def test_no_module_defines_a_computation_over_the_governed_domain() -> None:
    """No function named for classifying, routing, closing or admitting."""

    banned = (
        "classify", "route", "project_effect", "close", "admit", "evaluate",
        "measure", "sample", "replay", "apply", "revoke", "remediate",
    )
    offenders = []
    for path, tree in _trees():
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                lowered = node.name.lower()
                if any(word in lowered for word in banned):
                    offenders.append(f"{path.name}:{node.lineno} {node.name}")
    assert offenders == [], f"a governed-domain computation exists: {offenders}"


def test_the_package_names_no_record_type_from_the_record_graph() -> None:
    """A policy family must not import or restate the record graph it is about."""

    text = "\n".join(path.read_text(encoding="utf-8") for path in MODULES)
    for record_type in (
        "ClassificationRecord",
        "ConfirmationAmendment",
        "InvestigationRecord",
        "FinalResolutionRecord",
        "AdmissionReservation",
        "AdmissionClaim",
        "AdmissionCompletion",
        "ResolutionRevocationRecord",
        "RevocationImpactRecord",
    ):
        assert record_type not in text, f"{record_type} is named in a policy package"


def test_the_maturity_posture_is_machine_readable_and_inert() -> None:
    assert pkg.MATURITY == "REFERENCE_GRADE_CONTRACT_ONLY"
    assert pkg.ENFORCEMENT_ENABLED is False


def test_the_adapter_recognizes_exactly_its_own_type() -> None:
    """A subclass could add fields this family never validates."""

    adapter = pkg.ChangeEffectPolicyFamilyAdapter()
    assert adapter.recognizes(fx.policy()) is True

    class Widened(pkg.ChangeEffectClassificationPolicy):
        pass

    widened = Widened(
        metadata=fx.metadata(),
        constitution_ref="c",
        intent_specification_refs=("i",),
        protected_registries=fx.registries(),
    )
    assert adapter.recognizes(widened) is False
    with pytest.raises(Exception):
        adapter.describe(widened)
