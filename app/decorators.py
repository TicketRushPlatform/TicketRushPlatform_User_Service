from functools import wraps
from http import HTTPStatus

from flask import current_app, g, request

from app.errors import AppError
from app.models import Role, Status
from app.repositories import RoleRepository, UserRepository, UserRoleRepository
from app.services.token_service import TokenService, parse_uuid

LEGACY_ROLE_PERMISSIONS = {
    "PROFILE_OWNER": {"PROFILE_VIEW", "PROFILE_EDIT"},
    "EVENT_OWNER": {"EVENT_VIEW", "EVENT_CREATE", "EVENT_UPDATE", "EVENT_DELETE"},
    "BOOKING_OWNER": {"BOOKING_VIEW", "BOOKING_CREATE", "BOOKING_CONFIRM", "BOOKING_CANCEL"},
    "USER": {"PROFILE_VIEW", "PROFILE_EDIT"},
}


def require_auth(admin: bool = False):
    def decorator(handler):
        @wraps(handler)
        def wrapper(*args, **kwargs):
            header = request.headers.get("Authorization", "")
            if not header.startswith("Bearer "):
                raise AppError("AUTH_REQUIRED", "Bearer access token is required.", HTTPStatus.UNAUTHORIZED)
            payload = TokenService(current_app.config["APP_CONFIG"]).verify_access(header.removeprefix("Bearer ").strip())
            user = UserRepository().get_by_id(parse_uuid(payload["sub"]))
            if user is None:
                raise AppError("AUTH_REQUIRED", "Authenticated user no longer exists.", HTTPStatus.UNAUTHORIZED)
            if user.status != Status.ACTIVE:
                raise AppError("USER_BLOCKED", "User account is not active.", HTTPStatus.FORBIDDEN)
            if admin and user.role != Role.ADMIN:
                raise AppError("FORBIDDEN", "Admin role is required.", HTTPStatus.FORBIDDEN)
            g.current_user = user
            return handler(*args, **kwargs)

        return wrapper

    return decorator


def require_permission(permission: str):
    normalized_permission = permission.strip().upper()

    def decorator(handler):
        @wraps(handler)
        def wrapper(*args, **kwargs):
            user = getattr(g, "current_user", None)
            if user is None:
                raise AppError("AUTH_REQUIRED", "Authenticated user was not found in context.", HTTPStatus.UNAUTHORIZED)

            # Backward compatibility: legacy ADMIN role bypasses permission checks.
            if user.role == Role.ADMIN:
                return handler(*args, **kwargs)

            # Check permissions from dynamic role assignments (user_roles table)
            dynamic_permissions = UserRoleRepository().get_effective_permissions(user.id)
            if normalized_permission in dynamic_permissions:
                return handler(*args, **kwargs)

            # Fallback: check legacy role-based permissions
            role_name = user.role.value if hasattr(user.role, "value") else str(user.role)
            if role_name == "USER":
                role_name = "PROFILE_OWNER"
            role_def = RoleRepository().get_by_name(role_name)
            if role_def is None:
                role_permissions = LEGACY_ROLE_PERMISSIONS.get(role_name, set())
            else:
                role_permissions = {item.permission for item in role_def.permissions}
            if normalized_permission not in role_permissions:
                raise AppError("FORBIDDEN", f"Missing permission: {normalized_permission}.", HTTPStatus.FORBIDDEN)
            return handler(*args, **kwargs)

        return wrapper

    return decorator
