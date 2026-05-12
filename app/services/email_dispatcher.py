from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from app.services.email_service import EmailService
from app.services.job_queue import RedisJobQueue

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="email-dispatch")
_logger = logging.getLogger(__name__)


class EmailDispatcher:
    def __init__(self, config):
        self.config = config
        self.email = EmailService(config)
        self.queue: RedisJobQueue | None = None

        redis_url = getattr(config, "REDIS_URL", "")
        queue_name = getattr(config, "EMAIL_QUEUE_NAME", "user_api:email_jobs")
        if redis_url:
            try:
                self.queue = RedisJobQueue(redis_url, queue_name)
                _logger.info("Email dispatcher using Redis queue", extra={"queue": queue_name})
            except Exception as exc:  # noqa: BLE001
                _logger.exception("Email dispatcher Redis connection failed; falling back to background thread", extra={"error": str(exc)})
        else:
            _logger.info("Email dispatcher Redis disabled; using background thread")

    def send_password_reset(self, to_email: str, reset_url: str, full_name: str | None = None) -> None:
        if self.queue is None:
            self._submit(self.email.send_password_reset, to_email, reset_url, full_name)
            return

        self.queue.enqueue(
            {
                "type": "password_reset",
                "to_email": to_email,
                "reset_url": reset_url,
                "full_name": full_name,
            }
        )

    def send_booking_confirmation(self, to_email: str, payload: dict[str, Any]) -> None:
        if self.queue is None:
            self._submit(self.email.send_booking_confirmation, to_email, payload)
            return

        self.queue.enqueue(
            {
                "type": "booking_confirmation",
                "to_email": to_email,
                "payload": payload,
            }
        )

    def _submit(self, fn, *args) -> None:
        if getattr(self.config, "TESTING", False):
            fn(*args)
            return

        future = _executor.submit(fn, *args)
        future.add_done_callback(self._log_failure)

    @staticmethod
    def _log_failure(future) -> None:
        try:
            future.result()
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Async email dispatch failed", extra={"error": str(exc)})
