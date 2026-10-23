"""
In-memory per-IP rate limiter for abuse and spam protection on public endpoints.
"""
import time
from collections import defaultdict, deque
import threading
from typing import Dict, Deque
from fastapi import Request, HTTPException, status

from app.escalations.config import get_settings


class InMemoryRateLimiter:
    """
    Sliding-window per-IP rate limiter.
    Keeps timestamps of recent requests per client IP and rejects requests
    exceeding the configured limit within a 60-second window.
    """

    def __init__(self, window_seconds: int = 60):
        self.window_seconds = window_seconds
        self._requests: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check_rate_limit(self, client_ip: str, limit: int) -> int:
        """
        Check if client_ip has exceeded limit within window.
        Returns remaining requests allowed or raises HTTPException 429.
        """
        now = time.time()
        with self._lock:
            timestamps = self._requests[client_ip]

            # Evict timestamps outside current window
            while timestamps and timestamps[0] <= now - self.window_seconds:
                timestamps.popleft()

            if len(timestamps) >= limit:
                oldest = timestamps[0]
                retry_after = max(1, int(self.window_seconds - (now - oldest)))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": f"Too many requests. Please wait {retry_after} seconds.",
                        "retry_after_seconds": retry_after,
                    },
                    headers={"Retry-After": str(retry_after)},
                )

            timestamps.append(now)
            return limit - len(timestamps)

    def reset(self):
        """Clear all stored rate limit records (useful for test isolation)."""
        with self._lock:
            self._requests.clear()


limiter = InMemoryRateLimiter()


def rate_limit_dependency(request: Request):
    """
    FastAPI dependency enforcing per-IP rate limits on public routes.
    """
    settings = get_settings()
    client_ip = request.client.host if request.client else "127.0.0.1"
    # Respect x-forwarded-for header if present
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()

    limiter.check_rate_limit(client_ip, settings.rate_limit_per_minute)
