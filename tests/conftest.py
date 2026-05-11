import pytest

from app import create_app
from app.extensions import db


class TestConfig:
    SERVER_HOST = "127.0.0.1"
    SERVER_PORT = 8082
    JWT_SECRET = "test-secret-long-enough"
    JWT_ALGORITHM = "HS256"
    ACCESS_TOKEN_TTL_SECONDS = 900
    REFRESH_TOKEN_TTL_SECONDS = 604800
    GOOGLE_CLIENT_ID = "google-client"
    GOOGLE_CLIENT_SECRET = "google-secret"
    FACEBOOK_APP_ID = "facebook-app"
    FACEBOOK_APP_SECRET = "facebook-secret"
    REDIS_URL = ""
    RATE_LIMIT_STORAGE_URL = "memory://"
    TESTING = True
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    STORAGE_PROVIDER = "minio"
    S3_ENDPOINT_URL = "http://minio:9000"
    S3_ACCESS_KEY_ID = "minioadmin"
    S3_SECRET_ACCESS_KEY = "minioadmin"
    S3_BUCKET = "ticketrush-media"
    S3_REGION = "us-east-1"
    S3_PUBLIC_BASE_URL = "http://minio:9000/ticketrush-media"
    UPLOAD_MAX_BYTES = 5 * 1024 * 1024
    APP_PUBLIC_URL = "http://localhost:3000"
    PASSWORD_RESET_TOKEN_TTL_SECONDS = 1800
    SMTP_HOST = ""
    SMTP_PORT = 587
    SMTP_USERNAME = ""
    SMTP_PASSWORD = ""
    SMTP_FROM_EMAIL = "no-reply@ticketrush.local"
    SMTP_FROM_NAME = "TicketRush"
    SMTP_USE_TLS = True

    @property
    def SQLALCHEMY_DATABASE_URI(self):
        return "sqlite:///:memory:"


@pytest.fixture()
def app():
    flask_app = create_app(TestConfig())
    with flask_app.app_context():
        db.create_all()
        yield flask_app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()
