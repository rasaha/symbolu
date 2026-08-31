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

#: **R-11.** The complete public non-field surface of ``CapacityAuthorizationCandidate``:
#: every public name reachable on the class or through its MRO that is not a dataclass field.
#: Three methods and two constant properties.
#:
#: This is an allowlist over *names*, not a judgement about implementations. An earlier
#: attempt decided whether an exempt attribute was instance-derived by reading its source for
#: the name ``self``; that is source classification, and "derives from instance state" is a
#: semantic property whose every syntactic approximation has a bypass class — a renamed
#: receiver, a helper delegate, ``getattr``, a custom descriptor. Broadening the scan only
#: moves the boundary, so the classifier is gone. Whatever a member is implemented as, it must
#: be named here.
#:
#: ``trust_state`` and ``grants_authority`` stay properties rather than becoming digest-covered
#: fields on purpose: a read-only property cannot be forged by ``object.__setattr__`` on a
#: frozen dataclass, and a field can. Making them fields would trade a completeness hole for a
#: forgery one.
FROZEN_NON_FIELD_SURFACE: frozenset[str] = frozenset(
    {"digest", "digest_payload", "to_canonical_dict", "trust_state", "grants_authority"}
)


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
    assert FROZEN_NON_FIELD_SURFACE == frozenset(
        {"digest", "digest_payload", "to_canonical_dict", "trust_state", "grants_authority"}
    )


def test_every_candidate_field_is_digest_bound(candidate):
    """Every semantic field the candidate carries appears in its canonical payload."""

    payload_keys = set(candidate.digest_payload())
    fields = set(CapacityAuthorizationCandidate.__dataclass_fields__)
    unbound = sorted(fields - payload_keys - FROZEN_FIELD_EXCLUSIONS)
    assert not unbound, f"candidate fields carried but not digest-bound: {unbound}"


def public_non_field_members(cls) -> "set[str]":
    """Every public name on ``cls`` or its MRO that is not a dataclass field.

    **Statically.** ``inspect.getmembers_static`` never invokes a descriptor, so a property, a
    ``cached_property`` or a custom ``__get__`` is observed as the object it is rather than as
    the value it would compute — and a member whose computation raised could not hide by
    making enumeration fail. ``dir()`` plus ``inspect.getattr_static`` is the same guarantee
    where ``getmembers_static`` is unavailable.

    Enumeration is total over *names* and asks nothing about how a member is implemented. That
    is the whole design: a renamed receiver, a helper delegate, ``getattr``, a custom
    descriptor and an inherited attribute are all just names here, and all of them land in the
    net. Methods are included deliberately — pinning the public surface is the point, and a
    binding smuggled in as a zero-argument method would otherwise be exempt by category.
    """

    import inspect

    fields = set(getattr(cls, "__dataclass_fields__", {}))
    if hasattr(inspect, "getmembers_static"):
        names = {name for name, _ in inspect.getmembers_static(cls)}
    else:  # pragma: no cover - Python < 3.11
        names = set(dir(cls))
        for name in list(names):
            try:
                inspect.getattr_static(cls, name)
            except AttributeError:
                names.discard(name)
    return {n for n in names if not n.startswith("_") and n not in fields}


def test_every_public_non_field_member_is_digest_bound_or_named(candidate):
    """**R-11.** A binding may not reach the candidate outside the digest and unnamed.

    ``test_every_candidate_field_is_digest_bound`` enumerates ``__dataclass_fields__``, and a
    property is not a field. Measured before this existed: one per-instance, semantically
    load-bearing property outside ``digest_payload()`` left the whole suite green with **zero
    test edits** — cheaper than the partition ratchet's free ride, which cost six.

    The claim is precisely this and no wider: every public attribute *declared on the class or
    inherited through its MRO* is either digest-covered or named. The class is a frozen
    dataclass without ``__slots__``, so ``object.__setattr__`` can still staple an attribute
    onto a live instance; no static check sees that and this one does not claim to.
    """

    payload_keys = set(candidate.digest_payload())
    unnamed = sorted(
        public_non_field_members(CapacityAuthorizationCandidate)
        - payload_keys
        - FROZEN_NON_FIELD_SURFACE
    )
    assert not unnamed, (
        f"the candidate exposes public members its digest does not cover: {unnamed}. "
        "A property, descriptor or method is not a dataclass field, so the field test above "
        "cannot see it. Bind it in digest_payload(), or name it in FROZEN_NON_FIELD_SURFACE "
        "and disclose it in the changelog as 'surface: <name> — <why>'."
    )


def test_the_allowlist_names_only_members_that_exist():
    """A stale entry would pre-authorise a future member that reused the name."""

    assert FROZEN_NON_FIELD_SURFACE <= public_non_field_members(CapacityAuthorizationCandidate)


@pytest.mark.parametrize(
    "construct",
    ["renamed_receiver", "helper_delegate", "getattr_access", "custom_descriptor", "inherited"],
)
def test_the_enumerator_sees_every_way_an_attribute_can_arrive(construct):
    """The five bypasses the source classifier could not survive, measured on the enumerator.

    Each is a way a per-instance value could reach a reader without being a dataclass field.
    Against a scan for the literal name ``self`` the first four walk straight through. Against
    an enumeration over names none of them is even a distinguishable case — which is the
    argument for the redesign, made as a measurement rather than as a claim.
    """

    from dataclasses import dataclass

    class _Descriptor:
        def __get__(self, obj, owner=None):
            return "value" if obj is None else obj.tenant_id

    def _helper(instance):
        return instance.tenant_id

    @dataclass(frozen=True)
    class _Base:
        tenant_id: str

        @property
        def inherited(self) -> str:
            return self.tenant_id

    @dataclass(frozen=True)
    class _Candidate(_Base):
        @property
        def renamed_receiver(obj) -> str:  # noqa: N805 - the bypass under test
            return obj.tenant_id

        @property
        def helper_delegate(self) -> str:
            return _helper(self)

        @property
        def getattr_access(obj) -> str:  # noqa: N805 - the bypass under test
            return getattr(obj, "tenant_id")

        custom_descriptor = _Descriptor()

    assert construct in public_non_field_members(_Candidate)


def test_the_enumerator_sees_an_attribute_attached_after_class_creation():
    """Attached to the class rather than written in its body, and still enumerated."""

    from dataclasses import dataclass

    @dataclass(frozen=True)
    class _Candidate:
        tenant_id: str

    assert "stapled" not in public_non_field_members(_Candidate)
    _Candidate.stapled = property(lambda obj: obj.tenant_id)
    assert "stapled" in public_non_field_members(_Candidate)


def test_enumeration_never_executes_a_member():
    """A member that raised on access must not be able to hide by breaking enumeration."""

    from dataclasses import dataclass

    @dataclass(frozen=True)
    class _Candidate:
        tenant_id: str

        @property
        def explodes(self):
            raise RuntimeError("a member that refuses to be read is still a member")

    assert "explodes" in public_non_field_members(_Candidate)


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
