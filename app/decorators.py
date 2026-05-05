from functools import wraps
from http import HTTPStatus

from flask import current_app, g, request

from app.errors import AppError
from app.models import Role, Status
from app.repositories import UserRepository
from app.services.token_service import TokenService, parse_uuid


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
