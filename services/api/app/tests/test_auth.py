from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_signup_login_me_logout_cycle(client):
    # signup
    r = await client.post(
        "/auth/signup",
        json={"email": "user@example.com", "password": "supersecret1"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["user"]["email"] == "user@example.com"
    assert body["workspace"]["name"]
    assert "access_token" in r.cookies
    csrf = r.cookies.get("csrf_token")
    assert csrf

    # protected /auth/me works
    r = await client.get("/auth/me")
    assert r.status_code == 200
    assert r.json()["user"]["email"] == "user@example.com"

    # protected /api/docs works
    r = await client.get("/api/docs")
    assert r.status_code == 200
    assert r.json()["items"] == []

    # logout — needs CSRF header (state-changing while authed)
    r = await client.post("/auth/logout", headers={"x-csrf-token": csrf})
    assert r.status_code == 204

    # subsequent /auth/me is unauthenticated
    client.cookies.clear()
    r = await client.get("/auth/me")
    assert r.status_code == 401


async def test_signup_rejects_duplicate_email(client):
    payload = {"email": "dup@example.com", "password": "supersecret1"}
    r1 = await client.post("/auth/signup", json=payload)
    assert r1.status_code == 201
    client.cookies.clear()
    r2 = await client.post("/auth/signup", json=payload)
    assert r2.status_code == 409


async def test_login_wrong_password_returns_401(client):
    await client.post(
        "/auth/signup",
        json={"email": "wp@example.com", "password": "supersecret1"},
    )
    client.cookies.clear()
    r = await client.post(
        "/auth/login",
        json={"email": "wp@example.com", "password": "WRONG-password"},
    )
    assert r.status_code == 401


async def test_unauthed_protected_route_returns_401(client):
    r = await client.get("/api/docs")
    assert r.status_code == 401


async def test_csrf_required_for_state_change_when_authed(client):
    await client.post(
        "/auth/signup",
        json={"email": "csrf@example.com", "password": "supersecret1"},
    )
    # logout without csrf header → 403
    r = await client.post("/auth/logout")
    assert r.status_code == 403
