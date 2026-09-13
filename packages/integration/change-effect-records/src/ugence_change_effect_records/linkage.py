"""Linkage-entry contracts into the control-plane audit root — Stage 1 item 3.4.

    THIS MODULE DECLARES WHAT AN APPEND WOULD LOOK LIKE. IT APPENDS NOTHING,
    INSTANTIATES NO LEDGER, CALLS NO LEDGER METHOD, AND WRAPS NONE.

**This is the only module in the package permitted to import
``ugence_control_plane_root``**, and a boundary test enforces that: no record,
identifier, canonicalization, vocabulary, admission-data or refusal module may reach
it. The reason is not tidiness. A record type that could see a ledger is a record type
someone will eventually ask to write itself, and the whole point of the record contracts
is that they cannot.

What is imported is the immutable entry contract type and nothing else. ``AuditLedger``
is deliberately **not** imported: importing the thing that appends, in a package that
must not append, would make the prohibition a matter of discipline rather than of
structure. The first append happens in Stage 2 under the CEC-3 record contract, from a
component that does not exist.

--------------------------------------------------------------------------------------
A warning that is load-bearing, not boilerplate
--------------------------------------------------------------------------------------

Declaring an entry kind for each record must not be read as a claim that the existing
audit ledger can host this record graph. **It has not been shown to.** The rule requires
three capabilities of its audit root, and none of them is verified to exist anywhere in
this repository:

* an **atomic conditional append**, unique over ``(chain_id, predecessor_digest,
  transition_kind)``, which is what makes a second successor for one transition a fork
  rather than a race;
* a **linearizable control register per resolution**, read and conditionally advanced by
  both an APPLY claim and a revocation, which is what makes a write after a committed
  revocation unreachable;
* a **linearizable target-version registry** per ``(tenant, target)`` of governed memory,
  against which the mutation is an all-or-nothing compare-and-apply.

``REQUIRED_AUDIT_ROOT_CAPABILITIES`` below states them as data, each with its declared
status. Every one is ``DECLARED_GAP``. Where a compliant facility is absent the Stage 3
boundary fails closed with ``APPEND_UNIQUENESS_UNAVAILABLE``: no reservation issues and
no write reaches governed memory. That refusal is a property of a boundary that does not
exist yet; this module can only name it.
"""

from __future__ import annotations

from types import MappingProxyType

# The immutable entry contract type, and only that. `AuditLedger` is not imported: this
# package must not append, and must not hold the means to.
from ugence_control_plane_root import LedgerEntry

from ._canon import require_nonempty
from .errors import ContractViolation

__all__ = [
    "LINKAGE_KIND_PREFIX",
    "LINKAGE_KINDS",
    "LINKAGE_PAYLOAD_SCHEMA",
    "TRANSITION_KINDS",
    "UNIQUENESS_CONSTRAINT",
    "REQUIRED_AUDIT_ROOT_CAPABILITIES",
    "CAPABILITY_UNAVAILABLE_REFUSAL",
    "entry_kind_for",
    "linkage_payload_keys",
]

#: Every kind this package would be appended under shares this prefix and carries the
#: record-shape contract version, so an entry written under one schema is never mistaken
#: for one written under another.
LINKAGE_KIND_PREFIX = "change_effect.record"

#: record type name -> ``LedgerEntry.kind``. Thirteen kinds for thirteen record types.
LINKAGE_KINDS: "MappingProxyType[str, str]" = MappingProxyType({
    "ClassificationRecord": f"{LINKAGE_KIND_PREFIX}.classification.v1",
    "ConfirmationAmendment": f"{LINKAGE_KIND_PREFIX}.confirmation_amendment.v1",
    "InvestigationRecord": f"{LINKAGE_KIND_PREFIX}.investigation_opening.v1",
    "InvestigationExtensionRecord": f"{LINKAGE_KIND_PREFIX}.investigation_extension.v1",
    "InvestigationClosureRecord": f"{LINKAGE_KIND_PREFIX}.investigation_closure.v1",
    "FinalResolutionRecord": f"{LINKAGE_KIND_PREFIX}.final_resolution.v1",
    "AuthorizationBinding": f"{LINKAGE_KIND_PREFIX}.authorization_binding.v1",
    "ResolutionRevocationRecord": f"{LINKAGE_KIND_PREFIX}.resolution_revocation.v1",
    "RevocationImpactRecord": f"{LINKAGE_KIND_PREFIX}.revocation_impact.v1",
    "AdmissionReservationRecord": f"{LINKAGE_KIND_PREFIX}.admission_reservation.v1",
    "AdmissionClaimRecord": f"{LINKAGE_KIND_PREFIX}.admission_claim.v1",
    "AdmissionCompletionRecord": f"{LINKAGE_KIND_PREFIX}.admission_completion.v1",
    "AdmissionResolutionRecord": f"{LINKAGE_KIND_PREFIX}.admission_resolution.v1",
})

#: The payload keys every linkage entry carries, whatever its kind. The payload is a
#: locator, never a copy: it names the record by digest so the entry can be found and the
#: record verified, and it does not restate the record's contents.
LINKAGE_PAYLOAD_SCHEMA: tuple[str, ...] = (
    "chain_id",
    "record_digest",
    "predecessor_digest",
    "transition_kind",
    "contract_version",
)

#: ``transition_kind`` values, which are what the uniqueness constraint is taken over.
#: An investigation opening's kind carries its ``obligation_id``, so one-opening-per-
#: obligation is the same constraint rather than a second mechanism; an admission
#: reservation's carries the authorization digest, so a fresh authorization reserves on
#: its own transition instead of colliding with a consumed one.
TRANSITION_KINDS: tuple[str, ...] = (
    "CHAIN_OPEN",
    "CONFIRMATION_AMENDMENT",
    "INVESTIGATION_OPEN:<obligation_id>",
    "INVESTIGATION_EXTEND:<obligation_id>",
    "INVESTIGATION_CLOSE:<obligation_id>",
    "FINAL_RESOLUTION",
    "RESOLUTION_REVOKE",
    "REVOCATION_IMPACT",
    "ADMISSION_RESERVE:<authorization_digest>",
    "ADMISSION_CLAIM",
    "ADMISSION_COMPLETE",
    "ADMISSION_RESOLVE",
)

#: The tuple an atomic conditional append must be unique over.
UNIQUENESS_CONSTRAINT: tuple[str, ...] = (
    "chain_id", "predecessor_digest", "transition_kind",
)

#: Status vocabulary for the capability declarations below. There is currently no other
#: value in use, which is the point.
_DECLARED_GAP = "DECLARED_GAP"

#: capability -> (status, what it must guarantee, why it cannot be assumed).
REQUIRED_AUDIT_ROOT_CAPABILITIES: "MappingProxyType[str, tuple[str, str, str]]" = (
    MappingProxyType({
        "ATOMIC_CONDITIONAL_APPEND": (
            _DECLARED_GAP,
            "An append that succeeds for at most one writer under a uniqueness "
            "constraint over (chain_id, predecessor_digest, transition_kind).",
            "A refusal code does not create uniqueness. No component in this repository "
            "is verified to offer a conditional append, and an append that merely "
            "succeeds is not one.",
        ),
        "LINEARIZABLE_CHAIN_HEAD": (
            _DECLARED_GAP,
            "An authoritative, linearizable chain-head read returning an opaque "
            "concurrency token the conditional append consumes.",
            "A ledger scan, an advisory index and an eventually consistent replica "
            "cannot supply it, whatever they return.",
        ),
        "LINEARIZABLE_CONTROL_REGISTER": (
            _DECLARED_GAP,
            "One linearizable register per resolution, read and conditionally advanced "
            "by both an APPLY claim and a revocation.",
            "Without a single register shared by both, a revocation and an APPLY are in "
            "two concurrency domains and their order is not decided by anything.",
        ),
        "LINEARIZABLE_TARGET_VERSION_REGISTRY": (
            _DECLARED_GAP,
            "A version per (tenant, target) of governed memory, against which the "
            "mutation is an all-or-nothing compare-and-apply over the target set.",
            "Serialising concurrent writes prevents corruption but does not make the "
            "second authorization valid; only a version comparison does.",
        ),
    })
)

#: What a Stage 3 boundary returns where a required capability is absent, unverified or
#: degraded. It fails closed: no reservation issues and no write reaches memory.
CAPABILITY_UNAVAILABLE_REFUSAL = "APPEND_UNIQUENESS_UNAVAILABLE"


def entry_kind_for(record_type_name: str) -> str:
    """The ``LedgerEntry.kind`` a record of this type would be appended under.

    A lookup in a frozen mapping. It builds no entry, appends nothing, and takes a type
    *name* rather than a record, so it cannot be handed a record and mistaken for a
    writer.
    """

    name = require_nonempty(record_type_name, "record_type_name")
    try:
        return LINKAGE_KINDS[name]
    except KeyError:
        raise ContractViolation(
            f"no linkage kind is declared for '{name}'; the thirteen record types are "
            f"{', '.join(sorted(LINKAGE_KINDS))}"
        ) from None


def linkage_payload_keys() -> tuple[str, ...]:
    """The payload keys a linkage entry carries. Data, returned as data."""

    return LINKAGE_PAYLOAD_SCHEMA


#: The entry contract this package's kinds would be appended as. Bound here so the
#: declaration is checkable — a kind declared for a type the ledger does not accept is a
#: declaration about nothing — and never instantiated.
LINKAGE_ENTRY_CONTRACT = LedgerEntry
