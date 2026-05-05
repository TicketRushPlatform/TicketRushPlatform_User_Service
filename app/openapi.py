from __future__ import annotations

from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin
from apispec_webframeworks.flask import FlaskPlugin
from flask import Blueprint, jsonify
from flask_swagger_ui import get_swaggerui_blueprint

from app.schemas import (
    ErrorSchema,
    LoginSchema,
    LogoutSchema,
    OAuthSchema,
    RefreshSchema,
    RegisterSchema,
    TokenPairSchema,
    UpdateMeSchema,
    UserSchema,
)


def build_spec(app) -> APISpec:
    spec = APISpec(
        title="TicketRush User API",
        version="1.0.0",
        openapi_version="3.0.3",
        plugins=[FlaskPlugin(), MarshmallowPlugin()],
    )

    spec.components.security_scheme(
        "BearerAuth",
        {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        },
    )

    for schema in (
        RegisterSchema,
        LoginSchema,
        RefreshSchema,
        LogoutSchema,
        OAuthSchema,
        UpdateMeSchema,
        TokenPairSchema,
        UserSchema,
        ErrorSchema,
    ):
        spec.components.schema(schema.__name__, schema=schema)

    spec.components.response(
        "ErrorResponse",
        {
            "description": "Error",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ErrorSchema"}
                }
            },
        },
    )

    return spec


def register_paths(app, spec: APISpec) -> None:
    # Auto-register all paths that include apispec-style YAML docstrings.
    # This keeps the spec generated from in-code annotations, without a manual list.
    for endpoint, view in app.view_functions.items():
        doc = getattr(view, "__doc__", None) or ""
        if "---" not in doc:
            continue
        spec.path(view=view, app=app)


def init_openapi(app) -> None:
    cfg = app.config.get("APP_CONFIG")
    if cfg is not None and not getattr(cfg, "ENABLE_SWAGGER", True):
        return

    spec = build_spec(app)
    register_paths(app, spec)
    app.extensions["openapi_spec"] = spec

    @app.get("/openapi.json")
    def openapi_json():
        return jsonify(spec.to_dict())

    swaggerui_bp: Blueprint = get_swaggerui_blueprint(
        "/docs",
        "/openapi.json",
        config={"app_name": "TicketRush User API"},
    )
    app.register_blueprint(swaggerui_bp, url_prefix="/docs")
