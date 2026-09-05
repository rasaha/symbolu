"""Neutral data-classification label — *what did the declarer call this data?* (DE-5).

Lands the vocabulary half of wave 4's data privacy and egress row
(``docs/architecture/ADR_UGENCE_DATA_EGRESS_AUTHORITY_SCOPING.md``, decision DE-5)
here rather than in the package that first consumes it, for the same reason
``AssessedSystemBinding`` lives here (UVI ADR §20): every engine that carries a
classification label should carry the *same* type, not a parallel spelling per
package. Three consumers are foreseeable — the data-use admission slice,
ActionGate's ``allowed_region`` constraint and Model Selection's residency gate —
and a label they cannot share would be no vocabulary at all.

This module defines **contracts and structural invariants only**. It is not a
classifier, a taxonomy, a policy, a comparator or an authority. It grants no
permission and mints no authority: a :class:`DataClassificationLabel` says what
a declarer *called* some data, and nothing about what that name means, whether it
was correct, or what may be done with data so labelled.

Uninterpreted, by ruling
------------------------
DE-3 rules the label **uninterpreted**, following AI System Registry D-2
(``ADR_UGENCE_AI_SYSTEM_REGISTRY_SCOPING.md:43``): a non-empty opaque value with
**no enum, taxonomy, lattice, hierarchy, severity, ordering, dominance or implied
compatibility**. Concretely:

* there is no member set — any non-blank text is a label, and none is more
  recognized than another;
* two labels are either the same text or different; there is no ``<``, no
  ``dominates``, no ``is_compatible_with`` and no ``rank``. The dataclass is
  declared with ``order=False`` and defines no rich comparison of its own, so
  ``sorted()`` over labels raises rather than inventing an order;
* nothing here reads, normalizes, lower-cases or otherwise reinterprets the
  text beyond stripping surrounding whitespace, so two declarations that differ
  in case are two different labels — the package cannot know they are "really"
  the same, and does not pretend to.

Structural validation, and only that
------------------------------------
A label must be a ``str``, non-empty after stripping, and free of control
characters (a newline or NUL inside a label would make its canonical form
ambiguous across serializers). That is the whole rule. A label that means
nothing to anyone is still a label.

Relation to the frozen provider contracts
-----------------------------------------
The provider dataclasses are **unchanged**. A consumer that adopts this contract
carries a :class:`DataClassificationLabel` *alongside* a request or a record; no
existing field, default, constructor signature or serialized form moves, so
``CONTRACT_VERSION`` stays ``1.0.0``.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass

__all__ = [
    "DataClassificationContractError",
    "DataClassificationLabel",
]


class DataClassificationContractError(ValueError):
    """A structurally invalid label. Always a refusal, never a warning."""


# --------------------------------------------------------------------------- #
# Small validation helpers (stdlib-only; module-local, mirroring audit.py)
# --------------------------------------------------------------------------- #
def _require_label_text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise DataClassificationContractError(
            f"{name} must be a string (got {type(value).__name__})")
    text = value.strip()
    if not text:
        raise DataClassificationContractError(f"{name} must be a non-empty string")
    if any(ch.isspace() and ch not in " \t" for ch in text) or any(
            ord(ch) < 0x20 or ord(ch) == 0x7F for ch in text):
        raise DataClassificationContractError(
            f"{name} must not contain control characters or line breaks")
    return text


def _canonical_bytes(obj) -> bytes:
    payload = dataclasses.asdict(obj)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return encoded.encode("utf-8")


# --------------------------------------------------------------------------- #
@dataclass(frozen=True, order=False)
class DataClassificationLabel:
    """An immutable, non-empty, uninterpreted classification label.

    ``label`` is the text a declarer used — stored stripped, otherwise verbatim.
    Equality is exact text equality and nothing else: no case folding, no
    taxonomy lookup, no ordering. The dataclass is frozen, so no
    post-construction mutation can alter the text or the digest.

    It answers *what was this data called*, never *what does that mean*.
    """

    label: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "label", _require_label_text(self.label, "DataClassificationLabel.label"))

    # ------------------------------------------------------------------ #
    def canonical_bytes(self) -> bytes:
        """Deterministic canonical JSON bytes over the stripped label."""

        return _canonical_bytes(self)

    def canonical_digest(self) -> str:
        """Deterministic sha-256 over :meth:`canonical_bytes`.

        Equal labels share one digest; any different text changes it. The digest
        is a handle for binding a label into a larger record, not a comparison
        of what two labels mean.
        """

        return hashlib.sha256(self.canonical_bytes()).hexdigest()
