from __future__ import annotations

import time
from dataclasses import dataclass

from redis import Redis

from app.core.config import get_settings


@dataclass
class RateLimitResult:
    allowed: bool
    tokens_left: float


class TokenBucketRateLimiter:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        settings = get_settings()
        self.capacity = float(settings.rate_limit_capacity)
        self.refill_per_sec = float(settings.rate_limit_refill_per_sec)

    def allow(self, user_id: str, cost: float = 1.0) -> RateLimitResult:
        key = f"ratelimit:user:{user_id}"
        now = time.time()

        data = self.redis.hgetall(key)
        if not data:
            tokens = self.capacity
            last_refill = now
        else:
            tokens = float(data.get(b"tokens", self.capacity))
            last_refill = float(data.get(b"last_refill", now))

        elapsed = max(0.0, now - last_refill)
        tokens = min(self.capacity, tokens + elapsed * self.refill_per_sec)

        allowed = tokens >= cost
        if allowed:
            tokens -= cost

        self.redis.hset(key, mapping={"tokens": tokens, "last_refill": now})
        self.redis.expire(key, 3600)
        return RateLimitResult(allowed=allowed, tokens_left=tokens)
