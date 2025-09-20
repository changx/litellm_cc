from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from .base import MongoBaseModel


class ApiKey(MongoBaseModel):
    api_key: str = Field(..., unique=True, index=True)
    user_id: str = Field(..., index=True)
    key_name: str
    is_active: bool = True
    allowed_models: Optional[List[str]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ApiKeyCreate(BaseModel):
    api_key: str
    user_id: str
    key_name: str
    is_active: bool = True
    allowed_models: Optional[List[str]] = None


class ApiKeyUpdate(BaseModel):
    key_name: Optional[str] = None
    is_active: Optional[bool] = None
    allowed_models: Optional[List[str]] = None