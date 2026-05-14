from __future__ import annotations

import time
from collections.abc import Callable
from threading import Lock
from typing import TypeVar

T = TypeVar("T")


class CircuitBreakerOpenError(RuntimeError):
    pass


class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 3, recovery_timeout_seconds: float = 10.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self._failure_count = 0
        self._state = "closed"
        self._opened_at: float | None = None
        self._lock = Lock()

    def call(self, operation: Callable[[], T]) -> T:
        self._before_call()
        try:
            result = operation()
        except Exception:
            self._record_failure()
            raise
        self._record_success()
        return result

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "name": self.name,
                "state": self._state,
                "failure_count": self._failure_count,
                "failure_threshold": self.failure_threshold,
                "recovery_timeout_seconds": self.recovery_timeout_seconds,
            }

    def reset(self) -> None:
        with self._lock:
            self._state = "closed"
            self._failure_count = 0
            self._opened_at = None

    def _before_call(self) -> None:
        with self._lock:
            if self._state != "open":
                return

            opened_at = self._opened_at or 0.0
            if time.monotonic() - opened_at >= self.recovery_timeout_seconds:
                self._state = "half_open"
                return

            raise CircuitBreakerOpenError(f"circuit breaker '{self.name}' is open")

    def _record_success(self) -> None:
        with self._lock:
            self._state = "closed"
            self._failure_count = 0
            self._opened_at = None

    def _record_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            if self._state == "half_open" or self._failure_count >= self.failure_threshold:
                self._state = "open"
                self._opened_at = time.monotonic()
