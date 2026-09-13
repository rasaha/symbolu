"""The refusal-code register of rule section 10a — as data, with each code's effect.

Every outcome the rule names, in one place, so an implementation and a reviewer can
agree on what a refusal means. A code is *terminating* when the candidate ends on it,
*blocking* when the obligation stays open and the deadline machinery continues, and
*refusing* when one operation is rejected and the state is unchanged.

This package **raises** only the codes it can reach from a record's own shape; the
rest belong to boundaries that do not exist in Stage 1. They are listed here anyway,
because a register that omitted them would let two implementations invent different
names for the same refusal.
"""

from __future__ import annotations

from types import MappingProxyType

TERMINATING = "terminating"
BLOCKING = "blocking"
REFUSING = "refusing"
FAILS_CLOSED = "fails_closed"

#: code -> (effect, the condition that raises it)
REFUSAL_CODES: "MappingProxyType[str, tuple[str, str]]" = MappingProxyType({
    "CHAIN_ID_IN_USE": (REFUSING, "A second classification claims one chain identifier."),
    "OBLIGATION_ID_MISMATCH": (
        REFUSING, "A record's listed identifiers do not recompute from its chain identifier."),
    "OBLIGATION_UNKNOWN": (
        REFUSING, "An opening names an identifier its introducing record does not carry."),
    "AMENDMENT_SCOPE_REFUSED": (
        REFUSING, "The amendment tries to close anything but a CONFIRMATION_PENDING obligation."),
    "EVIDENCE_NOT_INDEPENDENT": (
        REFUSING, "An evaluation result is not signed by the independent evaluator."),
    "EVALUATION_RESULT_INCOMPLETE": (
        BLOCKING, "Raw evidence lacks a field the mapping requires. The closure does not seal "
                  "and the candidate does not end."),
    "BUNDLE_MAPPING_MISMATCH": (
        REFUSING, "A supplied bundle departs from the canonical derivation in any field."),
    "CLOSURE_NOT_EXPRESSIBLE": (
        TERMINATING, "The evaluation would write a frozen input, or the obligation kind cannot "
                     "close in chain."),
    "CLOSURE_EFFECT_CONFLICT": (
        TERMINATING, "Two bundles' write sets intersect, or a write is out of scope."),
    "CLOSURE_PIN_MISMATCH": (
        REFUSING, "A closure does not pin the opening and extension the ledger holds."),
    "COMPLETED_STATE_UNRESOLVED": (
        TERMINATING, "A condition survives the single recomputation, or the re-applied route "
                     "is provisional."),
    "EFFECTIVE_SET_NON_EMPTY": (
        REFUSING, "A resolution is attempted while an obligation is open."),
    "CHAIN_SEALED": (
        REFUSING, "Anything is appended behind a resolution or a terminating closure."),
    "INVESTIGATION_SEALED": (
        REFUSING, "An extension is appended behind its investigation's closure."),
    "CHAIN_FORK_REFUSED": (
        REFUSING, "A second successor is appended for one transition."),
    "SEED_AUTHORITY_INVALID": (
        REFUSING, "A supplemental seed comes from anyone but the classifier."),
    "POPULATION_MISMATCH": (
        REFUSING, "The materialised population does not match its pinned digest."),
    "SAMPLE_OVERLAP": (
        REFUSING, "A sample intersects the family, confirmation or an earlier supplemental "
                  "sample."),
    "SAMPLE_EXHAUSTED": (
        BLOCKING, "No disjoint sample of the ratified size remains. The obligation stays open; "
                  "the sampler never terminates a candidate."),
    "CROSS_TENANT_DELTA": (REFUSING, "A target set names more than one tenant."),
    "TARGET_SET_MISMATCH": (
        REFUSING, "The compare-and-apply's expectations and its delta name different targets."),
    "STALE_TARGET": (
        REFUSING, "A target's version moved between reservation and the compare-and-apply. "
                  "Completed FAILED; consumes the authorization."),
    "HEAD_MOVED": (
        REFUSING, "The chain head moved between the linearizable read and the reservation."),
    "CONTROL_VERSION_STALE": (
        REFUSING, "An APPLY or a revocation carries an expected control version the register "
                  "has passed."),
    "CONTROL_STATE_REFUSED": (
        REFUSING, "The control register's state forbids the transition, other than by "
                  "revocation."),
    "RESOLUTION_REVOKED": (REFUSING, "An operation meets a REVOKED register."),
    "RESOLUTION_ALREADY_APPLIED": (
        REFUSING, "A reservation is attempted against a resolution whose delta is applied."),
    "ADMISSION_IN_FLIGHT": (
        REFUSING, "A reservation is attempted while an APPLY claim is unresolved."),
    "COMPLETION_PENDING": (
        BLOCKING, "An impact record is attempted while an APPLY claim's completion is missing. "
                  "Recovery must run first."),
    "IMPACT_MISMATCH": (
        REFUSING, "A supplied impact record differs from the derived impact projection."),
    "READ_INELIGIBLE": (
        REFUSING, "The read port is asked for state whose resolution is revoked or never "
                  "applied."),
    "AUTHORITY_REFUSED": (
        REFUSING, "An actor attempts an operation the authority table denies it."),
    "APPEND_UNIQUENESS_UNAVAILABLE": (
        FAILS_CLOSED, "The audit root cannot supply a required linearizable register. No "
                      "reservation issues and no write reaches memory."),
    "CANONICAL_NULL_FORBIDDEN": (REFUSING, "A payload carries a null."),
    "CANONICAL_BOOLEAN_REFUSED": (
        REFUSING, "A payload carries a JSON boolean; a flag is an enumerated string."),
    "CANONICAL_NUMBER_REFUSED": (
        REFUSING, "A payload carries a float or an out-of-range integer."),
    "CANONICAL_TYPE_REFUSED": (REFUSING, "A payload carries an unencodable type."),
})

#: The codes this package itself can raise from a record's own shape. Everything else
#: in the register belongs to a Stage 2 or Stage 3 boundary.
CODES_RAISED_HERE: frozenset[str] = frozenset({
    "CANONICAL_NULL_FORBIDDEN",
    "CANONICAL_BOOLEAN_REFUSED",
    "CANONICAL_NUMBER_REFUSED",
    "CANONICAL_TYPE_REFUSED",
})
