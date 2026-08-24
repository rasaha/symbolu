"""D6's standing rule, enforced mechanically: no auditor status becomes an outcome.

Owner decision D6 reserves ``INDETERMINATE`` **by position**, and carries a standing
rule with a wider reach than that one term: no ``SemanticAuditorFindingStatus`` value
may be copied, mapped, coerced or defaulted into a ``TerminalOutcome`` or
``CandidateDisposition`` field. ``CONSISTENT`` becoming a terminal outcome would
breach it exactly as ``INDETERMINATE`` would.

The ADR records that obligation as ``[R]``: S1 must reject any such assignment or
conversion, and the test must land with the first outcome- or disposition-typed
field. This module is that test. It has two halves and neither waits on the other:

* a SOURCE half that rejects the shapes a projection takes — a conversion call, a
  lookup table, a union annotation, a status-valued assignment to an outcome field,
  a status-in/outcome-out function. It runs today, over today's sources.
* a RUNTIME half that is parametrized over every outcome- or disposition-typed field
  the package actually defines, and asserts each rejects every auditor status. It is
  empty only while no such field exists, and arms itself the moment one lands —
  which is what "lands with the first such field" requires of a test written before
  the field it guards.

The source half is self-tested against synthetic samples below, so a detector that
silently stopped matching would fail here rather than report a clean scan.
"""
from __future__ import annotations

import ast
import dataclasses
import enum
import importlib
import pathlib
import pkgutil
import typing

import pydantic
import pytest

import ugence_agentic_proposer as ap
from ugence_agentic_proposer.vocabulary import (
    CandidateDisposition,
    SemanticAuditorFindingStatus,
    TerminalOutcome,
)

SRC = pathlib.Path(ap.__file__).resolve().parent

#: The two positions D6 reserves. A status reaching either one is the violation.
RESERVED_POSITION_TYPES = ("TerminalOutcome", "CandidateDisposition")
STATUS_TYPE = "SemanticAuditorFindingStatus"


#: The three vocabularies this module tracks, by their canonical names.
TRACKED_TYPES = RESERVED_POSITION_TYPES + (STATUS_TYPE,)


def _aliases(tree):
    """Map every local binding back to the canonical type name it refers to.

    A projection written through an alias is the same projection. ``import ... as T``
    and ``from ... import TerminalOutcome as T`` both bind ``T`` to
    ``TerminalOutcome``; without this, the scan sees an untracked name and reports a
    clean module. Module bindings (``from . import vocabulary``) need no entry —
    ``vocabulary.TerminalOutcome`` is resolved by attribute name below.
    """
    return _direct_aliases(tree)


def _direct_aliases(tree):
    """Bindings made by importing a tracked name directly, without following hops."""
    bound = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in TRACKED_TYPES:
                    bound[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.Import):
            for alias in node.names:
                tail = alias.name.split(".")[-1]
                if tail in TRACKED_TYPES:
                    bound[alias.asname or tail] = tail
    return bound


def _module_key(path):
    """A source path as the dotted tail a relative import would name it by."""
    return path.stem


def _reexport_maps(paths):
    """Per-module alias maps, closed to a fixpoint across in-package re-exports.

    ``relay.py`` doing ``from .vocabulary import TerminalOutcome as Result`` makes
    ``from .relay import Result`` an alias for ``TerminalOutcome`` one hop further
    out. Resolution stopping at one hop is the same blindness as not resolving
    aliases at all, so the map is closed to a fixpoint.

    Kept PER MODULE rather than merged. A merged map makes one module's import
    rename a fact about every other: a parameter, a local variable or an unrelated
    import that happens to reuse the name would resolve to a tracked type in a
    module that never imported it, and lawful code would fail this guard.
    """
    per_module = {}
    trees = {}
    for path in paths:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError):
            continue
        trees[_module_key(path)] = tree
        per_module[_module_key(path)] = dict(_direct_aliases(tree))
    for _ in range(len(trees) + 1):
        changed = False
        for module, tree in trees.items():
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom) or not node.level:
                    continue
                source = (node.module or "").split(".")[-1]
                for alias in node.names:
                    canonical = per_module.get(source, {}).get(alias.name)
                    local = alias.asname or alias.name
                    if canonical and per_module[module].get(local) != canonical:
                        per_module[module][local] = canonical
                        changed = True
        if not changed:
            break
    return per_module


def _reexported_names(paths, module):
    """The alias map for one module, resolved through the package's re-exports."""
    return _reexport_maps(paths).get(module, {})


def _resolve(node, aliases):
    """The canonical type name ``node`` denotes, or "" if it denotes none of them.

    Resolves three spellings of the same reference: the bare name, an alias bound by
    an import, and an attribute access on a module (``vocabulary.TerminalOutcome``).
    """
    if isinstance(node, ast.Name):
        canonical = aliases.get(node.id, node.id)
        return canonical if canonical in TRACKED_TYPES else ""
    if isinstance(node, ast.Attribute):
        return node.attr if node.attr in TRACKED_TYPES else ""
    return ""


def _literal_string(node):
    """``node`` as a string if it is one at parse time, else "".

    Constant-folds, so a name assembled from pieces (``"Terminal" + "Outcome"``)
    resolves to the name it spells.
    """
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        # ``literal_eval`` folds arithmetic but not string concatenation, so a name
        # split across two literals would otherwise read as no name at all.
        left, right = _literal_string(node.left), _literal_string(node.right)
        return left + right if left and right else ""
    try:
        value = ast.literal_eval(node)
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        return ""
    return value if isinstance(value, str) else ""


def _getattr_names(node, aliases):
    """Tracked types reached through ``getattr``.

    ``getattr(vocabulary, "TerminalOutcome")`` denotes the type as surely as writing
    it does, and ``getattr(T, "ABSTAIN")`` selects a member of it.
    """
    found = set()
    for child in ast.walk(node):
        if not (isinstance(child, ast.Call) and _plain_name(child.func) == "getattr"):
            continue
        if child.args:
            owner = _resolve(child.args[0], aliases)
            if owner:
                found.add(owner)
        if len(child.args) > 1:
            named = _literal_string(child.args[1])
            if named in TRACKED_TYPES:
                found.add(named)
    return found


def _plain_name(node):
    """The bare name a node spells, without alias resolution."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _names(node, aliases=None):
    """Every canonical type name referenced anywhere inside ``node``.

    Aliased and module-qualified references resolve to the same canonical name as
    the bare one, so every shape below sees through both.
    """
    aliases = {} if aliases is None else aliases
    found = set()
    for child in ast.walk(node):
        canonical = _resolve(child, aliases)
        if canonical:
            found.add(canonical)
    return found | _getattr_names(node, aliases)


def _annotation_names(node, aliases=None):
    """Canonical names an ANNOTATION references, string forward references included.

    ``def project(s: "SemanticAuditorFindingStatus") -> "TerminalOutcome"`` is the
    same signature as the unquoted one; only a scan that never reads inside the
    quotes would call it clean. Applied to annotations only — a type name in a
    docstring is prose, not a reference.
    """
    aliases = {} if aliases is None else aliases
    found = _names(node, aliases)
    literal_strings = set()
    for child in ast.walk(node):
        # ``Literal["TerminalOutcome"]`` names a VALUE that happens to read like a
        # type. Resolving inside it would flag a function for describing which
        # vocabulary it is talking about.
        if isinstance(child, ast.Subscript) and _plain_name(child.value) == "Literal":
            literal_strings |= {id(n) for n in ast.walk(child.slice)
                                if isinstance(n, ast.Constant)}
    for child in ast.walk(node):
        if (isinstance(child, ast.Constant) and isinstance(child.value, str)
                and id(child) not in literal_strings):
            found |= {aliases.get(n, n) for n in _names_in_string_annotation(child.value)}
    return {n for n in found if n in TRACKED_TYPES}


def _refers_to_status(node, aliases=None):
    return STATUS_TYPE in _names(node, aliases)


def _refers_to_reserved_position(node, aliases=None):
    return bool(_names(node, aliases) & set(RESERVED_POSITION_TYPES))


def _called_name(call, aliases=None):
    return _resolve(call.func, {} if aliases is None else aliases)


def _reserved_member_accesses(scope, aliases):
    """Reads of a member OF a reserved vocabulary: ``TerminalOutcome.ABSTAIN``,
    ``T[name]``, ``vocabulary.CandidateDisposition.DEFER``.

    Constructing the value is only one way to reach it. Selecting a member reaches
    the same place and is how a projection is most naturally written — an if/elif
    ladder or a ``return TerminalOutcome.ABSTAIN`` guarded by a status check never
    calls the enum at all.
    """
    found = []
    for node in ast.walk(scope):
        if isinstance(node, ast.Attribute):
            owner = _resolve(node.value, aliases)
            if owner in RESERVED_POSITION_TYPES:
                found.append(f"{owner}.{node.attr}")
        elif isinstance(node, ast.Subscript):
            owner = _resolve(node.value, aliases)
            if owner in RESERVED_POSITION_TYPES:
                found.append(f"{owner}[...]")
        elif isinstance(node, ast.Call) and _plain_name(node.func) == "getattr":
            reached = _getattr_names(node, aliases) & set(RESERVED_POSITION_TYPES)
            found += [f"getattr(... {owner} ...)" for owner in sorted(reached)]
    return found


def _scopes(tree):
    """Yield each scope to judge as a unit: every function body, then the module.

    Shape 1 needs a scope rather than a single expression, because a conversion is
    routinely written so the status never appears inside the call's own parentheses
    — ``TerminalOutcome(s.value)`` guarded by an ``isinstance`` check two lines up is
    still a conversion. A scope that both reads an auditor status and constructs a
    reserved-position value is the violation; keeping the two in separate scopes is
    how lawful code that touches both vocabularies is written.
    """
    functions = [n for n in ast.walk(tree)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    for node in functions:
        yield node
    inner = {id(c) for f in functions for c in ast.walk(f)}
    for stmt in tree.body:
        if id(stmt) not in inner:
            yield stmt


def _projections(source, filename="<sample>", extra_aliases=None):
    """Return every place ``source`` moves an auditor status into a reserved position.

    Six shapes, because a projection can be written six ways and prose forbidding
    one of them forbids none of the others. Every shape resolves aliased and
    module-qualified references, so renaming an import does not evade the scan.
    """
    tree = ast.parse(source, filename=filename)
    aliases = dict(extra_aliases or {})
    aliases.update(_aliases(tree))
    found = []
    # 1. Conversion: a scope that reads an auditor status and builds a reserved value.
    # 6. Member access: the same scope selecting a reserved value instead of building it.
    for scope in _scopes(tree):
        if not _refers_to_status(scope, aliases):
            continue
        for node in ast.walk(scope):
            if isinstance(node, ast.Call) and _called_name(node, aliases) in RESERVED_POSITION_TYPES:
                found.append(("conversion-call", _called_name(node, aliases)))
        for access in _reserved_member_accesses(scope, aliases):
            found.append(("reserved-member-access", access))
    for node in ast.walk(tree):
        # 2. Lookup table mapping one vocabulary onto the other, in either direction.
        if isinstance(node, (ast.Dict, ast.DictComp)):
            # A comprehension building the same map is the same lookup table; only
            # its syntax differs from a literal.
            if isinstance(node, ast.DictComp):
                pairs = [(node.key, node.value)]
            else:
                pairs = [(k, v) for k, v in zip(node.keys, node.values)
                         if k is not None and v is not None]
            for key, value in pairs:
                whole = node if isinstance(node, ast.DictComp) else None
                pair = (_refers_to_status(key, aliases) or
                        (whole is not None and _refers_to_status(whole, aliases)),
                        _refers_to_reserved_position(value, aliases) or
                        (whole is not None and _refers_to_reserved_position(whole, aliases)))
                reverse = (_refers_to_reserved_position(key, aliases),
                           _refers_to_status(value, aliases))
                if all(pair) or all(reverse):
                    found.append(("lookup-table", ast.unparse(node)[:60]))
        # 3. Annotation admitting both vocabularies in one field.
        if isinstance(node, ast.AnnAssign) and node.annotation is not None:
            ann = node.annotation
            if (STATUS_TYPE in _annotation_names(ann, aliases)
                    and _annotation_names(ann, aliases) & set(RESERVED_POSITION_TYPES)):
                found.append(("union-annotation", ast.unparse(ann)))
            # 4. A reserved-position field defaulted or assigned from a status.
            if (_annotation_names(ann, aliases) & set(RESERVED_POSITION_TYPES)
                    and node.value is not None
                    and _refers_to_status(node.value, aliases)):
                found.append(("status-valued-field", ast.unparse(ann)))
        # 5. A status-in / outcome-out function is a conversion whatever its body.
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            annotations = [a.annotation for a in
                           list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs)
                           if a.annotation is not None]
            takes_status = any(STATUS_TYPE in _annotation_names(a, aliases) for a in annotations)
            returns_reserved = (node.returns is not None
                                and bool(_annotation_names(node.returns, aliases)
                                         & set(RESERVED_POSITION_TYPES)))
            if takes_status and returns_reserved:
                found.append(("status-to-outcome-function", node.name))
    return found


#: Samples the source half must flag. One per shape, so a detector that lost a shape
#: fails here instead of quietly reporting a clean package.
PROJECTION_SAMPLES = (
    "def f(s):\n    return TerminalOutcome(s.value) if isinstance(s, SemanticAuditorFindingStatus) else None\n",
    "TABLE = {SemanticAuditorFindingStatus.CONSISTENT: TerminalOutcome.PROPOSAL}\n",
    "class M:\n    outcome: TerminalOutcome | SemanticAuditorFindingStatus\n",
    "class M:\n    disposition: CandidateDisposition = SemanticAuditorFindingStatus.INDETERMINATE\n",
    "def project(status: SemanticAuditorFindingStatus) -> TerminalOutcome:\n    raise NotImplementedError\n",
    # Shape 6: selecting the value rather than constructing it. An if/elif ladder or
    # a guarded return never calls the enum, so shape 1 alone would let it through.
    ("def f(s):\n"
     "    if isinstance(s, SemanticAuditorFindingStatus):\n"
     "        return TerminalOutcome.ABSTAIN\n"
     "    return None\n"),
    ("def f(s: SemanticAuditorFindingStatus):\n"
     "    return TerminalOutcome[s.name]\n"),
    # The same six shapes written through an import alias.
    ("from .vocabulary import SemanticAuditorFindingStatus as S, TerminalOutcome as T\n"
     "def f(s):\n"
     "    return T(s.value) if isinstance(s, S) else None\n"),
    ("from .vocabulary import SemanticAuditorFindingStatus as S, CandidateDisposition as D\n"
     "TABLE = {S.CONSISTENT: D.DEFER}\n"),
    ("from .vocabulary import SemanticAuditorFindingStatus as S, TerminalOutcome as T\n"
     "def project(status: S) -> T:\n    raise NotImplementedError\n"),
    ("from .vocabulary import SemanticAuditorFindingStatus as S, TerminalOutcome as T\n"
     "def f(s):\n"
     "    if isinstance(s, S):\n        return T.ABSTAIN\n    return None\n"),
    # And through a module-qualified reference.
    ("from . import vocabulary\n"
     "def f(s):\n"
     "    if isinstance(s, vocabulary.SemanticAuditorFindingStatus):\n"
     "        return vocabulary.TerminalOutcome(s.value)\n"),
    ("from . import vocabulary\n"
     "def f(s):\n"
     "    if isinstance(s, vocabulary.SemanticAuditorFindingStatus):\n"
     "        return vocabulary.TerminalOutcome.ABSTAIN\n"),
    ("from . import vocabulary\n"
     "def project(status: vocabulary.SemanticAuditorFindingStatus)"
     " -> vocabulary.TerminalOutcome:\n    raise NotImplementedError\n"),
    # A dict COMPREHENSION building the same lookup table as the literal above.
    ("from .vocabulary import SemanticAuditorFindingStatus as S, TerminalOutcome as T\n"
     "TABLE = {m: list(T)[i] for i, m in enumerate(S)}\n"),
    # String forward references, quoted so an unquoted-only scan reads nothing.
    ('def project(status: "SemanticAuditorFindingStatus") -> "TerminalOutcome":\n'
     "    raise NotImplementedError\n"),
    ("from typing import TYPE_CHECKING\n"
     "if TYPE_CHECKING:\n"
     "    from .vocabulary import SemanticAuditorFindingStatus, TerminalOutcome\n"
     'def project(status: "SemanticAuditorFindingStatus") -> "TerminalOutcome":\n'
     "    raise NotImplementedError\n"),
    # getattr, including a name assembled from pieces.
    ("from . import vocabulary\n"
     "def f(s):\n"
     "    if isinstance(s, vocabulary.SemanticAuditorFindingStatus):\n"
     '        return getattr(vocabulary, "TerminalOutcome").ABSTAIN\n'),
    ("from . import vocabulary\n"
     "def f(s):\n"
     "    if isinstance(s, vocabulary.SemanticAuditorFindingStatus):\n"
     '        return getattr(vocabulary, "Terminal" + "Outcome").ABSTAIN\n'),
    # A pydantic validator coercing a status into a reserved-position field.
    ("from .vocabulary import SemanticAuditorFindingStatus as S, TerminalOutcome as T\n"
     "class M:\n"
     "    @field_validator('outcome', mode='before')\n"
     "    def _coerce(cls, v):\n"
     "        if v is S.INDETERMINATE:\n            return T.ABSTAIN\n"
     "        return v\n"),
)

#: Samples that must NOT be flagged: the two vocabularies may coexist in a module,
#: be imported together, and be carried in separate fields. Only crossing is barred.
CLEAN_SAMPLES = (
    "from .vocabulary import SemanticAuditorFindingStatus, TerminalOutcome\n",
    "class M:\n    outcome: TerminalOutcome\n    finding: SemanticAuditorFindingStatus\n",
    "def read(status: SemanticAuditorFindingStatus) -> str:\n    return status.value\n",
    "OUTCOMES = {TerminalOutcome.ABSTAIN: 'no recommendation'}\n",
    ("def read(status: SemanticAuditorFindingStatus) -> str:\n    return status.value\n"
     "\n\ndef decide() -> TerminalOutcome:\n    return TerminalOutcome.ABSTAIN\n"),
    # The same separation, written through an alias and a module reference: resolving
    # aliases must not make lawful code fail, only make evasion impossible.
    ("from .vocabulary import SemanticAuditorFindingStatus as S, TerminalOutcome as T\n"
     "def read(status: S) -> str:\n    return status.value\n"
     "\n\ndef decide() -> T:\n    return T.ABSTAIN\n"),
    ("from . import vocabulary\n"
     "def decide() -> vocabulary.TerminalOutcome:\n"
     "    return vocabulary.TerminalOutcome.ABSTAIN\n"),
    ("from .vocabulary import SemanticAuditorFindingStatus as S, TerminalOutcome as T\n"
     "class M:\n    outcome: T\n    finding: S\n"),
)


@pytest.mark.parametrize("sample", PROJECTION_SAMPLES, ids=lambda s: s.split("\n")[0][:40])
def test_the_detector_flags_every_projection_shape(sample):
    assert _projections(sample), "a projection shape stopped being detected"


@pytest.mark.parametrize("sample", CLEAN_SAMPLES, ids=lambda s: s.split("\n")[0][:40])
def test_the_detector_does_not_flag_lawful_coexistence(sample):
    assert not _projections(sample)


#: Spellings that reach a tracked type through an in-package re-export rather than a
#: direct import. Resolved against a synthetic package map, since a single sample
#: string has no package around it.
RELAY_ALIASES = {"Finding": STATUS_TYPE, "Result": "TerminalOutcome"}

RELAYED_PROJECTION_SAMPLES = (
    "from .relay import Finding, Result\ndef f(s):\n    if isinstance(s, Finding):\n        return Result.ABSTAIN\n",
    "from .relay import Finding, Result\ndef f(s):\n    return Result(s.value) if isinstance(s, Finding) else None\n",
    "from .relay import Finding, Result\nTABLE = {Finding.CONSISTENT: Result.PROPOSAL}\n",
    "from .relay import Finding, Result\ndef project(status: Finding) -> Result:\n    raise NotImplementedError\n",
)


@pytest.mark.parametrize("sample", RELAYED_PROJECTION_SAMPLES, ids=lambda s: s.split("\n")[1][:40])
def test_the_detector_follows_an_in_package_re_export(sample):
    """A re-export is an alias one hop further out.

    Resolution that stops at the first hop is the same blindness as not resolving
    aliases at all: the module doing the projection imports a name this scan has
    never seen bound to a tracked type.
    """
    assert not _projections(sample), "sample must be invisible without the package map"
    assert _projections(sample, extra_aliases=RELAY_ALIASES)


#: Lawful modules that reuse a name another module aliases to a tracked type. Each
#: also names an auditor status, so a merged alias map would flag every one of them.
NAME_REUSE_SAMPLES = (
    # An unrelated import of the same name from a different module.
    ("from .other import Result\n"
     "from .vocabulary import SemanticAuditorFindingStatus\n"
     "def f(s: SemanticAuditorFindingStatus):\n    return Result.ABSTAIN\n"),
    # A parameter of that name.
    ("from .vocabulary import SemanticAuditorFindingStatus\n"
     "def f(s: SemanticAuditorFindingStatus, Result=None):\n    return Result.ABSTAIN\n"),
    # A local variable of that name.
    ("from .vocabulary import SemanticAuditorFindingStatus\n"
     "def f(s: SemanticAuditorFindingStatus):\n"
     "    Result = {'a': 1}\n    return Result.get('a')\n"),
)


@pytest.mark.parametrize("sample", NAME_REUSE_SAMPLES, ids=lambda s: s.split("\n")[0][:40])
def test_another_modules_alias_is_not_a_fact_about_this_one(sample):
    """``Result`` meaning ``TerminalOutcome`` in one module means nothing here.

    A merged package-wide alias map would reject all three of these — ordinary code
    that never imported a reserved type. The first S1 contract to name a variable
    after another module's alias would fail this guard for no reason, and the
    natural response would be to weaken the guard.
    """
    assert not _projections(sample, extra_aliases={})


def test_a_literal_naming_a_type_is_not_a_reference_to_it():
    """``Literal["TerminalOutcome"]`` is a value; the quotes are not a forward
    reference. Resolving inside them flags a function for naming a vocabulary."""
    lawful = ('from typing import Literal\n'
              'from .vocabulary import SemanticAuditorFindingStatus\n'
              'def which(status: SemanticAuditorFindingStatus)'
              ' -> Literal["TerminalOutcome", "CandidateDisposition"]:\n'
              '    return "TerminalOutcome"\n')
    assert not _projections(lawful)

    # The same quotes outside a Literal ARE a forward reference, and still bind.
    projecting = ('def project(status: "SemanticAuditorFindingStatus")'
                  ' -> "TerminalOutcome":\n    raise NotImplementedError\n')
    assert _projections(projecting)


def test_the_re_export_map_closes_over_a_chain():
    """Built from real files, to a fixpoint, so a two-hop relay resolves too."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        (root / "vocabulary.py").write_text(
            "class TerminalOutcome:\n    pass\n", encoding="utf-8")
        (root / "relay.py").write_text(
            "from .vocabulary import TerminalOutcome as Result\n", encoding="utf-8")
        (root / "relay2.py").write_text(
            "from .relay import Result as Verdict\n", encoding="utf-8")
        maps = _reexport_maps(sorted(root.rglob("*.py")))

    assert maps["relay"].get("Result") == "TerminalOutcome"
    assert maps["relay2"].get("Verdict") == "TerminalOutcome", "the chain stopped at one hop"
    # Per module, not merged: relay2 renamed it again, and relay never saw that name.
    assert "Verdict" not in maps["relay"]
    assert "Result" not in maps["vocabulary"]


def test_sources_exist_to_scan():
    assert sorted(SRC.rglob("*.py"))


@pytest.mark.parametrize("path", sorted(SRC.rglob("*.py")), ids=lambda p: p.name)
def test_no_source_projects_an_auditor_status_into_a_reserved_position(path):
    found = _projections(path.read_text(encoding="utf-8"), filename=str(path),
                         extra_aliases=_reexport_maps(
                             sorted(SRC.rglob("*.py"))).get(_module_key(path), {}))
    assert not found, f"{path.name} projects an auditor status: {found}"


def _modules():
    yield ap
    for info in pkgutil.walk_packages(ap.__path__, ap.__name__ + "."):
        yield importlib.import_module(info.name)


def _names_in_string_annotation(text):
    """Canonical type names named inside a string annotation.

    ``"TerminalOutcome"``, ``"TerminalOutcome | SemanticAuditorFindingStatus"`` and
    ``"Optional[TerminalOutcome]"`` all name a reserved position; only the first is
    an exact match for the type's name.
    """
    for _ in range(3):
        try:
            expression = ast.parse(text, mode="eval")
        except SyntaxError:
            return {text} & set(TRACKED_TYPES)
        # Under ``from __future__ import annotations`` an annotation that was
        # already a string is stored still quoted, so one parse yields the inner
        # string rather than the type it names. Unwrap before resolving.
        if (isinstance(expression.body, ast.Constant)
                and isinstance(expression.body.value, str)):
            text = expression.body.value
            continue
        return _names(expression)
    return set()


def _is_reserved_position(annotation):
    """Whether ``annotation`` puts a value in a position D6 reserves.

    A union arm counts. ``TerminalOutcome | SemanticAuditorFindingStatus`` is the
    projection itself, so a field carrying it must be collected and judged, not
    passed over for not being the bare enum.
    """
    if isinstance(annotation, str):
        # A dataclass under ``from __future__ import annotations`` keeps its
        # annotation as a string, and a string union never resolves to a type at
        # all, so equality against the bare names would skip exactly the fields
        # most likely to carry the projection.
        return bool(_names_in_string_annotation(annotation) & set(RESERVED_POSITION_TYPES))
    candidates = {annotation} | set(typing.get_args(annotation))
    return bool(candidates & {TerminalOutcome, CandidateDisposition})


def _reserved_position_fields(namespaces=None):
    """Every declared field typed as a terminal outcome or a candidate disposition.

    Covers pydantic models and dataclasses alike, since either could carry the first
    such field. Empty until S1 defines a contract that has one — which is why
    ``namespaces`` is a parameter: the package supplies none today, so the collection
    can only be exercised against a synthetic one, and a collection that is never
    exercised is a collection that can quietly stop collecting.
    """
    fields = []
    seen = set()
    for module in (_modules() if namespaces is None else namespaces):
        for attr in vars(module).values():
            if not isinstance(attr, type) or attr in seen:
                continue
            seen.add(attr)
            annotations = dict(getattr(attr, "__annotations__", {}) or {})
            if dataclasses.is_dataclass(attr):
                annotations = {f.name: f.type for f in dataclasses.fields(attr)}
            model_fields = getattr(attr, "model_fields", None)
            if isinstance(model_fields, dict):
                annotations = {name: f.annotation for name, f in model_fields.items()}
            for name, annotation in annotations.items():
                if _is_reserved_position(annotation):
                    fields.append((attr, name, annotation))
    return fields


# --------------------------------------------------------------------------- #
# Self-tests for the RUNTIME half
#
# The package defines no reserved-position field in S0, so the parametrization below
# is empty and nothing else exercises this half. Without these, both the union-arm
# rule and the collection itself could be deleted and the suite would stay green —
# which is exactly what an audit of the previous revision found.
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("annotation", [
    TerminalOutcome,
    CandidateDisposition,
    typing.Optional[TerminalOutcome],
    typing.Union[TerminalOutcome, SemanticAuditorFindingStatus],
    "TerminalOutcome",
    "CandidateDisposition",
    "TerminalOutcome | SemanticAuditorFindingStatus",
    "Optional[TerminalOutcome]",
])
def test_a_reserved_position_is_recognised_however_it_is_spelled(annotation):
    """Union arms and string annotations are reserved positions too.

    ``TerminalOutcome | SemanticAuditorFindingStatus`` IS the projection; skipping it
    for not being the bare enum would leave the one field D6 most needs judged
    uncollected.
    """
    assert _is_reserved_position(annotation)


@pytest.mark.parametrize("annotation", [
    str,
    SemanticAuditorFindingStatus,
    typing.Optional[str],
    "str",
    "SemanticAuditorFindingStatus",
])
def test_an_unreserved_position_is_not_collected(annotation):
    """A status-typed field is lawful — the auditor's own vocabulary in its own
    position. Collecting it would make the runtime half fail on correct code."""
    assert not _is_reserved_position(annotation)


def test_the_field_collection_finds_a_reserved_field_on_every_model_kind():
    """The collection itself, run over a synthetic namespace.

    Pydantic model, dataclass and plain annotated class, each carrying a reserved
    position spelled differently. A collection returning nothing passes every other
    test in this module by leaving the parametrization empty.
    """
    import types

    class Plain:
        outcome: TerminalOutcome

    @dataclasses.dataclass
    class AsDataclass:
        disposition: CandidateDisposition = None

    @dataclasses.dataclass
    class AsStringUnion:
        outcome: "TerminalOutcome | SemanticAuditorFindingStatus" = None

    class AsModel(pydantic.BaseModel):
        outcome: typing.Union[TerminalOutcome, SemanticAuditorFindingStatus]

    class Unrelated:
        note: str
        finding: SemanticAuditorFindingStatus

    namespace = types.SimpleNamespace(
        Plain=Plain, AsDataclass=AsDataclass, AsStringUnion=AsStringUnion,
        AsModel=AsModel, Unrelated=Unrelated)
    collected = _reserved_position_fields([namespace])

    assert {(owner.__name__, name) for owner, name, _ in collected} == {
        ("Plain", "outcome"),
        ("AsDataclass", "disposition"),
        ("AsStringUnion", "outcome"),
        ("AsModel", "outcome"),
    }, collected


def test_the_collected_union_field_is_then_refused():
    """The two halves together: a union field is collected, and judged, and fails.

    Asserted here rather than left to the parametrization, which is empty until S1
    defines a contract.
    """
    import types

    class Widened(pydantic.BaseModel):
        outcome: typing.Union[TerminalOutcome, SemanticAuditorFindingStatus]

    collected = _reserved_position_fields([types.SimpleNamespace(Widened=Widened)])
    assert collected, "a widened reserved position was not collected"
    for owner, name, annotation in collected:
        with pytest.raises((AssertionError, pydantic.ValidationError)):
            test_a_reserved_position_field_rejects_every_auditor_status(
                owner, name, annotation)


def _declared_annotation(owner, name):
    """The annotation ``owner`` declares for ``name``, whatever kind of type it is."""
    model_fields = getattr(owner, "model_fields", None)
    if isinstance(model_fields, dict) and name in model_fields:
        return model_fields[name].annotation
    if dataclasses.is_dataclass(owner):
        for field in dataclasses.fields(owner):
            if field.name == name:
                return field.type
    return dict(getattr(owner, "__annotations__", {}) or {}).get(name)


def _resolve_annotation(annotation):
    """A string annotation (``from __future__ import annotations``) as its type."""
    if isinstance(annotation, str):
        return {
            "TerminalOutcome": TerminalOutcome,
            "CandidateDisposition": CandidateDisposition,
            STATUS_TYPE: SemanticAuditorFindingStatus,
        }.get(annotation, annotation)
    return annotation


@pytest.mark.parametrize(
    "owner,name,annotation",
    _reserved_position_fields(),
    ids=lambda v: getattr(v, "__name__", str(v)),
)
def test_a_reserved_position_field_rejects_every_auditor_status(owner, name, annotation):
    """Every auditor status must be refused by ``owner.name`` itself.

    Parametrized over what the package defines, so this arms itself with the first
    such field rather than needing to be remembered then.

    The assertion is against the field's own declared annotation, read back off the
    owner — not against the bare enum. Testing the enum would pass for a field
    annotated ``TerminalOutcome | SemanticAuditorFindingStatus``, which is the
    projection D6 forbids; the union is admitted by the field and refused by the
    enum, so only the field can answer the question.
    """
    declared = _declared_annotation(owner, name)
    assert declared is not None, f"{owner.__name__}.{name} has no readable annotation"
    resolved = _resolve_annotation(declared)

    # The status vocabulary must not be admissible in the field at all, directly or
    # as one arm of a union.
    admitted = {resolved} | set(typing.get_args(resolved))
    assert SemanticAuditorFindingStatus not in admitted, (
        f"{owner.__name__}.{name} admits {STATUS_TYPE}: {declared!r}")

    adapter = pydantic.TypeAdapter(resolved)
    for status in SemanticAuditorFindingStatus:
        # Neither the member nor its wire value may validate into this field.
        for candidate in (status, status.value):
            with pytest.raises((pydantic.ValidationError, ValueError, TypeError)):
                adapter.validate_python(candidate)


def test_no_auditor_status_value_is_admissible_in_a_reserved_position():
    """The enums themselves make the projection impossible, term by term.

    This is what keeps the rule wider than INDETERMINATE: it holds for CONSISTENT,
    INCONSISTENT and CONFLICTING too, and would fail if any of them were added to
    either reserved vocabulary later.
    """
    reserved_values = ({m.value for m in TerminalOutcome}
                       | {m.value for m in CandidateDisposition})
    for status in SemanticAuditorFindingStatus:
        assert status.value not in reserved_values
        for target in (TerminalOutcome, CandidateDisposition):
            with pytest.raises(ValueError):
                target(status.value)
            with pytest.raises(KeyError):
                target[status.name]


def test_the_three_vocabularies_are_distinct_types():
    """Projection by subclassing, aliasing or re-basing is closed off too."""
    for target in (TerminalOutcome, CandidateDisposition):
        assert not issubclass(SemanticAuditorFindingStatus, target)
        assert not issubclass(target, SemanticAuditorFindingStatus)
        assert set(SemanticAuditorFindingStatus) & set(target) == set()
    assert issubclass(SemanticAuditorFindingStatus, enum.Enum)
