from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from ugence_model_egress_unit import (
    CallBudget,
    CredentialLease,
    CredentialRequest,
    CustodyRefusal,
    CustodyRefused,
    EgressRequest,
    MinimizedUnit,
    reference_clearance,
)
from ugence_model_egress_provider_openai import DESIGNATED_MODEL, FakeTransport, OpenAIResponsesProvider

NOW = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)
PROFILE = "ugence-meu-validation/openai"

#: A fixture secret that must never appear in any state, record or repr. Not a key
#: shape, so the repository's key-shape scan never mistakes the fixture for one.
SECRET = "MARKER-THIS-MUST-NOT-LEAK-" + uuid.uuid4().hex


class MarkerCustody:
    """Leases a known marker so a test can prove it never leaks. Never production."""

    NON_PRODUCTION = True
    maturity = "FIXTURE_ONLY"
    custody_authority_id = "test-marker-custody"
    credential_profile = PROFILE
    is_production_authoritative = False
    max_credential_age = timedelta(days=1)

    def __init__(self, *, refuse: bool = False, production_authoritative: bool = False):
        self.refuse = refuse
        self.production_authoritative = production_authoritative
        self.requests = []

    def materialize(self, request: CredentialRequest, *, now, production=False):
        self.requests.append(request)
        if self.refuse:
            raise CustodyRefused(CustodyRefusal.CUSTODY_UNAVAILABLE, "test refusal")
        return CredentialLease(
            lease_id="lease-" + request.digest()[:12], custody_authority_id=self.custody_authority_id,
            credential_profile=self.credential_profile, vendor="openai", tenant_id=request.tenant_id,
            secret_version_ref="projects/p/secrets/s/versions/3", issued_at=now,
            expires_at=now + timedelta(minutes=5),
            is_production_authoritative=self.production_authoritative, _secret=SECRET)


def make_request(*, tenant=None, vendor="openai", model=DESIGNATED_MODEL, text="synthetic probe",
                 tokens=4, parameters=None, not_valid_after=None, units=None):
    tenant = tenant or uuid.uuid4()
    params = {"max_output_tokens": 256} if parameters is None else parameters
    return EgressRequest.create(
        request_id=uuid.uuid4(), tenant_id=tenant, correlation_id=uuid.uuid4(),
        submitted_at=NOW, not_valid_after=not_valid_after or NOW + timedelta(hours=1),
        authorization=reference_clearance(tenant_id=tenant, vendor=vendor, model=model),
        minimized_context=units if units is not None else [MinimizedUnit("u-1", text, tokens)],
        parameters=params)


@pytest.fixture
def transport():
    return FakeTransport()


@pytest.fixture
def custody():
    return MarkerCustody()


@pytest.fixture
def budget():
    return CallBudget()


@pytest.fixture
def provider(transport, custody, budget):
    return OpenAIResponsesProvider(transport=transport, custody=custody, budget=budget,
                                   credential_profile=PROFILE)
