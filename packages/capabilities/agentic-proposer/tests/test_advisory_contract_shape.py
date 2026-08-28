"""D7's contract shape, enforced mechanically.

Owner decision D7 fixes the recommendation artifact: it is ``ProposerAdvisory``,
carrying per-candidate ``CandidateAdvisory`` entries, kind
``ugence.agentic_proposer.advisory.v0``, identity field ``advisory_digest`` computed
only through ``ugence_jcs``, eight barred fields, and the barred name prefixes
``Proposal*`` and ``Recommendation*``. The ADR records the enforcement as ``[R]``:
S1 must assert all of it when it defines the contract.

Owner decision O-3 narrows the kind rule to the type that bears it. The kind and the
identity field belong to ``ProposerAdvisory`` alone; ``CandidateAdvisory`` is a
subordinate record carried inside it and must claim neither. The pair is still
ratified together — half a contract is not a contract — but only one half is
addressed to an authority.

Every check below is written so it does not depend on the contract already existing:

* the prefix bar, the kind-string bar and the identity-substrate rule are scanned
  over the package as it stands, and hold today;
* the shape assertions are parametrized over the ratified type names and arm
  themselves the moment those types appear, both halves together — a package that
  defined only one of the pair, or defined ``ProposerAdvisory`` carrying
  ``task_id`` three levels down, fails here.

The scanners are self-tested against synthetic sources, so a detector that stopped
matching fails rather than reporting a clean package. This matters more here than
usual: the contract's field set is not defined anywhere in this repository, so these
tests are the whole of the enforcement until it is.
"""
from __future__ import annotations

import ast
import importlib
import pathlib
import pkgutil
import typing

import pytest

import ugence_agentic_proposer as ap
import s1_specification_mirror as spec

SRC = pathlib.Path(ap.__file__).resolve().parent

#: The ratified pair. Both, or neither: half a contract is not a contract.
ADVISORY_TYPES = ("ProposerAdvisory", "CandidateAdvisory")
#: The ratified kind string, verbatim.
ADVISORY_KIND = "ugence.agentic_proposer.advisory.v0"
#: The namespace the ratified kind lives in. Pinned as a constant so narrowing it to
#: the ratified kind — which would make the rival-kind scan a tautology — fails the
#: equality assertion below instead of passing silently.
KIND_PREFIX = "ugence.agentic_proposer."
#: The single ratified identity field.
IDENTITY_FIELD = "advisory_digest"
#: The one type that declares the ratified kind (O-3). ``CandidateAdvisory`` is a
#: subordinate record carried inside the advisory, not a second advisory, and must
#: not claim the authority-facing kind.
KIND_BEARING_TYPE = "ProposerAdvisory"
#: Fields D7 bars from both types, at any nesting depth. Each is the mark of an
#: authority the proposer does not hold: a binding to an exact provider invocation,
#: to a replayable execution, or to a runtime execution context.
BARRED_FIELDS = frozenset({
    "fingerprint", "provider_id", "operation", "arguments",
    "idempotency_key", "workflow_id", "instance_id", "task_id",
})
#: Names owned elsewhere: ``Proposal*`` by Agent Runtime, ``Recommendation*`` by
#: Decision Authority. Case-sensitive prefixes on exported names; the ratified enum
#: MEMBERS ``PROPOSAL`` and ``RECOMMEND_*`` are values, not exported names.
BARRED_PREFIXES = ("Proposal", "Recommendation")
#: The only module permitted to produce identity (D2, D7).
IDENTITY_SUBSTRATE = "ugence_jcs"
#: Field names that would be a second identity next to ``advisory_digest``.
RIVAL_IDENTITY_FIELDS = frozenset({
    "id", "uid", "uuid", "identity", "identifier", "hash", "checksum",
    "content_hash", "advisory_id", "proposal_digest",
})


def _modules():
    yield ap
    for info in pkgutil.walk_packages(ap.__path__, ap.__name__ + "."):
        yield importlib.import_module(info.name)


def _public_names():
    """Every name the package exports: ``__all__`` where declared, public attrs else."""
    names = set()
    for module in _modules():
        declared = getattr(module, "__all__", None)
        names |= set(declared) if declared is not None else {
            n for n in vars(module) if not n.startswith("_")}
    return names


def _sources():
    return sorted(SRC.rglob("*.py"))


# --------------------------------------------------------------------------- #
# Scanners
# --------------------------------------------------------------------------- #

def _class_fields(tree):
    """Map each class in ``tree`` to its annotated fields: {class: {field: [types]}}."""
    out = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        fields = {}
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                referenced = [n.id for n in ast.walk(stmt.annotation)
                              if isinstance(n, ast.Name)]
                referenced += [n.attr for n in ast.walk(stmt.annotation)
                               if isinstance(n, ast.Attribute)]
                fields[stmt.target.id] = referenced
        out[node.name] = fields
    return out


def _fields_reachable_from(tree, roots):
    """Every field name reachable from ``roots``, following nested types to any depth."""
    classes = _class_fields(tree)
    seen, queue, found = set(), [r for r in roots if r in classes], set()
    while queue:
        current = queue.pop()
        if current in seen:
            continue
        seen.add(current)
        for field, referenced in classes.get(current, {}).items():
            found.add(field)
            queue += [name for name in referenced if name in classes]
    return found


def _runtime_owned_fields_reachable_from(model):
    """Every ``(owner, field)`` pair reachable from ``model``, following nested models to
    any depth.

    Ownership is carried, not discarded, because a bare name cannot say which contract
    declares it — and the digest exemption D7 grants is an entitlement of **one
    contract**, not of a spelling. A walk that returns names alone forces any exemption
    to be applied globally, which is how a nested shape bearing ``advisory_digest``
    escaped every root.
    """
    seen, queue, found = set(), [model], set()
    while queue:
        current = queue.pop()
        if current in seen or not isinstance(current, type):
            continue
        seen.add(current)
        model_fields = getattr(current, "model_fields", None)
        annotations = ({n: f.annotation for n, f in model_fields.items()}
                       if isinstance(model_fields, dict)
                       else dict(getattr(current, "__annotations__", {}) or {}))
        for name, annotation in annotations.items():
            found.add((current, name))
            queue += [a for a in (annotation,) + typing.get_args(annotation)
                      if isinstance(a, type)]
    return found


def _runtime_fields_reachable_from(model):
    """The same walk projected to bare names, for the guards that bar a name at **any**
    depth and so have no use for its owner."""
    return {name for _owner, name in _runtime_owned_fields_reachable_from(model)}


def _barred_prefix_names(names):
    """Names owned by another authority: ``Proposal*`` or ``Recommendation*``."""
    return sorted(n for n in names if n.startswith(BARRED_PREFIXES))


def _barred_prefix_definitions(source, filename="<sample>"):
    """Classes and functions defined here under a name owned by another authority."""
    tree = ast.parse(source, filename=filename)
    return sorted(node.name for node in ast.walk(tree)
                  if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                  and node.name.startswith(BARRED_PREFIXES))


def _declared_kind_strings(source, filename="<sample>"):
    """Every string constant in ``source`` that claims this package's kind namespace."""
    tree = ast.parse(source, filename=filename)
    return {node.value for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
            and node.value.startswith(KIND_PREFIX)}


def _identity_assignments(tree):
    """Every value expression assigned to the identity field."""
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == IDENTITY_FIELD and node.value is not None:
                out.append(node.value)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                name = (target.id if isinstance(target, ast.Name)
                        else target.attr if isinstance(target, ast.Attribute) else "")
                if name == IDENTITY_FIELD:
                    out.append(node.value)
        elif isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg == IDENTITY_FIELD:
                    out.append(keyword.value)
    return out


def _substrate_names(tree):
    """Names bound by importing the permitted identity substrate."""
    names, shadowed = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if node.level:
                # A RELATIVE import cannot reach the substrate: it names a module
                # inside this package. Seeding the permitted set with the bare
                # string would let a local module called ``ugence_jcs`` satisfy the
                # rule by name alone, which is the whole of what the rule asks.
                if root == IDENTITY_SUBSTRATE:
                    shadowed |= {a.asname or a.name for a in node.names}
                shadowed |= {a.asname or a.name for a in node.names
                             if a.name == IDENTITY_SUBSTRATE}
            elif root == IDENTITY_SUBSTRATE:
                names |= {a.asname or a.name for a in node.names}
                names.add(IDENTITY_SUBSTRATE)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == IDENTITY_SUBSTRATE:
                    names.add(alias.asname or alias.name.split(".")[0])
    return names - shadowed


def _root_name(node):
    while isinstance(node, ast.Attribute):
        node = node.value
    return node.id if isinstance(node, ast.Name) else ""


def _unpermitted_identity_sources(source, filename="<sample>"):
    """Identity values not produced by a call into the permitted substrate."""
    tree = ast.parse(source, filename=filename)
    permitted = _substrate_names(tree)
    offenders = []
    for value in _identity_assignments(tree):
        calls = [n for n in ast.walk(value) if isinstance(n, ast.Call)]
        if not calls:
            # A literal or a plain reference computes nothing; a constant identity is
            # not identity, so reject it too.
            offenders.append(ast.unparse(value))
            continue
        if not any(_root_name(call.func) in permitted for call in calls):
            offenders.append(ast.unparse(value))
    return offenders


# --------------------------------------------------------------------------- #
# Scanner self-tests
# --------------------------------------------------------------------------- #

NESTED_SAMPLE = (
    "class Inner:\n    task_id: str\n\n"
    "class Middle:\n    inner: Inner\n\n"
    "class ProposerAdvisory:\n    kind: str\n    middle: Middle\n"
)


def test_the_field_walk_reaches_a_barred_field_three_levels_down():
    tree = ast.parse(NESTED_SAMPLE)
    reachable = _fields_reachable_from(tree, ["ProposerAdvisory"])
    assert "task_id" in reachable
    assert reachable & BARRED_FIELDS == {"task_id"}


def test_the_field_walk_does_not_reach_unrelated_classes():
    tree = ast.parse("class Other:\n    provider_id: str\n\nclass ProposerAdvisory:\n    kind: str\n")
    assert _fields_reachable_from(tree, ["ProposerAdvisory"]) == {"kind"}


@pytest.mark.parametrize("sample", [
    "advisory_digest = _local_bytes(payload)\n",
    "self.advisory_digest = compute(payload)\n",
    "advisory_digest = '00' * 32\n",
    "ProposerAdvisory(advisory_digest=helper(payload))\n",
])
def test_the_identity_scanner_flags_a_foreign_identity_source(sample):
    assert _unpermitted_identity_sources(sample)


@pytest.mark.parametrize("sample", [
    "import ugence_jcs\nadvisory_digest = ugence_jcs.canonical_bytes(payload)\n",
    "from ugence_jcs import canonical_string\nadvisory_digest = canonical_string(payload)\n",
    "from ugence_jcs import canonical_string as cs\nself.advisory_digest = cs(payload)\n",
    "class M:\n    advisory_digest: str\n",
])
def test_the_identity_scanner_permits_only_the_declared_substrate(sample):
    assert not _unpermitted_identity_sources(sample)


@pytest.mark.parametrize("sample", [
    "from . import ugence_jcs\nadvisory_digest = ugence_jcs.canonical_sha256_hex(payload)\n",
    "from .ugence_jcs import canonical_sha256_hex\nadvisory_digest = canonical_sha256_hex(payload)\n",
    "from . import ugence_jcs as jcs\nadvisory_digest = jcs.canonical_sha256_hex(payload)\n",
])
def test_a_local_module_named_for_the_substrate_does_not_satisfy_the_rule(sample):
    """The substrate is a distribution, not a name.

    A module inside this package called ``ugence_jcs`` is reached by a RELATIVE
    import and can hash however it likes. Permitting it because the call reads
    ``ugence_jcs.canonical_sha256_hex`` would satisfy D7 by spelling alone.
    """
    assert _unpermitted_identity_sources(sample)


@pytest.mark.parametrize("names,expected", [
    ({"ProposerAdvisory", "ProposalDraft"}, ["ProposalDraft"]),
    ({"RecommendationSet", "CandidateAdvisory"}, ["RecommendationSet"]),
    ({"ProposalDraft", "RecommendationSet"}, ["ProposalDraft", "RecommendationSet"]),
    ({"ProposerAdvisory", "CandidateAdvisory", "PROPOSAL"}, []),
])
def test_the_prefix_scanner_flags_only_names_owned_elsewhere(names, expected):
    """``Proposer*`` is this package's; ``Proposal*`` is not, and the enum MEMBER
    ``PROPOSAL`` is a value rather than a name, so it must not be flagged."""
    assert _barred_prefix_names(names) == expected


@pytest.mark.parametrize("sample,expected", [
    ("class ProposalDraft:\n    pass\n", ["ProposalDraft"]),
    ("def RecommendationFor(x):\n    return x\n", ["RecommendationFor"]),
    ("async def ProposalBuild():\n    ...\n", ["ProposalBuild"]),
    ("class ProposerAdvisory:\n    pass\n", []),
    ("PROPOSAL = 'proposal'\n", []),
])
def test_the_definition_prefix_scanner_flags_a_barred_definition(sample, expected):
    assert _barred_prefix_definitions(sample) == expected


@pytest.mark.parametrize("sample,expected", [
    ("KIND = 'ugence.agentic_proposer.advisory.v1'\n",
     {"ugence.agentic_proposer.advisory.v1"}),
    ("KIND = 'ugence.agentic_proposer.draft.v0'\n",
     {"ugence.agentic_proposer.draft.v0"}),
    ("KIND = 'ugence.agentic_proposer.advisory.v0'\n", {ADVISORY_KIND}),
    ("KIND = 'ugence.decision_authority.recommendation.v0'\n", set()),
])
def test_the_kind_scanner_sees_every_claim_on_the_namespace(sample, expected):
    """It must see rival kinds, not only the ratified one. A scan narrowed to
    ``ADVISORY_KIND`` would return the ratified kind and nothing else, and the
    rival-kind assertion would hold vacuously forever."""
    assert _declared_kind_strings(sample) == expected


def test_the_runtime_field_walk_descends_into_nested_models():
    """The live-model twin of the source walk, self-tested to the same depth.

    Its source-level counterpart is self-tested above; without this, a runtime walk
    that stopped descending would report a clean model at every depth below one.
    """
    pydantic = pytest.importorskip("pydantic")

    class Inner(pydantic.BaseModel):
        task_id: str

    class Middle(pydantic.BaseModel):
        inner: Inner

    class Advisory(pydantic.BaseModel):
        kind: str
        middle: Middle

    reachable = _runtime_fields_reachable_from(Advisory)
    assert {"kind", "middle", "inner", "task_id"} <= reachable
    assert reachable & BARRED_FIELDS == {"task_id"}


def test_the_runtime_field_walk_follows_optional_and_sequence_arguments():
    """A barred field one union or list away is still reachable."""
    pydantic = pytest.importorskip("pydantic")

    class Entry(pydantic.BaseModel):
        provider_id: str

    class Advisory(pydantic.BaseModel):
        entries: typing.List[Entry]
        maybe: typing.Optional[Entry] = None

    assert "provider_id" in _runtime_fields_reachable_from(Advisory)


# --------------------------------------------------------------------------- #
# D7, enforced over the package
# --------------------------------------------------------------------------- #

def test_no_exported_name_begins_with_a_barred_prefix():
    """``Proposal*`` is Agent Runtime's; ``Recommendation*`` is Decision Authority's."""
    offenders = _barred_prefix_names(_public_names())
    assert not offenders, f"exported names owned elsewhere: {offenders}"


def test_no_class_or_function_in_the_source_begins_with_a_barred_prefix():
    """The bar is on the names, not only on what happens to be re-exported."""
    offenders = []
    for path in _sources():
        for name in _barred_prefix_definitions(
                path.read_text(encoding="utf-8"), filename=str(path)):
            offenders.append((path.name, name))
    assert not offenders, f"definitions named for another authority: {offenders}"


def test_the_ratified_pair_is_defined_together_or_not_at_all():
    """``ProposerAdvisory`` without ``CandidateAdvisory`` is not the ratified shape."""
    present = {name for name in ADVISORY_TYPES if hasattr(ap, name)}
    assert present in (set(), set(ADVISORY_TYPES)), f"half-defined contract: {present}"


def test_no_rival_kind_string_is_declared():
    """One kind, at one version. A second ``ugence.agentic_proposer.*`` kind would
    make the ratified one ambiguous, whatever it was named."""
    found = set()
    for path in _sources():
        found |= _declared_kind_strings(
            path.read_text(encoding="utf-8"), filename=str(path))
    assert found <= {ADVISORY_KIND}, f"unratified kind strings: {sorted(found)}"


@pytest.mark.parametrize("path", _sources(), ids=lambda p: p.name)
def test_identity_is_computed_only_through_the_permitted_substrate(path):
    offenders = _unpermitted_identity_sources(
        path.read_text(encoding="utf-8"), filename=str(path))
    assert not offenders, f"{path.name} computes identity outside {IDENTITY_SUBSTRATE}: {offenders}"


@pytest.mark.parametrize("path", _sources(), ids=lambda p: p.name)
def test_no_barred_field_appears_at_any_nesting_depth(path):
    """Reachability from the advisory types, so a barred field cannot hide in a
    nested model. Also checked source-wide: nothing in this package should carry a
    barred field at all, since each one names an authority it does not hold."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    reachable = _fields_reachable_from(tree, ADVISORY_TYPES)
    assert not reachable & BARRED_FIELDS, f"{path.name}: {sorted(reachable & BARRED_FIELDS)}"
    every_field = {f for fields in _class_fields(tree).values() for f in fields}
    assert not every_field & BARRED_FIELDS, f"{path.name}: {sorted(every_field & BARRED_FIELDS)}"


def _defined_advisory_types():
    return [(name, getattr(ap, name)) for name in ADVISORY_TYPES if hasattr(ap, name)]


@pytest.mark.parametrize("name,model", _defined_advisory_types(), ids=lambda v: str(v)[:40])
def test_a_defined_advisory_type_carries_no_barred_field_at_runtime(name, model):
    """Arms with the contract: the live model is walked to any depth."""
    reachable = _runtime_fields_reachable_from(model)
    assert not reachable & BARRED_FIELDS, sorted(reachable & BARRED_FIELDS)


def _declared_kinds_of(model):
    """Every kind string a live type declares: ``KIND``, ``kind``, or the default of
    a ``kind`` field."""
    declared = {getattr(model, "KIND", None), getattr(model, "kind", None)}
    fields = getattr(model, "model_fields", {}) or {}
    if "kind" in fields:
        declared.add(getattr(fields["kind"], "default", None))
    return {k.value if hasattr(k, "value") else k for k in declared if k is not None}


def test_the_kind_reader_sees_each_way_a_type_can_declare_one():
    """Self-test. A reader that stopped seeing one of the three spellings would
    report a clean ``CandidateAdvisory`` that claims the kind through the other."""
    pydantic = pytest.importorskip("pydantic")

    class ByConstant:
        KIND = ADVISORY_KIND

    class ByAttribute:
        kind = ADVISORY_KIND

    class ByDefault(pydantic.BaseModel):
        kind: str = ADVISORY_KIND

    class ByNothing:
        pass

    for model in (ByConstant, ByAttribute, ByDefault):
        assert _declared_kinds_of(model) == {ADVISORY_KIND}, model.__name__
    assert _declared_kinds_of(ByNothing) == set()


@pytest.mark.parametrize("name,model", _defined_advisory_types(), ids=lambda v: str(v)[:40])
def test_only_the_authority_facing_advisory_declares_the_ratified_kind(name, model):
    """O-3. The kind is ``ProposerAdvisory``'s and nothing else's.

    ``CandidateAdvisory`` is a subordinate per-candidate record carried inside the
    advisory; it is not itself addressed to an authority. A kind is what a consumer
    routes and stores on, so a candidate record declaring the advisory kind would be
    consumable as an advisory in its own right — the boundary D7 draws by naming,
    defeated by a field default.
    """
    declared = _declared_kinds_of(model)
    if name == KIND_BEARING_TYPE:
        assert ADVISORY_KIND in declared, (
            f"{name} does not declare the ratified kind: {sorted(declared)}")
    else:
        assert ADVISORY_KIND not in declared, (
            f"{name} claims the authority-facing advisory kind")
        assert not any(k.startswith(KIND_PREFIX) for k in declared), (
            f"{name} claims a kind in this capability's namespace: {sorted(declared)}")


@pytest.mark.parametrize("name,model", _defined_advisory_types(), ids=lambda v: str(v)[:40])
def test_identity_field_is_exactly_the_ratified_one(name, model):
    """``advisory_digest`` on the advisory, and no rival identity anywhere below it."""
    reachable = _runtime_fields_reachable_from(model)
    rivals = reachable & RIVAL_IDENTITY_FIELDS
    assert not rivals, f"a second identity field: {sorted(rivals)}"
    if name == "ProposerAdvisory":
        assert IDENTITY_FIELD in reachable


def test_the_enforcement_is_pinned_to_the_ratified_values():
    """D7's constants are asserted by equality, so none can be quietly relaxed."""
    assert ADVISORY_TYPES == ("ProposerAdvisory", "CandidateAdvisory")
    assert ADVISORY_KIND == "ugence.agentic_proposer.advisory.v0"
    assert KIND_PREFIX == "ugence.agentic_proposer."
    assert ADVISORY_KIND.startswith(KIND_PREFIX) and KIND_PREFIX != ADVISORY_KIND
    assert IDENTITY_FIELD == "advisory_digest"
    # O-3: one kind, borne by one type, and that type is the authority-facing one.
    assert KIND_BEARING_TYPE == "ProposerAdvisory"
    assert KIND_BEARING_TYPE in ADVISORY_TYPES
    assert BARRED_FIELDS == frozenset({
        "fingerprint", "provider_id", "operation", "arguments",
        "idempotency_key", "workflow_id", "instance_id", "task_id"})
    assert BARRED_PREFIXES == ("Proposal", "Recommendation")


# --------------------------------------------------------------------------- #
# I7.11 — rival-identity reachability against the corrected nested candidate graph
# --------------------------------------------------------------------------- #
#
# OD-4(a) restored the nesting ratified D7 requires: ``ProposerAdvisory`` carries an
# immutable ``candidates`` sequence of ``CandidateAdvisory`` and retains
# ``candidate_set_id`` as the reference to the top-level ``AdvisoryCandidateSet``.
#
# I7.11 requires this test to assert BOTH halves of that composition, so a change in
# either direction fails at the design boundary rather than deep in a guard:
#
#   * a nested ``ToolObservation`` is barred — A3 forces that half, because
#     ``ToolObservation.content_hash`` is a rival identity name and nesting the
#     observation makes it reachable from the advisory;
#   * a nested ``CandidateAdvisory`` is REQUIRED — a change back to reference-by-id
#     must fail here, not pass. A test that merely permits the nesting leaves the
#     ratified shape unpinned;
#   * no field of ``CandidateAdvisory`` may be a rival identity or a renamed digest.
#
# The walk runs against the representative shapes derived from the specification. It is
# the same walk the guards above run over ``src/``; when ``src/`` declares the
# contracts, it binds there and this becomes redundant rather than wrong.


@pytest.fixture(scope="module")
def graph():
    pytest.importorskip("pydantic")
    return spec.representative_shapes()


def test_the_advisory_reaches_every_candidate_field(graph):
    """The premise of the walk. If the candidates were not reachable, every assertion
    below would pass vacuously — which is exactly how a reference-by-id shape would
    slip past a walk written to bar things."""
    reachable = _runtime_fields_reachable_from(graph["ProposerAdvisory"])
    candidate_fields = set(graph["CandidateAdvisory"].model_fields)
    assert candidate_fields <= reachable, sorted(candidate_fields - reachable)
    assert "candidates" in reachable and "candidate_set_id" in reachable


#: Substrings that make a field name a *renamed* digest. D6 bars "a field of any name
#: whose value is a digest, fingerprint or hash of this candidate's content", so the
#: exact-name list is only half the rule and this closes the other half by shape.
DIGEST_SHAPED_MARKS = ("digest", "fingerprint", "hash", "checksum")

#: The only digest-shaped names D7 sanctions on ``ProposerAdvisory``, exempted by exact
#: name rather than by weakening the shape rule for everything.
#:
#: * ``advisory_digest`` is the **sole identity field** (D7).
#: * ``parent_advisory_digest`` is **lineage, not identity**: it holds the parent's
#:   digest, is C6-shaped, participates in identity including when ``null``, and L-1 bars
#:   it from equalling this advisory's own digest. It names another advisory's identity;
#:   it does not mint a second one for this advisory.
#:
#: Pinned by equality in
#: ``test_the_identity_exemption_is_exactly_the_two_ratified_fields``
#: so it cannot be widened to hide a rival. ``CandidateAdvisory`` gets **no** exemption:
#: it carries no identity at all.
RATIFIED_DIGEST_FIELDS = frozenset({"advisory_digest", "parent_advisory_digest"})


def _owner_name(owner):
    """A stable label for the model that declares a field, used in sort keys and in
    failure text so a nested rival names the shape it was planted on."""
    return getattr(owner, "__name__", str(owner))


def _rival_identity_failures(root, walker=None, exempt=RATIFIED_DIGEST_FIELDS):
    """Why ``root`` carries a rival identity, if it does. Empty means it does not.

    This is the whole of D6's standing prohibition as the guard applies it, in one
    place, so the live assertion and its mutation controls run the **same** code rather
    than two copies that can drift apart:

    * a reachable field whose name is on ``RIVAL_IDENTITY_FIELDS`` by exact match;
    * a reachable field whose name is on ``BARRED_FIELDS`` (D7's eight);
    * a reachable field that is **digest-shaped by name** — the renamed equivalent, which
      an exact-name list cannot see.

    ``exempt`` holds the sanctioned digest-shaped names — ``advisory_digest``, the sole
    identity D7 ratifies, and ``parent_advisory_digest``, which names the *parent's*
    identity rather than minting a second one here. Both are digest-shaped on purpose, so
    they are exempted by exact name rather than by weakening the shape rule for
    everything.

    **The exemption is scoped to the bearer.** It applies only to a field ``root`` itself
    declares; a field of the same name on anything nested is barred like any other
    renamed digest. That scoping is the whole reason the walk carries ownership. Applied
    globally — as an earlier revision applied it — a nested shape bearing
    ``advisory_digest`` was reported by no root at all: not by the advisory, which
    exempted the name wherever it appeared, and not by the candidate, from which such a
    shape need not be reachable. That is a second identity inside ``P_unsigned``, which is
    precisely what D6 bars.

    ``walker`` is injectable so a negative control can prove the verdict depends on the
    reachability walk and not on something the test arranged for itself. It must return
    ``(owner, field)`` pairs.
    """
    walk = _runtime_owned_fields_reachable_from if walker is None else walker
    owned = walk(root)
    reachable = {name for _owner, name in owned}
    failures = []
    for name in sorted(reachable & RIVAL_IDENTITY_FIELDS):
        failures.append(f"rival identity name reachable: {name}")
    for name in sorted(reachable & BARRED_FIELDS):
        failures.append(f"barred field reachable: {name}")
    for owner, name in sorted(owned, key=lambda pair: (pair[1], _owner_name(pair[0]))):
        if name in RIVAL_IDENTITY_FIELDS:
            continue
        if name in exempt and owner is root:
            continue
        if any(mark in name for mark in DIGEST_SHAPED_MARKS):
            failures.append(f"renamed digest reachable: {name}"
                            + ("" if owner is root else f" (declared on "
                                                        f"{_owner_name(owner)})"))
    return failures


#: The two advisory roots the guard walks, and the only two.
ADVISORY_ROOTS = ("ProposerAdvisory", "CandidateAdvisory")


def _exemption_for(root):
    """Which digest-shaped names this root is **entitled to declare on itself**.

    ``ProposerAdvisory`` earns the exemption: D7 ratifies ``advisory_digest`` as its sole
    identity and ``parent_advisory_digest`` as lineage, and both are digest-shaped on
    purpose. ``CandidateAdvisory`` earns none, because it carries no identity at all.

    Entitlement and scope are two separate things and both are needed.
    ``_rival_identity_failures`` supplies the scope — it honours ``exempt`` only for
    fields the root itself declares — and this function supplies the entitlement, so that
    the candidate does not gain the advisory's exemption merely by being walked as a
    root. Factoring the choice out also means a control can run the guard's own
    configuration instead of re-stating it: a control that passed ``exempt=frozenset()``
    itself would keep passing after this function was widened.
    """
    return RATIFIED_DIGEST_FIELDS if root == "ProposerAdvisory" else frozenset()


def _root_failures(root, graph, model=None):
    """The live guard's verdict for one advisory root, exemption included.

    ``model`` substitutes a mutated shape for the ratified one while keeping the root's
    own exemption, so a mutation control exercises this code rather than a copy of it.
    """
    target = graph[root] if model is None else model
    return _rival_identity_failures(target, exempt=_exemption_for(root))


def test_no_rival_identity_is_reachable_from_either_advisory_root(graph):
    """`reachable & RIVAL_IDENTITY_FIELDS` is empty for both roots, on the corrected
    graph. ``advisory_digest`` stays the sole identity field.

    Each root is walked under its own exemption — the advisory's two ratified digest
    names, and nothing at all for the candidate, which carries no identity and so needs
    no exemption.
    """
    for root in ADVISORY_ROOTS:
        assert not _root_failures(root, graph), f"{root}: {_root_failures(root, graph)}"
    assert IDENTITY_FIELD in _runtime_fields_reachable_from(graph["ProposerAdvisory"])
    assert IDENTITY_FIELD not in set(graph["CandidateAdvisory"].model_fields)
    assert _exemption_for("CandidateAdvisory") == frozenset(), (
        "the candidate is entitled to no digest-shaped name; it carries no identity")


def _reachable_models(model):
    seen, queue = set(), [model]
    while queue:
        current = queue.pop()
        if current in seen or not isinstance(current, type):
            continue
        seen.add(current)
        fields = getattr(current, "model_fields", None)
        if not isinstance(fields, dict):
            continue
        for field in fields.values():
            stack = [field.annotation]
            while stack:
                annotation = stack.pop()
                if isinstance(annotation, type):
                    queue.append(annotation)
                stack.extend(a for a in typing.get_args(annotation) if a is not Ellipsis)
    return seen


def test_a_tool_observation_is_not_reachable_from_either_advisory(graph):
    """A3's half. ``ToolObservation.content_hash`` is a rival identity name; nesting the
    observation would reintroduce through the candidate exactly what A3 bars directly.
    Evidence stays reference-by-id through ``observation_refs``."""
    for root in ("ProposerAdvisory", "CandidateAdvisory"):
        models = _reachable_models(graph[root])
        assert graph["ToolObservation"] not in models, root
        assert "content_hash" not in _runtime_fields_reachable_from(graph[root]), root
    assert "observation_refs" in graph["CandidateAdvisory"].model_fields


def _nested_candidate_failures(advisory, candidate_type):
    """Why ``advisory`` does not carry the ratified nested candidate sequence, if it does
    not. Empty means the composition holds.

    Factored out so the mutation control below runs a **real model** through exactly this
    code rather than through a parallel reimplementation of it. A mutation control that
    re-derives the rule is testing its own copy of the rule.
    """
    failures = []
    field = advisory.model_fields.get("candidates")
    if field is None:
        failures.append(
            "declares no candidates sequence; this is the reference-by-id shape OD-4 "
            "rejected")
        return failures
    annotation = field.annotation
    if typing.get_origin(annotation) is not tuple:
        failures.append(f"candidates is {annotation!r}, not a tuple")
        return failures
    args = typing.get_args(annotation)
    if len(args) != 2 or args[1] is not Ellipsis:
        failures.append("candidates is not a homogeneous variadic tuple")
    elif args[0] is not candidate_type:
        failures.append(f"candidates carries {args[0]!r}, not CandidateAdvisory")
    if candidate_type not in _reachable_models(advisory):
        failures.append("CandidateAdvisory is not in the advisory's reachable model set")
    return failures


def test_the_nested_candidate_advisory_is_required_not_merely_permitted(graph):
    """OD-4(a)'s half, and the one an earlier statement of this obligation left too
    weak. ``ProposerAdvisory.candidates`` must be declared, must be a sequence of
    ``CandidateAdvisory``, and ``CandidateAdvisory`` must appear in the advisory's
    reachable model set. **A reversion to reference-by-id fails here.**"""
    failures = _nested_candidate_failures(graph["ProposerAdvisory"],
                                          graph["CandidateAdvisory"])
    assert not failures, f"ProposerAdvisory: {failures}"


def test_the_candidate_set_reference_is_retained_alongside_the_nesting(graph):
    """OD-4(a) retains ``candidate_set_id``; it does not replace it with the nesting.
    Twenty-three fields, not twenty-two."""
    assert "candidate_set_id" in graph["ProposerAdvisory"].model_fields
    # OD-7 part 5 moved this from 23 to 27 (I8.11).
    assert len(graph["ProposerAdvisory"].model_fields) == 27
    assert "AdvisoryCandidateSet" in spec.TOP_LEVEL_CONTRACTS


def test_a_mutant_that_reverts_to_reference_by_id_fails(graph):
    """Mutation control for the required half, run through the same assertion the live
    test uses rather than through set arithmetic over field names.

    The mutant is a **real model**: an advisory that references its candidates solely by
    ``candidate_set_id``, which is the shape OD-4 rejected and the shape a future change
    would most plausibly reintroduce. It is fed to ``_nested_candidate_failures`` — the
    function the live assertion calls — and must be reported as failing. A control that
    only observed that a name is absent from a set would pass even if the live assertion
    had been deleted.
    """
    pydantic = pytest.importorskip("pydantic")

    class ReferenceByIdAdvisory(pydantic.BaseModel):
        advisory_digest: str
        candidate_set_id: str

    failures = _nested_candidate_failures(ReferenceByIdAdvisory,
                                          graph["CandidateAdvisory"])
    assert failures, (
        "the reference-by-id mutant was accepted; the nested-candidate requirement is "
        "not being enforced")
    assert any("no candidates sequence" in f for f in failures), failures
    assert graph["CandidateAdvisory"] not in _reachable_models(ReferenceByIdAdvisory)

    # And a second mutant that keeps the field but loses the ratified element type, so
    # the control covers the weaker reversion too — a sequence of identifiers rather
    # than of candidates.
    class IdSequenceAdvisory(pydantic.BaseModel):
        advisory_digest: str
        candidate_set_id: str
        candidates: tuple[str, ...]

    weaker = _nested_candidate_failures(IdSequenceAdvisory, graph["CandidateAdvisory"])
    assert weaker, "a tuple of identifiers is not a tuple of CandidateAdvisory"
    assert any("not CandidateAdvisory" in f for f in weaker), weaker

    # The ratified shape passes the same function, so the control is discriminating
    # rather than merely negative.
    assert not _nested_candidate_failures(graph["ProposerAdvisory"],
                                          graph["CandidateAdvisory"])


#: Every rival identity name D6 bars by exact match, plus renamed equivalents the exact
#: list cannot see, plus the two names the advisory's exemption sanctions. Each is
#: planted on a real model below.
#:
#: The last two are the names D7 sanctions **on the advisory itself**. They are planted
#: here because the exemption is an entitlement of one contract, not of a spelling: a
#: nested shape bearing either is a second identity inside ``P_unsigned``, and must fail
#: from the advisory root like any other rival. An earlier revision applied the exemption
#: by name across the whole reachable graph, and these two mutations are what a control
#: needs to keep that from returning.
RIVAL_IDENTITY_MUTATIONS = tuple(sorted(RIVAL_IDENTITY_FIELDS)) + (
    "candidate_digest", "body_fingerprint", "payload_checksum", "row_hash",
) + tuple(sorted(RATIFIED_DIGEST_FIELDS))


def _candidate_bearing(rival, base):
    """The ratified ``CandidateAdvisory`` representative shape with one rival identity
    field added — a real model, built by subclassing so the other ten fields are the
    ratified ones and the only difference is the mutation."""
    pydantic = pytest.importorskip("pydantic")
    return pydantic.create_model(
        "MutantCandidateAdvisory", __base__=base, **{rival: (str, ...)})


@pytest.mark.parametrize("rival", RIVAL_IDENTITY_MUTATIONS)
def test_a_mutant_adding_a_second_identity_to_the_candidate_fails(graph, rival):
    """D6's standing prohibition, as a **real mutated model** run through the same
    verdict the live guard uses.

    A per-candidate digest would be a second identity inside the first — and now that the
    candidates are inside ``P_unsigned``, one *covered by* the first, which is worse than
    one standing beside it.

    The mutant starts from the ratified ``CandidateAdvisory`` shape and adds one rival
    field, then goes through ``_rival_identity_failures`` — the function
    ``test_no_rival_identity_is_reachable_from_either_advisory_root`` calls. It must fail
    because the rival is **actually reachable** by the walk, not because a set of names
    was compared with another set of names.
    """
    base = graph["CandidateAdvisory"]
    mutant = _candidate_bearing(rival, base)

    assert not _rival_identity_failures(base, exempt=frozenset()), (
        "precondition: the unmodified ratified shape carries no rival identity")

    failures = _rival_identity_failures(mutant, exempt=frozenset())
    assert failures, f"a second identity named {rival!r} was not caught"
    assert any(rival in f for f in failures), (
        f"the failure does not name the planted field: {failures}")
    assert rival in _runtime_fields_reachable_from(mutant), (
        "the mutation must actually be reachable, or the control proves nothing")


@pytest.mark.parametrize("rival", RIVAL_IDENTITY_MUTATIONS)
def test_a_second_identity_on_a_nested_candidate_is_reachable_from_the_advisory(graph,
                                                                                rival):
    """The nesting half. OD-4(a) put the candidates inside ``P_unsigned``, so a rival on
    a nested candidate is reachable from ``ProposerAdvisory`` and covered by its digest.
    The walk must find it from the advisory root, not only from the candidate."""
    pydantic = pytest.importorskip("pydantic")
    mutant_candidate = _candidate_bearing(rival, graph["CandidateAdvisory"])

    class AdvisoryWithMutantCandidates(pydantic.BaseModel):
        advisory_digest: str
        candidate_set_id: str
        candidates: tuple[mutant_candidate, ...]

    assert rival in _runtime_fields_reachable_from(AdvisoryWithMutantCandidates), (
        "the mutation must actually be reachable, or the control proves nothing")

    failures = _root_failures("ProposerAdvisory", graph,
                              model=AdvisoryWithMutantCandidates)
    assert failures, f"a nested second identity named {rival!r} was not caught"
    assert any(rival in f for f in failures), failures


@pytest.mark.parametrize("sanctioned", tuple(sorted(RATIFIED_DIGEST_FIELDS)))
def test_a_sanctioned_name_on_a_shape_off_the_advisory_alone_still_fails(graph,
                                                                        sanctioned):
    """The escape a globally applied exemption left open, pinned as a regression.

    The shape hangs off ``ProposerAdvisory`` and is **not** reachable from
    ``CandidateAdvisory``, so the candidate root cannot see it however it is walked. When
    the exemption was applied by name over the whole graph, the advisory root exempted it
    too and the field was reported by **neither** root — a second identity inside
    ``P_unsigned``, which is exactly what D6 bars.

    Scoping the exemption to the bearer is what closes it: the advisory may declare these
    two names on itself, and nothing nested may declare them at all.
    """
    pydantic = pytest.importorskip("pydantic")

    class Lineage(pydantic.BaseModel):
        __annotations__ = {sanctioned: str}

    class AdvisoryWithLineageShape(pydantic.BaseModel):
        advisory_digest: str
        parent_advisory_digest: str
        candidate_set_id: str
        candidates: tuple[graph["CandidateAdvisory"], ...]
        lineage: Lineage

    assert Lineage not in _reachable_models(graph["CandidateAdvisory"]), (
        "precondition: the candidate root cannot reach this shape, so it cannot be the "
        "thing that catches it")

    failures = _root_failures("ProposerAdvisory", graph,
                              model=AdvisoryWithLineageShape)
    assert failures, (
        f"a shape declaring {sanctioned!r} off the advisory escaped every root; the "
        "exemption has been widened back to the whole reachable graph")
    assert any(sanctioned in f and "Lineage" in f for f in failures), failures

    # And the advisory's own two declarations are still lawful, so the fix is a scoping
    # of the exemption rather than its removal.
    assert not _root_failures("ProposerAdvisory", graph), (
        "the ratified advisory declares both names on itself and must still pass")


def test_the_identity_exemption_is_exactly_the_two_ratified_fields(graph):
    """The exemption is the one place this guard could be blunted, so it is pinned.

    Widening it would let a renamed digest through by name. Narrowing it would fail the
    ratified advisory, which carries both. Also asserted: the candidate is granted no
    exemption at all, because it carries no identity.
    """
    assert RATIFIED_DIGEST_FIELDS == {"advisory_digest", "parent_advisory_digest"}
    advisory_fields = set(graph["ProposerAdvisory"].model_fields)
    assert RATIFIED_DIGEST_FIELDS <= advisory_fields
    assert RATIFIED_DIGEST_FIELDS & set(graph["CandidateAdvisory"].model_fields) == set()

    # Widening the exemption to a renamed digest must actually hide it — which is why
    # the set is pinned rather than trusted.
    mutant = _candidate_bearing("candidate_digest", graph["CandidateAdvisory"])
    assert _rival_identity_failures(mutant, exempt=frozenset())
    assert not _rival_identity_failures(
        mutant, exempt=frozenset({"candidate_digest"})), (
        "a widened exemption hides the rival; that is what the equality pin above "
        "prevents")


def test_sabotaging_the_walker_makes_the_rival_mutant_escape(graph):
    """Negative control for the control: the verdict must depend on the reachability
    walk, not on anything the test arranged for itself.

    A blinded walker — one that reports the root's own fields and never descends, or one
    that reports nothing — is injected, and the mutant that the real walk catches must
    then escape. If the mutant still failed under a blinded walker, the mutation control
    above would be passing for a reason unrelated to reachability.
    """
    mutant = _candidate_bearing("candidate_digest", graph["CandidateAdvisory"])
    assert _rival_identity_failures(mutant, exempt=frozenset()), (
        "precondition: the real walker catches this mutant")

    assert not _rival_identity_failures(
        mutant, walker=lambda model: set(), exempt=frozenset()), (
        "a walker that reports nothing must let the mutant escape, proving the verdict "
        "is driven by the walk")

    nested = _candidate_bearing("candidate_digest", graph["CandidateAdvisory"])

    class Advisory(pytest.importorskip("pydantic").BaseModel):
        advisory_digest: str
        candidates: tuple[nested, ...]

    assert _rival_identity_failures(Advisory), (
        "precondition: the real walker descends into the nested candidate")
    shallow = lambda model: {(model, name)
                             for name in getattr(model, "model_fields", {})}
    assert not _rival_identity_failures(Advisory, walker=shallow), (
        "a non-descending walker must miss the nested rival, proving the descent is "
        "what catches it")


def test_the_name_predicate_alone_is_supplemental_not_the_enforcement_proof():
    """Helper self-test, clearly labelled.

    ``DIGEST_SHAPED_MARKS`` is a name predicate, and a name predicate on its own proves
    nothing about a model: it says which spellings *would* be caught if they appeared, not
    that none appears. The enforcement proof is the reachability walk above. This exists
    only so the mark list itself is exercised, and it must never be read as the guard.
    """
    for rival in RIVAL_IDENTITY_MUTATIONS:
        recognised = (rival in RIVAL_IDENTITY_FIELDS
                      or any(mark in rival for mark in DIGEST_SHAPED_MARKS))
        assert recognised, f"a planted mutation no predicate recognises: {rival}"
    assert not any(mark in "candidate_id" for mark in DIGEST_SHAPED_MARKS), (
        "the mark list must not match an ordinary identifier field")


def test_a_mutant_nesting_a_tool_observation_fails(graph):
    """Mutation control for the barred half, run through the same reachability walk the
    real assertion uses rather than through a parallel reimplementation of it."""
    pydantic = pytest.importorskip("pydantic")

    class MutantCandidate(pydantic.BaseModel):
        candidate_id: str
        observation: graph["ToolObservation"]

    class MutantAdvisory(pydantic.BaseModel):
        advisory_digest: str
        candidates: tuple[MutantCandidate, ...]

    reachable = _runtime_fields_reachable_from(MutantAdvisory)
    assert "content_hash" in reachable, "the mutant must actually reintroduce the rival"
    assert reachable & RIVAL_IDENTITY_FIELDS, (
        "the walk must catch a rival identity reached through a nested observation")
    assert graph["ToolObservation"] in _reachable_models(MutantAdvisory)


# --------------------------------------------------------------------------- #
# OD-5 — neither strategy field is inside the frozen projection
# --------------------------------------------------------------------------- #

#: The strategy names OD-5 keeps outside ``P_unsigned``.
#:
#: ``declared_strategy`` is a claim the process record makes about the method it used. It
#: is not a property of the advisory and may not reach the digest: bringing it inside
#: would make it identity-participating and so expose it to the B9 hazard OD-1's rider is
#: explicit about, and would make an advisory's identity depend on an assertion nothing in
#: this stage verifies.
#:
#: ``permitted_reasoning_strategies`` is listed beside it although **no S1 contract
#: declares it** — the owner deferred it to S2 with its vocabulary (Part J). Keeping the
#: name here is not redundant with its absence from the mirror: if a later change
#: reintroduces the field, this guard fails unless it is also kept out of the advisory,
#: which is the property OD-5 cares about and the cardinality pin does not express.
STRATEGY_FIELDS_OUTSIDE_IDENTITY = ("declared_strategy", "permitted_reasoning_strategies")


def _projection_keys(payload, prefix=""):
    """Every key in a ``model_dump`` projection, nested keys included and path-qualified.

    A flat top-level check would pass a design that hid either field one level down, on a
    nested candidate, which is exactly where OD-4(a) made new content reachable.
    """
    keys = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            keys.add(f"{prefix}{key}")
            keys |= _projection_keys(value, f"{prefix}{key}.")
    elif isinstance(payload, (list, tuple)):
        for item in payload:
            keys |= _projection_keys(item, f"{prefix}[].")
    return keys


@pytest.fixture(scope="module")
def unsigned_projection(graph):
    """``P_unsigned`` exactly as G1 freezes it, built from a complete advisory."""
    pytest.importorskip("pydantic")
    advisory = graph["ProposerAdvisory"](**spec.complete_advisory_fixture())
    return advisory.model_dump(mode="json", exclude={"advisory_digest"},
                               exclude_none=False)


@pytest.mark.parametrize("field", STRATEGY_FIELDS_OUTSIDE_IDENTITY)
def test_no_strategy_field_appears_in_the_unsigned_projection(unsigned_projection, field):
    """OD-5: strategy is metadata, and metadata is not identity."""
    offenders = sorted(key for key in _projection_keys(unsigned_projection)
                       if key.rsplit(".", 1)[-1] == field)
    assert not offenders, (
        f"{field!r} is inside P_unsigned at {offenders}; it would be covered by "
        "advisory_digest, which OD-5 says it is not")


def test_the_projection_probe_would_notice_a_field_that_did_appear(unsigned_projection):
    """The control. The assertion above runs over a projection that legitimately lacks
    both names, and a walker that returned nothing would report exactly the same pass.

    Two things are proved: the walker reaches real content at both levels, and a planted
    key at either level is found. Without this, deleting the recursion would leave the
    guard green.
    """
    keys = _projection_keys(unsigned_projection)
    assert "case_ref" in keys, "the walker does not reach top-level keys"
    assert any(key.startswith("candidates.[].") for key in keys), (
        "the walker does not descend into the nested candidates OD-4(a) added")
    assert "advisory_digest" not in keys, "G1 excludes the digest from its own projection"

    for planted in ({"declared_strategy": "x"},
                    {"candidates": [{"permitted_reasoning_strategies": []}]}):
        found = _projection_keys(planted)
        assert any(key.rsplit(".", 1)[-1] in STRATEGY_FIELDS_OUTSIDE_IDENTITY
                   for key in found), (
            f"the walker misses a planted strategy field in {planted!r}")


def test_neither_strategy_field_is_declared_on_either_advisory_type(graph):
    """The same rule read off the shapes rather than off one instance's projection.

    A field excluded from a dump — by an alias, an ``exclude`` marker, or a serializer —
    would pass the projection check while still being declared on the advisory, and a
    later change to how the model dumps would then bring it inside the digest silently.
    """
    for root in ("ProposerAdvisory", "CandidateAdvisory"):
        reachable = _runtime_fields_reachable_from(graph[root])
        for field in STRATEGY_FIELDS_OUTSIDE_IDENTITY:
            assert field not in reachable, (
                f"{field!r} is reachable from {root}; OD-5 keeps it outside P_unsigned")
    # ``declared_strategy`` still exists on its bearer, so the assertion above is about
    # placement rather than about the field having quietly ceased to exist.
    assert "declared_strategy" in graph["ProposerProcessRecord"].model_fields
    # ``permitted_reasoning_strategies`` is deferred to S2 and is declared by NO contract.
    # Asserted so the deferral is a checked fact rather than an omission a reader has to
    # notice, and so reintroducing the field trips this test as well as the mirror's pins.
    for contract in spec.TOP_LEVEL_CONTRACTS + spec.NESTED_PUBLIC_SHAPES:
        assert "permitted_reasoning_strategies" not in graph[contract].model_fields, (
            f"{contract} declares permitted_reasoning_strategies; OD-5 defers it to S2")


# --------------------------------------------------------------------------- #
# I7.11 on the DECLARED surface — armed by the first contract module
# --------------------------------------------------------------------------- #
#
# The assertions above run against the representative shapes, so they hold today. These
# run against whatever ``src/`` declares, and are dormant until it declares an advisory.
# Both are needed: the representative version states the rule executably now, and this
# one is what actually binds the production contract when it lands.


def _declared_advisory_classes():
    """``{class_name: ast.ClassDef}`` for the ratified advisory types, if declared."""
    found = {}
    for path in _sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name in ADVISORY_TYPES:
                found[node.name] = (path, node)
    return found


def _annotation_names(node):
    names = [n.id for n in ast.walk(node) if isinstance(n, ast.Name)]
    names += [n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)]
    return names


def test_a_declared_advisory_requires_its_nested_candidates():
    """OD-4(a) on the declared surface. **A reversion to reference-by-id fails here.**

    ``ProposerAdvisory`` must declare a ``candidates`` field whose annotation names
    ``CandidateAdvisory``. An advisory that carries only ``candidate_set_id`` is the
    shape OD-4 rejected, and it must fail rather than pass unexamined.
    """
    declared = _declared_advisory_classes()
    if "ProposerAdvisory" not in declared:
        pytest.skip("no ProposerAdvisory is declared in src yet")
    path, node = declared["ProposerAdvisory"]
    fields = {stmt.target.id: stmt.annotation for stmt in node.body
              if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)}
    assert "candidates" in fields, (
        f"{path.name}: ProposerAdvisory declares no candidates sequence; ratified D7 "
        "carries per-candidate CandidateAdvisory entries, and reference-by-id is the "
        "rejected alternative (OD-4(a))")
    assert "CandidateAdvisory" in _annotation_names(fields["candidates"]), (
        f"{path.name}: ProposerAdvisory.candidates is not a sequence of "
        f"CandidateAdvisory: {ast.unparse(fields['candidates'])}")
    assert "tuple" in ast.unparse(fields["candidates"]).lower(), (
        "the sequence is an immutable tuple on a frozen model, not a list")
    assert "candidate_set_id" in fields, (
        "candidate_set_id is retained as the reference to AdvisoryCandidateSet, not "
        "replaced by the nesting")


def test_a_declared_advisory_nests_no_tool_observation():
    """A3's half on the declared surface. ``ToolObservation.content_hash`` is a rival
    identity name; nesting the observation makes it reachable from the advisory."""
    declared = _declared_advisory_classes()
    if not declared:
        pytest.skip("no advisory type is declared in src yet")
    for name, (path, node) in declared.items():
        for stmt in node.body:
            if not (isinstance(stmt, ast.AnnAssign)
                    and isinstance(stmt.target, ast.Name)):
                continue
            assert "ToolObservation" not in _annotation_names(stmt.annotation), (
                f"{path.name}: {name}.{stmt.target.id} nests ToolObservation; evidence "
                "stays reference-by-id through observation_refs")


def test_a_declared_candidate_carries_no_second_identity():
    """D6's standing prohibition on the declared surface: no rival identity name, and
    no renamed digest."""
    declared = _declared_advisory_classes()
    if "CandidateAdvisory" not in declared:
        pytest.skip("no CandidateAdvisory is declared in src yet")
    path, node = declared["CandidateAdvisory"]
    names = {stmt.target.id for stmt in node.body
             if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)}
    rivals = names & RIVAL_IDENTITY_FIELDS
    assert not rivals, f"{path.name}: CandidateAdvisory carries {sorted(rivals)}"
    renamed = {n for n in names
               if any(mark in n for mark in ("digest", "fingerprint", "checksum"))}
    assert not renamed, (
        f"{path.name}: CandidateAdvisory carries a renamed digest {sorted(renamed)}; "
        "advisory_digest is the sole identity field")
    assert names == set(spec.FIELD_CLASSIFICATION["CandidateAdvisory"]), (
        f"{path.name}: CandidateAdvisory's declared fields do not match the ratified "
        "ten; the registry is a mirror of the specification, not a description of src")
