#!/usr/bin/env python3
"""Independent adversarial probes for the Ugence Trusted Evidence Authority.

**Independent** in the load-bearing sense: this file imports **only** the
curated public API — ``ugence_trusted_evidence_authority.api`` — plus the Python
standard library. It imports no package test module, no ``_builders`` helper, no
``conftest``, and no private submodule. It builds every fixture from scratch and
recomputes every expected digest with ``hashlib`` alone.

That matters because a probe that reuses the suite's own helpers can only
re-confirm the suite's own assumptions. If the package's internal validators
were removed wholesale, these probes would still fail.

Runs standalone (``python packages/trusted-evidence-authority/adversarial_probes.py``)
and is also executed inside the isolated wheel install by
``verify_trusted_evidence_authority_distribution.py``. Exit code 0 on success;
non-zero with a report on the first failure.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone

from ugence_trusted_evidence_authority.api import (  # noqa: F401
    EVIDENCE_LIFECYCLE_TRANSITIONS,
    EVIDENCE_IDENTITY_DIGEST_DOMAIN,
    TRUSTED_EVIDENCE_CANONICALIZATION_VERSION,
    TRUSTED_EVIDENCE_REFUSAL_REASONS,
    ApplicabilityCoordinate,
    ApplicabilityDeclaration,
    CanonicalEvidenceIdentity,
    EvidenceLifecycleState,
    EvidenceObservation,
    EvidenceProvenanceChain,
    EvidenceSchemaRef,
    EvidenceScopeBinding,
    EvidenceStructuralStatus,
    EvidenceTrustStage,
    EvidenceVerificationRequest,
    TrustedEvidenceCanonicalizationError,
    TrustedEvidenceContractError,
    TrustedEvidenceLifecycleError,
    TrustedEvidenceRefusalReason,
    canonical_bytes,
    canonical_digest,
    is_valid_lifecycle_transition,
    require_valid_lifecycle_transition,
)

UTC = timezone.utc
R = TrustedEvidenceRefusalReason

_FAILURES: list = []
_RUN = 0


def probe(fn):
    """Register and immediately run a probe, recording rather than raising."""

    global _RUN
    _RUN += 1
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 — a probe harness reports, not crashes
        _FAILURES.append(f"{fn.__name__}: {type(exc).__name__}: {exc}")
    return fn


def expect_refusal(callable_, *exc_types):
    """Assert ``callable_`` refuses; a silent acceptance is the failure mode."""

    types = exc_types or (TrustedEvidenceContractError,)
    try:
        result = callable_()
    except types:
        return
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(f"refused with an unexpected error: {exc!r}") from None
    raise AssertionError(f"expected a refusal, got {result!r}")


# --------------------------------------------------------------------------- #
# Fixtures — built here, from the public API only
# --------------------------------------------------------------------------- #
CONTENT = hashlib.sha256(b"probe-evidence-content").hexdigest()
CONTEXT = hashlib.sha256(b"probe-assessment-context").hexdigest()
BINDING = hashlib.sha256(b"probe-system-binding").hexdigest()
OTHER = hashlib.sha256(b"probe-something-else").hexdigest()

T_OBS = datetime(2026, 4, 1, 9, 30, 0, 125000, tzinfo=UTC)
T_COL = datetime(2026, 4, 1, 10, 0, 0, tzinfo=UTC)
T_FROM = datetime(2026, 4, 1, tzinfo=UTC)
T_TO = datetime(2026, 10, 1, tzinfo=UTC)
T_MID = datetime(2026, 7, 1, tzinfo=UTC)


def build_identity(**overrides) -> CanonicalEvidenceIdentity:
    base = dict(
        evidence_id="probe-ev",
        evidence_type="PROBE_EVIDENCE",
        schema=EvidenceSchemaRef(schema_id="probe.schema", schema_version="1"),
        content_digest=CONTENT,
        observation=EvidenceObservation(
            producer_id="probe-producer",
            collected_at=T_COL,
            observed_from=T_OBS,
            observed_to=None,
            issuer_id="",
        ),
        scope=EvidenceScopeBinding(
            tenant_id="probe-tenant",
            assessment_context_ref="probe-ctx",
            assessment_context_digest=CONTEXT,
            subject_ref="probe-subject",
            assessment_purpose_ref="probe-purpose",
            usage_scope_ref="probe-scope",
            assessed_system_applicability=ApplicabilityDeclaration.APPLICABLE,
            assessed_system_binding_ref="probe-binding",
            assessed_system_binding_digest=BINDING,
        ),
        provenance=EvidenceProvenanceChain(
            chain_ref="probe-chain", custody_refs=("link-a", "link-b")
        ),
        lifecycle_state=EvidenceLifecycleState.SUBMITTED,
        geography=ApplicabilityCoordinate.applicable("US"),
        domain=ApplicabilityCoordinate.not_applicable(),
        intended_outcome=ApplicabilityCoordinate.applicable("probe-outcome"),
        valid_from=T_FROM,
        valid_to=T_TO,
    )
    base.update(overrides)
    return CanonicalEvidenceIdentity(**base)


def build_request(**overrides) -> EvidenceVerificationRequest:
    base = dict(
        evidence=build_identity(),
        expected_content_digest=CONTENT,
        expected_tenant_id="probe-tenant",
        expected_assessment_context_ref="probe-ctx",
        expected_assessment_context_digest=CONTEXT,
        expected_subject_ref="probe-subject",
        expected_assessment_purpose_ref="probe-purpose",
        expected_usage_scope_ref="probe-scope",
        expected_assessed_system_binding_ref="probe-binding",
        expected_assessed_system_binding_digest=BINDING,
        as_of=T_MID,
        requested_trust_stages=(EvidenceTrustStage.CRYPTOGRAPHICALLY_AUTHENTIC,),
    )
    base.update(overrides)
    return EvidenceVerificationRequest(**base)


# --------------------------------------------------------------------------- #
# A. Nothing in this API can report a verified state
# --------------------------------------------------------------------------- #
@probe
def probe_no_verified_state_exists():
    assert list(EvidenceStructuralStatus) == [
        EvidenceStructuralStatus.STRUCTURAL_UNVERIFIED
    ]
    ident = build_identity()
    assert ident.structural_status is EvidenceStructuralStatus.STRUCTURAL_UNVERIFIED
    assert ident.authenticity_verified is False
    assert len(ident.unestablished_trust_stages) == 5
    assert ident.established_trust_stages == (
        EvidenceTrustStage.STRUCTURALLY_CONSTRUCTIBLE,
    )


@probe
def probe_every_refusal_reason_is_a_refusal():
    assert set(R) == set(TRUSTED_EVIDENCE_REFUSAL_REASONS)
    assert R.TRUSTED_EVIDENCE_INDETERMINATE in TRUSTED_EVIDENCE_REFUSAL_REASONS
    assert len(list(R)) == 19


@probe
def probe_a_request_reports_that_no_verification_happened():
    req = build_request()
    assert req.structural_scope_mismatches() == ()
    assert (
        req.unperformed_verification_reason
        is R.TRUSTED_EVIDENCE_VERIFICATION_NOT_PERFORMED
    )


# --------------------------------------------------------------------------- #
# B. Forgery routes (ADR §10, task §11)
# --------------------------------------------------------------------------- #
@probe
def probe_verified_true_and_truthy_values_are_unaccepted():
    for truthy in (True, 1, "true", "VERIFIED", [1], {"a": 1}):
        expect_refusal(lambda t=truthy: build_identity(verified=t), TypeError)
        expect_refusal(lambda t=truthy: build_request(verified=t), TypeError)


@probe
def probe_frozen_contracts_reject_assignment():
    ident = build_identity()
    for attribute, value in (
        ("authenticity_verified", True),
        ("structural_status", "VERIFIED"),
        ("evidence_id", "other"),
        ("content_digest", OTHER),
    ):
        expect_refusal(
            lambda a=attribute, v=value: setattr(ident, a, v),
            dataclasses.FrozenInstanceError,
        )
    assert ident.authenticity_verified is False


@probe
def probe_direct_enum_construction_cannot_reach_a_verified_member():
    for attempt in ("VERIFIED", "AUTHENTIC", "TRUSTED", "APPROVED", "OK"):
        expect_refusal(lambda a=attempt: EvidenceStructuralStatus(a), ValueError)
        expect_refusal(lambda a=attempt: R(a), ValueError)


@probe
def probe_a_subclass_cannot_enter_a_contract_graph():
    class Forged(CanonicalEvidenceIdentity):
        @property
        def authenticity_verified(self):
            return True

    base = build_identity()
    forged = Forged(
        **{f.name: getattr(base, f.name) for f in dataclasses.fields(base)}
    )
    assert forged.authenticity_verified is True  # it can lie about itself...
    expect_refusal(lambda: build_request(evidence=forged))  # ...and go no further
    # Its digest is separated by the type name bound into the frame.
    assert canonical_digest(forged) != base.canonical_digest()
    assert b'"type":"Forged"' in canonical_bytes(forged)


@probe
def probe_a_property_override_never_reaches_the_digest():
    base = build_identity()
    before = base.canonical_digest()
    original = CanonicalEvidenceIdentity.authenticity_verified
    try:
        CanonicalEvidenceIdentity.authenticity_verified = property(lambda self: True)
        assert base.canonical_digest() == before
        assert b"authenticity_verified" not in base.canonical_bytes()
    finally:
        CanonicalEvidenceIdentity.authenticity_verified = original
    assert build_identity().authenticity_verified is False


@probe
def probe_an_authority_looking_name_confers_nothing():
    for name in ("Ugence Trusted Evidence Authority", "TAP", "ROOT-TRUST-ANCHOR"):
        ident = build_identity(
            observation=EvidenceObservation(
                producer_id=name,
                collected_at=T_COL,
                observed_from=T_OBS,
                observed_to=None,
                issuer_id="",
            )
        )
        assert ident.authenticity_verified is False
        assert (
            EvidenceTrustStage.CRYPTOGRAPHICALLY_AUTHENTIC
            in ident.unestablished_trust_stages
        )


@probe
def probe_a_matching_digest_is_not_verification():
    req = build_request(expected_content_digest=CONTENT)
    assert req.structural_scope_mismatches() == ()
    assert req.evidence.authenticity_verified is False
    # Recomputing the digest independently changes nothing about trust.
    assert (
        hashlib.sha256(req.evidence.canonical_bytes()).hexdigest()
        == req.evidence.canonical_digest()
    )
    assert req.evidence.unestablished_trust_stages


@probe
def probe_a_duck_typed_lookalike_is_refused():
    base = build_identity()

    class Lookalike:
        pass

    fake = Lookalike()
    for field in dataclasses.fields(base):
        setattr(fake, field.name, getattr(base, field.name))
    fake.authenticity_verified = True
    expect_refusal(lambda: build_request(evidence=fake))

    @dataclasses.dataclass(frozen=True)
    class LookalikeSchema:
        schema_id: str = "probe.schema"
        schema_version: str = "1"

    expect_refusal(lambda: build_identity(schema=LookalikeSchema()))


@probe
def probe_cross_scope_replay_is_detectable_on_every_axis():
    base = build_identity()
    axes = {
        "tenant_id": ("probe-tenant-2", R.TRUSTED_EVIDENCE_TENANT_MISMATCH),
        "assessment_context_ref": ("probe-ctx-2", R.TRUSTED_EVIDENCE_CONTEXT_MISMATCH),
        "subject_ref": ("probe-subject-2", R.TRUSTED_EVIDENCE_SUBJECT_MISMATCH),
        "assessed_system_binding_ref": (
            "probe-binding-2",
            R.TRUSTED_EVIDENCE_SYSTEM_BINDING_MISMATCH,
        ),
        "assessment_purpose_ref": (
            "probe-purpose-2",
            R.TRUSTED_EVIDENCE_PURPOSE_SCOPE_MISMATCH,
        ),
        "usage_scope_ref": (
            "probe-scope-2",
            R.TRUSTED_EVIDENCE_PURPOSE_SCOPE_MISMATCH,
        ),
    }
    for field, (replacement, expected) in axes.items():
        original_scope = base.scope
        replayed_scope = EvidenceScopeBinding(
            **{
                **{
                    f.name: getattr(original_scope, f.name)
                    for f in dataclasses.fields(original_scope)
                },
                field: replacement,
            }
        )
        replayed = build_identity(scope=replayed_scope)
        assert replayed.canonical_digest() != base.canonical_digest(), field
        assert expected in build_request(evidence=replayed).structural_scope_mismatches()


# --------------------------------------------------------------------------- #
# C. Canonicalization and digests, recomputed independently
# --------------------------------------------------------------------------- #
@probe
def probe_digest_is_sha256_over_exactly_the_canonical_bytes():
    for contract in (
        build_identity(),
        build_request(),
        EvidenceSchemaRef(schema_id="probe.schema", schema_version="1"),
    ):
        raw = canonical_bytes(contract)
        assert hashlib.sha256(raw).hexdigest() == canonical_digest(contract)


@probe
def probe_the_canonical_frame_is_versioned_and_domain_separated():
    framed = json.loads(canonical_bytes(build_identity()).decode("utf-8"))
    assert framed["canonicalization"] == TRUSTED_EVIDENCE_CANONICALIZATION_VERSION
    assert framed["domain"] == EVIDENCE_IDENTITY_DIGEST_DOMAIN
    assert framed["type"] == "CanonicalEvidenceIdentity"
    assert (
        TRUSTED_EVIDENCE_CANONICALIZATION_VERSION
        == "ugence.trusted-evidence-authority/canonicalization/v1"
    )
    assert (
        EVIDENCE_IDENTITY_DIGEST_DOMAIN
        == "ugence.trusted-evidence-authority/evidence-identity/v1"
    )


@probe
def probe_a_hand_written_byte_string_reproduces_the_digest():
    """Reconstructed from the documented rules, not from a program run."""

    literal = (
        b'{"body":{"schema_id":"probe.schema","schema_version":"1"},'
        b'"canonicalization":"ugence.trusted-evidence-authority/canonicalization/v1",'
        b'"domain":"ugence.trusted-evidence-authority/evidence-identity/v1",'
        b'"type":"EvidenceSchemaRef"}'
    )
    schema = EvidenceSchemaRef(schema_id="probe.schema", schema_version="1")
    assert canonical_bytes(schema) == literal
    assert canonical_digest(schema) == hashlib.sha256(literal).hexdigest()


@probe
def probe_utc_offset_equivalence_and_microsecond_preservation():
    utc = datetime(2026, 4, 1, 9, 30, 0, 125000, tzinfo=UTC)
    ist = utc.astimezone(timezone(timedelta(hours=5, minutes=30)))
    nyc = utc.astimezone(timezone(timedelta(hours=-4)))
    built = [
        build_identity(
            observation=EvidenceObservation(
                producer_id="probe-producer",
                collected_at=T_COL,
                observed_from=t,
                observed_to=None,
                issuer_id="",
            )
        )
        for t in (utc, ist, nyc)
    ]
    assert len({b.canonical_bytes() for b in built}) == 1
    assert b"09:30:00.125000Z" in built[0].canonical_bytes()
    shifted = build_identity(
        observation=EvidenceObservation(
            producer_id="probe-producer",
            collected_at=T_COL,
            observed_from=utc.replace(microsecond=125001),
            observed_to=None,
            issuer_id="",
        )
    )
    assert shifted.canonical_digest() != built[0].canonical_digest()


@probe
def probe_naive_datetimes_are_refused_everywhere():
    naive = datetime(2026, 4, 1, 9, 30)
    expect_refusal(
        lambda: EvidenceObservation(
            producer_id="p", collected_at=naive, observed_from=T_OBS
        )
    )
    expect_refusal(lambda: build_identity(valid_from=naive))
    expect_refusal(lambda: build_request(as_of=naive))
    expect_refusal(lambda: build_identity().is_valid_at(naive))


@probe
def probe_reordered_stage_input_is_equivalent_and_custody_order_is_not():
    a = build_request(
        requested_trust_stages=(
            EvidenceTrustStage.CRYPTOGRAPHICALLY_AUTHENTIC,
            EvidenceTrustStage.CURRENTLY_VALID,
        )
    )
    b = build_request(
        requested_trust_stages=(
            EvidenceTrustStage.CURRENTLY_VALID,
            EvidenceTrustStage.CRYPTOGRAPHICALLY_AUTHENTIC,
        )
    )
    assert a.canonical_digest() == b.canonical_digest()

    forward = build_identity(
        provenance=EvidenceProvenanceChain(chain_ref="c", custody_refs=("x", "y"))
    )
    backward = build_identity(
        provenance=EvidenceProvenanceChain(chain_ref="c", custody_refs=("y", "x"))
    )
    assert forward.canonical_digest() != backward.canonical_digest()


@probe
def probe_the_encoder_has_no_permissive_fallback():
    @dataclasses.dataclass(frozen=True)
    class Holder:
        payload: object

    class Opaque:
        pass

    for bad in (
        Opaque(),
        1.5,
        float("nan"),
        float("inf"),
        b"bytes",
        {"k": "v"},
        {1, 2},
        datetime(2026, 4, 1),
        "é",  # NFD, not NFC
    ):
        expect_refusal(
            lambda b=bad: canonical_bytes(Holder(payload=b)),
            TrustedEvidenceCanonicalizationError,
        )


@probe
def probe_none_is_explicit_and_distinct_from_empty():
    with_bound = build_identity(valid_to=T_TO)
    without = build_identity(valid_to=None)
    assert json.loads(canonical_bytes(without))["body"]["valid_to"] is None
    assert with_bound.canonical_digest() != without.canonical_digest()


# --------------------------------------------------------------------------- #
# D. Constructor invariants
# --------------------------------------------------------------------------- #
@probe
def probe_blank_padded_and_mistyped_identifiers_are_refused():
    for bad in ("", " ", "\t", " probe-ev", "probe-ev ", None, 1, True, b"x", ["x"]):
        expect_refusal(lambda b=bad: build_identity(evidence_id=b))


@probe
def probe_malformed_digests_are_refused():
    for bad in ("", "nope", CONTENT.upper(), CONTENT[:-1], CONTENT + "0",
                "sha256:" + CONTENT, " " + CONTENT):
        expect_refusal(lambda b=bad: build_identity(content_digest=b))


@probe
def probe_temporal_orderings_are_enforced():
    # reversed observation window
    expect_refusal(
        lambda: EvidenceObservation(
            producer_id="p",
            collected_at=T_COL,
            observed_from=datetime(2026, 4, 1, 11, tzinfo=UTC),
            observed_to=datetime(2026, 4, 1, 10, tzinfo=UTC),
        )
    )
    # zero-length window (half-open)
    expect_refusal(
        lambda: EvidenceObservation(
            producer_id="p", collected_at=T_COL, observed_from=T_OBS, observed_to=T_OBS
        )
    )
    # collection before observation
    expect_refusal(
        lambda: EvidenceObservation(
            producer_id="p",
            collected_at=T_OBS - timedelta(seconds=1),
            observed_from=T_OBS,
        )
    )
    # reversed and zero-length validity interval
    expect_refusal(lambda: build_identity(valid_from=T_TO, valid_to=T_FROM))
    expect_refusal(lambda: build_identity(valid_from=T_FROM, valid_to=T_FROM))


@probe
def probe_half_open_validity_boundaries():
    ident = build_identity()
    tick = timedelta(microseconds=1)
    assert ident.is_valid_at(T_FROM) is True
    assert ident.temporal_refusal_at(T_FROM) is None
    assert ident.temporal_refusal_at(T_FROM - tick) is R.TRUSTED_EVIDENCE_NOT_YET_VALID
    assert ident.is_valid_at(T_TO - tick) is True
    assert ident.is_valid_at(T_TO) is False
    assert ident.temporal_refusal_at(T_TO) is R.TRUSTED_EVIDENCE_STALE


@probe
def probe_applicability_must_be_declared_not_omitted():
    expect_refusal(
        lambda: ApplicabilityCoordinate(
            declaration=ApplicabilityDeclaration.APPLICABLE, value=""
        )
    )
    expect_refusal(
        lambda: ApplicabilityCoordinate(
            declaration=ApplicabilityDeclaration.NOT_APPLICABLE, value="US"
        )
    )
    assert (
        build_identity(geography=ApplicabilityCoordinate.not_applicable()).canonical_digest()
        != build_identity(geography=ApplicabilityCoordinate.applicable("US")).canonical_digest()
    )


@probe
def probe_the_system_binding_pair_is_co_required_or_co_absent():
    def scope(**kw):
        base = dict(
            tenant_id="t",
            assessment_context_ref="c",
            assessment_context_digest=CONTEXT,
            subject_ref="s",
            assessment_purpose_ref="p",
            usage_scope_ref="u",
            assessed_system_applicability=ApplicabilityDeclaration.APPLICABLE,
            assessed_system_binding_ref="b",
            assessed_system_binding_digest=BINDING,
        )
        base.update(kw)
        return EvidenceScopeBinding(**base)

    expect_refusal(lambda: scope(assessed_system_binding_digest=""))
    expect_refusal(lambda: scope(assessed_system_binding_ref=""))
    expect_refusal(
        lambda: scope(
            assessed_system_applicability=ApplicabilityDeclaration.NOT_APPLICABLE
        )
    )
    ok = scope(
        assessed_system_applicability=ApplicabilityDeclaration.NOT_APPLICABLE,
        assessed_system_binding_ref="",
        assessed_system_binding_digest="",
    )
    assert ok.assessed_system_binding_ref == ""


@probe
def probe_custody_chains_reject_scalars_duplicates_and_blanks():
    for bad in ("abc", b"abc", {"a": 1}, 42, None):
        expect_refusal(
            lambda b=bad: EvidenceProvenanceChain(chain_ref="c", custody_refs=b)
        )
    expect_refusal(
        lambda: EvidenceProvenanceChain(chain_ref="c", custody_refs=("a", "a"))
    )
    expect_refusal(
        lambda: EvidenceProvenanceChain(chain_ref="c", custody_refs=("a", " "))
    )
    caller = ["a", "b"]
    chain = EvidenceProvenanceChain(chain_ref="c", custody_refs=caller)
    caller.append("c")
    assert chain.custody_refs == ("a", "b")


# --------------------------------------------------------------------------- #
# E. Lifecycle relation
# --------------------------------------------------------------------------- #
@probe
def probe_the_lifecycle_relation_is_closed_and_terminal_states_are_terminal():
    S = EvidenceLifecycleState
    admissible = {
        (S.PRODUCED, S.SUBMITTED), (S.PRODUCED, S.EXPIRED), (S.PRODUCED, S.REVOKED),
        (S.SUBMITTED, S.RETAINED), (S.SUBMITTED, S.EXPIRED), (S.SUBMITTED, S.REVOKED),
        (S.RETAINED, S.EXPIRED), (S.RETAINED, S.REVOKED),
    }
    for current in S:
        for proposed in S:
            expected = (current, proposed) in admissible
            assert is_valid_lifecycle_transition(current, proposed) is expected
            if not expected:
                try:
                    require_valid_lifecycle_transition(current, proposed)
                except TrustedEvidenceLifecycleError as exc:
                    assert (
                        exc.reason
                        is R.TRUSTED_EVIDENCE_INVALID_LIFECYCLE_TRANSITION
                    )
                else:
                    raise AssertionError(f"{current} -> {proposed} was not refused")
    assert EVIDENCE_LIFECYCLE_TRANSITIONS[S.REVOKED] == frozenset()
    assert EVIDENCE_LIFECYCLE_TRANSITIONS[S.EXPIRED] == frozenset()


@probe
def probe_no_verified_or_superseded_lifecycle_state_exists():
    values = {s.value for s in EvidenceLifecycleState}
    assert values == {"PRODUCED", "SUBMITTED", "RETAINED", "EXPIRED", "REVOKED"}
    assert not any("VERIF" in v or "SUPERSED" in v for v in values)
    assert not any("SUPERSED" in r.value for r in R)


# --------------------------------------------------------------------------- #
# F. Milestone boundary, from the public surface alone
# --------------------------------------------------------------------------- #
@probe
def probe_stage_six_cannot_be_requested_from_tap():
    expect_refusal(
        lambda: build_request(
            requested_trust_stages=(EvidenceTrustStage.POLICY_SUFFICIENT,)
        )
    )
    expect_refusal(lambda: build_request(requested_trust_stages=()))


@probe
def probe_no_verifier_receipt_or_key_type_is_exported():
    import ugence_trusted_evidence_authority.api as api_module

    for name in api_module.__all__:
        lowered = name.lower().replace("_", "")
        for forbidden in ("receipt", "verifier", "trustanchor", "keyring", "signer",
                          "signature", "verificationresult"):
            assert forbidden not in lowered, name


@probe
def probe_no_public_object_exposes_an_authorization_surface():
    import ugence_trusted_evidence_authority.api as api_module

    forbidden = {"authorize", "authorizes_deployment", "approve", "grant", "admit",
                 "sign", "verify", "revoke", "resolve", "register", "issue"}
    for name in api_module.__all__:
        obj = getattr(api_module, name)
        if isinstance(obj, type):
            assert not (set(dir(obj)) & forbidden), name


@probe
def probe_the_package_version_and_typing_marker():
    import pathlib

    import ugence_trusted_evidence_authority as pkg

    assert pkg.__version__ == "0.1.0"
    assert not hasattr(pkg, "CONTRACT_VERSION")
    assert (pathlib.Path(pkg.__file__).resolve().parent / "py.typed").is_file()


@probe
def probe_this_harness_imports_only_the_curated_api_and_the_stdlib():
    """This harness's own independence, asserted from inside it.

    Checks what *this file* imports, not what the package loads internally: the
    package is naturally free to import its own private modules, but a probe
    harness that reached into them — or into a test helper, fixture or conftest
    — would only re-confirm the suite's own assumptions.
    """

    import ast
    import pathlib

    for forbidden in ("_builders", "conftest"):
        assert forbidden not in sys.modules, forbidden

    source = pathlib.Path(__file__).read_text(encoding="utf-8")
    stdlib = set(getattr(sys, "stdlib_module_names", set()))
    imported: set = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert not node.level, "this harness uses no relative import"
            imported.add(node.module)

    for module in imported:
        root = module.split(".")[0]
        if root in stdlib or root == "__future__":
            continue
        assert module in (
            "ugence_trusted_evidence_authority",
            "ugence_trusted_evidence_authority.api",
        ), f"probe harness imports a non-curated module: {module}"


def main() -> int:
    print(f"trusted-evidence adversarial probes: {_RUN} probes run")
    if _FAILURES:
        print(f"\n{len(_FAILURES)} FAILED:")
        for failure in _FAILURES:
            print(f"  - {failure}")
        return 1
    print("ALL TRUSTED-EVIDENCE ADVERSARIAL PROBES PASSED ✔")
    return 0


if __name__ == "__main__":
    sys.exit(main())
