import hashlib
from datetime import datetime, timezone
from http import HTTPStatus
from uuid import uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError, VerificationError
from sqlalchemy.exc import IntegrityError

from app.errors import AppError
from app.extensions import db
from app.models import Provider, RefreshToken, Role, Status, User
from app.repositories import UserRepository
from app.services.email_service import EmailService
from app.services.oauth_service import OAuthVerifier
from app.services.token_service import TokenService, parse_uuid


class AuthService:
    def __init__(self, config):
        self.config = config
        self.users = UserRepository()
        self.tokens = TokenService(config)
        self.oauth = OAuthVerifier(config)
        self.email = EmailService(config)
        self.hasher = PasswordHasher()

    def register(self, data):
        if self.users.get_by_email(data["email"]):
            raise AppError("EMAIL_ALREADY_EXISTS", "Email is already registered.", HTTPStatus.CONFLICT)

        user = User(
            id=uuid4(),
            email=data["email"].lower(),
            password_hash=self.hasher.hash(data["password"]),
            full_name=data["full_name"],
            provider=Provider.LOCAL,
            role=Role.USER,
            status=Status.ACTIVE,
        )
        self.users.add(user)
        pair = self.tokens.issue_pair(user)
        self._commit_or_duplicate()
        return pair

    def login(self, data):
        user = self.users.get_by_email(data["email"])
        if user is None:
            raise AppError("INVALID_CREDENTIALS", "Email or password is incorrect.", HTTPStatus.UNAUTHORIZED)
        if not user.password_hash:
            if user.provider != Provider.LOCAL:
                raise AppError(
                    "PASSWORD_LOGIN_NOT_AVAILABLE",
                    "This account uses social login. Please sign in with your linked provider.",
                    HTTPStatus.BAD_REQUEST,
                )
            raise AppError("INVALID_CREDENTIALS", "Email or password is incorrect.", HTTPStatus.UNAUTHORIZED)
        if user.status != Status.ACTIVE:
            raise AppError("USER_BLOCKED", "User account is not active.", HTTPStatus.FORBIDDEN)
        try:
            self.hasher.verify(user.password_hash, data["password"])
        except (InvalidHashError, VerifyMismatchError, VerificationError) as exc:
            raise AppError("INVALID_CREDENTIALS", "Email or password is incorrect.", HTTPStatus.UNAUTHORIZED) from exc

        pair = self.tokens.issue_pair(user)
        db.session.commit()
        return pair

    def forgot_password(self, data):
        user = self.users.get_by_email(data["email"])
        if user and user.email and user.password_hash and user.status == Status.ACTIVE:
            token = self._issue_password_reset_token(user)
            reset_url = f"{self.config.APP_PUBLIC_URL.rstrip('/')}/reset-password?token={token}"
            self.email.send_password_reset(user.email, reset_url, user.full_name)
        return {"message": "If that email exists, a password reset link has been sent."}

    def reset_password(self, data):
        payload = self._verify_password_reset_token(data["token"])
        user = self.users.get_by_id(parse_uuid(payload["sub"]))
        if user is None or user.status != Status.ACTIVE:
            raise AppError("INVALID_RESET_TOKEN", "Password reset token is invalid or expired.", HTTPStatus.BAD_REQUEST)
        if user.provider != Provider.LOCAL:
            raise AppError("PASSWORD_LOGIN_NOT_AVAILABLE", "This account uses social login.", HTTPStatus.BAD_REQUEST)
        if payload.get("pwd") != self._password_fingerprint(user):
            raise AppError("INVALID_RESET_TOKEN", "Password reset token is invalid or expired.", HTTPStatus.BAD_REQUEST)

        user.password_hash = self.hasher.hash(data["password"])
        db.session.query(RefreshToken).filter_by(user_id=user.id, revoked=False).update({"revoked": True})
        db.session.commit()
        return {"message": "Password has been reset successfully."}

    def oauth_login(self, provider: Provider, payload: dict):
        profile = self.oauth.verify_google(payload) if provider == Provider.GOOGLE else self.oauth.verify_facebook(payload)
        if not profile.provider_id:
            raise AppError("INVALID_OAUTH_TOKEN", "OAuth provider id is missing.", HTTPStatus.UNAUTHORIZED)

        user = self.users.get_by_provider(provider, profile.provider_id)
        if user is None:
            user = self.users.get_by_email(profile.email)
            if user is None:
                user = User(
                    id=uuid4(),
                    email=profile.email.lower(),
                    full_name=profile.name,
                    avatar_url=profile.avatar_url,
                    provider=provider,
                    provider_id=profile.provider_id,
                    role=Role.USER,
                    status=Status.ACTIVE,
                )
                self.users.add(user)
            else:
                if user.provider == Provider.LOCAL and user.provider_id is None:
                    user.provider = provider
                    user.provider_id = profile.provider_id
                    user.avatar_url = user.avatar_url or profile.avatar_url
                elif user.provider != provider or user.provider_id != profile.provider_id:
                    raise AppError("ACCOUNT_LINK_CONFLICT", "Email belongs to another OAuth account.", HTTPStatus.CONFLICT)

        if user.status != Status.ACTIVE:
            raise AppError("USER_BLOCKED", "User account is not active.", HTTPStatus.FORBIDDEN)

        pair = self.tokens.issue_pair(user)
        self._commit_or_duplicate()
        return pair

    def _commit_or_duplicate(self):
        try:
            db.session.commit()
        except IntegrityError as exc:
            db.session.rollback()
            raise AppError("DUPLICATE_USER", "User already exists.", HTTPStatus.CONFLICT) from exc

    def _issue_password_reset_token(self, user: User) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user.id),
            "purpose": "password_reset",
            "pwd": self._password_fingerprint(user),
            "iat": int(now.timestamp()),
            "exp": int(now.timestamp()) + self.config.PASSWORD_RESET_TOKEN_TTL_SECONDS,
        }
        return jwt.encode(payload, self.config.JWT_SECRET, algorithm=self.config.JWT_ALGORITHM)

    def _verify_password_reset_token(self, token: str) -> dict:
        try:
            payload = jwt.decode(token, self.config.JWT_SECRET, algorithms=[self.config.JWT_ALGORITHM])
        except jwt.PyJWTError as exc:
            raise AppError("INVALID_RESET_TOKEN", "Password reset token is invalid or expired.", HTTPStatus.BAD_REQUEST) from exc
        if payload.get("purpose") != "password_reset":
            raise AppError("INVALID_RESET_TOKEN", "Password reset token is invalid or expired.", HTTPStatus.BAD_REQUEST)
        return payload

    @staticmethod
    def _password_fingerprint(user: User) -> str:
        return hashlib.sha256((user.password_hash or "").encode("utf-8")).hexdigest()
