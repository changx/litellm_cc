"""
MongoDB connection management
"""
import motor.motor_asyncio
from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorCollection
from gateway.utils.config import settings


# Global database connection
_db_client: motor.motor_asyncio.AsyncIOMotorClient = None
_database: AsyncIOMotorDatabase = None


async def connect_to_mongo():
    """Initialize MongoDB connection"""
    global _db_client, _database
    _db_client = motor.motor_asyncio.AsyncIOMotorClient(settings.mongo_uri)
    _database = _db_client[settings.mongo_db_name]

    # Create indexes
    await _create_indexes()


async def close_mongo_connection():
    """Close MongoDB connection"""
    global _db_client
    if _db_client:
        _db_client.close()


def get_database() -> AsyncIOMotorDatabase:
    """Get the database instance"""
    return _database


def get_collection(collection_name: str) -> AsyncIOMotorCollection:
    """Get a collection by name"""
    return _database[collection_name]


async def _create_indexes():
    """Create database indexes for optimal performance"""
    # Account indexes
    accounts = get_collection("accounts")
    await accounts.create_index("user_id", unique=True)
    await accounts.create_index("is_active")

    # API Key indexes
    apikeys = get_collection("apikeys")
    await apikeys.create_index("api_key", unique=True)
    await apikeys.create_index("user_id")
    await apikeys.create_index("is_active")

    # Model Cost indexes
    modelcosts = get_collection("modelcosts")
    await modelcosts.create_index("model_name", unique=True)
    await modelcosts.create_index("provider")

    # Usage Log indexes
    usagelogs = get_collection("usagelogs")
    await usagelogs.create_index("user_id")
    await usagelogs.create_index("api_key")
    await usagelogs.create_index("timestamp")
    await usagelogs.create_index([("user_id", 1), ("timestamp", -1)])
    await usagelogs.create_index([("api_key", 1), ("timestamp", -1)])