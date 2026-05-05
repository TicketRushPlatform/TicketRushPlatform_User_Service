from http import HTTPStatus

import requests

from app.errors import AppError


class OAuthProfile:
    def __init__(self, provider_id: str, email: str | None, name: str, avatar_url: str | None):
        self.provider_id = provider_id
        self.email = email
        self.name = name
        self.avatar_url = avatar_url


class OAuthVerifier:
    def __init__(self, config):
        self.config = config

    def verify_google(self, payload: dict) -> OAuthProfile:
        token = payload.get("id_token") or payload.get("access_token")
        if not token and payload.get("authorization_code"):
            if not self.config.GOOGLE_CLIENT_ID or not self.config.GOOGLE_CLIENT_SECRET or not payload.get("redirect_uri"):
                raise AppError("OAUTH_CONFIG_REQUIRED", "Google authorization code exchange is not configured.", HTTPStatus.BAD_REQUEST)
            exchanged = requests.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": payload["authorization_code"],
                    "client_id": self.config.GOOGLE_CLIENT_ID,
                    "client_secret": self.config.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": payload["redirect_uri"],
                    "grant_type": "authorization_code",
                },
                timeout=5,
            )
            if exchanged.status_code != 200:
                raise AppError("INVALID_OAUTH_TOKEN", "Google authorization code exchange failed.", HTTPStatus.UNAUTHORIZED)
            token = exchanged.json().get("id_token") or exchanged.json().get("access_token")

        if not token:
            raise AppError("UNSUPPORTED_OAUTH_FLOW", "Google authorization code exchange is not configured.", HTTPStatus.BAD_REQUEST)

        response = requests.get("https://oauth2.googleapis.com/tokeninfo", params={"id_token": token}, timeout=5)
        if response.status_code != 200 and payload.get("access_token"):
            response = requests.get("https://www.googleapis.com/oauth2/v3/userinfo", headers={"Authorization": f"Bearer {token}"}, timeout=5)
        if response.status_code != 200:
            raise AppError("INVALID_OAUTH_TOKEN", "Google token verification failed.", HTTPStatus.UNAUTHORIZED)

        data = response.json()
        audience = data.get("aud")
        if self.config.GOOGLE_CLIENT_ID and audience and audience != self.config.GOOGLE_CLIENT_ID:
            raise AppError("INVALID_OAUTH_TOKEN", "Google token audience is invalid.", HTTPStatus.UNAUTHORIZED)

        email = data.get("email")
        if not email:
            raise AppError("OAUTH_EMAIL_REQUIRED", "OAuth provider did not return an email.", HTTPStatus.BAD_REQUEST)

        return OAuthProfile(
            provider_id=data.get("sub"),
            email=email,
            name=data.get("name") or email.split("@")[0],
            avatar_url=data.get("picture"),
        )

    def verify_facebook(self, payload: dict) -> OAuthProfile:
        access_token = payload.get("access_token")
        if not access_token and payload.get("authorization_code"):
            if not self.config.FACEBOOK_APP_ID or not self.config.FACEBOOK_APP_SECRET or not payload.get("redirect_uri"):
                raise AppError("OAUTH_CONFIG_REQUIRED", "Facebook authorization code exchange is not configured.", HTTPStatus.BAD_REQUEST)
            exchanged = requests.get(
                "https://graph.facebook.com/v19.0/oauth/access_token",
                params={
                    "client_id": self.config.FACEBOOK_APP_ID,
                    "client_secret": self.config.FACEBOOK_APP_SECRET,
                    "redirect_uri": payload["redirect_uri"],
                    "code": payload["authorization_code"],
                },
                timeout=5,
            )
            if exchanged.status_code != 200:
                raise AppError("INVALID_OAUTH_TOKEN", "Facebook authorization code exchange failed.", HTTPStatus.UNAUTHORIZED)
            access_token = exchanged.json().get("access_token")

        if not access_token:
            raise AppError("UNSUPPORTED_OAUTH_FLOW", "Facebook login requires an access_token.", HTTPStatus.BAD_REQUEST)

        if self.config.FACEBOOK_APP_ID and self.config.FACEBOOK_APP_SECRET:
            app_token = f"{self.config.FACEBOOK_APP_ID}|{self.config.FACEBOOK_APP_SECRET}"
            debug = requests.get(
                "https://graph.facebook.com/debug_token",
                params={"input_token": access_token, "access_token": app_token},
                timeout=5,
            )
            if debug.status_code != 200 or not debug.json().get("data", {}).get("is_valid"):
                raise AppError("INVALID_OAUTH_TOKEN", "Facebook token verification failed.", HTTPStatus.UNAUTHORIZED)

        profile = requests.get(
            "https://graph.facebook.com/me",
            params={"fields": "id,name,email,picture", "access_token": access_token},
            timeout=5,
        )
        if profile.status_code != 200:
            raise AppError("INVALID_OAUTH_TOKEN", "Facebook profile verification failed.", HTTPStatus.UNAUTHORIZED)

        data = profile.json()
        email = data.get("email")
        if not email:
            raise AppError("OAUTH_EMAIL_REQUIRED", "OAuth provider did not return an email.", HTTPStatus.BAD_REQUEST)

        picture = data.get("picture", {}).get("data", {}).get("url")
        return OAuthProfile(data.get("id"), email, data.get("name") or email.split("@")[0], picture)
