from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId

from ..models import (
    Account,
    AccountCreate,
    AccountUpdate,
    ApiKey,
    ApiKeyCreate,
    ApiKeyUpdate,
    ModelCost,
    ModelCostCreate,
    ModelCostUpdate,
    UsageLog,
)
from .connection import db_manager


class AccountRepository:
    @staticmethod
    async def create(account_data: AccountCreate) -> Account:
        collection = db_manager.get_collection("accounts")
        account_dict = account_data.dict()
        account_dict["created_at"] = datetime.utcnow()
        account_dict["updated_at"] = datetime.utcnow()

        result = await collection.insert_one(account_dict)
        account_dict["_id"] = result.inserted_id
        return Account(**account_dict)

    @staticmethod
    async def get_by_user_id(user_id: str) -> Optional[Account]:
        collection = db_manager.get_collection("accounts")
        account_data = await collection.find_one({"user_id": user_id})
        return Account(**account_data) if account_data else None

    @staticmethod
    async def update(user_id: str, update_data: AccountUpdate) -> Optional[Account]:
        collection = db_manager.get_collection("accounts")
        update_dict = {k: v for k, v in update_data.dict(exclude_unset=True).items()}
        update_dict["updated_at"] = datetime.utcnow()

        result = await collection.find_one_and_update(
            {"user_id": user_id}, {"$set": update_dict}, return_document=True
        )
        return Account(**result) if result else None

    @staticmethod
    async def increment_spent(user_id: str, amount: float) -> bool:
        collection = db_manager.get_collection("accounts")
        result = await collection.update_one(
            {"user_id": user_id}, {"$inc": {"spent_usd": amount}}
        )
        return result.modified_count > 0


class ApiKeyRepository:
    @staticmethod
    async def create(apikey_data: ApiKeyCreate) -> ApiKey:
        collection = db_manager.get_collection("apikeys")
        apikey_dict = apikey_data.dict()
        apikey_dict["created_at"] = datetime.utcnow()
        apikey_dict["updated_at"] = datetime.utcnow()

        result = await collection.insert_one(apikey_dict)
        apikey_dict["_id"] = result.inserted_id
        return ApiKey(**apikey_dict)

    @staticmethod
    async def get_by_key(api_key: str) -> Optional[ApiKey]:
        collection = db_manager.get_collection("apikeys")
        apikey_data = await collection.find_one({"api_key": api_key})
        return ApiKey(**apikey_data) if apikey_data else None

    @staticmethod
    async def update(api_key: str, update_data: ApiKeyUpdate) -> Optional[ApiKey]:
        collection = db_manager.get_collection("apikeys")
        update_dict = {k: v for k, v in update_data.dict(exclude_unset=True).items()}
        update_dict["updated_at"] = datetime.utcnow()

        result = await collection.find_one_and_update(
            {"api_key": api_key}, {"$set": update_dict}, return_document=True
        )
        return ApiKey(**result) if result else None

    @staticmethod
    async def get_by_user_id(user_id: str) -> List[ApiKey]:
        collection = db_manager.get_collection("apikeys")
        cursor = collection.find({"user_id": user_id})
        apikeys = []
        async for doc in cursor:
            apikeys.append(ApiKey(**doc))
        return apikeys


class ModelCostRepository:
    @staticmethod
    async def create_or_update(cost_data: ModelCostCreate) -> ModelCost:
        collection = db_manager.get_collection("modelcosts")
        cost_dict = cost_data.dict()
        cost_dict["updated_at"] = datetime.utcnow()

        result = await collection.find_one_and_update(
            {"model_name": cost_data.model_name},
            {"$set": cost_dict},
            upsert=True,
            return_document=True,
        )
        return ModelCost(**result)

    @staticmethod
    async def get_by_model_name(model_name: str) -> Optional[ModelCost]:
        collection = db_manager.get_collection("modelcosts")
        cost_data = await collection.find_one({"model_name": model_name})
        return ModelCost(**cost_data) if cost_data else None

    @staticmethod
    async def get_all() -> List[ModelCost]:
        collection = db_manager.get_collection("modelcosts")
        cursor = collection.find()
        costs = []
        async for doc in cursor:
            costs.append(ModelCost(**doc))
        return costs


class UsageLogRepository:
    @staticmethod
    async def create(log_data: Dict[str, Any]) -> UsageLog:
        collection = db_manager.get_collection("usagelogs")
        log_data["timestamp"] = datetime.utcnow()

        result = await collection.insert_one(log_data)
        log_data["_id"] = result.inserted_id
        return UsageLog(**log_data)

    @staticmethod
    async def get_by_user_id(
        user_id: str, limit: int = 100, skip: int = 0
    ) -> List[UsageLog]:
        collection = db_manager.get_collection("usagelogs")
        cursor = (
            collection.find({"user_id": user_id})
            .sort("timestamp", -1)
            .skip(skip)
            .limit(limit)
        )
        logs = []
        async for doc in cursor:
            logs.append(UsageLog(**doc))
        return logs

    @staticmethod
    async def get_by_api_key(
        api_key: str, limit: int = 100, skip: int = 0
    ) -> List[UsageLog]:
        collection = db_manager.get_collection("usagelogs")
        cursor = (
            collection.find({"api_key": api_key})
            .sort("timestamp", -1)
            .skip(skip)
            .limit(limit)
        )
        logs = []
        async for doc in cursor:
            logs.append(UsageLog(**doc))
        return logs
