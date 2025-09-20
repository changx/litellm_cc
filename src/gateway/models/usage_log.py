from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import Field
from .base import MongoBaseModel


class UsageLog(MongoBaseModel):
    user_id: str = Field(..., index=True)
    api_key: str = Field(..., index=True)
    model_name: str
    is_cache_hit: bool
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    request_endpoint: str
    ip_address: Optional[str] = None
    request_payload: Dict[str, Any]
    response_payload: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)