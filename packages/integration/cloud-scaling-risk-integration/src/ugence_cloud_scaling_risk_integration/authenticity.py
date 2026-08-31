"""The Cloud Scaling recommendation authenticity boundary (ADR §7, Phase 4C).

Read this before relying on any guarantee in this package.

What Phase 4A/4B established
----------------------------
``validate_subject_binding`` proves *internal canonical consistency* of a v2 request: the
carried ``subject_digest`` reconciles with a binding reconstructed from authoritative
outer fields over a re-validated context. It detects **inconsistent or partial
tampering** — an altered field left paired with a stale digest. It does **not** detect a
*fully self-consistent fabricated request*, because a caller who recomputes every digest
produces an internally consistent object by construction. Phase 4A/4B therefore establish
integrity, never source authenticity.

What Phase 4C establishes here
------------------------------
This module establishes the *Cloud Scaling recommendation boundary* that Phase 4A/4B
deliberately left open. For a serialized recommendation it:

1. accepts **only** the **exact** canonical controller type or its canonical serialized
   form — a duck-typed look-alike *and a subclass* are both refused at the type
   boundary, before anything on the object is invoked (see "Exact-type admission");
2. reconstructs the serialized form through the controller's own strict
   ``CapacityActionRecommendation.from_dict``, which rejects unknown and missing fields
   and re-runs the full ``__post_init__`` revalidation (digest rebinding, candidate-set
   equality, score/feasibility/cost recomputation, temporal safety);
3. **independently recomputes** ``rec.digest()`` from that reconstruction;
4. compares the recomputation with the **independently carried** ``evidence_digest``
   from the input document.

Step 4 is genuinely independent, and this is the load-bearing fact: the controller's
``from_dict`` accepts ``evidence_digest`` as a known field but **never validates it and
never passes it to the constructor** — it is discarded. The recomputed value is therefore
derived purely from the record's *content*, while the compared value comes purely from
the *input document*. A payload whose content was altered while ``evidence_digest`` was
left stale reconstructs successfully and then fails here. This is not the forbidden
self-referential check (``rec.digest() == rec.digest()``), which would prove nothing.

Exact-type admission
--------------------
Admission is by ``type(source) is CapacityActionRecommendation``, **not** by
``isinstance``. This is load-bearing rather than pedantic: every value the adapter would
go on to read — ``digest()``, ``to_canonical_dict()``, ``_digest_payload()``, the
embedded objects' own serializers — is reached through dynamic dispatch, so a subclass
overriding any one of them controls what gets "recomputed". A subclass overriding
``digest()`` to return an attacker-chosen value would have its value adopted as the
authenticated ``recommendation_digest``.

Calling the base method unbound (``CapacityActionRecommendation.digest(source)``) does
**not** fix this: that method still calls ``self.to_canonical_dict()`` and
``self._digest_payload()``, so an override further down the chain is reached anyway.
Exact-type admission is the only correction that holds, and it runs **before any
attribute of ``source`` is touched** — only ``type()`` and ``isinstance()`` are consulted.

A caller holding a legitimate subclass is not locked out: serializing it and submitting
the canonical document reconstructs an exact base instance whose digest is recomputed
from content.

The authenticated token's own integrity invariant
------------------------------------------------
:class:`AuthenticatedRecommendation` is the *token* every downstream consumer trusts: a
caller holding one is entitled to assume its ``recommendation_digest`` is the digest of
its ``recommendation``. Nothing but this module establishes that, so the invariant is
enforced here rather than assumed:

    ``token.recommendation_digest == token.recommendation.digest()``

It is checked in ``__post_init__`` so no *supported* construction can produce a
mismatched token, and **re-checked at every consumption boundary** so an *unsupported*
one cannot be consumed either. The second check is the load-bearing one: a frozen
dataclass is not a security boundary. ``object.__new__`` skips ``__post_init__`` entirely,
``object.__setattr__`` rewrites a frozen field afterwards, and a subclass can replace
``recommendation`` with a property that returns a different object on each access.
Consumers therefore require the **exact** ``AuthenticatedRecommendation`` type — not
``isinstance`` — and recompute the digest from the embedded record before using it.

Requiring the exact embedded ``CapacityActionRecommendation`` type *before* invoking
``digest()`` is what makes that recomputation trustworthy: it is the same exact-type
discipline described above, applied to the token's contents, and it removes the
subclass-dispatch risk that would otherwise let the recomputation be chosen by the
attacker.

**This is content-integrity, not signed producer authenticity.** It proves the token's
digest describes the token's content. It does not prove who authored that content — see
"What Phase 4C still does NOT prove" below, which this correction does not narrow.

The in-process object path
--------------------------
A live :class:`CapacityActionRecommendation` carries no digest field of its own —
``evidence_digest`` is excluded from the dataclass and computed on demand. An in-process
object has also, by construction, already passed ``__post_init__``, so recomputing its
own digest is exactly the self-referential check that proves nothing. On that path the
caller **must** therefore supply ``expected_recommendation_digest``: an independently
carried expectation (from a decision log, an audit record, or the transport that
delivered the recommendation). Absent it, this module raises
:class:`~.errors.MissingIndependentDigestError` rather than proceeding — it will not
claim an authenticity it cannot establish.

What Phase 4C still does NOT prove
----------------------------------
* **Not a signature.** The controller digest is a canonical content *identity*, computed
  with an unkeyed SHA-256 over a domain-separated preimage. It proves that the content
  hashes to the expected value; it proves nothing about **who** produced it.
* **The expectation's own provenance is assumed, not verified.** On the object path the
  adapter cannot verify where ``expected_recommendation_digest`` came from. A caller that
  computes it from the same object it passes in has performed the self-referential check
  itself; the adapter has no way to detect that.
* **A fully self-consistent forgery still passes.** An attacker able to author a complete,
  internally valid ``CapacityActionRecommendation`` — one whose forecast evidence, cost
  book, topology, constraints, policy and candidate set all recompute consistently — and
  to serialize it with a matching ``evidence_digest`` produces an authentic-looking input.
  Detecting *that* requires a signed provenance chain over the controller's output, which
  does not exist anywhere in the repository today and which Phase 4C does not invent.
* **Evidence provenance is out of scope.** The evidence references projected onto the
  outer request are opaque digest strings. Whether they resolve to admitted, trusted,
  fresh evidence is RA-5's question, answered behind the seam.

**The remaining upstream trust assumption, stated plainly:** Phase 4C trusts that the
canonical recommendation document (or the independently carried digest expectation)
reached the adapter over a channel the composition root trusts. Establishing *that* is a
transport/provenance concern and remains unaddressed. No placeholder authenticator is
added here, because a placeholder would read as a control while providing none.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Final, Mapping, Optional, Union

from ugence_cloud_scaling_controller.planning.recommendation import (
    RECOMMENDATION_ABSTENTION_SCHEMA_VERSION,
    RECOMMENDATION_SCHEMA_VERSION,
    CapacityActionRecommendation,
    RecommendationAbstention,
    RecommendationError,
)

from .errors import (
    MissingIndependentDigestError,
    RecommendationAuthenticityError,
    RecommendationInputError,
    UnsupportedRecommendationSourceError,
)

__all__ = [
    "CARRIED_DIGEST_FIELD",
    "AuthenticatedRecommendation",
    "AuthenticatedAbstention",
    "DigestExpectationSource",
    "authenticate_controller_output",
]

#: The field name under which the controller's canonical serialized form carries the
#: recommendation's own digest. ``from_dict`` accepts but never validates it, which is
#: precisely what makes it usable as an independent expectation here.
CARRIED_DIGEST_FIELD: Final[str] = "evidence_digest"

_DIGEST_RE: Final[re.Pattern[str]] = re.compile(r"^sha256:[0-9a-f]{64}$")

_ControllerOutput = Union[
    CapacityActionRecommendation, RecommendationAbstention, Mapping[str, Any]
]


class DigestExpectationSource:
    """Where the independent digest expectation that was checked came from.

    A namespace of canonical strings recorded on the authenticated result purely for
    auditability — it carries no authority and selects no behavior.
    """

    #: Carried inside the canonical serialized document, ignored by ``from_dict``.
    CARRIED_CANONICAL_FORM: Final[str] = "carried_canonical_form"
    #: Supplied by the caller as an independently obtained expectation.
    CALLER_SUPPLIED_EXPECTATION: Final[str] = "caller_supplied_expectation"
    #: Both were present and both matched the recomputation.
    CARRIED_AND_CALLER_SUPPLIED: Final[str] = "carried_and_caller_supplied"

    ALL: Final[frozenset[str]] = frozenset(
        {
            "carried_canonical_form",
            "caller_supplied_expectation",
            "carried_and_caller_supplied",
        }
    )


@dataclass(frozen=True)
class AuthenticatedRecommendation:
    """A reconstructed recommendation whose digest reconciled with an independent value.

    An **integrity-and-source finding, not a grant**. Reaching it means the content
    hashes to an independently carried expectation; it grants nothing, evaluates nothing
    and authorizes nothing. Every authority flag is fixed ``False`` at construction.
    """

    recommendation: CapacityActionRecommendation
    recommendation_digest: str
    expectation_source: str
    # Fixed non-authority invariants — authenticating an input is not an evaluation.
    risk_evaluated: bool = False
    authority_granted: bool = False
    envelope_issued: bool = False
    actiongate_invoked: bool = False
    credential_issued: bool = False
    actuation_performed: bool = False
    effect_verified: bool = False
    executable: bool = False

    def __post_init__(self) -> None:
        # The single authoritative routine, run on the supported construction path so a
        # mismatched token cannot be minted by hand. It is deliberately the *same*
        # routine every consumer re-runs: one definition of "valid token", not two that
        # could drift apart. See ``_validate_authenticated_recommendation``.
        _validate_authenticated_recommendation(self)


@dataclass(frozen=True)
class AuthenticatedAbstention:
    """A reconstructed controller abstention — a typed **non**-recommendation.

    It never becomes a scaling recommendation, never enters the Risk Authority
    evaluation seam and never manufactures a subject digest. It exists so the adapter can
    report the upstream non-evaluation faithfully, carrying the controller's own typed
    reason and whatever input digests the controller had bound before abstaining.
    """

    abstention: RecommendationAbstention
    abstention_digest: Optional[str] = None
    expectation_source: Optional[str] = None
    risk_evaluated: bool = False
    authority_granted: bool = False
    envelope_issued: bool = False
    actiongate_invoked: bool = False
    credential_issued: bool = False
    actuation_performed: bool = False
    effect_verified: bool = False
    executable: bool = False

    def __post_init__(self) -> None:
        _validate_authenticated_abstention(self)


_AUTHORITY_FLAGS = (
    "risk_evaluated",
    "authority_granted",
    "envelope_issued",
    "actiongate_invoked",
    "credential_issued",
    "actuation_performed",
    "effect_verified",
    "executable",
)


def _assert_no_authority_fields(record: Any, kind: str) -> None:
    """Every non-authority flag must still be exactly ``False``.

    Re-read from the token rather than trusted from construction: the flags have no
    setter, but ``object.__setattr__`` does not need one, and a forged ``True`` is
    **rejected** rather than normalized — normalizing would launder the very claim the
    invariant exists to refuse.
    """

    for flag in _AUTHORITY_FLAGS:
        if _token_field(record, flag, kind) is not False:
            raise RecommendationAuthenticityError(
                f"{flag} must be False — authenticating an input grants no authority"
            )


def _require_digest_syntax(name: str, value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, str):
        raise RecommendationAuthenticityError(f"{name} must be a string")
    if not _DIGEST_RE.match(value):
        raise RecommendationAuthenticityError(
            f"{name} must be a canonical digest ('sha256:' + 64 lowercase hex)"
        )
    return value


#: Sentinel for "the attribute is absent", distinct from an attribute whose value is
#: ``None``. A fabricated token built with ``object.__new__`` has no fields at all, and
#: an ``AttributeError`` escaping a validation routine would be an *uncontrolled* failure
#: where the contract promises a controlled, typed, fail-closed one.
_MISSING: Final[object] = object()


def _token_field(token: Any, name: str, kind: str) -> Any:
    """Read one field of a possibly-fabricated token without ever raising ``AttributeError``.

    Only reached after the token's **exact** type has been established, so the read
    cannot be intercepted by a subclass property; this guards against the token having
    been constructed through ``object.__new__`` (which runs neither ``__init__`` nor
    ``__post_init__`` and therefore leaves the instance with no fields set at all).
    """

    value = getattr(token, name, _MISSING)
    if value is _MISSING:
        raise RecommendationAuthenticityError(
            f"{kind} is missing its required {name!r} field; it was not produced by a "
            "supported constructor (fail closed, nothing consumed)"
        )
    return value


def _require_exact_token(token: Any, expected: type, kind: str) -> None:
    """Require the **exact** token type, before any attribute of it is read.

    ``isinstance`` is deliberately not the rule. A subclass of the token can replace any
    field with a property, so the value validated and the value later consumed need not
    be the same object; it can also define its own ``__init__`` and never reach
    ``__post_init__``. Requiring the exact type removes both possibilities outright, and
    is checked here **before** anything on ``token`` is read, so only ``type()`` is
    consulted on an untrusted object.
    """

    if type(token) is not expected:
        raise UnsupportedRecommendationSourceError(
            f"{kind} must be exactly a {expected.__name__}, not "
            f"{type(token).__name__}: a subclass may override any field with a property "
            "or bypass __post_init__ entirely, so its invariants cannot be relied upon"
        )


def _validate_authenticated_recommendation(
    token: Any,
) -> tuple[CapacityActionRecommendation, str]:
    """The authoritative validity check for an :class:`AuthenticatedRecommendation`.

    Run at construction *and* re-run at every consumption boundary, because a frozen
    dataclass is not a security boundary: ``object.__new__`` skips ``__post_init__``,
    ``object.__setattr__`` rewrites a frozen field after the fact, and a subclass can
    make any field a property. Nothing but re-checking catches those.

    It establishes, in order and refusing to touch anything it has not yet typed:

    1. the **exact** ``AuthenticatedRecommendation`` token type;
    2. that every non-authority flag is still ``False``;
    3. the **exact** embedded ``CapacityActionRecommendation`` type;
    4. that ``recommendation_digest`` is syntactically canonical;
    5. that it **equals the digest recomputed from the embedded recommendation**.

    Step 3 is what makes step 5 meaningful: with the exact base type established, the
    ``digest()`` call cannot be redirected by subclass dispatch, so the recomputation is
    derived from canonical content rather than chosen by whoever built the token.

    :returns: the validated ``(recommendation, digest)`` pair. Consumers should use the
        returned values rather than re-reading the token, so there is no window between
        the check and the use.
    :raises UnsupportedRecommendationSourceError: wrong exact token or recommendation type.
    :raises RecommendationAuthenticityError: missing field, malformed digest, a forged
        authority flag, or a digest that does not describe the carried content.
    """

    _require_exact_token(token, AuthenticatedRecommendation, "an authenticated recommendation")
    _assert_no_authority_fields(token, "an authenticated recommendation")

    recommendation = _token_field(token, "recommendation", "an authenticated recommendation")
    if type(recommendation) is not CapacityActionRecommendation:
        raise UnsupportedRecommendationSourceError(
            "recommendation must be exactly a CapacityActionRecommendation, not a "
            f"subclass ({type(recommendation).__name__}): every value the projection "
            "reads is reached by dynamic dispatch, so a subclass would choose its own "
            "'recomputed' digest"
        )

    digest = _require_digest_syntax(
        "recommendation_digest",
        _token_field(token, "recommendation_digest", "an authenticated recommendation"),
    )
    # The invariant itself. Recomputed from the exact canonical record, then compared —
    # a syntactically valid but incorrect digest fails exactly here.
    recomputed = _recompute(recommendation, "recommendation")
    if digest != recomputed:
        raise RecommendationAuthenticityError(
            "authenticated recommendation digest does not describe its recommendation: "
            f"the token carries {digest} but the embedded recommendation hashes to "
            f"{recomputed}. The token was not produced by a supported constructor, or "
            "was mutated after construction (fail closed: nothing is projected, no "
            "request is built and the evaluation seam is not reached)"
        )
    return recommendation, digest


def _validate_authenticated_abstention(token: Any) -> RecommendationAbstention:
    """The authoritative validity check for an :class:`AuthenticatedAbstention`.

    The symmetric counterpart of :func:`_validate_authenticated_recommendation`, with the
    same exact-type and fabrication defences. No digest semantics are invented for
    abstentions: ``abstention_digest`` stays optional exactly as before. What is enforced
    is that a digest which *is* present actually describes the carried abstention — the
    same content-integrity property, applied to the field that already claims it.
    """

    _require_exact_token(token, AuthenticatedAbstention, "an authenticated abstention")
    _assert_no_authority_fields(token, "an authenticated abstention")

    abstention = _token_field(token, "abstention", "an authenticated abstention")
    if type(abstention) is not RecommendationAbstention:
        raise UnsupportedRecommendationSourceError(
            "abstention must be exactly a RecommendationAbstention, not a subclass "
            f"({type(abstention).__name__})"
        )

    carried = _token_field(token, "abstention_digest", "an authenticated abstention")
    if carried is not None:
        digest = _require_digest_syntax("abstention_digest", carried)
        recomputed = _recompute(abstention, "abstention")
        if digest != recomputed:
            raise RecommendationAuthenticityError(
                "authenticated abstention digest does not describe its abstention: the "
                f"token carries {digest} but the embedded abstention hashes to "
                f"{recomputed} (fail closed, nothing consumed)"
            )
    return abstention


def _validate_authenticated_output(token: Any) -> None:
    """Re-validate either authenticated token at a consumption boundary.

    Dispatches on **exact** type so an object that is neither token — including one
    subclassing either — is refused rather than silently taking a branch.
    """

    token_type = type(token)
    if token_type is AuthenticatedRecommendation:
        _validate_authenticated_recommendation(token)
    elif token_type is AuthenticatedAbstention:
        _validate_authenticated_abstention(token)
    else:
        raise UnsupportedRecommendationSourceError(
            "expected exactly an AuthenticatedRecommendation or an "
            f"AuthenticatedAbstention; got {token_type.__name__}"
        )


def _recompute(record: Any, artifact: str) -> str:
    """Recompute a canonical controller digest, converting any failure into a typed one.

    The record's exact canonical type has already been established, so this cannot reach
    overridden code — but a record fabricated field-by-field can still be internally
    incoherent enough that the controller's own digest machinery raises. That must
    surface as a controlled fail-closed rejection, never as an arbitrary exception
    escaping a validation routine.
    """

    try:
        value = record.digest()
    except Exception as exc:  # noqa: BLE001 - any failure here is a rejected token
        raise RecommendationAuthenticityError(
            f"the embedded {artifact} could not be canonically digested, so its "
            f"authenticated digest cannot be verified: {exc}"
        ) from exc
    return _require_digest_syntax(f"recomputed {artifact} digest", value)


def _reconcile(
    recomputed: str,
    *,
    carried: Optional[str],
    expected: Optional[str],
    artifact: str,
) -> str:
    """Require the recomputation to equal every independent expectation supplied.

    At least one independent expectation is mandatory: with none, there is nothing to
    compare against but the object itself, and asserting authenticity from that would be
    the self-referential check this module exists to avoid.
    """

    expectations: list[tuple[str, str]] = []
    if carried is not None:
        expectations.append(
            (DigestExpectationSource.CARRIED_CANONICAL_FORM, _require_digest_syntax(
                f"carried {artifact} digest", carried))
        )
    if expected is not None:
        expectations.append(
            (DigestExpectationSource.CALLER_SUPPLIED_EXPECTATION, _require_digest_syntax(
                f"expected {artifact} digest", expected))
        )
    if not expectations:
        raise MissingIndependentDigestError(
            f"no independent {artifact} digest is available to check: the canonical "
            f"serialized form carried no {CARRIED_DIGEST_FIELD!r} and no "
            "expected_recommendation_digest was supplied. Recomputing the object's own "
            "digest and comparing it to itself would prove nothing, so this fails closed."
        )
    for source, value in expectations:
        if value != recomputed:
            raise RecommendationAuthenticityError(
                f"{artifact} digest mismatch: recomputed {recomputed} but the "
                f"{source} expectation is {value} (fail closed, no request constructed, "
                "no evaluation performed)"
            )
    if len(expectations) == 2:
        return DigestExpectationSource.CARRIED_AND_CALLER_SUPPLIED
    return expectations[0][0]


_CONTROLLER_TYPES = (CapacityActionRecommendation, RecommendationAbstention)


def _reject_subclass(source: Any) -> None:
    """Refuse a *subclass* of a controller artifact, without touching the object.

    Admission is by **exact type**, not by ``isinstance``. A subclass is refused because
    every value the adapter would go on to read — the digest, the canonical dict, the
    digest payload, the subject, the selected plan — is reached through dynamic dispatch
    and can therefore be overridden. Admitting the subclass and then calling
    ``CapacityActionRecommendation.digest(source)`` unbound is **not** sufficient: that
    base method still calls ``self.to_canonical_dict()``, ``self._digest_payload()`` and
    the embedded objects' own serializers, so an override anywhere in that chain would be
    reached anyway and the recomputation would no longer be derived from canonical
    content.

    Nothing on ``source`` is invoked here — not a method, not a property, not a
    serializer. Only ``type()`` and ``isinstance()`` are consulted, and even a hostile
    ``__instancecheck__`` on the object's metaclass can only steer the object toward the
    unsupported-source rejection below, never toward admission.

    A caller holding a legitimate subclass may still use the adapter: serialize it and
    submit the canonical document, which is reconstructed into an exact base instance
    whose digest is recomputed from content.
    """

    if isinstance(source, _CONTROLLER_TYPES):
        raise UnsupportedRecommendationSourceError(
            f"{type(source).__name__} is a SUBCLASS of a canonical controller artifact; "
            "admission requires the exact canonical type. A subclass may override "
            "digest(), to_canonical_dict() or any serialization helper reached by "
            "dynamic dispatch, so its digest would not be derived from canonical "
            "content. Submit the canonical serialized document instead — it is "
            "reconstructed into an exact base instance and re-digested from content."
        )


def _require_exact_reconstruction(value: Any, expected: type) -> None:
    """Require strict reconstruction to have produced the exact canonical base type."""

    if type(value) is not expected:  # pragma: no cover - from_dict constructs via cls()
        raise UnsupportedRecommendationSourceError(
            f"strict reconstruction produced {type(value).__name__}, not the exact "
            f"canonical {expected.__name__}"
        )


def _carried_digest(document: Mapping[str, Any]) -> Optional[str]:
    value = document.get(CARRIED_DIGEST_FIELD)
    return value if value is not None else None


def _schema_tag(document: Mapping[str, Any]) -> Optional[str]:
    tag = document.get("schema_version")
    return tag if isinstance(tag, str) else None


def authenticate_controller_output(
    source: _ControllerOutput,
    *,
    expected_recommendation_digest: Optional[str] = None,
) -> Union[AuthenticatedRecommendation, AuthenticatedAbstention]:
    """Establish the Cloud Scaling recommendation boundary for ``source``.

    ``source`` is either a live controller artifact (``CapacityActionRecommendation`` or
    ``RecommendationAbstention``) or its canonical serialized form (a mapping carrying an
    explicit ``schema_version``). Nothing else is accepted: a duck-typed look-alike is
    refused here, before any digest is computed and long before the seam exists.

    :param expected_recommendation_digest: an independently obtained expectation.
        **Required** on the live-object path (see the module docstring); optional — and
        checked as an *additional* independent constraint — on the serialized path.
    :raises RecommendationInputError: unsupported input type, unrecognized schema tag, or
        a strict reconstruction failure reported by the controller.
    :raises RecommendationAuthenticityError: no independent digest was available, or a
        supplied one did not equal the recomputation.
    """

    if expected_recommendation_digest is not None:
        _require_digest_syntax(
            "expected_recommendation_digest", expected_recommendation_digest
        )

    # --- admission by EXACT type, before ``source`` is touched at all -----------------
    # This is the first thing that happens to an in-process object: no method, property,
    # serializer or digest function is called on it until its exact type is established.
    # ``isinstance`` is deliberately NOT the rule here — see ``_reject_subclass`` for why
    # a subclass must be refused rather than admitted through the base contract.
    source_type = type(source)

    if source_type is not CapacityActionRecommendation and (
        source_type is not RecommendationAbstention
    ):
        # Refuse a subclass BEFORE any other branch, so a subclass that also implements
        # ``Mapping`` cannot divert itself into the serialized path and have its own
        # ``get``/``keys`` consulted.
        _reject_subclass(source)

    # --- live controller artifacts -------------------------------------------------
    if source_type is CapacityActionRecommendation:
        # No carried digest exists on an in-process object, so the caller's independent
        # expectation is the only thing that can make this check load-bearing.
        expectation_source = _reconcile(
            source.digest(),
            carried=None,
            expected=expected_recommendation_digest,
            artifact="recommendation",
        )
        return AuthenticatedRecommendation(
            recommendation=source,
            recommendation_digest=source.digest(),
            expectation_source=expectation_source,
        )

    if source_type is RecommendationAbstention:
        # An abstention is never projected, so an expectation is optional here; when one
        # is supplied it is still checked, and a mismatch still fails closed.
        object_abstention_source = None
        if expected_recommendation_digest is not None:
            object_abstention_source = _reconcile(
                source.digest(),
                carried=None,
                expected=expected_recommendation_digest,
                artifact="abstention",
            )
        return AuthenticatedAbstention(
            abstention=source,
            abstention_digest=source.digest(),
            expectation_source=object_abstention_source,
        )

    # --- canonical serialized forms --------------------------------------------------
    if not isinstance(source, Mapping):
        raise UnsupportedRecommendationSourceError(
            "source must be a CapacityActionRecommendation, a RecommendationAbstention, "
            f"or one of their canonical serialized forms; got {type(source).__name__}"
        )

    tag = _schema_tag(source)
    if tag is None:
        raise UnsupportedRecommendationSourceError(
            "a canonical serialized controller artifact requires an explicit "
            "string 'schema_version'"
        )

    carried = _carried_digest(source)

    if tag == RECOMMENDATION_SCHEMA_VERSION:
        try:
            # Strict reconstruction: unknown fields, missing fields, non-canonical values
            # and every internally inconsistent relationship fail closed in the
            # controller's own __post_init__. `evidence_digest` is accepted as a known
            # key here but is never fed to the constructor, which is what keeps the
            # comparison below independent of the reconstruction.
            recommendation = CapacityActionRecommendation.from_dict(source)
        except RecommendationError as exc:
            raise RecommendationInputError(
                f"canonical recommendation failed strict reconstruction: {exc}"
            ) from exc
        # ``from_dict`` is invoked on the base class and constructs via ``cls(...)``, so
        # it yields the exact base type. Asserted rather than assumed: the whole point of
        # the serialized path is that what gets digested is an exact canonical instance.
        _require_exact_reconstruction(recommendation, CapacityActionRecommendation)
        recomputed = recommendation.digest()
        expectation_source = _reconcile(
            recomputed,
            carried=carried,
            expected=expected_recommendation_digest,
            artifact="recommendation",
        )
        return AuthenticatedRecommendation(
            recommendation=recommendation,
            recommendation_digest=recomputed,
            expectation_source=expectation_source,
        )

    if tag == RECOMMENDATION_ABSTENTION_SCHEMA_VERSION:
        try:
            abstention = RecommendationAbstention.from_dict(source)
        except RecommendationError as exc:
            raise RecommendationInputError(
                f"canonical abstention failed strict reconstruction: {exc}"
            ) from exc
        _require_exact_reconstruction(abstention, RecommendationAbstention)
        recomputed = abstention.digest()
        abstention_source = None
        if carried is not None or expected_recommendation_digest is not None:
            abstention_source = _reconcile(
                recomputed,
                carried=carried,
                expected=expected_recommendation_digest,
                artifact="abstention",
            )
        return AuthenticatedAbstention(
            abstention=abstention,
            abstention_digest=recomputed,
            expectation_source=abstention_source,
        )

    raise UnsupportedRecommendationSourceError(
        f"unsupported controller schema_version: {tag!r} (expected "
        f"{RECOMMENDATION_SCHEMA_VERSION!r} or "
        f"{RECOMMENDATION_ABSTENTION_SCHEMA_VERSION!r})"
    )
