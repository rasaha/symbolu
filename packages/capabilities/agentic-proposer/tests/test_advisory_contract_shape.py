"""D7's contract shape, enforced mechanically.

Owner decision D7 fixes the recommendation artifact: it is ``ProposerAdvisory``,
carrying per-candidate ``CandidateAdvisory`` entries, kind
``ugence.agentic_proposer.advisory.v0``, identity field ``advisory_digest`` computed
only through ``ugence_jcs``, eight barred fields, and the barred name prefixes
``Proposal*`` and ``Recommendation*``. The ADR records the enforcement as ``[R]``:
S1 must assert all of it when it defines the contract.

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

SRC = pathlib.Path(ap.__file__).resolve().parent

#: The ratified pair. Both, or neither: half a contract is not a contract.
ADVISORY_TYPES = ("ProposerAdvisory", "CandidateAdvisory")
#: The ratified kind string, verbatim.
ADVISORY_KIND = "ugence.agentic_proposer.advisory.v0"
#: The single ratified identity field.
IDENTITY_FIELD = "advisory_digest"
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


def _runtime_fields_reachable_from(model):
    """The same walk over a live pydantic model, following nested models to any depth."""
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
            found.add(name)
            queue += [a for a in (annotation,) + typing.get_args(annotation)
                      if isinstance(a, type)]
    return found


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
    names = {IDENTITY_SUBSTRATE}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == IDENTITY_SUBSTRATE:
            names |= {a.asname or a.name for a in node.names}
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == IDENTITY_SUBSTRATE:
                    names.add(alias.asname or alias.name.split(".")[0])
    return names


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


# --------------------------------------------------------------------------- #
# D7, enforced over the package
# --------------------------------------------------------------------------- #

def test_no_exported_name_begins_with_a_barred_prefix():
    """``Proposal*`` is Agent Runtime's; ``Recommendation*`` is Decision Authority's."""
    offenders = sorted(n for n in _public_names() if n.startswith(BARRED_PREFIXES))
    assert not offenders, f"exported names owned elsewhere: {offenders}"


def test_no_class_or_function_in_the_source_begins_with_a_barred_prefix():
    """The bar is on the names, not only on what happens to be re-exported."""
    offenders = []
    for path in _sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith(BARRED_PREFIXES):
                    offenders.append((path.name, node.name))
    assert not offenders, f"definitions named for another authority: {offenders}"


def test_the_ratified_pair_is_defined_together_or_not_at_all():
    """``ProposerAdvisory`` without ``CandidateAdvisory`` is not the ratified shape."""
    present = {name for name in ADVISORY_TYPES if hasattr(ap, name)}
    assert present in (set(), set(ADVISORY_TYPES)), f"half-defined contract: {present}"


def test_no_rival_kind_string_is_declared():
    """One kind, at one version. A second ``ugence.agentic_proposer.*`` kind would
    make the ratified one ambiguous, whatever it was named."""
    prefix = "ugence.agentic_proposer."
    found = set()
    for path in _sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value.startswith(prefix):
                    found.add(node.value)
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


@pytest.mark.parametrize("name,model", _defined_advisory_types(), ids=lambda v: str(v)[:40])
def test_a_defined_advisory_type_declares_the_ratified_kind(name, model):
    tree_kinds = {getattr(model, "KIND", None), getattr(model, "kind", None)}
    fields = getattr(model, "model_fields", {}) or {}
    if "kind" in fields:
        tree_kinds.add(getattr(fields["kind"], "default", None))
    assert ADVISORY_KIND in {k.value if hasattr(k, "value") else k for k in tree_kinds}


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
    assert IDENTITY_FIELD == "advisory_digest"
    assert BARRED_FIELDS == frozenset({
        "fingerprint", "provider_id", "operation", "arguments",
        "idempotency_key", "workflow_id", "instance_id", "task_id"})
    assert BARRED_PREFIXES == ("Proposal", "Recommendation")
