from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from .base import MongoBaseModel


class ModelCost(MongoBaseModel):
    model_name: str = Field(..., unique=True)
    provider: str
    input_cost_per_million_tokens_usd: float
    output_cost_per_million_tokens_usd: float
    cache_write_cost_per_million_tokens_usd: float
    cache_read_cost_per_million_tokens_usd: float
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ModelCostCreate(BaseModel):
    model_name: str
    provider: str
    input_cost_per_million_tokens_usd: float
    output_cost_per_million_tokens_usd: float
    cache_write_cost_per_million_tokens_usd: float
    cache_read_cost_per_million_tokens_usd: float


class ModelCostUpdate(BaseModel):
    provider: Optional[str] = None
    input_cost_per_million_tokens_usd: Optional[float] = None
    output_cost_per_million_tokens_usd: Optional[float] = None
    cache_write_cost_per_million_tokens_usd: Optional[float] = None
    cache_read_cost_per_million_tokens_usd: Optional[float] = None