"""BR-2A stops where the ratification says it stops — asserted, not promised."""

from __future__ import annotations

import ast
import inspect
import json
import pathlib
import re

import pytest

from _boundary import (
    resolved_parameter_types,
    resolved_return_types,
)
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


def test_the_reserved_names_are_bound_by_nothing_anywhere_under_src():
    """Any binding form, every file — not ``class`` statements in two modules.

    The previous version matched ``ast.ClassDef`` only, and checked ``pkg`` and
    ``api`` for attributes. The third audit bound ``BenchmarkRegistrationEvent``
    with ``NewType`` in a contracts module and it was invisible to both: a
    reserved authority-issued name existed, and nothing said so.

    Every way a name can come to exist is collected here — class and function
    definitions, plain and annotated assignment, augmented assignment, walrus,
    ``import``/``from`` aliases, ``for`` targets, ``with ... as``,
    ``except ... as``, ``global``/``nonlocal`` declarations and match captures —
    and none of them may be a reserved name.
    """

    reserved = set(api.BENCHMARK_RESERVED_AUTHORITY_ISSUED_TYPE_NAMES)
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            bound = set()
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                bound.add(node.name)
            elif isinstance(node, ast.Name) and isinstance(
                node.ctx, (ast.Store, ast.Del)
            ):
                bound.add(node.id)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for entry in node.names:
                    bound.add(entry.asname or entry.name.split(".")[0])
            elif isinstance(node, (ast.Global, ast.Nonlocal)):
                bound.update(node.names)
            elif isinstance(node, ast.ExceptHandler) and node.name:
                bound.add(node.name)
            elif isinstance(node, getattr(ast, "MatchAs", ())) and node.name:
                bound.add(node.name)
            elif isinstance(node, getattr(ast, "MatchStar", ())) and node.name:
                bound.add(node.name)
            for name in bound & reserved:
                offenders.append(f"{path.name}: {name}")
    assert offenders == [], offenders


def test_the_reserved_names_resolve_to_nothing_at_runtime():
    """Attribute access on every module, not only ``pkg`` and ``api``."""

    offenders = []
    for module in _package_modules():
        for name in api.BENCHMARK_RESERVED_AUTHORITY_ISSUED_TYPE_NAMES:
            if hasattr(module, name):
                offenders.append(f"{module.__name__}.{name}")
    assert offenders == [], offenders


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
CONTRACTS = SRC / "contracts"
NAMESPACE = "ugence_benchmark_registry_authority"

#: Every lifecycle payload a planner must never return.
LIFECYCLE_PAYLOAD_TYPES = frozenset(
    {
        api.BenchmarkSubmissionRecordPayload,
        api.BenchmarkAdmissionDecisionPayload,
        api.BenchmarkPostAdmissionRejectionEventPayload,
        api.BenchmarkRegistrationEventPayload,
        api.BenchmarkRevocationEventPayload,
        api.BenchmarkConflictRecordPayload,
        api.BenchmarkResolutionRecordPayload,
        api.BenchmarkHistoricalRecordPayload,
    }
)


def _package_modules():
    """Every module whose source text lives under ``src/``, imported.

    **The scanned path decides membership, not the code object.** An earlier
    version asked each function where its code came from — ``__code__
    .co_filename`` — and exempted anything outside ``contracts/``. That value is
    supplied by whoever compiled the function: ``exec`` with a chosen filename,
    or one ``__code__.replace(co_filename=...)`` on an ordinary ``def``, moved a
    plan-consuming callable out of scope without moving a single line of source.
    An earlier version also walked ``contracts/`` alone, so a plain ``def`` in
    ``api.py`` was never looked at.

    Both are the same mistake: letting something other than the filesystem decide
    what this package contains. The AST scan already walks every ``*.py`` under
    ``src/``; this walks exactly that set and imports it, so the runtime view and
    the textual view cover the same files by construction.
    """

    import importlib

    modules = []
    for path in sorted(SRC.rglob("*.py")):
        relative = path.relative_to(SRC).with_suffix("")
        parts = [part for part in relative.parts if part != "__init__"]
        modules.append(importlib.import_module(".".join([NAMESPACE, *parts])))
    return modules


CALLABLE_INVENTORY = json.loads(
    (PKG / "public_callable_inventory.json").read_text()
)
UNRESOLVED = "<unresolved>"


def _render(types) -> list:
    return sorted(f"{cls.__module__}.{cls.__qualname__}" for cls in types)


def _unwrap(member):
    """The underlying function of a classmethod, staticmethod or property."""

    if isinstance(member, (classmethod, staticmethod)):
        return getattr(member, "__func__", None)
    if isinstance(member, property):
        return member.fget
    return member


def _live_callables() -> dict:
    """``{label: signature}`` for every callable reachable under ``src/``.

    **No classification, no exemption, no ownership test.** The label is built
    from the module being walked and the attribute path, never from the
    callable's own ``__module__`` or ``__qualname__`` — both are writable, and
    the third audit reassigned ``__module__`` to ``"builtins"`` to move a method
    out of scope. Where a thing is bound is a fact about this package; what it
    says about itself is not.

    Imported, synthesized and injected callables are included. They are entries
    in the frozen inventory, not exclusions, because every exclusion previously
    written here became the next bypass.
    """

    entries = {}
    for module in _package_modules():
        for name, value in vars(module).items():
            func = _unwrap(value)
            if inspect.isfunction(func):
                entries[f"{module.__name__}::{name}"] = _signature(func)
            elif inspect.isclass(value):
                for attribute, member in vars(value).items():
                    inner = _unwrap(member)
                    if inspect.isfunction(inner):
                        entries[f"{module.__name__}::{name}.{attribute}"] = (
                            _signature(inner)
                        )
    return entries


def _signature(func) -> dict:
    try:
        parameters = {
            name: _render(types)
            for name, types in resolved_parameter_types(func).items()
        }
    except Exception:  # pragma: no cover - recorded, never skipped
        parameters = {UNRESOLVED: []}
    try:
        returns = _render(resolved_return_types(func))
    except Exception:  # pragma: no cover - recorded, never skipped
        returns = [UNRESOLVED]
    return {"parameters": parameters, "returns": returns}


# --------------------------------------------------------------------------- #
# The boundary, as a closed set rather than a rule
# --------------------------------------------------------------------------- #
def test_the_live_callable_set_equals_the_frozen_inventory_exactly():
    """Every callable under ``src/``, compared — not classified.

    Three audits found seven defects in the rules that used to assert BR-2B's
    boundary, and none in the boundary itself. Every one was a classification
    defect: a substring an alias walked past, a skipped ``None`` annotation, a
    PEP 563 string read as one opaque name, an ownership test keyed on
    attacker-supplied ``co_filename``, a walk scoped to ``contracts/``, then a
    dunder-named lambda, a reassigned ``__module__``, and a base class whose
    ``__module__`` was reassigned to make a method look generated.

    There is nothing here to walk past because nothing is decided. A callable
    the inventory does not list fails, whatever it is called, however it was
    compiled and wherever it was bound. A listed callable whose resolved
    signature moved fails too.
    """

    live = _live_callables()
    frozen = CALLABLE_INVENTORY["callables"]

    added = sorted(set(live) - set(frozen))
    removed = sorted(set(frozen) - set(live))
    assert added == [], f"callables not in the frozen inventory: {added[:6]}"
    assert removed == [], f"inventoried callables now absent: {removed[:6]}"

    moved = [
        label for label in sorted(live) if live[label] != frozen[label]
    ]
    assert moved == [], (
        f"resolved signature moved for: "
        f"{[(m, frozen[m], live[m]) for m in moved[:3]]}"
    )


def test_every_parameter_written_under_src_is_annotated_and_no_lambda_exists():
    """The annotation requirement, restored with nothing to exempt.

    Its previous form asked each *runtime* callable where it came from, and
    carried exemptions for ``EnumType``-copied methods, the dataclass method
    set and ``typing.Protocol``'s injected ``__init__`` — exemptions the third
    audit walked through twice. This form never meets those callables: it reads
    the source files under ``src/`` and checks the parameters written **in
    them**. A stdlib function imported into a module was not written here, so
    there is nothing to classify and nothing to exempt.

    Lambdas are refused outright rather than checked. A lambda cannot annotate
    its parameters, and the third audit's first plant was a dunder-named lambda
    consuming a plan. There is no lambda in this package and none may appear.
    """

    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Lambda):
                offenders.append(f"{path.name}:{node.lineno} lambda")
                continue
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            arguments = node.args
            written = [
                *arguments.posonlyargs,
                *arguments.args,
                *arguments.kwonlyargs,
                arguments.vararg,
                arguments.kwarg,
            ]
            for argument in written:
                if argument is None or argument.arg in ("self", "cls"):
                    continue
                if argument.annotation is None:
                    offenders.append(
                        f"{path.name}:{node.lineno} "
                        f"{node.name}({argument.arg})"
                    )
    assert offenders == [], offenders


def test_the_inventory_records_the_count_it_holds():
    assert CALLABLE_INVENTORY["callables_inventoried"] == len(
        CALLABLE_INVENTORY["callables"]
    )
    assert CALLABLE_INVENTORY["callables_inventoried"] > 0


def test_no_inventoried_callable_accepts_a_transition_plan():
    """Read off the frozen set, so it is a fact about a closed list.

    The set-equality property above is what makes this exhaustive: a plan
    consumer that never reached the inventory has already failed there.
    """

    plan = (
        f"{api.BenchmarkTransitionPlan.__module__}."
        f"{api.BenchmarkTransitionPlan.__qualname__}"
    )
    offenders = [
        f"{label}({name})"
        for label, entry in CALLABLE_INVENTORY["callables"].items()
        for name, types in entry["parameters"].items()
        if plan in types
    ]
    assert offenders == [], offenders


#: The only callables that may declare a lifecycle payload return, named
#: individually rather than matched by a name pattern. BR-2A's two exact-type
#: validators return the payload they validate, and the store port *declares*
#: one because a port is a shape BR-2D will implement. Every other callable
#: returning a lifecycle payload would be fabricating a registry event.
#:
#: A frozen list of three, not a rule: the previous version scoped the check to
#: ``plan_*`` names, and the third audit fabricated an event from a callable
#: that was not named ``plan_`` anything and consumed no plan.
PERMITTED_PAYLOAD_RETURNS = frozenset(
    {
        "::BenchmarkRegistryStorePort.read_historical",
        "::require_exact_historical_record_payload",
        "::require_exact_resolution_record_payload",
        "api::BenchmarkRegistryStorePort.read_historical",
        "api::require_exact_historical_record_payload",
        "api::require_exact_resolution_record_payload",
        "contracts.ports::BenchmarkRegistryStorePort.read_historical",
        "contracts.read_payloads::require_exact_historical_record_payload",
        "contracts.read_payloads::require_exact_resolution_record_payload",
        "contracts::BenchmarkRegistryStorePort.read_historical",
        "contracts::require_exact_historical_record_payload",
        "contracts::require_exact_resolution_record_payload",
    }
)


def test_no_inventoried_callable_returns_a_reserved_or_lifecycle_payload():
    """The return half, over the closed list and every callable in it.

    Not scoped to ``plan_*``. That narrowing was itself an audit finding: a
    callable consuming no plan and carrying no planning name fabricated a
    registry event, and no gate spoke about it. The three legitimate exceptions
    are enumerated above; everything else is refused.
    """

    payloads = {
        f"{cls.__module__}.{cls.__qualname__}" for cls in LIFECYCLE_PAYLOAD_TYPES
    }
    offenders = []
    for label, entry in CALLABLE_INVENTORY["callables"].items():
        suffix = label[len(NAMESPACE):]
        if suffix.lstrip(".") in PERMITTED_PAYLOAD_RETURNS:
            continue
        leaked = set(entry["returns"]) & payloads
        if leaked:
            offenders.append(f"{label} -> {sorted(leaked)}")
    assert offenders == [], offenders


def test_the_permitted_payload_returns_are_all_present_and_used():
    """A stale exception is an exception nobody notices has stopped applying."""

    suffixes = {
        label[len(NAMESPACE):].lstrip(".")
        for label in CALLABLE_INVENTORY["callables"]
    }
    unused = sorted(PERMITTED_PAYLOAD_RETURNS - suffixes)
    assert unused == [], unused


def test_no_exported_planner_can_return_a_lifecycle_payload():
    """Planning returns a plan or a refusal. It never returns a chain payload.

    Resolved, not read. Every module here uses PEP 563, so the raw return
    annotation is the *string* ``"BenchmarkPlanningOutcome"`` — one opaque name
    whose members the previous version never inspected, which made widening the
    alias to include a registry event completely invisible. The hints are now
    resolved and every ``Union`` member walked to its class object.
    """

    for symbol in pkg.__all__:
        value = getattr(pkg, symbol)
        if not (inspect.isfunction(value) and symbol.startswith("plan_")):
            continue
        returned = resolved_return_types(value)
        assert returned, symbol
        leaked = returned & LIFECYCLE_PAYLOAD_TYPES
        assert not leaked, f"{symbol} -> {sorted(c.__name__ for c in leaked)}"
        assert returned <= {
            api.BenchmarkTransitionPlan,
            api.BenchmarkTransitionRefusal,
        }, f"{symbol} -> {sorted(c.__name__ for c in returned)}"


def test_the_planning_outcome_alias_has_exactly_two_frozen_members():
    """Widening the alias must fail a gate, not merely move a symbol count."""

    import typing

    members = set(typing.get_args(api.BenchmarkPlanningOutcome))
    assert members == {
        api.BenchmarkTransitionPlan,
        api.BenchmarkTransitionRefusal,
    }, sorted(getattr(m, "__name__", str(m)) for m in members)
