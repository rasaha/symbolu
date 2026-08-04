"""Security tests: authorization, existence non-disclosure, session, input, jobs."""

from __future__ import annotations

import uuid

import pytest

from helpers import register_and_login
from ugence_dilchat.domain.enums import AuditAction
from ugence_dilchat.jobs import JobScopeRevoked, run_shared_write_job


def _hdr(auth: dict) -> dict:
    return {"Authorization": auth["Authorization"]}


async def _pair(client):
    a = await register_and_login(client)
    b = await register_and_login(client)
    token = (await client.post("/v1/couples/invitations", headers=_hdr(a))).json()["token"]
    couple = (
        await client.post(f"/v1/couples/invitations/{token}/accept", headers=_hdr(b))
    ).json()
    return a, b, couple


async def _make_artifact(client, granter, couple_id) -> str:
    consent = await client.post(
        "/v1/consents",
        json={"couple_id": couple_id, "artifact_type": "bounded_summary",
              "bounded_summary": "s"},
        headers=_hdr(granter),
    )
    art = await client.post(
        "/v1/shared-artifacts",
        json={"consent_event_id": consent.json()["consent_event_id"], "payload_snapshot": "x"},
        headers=_hdr(granter),
    )
    return art.json()["artifact_id"]


# --- object-id guessing & existence non-disclosure ------------------------- #
async def test_random_artifact_id_returns_404(ctx):
    auth = await register_and_login(ctx.client)
    r = await ctx.client.get(f"/v1/shared-artifacts/{uuid.uuid4()}", headers=_hdr(auth))
    assert r.status_code == 404


async def test_stranger_cannot_learn_other_couples_artifact_exists(ctx):
    a, b, couple = await _pair(ctx.client)
    artifact_id = await _make_artifact(ctx.client, a, couple["couple_id"])
    stranger = await register_and_login(ctx.client)
    r = await ctx.client.get(f"/v1/shared-artifacts/{artifact_id}", headers=_hdr(stranger))
    # 404 (not 403): the stranger cannot distinguish "exists but forbidden" from "absent".
    assert r.status_code == 404
    assert r.json()["code"] == "NOT_FOUND"


async def test_stranger_cannot_unpair_others_couple(ctx):
    a, b, couple = await _pair(ctx.client)
    stranger = await register_and_login(ctx.client)
    r = await ctx.client.post(
        f"/v1/couples/{couple['couple_id']}/unpair", headers=_hdr(stranger)
    )
    assert r.status_code == 404  # existence non-disclosure, not 403


# --- session lifecycle ----------------------------------------------------- #
async def test_revoked_session_rejected(ctx):
    auth = await register_and_login(ctx.client)
    assert (await ctx.client.get("/v1/users/me", headers=_hdr(auth))).status_code == 200
    await ctx.client.post("/v1/auth/logout", headers=_hdr(auth))
    after = await ctx.client.get("/v1/users/me", headers=_hdr(auth))
    assert after.status_code == 401
    assert after.json()["code"] == "AUTH_SESSION_REVOKED"


async def test_logout_all_revokes_every_session(ctx):
    auth = await register_and_login(ctx.client)
    await ctx.client.post("/v1/auth/logout-all", headers=_hdr(auth))
    assert (await ctx.client.get("/v1/users/me", headers=_hdr(auth))).status_code == 401


async def test_expired_access_token_rejected(ctx):
    auth = await register_and_login(ctx.client)
    # Decode the live token to reuse its sid/sub, then mint an EXPIRED one with the
    # app's own signing key.
    ts = ctx.app.state.token_service
    claims = ts.verify_access_token(auth["Authorization"].split()[1])
    ts._access_ttl = -10  # expire immediately
    expired = ts.issue_access_token(uuid.UUID(claims["sub"]), uuid.UUID(claims["sid"]))
    ts._access_ttl = 600
    r = await ctx.client.get("/v1/users/me", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401
    assert r.json()["code"] == "AUTH_TOKEN_EXPIRED"


async def test_missing_and_malformed_bearer(ctx):
    assert (await ctx.client.get("/v1/users/me")).status_code == 401
    r = await ctx.client.get("/v1/users/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert r.status_code == 401
    assert r.json()["code"] == "AUTH_TOKEN_INVALID"


# --- input validation ------------------------------------------------------ #
async def test_short_password_rejected(ctx):
    r = await ctx.client.post(
        "/v1/auth/register", json={"email": "x@example.com", "password": "short"}
    )
    assert r.status_code == 422


async def test_malformed_email_rejected(ctx):
    r = await ctx.client.post(
        "/v1/auth/register", json={"email": "notanemail", "password": "correcthorse7!"}
    )
    assert r.status_code == 422


async def test_oversized_payload_rejected(ctx):
    a, b, couple = await _pair(ctx.client)
    consent = await ctx.client.post(
        "/v1/consents",
        json={"couple_id": couple["couple_id"], "artifact_type": "bounded_summary",
              "bounded_summary": "s"},
        headers=_hdr(a),
    )
    r = await ctx.client.post(
        "/v1/shared-artifacts",
        json={"consent_event_id": consent.json()["consent_event_id"],
              "payload_snapshot": "z" * 9000},
        headers=_hdr(a),
    )
    assert r.status_code == 422


async def test_malformed_uuid_path_rejected(ctx):
    auth = await register_and_login(ctx.client)
    r = await ctx.client.get("/v1/shared-artifacts/not-a-uuid", headers=_hdr(auth))
    assert r.status_code == 422


# --- stale background-job authorization (DEC-027) -------------------------- #
async def test_stale_job_authorization_is_revalidated(ctx):
    a, b, couple = await _pair(ctx.client)
    cid = uuid.UUID(couple["couple_id"])
    actor = uuid.UUID(
        ctx.app.state.token_service.verify_access_token(a["Authorization"].split()[1])["sub"]
    )
    # Job was "queued" while authorized. Now the couple unpairs.
    await ctx.client.post(f"/v1/couples/{couple['couple_id']}/unpair", headers=_hdr(a))

    wrote = {"value": False}

    async def write_fn(session):
        wrote["value"] = True

    with pytest.raises(JobScopeRevoked):
        await run_shared_write_job(
            ctx.sessionmaker, couple_id=cid, actor_user_id=actor, write_fn=write_fn
        )
    assert wrote["value"] is False  # write never happened

    # The abort was audited.
    import sqlalchemy as sa

    from ugence_dilchat.infrastructure.orm import AuditEvent

    async with ctx.sessionmaker() as s:
        count = await s.scalar(
            sa.select(sa.func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == AuditAction.JOB_WRITE_ABORTED_SCOPE.value)
        )
    assert count == 1


# --- rate limiting (interface deferred) ------------------------------------ #
def test_rate_limit_error_code_interface_exists():
    # Actual rate limiting is deferred; the error-model hook exists for it.
    from ugence_dilchat.errors import ErrorCode

    assert ErrorCode.RATE_LIMITED.value == "RATE_LIMITED"
