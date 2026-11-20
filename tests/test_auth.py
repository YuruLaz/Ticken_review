EMAIL = "alice@example.com"
PASSWORD = "secret123"


async def register(client, **overrides):
    payload = {"email": EMAIL, "full_name": "Alice", "password": PASSWORD, **overrides}
    return await client.post("/auth/register", json=payload)


async def login(client, password=PASSWORD):
    # /auth/login takes form data, not JSON, because it follows the OAuth2 spec.
    return await client.post(
        "/auth/login", data={"username": EMAIL, "password": password}
    )


async def test_register_creates_customer(client):
    # Sending a role must not let anyone pick their own.
    response = await register(client, role="admin")

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == EMAIL
    assert body["role"] == "customer"
    assert "password" not in body and "hashed_password" not in body


async def test_register_duplicate_email_returns_409(client):
    await register(client)
    response = await register(client)
    assert response.status_code == 409


async def test_login_returns_token(client):
    await register(client)
    response = await login(client)

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


async def test_login_wrong_password_returns_401(client):
    await register(client)
    response = await login(client, password="wrong")
    assert response.status_code == 401


async def test_me_with_token_returns_user(client):
    await register(client)
    token = (await login(client)).json()["access_token"]

    response = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["email"] == EMAIL


async def test_me_without_token_returns_401(client):
    response = await client.get("/auth/me")
    assert response.status_code == 401
