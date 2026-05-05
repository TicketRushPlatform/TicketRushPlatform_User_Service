from http import HTTPStatus
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from sqlalchemy.exc import IntegrityError

from app.errors import AppError
from app.extensions import db
from app.models import Provider, Role, Status, User
from app.repositories import UserRepository
from app.services.oauth_service import OAuthVerifier
from app.services.token_service import TokenService


class AuthService:
    def __init__(self, config):
        self.users = UserRepository()
        self.tokens = TokenService(config)
        self.oauth = OAuthVerifier(config)
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
        if user is None or not user.password_hash:
            raise AppError("INVALID_CREDENTIALS", "Email or password is incorrect.", HTTPStatus.UNAUTHORIZED)
        if user.status != Status.ACTIVE:
            raise AppError("USER_BLOCKED", "User account is not active.", HTTPStatus.FORBIDDEN)
        try:
            self.hasher.verify(user.password_hash, data["password"])
        except (VerifyMismatchError, VerificationError) as exc:
            raise AppError("INVALID_CREDENTIALS", "Email or password is incorrect.", HTTPStatus.UNAUTHORIZED) from exc

        pair = self.tokens.issue_pair(user)
        db.session.commit()
        return pair

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
