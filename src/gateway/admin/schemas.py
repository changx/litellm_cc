"""
Pydantic schemas for admin API requests and responses
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from gateway.models.base import BudgetDuration


class AccountCreateRequest(BaseModel):
    """Schema for creating a new account"""
    user_id: str = Field(..., description="Unique user identifier")
    account_name: Optional[str] = Field(None, description="Human-readable account name")
    budget_usd: float = Field(0.0, ge=0, description="Budget limit in USD")
    budget_duration: BudgetDuration = Field(
        BudgetDuration.TOTAL,
        description="Budget duration period"
    )
    is_active: bool = Field(True, description="Whether account is active")


class AccountUpdateRequest(BaseModel):
    """Schema for updating an account"""
    account_name: Optional[str] = Field(None, description="Human-readable account name")
    budget_usd: Optional[float] = Field(None, ge=0, description="Budget limit in USD")
    budget_duration: Optional[BudgetDuration] = Field(None, description="Budget duration period")
    is_active: Optional[bool] = Field(None, description="Whether account is active")


class AccountResponse(BaseModel):
    """Schema for account response"""
    user_id: str
    account_name: Optional[str]
    budget_usd: float
    spent_usd: float
    remaining_budget_usd: float
    budget_duration: BudgetDuration
    is_active: bool
    is_over_budget: bool
    created_at: datetime
    updated_at: datetime


class ApiKeyCreateRequest(BaseModel):
    """Schema for creating a new API key"""
    user_id: str = Field(..., description="Associated user ID")
    key_name: str = Field(..., description="Human-readable key name")
    allowed_models: Optional[List[str]] = Field(
        None,
        description="List of allowed models, None means all models allowed"
    )
    is_active: bool = Field(True, description="Whether key is active")


class ApiKeyUpdateRequest(BaseModel):
    """Schema for updating an API key"""
    key_name: Optional[str] = Field(None, description="Human-readable key name")
    allowed_models: Optional[List[str]] = Field(None, description="List of allowed models")
    is_active: Optional[bool] = Field(None, description="Whether key is active")


class ApiKeyResponse(BaseModel):
    """Schema for API key response"""
    api_key: str
    user_id: str
    key_name: str
    is_active: bool
    allowed_models: Optional[List[str]]
    created_at: datetime
    updated_at: datetime


class ModelCostCreateRequest(BaseModel):
    """Schema for creating or updating model cost"""
    model_name: str = Field(..., description="Model name identifier")
    provider: str = Field(..., description="Provider name (openai, anthropic, etc.)")
    input_cost_per_million_tokens_usd: float = Field(
        ...,
        ge=0,
        description="Cost per million input tokens in USD"
    )
    output_cost_per_million_tokens_usd: float = Field(
        ...,
        ge=0,
        description="Cost per million output tokens in USD"
    )
    cached_read_cost_per_million_tokens_usd: float = Field(
        0.0,
        ge=0,
        description="Cost per million cached tokens in USD"
    )


class ModelCostResponse(BaseModel):
    """Schema for model cost response"""
    model_name: str
    provider: str
    input_cost_per_million_tokens_usd: float
    output_cost_per_million_tokens_usd: float
    cached_read_cost_per_million_tokens_usd: float
    updated_at: datetime


class UsageSummaryResponse(BaseModel):
    """Schema for usage summary response"""
    total_requests: int
    total_cost: float
    total_tokens: int
    total_input_tokens: int
    total_output_tokens: int
    total_cached_tokens: int
    current_budget_usd: Optional[float] = None
    current_spent_usd: Optional[float] = None
    remaining_budget_usd: Optional[float] = None
    budget_exceeded: Optional[bool] = None


class BulkApiKeyCreateRequest(BaseModel):
    """Schema for creating multiple API keys"""
    user_id: str = Field(..., description="Associated user ID")
    count: int = Field(..., ge=1, le=100, description="Number of keys to create")
    key_prefix: str = Field("api-key", description="Prefix for generated key names")
    allowed_models: Optional[List[str]] = Field(None, description="List of allowed models")
    is_active: bool = Field(True, description="Whether keys are active")