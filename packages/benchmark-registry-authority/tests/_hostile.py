"""Hostile object factories that record whether their own code ever ran.

Every factory here builds an object that *looks like* a genuine nested contract
and carries a validation method which, if the encoder ever invoked it, would
append to a shared recorder. The suites then assert **on the recorder**, not
merely on the raised error — because an error can be raised for the wrong
reason, and "the attacker's method was never called" is the property §07
actually requires.

Four forgeries, covering four different ways a check could be defeated:

* :func:`lying_post_init` — same field names, a ``__post_init__`` that records
  and returns cleanly. Defeats any boundary that trusts a node's own validator.
* :func:`same_name_same_module` — additionally forges ``__name__`` **and**
  ``__module__`` to match the genuine class. Defeats name-based or module-based
  membership.
* :func:`metaclass_forged` — a metaclass overriding the *class object's* own
  ``__eq__``/``__hash__`` so the forged class compares equal to, and hashes the
  same as, the genuine one. Defeats ``in``/``[]`` membership on a registry dict
  without touching the registry's contents.
* :func:`subclass_override` — a genuine **subclass** overriding
  ``__post_init__``. Defeats ``isinstance``, which is why every boundary in this
  package uses ``type(x) is Expected``.
"""

from __future__ import annotations

import dataclasses

#: Every invocation any hostile validation method receives **while armed**.
#: Must stay empty across every act under test.
INVOCATIONS: list = []

# Building a hostile object necessarily runs its own ``__post_init__`` once, via
# the dataclass ``__init__`` — that is the attacker constructing their own
# forgery, not the package invoking it, and counting it would make every
# assertion trivially fail for the wrong reason. Recording is therefore **armed
# separately**, immediately before the act under test, so the recorder answers
# exactly one question: *did the package give the attacker's code control?*
_ARMED = False


def reset() -> None:
    """Disarm and clear. Call before building forgeries."""

    global _ARMED
    _ARMED = False
    INVOCATIONS.clear()


def arm() -> None:
    """Start recording. Call immediately before the act under test."""

    global _ARMED
    INVOCATIONS.clear()
    _ARMED = True


def _record(tag: str) -> None:
    if _ARMED:
        INVOCATIONS.append(tag)


def _field_values(genuine):
    return {f.name: getattr(genuine, f.name) for f in dataclasses.fields(genuine)}


def lying_post_init(genuine, tag="lying_post_init"):
    """A same-shaped dataclass whose ``__post_init__`` records and returns."""

    fields = [
        (f.name, object, dataclasses.field(default=None))
        for f in dataclasses.fields(genuine)
    ]

    def __post_init__(self):  # noqa: N807
        _record(tag)

    cls = dataclasses.make_dataclass(
        f"Hostile{type(genuine).__name__}",
        fields,
        frozen=True,
        namespace={"__post_init__": __post_init__},
    )
    return cls(**_field_values(genuine))


def same_name_same_module(genuine, tag="same_name_same_module"):
    """A forgery whose ``__name__`` and ``__module__`` both match the genuine class."""

    forged = lying_post_init(genuine, tag=tag)
    type(forged).__name__ = type(genuine).__name__
    type(forged).__qualname__ = type(genuine).__qualname__
    type(forged).__module__ = type(genuine).__module__
    return forged


def metaclass_forged(genuine, tag="metaclass_forged"):
    """A forgery whose **metaclass** forges the class object's equality and hash."""

    target = type(genuine)

    class ForgingMeta(type):
        def __eq__(cls, other):  # noqa: N805
            return True

        def __ne__(cls, other):  # noqa: N805
            return False

        def __hash__(cls):  # noqa: N805
            return hash(target)

    def __post_init__(self):  # noqa: N807
        _record(tag)

    namespace = {
        "__annotations__": {
            f.name: object for f in dataclasses.fields(genuine)
        },
        "__post_init__": __post_init__,
        "__module__": target.__module__,
        # Supplied so ``@dataclass`` does not synthesize one. On CPython 3.10
        # ``dataclasses._process_class`` builds a missing ``__doc__`` from
        # ``str(inspect.signature(cls))``, and ``inspect`` takes a wrong branch
        # on a class whose metaclass forges ``__eq__`` — raising ValueError
        # before the forgery is ever handed to the code under test. That is a
        # limitation of the forgery builder on one interpreter, not of the
        # package, and it must not silently remove 3.10 from the tested matrix.
        "__doc__": f"Metaclass-forged stand-in for {target.__name__}.",
    }
    forged_cls = ForgingMeta(target.__name__, (), namespace)
    forged_cls = dataclasses.dataclass(frozen=True)(forged_cls)
    return forged_cls(**_field_values(genuine))


def subclass_override(genuine, tag="subclass_override"):
    """A genuine **subclass** overriding ``__post_init__`` to record."""

    target = type(genuine)

    def __post_init__(self):  # noqa: N807
        _record(tag)

    subclass = type(
        f"Sub{target.__name__}",
        (target,),
        {"__post_init__": __post_init__},
    )
    subclass = dataclasses.dataclass(frozen=True)(subclass)
    return subclass(**_field_values(genuine))


#: Every forgery, in the order the suites apply them.
HOSTILE_FACTORIES = (
    ("lying_post_init", lying_post_init),
    ("same_name_same_module", same_name_same_module),
    ("metaclass_forged", metaclass_forged),
    ("subclass_override", subclass_override),
)
