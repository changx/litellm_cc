"""
Usage log model for audit trails
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import Field

from .base import MongoBaseModel


class UsageLog(MongoBaseModel):
    """Usage log for detailed audit tracking"""

    user_id: str = Field(..., index=True, description="User ID who made the request")
    api_key: str = Field(..., index=True, description="API key used for the request")
    model_name: str = Field(..., description="Model name used")
    is_cache_hit: bool = Field(False, description="Whether response was cached")
    input_tokens: int = Field(0, ge=0, description="Number of input tokens")
    output_tokens: int = Field(0, ge=0, description="Number of output tokens")
    cached_tokens: int = Field(0, ge=0, description="Number of cached tokens")
    cache_creation_tokens: int = Field(
        0, ge=0, description="Number of cache creation tokens"
    )
    total_tokens: int = Field(0, ge=0, description="Total tokens used")
    cost_usd: float = Field(0.0, ge=0, description="Cost in USD")
    request_endpoint: str = Field(..., description="API endpoint called")
    ip_address: Optional[str] = Field(None, description="Client IP address")
    request_payload: Dict[str, Any] = Field({}, description="Request payload")
    response_payload: Dict[str, Any] = Field({}, description="Response payload")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, index=True, description="Request timestamp"
    )
    processing_time_ms: Optional[float] = Field(
        None, description="Processing time in milliseconds"
    )
    error_message: Optional[str] = Field(None, description="Error message if any")

    def set_token_counts(
        self,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int = 0,
        cache_creation_tokens: int = 0,
    ):
        """Set token counts and calculate total"""
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cached_tokens = cached_tokens
        self.cache_creation_tokens = cache_creation_tokens
        self.total_tokens = input_tokens + output_tokens
