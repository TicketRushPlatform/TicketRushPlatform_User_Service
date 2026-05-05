from app.extensions import db
from app.models import Provider, RefreshToken, User


class UserRepository:
    def get_by_id(self, user_id):
        return db.session.get(User, user_id)

    def get_by_email(self, email: str):
        return User.query.filter(db.func.lower(User.email) == email.lower()).one_or_none()

    def get_by_provider(self, provider: Provider, provider_id: str):
        return User.query.filter_by(provider=provider, provider_id=provider_id).one_or_none()

    def add(self, user: User):
        db.session.add(user)
        return user


class RefreshTokenRepository:
    def get_by_hash(self, token_hash: str):
        return RefreshToken.query.filter_by(token_hash=token_hash).one_or_none()

    def add(self, token: RefreshToken):
        db.session.add(token)
        return token

    def revoke_all_for_user(self, user_id):
        RefreshToken.query.filter_by(user_id=user_id, revoked=False).update({"revoked": True})
