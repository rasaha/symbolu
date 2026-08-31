"""Device-registration API behaviour (Phase 3C device model).

A registration is a device-installation endpoint owned by the user, never a
session credential: responses never echo the token, one user holds multiple
devices, a token maps to one ACTIVE registration globally (new sign-in on a
handed-over device displaces the previous owner), logout revokes this
session's devices, logout-all revokes them all.
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa

from helpers import register_and_login
from ugence_dilchat.infrastructure.devices_orm import ChatDevice
from ugence_dilchat.infrastructure.orm import AuditEvent


def _hdr(auth: dict) -> dict:
    return {"Authorization": auth["Authorization"]}


async def _register(client, auth, token: str, platform: str = "IOS"):
    return await client.post(
        "/v1/devices", headers=_hdr(auth), json={"push_token": token, "platform": platform}
    )


async def test_register_list_revoke_without_ever_echoing_the_token(ctx):
    a = await register_and_login(ctx.client)
    r = await _register(ctx.client, a, "ExponentPushToken[alpha]")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "ACTIVE"
    assert "push_token" not in body and "alpha" not in r.text

    r2 = await _register(ctx.client, a, "ExponentPushToken[beta]", platform="ANDROID")
    assert r2.status_code == 201  # multiple devices per user

    listed = await ctx.client.get("/v1/devices", headers=_hdr(a))
    assert listed.status_code == 200
    devices = listed.json()["devices"]
    assert len(devices) == 2
    assert "alpha" not in listed.text and "beta" not in listed.text

    # Idempotent re-registration of the same token keeps one row.
    again = await _register(ctx.client, a, "ExponentPushToken[alpha]")
    assert again.status_code == 201
    assert again.json()["device_id"] == body["device_id"]

    # Owner revoke, idempotent; foreign/unknown ids are 404 (no disclosure).
    for _ in range(2):
        r3 = await ctx.client.delete(f"/v1/devices/{body['device_id']}", headers=_hdr(a))
        assert r3.status_code == 200 and r3.json()["status"] == "REVOKED"
    stranger = await register_and_login(ctx.client)
    r4 = await ctx.client.delete(f"/v1/devices/{body['device_id']}", headers=_hdr(stranger))
    assert r4.status_code == 404
    r5 = await ctx.client.delete(f"/v1/devices/{uuid.uuid4()}", headers=_hdr(a))
    assert r5.status_code == 404

    # Audit is body-free and token-free.
    async with ctx.sessionmaker() as s:
        audits = list((await s.execute(sa.select(AuditEvent))).scalars().all())
        assert any(x.action == "DEVICE_REGISTERED" for x in audits)
        assert any(x.action == "DEVICE_REVOKED" for x in audits)
        for x in audits:
            assert "alpha" not in str(x.__dict__) and "beta" not in str(x.__dict__)


async def test_token_maps_to_one_active_registration_globally(ctx):
    shared = "ExponentPushToken[handed-over-device]"
    a = await register_and_login(ctx.client)
    b = await register_and_login(ctx.client)
    first = await _register(ctx.client, a, shared)
    assert first.status_code == 201
    # The device changes hands: B's registration displaces A's.
    second = await _register(ctx.client, b, shared)
    assert second.status_code == 201
    async with ctx.sessionmaker() as s:
        rows = list(
            (await s.execute(sa.select(ChatDevice).where(ChatDevice.push_token == shared)))
            .scalars().all()
        )
        active = [r for r in rows if r.status == "ACTIVE"]
        assert len(active) == 1  # never two active holders of one token
    # A's own list shows the displaced registration as revoked, not vanished.
    listed = await ctx.client.get("/v1/devices", headers=_hdr(a))
    assert [d["status"] for d in listed.json()["devices"]] == ["REVOKED"]


async def test_logout_revokes_this_sessions_devices_only(ctx):
    a = await register_and_login(ctx.client)
    r = await _register(ctx.client, a, "ExponentPushToken[phone]")
    assert r.status_code == 201
    # A second session (same account, different device) registers its own token.
    r = await ctx.client.post(
        "/v1/auth/login", json={"email": a["_email"], "password": a["_password"]}
    )
    other = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = await ctx.client.post(
        "/v1/devices", headers=other,
        json={"push_token": "ExponentPushToken[tablet]", "platform": "ANDROID"},
    )
    assert r.status_code == 201

    # Logout of the FIRST session revokes only the phone registration.
    r = await ctx.client.post("/v1/auth/logout", headers=_hdr(a))
    assert r.status_code == 204
    listed = await ctx.client.get("/v1/devices", headers=other)
    by_platform = {d["platform"]: d["status"] for d in listed.json()["devices"]}
    assert by_platform == {"IOS": "REVOKED", "ANDROID": "ACTIVE"}

    # Logout-all revokes every remaining registration.
    r = await ctx.client.post("/v1/auth/logout-all", headers=other)
    assert r.status_code == 204
    async with ctx.sessionmaker() as s:
        rows = list((await s.execute(sa.select(ChatDevice))).scalars().all())
        assert rows and all(x.status == "REVOKED" for x in rows)


async def test_validation_and_auth(ctx):
    a = await register_and_login(ctx.client)
    r = await ctx.client.post(
        "/v1/devices", headers=_hdr(a), json={"push_token": "x", "platform": "VISIONOS"}
    )
    assert r.status_code == 422  # unknown platform
    r = await ctx.client.post(
        "/v1/devices", headers=_hdr(a), json={"push_token": "bad\x00token", "platform": "IOS"}
    )
    assert r.status_code == 422  # control characters refused
    r = await ctx.client.post(
        "/v1/devices", json={"push_token": "t", "platform": "IOS"}
    )
    assert r.status_code == 401  # authentication required
