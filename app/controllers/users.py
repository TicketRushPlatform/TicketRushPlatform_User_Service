from flask import Blueprint, current_app, g, request

from app.decorators import require_auth
from app.errors import AppError
from app.extensions import db
from app.repositories import UserRepository
from app.schemas import UpdateMeSchema, user_to_dict
from app.services.storage_service import StorageService

bp = Blueprint("users", __name__, url_prefix="/users")


@bp.get("/me")
@require_auth()
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
