"""Make this package, the review service it implements a port of, and the review
service's own test fixtures importable in a bare source checkout, mirroring the
sibling integration packages' convention.

Every instant in this suite is explicit: a settable clock is injected into the
adapter and into the review service, and no test reads the wall clock.
"""

from __future__ import annotations

import pathlib
import sys
from datetime import datetime, timedelta, timezone

import pytest

HERE = pathlib.Path(__file__).resolve().parent
PKG = HERE.parent
REPO = PKG.parents[2]

for path in (
    PKG / "src",
    REPO / "packages" / "integration" / "governed-review-service" / "src",
    REPO / "packages" / "integration" / "governed-review" / "src",
    REPO / "packages" / "integration" / "control-plane-root" / "src",
    REPO / "packages" / "integration" / "approval-workflow" / "src",
    REPO / "packages" / "integration" / "authority-directory" / "src",
    REPO / "packages" / "governance-contracts" / "src",
    REPO / "packages" / "integration" / "agent-runtime-governance" / "src",
    REPO / "packages" / "integration" / "risk-authority-runtime" / "src",
    REPO / "packages" / "integration" / "risk-authority-status-runtime" / "src",
    REPO / "packages" / "runtime" / "agent-runtime" / "src",
    REPO / "packages" / "risk_authority" / "src",
    REPO / "packages" / "capabilities" / "decision-authority" / "src",
    REPO / "packages" / "providers" / "actiongate" / "src",
    REPO / "packages" / "integration" / "durable-execution" / "src",
    REPO / "packages" / "integration" / "governed-review" / "tests",
    REPO / "packages" / "integration" / "governed-review-service" / "tests",
    HERE,
):
    p = str(path)
    if path.is_dir() and p not in sys.path:
        sys.path.insert(0, p)

from _issuer import InProcessIssuer  # noqa: E402

from ugence_approver_identity_jwt import AdapterConfig, JwtApproverIdentityAdapter  # noqa: E402

NOW = datetime(2026, 9, 5, 9, 0, tzinfo=timezone.utc)
AUDIENCE = "ugence-governed-review-service"
STUDIO_AUDIENCE = "ugence-governance-studio"
TENANT_CLAIM = "ugence_tenant"
ACTOR_CLAIM = "ugence_actor"
HUMAN_VALUE = "human-sign-in"


class Clock:
    """A settable instant. ``datetime`` is what gets injected."""

    def __init__(self, start: datetime = NOW) -> None:
        self.now = start

    def datetime(self) -> datetime:
        return self.now

    def advance(self, **kwargs) -> None:
        self.now = self.now + timedelta(**kwargs)


def base_claims(issuer: InProcessIssuer, **over) -> dict:
    """A complete, well-formed access-token payload for Alice at ``NOW``."""

    claims = {
        "iss": issuer.issuer, "sub": "alice", "aud": issuer.audience,
        "iat": int((NOW - timedelta(seconds=60)).timestamp()),
        "exp": int((NOW + timedelta(hours=1)).timestamp()),
        "auth_time": int((NOW - timedelta(minutes=2)).timestamp()),
        "jti": "jti-0001", "amr": ["pwd", "otp"], "acr": "urn:example:loa2",
        TENANT_CLAIM: "tenant-a", ACTOR_CLAIM: HUMAN_VALUE,
    }
    for key, value in over.items():
        if value is None:
            claims.pop(key, None)
        else:
            claims[key] = value
    return claims


def config_for(issuer: InProcessIssuer, **over) -> AdapterConfig:
    kwargs = dict(issuer=issuer.issuer, audience=issuer.audience, jwks_url=issuer.jwks_url,
                  tenant_claim=TENANT_CLAIM, actor_type_claim=ACTOR_CLAIM,
                  human_actor_type_value=HUMAN_VALUE)
    kwargs.update(over)
    return AdapterConfig(**kwargs)


@pytest.fixture()
def issuer():
    iss = InProcessIssuer(audience=AUDIENCE)
    iss.add_key("RS256", kid="rsa-1")
    iss.start()
    try:
        yield iss
    finally:
        iss.stop()


@pytest.fixture()
def clock():
    return Clock()


@pytest.fixture()
def adapter(issuer, clock):
    return JwtApproverIdentityAdapter(config_for(issuer), clock=clock.datetime)
