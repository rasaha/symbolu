"""Neutral vendor-risk label — *what posture did the declarer assign this vendor?* (VR-3, VR-5).

Lands the vocabulary half of wave 4's third-party AI and vendor risk row
(``docs/architecture/ADR_UGENCE_VENDOR_RISK_SCOPING.md``, decisions VR-3 and
VR-5) here rather than in the package that first consumes it, for the reason
``AssessedSystemBinding`` and ``DataClassificationLabel`` live here: every engine
that carries a vendor-risk posture should carry the *same* type, not a parallel
spelling per package.

**A separate type, by ruling.** VR-3 rules that data classification and vendor-risk
posture are different dimensions: a dataset's sensitivity and a supplier's risk
standing are not the same axis, and a consumer that could pass one where the other
is expected would silently conflate them. So this is a distinct class, not an
alias of :class:`~ugence_governance_contracts.contracts.data_classification.DataClassificationLabel`,
and the two are deliberately not interchangeable.

This module defines **contracts and structural invariants only**. It is not a
scorer, a grade, a taxonomy, a policy, a comparator or an authority. It grants no
permission, makes no risk judgment and mints no authority: a :class:`VendorRiskLabel`
says what posture a declarer *assigned*, and nothing about whether that posture is
apt, what it means, or what may be done with a vendor so labelled.

Uninterpreted, by ruling
------------------------
VR-3 rules the label **uninterpreted**: a non-empty opaque value with **no grade,
enum, taxonomy, ordering, severity, score, dominance or implied eligibility**.
Concretely:

* there is no member set — any non-blank text is a label, and none is more
  recognized than another;
* two labels are either the same text or different; there is no ``<``, no
  ``dominates``, no ``is_eligible``, no ``score`` and no ``rank``. The dataclass is
  declared with ``order=False`` and defines no rich comparison of its own, so
  ``sorted()`` over labels raises rather than inventing an order;
* nothing here reads, normalizes, lower-cases or otherwise reinterprets the text
  beyond stripping surrounding whitespace.

Structural validation, and only that
------------------------------------
A label must be a ``str``, non-empty after stripping, and free of control
characters (a newline or NUL inside a label would make its canonical form
ambiguous across serializers). That is the whole rule.

Relation to the frozen provider contracts
-----------------------------------------
The provider dataclasses are **unchanged**. A consumer carries a
:class:`VendorRiskLabel` *alongside* a request or a record; no existing field,
default, constructor signature or serialized form moves, so ``CONTRACT_VERSION``
stays ``1.0.0``.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass

__all__ = [
    "VendorRiskContractError",
    "VendorRiskLabel",
]


class VendorRiskContractError(ValueError):
    """A structurally invalid label. Always a refusal, never a warning."""


# --------------------------------------------------------------------------- #
# Small validation helpers (stdlib-only; module-local, mirroring data_classification.py)
# --------------------------------------------------------------------------- #
def _require_label_text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise VendorRiskContractError(
            f"{name} must be a string (got {type(value).__name__})")
    text = value.strip()
    if not text:
        raise VendorRiskContractError(f"{name} must be a non-empty string")
    if any(ch.isspace() and ch not in " \t" for ch in text) or any(
            ord(ch) < 0x20 or ord(ch) == 0x7F for ch in text):
        raise VendorRiskContractError(
            f"{name} must not contain control characters or line breaks")
    return text


def _canonical_bytes(obj) -> bytes:
    payload = dataclasses.asdict(obj)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return encoded.encode("utf-8")


# --------------------------------------------------------------------------- #
@dataclass(frozen=True, order=False)
class VendorRiskLabel:
    """An immutable, non-empty, uninterpreted vendor-risk posture label.

    ``label`` is the text a declarer used — stored stripped, otherwise verbatim.
    Equality is exact text equality and nothing else: no case folding, no
    taxonomy lookup, no ordering, no score. The dataclass is frozen, so no
    post-construction mutation can alter the text or the digest.

    It answers *what posture was this vendor assigned*, never *how risky is it*.
    """

    label: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "label", _require_label_text(self.label, "VendorRiskLabel.label"))

    # ------------------------------------------------------------------ #
    def canonical_bytes(self) -> bytes:
        """Deterministic canonical JSON bytes over the stripped label."""

        return _canonical_bytes(self)

    def canonical_digest(self) -> str:
        """Deterministic sha-256 over :meth:`canonical_bytes`.

        Equal labels share one digest; any different text changes it. The digest
        is a handle for binding a label into a larger record, not a measure of
        risk.
        """

        return hashlib.sha256(self.canonical_bytes()).hexdigest()
