from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.core.security import verify_password
from app.models import AuthToken, User


def register_and_login(client, user_data):
    with patch("app.api.v1.auth._send_email_safely"):
        registration = client.post("/auth/register", json=user_data)

    assert registration.status_code == 201

    login = client.post(
        "/auth/login",
        json={
            "email": user_data["email"],
            "password": user_data["password"],
        },
    )
    assert login.status_code == 200
    return login.json()


def get_raw_token_from_email_mock(send_mock):
    """Extract a raw token from the mocked email body."""
    assert send_mock.called
    body = send_mock.call_args.args[2]

    for line in body.splitlines():
        candidate = line.strip()
        if len(candidate) >= 40 and " " not in candidate:
            return candidate

    pytest.fail("No raw token was found in the mocked email body")


def get_auth_token(db_session, email, purpose):
    user = db_session.query(User).filter(User.email == email).first()
    assert user is not None

    record = (
        db_session.query(AuthToken)
        .filter(
            AuthToken.user_id == user.id,
            AuthToken.purpose == purpose,
            AuthToken.used_at.is_(None),
        )
        .order_by(AuthToken.id.desc())
        .first()
    )
    assert record is not None
    return record, user


def test_register_customer(client, test_user):
    with patch("app.api.v1.auth._send_email_safely"):
        response = client.post("/auth/register", json=test_user)

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == test_user["email"]
    assert data["role"] == "CUSTOMER"
    assert "hashed_password" not in data
    assert "password" not in data


def test_duplicate_email_rejected(client, test_user):
    with patch("app.api.v1.auth._send_email_safely"):
        first = client.post("/auth/register", json=test_user)
        second = client.post("/auth/register", json=test_user)

    assert first.status_code == 201
    assert second.status_code == 409


def test_login_and_invalid_password(client, test_user):
    register_and_login(client, test_user)

    response = client.post(
        "/auth/login",
        json={
            "email": test_user["email"],
            "password": "WrongPassword123!",
        },
    )
    assert response.status_code == 401


def test_profile_requires_access_token(client, test_user):
    response = client.get("/auth/me")
    assert response.status_code == 401

    tokens = register_and_login(client, test_user)

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == test_user["email"]


def test_customer_cannot_access_admin_endpoint(client, test_user):
    tokens = register_and_login(client, test_user)

    response = client.get(
        "/auth/admin-check",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 403


def test_refresh_rotation_and_logout(client, test_user):
    tokens = register_and_login(client, test_user)

    refresh_response = client.post(
        "/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_response.status_code == 200

    new_tokens = refresh_response.json()
    assert new_tokens["access_token"]
    assert new_tokens["refresh_token"]

    old_refresh_response = client.post(
        "/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert old_refresh_response.status_code == 401

    logout_response = client.post(
        "/auth/logout",
        json={"refresh_token": new_tokens["refresh_token"]},
    )
    assert logout_response.status_code == 200

    revoked_response = client.post(
        "/auth/refresh",
        json={"refresh_token": new_tokens["refresh_token"]},
    )
    assert revoked_response.status_code == 401


def test_forgot_password_response_does_not_reveal_account(client):
    with patch("app.api.v1.auth._send_email_safely") as send_mock:
        existing = client.post(
            "/auth/forgot-password",
            json={"email": "customer@example.com"},
        )
        assert existing.status_code == 200
        assert not send_mock.called

    missing = client.post(
        "/auth/forgot-password",
        json={"email": "unknown@example.com"},
    )

    assert missing.status_code == 200
    assert existing.json() == missing.json()


def test_verify_email_token_once(client, db_session, test_user):
    with patch("app.api.v1.auth._send_email_safely"):
        registration = client.post("/auth/register", json=test_user)
    assert registration.status_code == 201

    with patch("app.api.v1.auth._send_email_safely") as send_mock:
        response = client.post(
            "/auth/resend-verification",
            json={"email": test_user["email"]},
        )

    assert response.status_code == 200
    raw_token = get_raw_token_from_email_mock(send_mock)

    verify_response = client.post(
        "/auth/verify-email",
        json={"token": raw_token},
    )
    assert verify_response.status_code == 200

    user = (
        db_session.query(User)
        .filter(User.email == test_user["email"])
        .first()
    )
    assert user.is_email_verified is True

    second_use = client.post(
        "/auth/verify-email",
        json={"token": raw_token},
    )
    assert second_use.status_code == 400


def test_reset_password_changes_password_and_revokes_refresh_tokens(
    client,
    db_session,
    test_user,
):
    with patch("app.api.v1.auth._send_email_safely"):
        registration = client.post("/auth/register", json=test_user)
    assert registration.status_code == 201

    login = client.post(
        "/auth/login",
        json={
            "email": test_user["email"],
            "password": test_user["password"],
        },
    )
    assert login.status_code == 200
    old_refresh_token = login.json()["refresh_token"]

    with patch("app.api.v1.auth._send_email_safely") as send_mock:
        response = client.post(
            "/auth/forgot-password",
            json={"email": test_user["email"]},
        )

    assert response.status_code == 200
    raw_token = get_raw_token_from_email_mock(send_mock)

    reset_response = client.post(
        "/auth/reset-password",
        json={
            "token": raw_token,
            "new_password": "NewSecurePassword123!",
        },
    )
    assert reset_response.status_code == 200

    user = (
        db_session.query(User)
        .filter(User.email == test_user["email"])
        .first()
    )
    assert verify_password("NewSecurePassword123!", user.hashed_password)

    old_refresh_response = client.post(
        "/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )
    assert old_refresh_response.status_code == 401

    reused_token_response = client.post(
        "/auth/reset-password",
        json={
            "token": raw_token,
            "new_password": "AnotherSecurePassword123!",
        },
    )
    assert reused_token_response.status_code == 400


def test_invalid_verification_token_is_rejected(client):
    response = client.post(
        "/auth/verify-email",
        json={"token": "invalid-token-value-that-is-long-enough"},
    )
    assert response.status_code == 400


def test_invalid_reset_token_is_rejected(client):
    response = client.post(
        "/auth/reset-password",
        json={
            "token": "invalid-token-value-that-is-long-enough",
            "new_password": "NewSecurePassword123!",
        },
    )
    assert response.status_code == 400


def test_expired_verification_token_is_rejected(
    client,
    db_session,
    test_user,
):
    with patch("app.api.v1.auth._send_email_safely"):
        client.post("/auth/register", json=test_user)

    with patch("app.api.v1.auth._send_email_safely") as send_mock:
        client.post(
            "/auth/resend-verification",
            json={"email": test_user["email"]},
        )

    raw_token = get_raw_token_from_email_mock(send_mock)
    record, _ = get_auth_token(
        db_session,
        test_user["email"],
        "email_verification",
    )

    record.expires_at = (
        datetime.now(timezone.utc) - timedelta(minutes=1)
    ).replace(tzinfo=None)
    db_session.commit()

    response = client.post(
        "/auth/verify-email",
        json={"token": raw_token},
    )
    assert response.status_code == 400


def test_expired_password_reset_token_is_rejected(
    client,
    db_session,
    test_user,
):
    with patch("app.api.v1.auth._send_email_safely"):
        client.post("/auth/register", json=test_user)

    with patch("app.api.v1.auth._send_email_safely") as send_mock:
        client.post(
            "/auth/forgot-password",
            json={"email": test_user["email"]},
        )

    raw_token = get_raw_token_from_email_mock(send_mock)
    record, user = get_auth_token(
        db_session,
        test_user["email"],
        "password_reset",
    )
    old_password_hash = user.hashed_password

    record.expires_at = (
        datetime.now(timezone.utc) - timedelta(minutes=1)
    ).replace(tzinfo=None)
    db_session.commit()

    response = client.post(
        "/auth/reset-password",
        json={
            "token": raw_token,
            "new_password": "NewSecurePassword123!",
        },
    )

    assert response.status_code == 400

    db_session.refresh(user)
    assert user.hashed_password == old_password_hash
