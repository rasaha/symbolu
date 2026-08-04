"""Integration tests: end-to-end flows over the ASGI app."""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa

from helpers import VALID_BIRTH_PROFILE, register_and_login
from ugence_dilchat.infrastructure.orm import BirthProfile


def _hdr(auth: dict) -> dict:
    return {"Authorization": auth["Authorization"]}


async def _create_profile(client, auth, **overrides):
    body = {**VALID_BIRTH_PROFILE, **overrides}
    return await client.post("/v1/birth-profiles", json=body, headers=_hdr(auth))


async def _pair(client):
    a = await register_and_login(client)
    b = await register_and_login(client)
    inv = await client.post("/v1/couples/invitations", headers=_hdr(a))
    assert inv.status_code == 201, inv.text
    token = inv.json()["token"]
    accept = await client.post(f"/v1/couples/invitations/{token}/accept", headers=_hdr(b))
    assert accept.status_code == 200, accept.text
    return a, b, accept.json()


# --- flagship flow --------------------------------------------------------- #
async def test_register_login_profile_natal(ctx):
    auth = await register_and_login(ctx.client)
    me = await ctx.client.get("/v1/users/me", headers=_hdr(auth))
    assert me.status_code == 200 and me.json()["email"] == auth["_email"]

    prof = await _create_profile(ctx.client, auth)
    assert prof.status_code == 201, prof.text
    assert prof.json()["input_confidence"] == 1.0  # EXACT

    natal = await ctx.client.post("/v1/natal/moon", headers=_hdr(auth))
    assert natal.status_code == 201, natal.text
    body = natal.json()
    assert 0 <= body["rashi_index"] <= 11
    assert 0 <= body["nakshatra_index"] <= 26
    assert 1 <= body["pada"] <= 4
    assert body["provenance"]["ayanamsa"] == "lahiri"

    # Idempotent: recompute returns the same immutable snapshot.
    natal2 = await ctx.client.post("/v1/natal/moon", headers=_hdr(auth))
    assert natal2.json()["snapshot_id"] == body["snapshot_id"]


async def test_birth_profile_versioning(ctx):
    auth = await register_and_login(ctx.client)
    r1 = await _create_profile(ctx.client, auth)
    assert r1.json()["version"] == 1
    r2 = await ctx.client.patch(
        "/v1/birth-profiles/me", json={**VALID_BIRTH_PROFILE, "preferred_name": "Asha2"},
        headers=_hdr(auth),
    )
    assert r2.status_code == 201
    assert r2.json()["version"] == 2
    latest = await ctx.client.get("/v1/birth-profiles/me", headers=_hdr(auth))
    assert latest.json()["preferred_name"] == "Asha2"


async def test_unknown_birth_time_low_confidence_and_no_instant(ctx):
    auth = await register_and_login(ctx.client)
    r = await _create_profile(
        ctx.client, auth, birth_time_local=None, birth_time_precision="UNKNOWN"
    )
    assert r.status_code == 201
    body = r.json()
    assert body["has_birth_time"] is False
    assert body["utc_birth_instant"] is None
    assert body["input_confidence"] == pytest.approx(0.2)
    # Natal still computable but flagged with an explicit assumption.
    natal = await ctx.client.post("/v1/natal/moon", headers=_hdr(auth))
    assert natal.status_code == 201
    assert natal.json()["provenance"]["time_assumption"] == "ASSUMED_NOON_UTC_UNKNOWN_PRECISION"
    assert natal.json()["provenance"]["input_confidence"] == pytest.approx(0.2)


async def test_ambiguous_time_requires_resolution_then_accepts(ctx):
    auth = await register_and_login(ctx.client)
    bad = await _create_profile(
        ctx.client, auth, birth_date="2021-11-07", birth_time_local="01:30:00",
        iana_timezone="America/New_York",
    )
    assert bad.status_code == 422
    assert bad.json()["code"] == "AMBIGUOUS_LOCAL_TIME"
    ok = await _create_profile(
        ctx.client, auth, birth_date="2021-11-07", birth_time_local="01:30:00",
        iana_timezone="America/New_York", ambiguity_resolution="EARLIER",
    )
    assert ok.status_code == 201


# --- pairing --------------------------------------------------------------- #
async def test_pairing_and_current_couple(ctx):
    a, b, couple = await _pair(ctx.client)
    assert couple["status"] == "ACTIVE"
    assert {m["scope_slot"] for m in couple["members"]} == {"A", "B"}
    cur = await ctx.client.get("/v1/couples/current", headers=_hdr(a))
    assert cur.status_code == 200 and cur.json()["couple_id"] == couple["couple_id"]


async def test_invitation_single_use(ctx):
    a = await register_and_login(ctx.client)
    b = await register_and_login(ctx.client)
    c = await register_and_login(ctx.client)
    token = (await ctx.client.post("/v1/couples/invitations", headers=_hdr(a))).json()["token"]
    first = await ctx.client.post(f"/v1/couples/invitations/{token}/accept", headers=_hdr(b))
    assert first.status_code == 200
    second = await ctx.client.post(f"/v1/couples/invitations/{token}/accept", headers=_hdr(c))
    assert second.status_code == 409
    assert second.json()["code"] == "INVITATION_USED"


async def test_unpair_revokes_shared_access_immediately(ctx):
    a, b, couple = await _pair(ctx.client)
    cid = couple["couple_id"]
    # Create a shared artifact via consent while active.
    consent = await ctx.client.post(
        "/v1/consents",
        json={"couple_id": cid, "artifact_type": "agreed_statement",
              "bounded_summary": "We agree to weekly check-ins."},
        headers=_hdr(a),
    )
    assert consent.status_code == 201, consent.text
    art = await ctx.client.post(
        "/v1/shared-artifacts",
        json={"consent_event_id": consent.json()["consent_event_id"],
              "payload_snapshot": "Weekly check-ins agreed."},
        headers=_hdr(a),
    )
    assert art.status_code == 201
    artifact_id = art.json()["artifact_id"]
    # Both members can read while active.
    read = await ctx.client.get(f"/v1/shared-artifacts/{artifact_id}", headers=_hdr(b))
    assert read.status_code == 200
    # Unpair.
    unpair = await ctx.client.post(f"/v1/couples/{cid}/unpair", headers=_hdr(a))
    assert unpair.status_code == 204
    # Shared access denied immediately for former members.
    after = await ctx.client.get(f"/v1/shared-artifacts/{artifact_id}", headers=_hdr(b))
    assert after.status_code == 403
    assert after.json()["code"] == "COUPLE_NOT_ACTIVE"


# --- consent / shared artifact / DEC-028 ----------------------------------- #
async def test_shared_artifact_survives_private_source_deletion(ctx):
    a, b, couple = await _pair(ctx.client)
    cid = couple["couple_id"]
    # Give partner A a private birth profile (a private-scope resource).
    await _create_profile(ctx.client, a)
    consent = await ctx.client.post(
        "/v1/consents",
        json={"couple_id": cid, "artifact_type": "bounded_summary",
              "bounded_summary": "Shared a value summary."},
        headers=_hdr(a),
    )
    art = await ctx.client.post(
        "/v1/shared-artifacts",
        json={"consent_event_id": consent.json()["consent_event_id"],
              "payload_snapshot": "Immutable snapshot content."},
        headers=_hdr(a),
    )
    artifact_id = art.json()["artifact_id"]

    # Delete A's private birth profile(s) directly (simulating private-source deletion).
    async with ctx.sessionmaker() as s:
        await s.execute(sa.delete(BirthProfile))
        await s.commit()

    # The shared artifact is unaffected and unchanged.
    after = await ctx.client.get(f"/v1/shared-artifacts/{artifact_id}", headers=_hdr(b))
    assert after.status_code == 200
    assert after.json()["payload_snapshot"] == "Immutable snapshot content."


async def test_shared_artifacts_have_no_fk_to_private_tables(ctx):
    # Structural DEC-028 guarantee: no FK from shared_artifacts to a private table.
    from ugence_dilchat.infrastructure.orm import SharedArtifact

    targets = {fk.column.table.name for fk in SharedArtifact.__table__.foreign_keys}
    assert "birth_profiles" not in targets
    assert targets <= {"couples", "consent_events"}


# --- refresh rotation & reuse ---------------------------------------------- #
async def test_refresh_rotation_and_reuse_rejected(ctx):
    auth = await register_and_login(ctx.client)
    old_refresh = auth["_refresh"]
    r = await ctx.client.post("/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert r.status_code == 200
    new_refresh = r.json()["refresh_token"]
    assert new_refresh != old_refresh
    # New refresh works.
    again = await ctx.client.post("/v1/auth/refresh", json={"refresh_token": new_refresh})
    assert again.status_code == 200
    # Reusing the OLD (already-rotated) refresh token is rejected as reuse.
    reuse = await ctx.client.post("/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert reuse.status_code == 401
    assert reuse.json()["code"] == "AUTH_REFRESH_REUSE"


async def test_transaction_rollback_on_error(ctx):
    # A service error must not persist partial writes. Register, then trigger a
    # duplicate-email registration (conflict) and assert no second user exists.
    email = f"dup_{uuid.uuid4().hex[:8]}@example.com"
    body = {"email": email, "password": "correcthorse7!"}
    r1 = await ctx.client.post("/v1/auth/register", json=body)
    assert r1.status_code == 201
    r2 = await ctx.client.post("/v1/auth/register", json=body)
    assert r2.status_code == 409
    from ugence_dilchat.infrastructure.orm import User
    async with ctx.sessionmaker() as s:
        count = await s.scalar(
            sa.select(sa.func.count()).select_from(User).where(User.email == email)
        )
    assert count == 1
