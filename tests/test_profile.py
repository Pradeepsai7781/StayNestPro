
def register_and_get_access_token(client, user_data):
    register_response = client.post(
        "/auth/register",
        json=user_data,
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/auth/login",
        json={
            "email": user_data["email"],
            "password": user_data["password"],
        },
    )
    assert login_response.status_code == 200

    return login_response.json()["access_token"]


def test_profile_requires_authentication(client):
    response = client.get("/profile/me")
    assert response.status_code == 401


def test_customer_can_view_own_profile(client, test_user):
    token = register_and_get_access_token(client, test_user)

    response = client.get(
        "/profile/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == test_user["email"]
    assert response.json()["city"] is None


def test_customer_can_update_own_profile(client, test_user):
    token = register_and_get_access_token(client, test_user)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.patch(
        "/profile/me",
        headers=headers,
        json={
            "full_name": "Updated Customer",
            "city": "Bengaluru",
            "country": "India",
        },
    )

    assert response.status_code == 200
    assert response.json()["full_name"] == "Updated Customer"
    assert response.json()["city"] == "Bengaluru"
    assert response.json()["country"] == "India"

    # Confirm the changes persist in the database.
    profile = client.get("/profile/me", headers=headers)
    assert profile.status_code == 200
    assert profile.json()["city"] == "Bengaluru"


def test_empty_profile_update_rejected(client, test_user):
    token = register_and_get_access_token(client, test_user)

    response = client.patch(
        "/profile/me",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )

    assert response.status_code == 400


def test_invalid_name_rejected(client, test_user):
    token = register_and_get_access_token(client, test_user)

    response = client.patch(
        "/profile/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"full_name": "A"},
    )

    assert response.status_code == 422


def test_customer_cannot_change_role(client, test_user):
    token = register_and_get_access_token(client, test_user)

    response = client.patch(
        "/profile/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"role": "ADMIN"},
    )

    # The role field is not part of the update schema.
    assert response.status_code == 400
