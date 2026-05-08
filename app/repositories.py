from app.extensions import db
from app.models import Provider, RefreshToken, RoleDefinition, RolePermission, User


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

    def list_all(self):
        return User.query.order_by(User.created_at.desc()).all()

    def delete(self, user: User):
        db.session.delete(user)


class RefreshTokenRepository:
    def get_by_hash(self, token_hash: str):
        return RefreshToken.query.filter_by(token_hash=token_hash).one_or_none()

    def add(self, token: RefreshToken):
        db.session.add(token)
        return token

    def revoke_all_for_user(self, user_id):
        RefreshToken.query.filter_by(user_id=user_id, revoked=False).update({"revoked": True})


class RoleRepository:
    def list_all(self):
        return RoleDefinition.query.order_by(RoleDefinition.name.asc()).all()

    def get_by_name(self, name: str):
        return RoleDefinition.query.filter(db.func.lower(RoleDefinition.name) == name.lower()).one_or_none()

    def add(self, role: RoleDefinition):
        db.session.add(role)
        return role

    def delete(self, role: RoleDefinition):
        db.session.delete(role)

    def list_permissions(self, role: RoleDefinition):
        return sorted({item.permission for item in role.permissions})

    def set_permissions(self, role: RoleDefinition, permissions: list[str]):
        target_permissions = set(permissions)
        existing_by_permission = {item.permission: item for item in role.permissions}

        # Keep existing rows when possible to avoid insert-before-delete
        # conflicts on unique(role_id, permission) during a single flush.
        for permission, existing in list(existing_by_permission.items()):
            if permission not in target_permissions:
                role.permissions.remove(existing)

        current_permissions = {item.permission for item in role.permissions}
        for permission in sorted(target_permissions - current_permissions):
            role.permissions.append(RolePermission(permission=permission))
        return role
