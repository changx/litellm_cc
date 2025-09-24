"""
L1 cache management with Redis pub/sub invalidation
"""
import json
import asyncio
import logging
from typing import Any, Optional, Dict
from datetime import datetime, timedelta
from cachetools import TTLCache
from gateway.models import Account, ApiKey, ModelCost
from gateway.database.repositories import AccountRepository, ApiKeyRepository, ModelCostRepository
from .redis_client import get_redis_client

logger = logging.getLogger(__name__)


class CacheManager:
    """Multi-level cache manager with Redis invalidation"""

    def __init__(self, cache_size: int = 10000, cache_ttl: int = 300):
        # L1 Cache - In-memory TTL cache
        self.cache: TTLCache = TTLCache(maxsize=cache_size, ttl=cache_ttl)

        # Repository instances
        self.account_repo = AccountRepository()
        self.apikey_repo = ApiKeyRepository()
        self.modelcost_repo = ModelCostRepository()

        # Redis pub/sub
        self.redis = None
        self.pubsub = None
        self._invalidation_task = None

    async def start(self):
        """Start the cache manager and Redis invalidation listener"""
        self.redis = get_redis_client()
        self.pubsub = self.redis.pubsub()

        # Subscribe to cache invalidation channel
        await self.pubsub.subscribe("cache_invalidation")

        # Start background task for handling invalidations
        self._invalidation_task = asyncio.create_task(self._handle_invalidations())
        logger.info("Cache manager started with Redis invalidation listener")

    async def stop(self):
        """Stop the cache manager"""
        if self._invalidation_task:
            self._invalidation_task.cancel()
            try:
                await self._invalidation_task
            except asyncio.CancelledError:
                pass

        if self.pubsub:
            await self.pubsub.unsubscribe("cache_invalidation")
            await self.pubsub.close()

        logger.info("Cache manager stopped")

    async def _handle_invalidations(self):
        """Handle cache invalidation messages from Redis"""
        try:
            async for message in self.pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"].decode())
                        cache_type = data.get("type")
                        key = data.get("key")

                        if cache_type and key:
                            cache_key = f"{cache_type}:{key}"
                            self.cache.pop(cache_key, None)
                            logger.debug(f"Invalidated cache key: {cache_key}")
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.error(f"Failed to process invalidation message: {e}")
        except asyncio.CancelledError:
            logger.info("Cache invalidation listener cancelled")
        except Exception as e:
            logger.error(f"Error in cache invalidation listener: {e}")

    async def publish_invalidation(self, cache_type: str, key: str):
        """Publish cache invalidation message"""
        message = json.dumps({"type": cache_type, "key": key})
        await self.redis.publish("cache_invalidation", message)
        logger.debug(f"Published invalidation for {cache_type}:{key}")

    def _get_from_cache(self, key: str) -> Optional[Any]:
        """Get item from L1 cache"""
        return self.cache.get(key)

    def _set_to_cache(self, key: str, value: Any):
        """Set item in L1 cache"""
        self.cache[key] = value

    async def get_api_key(self, api_key: str) -> Optional[ApiKey]:
        """Get API key with caching"""
        cache_key = f"apikey:{api_key}"

        # Try L1 cache first
        cached = self._get_from_cache(cache_key)
        if cached:
            logger.debug(f"Cache hit for API key: {api_key[:10]}...")
            return cached

        # L1 cache miss - query database
        key_obj = await self.apikey_repo.get_by_api_key(api_key)
        if key_obj:
            self._set_to_cache(cache_key, key_obj)
            logger.debug(f"Loaded API key from database: {api_key[:10]}...")

        return key_obj

    async def get_account(self, user_id: str) -> Optional[Account]:
        """Get account with caching"""
        cache_key = f"account:{user_id}"

        # Try L1 cache first
        cached = self._get_from_cache(cache_key)
        if cached:
            logger.debug(f"Cache hit for account: {user_id}")
            return cached

        # L1 cache miss - query database
        account = await self.account_repo.get_by_user_id(user_id)
        if account:
            self._set_to_cache(cache_key, account)
            logger.debug(f"Loaded account from database: {user_id}")

        return account

    async def get_model_cost(self, model_name: str) -> Optional[ModelCost]:
        """Get model cost with caching"""
        cache_key = f"modelcost:{model_name}"

        # Try L1 cache first
        cached = self._get_from_cache(cache_key)
        if cached:
            logger.debug(f"Cache hit for model cost: {model_name}")
            return cached

        # L1 cache miss - query database
        cost = await self.modelcost_repo.get_by_model_name(model_name)
        if cost:
            self._set_to_cache(cache_key, cost)
            logger.debug(f"Loaded model cost from database: {model_name}")

        return cost

    async def invalidate_api_key(self, api_key: str):
        """Invalidate API key cache across all instances"""
        await self.publish_invalidation("apikey", api_key)

    async def invalidate_account(self, user_id: str):
        """Invalidate account cache across all instances"""
        await self.publish_invalidation("account", user_id)

    async def invalidate_model_cost(self, model_name: str):
        """Invalidate model cost cache across all instances"""
        await self.publish_invalidation("modelcost", model_name)

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "cache_size": len(self.cache),
            "max_size": self.cache.maxsize,
            "ttl": self.cache.ttl,
            "hits": getattr(self.cache, 'hits', 0),
            "misses": getattr(self.cache, 'misses', 0)
        }


# Global cache manager instance
_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """Get the global cache manager instance"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager