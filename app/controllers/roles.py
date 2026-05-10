from flask import Blueprint, request

from app.decorators import require_auth
from app.errors import AppError
from app.extensions import db
from app.models import RoleDefinition
from app.repositories import RoleRepository
from app.schemas import RoleCreateSchema, RoleUpdateSchema

bp = Blueprint("roles", __name__, url_prefix="/roles")

SYSTEM_ROLES = {"ADMIN", "ORGANIZER"}
DEFAULT_ROLE_PERMISSIONS: dict[str, list[str]] = {
    "ORGANIZER": [
        "EVENT_CREATE",
    ],
    "ADMIN": [
        "EVENT_MANAGE_ALL",
        "USER_MANAGE_ALL",
    ],
}
ALLOWED_PERMISSIONS = sorted({
    "EVENT_CREATE",
    "EVENT_MANAGE_ALL",
    "USER_MANAGE_ALL",
})


def normalize_role_name(name: str) -> str:
    return name.strip().upper()


def normalize_permission_name(name: str) -> str:
    return name.strip().upper()


def validate_permissions(permissions: list[str]):
    unsupported = sorted({item for item in permissions if item not in ALLOWED_PERMISSIONS})
    if unsupported:
        raise AppError(
            "INVALID_PERMISSION",
            "Some permissions are not supported.",
            400,
            {"unsupported_permissions": unsupported, "allowed_permissions": ALLOWED_PERMISSIONS},
        )


def serialize_role(role: RoleDefinition, repo: RoleRepository):
    permissions = repo.list_permissions(role)
    return {
        "name": role.name,
        "system": role.name in SYSTEM_ROLES,
        "permissions": permissions,
        "created_at": role.created_at.isoformat(),
        "updated_at": role.updated_at.isoformat(),
    }


def ensure_default_roles(repo: RoleRepository):
    created = False
    for role_name, permissions in DEFAULT_ROLE_PERMISSIONS.items():
        existing = repo.get_by_name(role_name)
        if existing is None:
            role = RoleDefinition(name=role_name)
            repo.add(role)
            repo.set_permissions(role, [normalize_permission_name(item) for item in permissions])
            created = True
    if created:
        db.session.commit()


@bp.get("")
@require_auth(admin=True)
def list_roles():
    """List roles with permissions (admin only)."""
    repo = RoleRepository()
    ensure_default_roles(repo)
    roles = repo.list_all()
    return [serialize_role(role, repo) for role in roles]


@bp.get("/permissions-catalog")
@require_auth(admin=True)
def list_permission_catalog():
    """List available permission names (admin only)."""
    return {"permissions": ALLOWED_PERMISSIONS}


@bp.post("")
@require_auth(admin=True)
def create_role():
    """Create role with permissions (admin only)."""
    payload = RoleCreateSchema().load(request.get_json(silent=True) or {})
    repo = RoleRepository()
    ensure_default_roles(repo)

    role_name = normalize_role_name(payload["name"])
    if repo.get_by_name(role_name):
        raise AppError("ROLE_ALREADY_EXISTS", "Role already exists.", 409)

    normalized_permissions = [normalize_permission_name(item) for item in payload.get("permissions", []) if item.strip()]
    validate_permissions(normalized_permissions)

    role = RoleDefinition(name=role_name)
    repo.add(role)
    repo.set_permissions(role, normalized_permissions)
    db.session.commit()
    return serialize_role(role, repo), 201


@bp.patch("/<role_name>")
@require_auth(admin=True)
def update_role(role_name: str):
    """Update role permissions (admin only)."""
    payload = RoleUpdateSchema().load(request.get_json(silent=True) or {})
    repo = RoleRepository()
    ensure_default_roles(repo)

    role = repo.get_by_name(role_name)
    if role is None:
        raise AppError("ROLE_NOT_FOUND", "Role was not found.", 404)

    current_permissions = set(repo.list_permissions(role))
    full_permissions = payload.get("permissions")
    if full_permissions is not None:
        normalized_full = [normalize_permission_name(item) for item in full_permissions if item.strip()]
        validate_permissions(normalized_full)
        current_permissions = set(normalized_full)

    for item in payload.get("permissions_add", []):
        if item.strip():
            normalized = normalize_permission_name(item)
            validate_permissions([normalized])
            current_permissions.add(normalized)
    for item in payload.get("permissions_remove", []):
        if item.strip():
            current_permissions.discard(normalize_permission_name(item))

    repo.set_permissions(role, sorted(current_permissions))
    db.session.commit()
    return serialize_role(role, repo)


