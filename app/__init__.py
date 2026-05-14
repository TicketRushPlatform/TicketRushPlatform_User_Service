from dotenv import load_dotenv
from flask import Flask

from app.config import Config
from app.errors import register_error_handlers
from app.extensions import db, limiter
from app.observability import init_metrics


def create_app(config: Config | None = None):
    load_dotenv()
    app = Flask(__name__)
    cfg = config or Config()
    app.config.from_object(cfg)
    app.config["APP_CONFIG"] = cfg
    app.config["SQLALCHEMY_DATABASE_URI"] = cfg.SQLALCHEMY_DATABASE_URI
    app.config["RATELIMIT_STORAGE_URI"] = cfg.RATE_LIMIT_STORAGE_URL

    db.init_app(app)
    limiter.init_app(app)
    init_metrics(app)

    from app.controllers.auth import bp as auth_bp
    from app.controllers.notifications import bp as notifications_bp
    from app.controllers.roles import bp as roles_bp
    from app.controllers.users import bp as users_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(roles_bp)
    app.register_blueprint(users_bp)
    register_error_handlers(app)

    @app.get("/healthz")
    def healthz():
                """Health check.

                ---
                get:
                    tags:
                        - Health
                    summary: Health check
                    responses:
                        '200':
                            description: OK
                            content:
                                application/json:
                                    schema:
                                        type: object
                                        required:
                                            - status
                                        properties:
                                            status:
                                                type: string
                """

                return {"status": "ok"}

    from app.openapi import init_openapi

    init_openapi(app)

    return app
