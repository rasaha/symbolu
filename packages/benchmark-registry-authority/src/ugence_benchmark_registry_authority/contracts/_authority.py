"""The universal no-authority rule, installed as permanent derived properties.

§09 requires that **every caller-constructible type in this package capable of
describing an authority action must permanently derive**, as non-fields:

* ``authority_verified is False``
* ``publisher_authenticity_established is False``
* ``approval_authenticity_established is False``
* ``registry_admission_established is False``
* ``trusted_resolution_established is False``

"Permanently" is the operative word, and it rules out three tempting designs:

* **Not a field.** A field is a constructor argument, which means a caller
  supplies it, which means a caller can supply :data:`True`. Then the artifact
  asserting it is trustworthy is the artifact itself — precisely the
  caller-created verification object ADR B-5 rules is not evidence.
* **Not a class attribute.** ``Cls.authority_verified = True`` is legal Python
  for anyone who imported the module, and every existing instance would follow.
* **Not an inherited property.** A base class supplying these would be a
  "subclass hook": a subclass overriding one would inherit every other genuine
  behaviour while lying about the one thing that matters.

:func:`permanently_unverified_authority` therefore installs the properties
**directly on each decorated class**, with no shared base class and no ``super()``
path. Every class carries its own five properties.

Assignment is impossible on two independent grounds: the classes are
``@dataclass(frozen=True)``, and a ``property`` with no setter raises
:class:`AttributeError` on assignment regardless. ``object.__setattr__`` cannot
reach them either — there is no instance ``__dict__`` entry to overwrite,
because a data descriptor on the class always wins over instance state.

What survives the boundary
--------------------------
``tests/contract/test_no_authority.py`` proves the derivation survives every
route a caller has: construction, :func:`copy.copy`, :func:`copy.deepcopy`,
:mod:`pickle` round-trip, ``dataclasses.replace``, subclassing, a forged
same-named object, and the canonical payload itself. It also proves the
complementary property — that no caller-constructed payload can satisfy an API
expecting an authority-issued result, because the authority-issued result types
**do not exist at BR-2A** and their names are reserved.

Why the names are reserved rather than defined
----------------------------------------------
``BenchmarkAdmissionDecision``, ``BenchmarkRegistrationEvent`` and
``BenchmarkResolution`` are the authority-issued types. BR-2A defines **none** of
them; it defines their caller-constructible structural counterparts, each
suffixed ``Payload``. A caller can build a payload all day and never build a
result, because the result type has no definition to instantiate — which is a
stronger guarantee than a result type that exists and merely refuses to be
constructed.
"""

from __future__ import annotations

__all__ = [
    "BENCHMARK_UNVERIFIED_AUTHORITY_PROPERTIES",
    "BENCHMARK_RESERVED_AUTHORITY_ISSUED_TYPE_NAMES",
    "permanently_unverified_authority",
    "permanently_unverified_signature",
]

#: The five properties §09 requires on every authority-describing contract, in
#: ratified order. Published so the inventory, the tests and the probe harness
#: all read one list rather than three copies of it.
BENCHMARK_UNVERIFIED_AUTHORITY_PROPERTIES: tuple = (
    "authority_verified",
    "publisher_authenticity_established",
    "approval_authenticity_established",
    "registry_admission_established",
    "trusted_resolution_established",
)

#: The authority-issued result type names reserved for a later milestone and
#: **deliberately not defined** at BR-2A. ``tests/packaging/test_milestone_
#: boundary.py`` asserts that none of them exists anywhere in this package.
BENCHMARK_RESERVED_AUTHORITY_ISSUED_TYPE_NAMES: tuple = (
    "BenchmarkAdmissionDecision",
    "BenchmarkRegistrationEvent",
    "BenchmarkResolution",
)

_AUTHORITY_DOC = {
    "authority_verified": (
        "Permanently ``False``. No authority verified this object: this "
        "package ships no admission engine, no trust store and no registry, "
        "and a cryptographic verification is not an authority act. "
        "Derived with no constructor argument, no setter and no subclass hook."
    ),
    "publisher_authenticity_established": (
        "Permanently ``False``. A declared publisher identity and a "
        "well-formed detached signature are a *claim about* a publisher, not "
        "proof of one. Establishing publisher authenticity requires the "
        "audited Ed25519 verifier and the composition-root trust resolver of "
        "BR-2C, neither of which exists here."
    ),
    "approval_authenticity_established": (
        "Permanently ``False``. Neither a "
        ":class:`~.envelopes.BenchmarkApprovalEnvelope` nor a BR-1 artifact "
        "carrying ``lifecycle_state=APPROVED`` establishes approval: ADR B-5 "
        "rules that a lifecycle enum on the artifact is not approval evidence, "
        "and an unverified approval envelope is a signed-looking assertion "
        "nobody checked."
    ),
    "registry_admission_established": (
        "Permanently ``False``. Nothing in this package can admit anything. "
        "The six-stage admission ordering, the append-only log and the slot "
        "claim are BR-2D; a caller-constructed payload declaring ``ADMITTED`` "
        "records a declaration and nothing else."
    ),
    "trusted_resolution_established": (
        "Permanently ``False``. B-9: possession is not validity, retrieval is "
        "not resolution. Holding this object — or any digest of it — resolves "
        "nothing, authorizes nothing and establishes no active eligibility."
    ),
}


def _install_false_property(cls: type, name: str, doc: str) -> None:
    """Install one permanently-``False`` read-only property directly on ``cls``.

    Directly on the class, never on a shared base: there is no ``super()`` path
    to intercept and no inherited descriptor to override. The closure captures
    nothing mutable, so the returned value is a literal :data:`False` with no
    state behind it.
    """

    def _always_false(self) -> bool:
        return False

    _always_false.__name__ = name
    _always_false.__qualname__ = f"{cls.__name__}.{name}"
    _always_false.__doc__ = doc
    setattr(cls, name, property(_always_false, doc=doc))


def permanently_unverified_authority(cls: type) -> type:
    """Class decorator installing §09's five permanent ``False`` derivations.

    Applied to every caller-constructible contract in this package capable of
    describing an authority action — every envelope, every administrative
    payload and both read payloads.

    Refuses to overwrite an existing attribute of the same name, so a class that
    tried to declare one of these as a *field* fails at import time rather than
    shipping a settable authority claim.
    """

    for name in BENCHMARK_UNVERIFIED_AUTHORITY_PROPERTIES:
        if name in cls.__dict__:
            raise TypeError(
                f"{cls.__name__} already declares {name!r}; the five "
                "no-authority derivations are never fields, never class "
                "attributes and never overridable — a class that declares one "
                "itself would be shipping a settable authority claim"
            )
        _install_false_property(cls, name, _AUTHORITY_DOC[name])
    return cls


def permanently_unverified_signature(cls: type) -> type:
    """Install the two further permanent ``False`` derivations every envelope carries.

    ``signature_verified`` and ``admission_established`` are additional to §09's
    five, and are what keep a *signed-looking* envelope from reading as a
    verified one. Same discipline, same impossibility of assignment: a validator
    that checked 128 lowercase hex characters checked an **encoding**, and an
    encoding is not a signature.
    """

    for name, doc in (
        (
            "signature_verified",
            "Permanently ``False``. The detached signature field was validated "
            "as an *encoding* — exactly 128 lowercase hex characters — and "
            "nothing more. No key was parsed, no anchor was consulted, no "
            "curve operation was performed, and this package ships no "
            "cryptographic dependency at all.",
        ),
        (
            "admission_established",
            "Permanently ``False``. An envelope is an inbound assertion. It "
            "cannot admit itself, and nothing in BR-2A can admit it.",
        ),
    ):
        if name in cls.__dict__:
            raise TypeError(
                f"{cls.__name__} already declares {name!r}; the envelope "
                "derivations are never fields and never overridable"
            )
        _install_false_property(cls, name, doc)
    return cls
