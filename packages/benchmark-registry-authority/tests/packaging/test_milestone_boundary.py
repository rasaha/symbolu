"""BR-2A stops where the ratification says it stops — asserted, not promised."""

from __future__ import annotations

import ast
import inspect
import pathlib
import re

import pytest

from _boundary import (
    names_resolving_to,
    resolved_parameter_types,
    resolved_return_types,
    unannotated_parameters,
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


def _defined_here(value) -> bool:
    return str(getattr(value, "__module__", "")).startswith(NAMESPACE)


def _is_generated(owner, name: str, member) -> bool:
    """Whether ``owner.name`` was synthesized rather than written here.

    Decided by **identity against a base class**, or by the dataclass machinery's
    own fixed method set — never by a filename the code object carries.

    ``EnumType`` copies functions such as ``_generate_next_value_`` into every
    subclass's own ``__dict__``, and ``@dataclass`` synthesizes ``__init__``,
    ``__eq__`` and ``__repr__`` by exec. Nobody can annotate the ``other`` of a
    generated ``__eq__``, so these are exempt from the *annotation* requirement
    only. They are **not** exempt from the plan-consumption check, which needs no
    exemption at all: a synthesized method has no annotation naming a plan.
    """

    import dataclasses as _dc

    for base in getattr(owner, "__mro__", ())[1:]:
        if _defined_here(base):
            continue
        if getattr(base, name, None) is member:
            return True
    if _dc.is_dataclass(owner) and name in {
        "__init__",
        "__eq__",
        "__repr__",
        "__hash__",
        "__setattr__",
        "__delattr__",
    }:
        return True
    return False


def _names_defined_in_source(module) -> set:
    """Every name that appears as a ``def`` in this module's own source text.

    The scanned text is the authority for what this package wrote. A member
    bound in a module but absent from its source was injected or generated —
    ``typing.Protocol`` installs ``__init__`` and ``__subclasshook__`` on every
    Protocol class, and neither can be annotated by anyone here.

    This is deliberately *not* ``co_filename``: the filename travels with the
    code object and can be chosen by whoever compiled it, while this comes from
    reading the file the scan already walks.
    """

    tree = ast.parse(pathlib.Path(module.__file__).read_text())
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _callables_in(module):
    """``(label, function, generated?, attribute name)`` for every callable here.

    No filter on where the code claims to come from. A function bound in a module
    under ``src/`` is this package's regardless of how it was compiled — which is
    the whole point: ``exec``-created and ``__code__``-rewritten functions are
    exactly the ones the previous ownership test let through.
    """

    found = []
    for name, value in vars(module).items():
        if inspect.isfunction(value):
            found.append((f"{module.__name__}.{name}", value, False, name))
        elif inspect.isclass(value) and _defined_here(value):
            for attribute, member in vars(value).items():
                label = f"{module.__name__}.{value.__name__}.{attribute}"
                if inspect.isfunction(member):
                    found.append(
                        (
                            label,
                            member,
                            _is_generated(value, attribute, member),
                            attribute,
                        )
                    )
                elif isinstance(member, property) and member.fget is not None:
                    found.append(
                        (
                            label,
                            member.fget,
                            _is_generated(value, attribute, member.fget),
                            attribute,
                        )
                    )
    return found


def test_no_exported_callable_accepts_a_transition_plan_as_input():
    """A plan is an output of this package and an input to nothing in it.

    Decided by **class identity** on resolved annotations, never by matching the
    name in text: an alias, a ``Union`` member or a nested ``Optional`` spells
    the same type without spelling its name.
    """

    offenders = []
    for symbol in pkg.__all__:
        value = getattr(pkg, symbol)
        if not callable(value) or inspect.isclass(value):
            continue
        for name, types in resolved_parameter_types(value).items():
            if api.BenchmarkTransitionPlan in types:
                offenders.append(f"{symbol}({name})")
    assert offenders == [], offenders


def test_no_callable_anywhere_under_src_accepts_a_plan_however_spelled():
    """Every module whose source lives under ``src/``, not just ``contracts/``.

    This check has **no exemptions**. A synthesized method carries no annotation
    naming a plan, so excluding one would buy nothing and cost the guarantee — and
    the exclusions are precisely what the second audit walked through: a function
    ``exec``-compiled with a chosen ``co_filename``, the same trick via one
    ``__code__.replace``, and a plain ``def`` in ``api.py`` that the
    ``contracts/``-scoped walk never visited.
    """

    offenders = []
    for module in _package_modules():
        for label, func, _generated, _attribute in _callables_in(module):
            for name, types in resolved_parameter_types(func).items():
                if api.BenchmarkTransitionPlan in types:
                    offenders.append(f"{label}({name})")
    assert offenders == [], offenders


def test_no_planner_anywhere_under_src_returns_a_lifecycle_payload():
    """The return half, over every module rather than the exported surface.

    Scoped to planners, because that is what the ruling constrains: BR-2A's
    ``require_exact_resolution_record_payload`` legitimately returns a resolution
    record, and ``BenchmarkRegistryStorePort.read_historical`` legitimately
    declares one — a store port is a *shape*, and BR-2D will implement it. What
    must never return a lifecycle payload is something that plans.

    A callable that consumed a plan and returned an event is caught by the
    parameter check above, which has no exemptions at all, so nothing rests on
    this test recognising the name.
    """

    offenders = []
    for module in _package_modules():
        for label, func, _generated, _attribute in _callables_in(module):
            if not func.__name__.startswith("plan_"):
                continue
            returned = resolved_return_types(func)
            assert returned, label
            leaked = returned & LIFECYCLE_PAYLOAD_TYPES
            if leaked or not returned <= {
                api.BenchmarkTransitionPlan,
                api.BenchmarkTransitionRefusal,
            }:
                offenders.append(
                    f"{label} -> {sorted(c.__name__ for c in returned)}"
                )
    assert offenders == [], offenders


def test_every_parameter_under_src_is_annotated():
    """An unannotated parameter is the cheapest place to hide a plan.

    The identity checks can only speak about annotations that exist, so a bare
    parameter is a **failure**, never a skip. ``self`` and ``cls`` are exempt.
    Synthesized methods are exempt too — nobody can annotate the ``other`` of a
    generated ``__eq__`` — but that exemption is decided by identity against a
    base class or by the dataclass machinery's fixed method set, never by a
    filename the code object carries.
    """

    offenders = []
    for module in _package_modules():
        defined = _names_defined_in_source(module)
        for label, func, generated, attribute in _callables_in(module):
            if generated:
                continue
            # Keyed on the ATTRIBUTE, not the function's own __name__:
            # typing.Protocol installs __subclasshook__ and __init__ whose
            # underlying functions are named _proto_hook and
            # _no_init_or_replace_init, so a __name__-based test sees neither
            # as a dunder and demands annotations nobody here can add.
            if attribute.startswith("__") and func.__name__ not in defined:
                continue  # injected dunder, e.g. Protocol's __init__
            if func.__name__ not in defined and not _defined_here(func):
                # Imported, not written: ``from dataclasses import fields``
                # binds a stdlib function into this module's namespace, and
                # nobody here can annotate it.
                #
                # A function exec-compiled into this module's own globals keeps
                # this package's ``__module__`` and therefore stays in scope —
                # which is the case that matters. And the plan-consumption check
                # above carries no exemption of any kind, so even a function that
                # lied about its origin could not use this to hide an annotated
                # plan parameter.
                continue
            for name in unannotated_parameters(func):
                offenders.append(f"{label}({name})")
    assert offenders == [], offenders


def test_no_function_in_any_source_file_takes_a_plan_parameter():
    """The textual scan, alias-aware across **every** module the walk imports.

    AST cannot resolve an alias, so the names that resolve to the plan type are
    computed at runtime and the scan matches that set. The earlier version built
    that set from ``contracts/`` alone, so a module-level alias declared in
    ``api.py`` was a name the scan had never heard of.

    The scan keeps its one advantage over a runtime attribute walk — it sees
    closures and nested functions that no module attribute exposes — and now
    covers the same files.
    """

    alias_names = {api.BenchmarkTransitionPlan.__name__}
    for module in _package_modules():
        alias_names |= names_resolving_to(module, api.BenchmarkTransitionPlan)

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
                if argument.arg in ("self", "cls") or argument.annotation is None:
                    continue
                spelled = set(
                    re.findall(
                        r"[A-Za-z_][A-Za-z0-9_]*", ast.unparse(argument.annotation)
                    )
                )
                if spelled & alias_names:
                    offenders.append(f"{path.name}: {node.name}({argument.arg})")
    assert offenders == [], offenders


def test_the_alias_set_is_gathered_from_every_scanned_module():
    """A module the alias walk skips is a module whose aliases are invisible."""

    walked = {
        pathlib.Path(module.__file__).resolve() for module in _package_modules()
    }
    assert walked == {path.resolve() for path in SRC.rglob("*.py")}
    # api.py is the module the contracts/-scoped walk never visited.
    assert any(path.name == "api.py" for path in walked)


def test_the_ownership_test_cannot_be_granted_by_the_code_object():
    """``co_filename`` is attacker-supplied; the scanned path is not.

    Both shapes the second audit used are constructed here and required to stay
    in scope. If ownership ever consults the code object again, this fails.
    """

    planted = {}
    exec(  # noqa: S102 - a synthetic variant, defined and discarded here
        compile(
            "def smuggled(plan):\n    return None\n",
            "/tmp/not_under_contracts.py",
            "exec",
        ),
        planted,
    )
    smuggled = planted["smuggled"]
    assert smuggled.__code__.co_filename == "/tmp/not_under_contracts.py"
    assert unannotated_parameters(smuggled) == ["plan"]

    def rewritten(plan) -> None: ...

    rewritten.__code__ = rewritten.__code__.replace(
        co_filename="/tmp/not_under_contracts.py"
    )
    assert rewritten.__code__.co_filename == "/tmp/not_under_contracts.py"
    assert unannotated_parameters(rewritten) == ["plan"]

    # Neither is excluded by _is_generated: it consults base-class identity and
    # the dataclass method set, and knows nothing about filenames.
    class Holder:
        pass

    assert not _is_generated(Holder, "smuggled", smuggled)
    assert not _is_generated(Holder, "rewritten", rewritten)


def test_the_module_walk_covers_every_file_the_ast_scan_reads():
    """The runtime view and the textual view must cover the same files.

    A module the walk skips is a module whose aliases the AST scan never learns
    and whose functions the resolver never sees — which is how a plain ``def`` in
    ``api.py`` stayed invisible.
    """

    walked = {
        pathlib.Path(module.__file__).resolve() for module in _package_modules()
    }
    scanned = {path.resolve() for path in SRC.rglob("*.py")}
    assert walked == scanned, sorted(
        str(p) for p in scanned.symmetric_difference(walked)
    )


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
