from flask import Blueprint, current_app, request

from app.extensions import limiter
from app.models import Provider
from app.schemas import ForgotPasswordSchema, LoginSchema, LogoutSchema, OAuthSchema, RefreshSchema, RegisterSchema, ResetPasswordSchema
from app.services.auth_service import AuthService
from app.services.token_service import TokenService

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.post("/register")
@limiter.limit("5 per minute")
def register():
    """Register.

        ---
        post:
            tags:
                - Auth
            summary: Register
            requestBody:
                required: true
                content:
                    application/json:
                        schema:
                            $ref: '#/components/schemas/RegisterSchema'
            responses:
                '201':
                    description: Created
                    content:
                        application/json:
                            schema:
                                $ref: '#/components/schemas/TokenPairSchema'
                '400':
                    $ref: '#/components/responses/ErrorResponse'
                '409':
                    $ref: '#/components/responses/ErrorResponse'
                '429':
                    $ref: '#/components/responses/ErrorResponse'
    """
    data = RegisterSchema().load(request.get_json(silent=True) or {})
    return AuthService(current_app.config["APP_CONFIG"]).register(data), 201


@bp.post("/login")
@limiter.limit("10 per minute")
def login():
    """Login.

        ---
        post:
            tags:
                - Auth
            summary: Login
            requestBody:
                required: true
                content:
                    application/json:
                        schema:
                            $ref: '#/components/schemas/LoginSchema'
            responses:
                '200':
                    description: OK
                    content:
                        application/json:
                            schema:
                                $ref: '#/components/schemas/TokenPairSchema'
                '400':
                    $ref: '#/components/responses/ErrorResponse'
                '401':
                    $ref: '#/components/responses/ErrorResponse'
                '403':
                    $ref: '#/components/responses/ErrorResponse'
                '429':
                    $ref: '#/components/responses/ErrorResponse'
    """
    data = LoginSchema().load(request.get_json(silent=True) or {})
    return AuthService(current_app.config["APP_CONFIG"]).login(data)


@bp.post("/refresh")
@limiter.limit("30 per minute")
def refresh():
    """Refresh access token.

        ---
        post:
            tags:
                - Auth
            summary: Refresh access token
            requestBody:
                required: true
                content:
                    application/json:
                        schema:
                            $ref: '#/components/schemas/RefreshSchema'
            responses:
                '200':
                    description: OK
                    content:
                        application/json:
                            schema:
                                $ref: '#/components/schemas/TokenPairSchema'
                '400':
                    $ref: '#/components/responses/ErrorResponse'
                '401':
                    $ref: '#/components/responses/ErrorResponse'
                '403':
                    $ref: '#/components/responses/ErrorResponse'
                '429':
                    $ref: '#/components/responses/ErrorResponse'
    """
    data = RefreshSchema().load(request.get_json(silent=True) or {})
    return TokenService(current_app.config["APP_CONFIG"]).rotate_refresh(data["refresh_token"])


@bp.post("/logout")
def logout():
    """Logout (revoke refresh token).

        ---
        post:
            tags:
                - Auth
            summary: Logout (revoke refresh token)
            requestBody:
                required: true
                content:
                    application/json:
                        schema:
                            $ref: '#/components/schemas/LogoutSchema'
            responses:
                '204':
                    description: No Content
                '400':
                    $ref: '#/components/responses/ErrorResponse'
                '429':
                    $ref: '#/components/responses/ErrorResponse'
    """
    data = LogoutSchema().load(request.get_json(silent=True) or {})
    TokenService(current_app.config["APP_CONFIG"]).revoke_refresh(data["refresh_token"])
    return "", 204


@bp.post("/forgot-password")
@limiter.limit("5 per minute")
def forgot_password():
    data = ForgotPasswordSchema().load(request.get_json(silent=True) or {})
    return AuthService(current_app.config["APP_CONFIG"]).forgot_password(data)


@bp.post("/reset-password")
@limiter.limit("5 per minute")
def reset_password():
    data = ResetPasswordSchema().load(request.get_json(silent=True) or {})
    return AuthService(current_app.config["APP_CONFIG"]).reset_password(data)


@bp.post("/oauth/google")
@limiter.limit("10 per minute")
def google():
    """OAuth login (Google).

        ---
        post:
            tags:
                - Auth
            summary: OAuth login (Google)
            requestBody:
                required: true
                content:
                    application/json:
                        schema:
                            $ref: '#/components/schemas/OAuthSchema'
            responses:
                '200':
                    description: OK
                    content:
                        application/json:
                            schema:
                                $ref: '#/components/schemas/TokenPairSchema'
                '400':
                    $ref: '#/components/responses/ErrorResponse'
                '401':
                    $ref: '#/components/responses/ErrorResponse'
                '403':
                    $ref: '#/components/responses/ErrorResponse'
                '409':
                    $ref: '#/components/responses/ErrorResponse'
                '429':
                    $ref: '#/components/responses/ErrorResponse'
    """
    data = OAuthSchema().load(request.get_json(silent=True) or {})
    return AuthService(current_app.config["APP_CONFIG"]).oauth_login(Provider.GOOGLE, data)


@bp.post("/oauth/facebook")
@limiter.limit("10 per minute")
def facebook():
    """OAuth login (Facebook).

        ---
        post:
            tags:
                - Auth
            summary: OAuth login (Facebook)
            requestBody:
                required: true
                content:
                    application/json:
                        schema:
                            $ref: '#/components/schemas/OAuthSchema'
            responses:
                '200':
                    description: OK
                    content:
                        application/json:
                            schema:
                                $ref: '#/components/schemas/TokenPairSchema'
                '400':
                    $ref: '#/components/responses/ErrorResponse'
                '401':
                    $ref: '#/components/responses/ErrorResponse'
                '403':
                    $ref: '#/components/responses/ErrorResponse'
                '409':
                    $ref: '#/components/responses/ErrorResponse'
                '429':
                    $ref: '#/components/responses/ErrorResponse'
    """
    data = OAuthSchema().load(request.get_json(silent=True) or {})
    return AuthService(current_app.config["APP_CONFIG"]).oauth_login(Provider.FACEBOOK, data)
