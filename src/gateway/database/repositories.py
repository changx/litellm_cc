"""
Database repository classes for data access
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from motor.motor_asyncio import AsyncIOMotorCollection
from gateway.models import Account, ApiKey, ModelCost, UsageLog
from .connection import get_collection


class BaseRepository:
    """Base repository class with common operations"""

    def __init__(self, collection_name: str):
        self.collection_name = collection_name

    @property
    def collection(self) -> AsyncIOMotorCollection:
        return get_collection(self.collection_name)


class AccountRepository(BaseRepository):
    """Repository for Account operations"""

    def __init__(self):
        super().__init__("accounts")

    async def create_account(self, account: Account) -> Account:
        """Create a new account"""
        account_dict = account.model_dump(by_alias=True, exclude={"id"})
        result = await self.collection.insert_one(account_dict)
        account.id = result.inserted_id
        return account

    async def get_by_user_id(self, user_id: str) -> Optional[Account]:
        """Get account by user_id"""
        doc = await self.collection.find_one({"user_id": user_id})
        return Account(**doc) if doc else None

    async def update_account(self, user_id: str, updates: Dict[str, Any]) -> Optional[Account]:
        """Update account fields"""
        updates["updated_at"] = datetime.utcnow()
        result = await self.collection.find_one_and_update(
            {"user_id": user_id},
            {"$set": updates},
            return_document=True
        )
        return Account(**result) if result else None

    async def atomic_spend(self, user_id: str, amount_usd: float) -> bool:
        """Atomically add to spent_usd and return success"""
        result = await self.collection.update_one(
            {"user_id": user_id, "is_active": True},
            {"$inc": {"spent_usd": amount_usd}, "$set": {"updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0

    async def list_accounts(self, skip: int = 0, limit: int = 100) -> List[Account]:
        """List accounts with pagination"""
        cursor = self.collection.find().skip(skip).limit(limit)
        accounts = []
        async for doc in cursor:
            accounts.append(Account(**doc))
        return accounts


class ApiKeyRepository(BaseRepository):
    """Repository for API Key operations"""

    def __init__(self):
        super().__init__("apikeys")

    async def create_api_key(self, api_key: ApiKey) -> ApiKey:
        """Create a new API key"""
        api_key_dict = api_key.model_dump(by_alias=True, exclude={"id"})
        result = await self.collection.insert_one(api_key_dict)
        api_key.id = result.inserted_id
        return api_key

    async def get_by_api_key(self, api_key: str) -> Optional[ApiKey]:
        """Get API key by key string"""
        doc = await self.collection.find_one({"api_key": api_key})
        return ApiKey(**doc) if doc else None

    async def get_by_user_id(self, user_id: str) -> List[ApiKey]:
        """Get all API keys for a user"""
        cursor = self.collection.find({"user_id": user_id})
        keys = []
        async for doc in cursor:
            keys.append(ApiKey(**doc))
        return keys

    async def update_api_key(self, api_key: str, updates: Dict[str, Any]) -> Optional[ApiKey]:
        """Update API key fields"""
        updates["updated_at"] = datetime.utcnow()
        result = await self.collection.find_one_and_update(
            {"api_key": api_key},
            {"$set": updates},
            return_document=True
        )
        return ApiKey(**result) if result else None

    async def deactivate_key(self, api_key: str) -> bool:
        """Deactivate an API key"""
        result = await self.collection.update_one(
            {"api_key": api_key},
            {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0


class ModelCostRepository(BaseRepository):
    """Repository for Model Cost operations"""

    def __init__(self):
        super().__init__("modelcosts")

    async def create_or_update_cost(self, model_cost: ModelCost) -> ModelCost:
        """Create or update model cost configuration"""
        model_cost_dict = model_cost.model_dump(by_alias=True, exclude={"id"})
        result = await self.collection.find_one_and_update(
            {"model_name": model_cost.model_name},
            {"$set": model_cost_dict},
            upsert=True,
            return_document=True
        )
        return ModelCost(**result)

    async def get_by_model_name(self, model_name: str) -> Optional[ModelCost]:
        """Get model cost by model name"""
        doc = await self.collection.find_one({"model_name": model_name})
        return ModelCost(**doc) if doc else None

    async def list_all_costs(self) -> List[ModelCost]:
        """Get all model costs"""
        cursor = self.collection.find()
        costs = []
        async for doc in cursor:
            costs.append(ModelCost(**doc))
        return costs

    async def delete_cost(self, model_name: str) -> bool:
        """Delete a model cost configuration"""
        result = await self.collection.delete_one({"model_name": model_name})
        return result.deleted_count > 0


class UsageLogRepository(BaseRepository):
    """Repository for Usage Log operations"""

    def __init__(self):
        super().__init__("usagelogs")

    async def create_log(self, usage_log: UsageLog) -> UsageLog:
        """Create a new usage log entry"""
        log_dict = usage_log.model_dump(by_alias=True, exclude={"id"})
        result = await self.collection.insert_one(log_dict)
        usage_log.id = result.inserted_id
        return usage_log

    async def get_user_logs(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[UsageLog]:
        """Get usage logs for a user with optional date filtering"""
        query = {"user_id": user_id}

        if start_date or end_date:
            date_query = {}
            if start_date:
                date_query["$gte"] = start_date
            if end_date:
                date_query["$lte"] = end_date
            query["timestamp"] = date_query

        cursor = self.collection.find(query).sort("timestamp", -1).skip(skip).limit(limit)
        logs = []
        async for doc in cursor:
            logs.append(UsageLog(**doc))
        return logs

    async def get_usage_summary(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get usage summary for a user"""
        match_stage = {"user_id": user_id}

        if start_date or end_date:
            date_query = {}
            if start_date:
                date_query["$gte"] = start_date
            if end_date:
                date_query["$lte"] = end_date
            match_stage["timestamp"] = date_query

        pipeline = [
            {"$match": match_stage},
            {
                "$group": {
                    "_id": None,
                    "total_requests": {"$sum": 1},
                    "total_cost": {"$sum": "$cost_usd"},
                    "total_tokens": {"$sum": "$total_tokens"},
                    "total_input_tokens": {"$sum": "$input_tokens"},
                    "total_output_tokens": {"$sum": "$output_tokens"},
                    "total_cached_tokens": {"$sum": "$cached_tokens"}
                }
            }
        ]

        result = await self.collection.aggregate(pipeline).to_list(1)
        if result:
            summary = result[0]
            del summary["_id"]
            return summary

        return {
            "total_requests": 0,
            "total_cost": 0.0,
            "total_tokens": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cached_tokens": 0
        }