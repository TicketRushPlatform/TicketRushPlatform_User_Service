from argon2 import PasswordHasher
from flask import Blueprint, current_app, g, request

from app.decorators import require_auth, require_permission
from app.errors import AppError
from app.extensions import db
from app.repositories import UserRepository
from app.models import Provider, Role, Status, User
from app.schemas import AdminCreateUserSchema, AdminUpdateUserSchema, UpdateMeSchema, user_to_dict
from app.services.storage_service import StorageService

bp = Blueprint("users", __name__, url_prefix="/users")
hasher = PasswordHasher()


@bp.get("/me")
@require_auth()
@require_permission("PROFILE_VIEW")
def me():
    """Get current user profile.

        ---
        get:
            tags:
                - Users
            summary: Get current user profile
            security:
                - BearerAuth: []
            responses:
                '200':
                    description: OK
                    content:
                        application/json:
                            schema:
                                $ref: '#/components/schemas/UserSchema'
                '401':
                    $ref: '#/components/responses/ErrorResponse'
                '403':
                    $ref: '#/components/responses/ErrorResponse'
        """
    return user_to_dict(g.current_user)


@bp.patch("/me")
@require_auth()
@require_permission("PROFILE_EDIT")
def update_me():
    """Update current user profile.

        ---
        patch:
            tags:
                - Users
            summary: Update current user profile
            security:
                - BearerAuth: []
            requestBody:
                required: true
                content:
                    application/json:
                        schema:
                            $ref: '#/components/schemas/UpdateMeSchema'
            responses:
                '200':
                    description: OK
                    content:
                        application/json:
                            schema:
                                $ref: '#/components/schemas/UserSchema'
                '400':
                    $ref: '#/components/responses/ErrorResponse'
                '401':
                    $ref: '#/components/responses/ErrorResponse'
                '403':
                    $ref: '#/components/responses/ErrorResponse'
        """
    data = UpdateMeSchema().load(request.get_json(silent=True) or {})
    user = g.current_user
    for key, value in data.items():
        setattr(user, key, value)
    db.session.commit()
    return user_to_dict(user)


@bp.post("/me/media")
@require_auth()
@require_permission("PROFILE_EDIT")
def upload_me_media():
    """Upload media for current user.

        ---
        post:
            tags:
                - Users
            summary: Upload avatar or video to object storage
            security:
                - BearerAuth: []
            requestBody:
                required: true
                content:
                    multipart/form-data:
                        schema:
                            type: object
                            required:
                                - file
                            properties:
                                kind:
                                    type: string
                                    enum: [avatar, video]
                                file:
                                    type: string
                                    format: binary
            responses:
                '200':
                    description: OK
                    content:
                        application/json:
                            schema:
                                type: object
                                required:
                                    - url
                                properties:
                                    url:
                                        type: string
                '400':
                    $ref: '#/components/responses/ErrorResponse'
                '401':
                    $ref: '#/components/responses/ErrorResponse'
                '403':
                    $ref: '#/components/responses/ErrorResponse'
                '413':
                    $ref: '#/components/responses/ErrorResponse'
                '503':
                    $ref: '#/components/responses/ErrorResponse'
        """
    media_kind = request.form.get("kind", "avatar")
    upload_file = request.files.get("file")
    if upload_file is None:
        raise AppError("MISSING_FILE", "Upload file is required.", 400)

    storage = StorageService(current_app.config["APP_CONFIG"])
    file_url = storage.upload_user_media(str(g.current_user.id), upload_file, media_kind=media_kind)
    return {"url": file_url}


@bp.get("/<uuid:user_id>")
@require_auth(admin=True)
def get_user(user_id):
    """Get user by id (admin only).

        ---
        get:
            tags:
                - Users
            summary: Get user by id (admin only)
            security:
                - BearerAuth: []
            parameters:
                - in: path
                  name: user_id
                  required: true
                  schema:
                    type: string
                    format: uuid
            responses:
                '200':
                    description: OK
                    content:
                        application/json:
                            schema:
                                $ref: '#/components/schemas/UserSchema'
                '401':
                    $ref: '#/components/responses/ErrorResponse'
                '403':
                    $ref: '#/components/responses/ErrorResponse'
                '404':
                    $ref: '#/components/responses/ErrorResponse'
        """
    user = UserRepository().get_by_id(user_id)
    if user is None:
        raise AppError("USER_NOT_FOUND", "User was not found.", 404)
    return user_to_dict(user)


@bp.get("")
@require_auth(admin=True)
def list_users():
    """List all users (admin only).

        ---
        get:
            tags:
                - Users
            summary: List all users (admin only)
            security:
                - BearerAuth: []
            responses:
                '200':
                    description: OK
                    content:
                        application/json:
                            schema:
                                type: array
                                items:
                                    $ref: '#/components/schemas/UserSchema'
                '401':
                    $ref: '#/components/responses/ErrorResponse'
                '403':
                    $ref: '#/components/responses/ErrorResponse'
    """
    users = UserRepository().list_all()
    return [user_to_dict(user) for user in users]


@bp.post("")
@require_auth(admin=True)
def create_user():
    """Create user (admin only).

        ---
        post:
            tags:
                - Users
            summary: Create user (admin only)
            security:
                - BearerAuth: []
            requestBody:
                required: true
                content:
                    application/json:
                        schema:
                            type: object
                            required:
                                - email
                                - password
                                - full_name
                            properties:
                                email:
                                    type: string
                                    format: email
                                password:
                                    type: string
                                    minLength: 8
                                full_name:
                                    type: string
                                role:
                                    type: string
                                    enum: [USER, ADMIN]
                                status:
                                    type: string
                                    enum: [ACTIVE, BLOCKED]
            responses:
                '201':
                    description: Created
                    content:
                        application/json:
                            schema:
                                $ref: '#/components/schemas/UserSchema'
                '400':
                    $ref: '#/components/responses/ErrorResponse'
                '401':
                    $ref: '#/components/responses/ErrorResponse'
                '403':
                    $ref: '#/components/responses/ErrorResponse'
                '409':
                    $ref: '#/components/responses/ErrorResponse'
    """
    data = AdminCreateUserSchema().load(request.get_json(silent=True) or {})
    repo = UserRepository()
    normalized_email = data["email"].lower()
    if repo.get_by_email(normalized_email):
        raise AppError("EMAIL_ALREADY_EXISTS", "Email is already registered.", 409)

    user = User(
        email=normalized_email,
        password_hash=hasher.hash(data["password"]),
        full_name=data["full_name"],
        provider=Provider.LOCAL,
        role=Role(data["role"]),
        status=Status(data["status"]),
    )
    repo.add(user)
    db.session.commit()
    return user_to_dict(user), 201


@bp.patch("/<uuid:user_id>")
@require_auth(admin=True)
def update_user(user_id):
    """Update user by id (admin only).

        ---
        patch:
            tags:
                - Users
            summary: Update user by id (admin only)
            security:
                - BearerAuth: []
            parameters:
                - in: path
                  name: user_id
                  required: true
                  schema:
                    type: string
                    format: uuid
            requestBody:
                required: true
                content:
                    application/json:
                        schema:
                            type: object
                            properties:
                                full_name:
                                    type: string
                                role:
                                    type: string
                                    enum: [USER, ADMIN]
                                status:
                                    type: string
                                    enum: [ACTIVE, BLOCKED]
            responses:
                '200':
                    description: OK
                    content:
                        application/json:
                            schema:
                                $ref: '#/components/schemas/UserSchema'
                '400':
                    $ref: '#/components/responses/ErrorResponse'
                '401':
                    $ref: '#/components/responses/ErrorResponse'
                '403':
                    $ref: '#/components/responses/ErrorResponse'
                '404':
                    $ref: '#/components/responses/ErrorResponse'
    """
    repo = UserRepository()
    user = repo.get_by_id(user_id)
    if user is None:
        raise AppError("USER_NOT_FOUND", "User was not found.", 404)

    payload = AdminUpdateUserSchema().load(request.get_json(silent=True) or {})
    if not payload:
        raise AppError("VALIDATION_ERROR", "At least one field is required.", 400)

    if "full_name" in payload:
        user.full_name = payload["full_name"]
    if "role" in payload:
        user.role = Role(payload["role"])
    if "status" in payload:
        user.status = Status(payload["status"])

    db.session.commit()
    return user_to_dict(user)


@bp.delete("/<uuid:user_id>")
@require_auth(admin=True)
def delete_user(user_id):
    """Delete user by id (admin only).

        ---
        delete:
            tags:
                - Users
            summary: Delete user by id (admin only)
            security:
                - BearerAuth: []
            parameters:
                - in: path
                  name: user_id
                  required: true
                  schema:
                    type: string
                    format: uuid
            responses:
                '204':
                    description: Deleted
                '401':
                    $ref: '#/components/responses/ErrorResponse'
                '403':
                    $ref: '#/components/responses/ErrorResponse'
                '404':
                    $ref: '#/components/responses/ErrorResponse'
    """
    repo = UserRepository()
    user = repo.get_by_id(user_id)
    if user is None:
        raise AppError("USER_NOT_FOUND", "User was not found.", 404)
    if user.id == g.current_user.id:
        raise AppError("FORBIDDEN", "You cannot delete your own account.", 403)

    repo.delete(user)
    db.session.commit()
    return "", 204


@bp.get("/stats")
@require_auth(admin=True)
def get_user_stats():
    """Get user statistics (admin only).

        ---
        get:
            tags:
                - Users
            summary: Get user statistics (admin only)
            security:
                - BearerAuth: []
            responses:
                '200':
                    description: OK
                    content:
                        application/json:
                            schema:
                                type: object
                                properties:
                                    total_users:
                                        type: integer
                                    active_users:
                                        type: integer
                                    blocked_users:
                                        type: integer
                                    admin_count:
                                        type: integer
                '401':
                    $ref: '#/components/responses/ErrorResponse'
                '403':
                    $ref: '#/components/responses/ErrorResponse'
    """
    from app.models import Status, Role
    total_users = db.session.query(db.func.count(User.id)).scalar() or 0
    active_users = db.session.query(db.func.count(User.id)).filter(User.status == Status.ACTIVE).scalar() or 0
    blocked_users = db.session.query(db.func.count(User.id)).filter(User.status == Status.BLOCKED).scalar() or 0
    admin_count = db.session.query(db.func.count(User.id)).filter(User.role == Role.ADMIN).scalar() or 0
    return {
        "total_users": total_users,
        "active_users": active_users,
        "blocked_users": blocked_users,
        "admin_count": admin_count,
    }
