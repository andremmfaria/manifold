from __future__ import annotations

import pytest

from manifold.domain.users import create_user_record


async def _login(client, username: str, password: str):
    return await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )


@pytest.mark.asyncio
async def test_superadmin_can_list_and_create_users(client, superadmin_user):
    admin, password = superadmin_user
    await _login(client, admin.username, password)

    list_response = await client.get("/api/v1/users")
    assert list_response.status_code == 200
    assert any(item["username"] == admin.username for item in list_response.json())

    create_response = await client.post(
        "/api/v1/users",
        json={
            "username": "created-user",
            "password": "created-pass123",
            "role": "regular",
            "email": "created@example.com",
        },
    )
    assert create_response.status_code == 201
    assert create_response.json()["username"] == "created-user"


@pytest.mark.asyncio
async def test_superadmin_can_get_update_and_delete_user(client, superadmin_user):
    admin, password = superadmin_user
    await _login(client, admin.username, password)
    created = await client.post(
        "/api/v1/users",
        json={"username": "managed-user", "password": "managed-pass123", "role": "regular"},
    )
    user_id = created.json()["id"]

    get_response = await client.get(f"/api/v1/users/{user_id}")
    assert get_response.status_code == 200
    assert get_response.json()["username"] == "managed-user"

    update_response = await client.patch(
        f"/api/v1/users/{user_id}",
        json={"role": "superadmin", "must_change_password": True},
    )
    assert update_response.status_code == 200
    assert update_response.json()["role"] == "superadmin"
    assert update_response.json()["must_change_password"] is True

    delete_response = await client.delete(f"/api/v1/users/{user_id}")
    assert delete_response.status_code == 204


@pytest.mark.asyncio
async def test_regular_user_cannot_access_user_admin_endpoints(client, test_user):
    user, password = test_user
    await _login(client, user.username, password)

    response = await client.get("/api/v1/users")

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_user_can_manage_access_grants(client, test_user, another_user):
    user, password = test_user
    grantee, _ = another_user
    await _login(client, user.username, password)

    create_response = await client.post(
        "/api/v1/users/me/access",
        json={"grantee_user_id": str(grantee.id), "role": "viewer"},
    )
    assert create_response.status_code == 201
    grant_id = create_response.json()["id"]

    list_response = await client.get("/api/v1/users/me/access")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    delete_response = await client.delete(f"/api/v1/users/me/access/{grant_id}")
    assert delete_response.status_code == 204
    assert (await client.get("/api/v1/users/me/access")).json() == []


@pytest.mark.asyncio
async def test_user_cannot_self_grant_access(client, test_user):
    user, password = test_user
    await _login(client, user.username, password)

    response = await client.post(
        "/api/v1/users/me/access",
        json={"grantee_user_id": str(user.id), "role": "viewer"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_delete_last_superadmin_conflicts(client, superadmin_user):
    admin, password = superadmin_user
    await _login(client, admin.username, password)

    response = await client.delete(f"/api/v1/users/{admin.id}")

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_deactivated_user_cannot_log_in(client, superadmin_user, db_session):
    admin, password = superadmin_user
    regular = await create_user_record(
        username="to-deactivate",
        password="deactivate-pass123",
        role="regular",
        session=db_session,
    )
    await _login(client, admin.username, password)

    response = await client.patch(f"/api/v1/users/{regular.id}", json={"is_active": False})

    assert response.status_code == 200
    login_response = await _login(client, regular.username, "deactivate-pass123")
    assert login_response.status_code == 401
