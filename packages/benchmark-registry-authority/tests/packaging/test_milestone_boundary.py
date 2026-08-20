"""BR-2A stops where the ratification says it stops — asserted, not promised."""

from __future__ import annotations

import ast
import inspect
import pathlib
import re

import pytest

from _milestones import (
    SUBPHASE_LADDER,
    VERSION_SUBPHASE,
    banned_capability_tokens,
)

import ugence_benchmark_registry_authority as pkg
from ugence_benchmark_registry_authority import api

PKG = pathlib.Path(__file__).resolve().parents[2]
SRC = PKG / "src" / "ugence_benchmark_registry_authority"

#: Every capability §05 forbids, as the name a class or function would carry,
#: mapped to the subphase that may **first** ship it — D-19's milestone-
#: conditional form.
#:
#: ``None`` means **permanently banned, at every subphase**, and those entries
#: are not deferrals: D-07 rules that no convenience resolver or selection API
#: exists *ever*, and D-10 puts supersession out of BR-2 scope entirely. Folding
#: those into "not yet" would quietly convert a permanent prohibition into a
#: schedule, which is the exact weakening this restructuring must not perform.
FORBIDDEN_CAPABILITY_UNLOCK = {
    "admissionengine": "BR-2D",
    "admission_engine": "BR-2D",
    "registryengine": "BR-2D",
    "storage": "BR-2D",
    "store_impl": "BR-2D",
    "signatureverifier": "BR-2C",
    "signature_verifier": "BR-2C",
    "keyparser": "BR-2C",
    "key_parser": "BR-2C",
    "trustanchorstore": "BR-2C",
    "trust_anchor_store": "BR-2C",
    "approvalverifier": "BR-2C",
    "approval_verifier": "BR-2C",
    "resolverimpl": "BR-2D",
    "resolver_impl": "BR-2D",
    "convenienceresolver": None,
    "selectionapi": None,
    "selection_api": None,
    "supersessionengine": None,
    "adapterregistry": "BR-2D",
    "adapter_registry": "BR-2D",
    "identityallowlist": "BR-2D",
    "identity_allow_list": "BR-2D",
    "productioncompositionroot": "BR-2D",
    "production_composition_root": "BR-2D",
}

#: The exact token set BR-2A froze. Pinned separately from the map above so a
#: restructuring cannot drop an entry unnoticed: a token that vanished from the
#: map would simply stop being checked, and nothing else would fail.
BR2A_FROZEN_CAPABILITY_TOKENS = frozenset(
    {
        "admissionengine",
        "admission_engine",
        "registryengine",
        "storage",
        "store_impl",
        "signatureverifier",
        "signature_verifier",
        "keyparser",
        "key_parser",
        "trustanchorstore",
        "trust_anchor_store",
        "approvalverifier",
        "approval_verifier",
        "resolverimpl",
        "resolver_impl",
        "convenienceresolver",
        "selectionapi",
        "selection_api",
        "supersessionengine",
        "adapterregistry",
        "adapter_registry",
        "identityallowlist",
        "identity_allow_list",
        "productioncompositionroot",
        "production_composition_root",
    }
)


#: The tokens banned at the subphase this distribution currently is.
FORBIDDEN_CAPABILITY_TOKENS = tuple(
    sorted(
        banned_capability_tokens(
            VERSION_SUBPHASE[api.__version__], FORBIDDEN_CAPABILITY_UNLOCK
        )
    )
)


def test_happy_the_package_version_is_the_br2b_version():
    assert api.__version__ == "0.2.0"


# --------------------------------------------------------------------------- #
# D-19: the bans became milestone-conditional. They did not become weaker.
# --------------------------------------------------------------------------- #
def test_the_effective_ban_set_is_exactly_what_br2a_froze():
    """The whole point of the restructuring: nothing unlocks at BR-2B.

    D-19 makes the capability bans milestone-conditional. This asserts the
    change is structural rather than permissive — at this version the effective
    ban set must equal BR-2A's frozen set **exactly**, in both directions. A
    token that quietly acquired an already-reached unlock phase would show up
    here as a missing element, not as a silently passing suite.
    """

    assert FORBIDDEN_CAPABILITY_TOKENS != ()
    assert set(FORBIDDEN_CAPABILITY_TOKENS) == BR2A_FROZEN_CAPABILITY_TOKENS


def test_every_frozen_token_still_carries_an_unlock_ruling():
    """A token dropped from the map would simply stop being checked."""

    assert set(FORBIDDEN_CAPABILITY_UNLOCK) == BR2A_FROZEN_CAPABILITY_TOKENS


def test_no_capability_unlocks_at_br2b_at_all():
    assert banned_capability_tokens("BR-2B", FORBIDDEN_CAPABILITY_UNLOCK) == (
        BR2A_FROZEN_CAPABILITY_TOKENS
    )


def test_the_permanent_bans_never_unlock_at_any_subphase():
    """D-07 and D-10 are prohibitions, not deferrals.

    No convenience resolver and no selection API exists ever (D-07); supersession
    is out of BR-2 scope entirely (D-10). Folding those into "not yet" would
    convert a permanent ruling into a schedule.
    """

    permanent = {
        token
        for token, unlock in FORBIDDEN_CAPABILITY_UNLOCK.items()
        if unlock is None
    }
    assert permanent == {
        "convenienceresolver",
        "selectionapi",
        "selection_api",
        "supersessionengine",
    }
    for subphase in SUBPHASE_LADDER:
        still = banned_capability_tokens(subphase, FORBIDDEN_CAPABILITY_UNLOCK)
        assert permanent <= still, subphase


def test_every_unlock_phase_named_is_a_real_subphase():
    for token, unlock in FORBIDDEN_CAPABILITY_UNLOCK.items():
        assert unlock is None or unlock in SUBPHASE_LADDER, token


def test_no_capability_is_scheduled_to_unlock_at_or_before_this_version():
    """An unlock in the past would be a ban this release already lifted."""

    reached = SUBPHASE_LADDER.index(VERSION_SUBPHASE[api.__version__])
    for token, unlock in FORBIDDEN_CAPABILITY_UNLOCK.items():
        if unlock is None:
            continue
        assert SUBPHASE_LADDER.index(unlock) > reached, token


def _is_port_declaration(name: str, value) -> bool:
    """A ``...Port`` Protocol declares a seam; it does not implement one.

    ``BenchmarkApprovalVerifierPort`` names the shape a verifier must fit, and
    ``test_confusable_and_ports.py`` proves nothing in this package fits it. The
    capability ban is on implementations, so port declarations are exempt — and
    the exemption is narrow: the name must end in ``Port`` *and* the object must
    actually be a Protocol.

    ``value`` has no default. A default let the source-tree caller — which holds
    an AST node rather than an object — exempt **any** name ending in ``Port``
    without ever checking Protocol-ness, so a concrete, instantiable class
    called ``...Port`` passed the tree-wide capability ban. That caller now uses
    :func:`_is_inert_port_protocol_node`, which establishes the same fact
    structurally, and this signature makes the unchecked call unwritable.
    """

    return name.endswith("Port") and bool(getattr(value, "_is_protocol", False))


def _is_inert_port_protocol_node(node) -> bool:
    """The AST equivalent of :func:`_is_port_declaration` — verified, not assumed.

    A live object can be asked ``_is_protocol``; a source-tree scan walks ``ast``
    nodes and has nothing to ask, so it establishes the same three facts
    structurally: the node is a **class** whose name ends in ``Port``,
    ``Protocol`` is among its bases, and every method body is ``...``.

    A function is never exempt, whatever it is called, and neither is a class
    that merely ends in ``Port`` while carrying a real body — which is exactly
    what a concrete in-memory store or approval verifier would be.
    """

    if not isinstance(node, ast.ClassDef) or not node.name.endswith("Port"):
        return False
    bases = {
        base.id if isinstance(base, ast.Name) else getattr(base, "attr", "")
        for base in node.bases
    }
    if "Protocol" not in bases:
        return False
    for child in node.body:
        if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = [
            stmt
            for stmt in child.body
            if not (
                isinstance(stmt, ast.Expr)
                and isinstance(stmt.value, ast.Constant)
                and isinstance(stmt.value.value, str)
            )
        ]
        if len(body) != 1:
            return False
        only = body[0]
        if not (
            isinstance(only, ast.Expr)
            and isinstance(only.value, ast.Constant)
            and only.value.value is Ellipsis
        ):
            return False
    return True


def test_no_forbidden_capability_is_exported():
    for symbol in pkg.__all__:
        if _is_port_declaration(symbol, getattr(pkg, symbol)):
            continue
        lowered = symbol.lower().replace("_", "")
        for token in FORBIDDEN_CAPABILITY_TOKENS:
            assert token.replace("_", "") not in lowered, symbol


def test_every_port_named_symbol_really_is_an_inert_protocol():
    """The exemption above cannot be used to smuggle an implementation in."""

    for symbol in pkg.__all__:
        if symbol.endswith("Port"):
            value = getattr(pkg, symbol)
            assert getattr(value, "_is_protocol", False), symbol
            with pytest.raises(TypeError):
                value()


def test_no_class_or_function_anywhere_carries_a_forbidden_capability_name():
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                if _is_inert_port_protocol_node(node):
                    continue
                lowered = node.name.lower().replace("_", "")
                for token in FORBIDDEN_CAPABILITY_TOKENS:
                    if token.replace("_", "") in lowered:
                        offenders.append(f"{path.name}: {node.name}")
    assert offenders == [], offenders


def test_the_three_reserved_authority_issued_types_are_undefined():
    for reserved in api.BENCHMARK_RESERVED_AUTHORITY_ISSUED_TYPE_NAMES:
        assert not hasattr(pkg, reserved), reserved
        assert not hasattr(api, reserved), reserved


def test_the_reserved_names_appear_nowhere_as_a_class_definition():
    reserved = set(api.BENCHMARK_RESERVED_AUTHORITY_ISSUED_TYPE_NAMES)
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                assert node.name not in reserved, f"{path.name}: {node.name}"


def test_no_executable_stub_or_todo_backed_runtime_path_exists():
    for path in sorted(SRC.rglob("*.py")):
        code_lines = [
            line
            for line in path.read_text().splitlines()
            if not line.strip().startswith("#")
        ]
        code = "\n".join(code_lines)
        assert "TODO" not in code, path.name
        assert "FIXME" not in code, path.name
        assert "XXX" not in code, path.name


def test_every_test_file_cited_in_the_source_tree_actually_exists():
    """A docstring citing a gate that does not exist is an unverifiable claim.

    These citations ship inside both artifacts, so a consumer reads them as this
    package's own evidence for what is enforced. Four of them named modules that
    a suite reorganization had merged away, and nothing noticed — because
    nothing checked. A claim about a gate is worth exactly what the gate is
    worth, and a missing file is worth nothing.
    """

    missing = []
    for path in sorted(SRC.rglob("*.py")):
        for cited in re.findall(r"tests/[A-Za-z0-9_/]+\.py", path.read_text()):
            if not (PKG / cited).exists():
                missing.append(f"{path.name}: {cited}")
    assert missing == [], missing


def test_no_notimplementederror_pretends_to_be_a_port_implementation():
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Raise) and node.exc is not None:
                target = node.exc
                if isinstance(target, ast.Call):
                    target = target.func
                if isinstance(target, ast.Name):
                    assert target.id != "NotImplementedError", path.name


def test_no_permissive_fallback_or_default_hook_exists_in_the_encoder():
    canonical = (SRC / "contracts" / "canonical.py").read_text()
    code = canonical.split('"""', 2)[-1]
    assert "default=" not in code
    assert "except Exception" not in code
    assert "pass  # " not in code


def test_no_boolean_capability_field_exists_on_any_public_contract():
    """D-15: an unavailable guarantee is never a flippable Boolean."""

    import dataclasses

    for symbol in pkg.__all__:
        value = getattr(pkg, symbol)
        if not (inspect.isclass(value) and dataclasses.is_dataclass(value)):
            continue
        for f in dataclasses.fields(value):
            assert f.type is not bool, f"{symbol}.{f.name}"
            assert not f.name.startswith("is_"), f"{symbol}.{f.name}"
            assert not f.name.startswith("enable"), f"{symbol}.{f.name}"
            assert not f.name.startswith("allow"), f"{symbol}.{f.name}"


def test_no_dormant_or_reserved_future_field_exists():
    import dataclasses

    banned = ("reserved", "future", "unused", "placeholder", "todo", "tbd",
              "extension", "metadata", "extra")
    for symbol in pkg.__all__:
        value = getattr(pkg, symbol)
        if not (inspect.isclass(value) and dataclasses.is_dataclass(value)):
            continue
        for f in dataclasses.fields(value):
            for token in banned:
                assert token not in f.name.lower(), f"{symbol}.{f.name}"


def test_nothing_in_the_package_performs_cryptography():
    banned_calls = ("hmac", "sign", "verify_signature", "ed25519", "x25519")
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id.lower() not in banned_calls, path.name


def test_the_only_hash_used_is_sha256_over_canonical_bytes():
    canonical = (SRC / "contracts" / "canonical.py").read_text()
    assert "hashlib.sha256" in canonical
    for other in ("md5", "sha1(", "sha512", "blake2"):
        assert other not in canonical


def test_no_module_outside_canonical_computes_a_digest():
    """One encoder, one digest path — enforced structurally."""

    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        if path.name == "canonical.py":
            continue
        if "hashlib" in path.read_text():
            offenders.append(path.name)
    assert offenders == [], offenders


def test_no_json_serialization_happens_outside_the_encoder():
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        if path.name == "canonical.py":
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "json":
                        offenders.append(path.name)
    assert offenders == [], offenders


@pytest.mark.parametrize(
    "capability",
    [
        "register",
        "admit",
        "resolve",
        "lookup",
        "revoke",
        "append",
        "claim_slot",
        "verify",
        "sign",
        "now",
        "read",
        "write",
        "persist",
    ],
)
def test_no_module_level_function_performs_a_registry_operation(capability):
    """Pure validation only: nothing in the package *does* anything."""

    offenders = []
    for symbol in pkg.__all__:
        value = getattr(pkg, symbol)
        if inspect.isfunction(value) and value.__name__.startswith(capability):
            offenders.append(symbol)
    assert offenders == [], offenders


#: Exported-function prefixes, mapped to the subphase that introduced each —
#: D-19's milestone-scoped allow-list. BR-2B adds ``plan_`` and nothing else,
#: chosen so no verb implies an authoritative act: a plan states what *would be*
#: admissible. The registry-operation ban below is untouched by this.
EXPORTED_FUNCTION_PREFIX_ORIGIN = {
    "require_": "BR-2A",
    "is_": "BR-2A",
    "canonical_": "BR-2A",
    "bound_": "BR-2A",
    "fault_": "BR-2A",
    "plan_": "BR-2B",
}


def test_every_exported_function_is_a_validator_a_reader_or_a_planner():
    allowed_prefixes = tuple(EXPORTED_FUNCTION_PREFIX_ORIGIN)
    for symbol in pkg.__all__:
        value = getattr(pkg, symbol)
        if inspect.isfunction(value):
            assert symbol.startswith(allowed_prefixes), symbol


def test_no_exported_function_prefix_arrives_before_its_subphase():
    """A prefix may not be introduced by a subphase this release has not reached."""

    reached = SUBPHASE_LADDER.index(VERSION_SUBPHASE[api.__version__])
    for prefix, origin in EXPORTED_FUNCTION_PREFIX_ORIGIN.items():
        assert SUBPHASE_LADDER.index(origin) <= reached, prefix


def test_br2b_added_exactly_one_verb_and_it_implies_no_authoritative_act():
    added = {
        prefix
        for prefix, origin in EXPORTED_FUNCTION_PREFIX_ORIGIN.items()
        if origin == "BR-2B"
    }
    assert added == {"plan_"}
    # The registry-operation ban is what keeps the new verb honest: a function
    # named plan_register would still be refused by the parametrized ban above.
    for banned in ("register", "admit", "resolve", "revoke", "append", "verify"):
        assert not any(prefix.startswith(banned) for prefix in added)


# --------------------------------------------------------------------------- #
# BR-2B plans. It does not apply plans.
# --------------------------------------------------------------------------- #
def _annotation_names(annotation) -> set:
    """Every identifier appearing in a parameter annotation, however spelled."""

    if annotation is inspect.Parameter.empty:
        return set()
    text = annotation if isinstance(annotation, str) else repr(annotation)
    return set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text))


def test_no_exported_callable_accepts_a_transition_plan_as_input():
    """A plan is an output of this package and an input to nothing in it.

    This is the structural half of "BR-2B may determine what transition would be
    valid; BR-2D is the first phase permitted to assert that one occurred". A
    function that consumed a plan would be the seam through which applying,
    committing, appending, admitting, registering, revoking or resolving one
    could later arrive — so no exported callable takes it as a parameter at all,
    and no consumer can be handed a signature that invites it.
    """

    offenders = []
    for symbol in pkg.__all__:
        value = getattr(pkg, symbol)
        if not callable(value) or inspect.isclass(value):
            continue
        try:
            signature = inspect.signature(value)
        except (TypeError, ValueError):  # pragma: no cover - builtins
            continue
        for name, parameter in signature.parameters.items():
            if "BenchmarkTransitionPlan" in _annotation_names(
                parameter.annotation
            ):
                offenders.append(f"{symbol}({name})")
    assert offenders == [], offenders


def test_no_function_anywhere_in_the_source_tree_takes_a_plan_parameter():
    """The signature check again, over the tree, so a private helper cannot either."""

    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            args = node.args
            every = (
                list(args.posonlyargs)
                + list(args.args)
                + list(args.kwonlyargs)
                + [a for a in (args.vararg, args.kwarg) if a is not None]
            )
            for argument in every:
                if argument.annotation is None:
                    continue
                if "BenchmarkTransitionPlan" in ast.unparse(argument.annotation):
                    offenders.append(f"{path.name}: {node.name}({argument.arg})")
    assert offenders == [], offenders


def test_no_exported_planner_can_return_a_lifecycle_payload():
    """Planning returns a plan or a refusal. It never returns a chain payload.

    Checked on the live return annotation rather than on names, so a function
    that quietly started producing a registry event would fail here even if it
    kept a planning name.
    """

    payload_types = {
        "BenchmarkSubmissionRecordPayload",
        "BenchmarkAdmissionDecisionPayload",
        "BenchmarkPostAdmissionRejectionEventPayload",
        "BenchmarkRegistrationEventPayload",
        "BenchmarkRevocationEventPayload",
        "BenchmarkConflictRecordPayload",
        "BenchmarkResolutionRecordPayload",
        "BenchmarkHistoricalRecordPayload",
    }
    for symbol in pkg.__all__:
        value = getattr(pkg, symbol)
        if not (inspect.isfunction(value) and symbol.startswith("plan_")):
            continue
        returned = _annotation_names(
            inspect.signature(value).return_annotation
        )
        assert returned, symbol
        assert not (returned & payload_types), f"{symbol} -> {returned}"
