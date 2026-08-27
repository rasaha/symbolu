"""The package defines no local JSON-canonicalization function.

Owner decision D2: the only permitted implementation of proposal identity is a call
into ``ugence_jcs``. A second canonicalizer — even a "temporary" helper, a fallback
behind a flag, or a test fixture — would create a competing exact-identity substrate,
which is precisely what D2 forbids. So this scans ``src`` and ``tests`` alike — a
canonicalizer parked in a test fixture is still a second canonicalizer.

The scan is a glob over both trees, so a module added later is covered by default;
``test_scan_covers_the_s1_enforcement_modules_by_name`` additionally pins the three
S1 enforcement guards by name, and
``test_every_module_in_the_package_is_scanned_or_named_as_exempt`` closes the
general case, so a file can only be scanned or explicitly exempt.

Two files are outside that scan, and neither is a hole:

* this guard module, which necessarily names every pattern it hunts for;
* ``verify_agentic_proposer_distribution.py``, packaging tooling that hashes built
  wheel and sdist FILES to report artifact identity and build reproducibility. It
  runs at build time, ships in no wheel, and canonicalizes no proposal. The test
  below pins that exemption to that one filename so it cannot widen.

**I1 — the module-path-scoped digest-grammar mask.** A7 records that the ratified
``sha256:`` identity prefix and the C6 digest grammar
``^sha256:[0-9a-f]{64}$`` collide with this scan's bare ``"sha256"`` hunt: D7 requires
identity to carry that prefix and every digest-shaped field to be validated against
that pattern, and both spellings contain the literal ``"sha256"`` this scan is built
to catch. The mask below resolves the collision **narrowly**: exactly the two strings
``"sha256:"`` and ``"^sha256:[0-9a-f]{64}$"``, and only inside
``identity.py`` — the single module authorised to compute proposal identity (D2, D7).
Every other file, including every other string, stays fully scanned. No definition
name is exempted: the identity function names (``compute_advisory_identity``,
``verify_advisory_identity``, and the three verifiers in ``verification.py``) are
chosen to contain no ``SUSPECT_DEF_SUBSTRINGS`` member in the first place, so
``SUSPECT_DEF_SUBSTRINGS`` itself is untouched.
"""
from __future__ import annotations

import ast
import importlib
import pathlib

import pytest

PKG_ROOT = pathlib.Path(__file__).resolve().parents[1]
SELF = pathlib.Path(__file__).resolve()
#: Build-time packaging tooling that hashes artifact files, not proposals.
VERIFIER = PKG_ROOT / "verify_agentic_proposer_distribution.py"
#: The directories that carry the capability. Everything in them is scanned.
SCANNED_TREES = (PKG_ROOT / "src", PKG_ROOT / "tests")

#: Names that would signal a canonicalizer or an identity digest defined here.
SUSPECT_DEF_SUBSTRINGS = (
    "canonical", "canonicalize", "canon", "jcs", "rfc8785", "normalize_json",
    "serialize_stable", "stable_json", "fingerprint", "digest", "proposal_id",
)

#: Source text that would signal canonicalization or hashing, wherever it appears.
SUSPECT_TEXT = (
    "sort_keys", "rfc8785", "RFC 8785", "separators=(", "utf-16-be",
    "hashlib", "sha256", "sha3_", "blake2",
)

#: Calls INTO the permitted substrate, which the text scan must not mistake for local
#: hashing. D7 requires identity to be produced by ``ugence_jcs.canonical_sha256_hex``;
#: that spelling contains ``sha256``, so without this the rule D7 mandates and the rule
#: D2 enforces would be jointly unsatisfiable. Masked before the scan, longest first,
#: so only these exact spellings are exempt — a bare ``hashlib.sha256`` in the same
#: position still carries ``hashlib`` and an unmasked ``sha256``, and a locally defined
#: ``canonical_*`` is caught by the definition scan regardless.
PERMITTED_SUBSTRATE_CALLS = (
    "ugence_jcs.canonical_sha256_hex",
    "ugence_jcs.canonical_bytes",
    "ugence_jcs.canonical_string",
    "canonical_sha256_hex",
    "canonical_bytes",
    "canonical_string",
)


#: I1. The single module authorised to spell the digest grammar as bare text, and the
#: exact two strings the mask hides there and nowhere else. Pinned by name so the
#: exemption cannot silently widen to a second file or a third string.
AUTHORISED_IDENTITY_MODULE = "identity.py"
IDENTITY_MODULE_MASKED_TEXT = (
    "sha256:",
    "^sha256:[0-9a-f]{64}$",
)


def _suspect_text(body, filename=None):
    """Suspect substrings in ``body``, with permitted substrate calls masked out, and
    (I1) the two ratified digest-grammar strings masked when — and only when —
    ``filename`` is the single authorised identity module."""
    masked = body
    for call in sorted(PERMITTED_SUBSTRATE_CALLS, key=len, reverse=True):
        masked = masked.replace(call, "<permitted-substrate-call>")
    if filename == AUTHORISED_IDENTITY_MODULE:
        for literal in sorted(IDENTITY_MODULE_MASKED_TEXT, key=len, reverse=True):
            masked = masked.replace(literal, "<identity-module-digest-grammar>")
    return [s for s in SUSPECT_TEXT if s in masked]

#: Modules whose presence would mean identity is being computed locally.
#: ``importlib`` is here because it reaches every other name on the list without
#: naming it: ``importlib.import_module("hash" + "lib")`` imports nothing this scan
#: would otherwise see.
FORBIDDEN_IMPORTS = {"hashlib", "hmac", "binascii", "struct"}

#: Barred in ``src`` only. The guards in ``tests`` import ``importlib`` to walk this
#: package's own modules, which is how they arm themselves over a surface that does
#: not exist yet; the shipped capability has no such need, and that is where a
#: name-assembling import would do its work.
SRC_ONLY_FORBIDDEN_IMPORTS = {"importlib"}

#: The identity substrate is a distribution reached by an ABSOLUTE import. A module
#: of this name inside the package would satisfy every by-name check while hashing
#: locally, so the name itself is reserved here.
SUBSTRATE_MODULE = "ugence_jcs"


def _substrate_shadows(trees):
    """Files or directories under ``trees`` named for the identity substrate."""
    offenders = []
    for tree in trees:
        if not tree.exists():
            continue
        for path in tree.rglob("*"):
            if any(part in {"build", "dist", ".venv", "__pycache__"} for part in path.parts):
                continue
            if path.is_dir() and path.name == SUBSTRATE_MODULE:
                offenders.append(str(path))
            elif path.suffix == ".py" and path.stem == SUBSTRATE_MODULE:
                offenders.append(str(path))
    return sorted(offenders)


#: Dynamic-import entry points. A module imported through one of these is imported.
DYNAMIC_IMPORT_CALLS = ("import_module", "__import__")


def _dynamic_import_offenders(source, barred, filename="<sample>"):
    """Dynamic imports that reach a barred module, or hide which module they reach.

    Two shapes, because barring ``importlib`` alone stops one spelling of one route:

    * a literal naming a barred module — ``import_module("hashlib")``;
    * a module name ASSEMBLED at the call site — ``__import__("hash" + "lib")``.
      The assembled form is barred whatever it spells, since no text scan can read
      it. A plain name (``import_module(info.name)``) is permitted: that is how the
      guards in this directory walk this package's own modules.
    """
    tree = ast.parse(source, filename=filename)
    by_scope = _assembled_names_by_scope(tree)
    owner = _enclosing_scopes(tree)
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        called = (func.id if isinstance(func, ast.Name)
                  else func.attr if isinstance(func, ast.Attribute) else "")
        if called not in DYNAMIC_IMPORT_CALLS or not node.args:
            continue
        argument = node.args[0]
        if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
            if argument.value.split(".")[0] in barred:
                offenders.append(f"{called}({argument.value!r})")
        elif _is_assembled_string(argument):
            offenders.append(f"{called}(<assembled name>)")
        elif (isinstance(argument, ast.Name)
              and argument.id in by_scope.get(owner.get(id(node), id(tree)), set())):
            # Assembly one line earlier is still assembly. Without this the rule
            # reads as coverage it does not have: ``_n = "hash" + "lib"`` followed
            # by ``__import__(_n)`` passes a bare name the scan would permit.
            offenders.append(f"{called}({argument.id} = <assembled name>)")
    return offenders


#: Calls that build a string out of parts rather than writing it.
ASSEMBLY_METHODS = {"join", "format", "decode", "replace", "translate"}
ASSEMBLY_BUILTINS = {"bytes", "bytearray", "chr"}


def _is_assembled_string(node):
    """Whether ``node`` composes a string rather than spelling one."""
    if isinstance(node, (ast.BinOp, ast.JoinedStr)):
        return True
    if isinstance(node, ast.Call):
        if getattr(node.func, "attr", "") in ASSEMBLY_METHODS:
            return True
        if getattr(node.func, "id", "") in ASSEMBLY_BUILTINS:
            return True
    return False


#: Nodes that open a scope of their own. A binding inside one is not a binding
#: outside it — including comprehensions, whose loop variable is exactly the shape
#: the guards use to walk this package.
SCOPE_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda,
               ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


def _own_scope_nodes(scope):
    """Nodes belonging to ``scope`` itself, not to any scope nested inside it."""
    for child in ast.iter_child_nodes(scope):
        if isinstance(child, SCOPE_NODES):
            continue
        yield child
        yield from _own_scope_nodes(child)


def _scope_bindings(scope):
    """``(assembled, plain)`` — names this scope binds, by how it binds them.

    ``plain`` is every other way a name is bound here: a parameter, a loop or
    comprehension variable, an import, an assignment from something that is not
    string assembly. Those SHADOW an outer binding of the same name rather than
    inheriting its meaning.
    """
    assembled, plain = set(), set()

    def bind(target, is_assembled):
        for node in ast.walk(target):
            if isinstance(node, ast.Name):
                (assembled if is_assembled else plain).add(node.id)
                (plain if is_assembled else assembled).discard(node.id)

    args = getattr(scope, "args", None)
    if args is not None:
        for argument in (list(args.posonlyargs) + list(args.args)
                         + list(args.kwonlyargs)
                         + [a for a in (args.vararg, args.kwarg) if a]):
            plain.add(argument.arg)
    for generator in getattr(scope, "generators", []):
        bind(generator.target, False)

    for node in _own_scope_nodes(scope):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                bind(target, _is_assembled_string(node.value))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.value is not None:
                bind(node.target, _is_assembled_string(node.value))
        elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
            # ``_n += "lib"`` composes; ``n += 1`` does not. The value decides,
            # not the fact that an augmented assignment happened.
            value = node.value
            appends_text = (_is_assembled_string(value)
                            or (isinstance(value, ast.Constant)
                                and isinstance(value.value, str)))
            if isinstance(node.op, ast.Add) and appends_text:
                assembled.add(node.target.id)
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            bind(node.target, False)
        elif isinstance(node, ast.withitem) and node.optional_vars is not None:
            bind(node.optional_vars, False)
        elif isinstance(node, ast.NamedExpr):
            bind(node.target, _is_assembled_string(node.value))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            plain |= {a.asname or a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ExceptHandler) and node.name:
            plain.add(node.name)
    return assembled, plain


def _assembled_names_by_scope(tree):
    """``{id(scope): names assembled and visible there}``, scope by scope.

    Built per scope rather than per module. A set merged across the module makes one
    scope's binding a fact about another: a module-level ``name = "age" + "ntic"``
    would mark the parameter of ``def load(name)`` as composed, and the guards' own
    ``import_module(name) for name in infos`` with it. That is the merged-alias-map
    defect one level down, and it rejects ordinary code.
    """
    by_scope = {}

    def visit(scope, inherited):
        assembled, plain = _scope_bindings(scope)
        visible = (inherited - plain) | assembled
        by_scope[id(scope)] = visible
        for node in ast.walk(scope):
            if node is not scope and isinstance(node, SCOPE_NODES):
                if id(node) not in by_scope:
                    visit(node, visible)

    visit(tree, set())
    return by_scope


def _enclosing_scopes(tree):
    """``{id(node): id(nearest enclosing scope)}`` for every node in ``tree``."""
    owner = {}

    def visit(scope):
        for node in _own_scope_nodes(scope):
            owner[id(node)] = id(scope)
        for node in ast.walk(scope):
            if node is not scope and isinstance(node, SCOPE_NODES):
                if id(node) not in owner:
                    owner[id(node)] = id(scope)
                    visit(node)

    visit(tree)
    return owner


def _assembled_string_names(tree):
    """Names assembled and visible at module scope."""
    return _assembled_names_by_scope(tree)[id(tree)]


def _barred_for(path):
    """The modules ``path`` may not import, by where it lives."""
    barred = set(FORBIDDEN_IMPORTS)
    if (PKG_ROOT / "src") in path.parents:
        barred |= SRC_ONLY_FORBIDDEN_IMPORTS
    return barred


def _import_offenders_for(path):
    """Every barred module ``path`` reaches, by statement or by dynamic import.

    One function so the per-file check and its self-test exercise the same wiring:
    a scanner that is self-tested but never applied is a scanner that does nothing.
    """
    body = path.read_text(encoding="utf-8")
    barred = _barred_for(path)
    offenders = _forbidden_imports(body, barred, filename=str(path))
    # A dynamic import reaches the same modules without an import statement, and an
    # assembled name reaches them without spelling them. Barred in tests too: a
    # canonicalizer parked in a fixture is still a second canonicalizer.
    return offenders + _dynamic_import_offenders(body, FORBIDDEN_IMPORTS,
                                                 filename=str(path))


def _forbidden_imports(source, barred, filename="<sample>"):
    """Every module in ``barred`` that ``source`` imports, directly or by name."""
    tree = ast.parse(source, filename=filename)
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            offenders += [a.name for a in node.names if a.name.split(".")[0] in barred]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            if node.module.split(".")[0] in barred:
                offenders.append(node.module)
    return offenders


def _package_files():
    for tree in SCANNED_TREES:
        for path in sorted(tree.rglob("*.py")):
            if path.resolve() in (SELF, VERIFIER.resolve()):
                continue
            if any(part in {"build", "dist", ".venv", "__pycache__"} for part in path.parts):
                continue
            yield path


def test_package_has_files_to_scan():
    assert list(_package_files())


#: Text the scan must flag: identity computed here, however it is spelled.
LOCAL_HASHING_SAMPLES = (
    "import hashlib\nadvisory_digest = hashlib.sha256(payload).hexdigest()\n",
    "from hashlib import sha256\nadvisory_digest = sha256(payload).hexdigest()\n",
    "blob = json.dumps(value, sort_keys=True, separators=(',', ':'))\n",
    "digest = blake2b(payload).hexdigest()\n",
)

#: Text the scan must permit: identity produced by the one permitted substrate.
#: D7 mandates exactly this call, so a scan that flagged it would leave D7 and D2
#: jointly unsatisfiable — no source could both compute identity and pass.
PERMITTED_SUBSTRATE_SAMPLES = (
    "import ugence_jcs\nadvisory_digest = ugence_jcs.canonical_sha256_hex(payload)\n",
    "from ugence_jcs import canonical_sha256_hex\nadvisory_digest = canonical_sha256_hex(payload)\n",
    "import ugence_jcs\nblob = ugence_jcs.canonical_bytes(payload)\n",
)


@pytest.mark.parametrize("sample", LOCAL_HASHING_SAMPLES, ids=lambda s: s.split("\n")[0][:40])
def test_the_text_scan_flags_local_hashing(sample):
    assert _suspect_text(sample), "the text scan stopped seeing local hashing"


@pytest.mark.parametrize("sample", PERMITTED_SUBSTRATE_SAMPLES, ids=lambda s: s.split("\n")[0][:40])
def test_the_text_scan_permits_the_declared_substrate(sample):
    assert not _suspect_text(sample), "the permitted substrate call was flagged"


def test_no_module_here_shadows_the_identity_substrate():
    """No file or package under this distribution may be named for the substrate.

    The text mask and D7's substrate rule both key on the name ``ugence_jcs``. A
    local module of that name, reached by ``from . import ugence_jcs``, would pass
    both while computing identity here — the exact thing D2 exists to prevent.
    """
    offenders = _substrate_shadows(SCANNED_TREES)
    assert not offenders, f"a local module shadows the substrate: {offenders}"


def test_the_per_file_check_applies_both_scans():
    """The wiring, not just the scanners.

    Both routes must reach a real file through the same function the parametrized
    check uses; otherwise either scan could be self-tested and never called.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "probe.py"

        path.write_text("import pathlib\n", encoding="utf-8")
        assert _import_offenders_for(path) == []

        path.write_text("import hashlib\n", encoding="utf-8")
        assert _import_offenders_for(path), "the statement scan is not applied"

        path.write_text("_impl = __import__('hash' + 'lib')\n", encoding="utf-8")
        assert _import_offenders_for(path), "the dynamic-import scan is not applied"

    # The src-only bar must actually be applied by where a file lives.
    assert SRC_ONLY_FORBIDDEN_IMPORTS <= _barred_for(PKG_ROOT / "src" / "pkg" / "m.py")
    assert not (SRC_ONLY_FORBIDDEN_IMPORTS & _barred_for(SELF)), (
        "the guards themselves need importlib")


def test_the_shadow_detector_sees_both_a_module_and_a_package():
    """Exercised against a synthetic tree, since the real one is clean.

    Both branches matter: a shadow can be ``ugence_jcs.py`` or a directory
    ``ugence_jcs/``. Nothing else in this suite fails if either stops matching.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        (root / "clean.py").write_text("", encoding="utf-8")
        assert _substrate_shadows([root]) == []

        module = root / f"{SUBSTRATE_MODULE}.py"
        module.write_text("", encoding="utf-8")
        assert _substrate_shadows([root]) == [str(module)], "the .py branch stopped matching"
        module.unlink()

        package = root / SUBSTRATE_MODULE
        package.mkdir()
        (package / "__init__.py").write_text("", encoding="utf-8")
        assert _substrate_shadows([root]) == [str(package)], "the directory branch stopped matching"


@pytest.mark.parametrize("sample", [
    "import importlib\n_impl = importlib.import_module('hash' + 'lib')\n",
    "_impl = __import__('hash' + 'lib')\n",
    "_impl = __import__('hashlib')\n",
    "from importlib import import_module\n_impl = import_module('hashlib')\n",
    "_impl = __import__(''.join(['hash', 'lib']))\n",
    "part = 'lib'\n_impl = __import__(f'hash{part}')\n",
    # Assembled one line earlier, then passed as a bare name.
    "_NAME = 'hash' + 'lib'\n_impl = __import__(_NAME)\n",
    "_n = 'hash'\n_n += 'lib'\n_impl = __import__(_n)\n",
    "_impl = __import__(bytes([104, 97, 115, 104, 108, 105, 98]).decode())\n",
    "_NAME = '%slib' % 'hash'\n_impl = __import__(_NAME)\n",
    "_NAME: str = ''.join(['hash', 'lib'])\n_impl = __import__(_NAME)\n",
    # Built from bytes or characters, with no string method to give it away.
    "_impl = __import__(bytes(data))\n",
    "_NAME = bytearray(data)\n_impl = __import__(_NAME)\n",
    "_impl = __import__(chr(104))\n",
])
def test_a_dynamic_import_cannot_reach_a_barred_module(sample):
    """Neither by naming it nor by assembling its name.

    ``__import__`` reaches ``hashlib`` without importing ``importlib``, which is the
    route barring ``importlib`` was meant to close. An assembled name is barred
    whatever it spells: no text scan can read it.
    """
    assert _dynamic_import_offenders(sample, FORBIDDEN_IMPORTS)


#: Lawful modules that assemble a string somewhere and, separately, import by a
#: variable of the same name. A module-wide set makes the first fact about the
#: second and rejects all of these.
SCOPED_NAME_REUSE_SAMPLES = (
    # A parameter shadowing a module-level assembled name.
    ("name = 'age' + 'ntic'\n"
     "def load(name):\n    return __import__(name)\n"),
    # A comprehension loop variable — the shape the guards themselves use.
    ("import importlib\n"
     "name = 'age' + 'ntic'\n"
     "modules = [importlib.import_module(name) for name in infos]\n"),
    # A for-loop variable.
    ("import importlib\n"
     "name = 'age' + 'ntic'\n"
     "def load(infos):\n"
     "    for name in infos:\n        importlib.import_module(name)\n"),
    # Rebound from a non-assembled source before use.
    ("import importlib\n"
     "name = 'age' + 'ntic'\n"
     "name = info.name\n"
     "module = importlib.import_module(name)\n"),
)


@pytest.mark.parametrize("sample", SCOPED_NAME_REUSE_SAMPLES,
                         ids=lambda s: s.strip().split("\n")[-1][:44])
def test_an_assembled_name_in_one_scope_is_not_a_fact_about_another(sample):
    """A binding in one scope is never a binding in another.

    A set merged across the module is the merged alias map one level down: the
    first lawful contract that assembles a string and elsewhere imports by a
    same-named variable would fail this guard for no reason.
    """
    assert not _dynamic_import_offenders(sample, FORBIDDEN_IMPORTS)


def test_a_nested_scope_still_inherits_a_genuinely_assembled_name():
    """Scoping must not become a way out: an inner scope that does NOT rebind the
    name still sees the outer assembly."""
    sample = ("_NAME = 'hash' + 'lib'\n"
              "def load():\n    return __import__(_NAME)\n")
    assert _dynamic_import_offenders(sample, FORBIDDEN_IMPORTS)


@pytest.mark.parametrize("sample", [
    "import importlib\nmodule = importlib.import_module(info.name)\n",
    "import importlib\nmodule = importlib.import_module(name)\n",
    "module = __import__('pathlib')\n",
    # A name the module did not compose: bound from an attribute, or a parameter.
    "import importlib\ndef load(spec):\n    return importlib.import_module(spec.name)\n",
    "import importlib\nchosen = info.name\nmodule = importlib.import_module(chosen)\n",
])
def test_a_dynamic_import_of_a_named_module_is_permitted(sample):
    """The guards here walk this package's modules that way; barring it outright
    would make the enforcement unwritable.

    The line the rule draws is composition, not indirection: a name this module
    built is barred, a name it merely received is not.
    """
    assert not _dynamic_import_offenders(sample, FORBIDDEN_IMPORTS)


@pytest.mark.parametrize("source,expected", [
    ("_n = 'hash' + 'lib'\n", {"_n"}),
    ("_n = 'hash'\n_n += 'lib'\n", {"_n"}),
    ("_n = ''.join(parts)\n", {"_n"}),
    ("_n = f'{a}{b}'\n", {"_n"}),
    ("_n: str = bytes(data).decode()\n", {"_n"}),
    ("_n = 'hashlib'\n", set()),
    ("_n = info.name\n", set()),
    ("_n = other(x)\n", set()),
    # The value decides, not the fact of an augmented assignment.
    ("n = 0\nn += 1\n", set()),
    ("total = 0\nfor x in xs:\n    total += x\n", set()),
    # A name rebound from a non-assembled source is no longer assembled.
    ("_n = 'hash' + 'lib'\n_n = info.name\n", set()),
])
def test_assembled_string_names_are_tracked(source, expected):
    """The binding, not just the call argument.

    ``_n = "hash" + "lib"`` then ``__import__(_n)`` hands the call a bare name; a
    rule that only reads the argument expression permits it.
    """
    assert _assembled_string_names(ast.parse(source)) == expected


@pytest.mark.parametrize("sample", [
    "import importlib\n_impl = importlib.import_module('hash' + 'lib')\n",
    "from importlib import import_module\n_impl = import_module('hashlib')\n",
])
def test_the_import_scan_sees_an_indirect_import(sample):
    """A module imported through ``importlib`` is still imported.

    Assembling the name from pieces defeats every text scan, so the reachable
    mechanism is barred rather than the spelling of its argument.
    """
    barred = FORBIDDEN_IMPORTS | SRC_ONLY_FORBIDDEN_IMPORTS
    assert _forbidden_imports(sample, barred), "an indirect import route is not barred"
    assert not _forbidden_imports(sample, FORBIDDEN_IMPORTS), (
        "importlib must be barred in src only; the guards themselves need it")


def test_masking_the_substrate_call_does_not_mask_local_hashing():
    """The exemption is the exact call spelling, not the word ``sha256``.

    A module that calls the substrate AND hashes locally is still caught: masking
    removes only the permitted spellings, leaving the local call fully visible.
    """
    both = ("import hashlib\nimport ugence_jcs\n"
            "a = ugence_jcs.canonical_sha256_hex(payload)\n"
            "b = hashlib.sha256(payload).hexdigest()\n")
    assert "hashlib" in _suspect_text(both)
    assert "sha256" in _suspect_text(both)


@pytest.mark.parametrize("path", list(_package_files()), ids=lambda p: p.name)
def test_no_canonicalization_or_digest_function_is_defined(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            lowered = node.name.lower()
            for suspect in SUSPECT_DEF_SUBSTRINGS:
                if suspect in lowered:
                    offenders.append(node.name)
    assert not offenders, f"{path.name} defines {offenders}"


@pytest.mark.parametrize("path", list(_package_files()), ids=lambda p: p.name)
def test_no_canonicalization_or_hashing_source_text(path):
    found = _suspect_text(path.read_text(encoding="utf-8"), filename=path.name)
    assert not found, f"{path.name} contains {found}"


# --------------------------------------------------------------------------- #
# I1 — the module-path-scoped mask, and the five required mutation tests
# --------------------------------------------------------------------------- #

def test_the_masked_grammar_does_not_widen_to_another_module():
    """(1) An arbitrary ``sha256:`` literal in a module OTHER than the authorised one
    is still rejected: the mask is keyed on filename, not on the string alone."""
    sample = 'DIGEST_PATTERN = r"^sha256:[0-9a-f]{64}$"\nADVISORY_PREFIX = "sha256:"\n'
    assert _suspect_text(sample, filename="not_identity.py") == ["sha256"]
    assert _suspect_text(sample, filename="identity.py") == []


def test_a_class_scoped_definition_of_the_authorised_name_still_requires_the_substrate_call():
    """(2) The authorised name defined at class scope earns no exemption of its own.

    Even inside ``identity.py``, an ``advisory_digest`` assignment with no call into
    the substrate is an unpermitted identity source (A5) whether it is written at
    module scope or nested inside a class body naming one of the authorised
    functions: the exemption in ``test_advisory_contract_shape.py`` is about what
    computes the value, never about which scope or name surrounds the assignment.
    """
    shape = importlib.import_module("test_advisory_contract_shape")
    sample = (
        "class _Wrapper:\n"
        "    def compute_advisory_identity(self, payload):\n"
        "        self.advisory_digest = 'sha256:' + '0' * 64\n"
        "        return self.advisory_digest\n"
    )
    offenders = shape._unpermitted_identity_sources(sample, filename="identity.py")
    assert offenders, ("a class-scoped assignment naming an authorised function "
                       "escaped the substrate-call requirement")


def test_the_authorised_name_without_the_substrate_call_is_rejected():
    """(3) Carrying one of the authorised names is not itself a pass: a module-level
    ``compute_advisory_identity`` that assigns ``advisory_digest`` without calling the
    substrate is still an unpermitted identity source, in the authorised module or
    anywhere else."""
    shape = importlib.import_module("test_advisory_contract_shape")
    sample = (
        "def compute_advisory_identity(payload):\n"
        "    advisory_digest = 'sha256:' + '0' * 64\n"
        "    return advisory_digest\n"
    )
    assert shape._unpermitted_identity_sources(sample, filename="identity.py")


def test_the_authorised_module_may_not_import_hashlib():
    """(4) The text mask is narrow: it hides two strings and nothing else. The
    authorised module stays fully subject to the import scan, exactly like every
    other file."""
    sample = "import hashlib\nadvisory_digest = hashlib.sha256(payload).hexdigest()\n"
    assert _import_offenders_for_source(sample, "identity.py")


def _import_offenders_for_source(source, filename):
    """``_import_offenders_for`` over in-memory ``source`` rather than a path on
    disk, so a mutation sample can name itself ``identity.py`` without writing a real
    file at that path."""
    barred = FORBIDDEN_IMPORTS | SRC_ONLY_FORBIDDEN_IMPORTS
    offenders = _forbidden_imports(source, barred, filename=filename)
    return offenders + _dynamic_import_offenders(source, FORBIDDEN_IMPORTS,
                                                 filename=filename)


def test_a_locally_defined_canonical_sha256_hex_in_the_authorised_module_is_still_rejected():
    """(5) The text mask never touches ``SUSPECT_DEF_SUBSTRINGS``: a local definition
    shadowing the real substrate function's name is caught in the authorised module
    exactly as anywhere else."""
    sample = "def canonical_sha256_hex(payload):\n    return '0' * 64\n"
    tree = ast.parse(sample, filename="identity.py")
    offenders = [node.name for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and any(s in node.name.lower() for s in SUSPECT_DEF_SUBSTRINGS)]
    assert offenders == ["canonical_sha256_hex"]


#: I1's five mutation tests, named so none of them contains "digest" (I1's own rule,
#: for the same reason the field name ``advisory_digest`` is an ``AnnAssign`` target
#: rather than a definition and so is not scanned by ``SUSPECT_DEF_SUBSTRINGS``).
_I1_MUTATION_TESTS = (
    "test_the_masked_grammar_does_not_widen_to_another_module",
    "test_a_class_scoped_definition_of_the_authorised_name_still_requires_the_substrate_call",
    "test_the_authorised_name_without_the_substrate_call_is_rejected",
    "test_the_authorised_module_may_not_import_hashlib",
    "test_a_locally_defined_canonical_sha256_hex_in_the_authorised_module_is_still_rejected",
)


def test_the_five_i1_mutation_tests_are_present_and_unnamed_for_digest():
    for name in _I1_MUTATION_TESTS:
        assert name in globals() and callable(globals()[name]), name
        assert "digest" not in name.lower(), name


@pytest.mark.parametrize("path", list(_package_files()), ids=lambda p: p.name)
def test_no_hashing_module_is_imported(path):
    offenders = _import_offenders_for(path)
    assert not offenders, f"{path.name} imports {offenders}"


def test_json_is_not_used_to_canonicalize():
    """``json.dumps`` with ordering or separator control is a canonicalizer."""
    for path in _package_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if name not in ("dumps", "dump"):
                continue
            kwargs = {kw.arg for kw in node.keywords}
            assert not (kwargs & {"sort_keys", "separators", "ensure_ascii"}), \
                f"{path.name} calls json.{name} with canonicalization arguments"


def test_scan_covers_both_src_and_tests():
    """The scan is only meaningful if it actually reaches both trees."""
    scanned = {p.parent.name for p in _package_files()}
    assert "ugence_agentic_proposer" in scanned and "tests" in scanned


#: The modules discharging S1's [R] enforcement obligations, D6-D8 and the O-1/O-4
#: refinements alike. They are named here, not just swept up by the glob, because
#: each of them reasons about identity fields and about the permitted identity
#: substrate — which is exactly the place a "temporary" helper computing an identity
#: locally would be convenient to write. The identifier-normalization guard is the
#: sharpest case: it exists because identity is computed with an empty normalization
#: profile, so it names the substrate call while asserting nothing may replace it.
#: A module dropping out of the scan must fail here rather than pass quietly.
S1_ENFORCEMENT_MODULES = (
    "test_no_auditor_status_projection.py",
    "test_advisory_contract_shape.py",
    "test_role_projection_bounds.py",
    "test_selection_dependent_fields.py",
    "test_identifier_normalization.py",
)


def test_scan_covers_the_s1_enforcement_modules_by_name():
    scanned = {p.name for p in _package_files()}
    missing = [m for m in S1_ENFORCEMENT_MODULES if m not in scanned]
    assert not missing, f"outside the scan: {missing}"


def test_every_module_in_the_package_is_scanned_or_named_as_exempt():
    """No third category. A file is scanned, or it is one of the two exemptions."""
    exempt = {SELF.name, VERIFIER.name}
    on_disk = {p.name for tree in SCANNED_TREES for p in tree.rglob("*.py")
               if not any(part in {"build", "dist", ".venv", "__pycache__"}
                          for part in p.parts)}
    on_disk |= {VERIFIER.name}
    unaccounted = on_disk - {p.name for p in _package_files()} - exempt
    assert not unaccounted, f"neither scanned nor exempt: {sorted(unaccounted)}"


def test_the_only_exempt_file_is_the_packaging_verifier():
    """The exemption is one named build-time script, and it ships in no wheel.

    If the verifier ever grew a canonicalizer it would still be outside the scan, so
    this pins what the exemption covers: it hashes file bytes for artifact identity,
    and it is not part of the distributed package.
    """
    assert VERIFIER.is_file()
    body = VERIFIER.read_text(encoding="utf-8")
    # Hashing in the verifier is over file bytes only.
    assert "_sha256(path: Path)" in body
    assert "path.read_bytes()" in body
    # It is packaging tooling: setuptools ships only src/, so it is not in the wheel.
    pyproject = (PKG_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'where = ["src"]' in pyproject


def test_ugence_jcs_is_the_declared_identity_substrate():
    """D2 is recorded in the packaging metadata, not only in prose."""
    pyproject = (PKG_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "ugence-jcs>=0.2.0" in pyproject
