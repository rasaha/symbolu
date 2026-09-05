"""Neutral assurance-finding label — *what did the exercise find?* (AE-3, AE-5).

Lands the vocabulary half of wave 4's agent security and assurance row
(``docs/architecture/ADR_UGENCE_AGENT_ASSURANCE_EVIDENCE_SCOPING.md``, decisions
AE-3 and AE-5) here rather than in the package that first consumes it, for the
reason ``AssessedSystemBinding``, ``DataClassificationLabel`` and ``VendorRiskLabel``
live here: every engine that carries what an exercise found should carry the *same*
type, not a parallel spelling per package.

**Not a verification status, by ruling.** AE-3 rules that
:class:`~ugence_governance_contracts.contracts.evidence.VerificationStatus` remains an
independent statement about whether a claim was *checked* and must not represent
what an exercise *found*. So this is a distinct class, not an alias of that enum
and not an alias of the other two labels; none is interchangeable with it.

This module defines **contracts and structural invariants only**. It is not a
scorer, a severity, a taxonomy, a verifier, a probe or an authority. It grants no
permission, verifies nothing, interprets no risk and mints no authority: an
:class:`AssuranceFindingLabel` says what a declarer *called* what an exercise
found, and nothing about whether the finding is true, how bad it is, or what may
be done about it.

Uninterpreted, by ruling
------------------------
AE-3 rules the label **uninterpreted**: a non-empty opaque value with **no
taxonomy, severity, score, ordering or implied verification**. Concretely:

* there is no member set — any non-blank text is a label, and none is more
  recognized than another;
* two labels are either the same text or different; there is no ``<``, no
  ``severity``, no ``is_verified``, no ``score`` and no ``rank``. The dataclass is
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
The provider dataclasses are **unchanged**. A consumer carries an
:class:`AssuranceFindingLabel` *alongside* an evidence reference or a record; no
existing field, default, constructor signature or serialized form moves, so
``CONTRACT_VERSION`` stays ``1.0.0``.
"""

from __future__ import annotations

import dataclasses
import enum
import hashlib
import json
from dataclasses import dataclass

__all__ = [
    "AssuranceFindingContractError",
    "AssuranceFindingLabel",
]


class AssuranceFindingContractError(ValueError):
    """A structurally invalid label. Always a refusal, never a warning."""


# --------------------------------------------------------------------------- #
# Small validation helpers (stdlib-only; module-local, mirroring vendor_risk.py)
# --------------------------------------------------------------------------- #
def _require_label_text(value: object, name: str) -> str:
    # A ``str``-valued Enum member (``VerificationStatus.VERIFIED`` is one) passes an
    # ``isinstance(str)`` check and would silently become a label carrying the
    # enum's value — the exact bridge AE-3 forbids. Refuse enum members first.
    if isinstance(value, enum.Enum) or not isinstance(value, str):
        raise AssuranceFindingContractError(
            f"{name} must be a string, never an Enum member (got {type(value).__name__})")
    text = value.strip()
    if not text:
        raise AssuranceFindingContractError(f"{name} must be a non-empty string")
    if any(ch.isspace() and ch not in " \t" for ch in text) or any(
            ord(ch) < 0x20 or ord(ch) == 0x7F for ch in text):
        raise AssuranceFindingContractError(
            f"{name} must not contain control characters or line breaks")
    return text


def _canonical_bytes(obj) -> bytes:
    payload = dataclasses.asdict(obj)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return encoded.encode("utf-8")


# --------------------------------------------------------------------------- #
@dataclass(frozen=True, order=False)
class AssuranceFindingLabel:
    """An immutable, non-empty, uninterpreted assurance-finding label.

    ``label`` is the text a declarer used — stored stripped, otherwise verbatim.
    Equality is exact text equality and nothing else: no case folding, no
    taxonomy lookup, no ordering, no severity, no score. The dataclass is frozen, so no
    post-construction mutation can alter the text or the digest.

    It answers *what was this finding called*, never *is it true* or *how bad is it*.
    """

    label: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "label", _require_label_text(self.label, "AssuranceFindingLabel.label"))

    # ------------------------------------------------------------------ #
    def canonical_bytes(self) -> bytes:
        """Deterministic canonical JSON bytes over the stripped label."""

        return _canonical_bytes(self)

    def canonical_digest(self) -> str:
        """Deterministic sha-256 over :meth:`canonical_bytes`.

        Equal labels share one digest; any different text changes it. The digest
        is a handle for binding a label into a larger record, not a measure of
        severity or truth.
        """

        return hashlib.sha256(self.canonical_bytes()).hexdigest()
