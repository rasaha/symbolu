"""Public-API compatibility checker (Task 7).

Compares two API snapshots and classifies each difference as BREAKING (MAJOR),
ADDITIVE (MINOR-compatible), or INFO. Breaking changes fail verification unless
the platform major version is explicitly advanced.

Breaking: removed symbol, kind change, removed/renamed function param, new
required param, removed field, new required field, enum value removal, protocol
method removal/signature change, exception base change.
Additive: new symbol, new optional param, new optional field, new enum value,
new protocol method.
"""
from __future__ import annotations

from dataclasses import dataclass

BREAKING = "BREAKING"
ADDITIVE = "ADDITIVE"
INFO = "INFO"


@dataclass(frozen=True)
class Diff:
    severity: str
    location: str
    change: str


def _param_map(fn: dict) -> dict:
    return {p["name"]: p for p in fn.get("params", [])}


def _compare_fn(loc: str, old: dict, new: dict, out: list) -> None:
    op, np = _param_map(old), _param_map(new)
    for name in op:
        if name not in np:
            out.append(Diff(BREAKING, loc, f"parameter '{name}' removed"))
    for name, p in np.items():
        if name not in op and not p.get("has_default", False) \
                and p["kind"] not in ("VAR_POSITIONAL", "VAR_KEYWORD"):
            out.append(Diff(BREAKING, loc, f"new required parameter '{name}'"))
        elif name not in op:
            out.append(Diff(ADDITIVE, loc, f"new optional parameter '{name}'"))
    # a changed default-ness of an existing param is breaking
    for name in op:
        if name in np and op[name].get("has_default") and not np[name].get("has_default"):
            out.append(Diff(BREAKING, loc, f"parameter '{name}' lost its default"))


def _compare_fields(loc: str, old: dict, new: dict, out: list) -> None:
    for name in old:
        if name not in new:
            out.append(Diff(BREAKING, loc, f"field '{name}' removed"))
    for name, f in new.items():
        if name not in old:
            sev = BREAKING if f.get("required") else ADDITIVE
            out.append(Diff(sev, loc, f"{'required' if f.get('required') else 'optional'} "
                                      f"field '{name}' added"))
    for name in old:
        if name in new and not old[name].get("required") and new[name].get("required"):
            out.append(Diff(BREAKING, loc, f"field '{name}' became required"))


def _compare_symbol(loc: str, old: dict, new: dict, out: list) -> None:
    if old.get("kind") != new.get("kind"):
        out.append(Diff(BREAKING, loc, f"kind changed {old.get('kind')} -> {new.get('kind')}"))
        return
    kind = old.get("kind")
    if kind == "function":
        _compare_fn(loc, old, new, out)
    elif kind == "enum":
        ov, nv = old.get("values", {}), new.get("values", {})
        for k in ov:
            if k not in nv:
                out.append(Diff(BREAKING, loc, f"enum value '{k}' removed"))
            elif ov[k] != nv[k]:
                out.append(Diff(BREAKING, loc, f"enum value '{k}' changed {ov[k]} -> {nv[k]}"))
        for k in nv:
            if k not in ov:
                out.append(Diff(ADDITIVE, loc, f"enum value '{k}' added"))
    elif kind == "exception":
        if old.get("bases") != new.get("bases"):
            out.append(Diff(BREAKING, loc, f"exception bases changed {old.get('bases')} "
                                           f"-> {new.get('bases')}"))
    elif kind == "protocol":
        om, nm = old.get("methods", {}), new.get("methods", {})
        for m in om:
            if m not in nm:
                out.append(Diff(BREAKING, f"{loc}.{m}", "protocol method removed"))
            else:
                _compare_fn(f"{loc}.{m}", om[m], nm[m], out)
        for m in nm:
            if m not in om:
                out.append(Diff(ADDITIVE, f"{loc}.{m}", "protocol method added"))
        _compare_fields(loc, old.get("fields", {}), new.get("fields", {}), out)
    elif kind == "class":
        _compare_fields(loc, old.get("fields", {}), new.get("fields", {}), out)
        om, nm = old.get("methods", {}), new.get("methods", {})
        for m in om:
            if m not in nm:
                out.append(Diff(BREAKING, f"{loc}.{m}", "method removed"))
            else:
                _compare_fn(f"{loc}.{m}", om[m], nm[m], out)
        for m in nm:
            if m not in om:
                out.append(Diff(ADDITIVE, f"{loc}.{m}", "method added"))
    elif kind == "constant":
        if old.get("value") != new.get("value"):
            out.append(Diff(INFO, loc, f"constant value changed {old.get('value')} "
                                       f"-> {new.get('value')}"))


def compare_snapshots(old: dict, new: dict) -> list:
    """old/new: snapshot_all() outputs {module -> {symbols: {...}}}."""
    diffs: list = []
    for module in sorted(set(old) | set(new)):
        if module not in new:
            diffs.append(Diff(BREAKING, module, "module removed"))
            continue
        if module not in old:
            diffs.append(Diff(ADDITIVE, module, "module added"))
            continue
        osym = old[module].get("symbols", {})
        nsym = new[module].get("symbols", {})
        for name in osym:
            loc = f"{module}.{name}"
            if name not in nsym:
                diffs.append(Diff(BREAKING, loc, "symbol removed"))
            else:
                _compare_symbol(loc, osym[name], nsym[name], diffs)
        for name in nsym:
            if name not in osym:
                diffs.append(Diff(ADDITIVE, f"{module}.{name}", "symbol added"))
    return diffs


def classify(diffs: list) -> str:
    if any(d.severity == BREAKING for d in diffs):
        return "MAJOR"
    if any(d.severity == ADDITIVE for d in diffs):
        return "MINOR"
    return "PATCH"


def is_compatible(diffs: list) -> bool:
    return not any(d.severity == BREAKING for d in diffs)
