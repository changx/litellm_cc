"""
Redis client management
"""
import redis.asyncio as redis
from gateway.utils.config import settings


# Global Redis client
_redis_client: redis.Redis = None


async def connect_to_redis():
    """Initialize Redis connection"""
    global _redis_client
    _redis_client = redis.from_url(settings.redis_url)


async def close_redis_connection():
    """Close Redis connection"""
    global _redis_client
    if _redis_client:
        await _redis_client.close()


def get_redis_client() -> redis.Redis:
    """Get the Redis client instance"""
    return _redis_client