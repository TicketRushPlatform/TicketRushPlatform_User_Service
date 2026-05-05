import io

from app.extensions import db
from app.models import Provider, RefreshToken, User
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
