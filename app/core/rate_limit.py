"""
Session tracking, question counting, and sliding-window rate limiting.
Enforces the 2-question anonymous cap and per-minute abuse thresholds.
"""
import time
import threading
from collections import defaultdict, deque
from typing import Dict, Deque, Optional
from fastapi import HTTPException, status, Request
from app.core.config import get_settings
from app.core.security import is_greeting_or_command


class SessionTracker:
    """
    Tracks question counts and request rates per user/session.
    Thread-safe and supports anonymous session preservation through sign-in.
    """

    def __init__(self, window_seconds: int = 60):
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        # session_id/user_id -> question count
        self._question_counts: Dict[str, int] = defaultdict(int)
        # identifier -> deque of timestamps
        self._request_timestamps: Dict[str, Deque[float]] = defaultdict(deque)
        # anonymous session -> linked authenticated user id
        self._session_user_links: Dict[str, str] = {}

    def record_and_check_question(
        self,
        session_id: str,
        question: str,
        user_sub: Optional[str] = None
    ) -> int:
        """
        Increments question count unless question is an approved greeting/command.
        Enforces that anonymous users cannot exceed anonymous_question_limit.
        Preserves question count across sign-in.
        """
        settings = get_settings()

        if is_greeting_or_command(question):
            return 0  # Does not count towards question quotas

        with self._lock:
            # Handle anonymous session linking to authenticated sub
            tracking_id = session_id
            if user_sub:
                if session_id in self._question_counts and user_sub not in self._question_counts:
                    # Transfer count upon sign-in so sign-in does not reset the count
                    self._question_counts[user_sub] = self._question_counts[session_id]
                tracking_id = user_sub
                self._session_user_links[session_id] = user_sub

            current_count = self._question_counts[tracking_id]

            # If user is anonymous and reached limit, require login
            if not user_sub and current_count >= settings.anonymous_question_limit:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "code": "LOGIN_REQUIRED",
                        "message": f"You have reached the free limit of {settings.anonymous_question_limit} questions. Please sign in with Google to continue.",
                    },
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # If user is logged in and reached conversation follow-up cap
            if user_sub and current_count >= (settings.anonymous_question_limit + settings.max_conversation_followups):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "code": "CONVERSATION_LIMIT_REACHED",
                        "message": f"You have reached the maximum of {settings.max_conversation_followups} follow-up questions for this session.",
                        "retry_after_seconds": 3600,
                    },
                    headers={"Retry-After": "3600"},
                )

            self._question_counts[tracking_id] += 1
            return self._question_counts[tracking_id]

    def check_rate_limit(self, identifier: str, limit: int) -> int:
        """
        Sliding-window abuse limit (requests per minute).
        Raises 429 if threshold is exceeded.
        """
        now = time.time()
        with self._lock:
            timestamps = self._request_timestamps[identifier]
            while timestamps and timestamps[0] <= now - self.window_seconds:
                timestamps.popleft()

            if len(timestamps) >= limit:
                oldest = timestamps[0]
                retry_after = max(1, int(self.window_seconds - (now - oldest)))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": f"Rate limit exceeded. Please wait {retry_after} seconds before sending another request.",
                        "retry_after_seconds": retry_after,
                    },
                    headers={"Retry-After": str(retry_after)},
                )

            timestamps.append(now)
            return limit - len(timestamps)

    def reset(self):
        """Reset state (for test isolation)."""
        with self._lock:
            self._question_counts.clear()
            self._request_timestamps.clear()
            self._session_user_links.clear()


session_tracker = SessionTracker()
