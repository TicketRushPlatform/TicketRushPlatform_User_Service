import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Index

from app.extensions import db


class Provider(str, enum.Enum):
    LOCAL = "LOCAL"
    GOOGLE = "GOOGLE"
    FACEBOOK = "FACEBOOK"


class Role(str, enum.Enum):
    USER = "USER"
    ADMIN = "ADMIN"
    PROFILE_OWNER = "PROFILE_OWNER"
    EVENT_OWNER = "EVENT_OWNER"
    BOOKING_OWNER = "BOOKING_OWNER"


class Status(str, enum.Enum):
    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"


def utcnow():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = db.Column(db.String, nullable=True)
    password_hash = db.Column(db.String, nullable=True)
    full_name = db.Column(db.String, nullable=False)
    avatar_url = db.Column(db.String, nullable=True)
    gender = db.Column(db.String(20), nullable=True)
    age = db.Column(db.Integer, nullable=True)
    address = db.Column(db.String(255), nullable=True)
    phone_number = db.Column(db.String(32), nullable=True)
    bio = db.Column(db.String(500), nullable=True)
    provider = db.Column(db.Enum(Provider, name="user_provider"), nullable=False, default=Provider.LOCAL)
    provider_id = db.Column(db.String, nullable=True)
    role = db.Column(db.Enum(Role, name="user_role"), nullable=False, default=Role.USER)
    status = db.Column(db.Enum(Status, name="user_status"), nullable=False, default=Status.ACTIVE)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        Index("ux_users_email_present", "email", unique=True, postgresql_where=email.isnot(None)),
        Index("ux_users_provider_id_present", "provider", "provider_id", unique=True, postgresql_where=provider_id.isnot(None)),
    )


class RefreshToken(db.Model):
    __tablename__ = "refresh_tokens"

    id = db.Column(db.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(db.Uuid(as_uuid=True), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = db.Column(db.String(64), nullable=False, unique=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    revoked = db.Column(db.Boolean, nullable=False, default=False)

    user = db.relationship("User", lazy="joined")


class RoleDefinition(db.Model):
    __tablename__ = "role_definitions"

    id = db.Column(db.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(64), nullable=False, unique=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    permissions = db.relationship(
        "RolePermission",
        back_populates="role",
        cascade="all, delete-orphan",
        lazy="joined",
    )


class RolePermission(db.Model):
    __tablename__ = "role_permissions"

    id = db.Column(db.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    role_id = db.Column(db.Uuid(as_uuid=True), db.ForeignKey("role_definitions.id", ondelete="CASCADE"), nullable=False, index=True)
    permission = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    role = db.relationship("RoleDefinition", back_populates="permissions")

    __table_args__ = (Index("ux_role_permission", "role_id", "permission", unique=True),)
