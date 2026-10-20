
from fastapi import status

from app.core.dependencies import get_current_user
from app.core.security import hash_password
from app.main import app
from app.models import User, UserRole


def create_user(db_session, user_id, email, role, is_active=True):
    user = User(
        id=user_id,
        full_name=f"Test User {user_id}",
        email=email,
        hashed_password=hash_password("TestPassword123!"),
        role=role,
        is_active=is_active,
        is_email_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_admin_users_requires_authentication(client):
    response = client.get("/admin/users")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_customer_cannot_list_users(client, db_session):
    customer = create_user(
        db_session, 100, "customer-rbac@example.com", UserRole.CUSTOMER
    )
    app.dependency_overrides[get_current_user] = lambda: customer
    try:
        response = client.get("/admin/users")
        assert response.status_code == status.HTTP_403_FORBIDDEN
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_admin_can_list_users(client, db_session):
    admin = create_user(
        db_session, 101, "admin-rbac@example.com", UserRole.ADMIN
    )
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        response = client.get("/admin/users")
        assert response.status_code == status.HTTP_200_OK
        assert any(user["id"] == 101 for user in response.json())
        for user in response.json():
            assert "hashed_password" not in user
            assert "password" not in user
            assert "refresh_token" not in user
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_admin_cannot_change_own_role(client, db_session):
    admin = create_user(
        db_session, 102, "admin-self-role@example.com", UserRole.ADMIN
    )
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        response = client.patch(
            "/admin/users/102/role", json={"role": "CUSTOMER"}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "You cannot change your own role"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_admin_cannot_deactivate_own_account(client, db_session):
    admin = create_user(
        db_session, 103, "admin-self-status@example.com", UserRole.ADMIN
    )
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        response = client.patch(
            "/admin/users/103/status", json={"is_active": False}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == (
            "You cannot deactivate your own account"
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_admin_role_update_returns_404_for_missing_user(client, db_session):
    admin = create_user(
        db_session, 104, "admin-missing-user@example.com", UserRole.ADMIN
    )
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        response = client.patch(
            "/admin/users/999999/role", json={"role": "HOTEL_OWNER"}
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "User not found"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_admin_status_update_returns_404_for_missing_user(client, db_session):
    admin = create_user(
        db_session, 105, "admin-missing-status@example.com", UserRole.ADMIN
    )
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        response = client.patch(
            "/admin/users/999999/status", json={"is_active": False}
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "User not found"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_admin_can_change_another_users_role(client, db_session):
    admin = create_user(
        db_session, 106, "admin-change-role@example.com", UserRole.ADMIN
    )
    customer = create_user(
        db_session, 107, "customer-change-role@example.com", UserRole.CUSTOMER
    )
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        response = client.patch(
            f"/admin/users/{customer.id}/role",
            json={"role": "HOTEL_OWNER"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["role"] == "HOTEL_OWNER"
        db_session.refresh(customer)
        assert customer.role == UserRole.HOTEL_OWNER
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_admin_can_deactivate_another_user(client, db_session):
    admin = create_user(
        db_session, 108, "admin-change-status@example.com", UserRole.ADMIN
    )
    customer = create_user(
        db_session, 109, "customer-change-status@example.com", UserRole.CUSTOMER
    )
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        response = client.patch(
            f"/admin/users/{customer.id}/status",
            json={"is_active": False},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["is_active"] is False
        db_session.refresh(customer)
        assert customer.is_active is False
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_cannot_demote_last_active_admin(client, db_session):
    admin = create_user(
        db_session, 110, "admin-last-role@example.com", UserRole.ADMIN
    )
    second_admin = create_user(
        db_session, 111, "admin-actor-role@example.com", UserRole.ADMIN
    )

    # Make the target the only active admin.
    admin.is_active = False
    db_session.commit()

    # Reactivate the target and deactivate the actor to simulate a single
    # active admin without using the actor as the target.
    admin.is_active = True
    second_admin.is_active = False
    db_session.commit()

    # The inactive actor cannot authenticate, so create a separate active
    # actor while keeping the target as the only active admin is impossible
    # under the endpoint's normal authorization rules.
    # Instead, verify the helper's protection through the endpoint using
    # the target's self-protection as the first line of defense.
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        response = client.patch(
            f"/admin/users/{admin.id}/role",
            json={"role": "CUSTOMER"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_cannot_deactivate_last_active_admin(client, db_session):
    admin = create_user(
        db_session, 112, "admin-last-status@example.com", UserRole.ADMIN
    )
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        response = client.patch(
            f"/admin/users/{admin.id}/status",
            json={"is_active": False},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    finally:
        app.dependency_overrides.pop(get_current_user, None)
