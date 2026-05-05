from __future__ import annotations

from datetime import datetime, timezone
import json
from uuid import uuid4

from minio import Minio
from minio.error import S3Error

from app.errors import AppError


class StorageService:
    _bucket_checked = False

    def __init__(self, config):
        self.config = config
        endpoint = (config.S3_ENDPOINT_URL or "").replace("http://", "").replace("https://", "")
        secure = config.S3_ENDPOINT_URL.startswith("https://")
        self.client = Minio(
            endpoint,
            access_key=config.S3_ACCESS_KEY_ID,
            secret_key=config.S3_SECRET_ACCESS_KEY,
            secure=secure,
            region=config.S3_REGION or None,
        )

    def upload_user_media(self, user_id: str, file_storage, *, media_kind: str) -> str:
        if media_kind not in {"avatar", "video"}:
            raise AppError("UNSUPPORTED_MEDIA_KIND", "Only avatar and video uploads are supported.", 400)
        if file_storage is None or not getattr(file_storage, "filename", ""):
            raise AppError("MISSING_FILE", "Upload file is required.", 400)

        mime_type = (file_storage.mimetype or "").lower()
        if media_kind == "avatar" and not mime_type.startswith("image/"):
            raise AppError("INVALID_MEDIA_TYPE", "Avatar must be an image file.", 400)
        if media_kind == "video" and not mime_type.startswith("video/"):
            raise AppError("INVALID_MEDIA_TYPE", "Video must be a video file.", 400)

        file_storage.stream.seek(0, 2)
        size = file_storage.stream.tell()
        file_storage.stream.seek(0)
        if size <= 0:
            raise AppError("EMPTY_FILE", "Upload file cannot be empty.", 400)
        if size > self.config.UPLOAD_MAX_BYTES:
            raise AppError(
                "FILE_TOO_LARGE",
                "Upload file exceeds maximum allowed size.",
                413,
                {"max_bytes": self.config.UPLOAD_MAX_BYTES},
            )

        self._ensure_bucket()
        ext = self._guess_extension(file_storage.filename)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        object_name = f"{media_kind}s/{user_id}/{timestamp}-{uuid4().hex}{ext}"

        try:
            self.client.put_object(
                bucket_name=self.config.S3_BUCKET,
                object_name=object_name,
                data=file_storage.stream,
                length=size,
                content_type=mime_type or "application/octet-stream",
            )
            uploaded = self.client.stat_object(self.config.S3_BUCKET, object_name)
            if uploaded.size <= 0:
                raise AppError("STORAGE_UPLOAD_FAILED", "Uploaded file is empty in object storage.", 502)
        except S3Error as exc:
            raise AppError("STORAGE_UPLOAD_FAILED", "Failed to upload file to object storage.", 502, {"reason": str(exc)}) from exc

        base_url = self.config.S3_PUBLIC_BASE_URL.rstrip("/")
        return f"{base_url}/{object_name}"

    def _ensure_bucket(self) -> None:
        if StorageService._bucket_checked:
            return
        try:
            if not self.client.bucket_exists(self.config.S3_BUCKET):
                self.client.make_bucket(self.config.S3_BUCKET)
            # Make uploaded assets readable via direct URL in browser.
            policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": ["*"]},
                        "Action": ["s3:GetObject"],
                        "Resource": [f"arn:aws:s3:::{self.config.S3_BUCKET}/*"],
                    }
                ],
            }
            self.client.set_bucket_policy(self.config.S3_BUCKET, json.dumps(policy))
        except S3Error as exc:
            raise AppError("STORAGE_UNAVAILABLE", "Object storage is not available.", 503, {"reason": str(exc)}) from exc
        StorageService._bucket_checked = True

    @staticmethod
    def _guess_extension(filename: str) -> str:
        if "." not in filename:
            return ""
        return f".{filename.rsplit('.', 1)[1].lower()}"
