"""Global emergency stop (E-STOP).

When engaged, the permission engine denies every tool action and the orchestrator
halts between steps. Backed by a Redis key so the API and the tool-worker share one
switch; falls back to an in-memory flag when Redis is unavailable (dev/tests), with
graceful degradation so a missing Redis never crashes a request.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class EStop:
    def __init__(self, redis=None, key: str = "apex:estop") -> None:
        self._redis = redis
        self._key = key
        self._memory_engaged = False  # fallback when no/!reachable Redis

    @classmethod
    def from_settings(cls, settings) -> EStop:
        """Build from settings, attaching a Redis client if the package is present.

        Import and client creation are guarded so the app runs without Redis in dev.
        """
        redis_client = None
        try:
            import redis.asyncio as aioredis

            redis_client = aioredis.from_url(settings.redis_url)
        except Exception as exc:  # pragma: no cover - environment dependent
            logger.warning("E-STOP falling back to in-memory (no Redis): %r", exc)
        return cls(redis=redis_client, key=settings.estop_key)

    async def engage(self, reason: str = "manual") -> None:
        self._memory_engaged = True
        if self._redis is not None:
            try:
                await self._redis.set(self._key, reason)
            except Exception as exc:  # pragma: no cover
                logger.warning("E-STOP engage: Redis unavailable, memory-only: %r", exc)

    async def clear(self) -> None:
        self._memory_engaged = False
        if self._redis is not None:
            try:
                await self._redis.delete(self._key)
            except Exception as exc:  # pragma: no cover
                logger.warning("E-STOP clear: Redis unavailable, memory-only: %r", exc)

    async def is_engaged(self) -> bool:
        if self._redis is not None:
            try:
                return bool(await self._redis.exists(self._key))
            except Exception as exc:  # pragma: no cover
                logger.warning("E-STOP read: Redis unavailable, memory-only: %r", exc)
        return self._memory_engaged
