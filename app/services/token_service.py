import hashlib
import secrets
import uuid
from datetime import timezone, timedelta
from http import HTTPStatus

import jwt

from app.errors import AppError
from app.extensions import db
from app.models import RefreshToken, Status, utcnow
from app.repositories import RefreshTokenRepository, UserRepository


class TokenService:
    def __init__(self, config):
        self.config = config
        self.refresh_tokens = RefreshTokenRepository()
        self.users = UserRepository()

    def issue_pair(self, user):
        now = utcnow()
        access_payload = {
            "sub": str(user.id),
            "role": user.role.value,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=self.config.ACCESS_TOKEN_TTL_SECONDS)).timestamp()),
            "type": "access",
        }
        access_token = jwt.encode(access_payload, self.config.JWT_SECRET, algorithm=self.config.JWT_ALGORITHM)

        raw_refresh = secrets.token_urlsafe(48)
        refresh = RefreshToken(
            user_id=user.id,
            token_hash=self.hash_refresh(raw_refresh),
            expires_at=now + timedelta(seconds=self.config.REFRESH_TOKEN_TTL_SECONDS),
        )
        self.refresh_tokens.add(refresh)
        db.session.flush()
        return {"access_token": access_token, "refresh_token": raw_refresh, "token_type": "Bearer"}

    def verify_access(self, token: str):
        try:
            payload = jwt.decode(token, self.config.JWT_SECRET, algorithms=[self.config.JWT_ALGORITHM])
        except jwt.PyJWTError as exc:
            raise AppError("INVALID_TOKEN", "Access token is invalid or expired.", HTTPStatus.UNAUTHORIZED) from exc
        if payload.get("type") != "access":
            raise AppError("INVALID_TOKEN", "Token type is invalid.", HTTPStatus.UNAUTHORIZED)
        return payload

    def rotate_refresh(self, raw_refresh: str):
        token = self.refresh_tokens.get_by_hash(self.hash_refresh(raw_refresh))
        now = utcnow()
        if token is None:
            raise AppError("INVALID_REFRESH_TOKEN", "Refresh token is invalid.", HTTPStatus.UNAUTHORIZED)

        if token.revoked:
            self.refresh_tokens.revoke_all_for_user(token.user_id)
            db.session.commit()
            raise AppError("REFRESH_TOKEN_REUSE", "Refresh token reuse detected; all sessions were revoked.", HTTPStatus.UNAUTHORIZED)

        expires_at = token.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= now:
            token.revoked = True
            db.session.commit()
            raise AppError("INVALID_REFRESH_TOKEN", "Refresh token has expired.", HTTPStatus.UNAUTHORIZED)

        user = token.user
        if user.status != Status.ACTIVE:
            raise AppError("USER_BLOCKED", "User account is not active.", HTTPStatus.FORBIDDEN)

        token.revoked = True
        pair = self.issue_pair(user)
        db.session.commit()
        return pair

    def revoke_refresh(self, raw_refresh: str):
        token = self.refresh_tokens.get_by_hash(self.hash_refresh(raw_refresh))
        if token is not None:
            token.revoked = True
            db.session.commit()

    @staticmethod
    def hash_refresh(raw_refresh: str) -> str:
        return hashlib.sha256(raw_refresh.encode("utf-8")).hexdigest()


def parse_uuid(value: str):
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise AppError("INVALID_TOKEN", "Token subject is invalid.", HTTPStatus.UNAUTHORIZED) from exc
