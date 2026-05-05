import os
from dataclasses import dataclass


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Config:
    SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")
    SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8082"))
    JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-only-secret")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_TTL_SECONDS: int = int(os.getenv("ACCESS_TOKEN_TTL_SECONDS", "900"))
    REFRESH_TOKEN_TTL_SECONDS: int = int(os.getenv("REFRESH_TOKEN_TTL_SECONDS", "604800"))
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    FACEBOOK_APP_ID: str = os.getenv("FACEBOOK_APP_ID", "")
    FACEBOOK_APP_SECRET: str = os.getenv("FACEBOOK_APP_SECRET", "")
    REDIS_URL: str = os.getenv("REDIS_URL", "")
    RATE_LIMIT_STORAGE_URL: str = os.getenv("RATE_LIMIT_STORAGE_URL", "memory://")
    ENABLE_SWAGGER: bool = _bool(os.getenv("ENABLE_SWAGGER"), True)
    TESTING: bool = _bool(os.getenv("TESTING"))
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    STORAGE_PROVIDER: str = os.getenv("STORAGE_PROVIDER", "minio")
    S3_ENDPOINT_URL: str = os.getenv("S3_ENDPOINT_URL", "http://minio:9000")
    S3_ACCESS_KEY_ID: str = os.getenv("S3_ACCESS_KEY_ID", "minioadmin")
    S3_SECRET_ACCESS_KEY: str = os.getenv("S3_SECRET_ACCESS_KEY", "minioadmin")
    S3_BUCKET: str = os.getenv("S3_BUCKET", "ticketrush-media")
    S3_REGION: str = os.getenv("S3_REGION", "us-east-1")
    S3_PUBLIC_BASE_URL: str = os.getenv("S3_PUBLIC_BASE_URL", "http://localhost:9000/ticketrush-media")
    UPLOAD_MAX_BYTES: int = int(os.getenv("UPLOAD_MAX_BYTES", str(50 * 1024 * 1024)))

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        explicit = os.getenv("DATABASE_URL")
        if explicit:
            return explicit

        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_PORT", "5432")
        user = os.getenv("POSTGRES_USER", "postgres")
        password = os.getenv("POSTGRES_PASSWORD", "postgres")
        db_name = os.getenv("POSTGRES_DB", "ticket_db")
        sslmode = os.getenv("POSTGRES_SSLMODE", "disable")
        return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db_name}?sslmode={sslmode}"
