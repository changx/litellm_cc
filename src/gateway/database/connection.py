import asyncio
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, IndexModel


class DatabaseManager:
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.database: Optional[AsyncIOMotorDatabase] = None

    async def connect(self, mongo_uri: str, db_name: str):
        self.client = AsyncIOMotorClient(mongo_uri)
        self.database = self.client[db_name]
        await self._create_indexes()

    async def disconnect(self):
        if self.client:
            self.client.close()

    async def _create_indexes(self):
        if self.database is None:
            return

        # Account indexes
        accounts_collection = self.database.accounts
        await accounts_collection.create_index([("user_id", ASCENDING)], unique=True)

        # API Key indexes
        apikeys_collection = self.database.apikeys
        await apikeys_collection.create_index([("api_key", ASCENDING)], unique=True)
        await apikeys_collection.create_index([("user_id", ASCENDING)])

        # Model cost indexes
        modelcosts_collection = self.database.modelcosts
        await modelcosts_collection.create_index(
            [("model_name", ASCENDING)], unique=True
        )

        # Usage log indexes
        usagelogs_collection = self.database.usagelogs
        await usagelogs_collection.create_index([("user_id", ASCENDING)])
        await usagelogs_collection.create_index([("api_key", ASCENDING)])
        await usagelogs_collection.create_index([("timestamp", ASCENDING)])

    def get_collection(self, name: str):
        if self.database is None:
            raise RuntimeError("Database not connected")
        return self.database[name]


db_manager = DatabaseManager()
