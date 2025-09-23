import asyncio
import json
import logging
from typing import Any, Dict, Optional

import redis.asyncio as aioredis
from cachetools import TTLCache

from ..models import Account, ApiKey, ModelCost

logger = logging.getLogger(__name__)


class CacheManager:
    def __init__(self, redis_url: str, cache_ttl: int = 3600):
        self.redis_url = redis_url
        self.cache_ttl = cache_ttl
        self.redis_client: Optional[aioredis.Redis] = None
        self.pubsub: Optional[aioredis.client.PubSub] = None

        # Local L1 cache
        self.account_cache: TTLCache = TTLCache(maxsize=10000, ttl=cache_ttl)
        self.apikey_cache: TTLCache = TTLCache(maxsize=10000, ttl=cache_ttl)
        self.modelcost_cache: TTLCache = TTLCache(maxsize=1000, ttl=cache_ttl)

        self._cache_invalidation_task: Optional[asyncio.Task] = None

    async def connect(self):
        self.redis_client = aioredis.from_url(self.redis_url)
        self.pubsub = self.redis_client.pubsub()
        await self.pubsub.subscribe("cache-invalidation")

        # Start cache invalidation listener
        self._cache_invalidation_task = asyncio.create_task(
            self._listen_for_cache_invalidation()
        )

    async def disconnect(self):
        if self._cache_invalidation_task:
            self._cache_invalidation_task.cancel()

        if self.pubsub:
            await self.pubsub.unsubscribe("cache-invalidation")
            await self.pubsub.close()

        if self.redis_client:
            await self.redis_client.close()

    async def _listen_for_cache_invalidation(self):
        try:
            while True:
                message = await self.pubsub.get_message(ignore_subscribe_messages=True)
                if message:
                    try:
                        data = json.loads(message["data"])
                        await self._handle_cache_invalidation(data)
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.error(f"Invalid cache invalidation message: {e}")
                await asyncio.sleep(0.01)  # Small delay to prevent tight loop
        except asyncio.CancelledError:
            logger.info("Cache invalidation listener stopped")
        except Exception as e:
            logger.error(f"Error in cache invalidation listener: {e}")

    async def _handle_cache_invalidation(self, data: Dict[str, Any]):
        cache_type = data.get("type")
        cache_key = data.get("key")

        if not cache_type or not cache_key:
            return

        if cache_type == "account":
            self.account_cache.pop(f"account:{cache_key}", None)
            logger.debug(f"Invalidated account cache for: {cache_key}")
        elif cache_type == "apikey":
            self.apikey_cache.pop(f"apikey:{cache_key}", None)
            logger.debug(f"Invalidated apikey cache for: {cache_key}")
        elif cache_type == "modelcost":
            self.modelcost_cache.pop(f"modelcost:{cache_key}", None)
            logger.debug(f"Invalidated modelcost cache for: {cache_key}")

    async def publish_cache_invalidation(self, cache_type: str, cache_key: str):
        if self.redis_client:
            message = json.dumps({"type": cache_type, "key": cache_key})
            await self.redis_client.publish("cache-invalidation", message)

    # Account cache methods
    def get_account(self, user_id: str) -> Optional[Account]:
        return self.account_cache.get(f"account:{user_id}")

    def set_account(self, user_id: str, account: Account):
        self.account_cache[f"account:{user_id}"] = account

    # API Key cache methods
    def get_apikey(self, api_key: str) -> Optional[ApiKey]:
        return self.apikey_cache.get(f"apikey:{api_key}")

    def set_apikey(self, api_key: str, apikey_obj: ApiKey):
        self.apikey_cache[f"apikey:{api_key}"] = apikey_obj

    # Model cost cache methods
    def get_model_cost(self, model_name: str) -> Optional[ModelCost]:
        return self.modelcost_cache.get(f"modelcost:{model_name}")

    def set_model_cost(self, model_name: str, model_cost: ModelCost):
        self.modelcost_cache[f"modelcost:{model_name}"] = model_cost


# Global cache manager instance
cache_manager = CacheManager("redis://localhost:6379")
