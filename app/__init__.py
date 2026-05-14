from dotenv import load_dotenv
from flask import Flask, request

from app.config import Config
from app.errors import register_error_handlers
from app.extensions import db, limiter
from app.observability import init_metrics
from app.services.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError


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

    demo_breaker = CircuitBreaker(
        name="demo_dependency",
        failure_threshold=3,
        recovery_timeout_seconds=10,
    )

    @app.get("/circuit-breaker/demo")
    def circuit_breaker_demo():
        """Circuit breaker demo.

        ---
        get:
            tags:
                - Resilience
            summary: Demonstrate circuit breaker behavior
            parameters:
                - in: query
                  name: fail
                  required: false
                  schema:
                    type: boolean
                  description: Force the protected demo operation to fail.
                - in: query
                  name: reset
                  required: false
                  schema:
                    type: boolean
                  description: Reset the circuit breaker state before running.
            responses:
                '200':
                    description: Demo operation succeeded
                    content:
                        application/json:
                            schema:
                                type: object
                '502':
                    description: Protected operation failed
                    content:
                        application/json:
                            schema:
                                type: object
                '503':
                    description: Circuit breaker is open
                    content:
                        application/json:
                            schema:
                                type: object
        """
        if request.args.get("reset", "").lower() in {"1", "true", "yes"}:
            demo_breaker.reset()

        should_fail = request.args.get("fail", "").lower() in {"1", "true", "yes"}

        def protected_operation():
            if should_fail:
                raise RuntimeError("demo dependency failed")
            return "demo dependency responded"

        try:
            message = demo_breaker.call(protected_operation)
            return {"message": message, "breaker": demo_breaker.snapshot()}
        except CircuitBreakerOpenError as exc:
            return {"code": "CIRCUIT_OPEN", "message": str(exc), "breaker": demo_breaker.snapshot()}, 503
        except RuntimeError as exc:
            return {"code": "UPSTREAM_FAILED", "message": str(exc), "breaker": demo_breaker.snapshot()}, 502

    from app.openapi import init_openapi

    init_openapi(app)

    return app
