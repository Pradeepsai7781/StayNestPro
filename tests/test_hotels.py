
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import (
    Hotel,
    HotelImage,
    HotelReview,
    HotelStatus,
    Reservation,
    ReservationStatus,
    Room,
    RoomStatus,
    RoomType,
    RoomTypeCategory,
    User,
    UserRole,
)


def register_user(
    client: TestClient,
    full_name: str,
    email: str,
    password: str,
) -> None:
    response = client.post(
        "/auth/register",
        json={
            "full_name": full_name,
            "email": email,
            "password": password,
        },
    )
    assert response.status_code == 201, response.text


def login_user(
    client: TestClient,
    email: str,
    password: str,
) -> str:
    response = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def make_hotel_owner(db_session: Session, email: str) -> User:
    user = (
        db_session.query(User)
        .filter(User.email == email)
        .first()
    )
    assert user is not None

    user.role = UserRole.HOTEL_OWNER
    db_session.commit()
    db_session.refresh(user)
    return user


def hotel_payload():
    return {
        "name": "Test Hotel",
        "description": "Hotel for automated testing",
        "email": "hotel.test@example.com",
        "phone_number": "9876543210",
        "address": "10 Test Street",
        "city": "Bengaluru",
        "state": "Karnataka",
        "postal_code": "560001",
        "country": "India",
    }


def create_owner_and_get_token(client, db_session, email):
    password = "OwnerTest123!"

    register_user(
        client,
        "Test Hotel Owner",
        email,
        password,
    )
    make_hotel_owner(db_session, email)

    return login_user(client, email, password)


def test_hotel_owner_can_register_hotel(
    client,
    db_session,
):
    token = create_owner_and_get_token(
        client,
        db_session,
        "owner1@example.com",
    )

    response = client.post(
        "/hotels/",
        json=hotel_payload(),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201, response.text
    assert response.json()["name"] == "Test Hotel"
    assert response.json()["status"] == "PENDING"


def test_customer_cannot_register_hotel(client, test_user):
    register_user(
        client,
        test_user["full_name"],
        test_user["email"],
        test_user["password"],
    )
    token = login_user(
        client,
        test_user["email"],
        test_user["password"],
    )

    response = client.post(
        "/hotels/",
        json=hotel_payload(),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_customer_cannot_update_hotel(client, test_user):
    register_user(
        client,
        test_user["full_name"],
        test_user["email"],
        test_user["password"],
    )
    token = login_user(
        client,
        test_user["email"],
        test_user["password"],
    )

    response = client.patch(
        "/hotels/1",
        json={"city": "Bengaluru"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_hotel_owner_can_list_and_update_own_hotel(
    client,
    db_session,
):
    token = create_owner_and_get_token(
        client,
        db_session,
        "owner2@example.com",
    )
    headers = {"Authorization": f"Bearer {token}"}

    create_response = client.post(
        "/hotels/",
        json=hotel_payload(),
        headers=headers,
    )
    assert create_response.status_code == 201, create_response.text
    hotel_id = create_response.json()["id"]

    list_response = client.get("/hotels/mine", headers=headers)
    assert list_response.status_code == 200
    assert any(h["id"] == hotel_id for h in list_response.json())

    get_response = client.get(
        f"/hotels/{hotel_id}",
        headers=headers,
    )
    assert get_response.status_code == 200

    update_response = client.patch(
        f"/hotels/{hotel_id}",
        json={
            "description": "Updated description",
            "city": "Mysuru",
        },
        headers=headers,
    )

    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["description"] == "Updated description"
    assert update_response.json()["city"] == "Mysuru"
    assert update_response.json()["status"] == "PENDING"


def test_hotel_owner_cannot_update_another_owners_hotel(
    client,
    db_session,
):
    token = create_owner_and_get_token(
        client,
        db_session,
        "owner3@example.com",
    )

    other_owner = User(
        full_name="Another Owner",
        email="another.owner@example.com",
        hashed_password="unused-test-hash",
        role=UserRole.HOTEL_OWNER,
        is_active=True,
        is_email_verified=False,
    )
    db_session.add(other_owner)
    db_session.flush()

    other_hotel = Hotel(
        **hotel_payload(),
        owner_id=other_owner.id,
        status=HotelStatus.PENDING,
    )
    db_session.add(other_hotel)
    db_session.commit()
    db_session.refresh(other_hotel)

    response = client.patch(
        f"/hotels/{other_hotel.id}",
        json={"city": "Chennai"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    db_session.refresh(other_hotel)
    assert other_hotel.city == "Bengaluru"


# --------------------------------------------------
# MODULE 11: UNPUBLISHED HOTEL ACCESS CONTROL
# --------------------------------------------------

def test_unpublished_hotel_is_hidden_from_public_but_visible_to_owner(
    client,
    db_session,
):
    token = create_owner_and_get_token(
        client,
        db_session,
        "module11owner@example.com",
    )
    headers = {"Authorization": f"Bearer {token}"}

    create_response = client.post(
        "/hotels/",
        json=hotel_payload(),
        headers=headers,
    )
    assert create_response.status_code == 201, create_response.text
    hotel_id = create_response.json()["id"]

    response = client.get(f"/hotels/{hotel_id}/details")
    assert response.status_code == 404

    response = client.get(
        f"/hotels/{hotel_id}/details",
        headers=headers,
    )
    assert response.status_code == 200, response.text


# --------------------------------------------------
# MODULE 11: REVIEWS IN HOTEL DETAILS
# --------------------------------------------------

def test_hotel_details_returns_saved_reviews(
    client,
    db_session,
):
    token = create_owner_and_get_token(
        client,
        db_session,
        "reviewowner@example.com",
    )
    headers = {"Authorization": f"Bearer {token}"}

    create_response = client.post(
        "/hotels/",
        json=hotel_payload(),
        headers=headers,
    )
    assert create_response.status_code == 201, create_response.text
    hotel_id = create_response.json()["id"]

    hotel = (
        db_session.query(Hotel)
        .filter(Hotel.id == hotel_id)
        .first()
    )
    assert hotel is not None

    hotel.status = HotelStatus.APPROVED
    db_session.commit()

    owner = (
        db_session.query(User)
        .filter(User.email == "reviewowner@example.com")
        .first()
    )
    assert owner is not None

    room_type = RoomType(
        hotel_id=hotel_id,
        name=RoomTypeCategory.SINGLE,
        description="Room type for review test",
        price_per_night=Decimal("100.00"),
        capacity=2,
    )
    db_session.add(room_type)
    db_session.flush()

    room = Room(
        hotel_id=hotel_id,
        room_type_id=room_type.id,
        room_number="101",
        capacity=2,
        status=RoomStatus.AVAILABLE,
    )
    db_session.add(room)
    db_session.flush()

    today = date.today()
    reservation = Reservation(
        room_id=room.id,
        customer_id=owner.id,
        check_in=today - timedelta(days=3),
        check_out=today - timedelta(days=1),
        guest_count=1,
        total_price=Decimal("100.00"),
        status=ReservationStatus.COMPLETED,
    )
    db_session.add(reservation)
    db_session.flush()

    review = HotelReview(
        reservation_id=reservation.id,
        hotel_id=hotel_id,
        user_id=owner.id,
        rating=5,
        comment="Excellent stay",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(review)
    db_session.commit()

    response = client.get(f"/hotels/{hotel_id}/details")

    assert response.status_code == 200, response.text

    reviews = response.json()["reviews"]
    assert len(reviews) == 1
    assert reviews[0]["hotel_id"] == hotel_id
    assert reviews[0]["rating"] == 5
    assert reviews[0]["comment"] == "Excellent stay"


# --------------------------------------------------
# MODULE 11: GALLERY IMAGE METADATA
# --------------------------------------------------

def test_hotel_owner_can_manage_gallery_metadata(
    client,
    db_session,
):
    token = create_owner_and_get_token(
        client,
        db_session,
        "galleryowner@example.com",
    )
    headers = {"Authorization": f"Bearer {token}"}

    create_response = client.post(
        "/hotels/",
        json=hotel_payload(),
        headers=headers,
    )
    assert create_response.status_code == 201, create_response.text
    hotel_id = create_response.json()["id"]

    create_image_response = client.post(
        f"/hotels/{hotel_id}/images",
        json={
            "image_url": "https://example.com/hotel-room.jpg",
            "caption": "Main room",
            "category": "ROOM",
            "display_order": 1,
            "is_primary": True,
        },
        headers=headers,
    )
    assert create_image_response.status_code == 201, create_image_response.text

    image_id = create_image_response.json()["id"]
    assert create_image_response.json()["hotel_id"] == hotel_id
    assert create_image_response.json()["category"] == "ROOM"
    assert create_image_response.json()["display_order"] == 1
    assert create_image_response.json()["is_primary"] is True

    list_response = client.get(
        f"/hotels/{hotel_id}/images",
        headers=headers,
    )
    assert list_response.status_code == 200, list_response.text
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["caption"] == "Main room"

    update_response = client.patch(
        f"/hotels/{hotel_id}/images/{image_id}",
        json={
            "caption": "Updated room caption",
            "display_order": 2,
        },
        headers=headers,
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["caption"] == "Updated room caption"
    assert update_response.json()["display_order"] == 2

    delete_response = client.delete(
        f"/hotels/{hotel_id}/images/{image_id}",
        headers=headers,
    )
    assert delete_response.status_code == 204

    final_list_response = client.get(
        f"/hotels/{hotel_id}/images",
        headers=headers,
    )
    assert final_list_response.status_code == 200
    assert final_list_response.json() == []
