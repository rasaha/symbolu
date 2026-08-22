"""F-2: the candidate digest must cover **everything the candidate carries**.

The audit found `_digest_payload()` accepting 37 parameters and reading only 35:
`policy_binding` and `producer_attestation` were passed in and silently ignored. The
payload bound derived scalars (`policy_binding_digest`, `producer_signing_payload_digest`)
while the candidate still *carried* the full objects — so the two could disagree. A rogue
policy issuer or forged producer signature could be swapped into the carried artifact and
the stale digest would continue to validate.

That is the failure this module exists to prevent recurring. It attacks the problem from
three directions, because any one alone would rot:

* **Statically** — an AST read-set analysis, the same technique that found the defect,
  asserting every parameter is read and every dataclass field is digest-bound.
* **Behaviourally** — independent substitution of each carried field, proving the digest
  moves for every one.
* **End-to-end** — the reported rogue-policy-issuer attack, reproduced and shown closed.

None of this establishes cryptographic trust. It establishes **complete content binding**:
a candidate can never carry different policy or attestation evidence under the same digest.
"""

from __future__ import annotations

import ast
import copy
import inspect
import pathlib

import pytest

from conftest import (
    build_attestation,
    build_candidate,
    build_policy_binding,
    build_projection,
    build_target_scope,
    coordinate_for,
)
from ugence_cloud_scaling_authorization_contracts import (
    CandidateConstructionError,
    CapacityAuthorizationCandidate,
    build_capacity_authorization_candidate,
)
from ugence_cloud_scaling_authorization_contracts import candidate as candidate_module

SRC = pathlib.Path(candidate_module.__file__).resolve()

#: Parameters of ``_digest_payload`` intentionally excluded from the emitted payload.
#: **Frozen and empty.** Every parameter must reach the payload. Adding a name here is a
#: security decision that requires a written rationale beside it, not a convenience.
FROZEN_PAYLOAD_PARAM_EXCLUSIONS: frozenset[str] = frozenset()

#: Candidate dataclass fields that are deliberately not *inside* the digest payload.
#: ``candidate_digest`` is the digest itself — a digest cannot cover itself. Nothing else
#: qualifies: every other field is semantic and must be bound.
FROZEN_FIELD_EXCLUSIONS: frozenset[str] = frozenset({"candidate_digest"})

#: Public attributes that are **not** dataclass fields and are deliberately outside the
#: digest payload (R-11, 5B-2). Both are constants that derive nothing from the instance, so
#: there is nothing about *this* candidate for a digest to cover:
#:
#: * ``trust_state`` — always ``PRESENT_BUT_NOT_TRUST_VERIFIED``, the whole package's posture;
#: * ``grants_authority`` — always ``False``, and no branch in this package returns ``True``.
#:
#: Membership here is not taken on trust. ``test_an_exempt_attribute_may_not_read_the_instance``
#: reads each exempt property's source and refuses one that touches ``self`` at all.
FROZEN_NON_FIELD_EXCLUSIONS: frozenset[str] = frozenset({"trust_state", "grants_authority"})


def _digest_payload_ast() -> ast.FunctionDef:
    tree = ast.parse(SRC.read_text(encoding="utf-8"), filename=str(SRC))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_digest_payload":
            return node
    raise AssertionError("_digest_payload not found")


def _params_and_reads():
    node = _digest_payload_ast()
    params = [a.arg for a in node.args.args] + [a.arg for a in node.args.kwonlyargs]
    reads = {
        n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
    }
    return params, reads


def test_every_digest_payload_parameter_is_read():
    """The exact defect the audit found: a parameter accepted and then ignored.

    This is the guard that makes the fix durable — a future parameter added to the
    signature but forgotten in the returned dict fails here, not in an incident.
    """

    params, reads = _params_and_reads()
    ignored = [p for p in params if p not in reads]
    unjustified = sorted(set(ignored) - FROZEN_PAYLOAD_PARAM_EXCLUSIONS)
    assert not unjustified, (
        f"_digest_payload accepts {len(params)} parameters but ignores {unjustified}; "
        "an accepted-and-ignored parameter means the candidate carries a value its digest "
        "does not cover. Bind it, or name it in FROZEN_PAYLOAD_PARAM_EXCLUSIONS with a "
        "written security rationale."
    )


def test_the_exclusion_sets_stay_frozen():
    """Widening an exclusion set is how this guard would be defeated; pin both."""

    assert FROZEN_PAYLOAD_PARAM_EXCLUSIONS == frozenset()
    assert FROZEN_FIELD_EXCLUSIONS == frozenset({"candidate_digest"})
    assert FROZEN_NON_FIELD_EXCLUSIONS == frozenset({"trust_state", "grants_authority"})


def test_every_candidate_field_is_digest_bound(candidate):
    """Every semantic field the candidate carries appears in its canonical payload."""

    payload_keys = set(candidate.digest_payload())
    fields = set(CapacityAuthorizationCandidate.__dataclass_fields__)
    unbound = sorted(fields - payload_keys - FROZEN_FIELD_EXCLUSIONS)
    assert not unbound, f"candidate fields carried but not digest-bound: {unbound}"


def _public_non_field_attributes() -> dict:
    """Public non-field attributes of the candidate class, name → descriptor.

    Properties and ``cached_property`` alike. Read off the class rather than an instance so a
    descriptor is seen as itself instead of as the value it computes, and across the MRO so an
    attribute inherited from a base is not missed.
    """

    from functools import cached_property

    fields = set(CapacityAuthorizationCandidate.__dataclass_fields__)
    found = {}
    for klass in CapacityAuthorizationCandidate.__mro__:
        if klass is object:
            continue
        for name, attr in vars(klass).items():
            if name.startswith("_") or name in fields or name in found:
                continue
            if isinstance(attr, (property, cached_property)):
                found[name] = attr
    return found


def test_every_public_non_field_attribute_is_digest_bound_or_named_exempt(candidate):
    """**R-11.** A digest-covered binding must not be able to arrive as a property.

    ``test_every_candidate_field_is_digest_bound`` enumerates ``__dataclass_fields__``, and a
    property is not a field. Measured before this test existed: adding one per-instance,
    semantically load-bearing property outside ``digest_payload()`` left the whole suite green
    with **zero test edits** — cheaper than the partition ratchet's free ride, which at least
    cost six. So the completeness claim under D-5B1-1 held only for bindings that happen to be
    fields, and nothing made a future one be a field.

    What this refuses is the *silent* case. A derived attribute is still allowed; it has to be
    named in ``FROZEN_NON_FIELD_EXCLUSIONS``, and the test below decides whether it may be.
    """

    payload_keys = set(candidate.digest_payload())
    unbound = sorted(
        set(_public_non_field_attributes()) - payload_keys - FROZEN_NON_FIELD_EXCLUSIONS
    )
    assert not unbound, (
        f"the candidate carries public attributes its digest does not cover: {unbound}. "
        "A property is not a dataclass field, so the field-completeness test above cannot "
        "see it. Bind it in digest_payload(), or name it in FROZEN_NON_FIELD_EXCLUSIONS "
        "with a written rationale."
    )


def test_an_exempt_attribute_may_not_read_the_instance():
    """The exemption is earned structurally, not by being written down.

    An earlier draft of this test compared two candidates and asserted the exempt attributes
    agreed. That was vacuous in the way this repository has learned to distrust: it passed
    against a deliberately planted property reading ``self.tenant_id``, because the two
    fixtures happened to differ in another field. Whether the check fires should not depend
    on which fixture varies.

    So the claim is measured where it actually lives — in the source. An exempt property may
    not touch ``self`` at all. That is strictly stronger than constancy across two samples,
    and it cannot be satisfied by luck.
    """

    import inspect
    import textwrap

    for name in sorted(FROZEN_NON_FIELD_EXCLUSIONS):
        descriptor = _public_non_field_attributes()[name]
        func = getattr(descriptor, "fget", None) or getattr(descriptor, "func")
        tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
        reads_self = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Name) and node.id == "self" and isinstance(node.ctx, ast.Load)
        ]
        assert not reads_self, (
            f"{name} is exempt from the candidate digest on the grounds that it derives "
            "nothing from the instance, and it reads self. Either it is per-instance data, "
            "which must be digest-bound, or the exemption is wrong."
        )


def test_the_exempt_attributes_are_the_two_that_exist():
    """The exemption list is not allowed to name something that is not there.

    A stale entry would silently pre-authorise a future property that happened to reuse the
    name, which is the same defeat as widening the set.
    """

    assert FROZEN_NON_FIELD_EXCLUSIONS <= set(_public_non_field_attributes())


def test_the_carried_artifacts_are_bound_in_full_not_by_digest_alone(candidate):
    """The three carried objects appear as complete canonical forms, not stand-ins."""

    payload = candidate.digest_payload()
    for key, obj in (
        ("target_scope", candidate.target_scope),
        ("policy_binding", candidate.policy_binding),
        ("producer_attestation", candidate.producer_attestation),
    ):
        assert key in payload, f"{key} is carried but absent from the payload"
        assert payload[key] == obj.to_canonical_dict(), (
            f"{key} is bound by something other than its full canonical form"
        )


def test_signature_bytes_and_issuer_identity_are_inside_the_payload(candidate):
    """The values an attacker would swap are literally present in the covered bytes."""

    payload = candidate.digest_payload()
    assert payload["producer_attestation"]["signature"] == candidate.producer_attestation.signature
    assert payload["policy_binding"]["policy_signature"] == candidate.policy_binding.policy_signature
    assert payload["policy_binding"]["policy_issuer"] == candidate.policy_binding.policy_issuer
    assert payload["policy_binding"]["policy_key_id"] == candidate.policy_binding.policy_key_id
    assert payload["policy_binding"]["policy_version"] == candidate.policy_binding.policy_version
    # Both trust states are framed in, so the digest commits to "not trust-verified".
    assert payload["producer_attestation"]["trust_state"] == "PRESENT_BUT_NOT_TRUST_VERIFIED"
    assert payload["policy_binding"]["trust_state"] == "PRESENT_BUT_NOT_TRUST_VERIFIED"


# ======================================================================================
# Independent substitution: changing any carried field must move the candidate digest
# ======================================================================================


def _rebuilt(projection, decision, *, attestation=None, scope=None, policy=None):
    scope = scope if scope is not None else build_target_scope(projection)
    return build_capacity_authorization_candidate(
        projection=projection,
        decision=decision,
        producer_attestation=(
            attestation
            if attestation is not None
            else build_attestation(recommendation_digest=projection.recommendation_digest)
        ),
        policy_binding=policy if policy is not None else build_policy_binding(scope),
        policy_coordinate_binding=coordinate_for(policy if policy is not None else build_policy_binding(scope)),
        target_scope=scope,
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("producer_id", "attacker.rogue-producer"),
        ("producer_key_id", "rogue-producer-key"),
    ],
)
def test_producer_identity_substitution_moves_the_digest(projection, decision, field, value):
    """``signing_purpose`` is deliberately absent here: it is a closed single-member set,
    so a substituted value is *rejected at construction* rather than reaching a digest.
    That path is covered by ``test_unsupported_signing_purpose_is_refused``."""

    base = _rebuilt(projection, decision)
    other = _rebuilt(
        projection,
        decision,
        attestation=build_attestation(
            recommendation_digest=projection.recommendation_digest, **{field: value}
        ),
    )
    assert other.candidate_digest != base.candidate_digest, f"{field} is not digest-bound"


def test_producer_signature_bytes_substitution_moves_the_digest(projection, decision):
    """The signature bytes themselves — the pre-F-2 blind spot."""

    base = _rebuilt(projection, decision)
    forged = build_attestation(recommendation_digest=projection.recommendation_digest)
    object.__setattr__(forged, "signature", "de" * 32)
    tampered = copy.copy(base)
    object.__setattr__(tampered, "producer_attestation", forged)
    assert tampered.digest() != tampered.candidate_digest, (
        "forged producer signature bytes ride along under an unchanged candidate digest"
    )


def test_producer_signing_payload_digest_is_bound(candidate):
    tampered = copy.copy(candidate)
    object.__setattr__(tampered, "producer_signing_payload_digest", "sha256:" + "a" * 64)
    assert tampered.digest() != tampered.candidate_digest


@pytest.mark.parametrize(
    "field,value",
    [
        ("policy_id", "attacker.rogue-policy"),
        ("policy_version", "9.9.9"),
        ("policy_issuer", "attacker.rogue-authority"),
        ("policy_key_id", "rogue-signing-key"),
    ],
)
def test_policy_identity_substitution_moves_the_digest(projection, decision, field, value):
    scope = build_target_scope(projection)
    base = _rebuilt(projection, decision, scope=scope)
    other = _rebuilt(
        projection, decision, scope=scope, policy=build_policy_binding(scope, **{field: value})
    )
    assert other.candidate_digest != base.candidate_digest, f"{field} is not digest-bound"


def test_policy_artifact_digest_and_signature_are_bound(projection, decision):
    scope = build_target_scope(projection)
    base = _rebuilt(projection, decision, scope=scope)
    # A different policy artifact digest, everything else identical.
    other = _rebuilt(
        projection,
        decision,
        scope=scope,
        policy=build_policy_binding(scope, policy_version="3.1.1"),
    )
    assert other.candidate_digest != base.candidate_digest
    # And the carried signature itself.
    rogue = build_policy_binding(scope)
    object.__setattr__(rogue, "policy_signature", "ff" * 32)
    tampered = copy.copy(base)
    object.__setattr__(tampered, "policy_binding", rogue)
    assert tampered.digest() != tampered.candidate_digest


@pytest.mark.parametrize(
    "field,value",
    [
        ("account_id", "acct-999999999999"),
        ("max_magnitude", 19),
        ("max_delta", 4),
    ],
)
def test_target_scope_substitution_moves_the_digest(projection, decision, field, value):
    base = _rebuilt(projection, decision)
    scope = build_target_scope(projection, **{field: value})
    other = _rebuilt(projection, decision, scope=scope)
    assert other.candidate_digest != base.candidate_digest, f"{field} is not digest-bound"


def test_trust_state_representation_is_bound(candidate):
    """Both trust states are inside the covered bytes, so a forged one changes the digest."""

    payload = candidate.digest_payload()
    forged = copy.deepcopy(payload)
    forged["producer_attestation"]["trust_state"] = "TRUST_VERIFIED"
    from ugence_cloud_scaling_authorization_contracts import canonical_digest

    assert canonical_digest(forged) != candidate.candidate_digest


# ======================================================================================
# The reported attack, reproduced end to end
# ======================================================================================


def test_rogue_policy_issuer_attack_is_closed(projection, decision):
    """The audit's reported attack, run as the audit ran it.

    1. build the genuine candidate and record its digest;
    2. substitute a rogue policy issuer into the carried artifact;
    3. preserve the former candidate digest;
    4. construction is refused;
    5. recomputation over the tampered artifact yields a different digest.
    """

    scope = build_target_scope(projection)
    genuine = _rebuilt(projection, decision, scope=scope)
    recorded = genuine.candidate_digest

    rogue = build_policy_binding(
        scope, policy_issuer="attacker.rogue-authority", policy_key_id="rogue-key-1"
    )

    # (4) construction with the rogue artifact and the preserved digest must be refused
    fields = {f: getattr(genuine, f) for f in genuine.__dataclass_fields__}
    fields["policy_binding"] = rogue
    with pytest.raises(CandidateConstructionError) as exc:
        CapacityAuthorizationCandidate(**fields)
    assert exc.value.reason.value == "candidate_digest_failure"

    # (5) and a forced substitution no longer validates against the recorded digest
    tampered = copy.copy(genuine)
    object.__setattr__(tampered, "policy_binding", rogue)
    assert tampered.digest() != recorded
    assert tampered.policy_binding.policy_issuer == "attacker.rogue-authority"


def test_a_candidate_cannot_carry_two_different_evidence_sets_under_one_digest(
    projection, decision
):
    """The invariant in one sentence, asserted over every carried artifact."""

    scope = build_target_scope(projection)
    genuine = _rebuilt(projection, decision, scope=scope)
    substitutes = {
        "policy_binding": build_policy_binding(scope, policy_issuer="other.authority"),
        "producer_attestation": build_attestation(
            recommendation_digest=projection.recommendation_digest,
            producer_id="other.producer",
        ),
        "target_scope": build_target_scope(projection, account_id="acct-777777777777"),
    }
    for name, substitute in substitutes.items():
        tampered = copy.copy(genuine)
        object.__setattr__(tampered, name, substitute)
        assert tampered.digest() != genuine.candidate_digest, (
            f"{name} can be swapped while the candidate digest stays valid"
        )


def test_digest_completeness_is_verified_from_the_public_api_too(candidate):
    """The guard holds through the public surface, not only against module internals."""

    params = set(inspect.signature(candidate_module._digest_payload).parameters)
    payload = set(candidate.digest_payload())
    # Every parameter name is either a payload key or contributes to one (the three
    # artifact objects are keys in their own right after F-2).
    assert params - payload == set(), f"parameters not represented in the payload: {params - payload}"
