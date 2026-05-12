import json
import logging
from typing import Any

import redis

logger = logging.getLogger(__name__)


class RedisJobQueue:
    def __init__(self, redis_url: str, queue_name: str):
        self._client = redis.Redis.from_url(redis_url)
        self._queue_name = queue_name
        self._client.ping()
        logger.info("Redis job queue connected", extra={"queue": queue_name})

    def enqueue(self, job: dict[str, Any]) -> None:
        self._client.lpush(self._queue_name, json.dumps(job))
        logger.info("Redis email job queued", extra={"queue": self._queue_name, "type": job.get("type")})

    def dequeue_blocking(self, *, timeout_seconds: int = 5) -> dict[str, Any] | None:
        item = self._client.brpop(self._queue_name, timeout=timeout_seconds)
        if item is None:
            return None
        _queue, raw = item
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode("utf-8")
        return json.loads(raw)
