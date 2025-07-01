from typing import Any, Optional
import json
import hashlib
import logging

import redis

from .config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class RedisCache:
    """Thin wrapper around Redis JSON cache. Falls back to in-memory dict."""

    def __init__(self) -> None:
        self.cli = None
        self._memory: dict[str, str] = {}
        try:
            # Short timeout to avoid blocking, force connection with ping
            self.cli = redis.Redis.from_url(
                settings.redis_url, decode_responses=True, socket_connect_timeout=1
            )
            self.cli.ping()
            logger.info("Redis cache is connected.")
        except Exception:
            self.cli = None  # Ensure cli is None on any failure
            logger.warning("Redis connection failed. Falling back to in-memory cache.")

    @staticmethod
    def _hash_payload(payload: dict) -> str:
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        return digest

    def get(self, payload: dict) -> Optional[dict]:
        key = self._hash_payload(payload)
        raw = None
        if self.cli:
            try:
                raw = self.cli.get(key)
            except Exception:
                logger.error("Redis GET failed. Disabling Redis for this session.")
                self.cli = None
                raw = self._memory.get(key)
        else:
            raw = self._memory.get(key)

        return json.loads(raw) if raw else None

    def set(self, payload: dict, result: dict) -> None:
        key = self._hash_payload(payload)
        value = json.dumps(result)
        if self.cli:
            try:
                self.cli.setex(key, settings.cache_ttl_seconds, value)
            except Exception:
                logger.error("Redis SET failed. Disabling Redis for this session.")
                self.cli = None
                self._memory[key] = value
        else:
            self._memory[key] = value 