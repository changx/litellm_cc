from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from .base import MongoBaseModel
from .enums import BudgetDuration


class Account(MongoBaseModel):
    user_id: str = Field(..., index=True, unique=True)
    account_name: Optional[str] = None
    budget_usd: float = 0.0
    spent_usd: float = 0.0
    budget_duration: BudgetDuration = BudgetDuration.TOTAL
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AccountCreate(BaseModel):
    user_id: str
    account_name: Optional[str] = None
    budget_usd: float = 0.0
    budget_duration: BudgetDuration = BudgetDuration.TOTAL
    is_active: bool = True


class AccountUpdate(BaseModel):
    account_name: Optional[str] = None
    budget_usd: Optional[float] = None
    budget_duration: Optional[BudgetDuration] = None
    is_active: Optional[bool] = None