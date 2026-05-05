from http import HTTPStatus

from flask import jsonify
from marshmallow import ValidationError


class AppError(Exception):
    def __init__(self, code: str, message: str, status: int = 400, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.details = details or {}


def error_response(code: str, message: str, status: int, details: dict | None = None):
    payload = {"code": code, "message": message, "details": details or {}}
    return jsonify(payload), status


def register_error_handlers(app):
    @app.errorhandler(AppError)
    def handle_app_error(error: AppError):
        return error_response(error.code, error.message, error.status, error.details)

    @app.errorhandler(ValidationError)
    def handle_validation_error(error: ValidationError):
        return error_response(
            "VALIDATION_ERROR",
            "Request payload failed validation.",
            HTTPStatus.BAD_REQUEST,
            error.messages,
        )

    @app.errorhandler(404)
    def handle_not_found(_):
        return error_response("NOT_FOUND", "Resource was not found.", HTTPStatus.NOT_FOUND)

    @app.errorhandler(429)
    def handle_rate_limited(error):
        return error_response("RATE_LIMITED", "Too many requests.", HTTPStatus.TOO_MANY_REQUESTS, {"limit": str(error.description)})
