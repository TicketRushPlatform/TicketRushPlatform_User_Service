import logging
import time

from dotenv import load_dotenv

from app.config import Config
from app.services.email_service import EmailService
from app.services.job_queue import RedisJobQueue


def _configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def _handle_job(email: EmailService, job: dict) -> bool:
    job_type = job.get("type")

    if job_type == "password_reset":
        return email.send_password_reset(
            job.get("to_email") or "",
            job.get("reset_url") or "",
            job.get("full_name"),
        )

    if job_type == "booking_confirmation":
        return email.send_booking_confirmation(
            job.get("to_email") or "",
            job.get("payload") or {},
        )

    logging.getLogger(__name__).warning("Unknown email job type", extra={"type": job_type})
    return True


def main():
    load_dotenv()
    _configure_logging()

    cfg = Config()
    if not cfg.REDIS_URL:
        raise RuntimeError("REDIS_URL is required to run email worker")

    queue_name = getattr(cfg, "EMAIL_QUEUE_NAME", "user_api:email_jobs")
    queue = RedisJobQueue(cfg.REDIS_URL, queue_name)
    email = EmailService(cfg)

    logger = logging.getLogger(__name__)
    logger.info("Email worker connected to Redis and started", extra={"queue": queue_name})

    while True:
        try:
            job = queue.dequeue_blocking(timeout_seconds=5)
            if job is None:
                continue

            ok = _handle_job(email, job)
            if not ok:
                logger.warning("Email job send returned false", extra={"type": job.get("type")})
        except Exception as exc:  # noqa: BLE001
            logger.exception("Email worker error", extra={"error": str(exc)})
            time.sleep(1)


if __name__ == "__main__":
    main()
