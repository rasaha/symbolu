"""Phase 4B F-2: exactly what ``subject_digest`` covers — and what it does not.

Why this file exists (independent-audit finding F-2). ``subject_digest =
digest(SubjectBinding)`` and ``SubjectBinding`` carries only ``{schema_version, tenant_id,
subject_id, subject_type, recommendation_digest, context_digest}``. It therefore binds the
canonical **subject / subject-context identity** and nothing else.

It does **not** bind the request's *routing* fields:

    requested_purpose · requested_domain · requested_risk_class · requested_scope ·
    evidence_references

Substituting any one of them leaves ``subject_digest`` **byte-identical**, and the
subject-aware resolver then routes on the substituted value. That is not a defect — those
fields are bound by ``request_digest``, which is a different commitment with a different
purpose — but it means **subject-digest equality is not whole-request authenticity**, and
no document may imply otherwise.

These tests pin the factual claim so the documentation cannot drift away from it, and pin
the documentation itself so the claim cannot be quietly restated as authenticity.

Naming note: nothing here is named "authentic". Every assertion is about *coverage*.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from risk_authority.domain import RiskClass, Scope
from risk_authority.integrations import (
    SubjectBinding,
    SubjectRiskDisposition,
)

from ..contract.test_subject_context_contracts import adr_context, v2_request
from .test_phase4b_context_revalidation import (
    audited_production_seam,
    resealed_request,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
RA_README = REPO_ROOT / "packages" / "risk_authority" / "README.md"
PHASE4_ADR = (REPO_ROOT / "docs" / "architecture"
              / "ADR_CLOUD_SCALING_RISK_AUTHORITY_INTEGRATION_PHASE4.md")

# The routing fields the subject digest does NOT cover, each with a substituted value
# that is itself perfectly valid — so nothing else can be blamed for the outcome.
UNCOVERED_SUBSTITUTIONS = [
    pytest.param("requested_purpose", "some.other.purpose", id="requested_purpose"),
    pytest.param("requested_domain", "some_other_domain", id="requested_domain"),
    pytest.param("requested_risk_class", RiskClass.LOW, id="requested_risk_class"),
    pytest.param("requested_scope", Scope(purposes=("attacker.chosen.purpose",)),
                 id="requested_scope"),
    pytest.param("evidence_references", ("sha256:zzz", "sha256:yyy"),
                 id="evidence_references"),
]


def genuine_subject_digest() -> str:
    """The subject digest of a genuine, fully valid request."""

    return v2_request().subject_digest


# ------------------------------------------------- (1)-(3) coverage is what it is
def test_the_genuine_subject_digest_is_the_binding_digest_and_nothing_more():
    """Establishes the baseline: subject_digest is exactly digest(SubjectBinding)."""

    request = v2_request()
    binding = SubjectBinding(
        tenant_id=request.tenant_id, subject_id=request.subject_id,
        subject_type=request.subject_type,
        recommendation_digest=request.recommendation_digest,
        context_digest=request.subject_context.digest())
    assert request.subject_digest == binding.digest()

    # The complete set of fields the digest is computed over — no routing field appears.
    assert set(binding.to_canonical_dict()) == {
        "schema_version", "tenant_id", "subject_id", "subject_type",
        "recommendation_digest", "context_digest",
    }


@pytest.mark.parametrize("field_name,substituted", UNCOVERED_SUBSTITUTIONS)
def test_substituting_an_uncovered_routing_field_leaves_the_subject_digest_unchanged(
        field_name, substituted):
    """(2) and (3): substitute one field, confirm the subject digest does not move."""

    baseline = genuine_subject_digest()
    substituted_request = v2_request(**{field_name: substituted})

    assert substituted_request.subject_digest == baseline, (
        f"{field_name} unexpectedly moved the subject digest")
    # ...while the value really did change, so this is not a no-op substitution.
    assert getattr(substituted_request, field_name) == substituted


@pytest.mark.parametrize("field_name,substituted", UNCOVERED_SUBSTITUTIONS)
def test_the_request_digest_does_move_for_the_same_substitution(field_name, substituted):
    """The other half of the honest statement: these fields ARE bound — by request_digest.

    Without this, the file would read as though the fields were unbound entirely, which
    would be its own overclaim in the opposite direction."""

    assert v2_request(**{field_name: substituted}).digest() != v2_request().digest()


# ------------------------------------- (4) the resolver routes on the substituted value
@pytest.mark.parametrize("field_name,substituted", UNCOVERED_SUBSTITUTIONS)
def test_the_resolver_receives_the_substituted_routing_value(field_name, substituted):
    """(4): an otherwise-valid substituted request is admitted and routes on the new value.

    This is the consequence that makes the documentation necessary: binding validation
    passes — the subject digest still reconciles — and policy is then resolved using the
    substituted routing field."""

    seam, counters = audited_production_seam()
    request = resealed_request(adr_context(), **{field_name: substituted})

    # The subject digest is untouched by the substitution, so binding validation passes.
    assert request.subject_digest == resealed_request(adr_context()).subject_digest

    result = seam.evaluate(request)

    # Admitted: it was not refused as an invalid subject/binding.
    assert result.non_decision_reason is None or (
        result.non_decision_reason.value != "invalid_subject")
    assert counters.policy == 1, "policy resolution should have been reached"

    # (5) ...and no execution authorization was produced by any of it.
    assert counters.envelope_issuer == 0 and counters.actiongate == 0
    assert result.executable is False
    assert result.authorization_performed is False and result.envelope_issued is False


def test_the_resolver_sees_the_substituted_purpose_and_domain_verbatim():
    """Sharpens (4): the substituted values arrive at the resolver, not the originals."""

    seam, counters = audited_production_seam()

    class _Recorder:
        is_production_authoritative = True
        is_subject_context_aware = True
        seen: dict = {}

        def resolve_with_subject_context(self, *, tenant_id, purpose, domain, risk_class,
                                         requested_scope, subject_context,
                                         evidence_references, now):
            _Recorder.seen = {"purpose": purpose, "domain": domain,
                              "risk_class": risk_class, "scope": requested_scope,
                              "evidence_references": evidence_references}
            counters.policy += 1
            return None  # no policy -> fail closed; routing is what is under test

        def resolve(self, **kwargs):  # pragma: no cover
            raise AssertionError("v1 fallback must not occur for a v2 request")

    seam._policy_resolver = _Recorder()  # type: ignore[attr-defined]
    seam.evaluate(resealed_request(
        adr_context(),
        requested_purpose="attacker.purpose", requested_domain="attacker_domain",
        requested_risk_class=RiskClass.LOW,
        requested_scope=Scope(purposes=("attacker.purpose",)),
        evidence_references=("sha256:attacker",)))

    assert _Recorder.seen["purpose"] == "attacker.purpose"
    assert _Recorder.seen["domain"] == "attacker_domain"
    assert _Recorder.seen["risk_class"] is RiskClass.LOW
    assert _Recorder.seen["scope"].purposes == ("attacker.purpose",)
    assert _Recorder.seen["evidence_references"] == ("sha256:attacker",)


def test_no_execution_authorization_arises_from_any_substitution():
    """(5), stated once over the whole substitution set rather than per-case."""

    for field_name, substituted in [(p.values[0], p.values[1])
                                    for p in UNCOVERED_SUBSTITUTIONS]:
        seam, counters = audited_production_seam()
        result = seam.evaluate(resealed_request(adr_context(),
                                                **{field_name: substituted}))
        assert counters.envelope_issuer == 0, field_name
        assert counters.actiongate == 0, field_name
        assert result.executable is False, field_name
        serialized = result.to_canonical_dict()
        for flag in ("authorization_performed", "envelope_issued", "actiongate_invoked",
                     "actuation_performed", "effect_verified", "executable"):
            assert serialized[flag] is False, (field_name, flag)


def test_a_substituted_request_still_terminates_at_a_non_executable_decision():
    seam, _ = audited_production_seam()
    result = seam.evaluate(resealed_request(
        adr_context(), requested_purpose="attacker.purpose"))
    assert result.disposition in set(SubjectRiskDisposition)
    assert result.executable is False


# --------------------------------- (6) the documentation must not overclaim
NORMATIVE_CLAIMS = [
    "binds the canonical subject / subject-context identity only",
    "subject-digest equality is not whole-request authenticity",
]

UNCOVERED_FIELD_NAMES = ["requested_purpose", "requested_domain", "requested_risk_class",
                         "requested_scope", "evidence_references"]


@pytest.mark.parametrize("document", [RA_README, PHASE4_ADR],
                         ids=["risk-authority-readme", "phase4-adr"])
def test_the_document_states_the_subject_digest_coverage_boundary(document):
    """(6): both authoritative documents must carry the explicit non-coverage statement."""

    text = document.read_text(encoding="utf-8")
    for claim in NORMATIVE_CLAIMS:
        assert claim in text, f"{document.name} is missing the normative claim: {claim}"
    for field_name in UNCOVERED_FIELD_NAMES:
        assert field_name in text, f"{document.name} does not list {field_name}"


@pytest.mark.parametrize("document", [RA_README, PHASE4_ADR],
                         ids=["risk-authority-readme", "phase4-adr"])
def test_the_document_does_not_claim_scope_is_bound_into_the_subject_digest(document):
    """The specific overclaim F-2 found, pinned so it cannot return.

    The §15 threat-model row previously read "`tenant_id` + scope bound into
    `subject_digest`". Scope is not bound into it."""

    text = document.read_text(encoding="utf-8")
    for overclaim in (
        "scope bound into `subject_digest`",
        "scope is bound into `subject_digest`",
        "`requested_scope` is bound into `subject_digest`",
    ):
        assert overclaim not in text, f"{document.name} overclaims: {overclaim}"


@pytest.mark.parametrize("document", [RA_README, PHASE4_ADR],
                         ids=["risk-authority-readme", "phase4-adr"])
def test_the_document_defers_recommendation_authenticity_to_the_adapter(document):
    text = document.read_text(encoding="utf-8")
    assert "authenticity" in text
    # The deferral must be explicit, not merely implied.
    assert ("adapter" in text and "rec.digest()" in text), (
        f"{document.name} must state that recommendation authenticity remains the "
        f"adapter's deferred responsibility")
