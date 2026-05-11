import io

from sqlalchemy import text

from app.extensions import db
from app.models import Provider, RefreshToken, Role, User
from app.repositories import DELETED_USER_ID
from app.services.email_service import EmailService
from app.services.oauth_service import OAuthProfile, OAuthVerifier
from app.services.storage_service import StorageService


def register(client, email="ada@example.com", password="correct-password"):
    return client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "Ada Lovelace"},
    )


def test_register_and_login_issue_tokens(client):
    response = register(client)
    assert response.status_code == 201
    body = response.get_json()
    assert body["access_token"]
    assert body["refresh_token"]

    login = client.post("/auth/login", json={"email": "ada@example.com", "password": "correct-password"})
    assert login.status_code == 200
    assert login.get_json()["access_token"]


def test_login_rejects_invalid_password(client):
    register(client)

    response = client.post("/auth/login", json={"email": "ada@example.com", "password": "wrong"})

    assert response.status_code == 401
    assert response.get_json()["code"] == "INVALID_CREDENTIALS"


def test_login_handles_invalid_password_hash_without_500(client):
    register(client)
    user = User.query.filter_by(email="ada@example.com").one()
    user.password_hash = "not-a-valid-argon2-hash"
    db.session.commit()

    response = client.post("/auth/login", json={"email": "ada@example.com", "password": "correct-password"})

    assert response.status_code == 401
    assert response.get_json()["code"] == "INVALID_CREDENTIALS"


def test_oauth_google_links_existing_email_without_duplicate(client, monkeypatch):
    register(client, email="grace@example.com")

    def verified_google(_self, _payload):
        return OAuthProfile("google-123", "grace@example.com", "Grace Hopper", "https://example.com/avatar.png")

    monkeypatch.setattr(OAuthVerifier, "verify_google", verified_google)

    response = client.post("/auth/oauth/google", json={"id_token": "verified-by-provider"})

    assert response.status_code == 200
    assert User.query.count() == 1
    user = User.query.filter_by(email="grace@example.com").one()
    assert user.provider == Provider.GOOGLE
    assert user.provider_id == "google-123"
    assert response.get_json()["refresh_token"]


def test_password_login_reports_social_account_for_oauth_user(client, monkeypatch):
    def verified_google(_self, _payload):
        return OAuthProfile("google-456", "oauth-only@example.com", "OAuth User", "https://example.com/avatar.png")

    monkeypatch.setattr(OAuthVerifier, "verify_google", verified_google)

    oauth_login = client.post("/auth/oauth/google", json={"id_token": "verified-by-provider"})
    assert oauth_login.status_code == 200

    password_login = client.post("/auth/login", json={"email": "oauth-only@example.com", "password": "does-not-matter"})
    assert password_login.status_code == 400
    assert password_login.get_json()["code"] == "PASSWORD_LOGIN_NOT_AVAILABLE"


def test_refresh_rotates_token_and_reuse_revokes_sessions(client):
    created = register(client).get_json()

    rotated = client.post("/auth/refresh", json={"refresh_token": created["refresh_token"]})

    assert rotated.status_code == 200
    new_refresh = rotated.get_json()["refresh_token"]
    assert new_refresh != created["refresh_token"]

    reused = client.post("/auth/refresh", json={"refresh_token": created["refresh_token"]})

    assert reused.status_code == 401
    assert reused.get_json()["code"] == "REFRESH_TOKEN_REUSE"
    assert RefreshToken.query.filter_by(revoked=False).count() == 0


def test_logout_revokes_refresh_token(client):
    created = register(client).get_json()

    logout = client.post("/auth/logout", json={"refresh_token": created["refresh_token"]})

    assert logout.status_code == 204
    assert db.session.query(RefreshToken).filter_by(revoked=True).count() == 1
    refreshed = client.post("/auth/refresh", json={"refresh_token": created["refresh_token"]})
    assert refreshed.status_code == 401


def test_forgot_and_reset_password(client, monkeypatch):
    register(client)
    sent = {}

    def fake_send(_self, to_email, reset_url, full_name=None):
        sent["to_email"] = to_email
        sent["reset_url"] = reset_url
        sent["full_name"] = full_name

    monkeypatch.setattr(EmailService, "send_password_reset", fake_send)

    forgot = client.post("/auth/forgot-password", json={"email": "ada@example.com"})
    assert forgot.status_code == 200
    assert sent["to_email"] == "ada@example.com"

    token = sent["reset_url"].split("token=", 1)[1]
    reset = client.post("/auth/reset-password", json={"token": token, "password": "new-correct-password"})
    assert reset.status_code == 200

    old_login = client.post("/auth/login", json={"email": "ada@example.com", "password": "correct-password"})
    assert old_login.status_code == 401
    new_login = client.post("/auth/login", json={"email": "ada@example.com", "password": "new-correct-password"})
    assert new_login.status_code == 200


def test_forgot_password_does_not_reveal_unknown_email(client, monkeypatch):
    called = False

    def fake_send(*_args, **_kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(EmailService, "send_password_reset", fake_send)

    response = client.post("/auth/forgot-password", json={"email": "missing@example.com"})
    assert response.status_code == 200
    assert called is False


def test_get_and_update_me(client):
    created = register(client).get_json()
    headers = {"Authorization": f"Bearer {created['access_token']}"}

    me = client.get("/users/me", headers=headers)
    assert me.status_code == 200
    assert me.get_json()["email"] == "ada@example.com"

    updated = client.patch(
        "/users/me",
        headers=headers,
        json={
            "full_name": "Ada Byron",
            "gender": "female",
            "age": 25,
            "address": "District 1, Ho Chi Minh City",
            "phone_number": "+84999999999",
            "bio": "Loves concerts and late-night movies.",
        },
    )
    assert updated.status_code == 200
    assert updated.get_json()["full_name"] == "Ada Byron"
    assert updated.get_json()["gender"] == "female"
    assert updated.get_json()["age"] == 25
    assert updated.get_json()["address"] == "District 1, Ho Chi Minh City"


def test_upload_me_avatar_returns_url(client, monkeypatch):
    created = register(client).get_json()
    headers = {"Authorization": f"Bearer {created['access_token']}"}

    def fake_upload(_self, _user_id, _file_storage, *, media_kind):
        assert media_kind == "avatar"
        return "http://localhost:9000/ticketrush-media/avatars/demo.png"

    monkeypatch.setattr(StorageService, "upload_user_media", fake_upload)

    response = client.post(
        "/users/me/media",
        headers=headers,
        data={"kind": "avatar", "file": (io.BytesIO(b"fake-image"), "avatar.png")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert response.get_json()["url"].startswith("http://localhost:9000/ticketrush-media/")

def test_admin_delete_user_reassigns_booking_references(client):
    register(client, email="admin@example.com")
    admin = User.query.filter_by(email="admin@example.com").one()
    admin.role = Role.ADMIN
    db.session.commit()
    admin_token = client.post("/auth/login", json={"email": "admin@example.com", "password": "correct-password"}).get_json()["access_token"]

    register(client, email="buyer@example.com")
    buyer = User.query.filter_by(email="buyer@example.com").one()

    db.session.execute(text("CREATE TABLE bookings (id TEXT PRIMARY KEY, user_id TEXT NOT NULL)"))
    db.session.execute(text("INSERT INTO bookings (id, user_id) VALUES ('booking-1', :user_id)"), {"user_id": str(buyer.id)})
    db.session.commit()

    response = client.delete(f"/users/{buyer.id}", headers={"Authorization": f"Bearer {admin_token}"})

    assert response.status_code == 204
    assert db.session.get(User, buyer.id) is None
    booking_user_id = db.session.execute(text("SELECT user_id FROM bookings WHERE id = 'booking-1'")).scalar_one()
    assert booking_user_id == str(DELETED_USER_ID)

    listed = client.get("/users", headers={"Authorization": f"Bearer {admin_token}"}).get_json()
    assert all(item["id"] != str(DELETED_USER_ID) for item in listed)
