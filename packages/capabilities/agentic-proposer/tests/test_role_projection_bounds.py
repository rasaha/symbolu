"""D8's containment bounds on the D1 role projection, enforced mechanically.

The Agent Constitution does not exist and will not exist before S1 (D8). The D1
``CognitiveRoleContract`` therefore proceeds as a proposer-local **v0** projection,
bounded to: never exported to shared contracts, carrying no constitution-derived
attribute, exposing no role lifecycle verb. The ADR records two of those bounds as
an ``[R]`` obligation on S1 — the export bound and the lifecycle-verb bound — and
this module discharges it.

Both bounds are enforceable now, before the projection exists, and both are
enforced over the repository rather than over prose:

* the EXPORT bound is checked from the shared-contract side. Every shared contract
  distribution in this repository is discovered and scanned for a role-projection
  name, for a re-export of it, and for a dependency on this capability. That check
  is meaningful today: it would fail the moment a projection name appeared there,
  whether or not this package ever defines one.
* the LIFECYCLE bound is checked over this package's whole defined surface —
  modules, classes, methods and annotated fields — so lifecycle authority cannot
  arrive on a projection later without failing here.

Owner decision O-2 narrows what the lifecycle bound prohibits. The bound is on
AUTHORITY: an operation, or a callable this capability could invoke, that mints,
activates, suspends, ratifies, revokes, expires or replaces a role. It is not a bar
on the domain's vocabulary for lifecycle facts determined elsewhere — ``SUSPENDED``,
``REVOKED``, ``RoleActivationStatus``, ``activation_status`` and ``expires_at`` are
what a reader of roles calls what it read, and a scan that rejected them would buy
no containment and cost the contract its correct words. The narrowed guard reads
grammatical FORM and syntactic POSITION rather than the bare stem.

Scanners are self-tested against synthetic sources below, and the narrowing itself
is mutation-tested: each rule is weakened in turn and a real violation must escape,
so no rule survives here without a sample that would catch its removal.
"""
from __future__ import annotations

import ast
import enum
import re
import importlib
import pathlib
import pkgutil

import pytest

import ugence_agentic_proposer as ap

SRC = pathlib.Path(ap.__file__).resolve().parent
PKG_ROOT = SRC.parents[1]
REPO_ROOT = PKG_ROOT.parents[2]
PACKAGES = REPO_ROOT / "packages"

#: This distribution, as a shared contract package would have to name it to depend on it.
THIS_DISTRIBUTION = "ugence-agentic-proposer"
THIS_NAMESPACE = "ugence_agentic_proposer"
#: Any name carrying the projection. Matched as a substring so a renamed or wrapped
#: re-export (``CognitiveRoleContractV0``, ``CognitiveRoleRef``) is caught too.
PROJECTION_MARKERS = ("CognitiveRole", "COGNITIVE_ROLE", "cognitive_role")
#: Role lifecycle verbs, as infinitives. D1 and D3 both depend on this capability
#: never authoring a role: activation state is an input fact, never computed, and no
#: identity or role is minted, changed or ended here.
#:
#: Owner decision O-2 fixes what the presence of one of these verbs means. The bar is
#: on OPERATIONS and on CALLABLE AUTHORITY — ``activate``, ``suspend``, ``revoke``,
#: ``expire`` and their equivalents, wherever the capability could invoke one. It is
#: not a bar on a contract DESCRIBING a lifecycle state somebody else determined, or
#: a validity period somebody else set: ``SUSPENDED``, ``REVOKED``,
#: ``RoleActivationStatus``, ``activation_status`` and ``expires_at`` are the
#: vocabulary of a reader of roles, and renaming them would cost the domain its
#: correct words to satisfy a lexical scan.
#:
#: The two are told apart by grammatical FORM and by syntactic POSITION, not by the
#: stem alone. See ``_authority_offenders``.
LIFECYCLE_VERBS = (
    "mint", "activate", "deactivate", "reactivate", "suspend", "unsuspend",
    "ratify", "revoke", "reinstate", "issue", "expire", "provision", "grant",
    "authorize", "authorise", "enroll", "enrol", "assign", "replace",
)

#: The positions a name can occupy. A name's position is what decides whether an
#: actor form ("issuer") names an authority this capability holds or an external
#: party it merely records.
CALLABLE = "callable"
TYPE = "type"
FIELD = "field"
#: A field whose annotation is itself callable: authority reachable through a
#: state-shaped name.
CALLABLE_FIELD = "callable-field"
BINDING = "binding"

#: Annotations that make a field a callable rather than a value.
CALLABLE_ANNOTATIONS = ("Callable", "Awaitable", "Coroutine")


def _stem(verb):
    """The verb without its inflectable tail: ``activate`` -> ``activat``."""
    return verb[:-1] if verb.endswith(("e", "y")) else verb


def _mutation_forms(verb):
    """The forms in which a verb names an ACT: the imperative and the progressive.

    ``activate``/``activating``, ``revoke``/``revoking``, ``ratify``/``ratifying``.
    These are barred in every position: a name in one of them describes something
    being done, not something that is the case.
    """
    if verb.endswith("e"):
        progressive = verb[:-1] + "ing"
    elif verb.endswith("y"):
        progressive = verb[:-1] + "ying"
    else:
        progressive = verb + "ing"
    return {verb, progressive}


def _actor_forms(verb):
    """The forms in which a verb names an ACTOR: ``activator``, ``issuer``.

    Barred as a type or a callable — that is this capability holding the authority.
    Permitted as a field or a reference: ``issuer_ref`` records who issued a role
    elsewhere, which is exactly the external fact D1 says the proposer reads.
    """
    base = verb[:-1] if verb.endswith("e") else verb
    if verb.endswith("y"):
        return {verb[:-1] + "ier"}
    return {base + "er", base + "or"}


def _tokens(name):
    """``name`` split into lowercase word tokens, snake_case and CamelCase alike."""
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name)
    spaced = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", spaced)
    return [token for token in re.split(r"[^A-Za-z0-9]+", spaced.lower()) if token]


def _distribution_name(pyproject):
    for line in pyproject.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("name =") or stripped.startswith("name="):
            return stripped.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _shared_contract_packages():
    """Every distribution in this repository whose role is to hold shared contracts.

    Discovered, not listed, so a shared contract package added later is covered
    without anyone remembering to add it here.
    """
    found = []
    for pyproject in sorted(PACKAGES.rglob("pyproject.toml")):
        if any(part in {"build", "dist", ".venv", "node_modules"} for part in pyproject.parts):
            continue
        name = _distribution_name(pyproject)
        if "contract" in name and name != THIS_DISTRIBUTION:
            found.append((name, pyproject.parent))
    return found


def _is_callable_annotation(annotation):
    """Whether an annotation makes the field it annotates a callable."""
    referenced = {n.id for n in ast.walk(annotation) if isinstance(n, ast.Name)}
    referenced |= {n.attr for n in ast.walk(annotation) if isinstance(n, ast.Attribute)}
    referenced |= {n.value for n in ast.walk(annotation)
                   if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    return any(any(marker in str(name) for marker in CALLABLE_ANNOTATIONS)
               for name in referenced)


def _is_callable_value(value):
    """Whether an assigned value binds a callable rather than data."""
    if isinstance(value, ast.Lambda):
        return True
    if isinstance(value, ast.Call):
        called = (value.func.id if isinstance(value.func, ast.Name)
                  else value.func.attr if isinstance(value.func, ast.Attribute) else "")
        return called in {"partial", "partialmethod", "staticmethod", "classmethod"}
    return False


def _declared_names(source, filename="<sample>"):
    """Every ``(name, position)`` a module declares or re-exports.

    Classes, functions, assignments, class-level fields and methods, imported
    bindings, and the strings listed in ``__all__``. The POSITION travels with the
    name because O-2's bound is about what a name DOES, and the same token means
    different things in different positions.

    Strings elsewhere — docstrings, enum VALUES — are deliberately excluded. A term
    in a docstring is not a name on the surface, and the ratified D4 values are
    already governed by ``test_vocabulary.py``; scanning them here would confuse a
    vocabulary question with a lifecycle one.
    """
    tree = ast.parse(source, filename=filename)
    declared = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            declared.add((node.name, TYPE))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            declared.add((node.name, CALLABLE))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            declared.add((node.target.id,
                          CALLABLE_FIELD if _is_callable_annotation(node.annotation)
                          else FIELD))
        elif isinstance(node, ast.Assign):
            position = CALLABLE if _is_callable_value(node.value) else BINDING
            declared |= {(t.id, position) for t in node.targets
                         if isinstance(t, ast.Name)}
            if any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
                declared |= {(e.value, BINDING) for e in ast.walk(node.value)
                             if isinstance(e, ast.Constant) and isinstance(e.value, str)}
        elif isinstance(node, ast.ImportFrom):
            declared |= {(a.asname or a.name, BINDING) for a in node.names}
        elif isinstance(node, ast.Import):
            declared |= {(a.asname or a.name.split(".")[0], BINDING) for a in node.names}
    return declared


def _defined_names(source, filename="<sample>"):
    """The names alone, for the projection scans, which do not read position."""
    return {name for name, _ in _declared_names(source, filename=filename)}


def _projection_hits(names):
    """Every name in ``names`` that carries the role projection."""
    return sorted(n for n in names if any(m in n for m in PROJECTION_MARKERS))


def _snapshot_projection_hits(body):
    """Markers present in a public-API snapshot's text."""
    return sorted(m for m in PROJECTION_MARKERS if m in body)


def _capability_dependency_hits(text):
    """References to this distribution or its namespace in another package's text."""
    return sorted(m for m in (THIS_DISTRIBUTION, THIS_NAMESPACE) if m in text)


def _authority_offenders(declared, *, verbs=LIFECYCLE_VERBS, tokens_of=_tokens,
                         mutation_forms=_mutation_forms, actor_forms=_actor_forms,
                         bar_actor_authority=True, bar_callable_fields=True):
    """The names in ``declared`` that give this capability role lifecycle authority.

    ``declared`` is a set of ``(name, position)`` pairs. Three rules, in order:

    1. a MUTATION form in any position — ``activate``, ``suspending_role`` — is an
       operation however it is bound, including an imported one;
    2. an ACTOR form naming a type or a callable — ``class RoleActivator`` — is this
       capability holding the authority, while the same token on a field records an
       external party and is permitted;
    3. any lifecycle-stemmed name whose annotation is a callable — ``activation_status:
       Callable[[], None]`` — is authority smuggled through a state-shaped name.

    A lifecycle-stemmed name in any other position is a description of a state or a
    validity period this capability received, and O-2 requires it to pass.

    The keyword arguments exist so the mutation tests below can weaken one rule at a
    time and prove that a real violation escapes the weakened guard.
    """
    mutations = set().union(*(mutation_forms(verb) for verb in verbs))
    actors = set().union(*(actor_forms(verb) for verb in verbs))
    stems = {_stem(verb) for verb in verbs}
    offenders = set()
    for name, position in declared:
        tokens = set(tokens_of(name))
        if tokens & mutations:
            offenders.add(name)
        elif bar_actor_authority and position in (CALLABLE, TYPE) and tokens & actors:
            offenders.add(name)
        elif (bar_callable_fields and position == CALLABLE_FIELD
              and any(stem in token for token in tokens for stem in stems)):
            offenders.add(name)
    return sorted(offenders)


def _lifecycle_offenders(source, filename="<sample>"):
    """``_authority_offenders`` over everything ``source`` declares."""
    return _authority_offenders(_declared_names(source, filename=filename))


# --------------------------------------------------------------------------- #
# Scanner self-tests
# --------------------------------------------------------------------------- #

def test_the_name_scanner_sees_a_re_export():
    names = _defined_names(
        "from ugence_agentic_proposer import CognitiveRoleContract\n"
        "__all__ = ['CognitiveRoleContract']\n")
    assert any(marker in n for n in names for marker in PROJECTION_MARKERS)


def test_the_name_scanner_sees_class_level_fields_and_methods():
    names = _defined_names(
        "class RoleProjection:\n"
        "    role_ref: str\n"
        "    def activate(self):\n        ...\n")
    assert {"RoleProjection", "role_ref", "activate"} <= names


#: Sources in which this capability takes role lifecycle authority. Every one must
#: be flagged, and each is the sole witness for at least one mutant below.
UNAUTHORIZED_LIFECYCLE_SOURCES = (
    "def mint_role():\n    ...\n",
    "class R:\n    def suspend(self):\n        ...\n",
    "def revoke_role_binding():\n    ...\n",
    "class R:\n    def suspending_role(self):\n        ...\n",
    "from role_service import activate\n",
    "activate = _impl\n",
    "class RoleActivator:\n    pass\n",
    "class R:\n    activation_status: Callable[[], None]\n",
    "class R:\n    on_expiry: Callable[[str], None]\n",
    "expire_role = lambda ref: None\n",
)

#: Sources describing a lifecycle state or a validity period somebody else
#: determined. O-2 requires every one of them to pass: they are the domain's correct
#: vocabulary, and the guard exists to bar authority, not words.
PERMITTED_LIFECYCLE_SOURCES = (
    "class R:\n    role_ref: str\n    is_active: bool\n",
    "def read_role(role):\n    return role.role_ref\n",
    "class RoleActivationStatus(Enum):\n    ACTIVE = 'ACTIVE'\n"
    "    SUSPENDED = 'SUSPENDED'\n    REVOKED = 'REVOKED'\n",
    "class R:\n    activation_status: RoleActivationStatus\n",
    "class R:\n    expires_at: str\n",
    "class R:\n    activated_at: str\n    revoked_at: str\n",
    "class R:\n    issuer_ref: str\n",
    "class R:\n    granted_by_ref: str\n    reason_code: str\n",
)


@pytest.mark.parametrize("sample", UNAUTHORIZED_LIFECYCLE_SOURCES,
                         ids=lambda s: s.split("\n")[0][:44])
def test_the_verb_scanner_flags_lifecycle_authority(sample):
    assert _lifecycle_offenders(sample), "unauthorized lifecycle authority passed"


@pytest.mark.parametrize("sample", PERMITTED_LIFECYCLE_SOURCES,
                         ids=lambda s: s.split("\n")[0][:44])
def test_the_verb_scanner_permits_a_described_lifecycle_state(sample):
    """O-2. An input fact is lawful; acting on it is not.

    ``SUSPENDED``, ``REVOKED``, ``RoleActivationStatus``, ``activation_status`` and
    ``expires_at`` are retained domain vocabulary. A guard that rejected them would
    force a rename that costs the contract its meaning and buys no containment.
    """
    assert not _lifecycle_offenders(sample), "a described lifecycle state was flagged"


#: Weakenings of the guard, each dropping exactly one thing it does. A mutant that
#: still flags every unauthorized sample is a rule no sample pins — the guard would
#: be free to lose it silently. Each entry must therefore let at least one violation
#: through, and the sample it lets through names what that rule is for.
GUARD_MUTANTS = {
    "verb list truncated": {"verbs": ("mint",)},
    "actor authority permitted": {"bar_actor_authority": False},
    "callable fields permitted": {"bar_callable_fields": False},
    "names not tokenized": {"tokens_of": lambda name: [name.lower()]},
    "only the bare infinitive matched": {"mutation_forms": lambda verb: {verb}},
    "stems matched instead of forms": {"actor_forms": lambda verb: set(),
                                       "mutation_forms": lambda verb: {verb}},
}


@pytest.mark.parametrize("label,weakening", sorted(GUARD_MUTANTS.items()))
def test_every_rule_in_the_guard_is_pinned_by_a_sample(label, weakening):
    """Mutation test. O-2 narrowed this guard, so what remains must be load-bearing.

    Narrowing a guard is only safe if the narrowed guard still fails on the thing it
    was narrowed away from. Weakening one rule at a time and requiring a real
    violation to escape proves that each rule is doing work, and that the samples
    above would catch its removal.
    """
    escaped = [sample for sample in UNAUTHORIZED_LIFECYCLE_SOURCES
               if not _authority_offenders(_declared_names(sample), **weakening)]
    assert escaped, (
        f"weakening the guard by '{label}' changed nothing: no sample pins that rule")


@pytest.mark.parametrize("label,weakening", sorted(GUARD_MUTANTS.items()))
def test_a_weakened_guard_still_permits_the_retained_vocabulary(label, weakening):
    """A mutant may only lose detections. One that gained a false positive would
    mean the samples above proved a rule the real guard does not have."""
    for sample in PERMITTED_LIFECYCLE_SOURCES:
        assert not _authority_offenders(_declared_names(sample), **weakening), \
            f"'{label}' flags retained vocabulary: {sample!r}"


def test_the_name_scanner_sees_a_bare_re_export():
    """Without ``__all__``. The re-export self-test above is satisfied through the
    ``__all__`` path, so a broken ImportFrom branch would survive it."""
    names = _defined_names("from ugence_agentic_proposer import CognitiveRoleContract\n")
    assert "CognitiveRoleContract" in names
    names = _defined_names(
        "from ugence_agentic_proposer import CognitiveRoleContract as RoleRef\n")
    assert "RoleRef" in names


@pytest.mark.parametrize("names,expected", [
    ({"CognitiveRoleContract"}, ["CognitiveRoleContract"]),
    ({"CognitiveRoleContractV0", "Unrelated"}, ["CognitiveRoleContractV0"]),
    ({"COGNITIVE_ROLE_REF"}, ["COGNITIVE_ROLE_REF"]),
    ({"cognitive_role_id"}, ["cognitive_role_id"]),
    ({"RoleContract", "role_ref"}, []),
])
def test_the_projection_scanner_flags_a_carried_projection(names, expected):
    """Substring matching, so a renamed or wrapped re-export is caught too."""
    assert _projection_hits(names) == expected


@pytest.mark.parametrize("body,expected", [
    ('{"exports": ["CognitiveRoleContract"]}', ["CognitiveRole"]),
    ('{"exports": ["cognitive_role_ref"]}', ["cognitive_role"]),
    ('{"exports": ["RoleContract"]}', []),
])
def test_the_snapshot_scanner_flags_an_exported_projection(body, expected):
    assert _snapshot_projection_hits(body) == expected


@pytest.mark.parametrize("text,expected", [
    ('dependencies = ["ugence-agentic-proposer>=0.0.1"]', [THIS_DISTRIBUTION]),
    ("from ugence_agentic_proposer import vocabulary\n", [THIS_NAMESPACE]),
    ('dependencies = ["ugence-jcs>=0.2.0"]', []),
])
def test_the_dependency_scanner_flags_a_reference_to_this_capability(text, expected):
    assert _capability_dependency_hits(text) == expected


# --------------------------------------------------------------------------- #
# The export bound (D8), checked from the shared-contract side
# --------------------------------------------------------------------------- #

def _shared_contract_names_by_regex():
    """The same discovery, done a different way, as an oracle for the scan above.

    ``_distribution_name`` parses ``pyproject.toml`` line by line; this reads the
    name with a regex instead. A narrowing to either one — a stricter filter, a
    parser that stops recognising a name form — makes the two disagree.
    """
    names = set()
    for pyproject in sorted(PACKAGES.rglob("pyproject.toml")):
        if any(part in {"build", "dist", ".venv", "node_modules"} for part in pyproject.parts):
            continue
        match = re.search(r"""^\s*name\s*=\s*['"]([^'"]+)['"]""",
                          pyproject.read_text(encoding="utf-8"), re.MULTILINE)
        if match and "contract" in match.group(1) and match.group(1) != THIS_DISTRIBUTION:
            names.add(match.group(1))
    return names


#: The repository holds at least this many shared contract distributions. Asserting a
#: floor rather than non-emptiness is what makes a narrowed scan fail: a discovery
#: that found one package instead of all of them would still be "not empty".
MINIMUM_SHARED_CONTRACT_PACKAGES = 3


def test_shared_contract_packages_are_discovered():
    """The export bound is only enforced if the scan finds ALL the packages.

    Non-emptiness is not enough: a scan narrowed to a single distribution would
    satisfy it while leaving every other shared contract package unchecked.
    """
    found = _shared_contract_packages()
    names = {name for name, _ in found}
    assert names == _shared_contract_names_by_regex(), (
        "the discovery disagrees with an independent read of the same files: "
        f"{sorted(names ^ _shared_contract_names_by_regex())}")
    assert len(found) >= MINIMUM_SHARED_CONTRACT_PACKAGES, (
        f"only {len(found)} shared contract distributions discovered under "
        f"{PACKAGES}: {sorted(names)}")
    assert len(names) == len(found), f"duplicate discovery: {sorted(names)}"


@pytest.mark.parametrize(
    "name,root", _shared_contract_packages(), ids=lambda v: str(v)[:48])
def test_no_shared_contract_package_carries_the_role_projection(name, root):
    offenders = []
    for path in sorted((root / "src").rglob("*.py")):
        names = _defined_names(path.read_text(encoding="utf-8"), filename=str(path))
        hits = _projection_hits(names)
        if hits:
            offenders.append((path.name, hits))
    assert not offenders, f"{name} carries the projection: {offenders}"


@pytest.mark.parametrize(
    "name,root", _shared_contract_packages(), ids=lambda v: str(v)[:48])
def test_no_shared_contract_package_snapshot_carries_the_role_projection(name, root):
    """The curated public-API snapshots are the exported surface of record."""
    snapshots = sorted(root.glob("public_api.json"))
    if not snapshots:
        pytest.skip(f"{name} publishes no public_api.json snapshot")
    for snapshot in snapshots:
        hits = _snapshot_projection_hits(snapshot.read_text(encoding="utf-8"))
        assert not hits, f"{name}/{snapshot.name} exports {hits}"


@pytest.mark.parametrize(
    "name,root", _shared_contract_packages(), ids=lambda v: str(v)[:48])
def test_no_shared_contract_package_depends_on_this_capability(name, root):
    """A shared package cannot re-export what it cannot import."""
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert not _capability_dependency_hits(pyproject), f"{name} depends on this capability"
    for path in sorted((root / "src").rglob("*.py")):
        hits = _capability_dependency_hits(path.read_text(encoding="utf-8"))
        assert not hits, f"{name}/{path.name} references this capability: {hits}"


def test_the_projection_is_local_to_this_package_wherever_it_is_defined():
    """Repository-wide: the projection may exist in this package and nowhere else."""
    offenders = []
    for path in sorted(PACKAGES.rglob("*.py")):
        if PKG_ROOT in path.parents or any(
                part in {"build", "dist", ".venv", "__pycache__"} for part in path.parts):
            continue
        body = path.read_text(encoding="utf-8", errors="ignore")
        if any(marker in body for marker in PROJECTION_MARKERS):
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert not offenders, f"the projection escaped this capability: {offenders}"


# --------------------------------------------------------------------------- #
# The lifecycle-verb bound (D8), checked over this package's surface
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("path", sorted(SRC.rglob("*.py")), ids=lambda p: p.name)
def test_no_source_name_takes_role_lifecycle_authority(path):
    offenders = _lifecycle_offenders(
        path.read_text(encoding="utf-8"), filename=str(path))
    assert not offenders, f"{path.name} takes lifecycle authority: {offenders}"


def _runtime_position(value):
    """The position an imported object occupies, read from the object itself."""
    if isinstance(value, type):
        return TYPE
    return CALLABLE if callable(value) else BINDING


def _public_surface():
    """Every ``(name, position)`` reachable on the imported package.

    Exports, class members and model fields, each carrying what it actually is, so
    the runtime half applies O-2's rules the same way the source half does.
    """
    declared = set()
    modules = [ap]
    for info in pkgutil.walk_packages(ap.__path__, ap.__name__ + "."):
        modules.append(importlib.import_module(info.name))
    for module in modules:
        exported = getattr(module, "__all__", None) or [
            n for n in vars(module) if not n.startswith("_")]
        declared |= {(n, _runtime_position(getattr(module, n, None))) for n in exported}
        for attr_name in exported:
            attr = getattr(module, attr_name, None)
            if isinstance(attr, type):
                # Inherited str/Enum machinery is not this package's surface.
                inherited = set(dir(str)) | set(dir(enum.Enum))
                declared |= {(n, _runtime_position(getattr(attr, n, None)))
                             for n in dir(attr)
                             if not n.startswith("_") and n not in inherited}
                model_fields = getattr(attr, "model_fields", None)
                if isinstance(model_fields, dict):
                    declared |= {(n, FIELD) for n in model_fields}
    return declared


def test_the_imported_surface_takes_no_role_lifecycle_authority():
    offenders = _authority_offenders(_public_surface())
    assert not offenders, f"lifecycle authority on the public surface: {offenders}"


def test_the_runtime_position_reader_agrees_with_the_source_reader():
    """The two halves must classify the same thing the same way, or O-2's narrowing
    means one thing in ``src`` and another on the imported surface."""
    class _Sample:
        pass

    assert _runtime_position(_Sample) == TYPE
    assert _runtime_position(lambda: None) == CALLABLE
    assert _runtime_position("ACTIVE") == BINDING
    assert _authority_offenders({("RoleActivator", TYPE)}) == ["RoleActivator"]
    assert _authority_offenders({("issuer_ref", FIELD)}) == []


def test_the_bounds_are_pinned_to_the_ratified_wording():
    """D8's two enforceable bounds, asserted by equality so neither can be relaxed."""
    assert PROJECTION_MARKERS == ("CognitiveRole", "COGNITIVE_ROLE", "cognitive_role")
    # D8 names six verbs explicitly; an operation named for any of them is barred
    # in every position the capability could invoke it from.
    for verb in ("mint", "activate", "suspend", "ratify", "revoke", "replace"):
        for position in (CALLABLE, TYPE, FIELD, BINDING):
            assert _authority_offenders({(f"{verb}_role", position)}) == [f"{verb}_role"], \
                (verb, position)


def test_the_retained_governance_vocabulary_is_pinned():
    """O-2, asserted by equality on the names themselves.

    These five are the domain's words for a lifecycle state or a validity period
    that some other authority determined. The guard must permit each of them in a
    data position — a later re-widening that rejected them would fail here rather
    than force a rename.
    """
    retained = [
        ("SUSPENDED", BINDING),
        ("REVOKED", BINDING),
        ("RoleActivationStatus", TYPE),
        ("activation_status", FIELD),
        ("expires_at", FIELD),
    ]
    assert _authority_offenders(set(retained)) == []
    # And the narrowing is not a hole: authority over the same concepts still fails.
    assert _authority_offenders({("suspend", CALLABLE)}) == ["suspend"]
    assert _authority_offenders({("revoke_role", BINDING)}) == ["revoke_role"]
    assert _authority_offenders({("RoleActivator", TYPE)}) == ["RoleActivator"]
    assert _authority_offenders({("activation_status", CALLABLE_FIELD)}) == \
        ["activation_status"]
