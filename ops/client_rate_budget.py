"""Cooperative, single-instance admission for bounded public MCP clients.

This module has no network transport and never retries a callback.
"""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable
from datetime import UTC
from email.utils import parsedate_to_datetime
from typing import TypeVar

T = TypeVar("T")


class AdmissionDeadlineExceeded(TimeoutError):
    """No request may start, or be reported successful, past its deadline."""


class AdmissionCancelled(RuntimeError):
    """Queued admission was cancelled; in-flight work must cooperate."""


class AttemptBudgetExceeded(RuntimeError):
    """The caller's finite attempt count is exhausted."""


class RateLimited(RuntimeError):
    """The transport observed HTTP 429; preserve the outcome without replay."""

    def __init__(self, retry_after: str | None = None) -> None:
        super().__init__("HTTP 429; no automatic retry was performed.")
        self.retry_after = retry_after


class RateLimitHold(RateLimited):
    """The shared instance remains paused until explicit eligible resume."""

    def __init__(self, remaining_seconds: float) -> None:
        super().__init__()
        self.remaining_seconds = remaining_seconds


def retry_after_seconds(
    value: str | None, *, wall_time: float, fallback_seconds: float = 10.0
) -> float:
    """Read delta-seconds or HTTP-date; invalid input uses a finite fallback.

    An excessive valid delay remains excessive, including infinity on numeric
    overflow. It is never shortened to fit a job deadline.
    """
    if not math.isfinite(fallback_seconds) or fallback_seconds < 0:
        raise ValueError("Fallback delay must be finite and nonnegative")
    if not isinstance(value, str) or not value.strip():
        return fallback_seconds
    value = value.strip()
    if value.isascii() and value.isdecimal():
        return float(value)
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        delay = parsed.timestamp() - wall_time
    except (ValueError, TypeError, OverflowError):
        return fallback_seconds
    return max(0.0, delay) if math.isfinite(delay) else math.inf


class RateBudget:
    """Serialize cooperating calls, including discovery, in one shared instance.

    Ten-second start spacing is conservative for the observed six/minute policy.
    It does not coordinate other instances/processes or promise server capacity.
    execute() calls its transport once, passing remaining seconds. The transport
    must honor that timeout; arbitrary synchronous I/O cannot be force-cancelled.
    A late return is rejected. HTTP 429 latches admission until explicit resume.
    """

    def __init__(
        self,
        *,
        max_attempts: int = 4,
        minimum_interval: float = 10.0,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if type(max_attempts) is not int or max_attempts < 1:
            raise ValueError("A positive finite integer attempt budget is required")
        if not math.isfinite(minimum_interval) or minimum_interval < 10.0:
            raise ValueError("Admission interval must be finite and at least 10s")
        self._max_attempts = max_attempts
        self._interval = minimum_interval
        self._clock = clock
        self._wall_clock = wall_clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._attempts = 0
        self._next_allowed = clock()
        self._limited = False
        self._limited_until = 0.0

    def _remaining(
        self, deadline: float, cancelled: Callable[[], bool] | None
    ) -> float:
        if not math.isfinite(deadline):
            raise ValueError("An absolute finite monotonic deadline is required")
        if cancelled is not None and cancelled():
            raise AdmissionCancelled("Request admission was cancelled")
        remaining = deadline - self._clock()
        if remaining <= 0:
            raise AdmissionDeadlineExceeded("Request deadline exhausted")
        return remaining

    def _acquire(self, deadline: float, cancelled: Callable[[], bool] | None) -> None:
        while True:
            remaining = self._remaining(deadline, cancelled)
            if self._lock.acquire(blocking=False):
                return
            self._sleep(min(0.05, remaining))

    def execute(
        self,
        operation: Callable[[float], T],
        *,
        deadline: float,
        cancelled: Callable[[], bool] | None = None,
    ) -> T:
        """Call operation once after admission. No transport or retry loop here."""
        self._acquire(deadline, cancelled)
        try:
            self._remaining(deadline, cancelled)
            if self._limited:
                raise RateLimitHold(max(0.0, self._limited_until - self._clock()))
            if self._attempts >= self._max_attempts:
                raise AttemptBudgetExceeded("Finite request attempt budget exhausted")
            while self._next_allowed > self._clock():
                remaining = self._remaining(deadline, cancelled)
                wait = self._next_allowed - self._clock()
                if wait <= 0:
                    break
                if wait >= remaining:
                    raise AdmissionDeadlineExceeded(
                        "Admission delay would consume the remaining deadline"
                    )
                self._sleep(min(wait, remaining, 0.05))
            remaining = self._remaining(deadline, cancelled)
            self._attempts += 1
            self._next_allowed = self._clock() + self._interval
            try:
                result = operation(remaining)
            except RateLimited as error:
                delay = retry_after_seconds(
                    error.retry_after, wall_time=self._wall_clock()
                )
                self._limited_until = max(self._next_allowed, self._clock() + delay)
                self._limited = True
                raise
            self._remaining(deadline, cancelled)
            return result
        finally:
            self._lock.release()

    def resume(
        self,
        *,
        deadline: float,
        cancelled: Callable[[], bool] | None = None,
    ) -> bool:
        """Explicitly clear an elapsed cooldown; do not wait, send or reset counts."""
        self._acquire(deadline, cancelled)
        try:
            self._remaining(deadline, cancelled)
            if not self._limited:
                return False
            remaining = self._limited_until - self._clock()
            if remaining > 0:
                raise RateLimitHold(remaining)
            self._limited = False
            self._next_allowed = max(self._next_allowed, self._limited_until)
            return True
        finally:
            self._lock.release()
