"""The mapping is **referenced**, never carried.

Carries three of the owner's nine required proofs: **no D1/D3/D4/D5 structures or
semantics are present**, **no mapping content is embedded**, and **no sentinel or
placeholder mapping coordinate is accepted**.

The first two are asserted over the AST rather than over the source text. A substring
ban would have been satisfiable by deleting the prose that states the property — the
README and the error docstrings say "D1, D3, D4 and D5" precisely *because* those are
what Stage 1 excludes, and a test that failed on that would push the documentation out
rather than the content.
"""

from __future__ import annotations

import ast
import dataclasses
import pathlib

import pytest

import _change_effect_policy_fixtures as fx
import ugence_change_effect_policy as pkg
from ugence_policy_authority.api import PolicyCoordinate
from ugence_change_effect_policy import MappingCoordinateRefused

SRC = pathlib.Path(pkg.__file__).resolve().parent
MODULES = sorted(SRC.glob("*.py"))

#: What a D-entry would be spelled as if it were *data* rather than prose. Prose says
#: "D1, D3, D4 and D5" inside a sentence; a table says ``"D1"``.
_D_ENTRY_TOKENS = frozenset({"D1", "D2", "D3", "D4", "D5", "D6"})

#: Names a mapping-content structure would have to bind itself to in order to exist.
_CONTENT_NAME_FRAGMENTS = (
    "obligation_to_effect",
    "obligationtoeffect",
    "required_primitive",
    "requiredprimitive",
    "effect_rule",
    "closure_bundle",
    "closurebundle",
    "bundle_mapping",
    "predicate",
)


def _trees() -> list[tuple[pathlib.Path, ast.Module]]:
    return [(path, ast.parse(path.read_text(encoding="utf-8"))) for path in MODULES]


def _docstring_nodes(tree: ast.Module) -> set[int]:
    """Every string node that is a docstring, by identity, so prose is excluded."""

    found: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                found.add(id(body[0].value))
    return found


# --------------------------------------------------------------------------------------
# Required proof: no D1/D3/D4/D5 structures or semantics are present
# --------------------------------------------------------------------------------------


def test_no_d_entry_appears_as_data_anywhere_in_the_package() -> None:
    """A bare ``"D1"`` string constant is a table key. Nothing here has one.

    Comments and docstrings are excluded deliberately; a D-entry mentioned in a sentence
    is documentation of an exclusion, while a D-entry standing alone as a value is the
    exclusion being violated.
    """

    offenders = []
    for path, tree in _trees():
        docstrings = _docstring_nodes(tree)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in docstrings
                and node.value.strip() in _D_ENTRY_TOKENS
            ):
                offenders.append(f"{path.name}:{node.lineno} {node.value!r}")
    assert offenders == [], f"D-entry carried as data: {offenders}"


def test_no_binding_in_the_package_is_named_for_a_d_entry() -> None:
    """No class, function, field, constant or argument named ``D1`` and friends."""

    offenders = []
    for path, tree in _trees():
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                names.append(node.name)
            elif isinstance(node, ast.Name):
                names.append(node.id)
            elif isinstance(node, ast.arg):
                names.append(node.arg)
            elif isinstance(node, ast.Attribute):
                names.append(node.attr)
            for name in names:
                if name.upper() in _D_ENTRY_TOKENS:
                    offenders.append(f"{path.name}:{node.lineno} {name}")
    assert offenders == [], f"D-entry bound as a name: {offenders}"


def test_no_mapping_content_structure_is_named_or_defined() -> None:
    """No obligation-to-effect rule, required-primitive table or predicate, by name.

    Checked over defined names rather than over text, and the exclusions are the
    definitions themselves — ``MAPPING_POLICY_FAMILY`` names the family a *coordinate*
    must point at, and the error class names the refusal.
    """

    allowed = {"MAPPING_POLICY_FAMILY", "MappingCoordinateRefused", "mapping_coordinate"}
    offenders = []
    for path, tree in _trees():
        for node in ast.walk(tree):
            name = None
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                name = node.name
            elif isinstance(node, ast.arg):
                name = node.arg
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                name = node.id
            if name is None or name in allowed:
                continue
            lowered = name.lower()
            if any(fragment in lowered for fragment in _CONTENT_NAME_FRAGMENTS):
                offenders.append(f"{path.name}:{node.lineno} {name}")
    assert offenders == [], f"mapping-content structure defined: {offenders}"


def test_the_package_defines_no_callable_that_could_evaluate_a_rule() -> None:
    """No lambda, no ``eval``/``exec``/``compile``, no dynamic import.

    An executable predicate has to be built out of one of these, and none is here.
    """

    banned_calls = {"eval", "exec", "compile", "__import__", "importlib"}
    offenders = []
    for path, tree in _trees():
        for node in ast.walk(tree):
            if isinstance(node, ast.Lambda):
                offenders.append(f"{path.name}:{node.lineno} lambda")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in banned_calls:
                    offenders.append(f"{path.name}:{node.lineno} {node.func.id}()")
    assert offenders == [], f"an evaluation seam exists: {offenders}"


# --------------------------------------------------------------------------------------
# Required proof: no mapping content is embedded
# --------------------------------------------------------------------------------------


def test_the_coordinate_is_identity_only_and_carries_no_content() -> None:
    """Six identity components and nothing else — no rules, table or bundle rides in."""

    assert [f.name for f in dataclasses.fields(PolicyCoordinate)] == [
        "policy_family",
        "policy_id",
        "version",
        "content_digest",
        "scope",
        "tenant_id",
    ]


def test_the_canonical_projection_carries_the_coordinate_and_no_mapping_content() -> None:
    """The structural form of "referenced, not carried".

    What reaches the digest under ``mapping_coordinate`` is exactly the six identity
    components. There is no path by which mapping content could ride along, because
    there is no field for it to ride in.
    """

    descriptor = pkg.ChangeEffectPolicyFamilyAdapter().describe(fx.operative_policy())
    projected = descriptor.canonical_projection["mapping_coordinate"]
    assert set(projected) == {
        "policy_family",
        "policy_id",
        "version",
        "content_digest",
        "scope",
        "tenant_id",
    }


def test_the_package_exports_no_mapping_artifact_type() -> None:
    """The family constant names a family this package cannot construct an artifact for."""

    assert pkg.MAPPING_POLICY_FAMILY == "change_effect.closure_bundle_mapping"
    artifact_types = [
        name
        for name in pkg.__all__
        if isinstance(getattr(pkg, name), type)
        and not issubclass(getattr(pkg, name), BaseException)
        and "mapping" in name.lower()
    ]
    assert artifact_types == []


def test_the_artifact_holds_the_coordinate_object_itself_not_a_copy_of_its_content() -> None:
    coordinate = fx.mapping_coordinate()
    artifact = fx.operative_policy(mapping_coordinate=coordinate)
    assert artifact.mapping_coordinate is coordinate


# --------------------------------------------------------------------------------------
# Required proof: no sentinel or placeholder mapping coordinate is accepted
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "token", ["TBD", "todo", "none", "PLACEHOLDER", "pending", "unknown", "n/a", "xxx"]
)
def test_a_sentinel_policy_id_is_refused(token: str) -> None:
    with pytest.raises(MappingCoordinateRefused):
        fx.operative_policy(mapping_coordinate=fx.mapping_coordinate(policy_id=token))


@pytest.mark.parametrize("token", ["TBD", "unset", "placeholder", "none"])
def test_a_sentinel_version_is_refused(token: str) -> None:
    with pytest.raises(MappingCoordinateRefused):
        fx.operative_policy(mapping_coordinate=fx.mapping_coordinate(version=token))


@pytest.mark.parametrize("char", ["0", "a", "f"])
def test_a_fabricated_repeated_character_digest_is_refused(char: str) -> None:
    with pytest.raises(MappingCoordinateRefused):
        fx.operative_policy(
            mapping_coordinate=fx.mapping_coordinate(content_digest=char * 64)
        )


def test_a_coordinate_naming_the_wrong_family_is_refused() -> None:
    """A reference to the wrong thing is not better than a reference to nothing."""

    with pytest.raises(MappingCoordinateRefused):
        fx.operative_policy(
            mapping_coordinate=fx.mapping_coordinate(
                policy_family="change_effect.classification_policy"
            )
        )


def test_a_refused_coordinate_cannot_be_laundered_through_a_draft_artifact() -> None:
    """The sentinel refusal is unconditional, not gated on the lifecycle state.

    Otherwise a placeholder could be parked in a draft and promoted later by a state
    change that never re-examined it.
    """

    with pytest.raises(MappingCoordinateRefused):
        fx.policy(mapping_coordinate=fx.mapping_coordinate(policy_id="TBD"))


def test_a_real_coordinate_is_accepted_so_the_refusals_are_discriminating() -> None:
    """Without this, every refusal above would pass on a package that refused all."""

    artifact = fx.operative_policy()
    assert artifact.mapping_coordinate is not None
    assert artifact.mapping_coordinate.policy_family == pkg.MAPPING_POLICY_FAMILY
