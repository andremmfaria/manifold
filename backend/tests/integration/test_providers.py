from __future__ import annotations

import pytest


async def _login(client, username: str, password: str):
    return await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )


@pytest.mark.asyncio
async def test_list_providers_includes_auth_kind(client, test_user):
    user, password = test_user
    await _login(client, user.username, password)

    response = await client.get("/api/v1/providers")
    assert response.status_code == 200
    providers = response.json()
    assert len(providers) >= 1

    by_type = {p["provider_type"]: p for p in providers}
    assert "json" in by_type, "json provider must be registered"
    assert by_type["json"]["auth_kind"] == "file"

    if "truelayer" in by_type:
        assert by_type["truelayer"]["auth_kind"] == "oauth"


@pytest.mark.asyncio
async def test_json_provider_auth_kind_field_present(client, test_user):
    user, password = test_user
    await _login(client, user.username, password)

    response = await client.get("/api/v1/providers")
    assert response.status_code == 200
    for provider in response.json():
        assert "auth_kind" in provider, f"auth_kind missing from {provider['provider_type']}"
