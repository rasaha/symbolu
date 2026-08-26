"""The shared D1 clock-domain guard: one implementation, three harness trees.

Decision D1 (``Project_documentation/repository/docs/audits/actiongate_vnext/
RATIFIED_DECISIONS.md``) says a replayed scenario has exactly one time domain —
the frozen scenario clock its DGM services are built from — and fixes the rule's
applicability at **composition-root granularity**: a composition root that
injects a clock into any Decision Authority or governance-provider-framework
collaborator must inject one into *every* clock-capable collaborator it wires.
A root that injects nowhere is not replaying under an injected clock and the
guard says nothing about it.

This module carries the parts of that guard that do not vary between trees: the
call-site scan that implements the trigger, and the skew seam that moves every
default (wall) clock the replay stack can reach. Each tree keeps its own
``tests/test_clock_domain.py`` for the part that does vary — the replay body
that re-runs its own scenarios across the seam.

It is hosted here because ``comparative_governance_benchmark`` and
``provider_heterogeneity_validation`` already depend on the pilot; the reverse
dependency does not exist and must not be created.
"""
from __future__ import annotations

import ast
import dataclasses
import functools
import importlib
import inspect
import pkgutil
import sys
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

# Deliberately on the far side of the frozen scenario clock (2026-01-01T00:00:00Z):
# a collaborator that reads this instead of the scenario clock stamps and compares
# the wrong instant — an authorization minted here is already expired against the
# scenario clock. This is the skew that originally reproduced the regression.
SKEW = datetime(2025, 6, 1, tzinfo=timezone.utc)

# The authorities D1 speaks about. Injecting a clock into a collaborator defined
# in one of these — directly, or through a tree-owned factory that constructs one
# — is what makes a composition root subject to the rule.
_AUTHORITIES = (
    "ugence_decision_authority", "decision_governance",
    "ugence_governance_provider_framework", "governance_providers")

# kernel-opaque ids are permitted volatile fields; every substantive field is stable
_VOLATILE = {"authorization_id"}

_MODULE_ROOT = "<module>"


# --------------------------------------------------------------------------
# The scan: the D1 trigger, evaluated one composition root at a time.
#
# For each call site under a tree the callee is resolved to the real object
# through the calling module's own imports, and the site counts as a
# collaborator whenever that object's signature has a ``clock`` parameter. Sites
# are then grouped by their composition root — the top-level class or function
# that does the wiring, or the module body for wiring done at import time. A root
# that hands a clock to an authority collaborator is subject to D1, and every
# clock-capable site in it that passes none is an offender. A root that injects
# nowhere is silent.
#
# The scan is not a single-class check: it reaches the kernel services, the audit
# service, the validation services, the execution adapter and the control-plane
# adapter alike, and it keeps reaching a collaborator that grows a clock later.
#
# Factory-mediated construction is covered from both ends: a factory that itself
# takes ``clock`` is a collaborator, so its own call sites must pass one; inside
# such a factory the constructor it mediates is exempt, since the clock reaches
# that constructor through a forwarded mapping the AST cannot read.
# --------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class _Site:
    path: Path
    lineno: int
    name: str
    injected: bool
    authority: bool

    def render(self, tree: Path) -> str:
        return f"{self.path.relative_to(tree)}:{self.lineno} -> {self.name}"


def _module_name(path: Path) -> str:
    return ".".join(path.relative_to(_ROOT).with_suffix("").parts)


def _bindings(module_ast: ast.AST, module_name: str) -> dict:
    """Local name -> the dotted module it can be resolved against.

    ``from x import Y`` binds ``Y`` to module ``x``; ``import a.b as m`` binds
    ``m`` to the module itself (recorded as its own dotted name).
    """
    package = module_name.rsplit(".", 1)[0]
    out: dict[str, str] = {}
    for node in ast.walk(module_ast):
        if isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parts = package.split(".")
                anchor = ".".join(parts[: len(parts) - node.level + 1])
                base = f"{anchor}.{base}" if base else anchor
            for alias in node.names:
                out[alias.asname or alias.name] = base
        elif isinstance(node, ast.Import):
            for alias in node.names:
                out[alias.asname or alias.name.split(".")[0]] = (
                    alias.name if alias.asname else alias.name.split(".")[0])
    return out


def _load(module: str, attr: str | None = None):
    try:
        obj = importlib.import_module(module)
    except Exception:
        return None
    return getattr(obj, attr, None) if attr else obj


def _callee(node: ast.Call, bindings: dict, module_name: str):
    """The object a call refers to, or None when it cannot be resolved statically."""
    func = node.func
    if isinstance(func, ast.Name):
        origin = bindings.get(func.id)
        if origin is not None:
            return _load(origin, func.id)
        return _load(module_name, func.id)          # defined in this module
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        origin = bindings.get(func.value.id)
        if origin is None:
            return None                              # `self.x(...)`, a local, ...
        holder = _load(origin) if origin == func.value.id else _load(origin, func.value.id)
        return getattr(holder, func.attr, None) if holder is not None else None
    return None


def _accepts_clock(obj) -> bool:
    if not callable(obj):
        return False
    try:
        return "clock" in inspect.signature(obj).parameters
    except (TypeError, ValueError):
        return False


def _defining_module(obj) -> str:
    return getattr(obj, "__module__", "") or ""


def _is_authority(obj) -> bool:
    """Defined by the Decision Authority kernel or the provider framework."""
    module = _defining_module(obj)
    return any(module == a or module.startswith(a + ".") for a in _AUTHORITIES)


@functools.lru_cache(maxsize=None)
def _is_authority_facing(obj) -> bool:
    """An authority collaborator, or a factory whose whole job is to build one.

    ``build_execution_adapter`` is tree-owned but constructs the kernel's
    ``OfflineDeterministicExecutionAdapter``; handing it a clock is handing the
    kernel a clock, so a root that does so is subject to D1. Resolved one level
    deep through the factory's own module, which is as far as the construction
    is ever nested here.
    """
    if _is_authority(obj):
        return True
    try:
        source_file = inspect.getsourcefile(obj)
        name = obj.__name__
    except (TypeError, AttributeError):
        return False
    if not source_file or not name:
        return False
    path = Path(source_file)
    try:
        module_ast = ast.parse(path.read_text(encoding="utf-8"), str(path))
    except (OSError, SyntaxError):
        return False
    module_name = _defining_module(obj)
    bindings = _bindings(module_ast, module_name)
    for node in ast.walk(module_ast):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name != name:
            continue
        for call in ast.walk(node):
            if not isinstance(call, ast.Call):
                continue
            inner = _callee(call, bindings, module_name)
            if _accepts_clock(inner) and _is_authority(inner):
                return True
    return False


def _clock_bearing_functions(module_ast: ast.AST) -> list:
    """Function nodes that take a ``clock`` and can therefore forward one onward."""
    out = []
    for node in ast.walk(module_ast):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            names = [a.arg for a in (*args.posonlyargs, *args.args, *args.kwonlyargs)]
            if "clock" in names:
                out.append(node)
    return out


def _roots(module_ast: ast.AST) -> dict:
    """Call node id -> its composition root.

    A composition root is the top-level definition that does the wiring: a class
    (all of whose methods wire one object's collaborators together — the pilot's
    ``PilotComposition`` builds its adapter, its control plane and its DGM bundle
    across three methods, and they are one root), a module-level function, or the
    module body for wiring done at import time. Definitions nested inside one of
    those belong to it.
    """
    out: dict[int, str] = {}

    def descend(node, root: str):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                descend(child, child.name if root == _MODULE_ROOT else root)
                continue
            if isinstance(child, ast.Call):
                out[id(child)] = root
            descend(child, root)

    descend(module_ast, _MODULE_ROOT)
    return out


def scan(tree: Path):
    """(offenders, collaborators reached) for every composition root under ``tree``.

    An offender is a clock-capable collaborator built on its default clock inside
    a root that hands an injected clock to an authority collaborator elsewhere —
    the mixed time domain D1 forbids. A root that injects nowhere is silent.
    """
    by_root: dict = defaultdict(list)
    reached: set = set()
    for path in sorted(tree.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        module_name = _module_name(path)
        try:
            module_ast = ast.parse(path.read_text(encoding="utf-8"), str(path))
        except SyntaxError:
            continue
        bindings = _bindings(module_ast, module_name)
        roots = _roots(module_ast)
        mediated = {id(c) for f in _clock_bearing_functions(module_ast)
                    for c in ast.walk(f) if isinstance(c, ast.Call)}
        for node in ast.walk(module_ast):
            if not isinstance(node, ast.Call):
                continue
            obj = _callee(node, bindings, module_name)
            if not _accepts_clock(obj):
                continue
            reached.add(getattr(obj, "__name__", repr(obj)))
            injected = any(kw.arg == "clock" for kw in node.keywords)
            if not injected and id(node) in mediated and any(
                    kw.arg is None for kw in node.keywords):
                # the clock arrives through the enclosing factory's own parameter,
                # in a forwarded mapping the AST cannot see into
                injected = True
            by_root[(str(path), roots.get(id(node), _MODULE_ROOT))].append(_Site(
                path=path, lineno=node.lineno,
                name=getattr(obj, "__name__", repr(obj)), injected=injected,
                authority=_is_authority_facing(obj)))

    offenders = []
    for (path, root), group in sorted(by_root.items()):
        if not any(s.injected and s.authority for s in group):
            continue                                  # this root is not replaying
        offenders.extend(f"{s.render(tree)} (root {Path(path).name}:{root})"
                         for s in group if not s.injected)
    return sorted(offenders), reached


# --------------------------------------------------------------------------
# The skew seam: move every default (wall) clock the replay stack can reach.
#
# A wall clock reaches a replay three ways, and all three have to move together
# or a tree's replay body is vacuous:
#
#   1. ``ugence_decision_authority.common.utc_now`` — the kernel's clock
#      function, read by anything that calls it through its module.
#   2. The parameter defaults that *bound* ``utc_now`` at import time. A kernel
#      collaborator constructed without ``clock=`` holds the original function
#      object in ``__init__.__kwdefaults__``, where patching a module attribute
#      cannot reach it.
#   3. ``ActionGovernanceControlPlaneAdapter``'s default, which resolves
#      ``utc_now`` through the framework adapter's lazily built kernel cache.
# --------------------------------------------------------------------------


def _kernel_modules():
    import ugence_decision_authority as kernel

    for info in pkgutil.walk_packages(kernel.__path__, kernel.__name__ + "."):
        try:
            importlib.import_module(info.name)
        except Exception:                            # optional/absent submodule
            pass
    return [m for name, m in list(sys.modules.items())
            if m is not None and (name == "ugence_decision_authority"
                                  or name.startswith("ugence_decision_authority."))]


def _rebind(func, original, replacement) -> list:
    """Swap ``original`` for ``replacement`` in one callable's defaults."""
    undo = []
    kwdefaults = func.__kwdefaults__ or {}
    for key, value in list(kwdefaults.items()):
        if value is original:
            kwdefaults[key] = replacement
            undo.append(lambda k=key, f=func: f.__kwdefaults__.__setitem__(k, original))
    defaults = func.__defaults__ or ()
    if any(value is original for value in defaults):
        func.__defaults__ = tuple(replacement if v is original else v for v in defaults)
        undo.append(lambda f=func, d=defaults: setattr(f, "__defaults__", d))
    return undo


@contextmanager
def wall_clock_at(instant: datetime):
    """Pin every default wall clock the replay stack can reach to ``instant``."""
    from ugence_decision_authority import common as kernel_common
    from ugence_governance_provider_framework.adapters import action_to_control_plane as a2cp

    original = kernel_common.utc_now

    def replacement(*_args, **_kwargs):
        return instant

    undo = []
    for module in _kernel_modules():
        for name in dir(module):
            member = getattr(module, name, None)
            if member is original:                                       # seam 1
                setattr(module, name, replacement)
                undo.append(lambda m=module, n=name: setattr(m, n, original))
                continue
            target = member if inspect.isfunction(member) else getattr(
                member, "__init__", None) if inspect.isclass(member) else None
            if inspect.isfunction(target):                               # seam 2
                undo.extend(_rebind(target, original, replacement))

    a2cp._kernel()                                                       # seam 3
    cached = a2cp._KERNEL["utc_now"]
    a2cp._KERNEL["utc_now"] = replacement
    undo.append(lambda: a2cp._KERNEL.__setitem__("utc_now", cached))

    try:
        yield
    finally:
        for restore in reversed(undo):
            restore()


def stable(result):
    """A replay result with only its kernel-opaque ids dropped."""
    d = {k: v for k, v in dataclasses.asdict(result).items() if k not in _VOLATILE}
    d["trace"] = {k: v for k, v in d["trace"].items() if k not in _VOLATILE}
    return d


# --------------------------------------------------------------------------
# the guards each tree re-exports as its own tests
# --------------------------------------------------------------------------


def assert_scan_reaches(tree: Path, guarded: set) -> None:
    """A resolver that silently resolved nothing would make the scan vacuous."""
    _offenders, reached = scan(tree)
    missing = set(guarded) - reached
    assert not missing, (
        f"the clock-domain scan resolved no call site for {sorted(missing)}, so it is not "
        "actually guarding them — the resolver or the tree's imports have moved")


def assert_no_root_mixes_clock_domains(tree: Path) -> None:
    """D1 at composition-root granularity: inject in a root, inject throughout it."""
    offenders, _reached = scan(tree)
    assert not offenders, (
        "these sites build a collaborator on its default wall clock inside a composition "
        "root that hands the scenario clock to an authority collaborator elsewhere, so the "
        f"root replays in two time domains: {offenders}")


def assert_the_skew_seam_bites() -> None:
    """A tree's replay body is only meaningful if the seam actually moves a clock."""
    from decision_governance.api.audit import AuditService, InMemoryAuditRepository
    from ugence_decision_authority import common as kernel_common
    from ugence_governance_provider_framework.adapters import action_to_control_plane as a2cp

    before = kernel_common.utc_now()
    with wall_clock_at(SKEW):
        assert kernel_common.utc_now() == SKEW, "the kernel clock function did not move"
        assert a2cp._default_clock() == SKEW, "the adapter's default clock did not move"
        assert AuditService(InMemoryAuditRepository())._clock() == SKEW, (
            "a collaborator left on its default clock did not move — the bound-default "
            "seam is not reaching parameter defaults")
    assert kernel_common.utc_now() != SKEW or before == SKEW, "the seam did not restore"
