"""The pilot replays scenarios in one time domain — the frozen scenario clock.

A replayed scenario issues its CER on ``composition.determinism.make_clock``
(2026-01-01T00:00:00Z, so ``expires_at`` is 2026-01-01T01:00:00Z). Any
collaborator left on its own default clock — the control-plane adapter, the
audit service, either validation service, the execution adapter — stamps or
compares ``now_wall`` instead, and the two instants are then compared against
each other. Whenever they disagree in the wrong direction the pilot collapses
with ``AuthorizationExpiredError``, and whether it does depends on the date the
suite happens to run.

These guards pin the decision recorded in
``Project_documentation/repository/docs/audits/actiongate_vnext/RATIFIED_DECISIONS.md``
(decision D1): for a replayed scenario the scenario clock is authoritative, and
no wall clock may be read — by any collaborator, however it is constructed.
"""
from __future__ import annotations

import ast
import dataclasses
import importlib
import inspect
import pkgutil
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from decision_governance.api.audit import AuditService, InMemoryAuditRepository

from enterprise_validation_pilot.datasets.build_dataset import build
from enterprise_validation_pilot.runners.workflow import run_scenario


_TREE = Path(__file__).resolve().parents[1]
_ROOT = _TREE.parent

# Deliberately on the far side of the frozen scenario clock: a collaborator that
# reads this instead of the scenario clock stamps and compares the wrong instant
# — an authorization minted here is already expired against the scenario clock.
_SKEW = datetime(2025, 6, 1, tzinfo=timezone.utc)

# the collaborators the scan must keep reaching; a resolver that silently matched
# nothing would make the scan vacuous
_GUARDED = {
    "ActionGovernanceControlPlaneAdapter", "AuditService", "ExecutionValidationService",
    "ActionRequestValidationService", "build_execution_adapter", "ExecutionService"}

# kernel-opaque ids are permitted volatile fields; every substantive field is stable
_VOLATILE = {"authorization_id"}


# --------------------------------------------------------------------------
# The scan: every collaborator that accepts a clock must be handed one.
#
# Not a single-class check. For each call site under the tree the callee is
# resolved to the real object through the calling module's own imports, and the
# site is an offender whenever that object's signature has a ``clock`` parameter
# and the call does not pass one. That reaches the kernel services, the audit
# service, the validation services, the execution adapter and the control-plane
# adapter alike, and it keeps reaching a collaborator that grows a clock later.
#
# Factory-mediated construction is covered from both ends: a factory in the tree
# that itself takes ``clock`` is a collaborator, so its call sites must pass one;
# inside such a factory the constructor call it mediates is exempt, since the
# clock reaches the constructor through a forwarded mapping the AST cannot read.
# --------------------------------------------------------------------------


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


def _mediating_factories(module_ast: ast.AST) -> list:
    """Bodies of functions that take a ``clock`` and forward it onward."""
    out = []
    for node in ast.walk(module_ast):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            names = [a.arg for a in (*args.posonlyargs, *args.args, *args.kwonlyargs)]
            if "clock" in names:
                out.append(node)
    return out


def scan(tree: Path):
    """(offenders, collaborators reached) for every call site under ``tree``."""
    offenders, reached = [], set()
    for path in sorted(tree.rglob("*.py")):
        if "__pycache__" in path.parts or path == Path(__file__).resolve():
            continue          # this guard constructs on the default clock on purpose
        module_name = _module_name(path)
        module_ast = ast.parse(path.read_text(encoding="utf-8"), str(path))
        bindings = _bindings(module_ast, module_name)
        mediated = {id(c) for f in _mediating_factories(module_ast)
                    for c in ast.walk(f) if isinstance(c, ast.Call)}
        for node in ast.walk(module_ast):
            if not isinstance(node, ast.Call):
                continue
            obj = _callee(node, bindings, module_name)
            if not _accepts_clock(obj):
                continue
            reached.add(getattr(obj, "__name__", repr(obj)))
            if any(kw.arg == "clock" for kw in node.keywords):
                continue
            if id(node) in mediated and any(kw.arg is None for kw in node.keywords):
                # the clock arrives through the factory's own parameter, in a
                # forwarded mapping the AST cannot see into
                continue
            offenders.append(f"{path.relative_to(tree)}:{node.lineno} -> "
                             f"{getattr(obj, '__name__', obj)}")
    return offenders, reached


# --------------------------------------------------------------------------
# The skew seam: move every default (wall) clock the replay stack can reach.
#
# A wall clock reaches a replay three ways, and all three have to move together
# or the replay test is vacuous:
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
def _wall_clock_at(instant: datetime):
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


def _stable(result):
    d = {k: v for k, v in dataclasses.asdict(result).items() if k not in _VOLATILE}
    d["trace"] = {k: v for k, v in d["trace"].items() if k not in _VOLATILE}
    return d


# --------------------------------------------------------------------------
# guards
# --------------------------------------------------------------------------


def test_the_scan_reaches_the_collaborators_it_is_meant_to_guard():
    """A resolver that silently resolved nothing would make the scan vacuous."""
    _offenders, reached = scan(_TREE)
    missing = _GUARDED - reached
    assert not missing, (
        f"the clock-domain scan resolved no call site for {sorted(missing)}, so it is not "
        "actually guarding them — the resolver or the tree's imports have moved")


def test_no_collaborator_is_constructed_on_the_default_wall_clock():
    offenders, _reached = scan(_TREE)
    assert not offenders, (
        "these sites build a collaborator on its default wall clock while the scenario "
        f"is replayed on the frozen scenario clock: {offenders}")


def test_the_skew_seam_actually_moves_a_default_clock():
    """The replay guard below is only meaningful if the seam bites."""
    from ugence_decision_authority import common as kernel_common
    from ugence_governance_provider_framework.adapters import action_to_control_plane as a2cp

    before = kernel_common.utc_now()
    with _wall_clock_at(_SKEW):
        assert kernel_common.utc_now() == _SKEW, "the kernel clock function did not move"
        assert a2cp._default_clock() == _SKEW, "the adapter's default clock did not move"
        assert AuditService(InMemoryAuditRepository())._clock() == _SKEW, (
            "a collaborator left on its default clock did not move — the bound-default "
            "seam is not reaching parameter defaults")
    assert kernel_common.utc_now() != _SKEW or before == _SKEW, "the seam did not restore"


def test_replay_outcomes_do_not_move_when_the_wall_clock_moves():
    scenarios = list(build().ordered())
    baseline = [_stable(run_scenario(s)) for s in scenarios]
    with _wall_clock_at(_SKEW):
        skewed = [_stable(run_scenario(s)) for s in scenarios]
    differing = [s.scenario_id for s, b, k in zip(scenarios, baseline, skewed) if b != k]
    assert not differing, (
        "these scenarios replayed differently once the wall clock moved, so the pilot is "
        f"still reading it somewhere: {differing}")
