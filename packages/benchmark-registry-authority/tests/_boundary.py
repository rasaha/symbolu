"""Resolve annotations to real class objects, so a boundary gate cannot be spelled past.

The gates that assert BR-2B's central boundary — *no callable consumes a
transition plan, and no planner returns a lifecycle payload* — first matched the
literal substring ``"BenchmarkTransitionPlan"`` in an annotation, and skipped any
parameter whose annotation was ``None``. The closure audit showed the property
held at that commit while all four gates could be walked past three ways:

* **an alias.** ``PlanAlias = BenchmarkTransitionPlan`` or a ``Union`` containing
  it spells the annotation without the substring.
* **no annotation at all.** ``def apply(plan):`` was skipped, not failed.
* **a widened return.** Under PEP 563 every annotation in these modules is a
  *string*, so reading ``inspect.signature(...).return_annotation`` returned
  ``"BenchmarkPlanningOutcome"`` — one opaque name, whose members were never
  inspected. Widening the alias to include a registry event was invisible.

So nothing here matches text. Annotations are resolved through
:func:`typing.get_type_hints`, which evaluates PEP 563 strings against the
function's own globals, and every ``Union``/``Optional``/generic is walked with
:func:`typing.get_args` down to the class objects. Membership is then decided by
**identity** against the real class — the same ``is``-based discipline the
contract-type registry uses, and for the same reason: a name can be forged, a
class object cannot.
"""

from __future__ import annotations

import inspect
import typing

__all__ = [
    "types_in_annotation",
    "resolved_parameter_types",
    "resolved_return_types",
    "unannotated_parameters",
    "names_resolving_to",
]


def types_in_annotation(annotation: object) -> set:
    """Every class object reachable inside ``annotation``.

    Walks ``Union``, ``Optional``, and generic parameters to their leaves, so a
    plan hidden inside ``Optional[Union[Plan, None]]`` is as visible as a bare
    one. Non-class leaves (``None``, ``Ellipsis``, ``TypeVar``) are dropped
    rather than raising: this answers "which classes does this mention", and
    anything that is not a class mentions none.
    """

    found: set = set()
    pending = [annotation]
    visited: list = []
    while pending:
        current = pending.pop()
        if any(current is seen for seen in visited):
            continue
        visited.append(current)
        if isinstance(current, type):
            found.add(current)
        origin = typing.get_origin(current)
        if isinstance(origin, type):
            found.add(origin)
        pending.extend(typing.get_args(current))
    return found


def _hints(func) -> dict:
    """Resolved type hints, or an empty mapping when they cannot be resolved.

    An unresolvable hint is **not** silently treated as absent by the callers:
    :func:`unannotated_parameters` reports a parameter with no usable resolved
    type as unannotated, which the gates treat as a failure inside
    ``contracts/``. A hint that cannot be resolved is a hint that cannot be
    checked, and an unchecked annotation is exactly what this module exists to
    stop being invisible.
    """

    try:
        return typing.get_type_hints(func)
    except Exception:  # pragma: no cover - defensive; reported as unannotated
        return {}


def resolved_parameter_types(func) -> dict:
    """``{parameter name: {class objects in its resolved annotation}}``."""

    hints = _hints(func)
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):  # pragma: no cover - builtins
        return {}
    # A missing hint yields the empty set, never the ``inspect.Parameter.empty``
    # sentinel — that sentinel is itself a class, so walking it would report a
    # spurious type for every unannotated parameter.
    return {
        name: types_in_annotation(hints[name]) if name in hints else set()
        for name in signature.parameters
    }


def resolved_return_types(func) -> set:
    """Every class object the resolved return annotation mentions.

    An alias resolves to what it aliases, so widening
    ``BenchmarkPlanningOutcome`` to include a registry event makes that event
    appear here — which is precisely what the string-reading version could not
    see.
    """

    hints = _hints(func)
    return types_in_annotation(hints["return"]) if "return" in hints else set()


def unannotated_parameters(func) -> list:
    """Parameters carrying no resolvable annotation, excluding ``self``/``cls``.

    ``self`` and ``cls`` are exempt because annotating the receiver is not the
    convention anywhere in this package. Everything else is not exempt: an
    unannotated parameter is the cheapest way to hide a plan, and a gate that
    skipped it was inviting exactly that.
    """

    hints = _hints(func)
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):  # pragma: no cover - builtins
        return []
    return [
        name
        for name in signature.parameters
        if name not in ("self", "cls") and name not in hints
    ]


def names_resolving_to(module, target: type) -> set:
    """Every attribute name in ``module`` whose value mentions ``target``.

    Used by the source-tree scan, which reads AST and therefore cannot resolve
    an alias on its own. Computing the alias names at runtime and matching the
    AST against that set closes the alias hole in the textual scan too, while
    keeping the scan's reach over closures and nested functions that no runtime
    attribute walk can see.
    """

    names = {target.__name__}
    for name, value in vars(module).items():
        if name.startswith("__"):
            continue
        if value is target or target in types_in_annotation(value):
            names.add(name)
    return names
