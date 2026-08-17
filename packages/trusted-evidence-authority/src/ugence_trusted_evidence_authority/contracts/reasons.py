"""The typed trusted-evidence refusal vocabulary (ADR §11, E-9, DD-1).

ADR §11 ratifies that every evidence-admission failure condition is fail-closed
and carries a **stable, typed, namespace-scoped** reason code, and records the
exact vocabulary as **DD-1** — "implementation detail; §11 ratifies that codes
must be stable, typed and namespace-scoped, which is the boundary-relevant
part". DD-1 is therefore not an *unresolved* decision that TEV-1 must stop on;
it is a decision the ADR explicitly delegates to this milestone. This module
discharges it for the TEV-1 surface.

Every member is a **refusal**
-----------------------------
There is no success member, and none can be added without changing this type's
name and documentation. In particular ``TRUSTED_EVIDENCE_INDETERMINATE`` is a
refusal, not a pass — ADR §11: "*Indeterminate is a refusal, not a pass. A
verifier that cannot decide has not verified.*" Because the enum is *entirely*
refusals, "no reason code" is the only way to express "nothing was refused", and
that is deliberately **not** a positive verification state either (§10).

Namespace
---------
Every member is prefixed ``TRUSTED_EVIDENCE_``: neutral, capability-scoped, and
free of milestone branding. There are **no aliases and no deprecated spellings**
— ADR §22.11 requires a namespace that is "stable across versions, never reused
for a different meaning", which alias pairs immediately violate.

What is deliberately **absent** at TEV-1
----------------------------------------
The following ADR §11 conditions are real and ratified, but no TEV-1 contract
can reach them, so shipping a code for them now would advertise a check that
does not exist:

* ``PRODUCER_UNKNOWN`` / ``PRODUCER_UNAUTHORIZED`` (§11 row 4) — requires an
  authorized-producer trust boundary configured at the composition root (E-5).
  **TEV-2.**
* ``KEY_UNKNOWN`` / ``KEY_REVOKED`` / ``KEY_EXPIRED`` / ``KEY_NOT_YET_VALID``
  (§11 row 5) and ``SIGNATURE_INVALID`` (§11 row 6) — key management and
  cryptographic verification. **TEV-2.**
* ``UNIT_MISMATCH`` / ``METRIC_MISMATCH`` (§11 row 13) — a unit or metric is
  mismatched only *against a requirement*, and ADR §12 rules requirement
  sufficiency (stage 6) requirement-relative and never TAP's. It belongs to the
  consuming evaluation engine under a Policy Authority requirement (§18).

**No evidence-supersession code exists.** ADR §28's ratified *evidence*
lifecycle has no supersession arrow; supersession appears only in the
*benchmark* lifecycle (§29) and is itself deferred to DD-4. Inventing an
evidence-supersession reason would ratify a lifecycle the ADR does not have.
"""

from __future__ import annotations

from enum import Enum

__all__ = [
    "TrustedEvidenceRefusalReason",
    "TRUSTED_EVIDENCE_REFUSAL_REASONS",
]


class TrustedEvidenceRefusalReason(str, Enum):
    """Stable typed refusal codes for trusted-evidence admission (ADR §11).

    Declaration order is the **deterministic reason ordering** required by ADR
    §22.13: any routine that reports several refusals sorts them into this
    order, so a digest taken over a result set is stable. Members are grouped
    presence -> structure -> identity -> integrity -> scope -> provenance ->
    time -> lifecycle -> verification-unavailable, which is the order in which
    the ADR §16.2-style ordered checks would encounter them.
    """

    # -- presence ---------------------------------------------------------- #
    #: §11 row 1 — no evidence was supplied where evidence is required.
    TRUSTED_EVIDENCE_MISSING = "TRUSTED_EVIDENCE_MISSING"

    # -- structure --------------------------------------------------------- #
    #: §11 row 2 — the contract does not parse into a well-formed known shape.
    TRUSTED_EVIDENCE_MALFORMED_CONTRACT = "TRUSTED_EVIDENCE_MALFORMED_CONTRACT"
    #: §11 row 12 — the declared schema id/version is not one this stage admits.
    TRUSTED_EVIDENCE_SCHEMA_UNSUPPORTED = "TRUSTED_EVIDENCE_SCHEMA_UNSUPPORTED"
    #: §22.8 — the declared evidence type is not one this stage admits.
    TRUSTED_EVIDENCE_TYPE_UNSUPPORTED = "TRUSTED_EVIDENCE_TYPE_UNSUPPORTED"

    # -- identity ---------------------------------------------------------- #
    #: §9 — a required identity coordinate is absent or blank.
    TRUSTED_EVIDENCE_IDENTITY_COORDINATE_MISSING = (
        "TRUSTED_EVIDENCE_IDENTITY_COORDINATE_MISSING"
    )

    # -- integrity --------------------------------------------------------- #
    #: §11 row 3 — the declared content digest does not equal the expected one.
    TRUSTED_EVIDENCE_CONTENT_DIGEST_MISMATCH = (
        "TRUSTED_EVIDENCE_CONTENT_DIGEST_MISMATCH"
    )

    # -- scope (§7.1 row 5; replay/swap resistance, §26.5) ------------------ #
    #: §11 row 7 — the evidence binds a different tenant.
    TRUSTED_EVIDENCE_TENANT_MISMATCH = "TRUSTED_EVIDENCE_TENANT_MISMATCH"
    #: §11 row 8 — the evidence binds a different assessment context.
    TRUSTED_EVIDENCE_CONTEXT_MISMATCH = "TRUSTED_EVIDENCE_CONTEXT_MISMATCH"
    #: §11 row 9 — the evidence binds a different subject.
    TRUSTED_EVIDENCE_SUBJECT_MISMATCH = "TRUSTED_EVIDENCE_SUBJECT_MISMATCH"
    #: §11 row 9 — the evidence binds a different assessed-system binding.
    TRUSTED_EVIDENCE_SYSTEM_BINDING_MISMATCH = (
        "TRUSTED_EVIDENCE_SYSTEM_BINDING_MISMATCH"
    )
    #: §7.1 row 5 — the evidence binds a different declared purpose or usage
    #: scope than the one admission was requested for.
    TRUSTED_EVIDENCE_PURPOSE_SCOPE_MISMATCH = "TRUSTED_EVIDENCE_PURPOSE_SCOPE_MISMATCH"

    # -- provenance -------------------------------------------------------- #
    #: §11 row 11 — the declared chain of custody does not match, or is broken.
    TRUSTED_EVIDENCE_PROVENANCE_MISMATCH = "TRUSTED_EVIDENCE_PROVENANCE_MISMATCH"

    # -- time -------------------------------------------------------------- #
    #: §11 row 10 — the caller's instant precedes the validity interval.
    TRUSTED_EVIDENCE_NOT_YET_VALID = "TRUSTED_EVIDENCE_NOT_YET_VALID"
    #: §11 row 10 — the caller's instant is at or past the validity interval's
    #: exclusive end (half-open ``[valid_from, valid_to)``, ADR §17.9).
    TRUSTED_EVIDENCE_STALE = "TRUSTED_EVIDENCE_STALE"

    # -- lifecycle --------------------------------------------------------- #
    #: §11 row 15 — the evidence is revoked.
    TRUSTED_EVIDENCE_REVOKED = "TRUSTED_EVIDENCE_REVOKED"
    #: §28 — the proposed lifecycle transition is not a ratified arrow.
    TRUSTED_EVIDENCE_INVALID_LIFECYCLE_TRANSITION = (
        "TRUSTED_EVIDENCE_INVALID_LIFECYCLE_TRANSITION"
    )

    # -- verification unavailable (never a pass) ---------------------------- #
    #: §10 — a consumer required verification and none was performed. This is
    #: the code for the ordinary TEV-1 situation: contracts exist, no verifier
    #: does. Possession of a structurally valid contract is not verification.
    TRUSTED_EVIDENCE_VERIFICATION_NOT_PERFORMED = (
        "TRUSTED_EVIDENCE_VERIFICATION_NOT_PERFORMED"
    )
    #: §11 row 14 — a verifier was configured but timed out or errored.
    TRUSTED_EVIDENCE_VERIFIER_UNAVAILABLE = "TRUSTED_EVIDENCE_VERIFIER_UNAVAILABLE"
    #: §11 row 16 — the verifier could not decide. **A refusal, never a pass.**
    TRUSTED_EVIDENCE_INDETERMINATE = "TRUSTED_EVIDENCE_INDETERMINATE"


#: Every member of :class:`TrustedEvidenceRefusalReason`, as an immutable set.
#:
#: The equality ``TRUSTED_EVIDENCE_REFUSAL_REASONS == set(TrustedEvidenceRefusalReason)``
#: is asserted by the package tests. It is the structural statement that the
#: vocabulary contains **no success state**: there is nothing to add a member to
#: except the refusal set.
TRUSTED_EVIDENCE_REFUSAL_REASONS: frozenset = frozenset(TrustedEvidenceRefusalReason)
