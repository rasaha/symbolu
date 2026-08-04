"""Shared test helpers (importable via pythonpath=['tests'])."""

from __future__ import annotations

import uuid

from httpx import AsyncClient

VALID_BIRTH_PROFILE = {
    "preferred_name": "Asha",
    "birth_date": "1990-05-15",
    "birth_time_local": "14:30:00",
    "birth_time_precision": "EXACT",
    "birthplace_label": "Mumbai, India",
    "latitude": 19.076,
    "longitude": 72.8777,
    "iana_timezone": "Asia/Kolkata",
}


async def register_and_login(
    client: AsyncClient, email: str | None = None, password: str = "correcthorse7!"
) -> dict:
    """Register + login a fresh user; return an Authorization header dict."""
    email = email or f"user_{uuid.uuid4().hex[:10]}@example.com"
    r = await client.post("/v1/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    r = await client.post("/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    tokens = r.json()
    return {
        "Authorization": f"Bearer {tokens['access_token']}",
        "_refresh": tokens["refresh_token"],
        "_email": email,
        "_password": password,
    }
