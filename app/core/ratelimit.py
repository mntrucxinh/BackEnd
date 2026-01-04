from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock
from typing import Dict, List, Optional, Tuple

from fastapi import Request, status
from fastapi.responses import JSONResponse


@dataclass(frozen=True)
class RateLimitRule:
    path: str  # prefix match
    limit: int
    window_seconds: int


RATE_LIMIT_RULES: List[RateLimitRule] = [
    RateLimitRule(path="/auth/google/login", limit=10, window_seconds=300),
    RateLimitRule(path="/auth/local/signin", limit=10, window_seconds=300),
    RateLimitRule(path="/contact", limit=5, window_seconds=600),
]


class RateLimiter:
    """
    Đơn giản: lưu vết các request gần đây theo key (path prefix + IP).
    Dùng in-memory cho dev/đơn instance; nếu deploy multi-instance cần chuyển sang Redis.
    """

    def __init__(self, rules: List[RateLimitRule]) -> None:
        self.rules = rules
        self._buckets: Dict[Tuple[str, str], List[float]] = {}
        self._lock = Lock()

    def _match_rule(self, path: str) -> Optional[RateLimitRule]:
        for rule in self.rules:
            if path.startswith(rule.path):
                return rule
        return None

    def _client_ip(self, request: Request) -> str:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def check(self, request: Request) -> Optional[JSONResponse]:
        rule = self._match_rule(request.url.path)
        if not rule:
            return None

        key = (rule.path, self._client_ip(request))
        now = time.time()
        window_start = now - rule.window_seconds

        with self._lock:
            history = self._buckets.setdefault(key, [])
            # drop expired
            while history and history[0] < window_start:
                history.pop(0)

            if len(history) >= rule.limit:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "code": "rate_limited",
                        "message": "Vượt quá giới hạn, vui lòng thử lại sau.",
                        "fields": None,
                    },
                )

            history.append(now)

        return None
