from __future__ import annotations

import pytest
from sqlalchemy import select

from manifold.models.user import UserSession


async def _login(client, username: str, password: str):
    return await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
        headers={"x-device-label": "pytest-laptop"},
    )


@pytest.mark.asyncio
async def test_login_success(client, test_user):
    user, password = test_user

    response = await _login(client, user.username, password)

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "access_token" in client.cookies
    assert "refresh_token" in client.cookies
    assert "device_binding" in client.cookies


@pytest.mark.asyncio
async def test_login_wrong_password(client, test_user):
    user, _ = test_user

    response = await _login(client, user.username, "wrongpass")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_user(client):
    response = await _login(client, "nobody", "pass")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_authenticated(client, test_user):
    user, password = test_user

    await _login(client, user.username, password)
    response = await client.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert response.json()["username"] == user.username


@pytest.mark.asyncio
async def test_get_me_unauthenticated(client):
    response = await client.get("/api/v1/auth/me")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rotates_access_token(client, test_user):
    user, password = test_user

    await _login(client, user.username, password)
    first_refresh_token = client.cookies["refresh_token"]
    response = await client.post("/api/v1/auth/refresh")

    assert response.status_code == 200
    assert "access_token" in response.json()
    assert client.cookies["refresh_token"] != first_refresh_token
    assert "refresh_token" in client.cookies


@pytest.mark.asyncio
async def test_logout_clears_session(client, test_user):
    user, password = test_user

    await _login(client, user.username, password)
    response = await client.post("/api/v1/auth/logout")

    assert response.status_code == 204
    me_response = await client.get("/api/v1/auth/me")
    assert me_response.status_code == 401


@pytest.mark.asyncio
async def test_change_password(client, test_user):
    user, password = test_user

    await _login(client, user.username, password)
    old_refresh_token = client.cookies["refresh_token"]
    response = await client.patch(
        "/api/v1/auth/me/password",
        json={"current_password": password, "new_password": "newpass123"},
    )

    assert response.status_code == 204
    refresh_response = await client.post(
        "/api/v1/auth/refresh",
        cookies={
            "refresh_token": old_refresh_token,
            "device_binding": client.cookies["device_binding"],
        },
    )
    assert refresh_response.status_code == 401
    await client.post("/api/v1/auth/logout")
    old_login = await _login(client, user.username, password)
    assert old_login.status_code == 401
    new_login = await _login(client, user.username, "newpass123")
    assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_list_sessions_and_revoke_session(client, test_user, db_session):
    user, password = test_user

    await _login(client, user.username, password)
    sessions_response = await client.get("/api/v1/auth/sessions")

    assert sessions_response.status_code == 200
    sessions = sessions_response.json()
    assert len(sessions) == 1
    session_id = sessions[0]["id"]

    revoke_response = await client.delete(f"/api/v1/auth/sessions/{session_id}")
    assert revoke_response.status_code == 204

    query = await db_session.execute(select(UserSession).where(UserSession.id == session_id))
    session_row = query.scalar_one()
    assert session_row.revoked_at is not None


@pytest.mark.asyncio
async def test_revoke_other_sessions_keeps_current(client, test_user):
    user, password = test_user

    await _login(client, user.username, password)
    other_client = client.__class__(transport=client._transport, base_url="http://testserver")
    async with other_client:
        await _login(other_client, user.username, password)
        response = await client.post("/api/v1/auth/sessions/revoke-others")
        assert response.status_code == 204
        primary_sessions = await client.get("/api/v1/auth/sessions")
        other_sessions = await other_client.get("/api/v1/auth/sessions")
        other_refresh = await other_client.post("/api/v1/auth/refresh")

    assert primary_sessions.status_code == 200
    assert len(primary_sessions.json()) == 1
    assert other_sessions.status_code == 200
    assert len(other_sessions.json()) == 1
    assert other_refresh.status_code == 401
