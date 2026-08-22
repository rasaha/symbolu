"""BR-2A stops where the ratification says it stops — asserted, not promised."""

from __future__ import annotations

import ast
import inspect
import pathlib
import re

import pytest

from _boundary import (
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

#: The exact token set BR-2A froze, held separately from the map above so that a
#: **one-sided** edit is caught: a token dropped from the map alone stops being
#: checked, and the equality against this set fails.
#:
#: **This vocabulary is self-attested, and the guard is weaker than it reads.**
#: Both literals live in this one file, so an edit that removes a token from the
#: map *and* from this set moves both sides of the comparison together and the
#: suite stays green — measured, not supposed: deleting ``"keyparser"`` and
#: ``"key_parser"`` from both while shipping a live ``class KeyParser`` under
#: ``src/`` leaves the suite passing, and a capability the ADR bans until
#: ``0.3.0`` would ship with nothing saying so.
#:
#: No second authority for these tokens exists in this repository: the probe
#: harness carries none, the gate inventory carries none, and ADR §35.2 names
#: them only in prose. Pinning them to one is genuine engineering and needs its
#: own ratification. Until then this comment is the warning, and the reviewer of
#: any diff touching either literal is the check.
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


def test_happy_the_package_version_is_the_br2c_0_rung():
    """D-33's rung: BR-2C's contracts landed, no BR-2C capability did."""

    assert api.__version__ == "0.2.3"
    assert VERSION_SUBPHASE[api.__version__] == "BR-2C-0"


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


# --------------------------------------------------------------------------- #
# D-36: splitting the BR-2C-0 rung per version would rule nothing.
# --------------------------------------------------------------------------- #
#: The ladder D-36 closed: one rung per version instead of one rung carrying
#: ``0.2.1``, ``0.2.2`` and ``0.2.3``. It is never the real ladder — it exists
#: only so the option D-36 rejected can be *measured* rather than asserted.
_PER_VERSION_LADDER = (
    "BR-2A",
    "BR-2B",
    "BR-2C-0/0.2.1",
    "BR-2C-0/0.2.2",
    "BR-2C-0/0.2.3",
    "BR-2C",
    "BR-2D",
    "BR-2E",
)

_SPLIT_RUNGS = ("BR-2C-0/0.2.1", "BR-2C-0/0.2.2", "BR-2C-0/0.2.3")

#: Both unlock maps, so the check covers the tree-wide capability scan *and*
#: the exported-symbol scan. D-33 records that ``0.3.0`` unlocks twelve tokens
#: across the two, not eight across one, so a check reading only one map would
#: measure two thirds of the ground it claims to pin.
def _both_unlock_maps():
    import importlib.util

    other = PKG / "tests" / "contract" / "test_confusable_and_ports.py"
    spec = importlib.util.spec_from_file_location("_d36_exported_unlock", other)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return (
        ("FORBIDDEN_CAPABILITY_UNLOCK", FORBIDDEN_CAPABILITY_UNLOCK),
        ("EXPORTED_IMPLEMENTATION_UNLOCK", module.EXPORTED_IMPLEMENTATION_UNLOCK),
    )


def test_no_token_unlocks_at_the_br2c_0_rung_itself():
    """The precondition D-36's ground rests on, asserted rather than assumed.

    D-36 closes the rung-per-version option because the extra ladder indices
    would produce ban sets identical to ``BR-2C-0``'s, and so rule nothing.
    That holds **only** while no token names ``BR-2C-0`` as its unlock phase: a
    token that did would be shippable at one of the three versions and not the
    others, the split rungs would stop being interchangeable, and D-36's ground
    would be false with nothing saying so. Every unlock is `BR-2C`, `BR-2D` or
    permanent, and this is the check that keeps it that way.
    """

    for name, unlock_map in _both_unlock_maps():
        offenders = sorted(
            token for token, unlock in unlock_map.items() if unlock == "BR-2C-0"
        )
        assert offenders == [], (
            f"{name}: {offenders} unlock at BR-2C-0 itself, which falsifies "
            "ADR §35.2 D-36's ground. The rung carries three versions; a token "
            "first shippable at one of them needs its own ratification."
        )


def test_splitting_the_br2c_0_rung_per_version_changes_no_ban_set():
    """D-36's ground, measured on both surfaces rather than asserted.

    Builds the ladder D-36 rejected — ``BR-2C-0`` split into one rung per
    version — and compares ban sets against the real ladder. At each of the
    three split rungs the ban set must equal the real ``BR-2C-0``'s, and at
    ``BR-2C``, ``BR-2D`` and ``BR-2E`` it must be unchanged by the insertion,
    because :func:`banned_capability_tokens` compares by ladder **index**.
    Identical ban sets at every rung is the whole of why the extra rungs would
    rule nothing.

    This weakens no ban: it asserts equality against the live ban set rather
    than against a copied literal, so a ban that shrank would fail
    :func:`test_the_effective_ban_set_is_exactly_what_br2a_froze` first and this
    check would still see the two ladders agree.
    """

    for name, unlock_map in _both_unlock_maps():
        real = banned_capability_tokens("BR-2C-0", unlock_map)
        assert real, name

        for rung in _SPLIT_RUNGS:
            assert banned_capability_tokens(
                rung, unlock_map, _PER_VERSION_LADDER
            ) == real, (
                f"{name}: splitting BR-2C-0 changed the ban set at {rung}"
            )

        for rung in ("BR-2C", "BR-2D", "BR-2E"):
            assert banned_capability_tokens(
                rung, unlock_map, _PER_VERSION_LADDER
            ) == banned_capability_tokens(rung, unlock_map), (
                f"{name}: inserting rungs moved the ban set at {rung}"
            )


def test_a_token_is_banned_below_its_unlock_rung_and_not_at_it():
    """The ``reached`` boundary itself, which nothing pinned before.

    :func:`banned_capability_tokens` bans a token whose unlock index is strictly
    **greater** than the rung reached. Nothing exercised that boundary: every
    check ran at rungs where no token unlocks, so drifting ``>`` to ``>=`` — a
    one-character change that would keep every capability banned one rung too
    long — left the suite green. Found by an independent audit of the D-36
    check; the gap is older than that check.

    This asserts the semantics directly, on both surfaces: at a token's own
    unlock rung it is **not** banned, and one rung below it **is**.
    """

    for name, unlock_map in _both_unlock_maps():
        checked = 0
        for token, unlock in unlock_map.items():
            if unlock is None:
                continue
            at = SUBPHASE_LADDER.index(unlock)
            assert token not in banned_capability_tokens(unlock, unlock_map), (
                f"{name}: {token} is still banned at its own unlock rung {unlock}"
            )
            below = SUBPHASE_LADDER[at - 1]
            assert token in banned_capability_tokens(below, unlock_map), (
                f"{name}: {token} is not banned at {below}, one rung below "
                f"its unlock {unlock}"
            )
            checked += 1
        assert checked, f"{name}: no token carries a real unlock phase"


def test_the_rung_carries_exactly_the_three_versions_d36_ruled():
    """D-36's **ruling**, not merely its ground.

    D-36 rules that ``0.2.1``, ``0.2.2`` and ``0.2.3`` all sit on ``BR-2C-0``:
    the rung names what a version ships, not how many times it shipped, and all
    three ship BR-2C's contract surface and no BR-2C capability.

    The ground — that splitting the rung would change no ban set — was pinned
    first, and an independent audit found the ruling itself still unpinned:
    re-mapping ``0.2.2`` to ``BR-2B`` left the suite green, because the
    fail-closed ``KeyError`` every consumer relies on catches an **unmapped**
    version, never a **mis**-mapped one, and only once that version is live.
    """

    assert {v: VERSION_SUBPHASE[v] for v in ("0.2.1", "0.2.2", "0.2.3")} == {
        "0.2.1": "BR-2C-0",
        "0.2.2": "BR-2C-0",
        "0.2.3": "BR-2C-0",
    }
    assert [v for v, rung in VERSION_SUBPHASE.items() if rung == "BR-2C-0"] == [
        "0.2.1",
        "0.2.2",
        "0.2.3",
    ]


def test_the_hypothetical_ladder_is_never_the_real_one():
    """A guard on the guard: the rejected ladder must not become the shipped one."""

    assert SUBPHASE_LADDER == (
        "BR-2A",
        "BR-2B",
        "BR-2C-0",
        "BR-2C",
        "BR-2D",
        "BR-2E",
    )
    assert _PER_VERSION_LADDER != SUBPHASE_LADDER
    assert set(VERSION_SUBPHASE.values()) <= set(SUBPHASE_LADDER)


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


# --------------------------------------------------------------------------- #
# The enforceable boundary: what is *exported*, and what capability exists
# --------------------------------------------------------------------------- #
# Ratified 2026-08-20. The previous design tried to prove that **no callable
# anywhere under src/** consumes a transition plan. That claim is not provable
# in Python and was abandoned, not merely re-implemented:
#
#   Python permits closures, callables held in containers, dynamic attributes,
#   ``exec``, ``type()``, ``__getattr__``, ``functools.partial`` and runtime
#   rebinding. Every design that "discovered" callables only changed *what
#   counts as discoverable*, and three audits found seven bypasses on exactly
#   that seam. The last design — a frozen 2207-entry inventory — could be
#   defeated by regenerating it in the same commit as the plant, so it did not
#   even hold against the adversary it was written for.
#
# The enforceable claim is capability absence, and it is what actually keeps
# BR-2B safe: **even if a private helper or a verifier were introduced, there is
# no store, no clock, no authority-issued result and no effectful operation for
# it to unlock.** A private plan-consuming helper computes a value and can do
# nothing with it. That is "non-authoritative by construction".
#
# Private-source expansion is therefore governed, not gated: see CODEOWNERS and
# docs/governance/PROTECTED_BRANCHES.md. A contributor who can modify production
# code *and* its tests in one commit is stopped by an independent approving
# review, not by a generated artifact they can regenerate.
#
# Four properties, each decidable, are asserted below and above:
#   1. No exported callable or Protocol method accepts a transition plan.
#   2. No authority-issued result type exists (the reserved-name gates).
#   3. No store, verifier, clock, append/apply operation, composition root or
#      prohibited dependency exists (capability, dependency and clock gates).
#   4. Planning returns only a structural plan or a typed refusal.
# --------------------------------------------------------------------------- #


def _exported_callables() -> dict:
    """``{name: function}`` for every callable on the curated public surface.

    The curated surface is the thing this package promises and the thing a
    caller can reach. It is enumerated by ``api.__all__``, which is pinned
    against ``public_api.json`` by a separate gate, so it cannot be widened
    quietly to make this check smaller.
    """

    found = {}
    for symbol in api.__all__:
        value = getattr(api, symbol)
        if inspect.isfunction(value):
            found[symbol] = value
    return found


def _protocol_methods() -> dict:
    """``{Protocol.method: function}`` for every method a declared port exposes.

    Ports are the shapes BR-2D will implement. A plan parameter *declared* here
    would be a plan parameter BR-2D is obliged to accept, which is the one way
    an exported-surface check alone could be walked past.
    """

    found = {}
    for symbol in api.__all__:
        value = getattr(api, symbol)
        if not inspect.isclass(value) or not _is_port_declaration(symbol, value):
            continue
        for attribute, member in vars(value).items():
            if inspect.isfunction(member) and not attribute.startswith("_"):
                found[f"{symbol}.{attribute}"] = member
    return found


def test_no_exported_callable_or_protocol_method_accepts_a_transition_plan():
    """Property 1, by resolved type identity — the claim BR-2B actually makes.

    Resolved, never matched as text: ``typing.get_type_hints`` evaluates the
    PEP 563 strings and every ``Union``/``Optional``/generic is walked to its
    leaves, so an alias, a nested ``Optional`` or a container-nested plan is as
    visible as a bare one. Membership is decided by ``is`` against the real
    class, the same discipline the sealed contract-type registry uses.

    This does **not** claim no private helper takes a plan. It claims no caller
    can hand one to this package, and no port obliges BR-2D to accept one.
    """

    offenders = []
    for label, func in {**_exported_callables(), **_protocol_methods()}.items():
        for name, types in resolved_parameter_types(func).items():
            if api.BenchmarkTransitionPlan in types:
                offenders.append(f"{label}({name})")
    assert offenders == [], offenders


def test_every_exported_callable_and_protocol_method_is_fully_annotated():
    """Otherwise property 1 is silently vacuous for an unannotated parameter.

    An unannotated parameter resolves to no types, so a plan hidden behind one
    would pass the check above by contributing nothing to it. On the curated
    surface an unannotated parameter is a failure, not a skip — this package
    ships ``py.typed`` and annotates everything it exports.
    """

    offenders = [
        f"{label}({name})"
        for label, func in {
            **_exported_callables(),
            **_protocol_methods(),
        }.items()
        for name in unannotated_parameters(func)
    ]
    assert offenders == [], offenders


#: Exactly what property 1 walks. Pinned, not floored: a surface that *shrinks*
#: makes the check smaller without failing anything, and a gate that quietly
#: covers less is the failure mode all three audits found. Moving this number is
#: a reviewed change, the same as moving ``public_api.json``.
EXPORTED_CALLABLES_WALKED = 13
#: Ten, not nine, since D-26 added ``verify_revocation`` to
#: ``BenchmarkApprovalVerifierPort``. The ports stay inert Protocols; the count
#: moves because there is one more seam declared, not one more implemented.
PROTOCOL_METHODS_WALKED = 10


def test_the_surface_property_one_walks_is_exactly_what_is_pinned():
    """A gate over an empty — or quietly shrunken — set passes for the wrong reason."""

    assert len(_exported_callables()) == EXPORTED_CALLABLES_WALKED, sorted(
        _exported_callables()
    )
    assert len(_protocol_methods()) == PROTOCOL_METHODS_WALKED, sorted(
        _protocol_methods()
    )


def test_every_parameter_written_under_src_is_annotated_and_no_lambda_exists():
    """A legibility requirement on shipped source. **Not** a boundary control.

    This does not prove anything about hidden callables and is not relied on to
    — property 1 is asserted on the exported surface above. What it buys is that
    every parameter written in this package is annotated and no lambda appears,
    so a reviewer reading a diff can see what a function accepts. Reviewability
    is the control that governs private source; this keeps it cheap.

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
