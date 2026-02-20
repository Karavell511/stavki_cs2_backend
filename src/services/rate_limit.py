import time

from redis.asyncio import Redis


class RateLimiter:
    def __init__(self, redis: Redis):
        self.redis = redis

    async def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        now_bucket = int(time.time() // window_seconds)
        redis_key = f"rl:{key}:{now_bucket}"
        count = await self.redis.incr(redis_key)
        if count == 1:
            await self.redis.expire(redis_key, window_seconds + 1)
        return count <= limit
