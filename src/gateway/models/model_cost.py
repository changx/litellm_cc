"""
Model cost configuration
"""

from datetime import datetime

from pydantic import Field

from .base import MongoBaseModel


class ModelCost(MongoBaseModel):
    """Model cost configuration for billing calculations"""

    model_name: str = Field(..., unique=True, description="Model name identifier")
    provider: str = Field(..., description="Provider name (openai, anthropic, etc.)")
    input_cost_per_million_tokens_usd: float = Field(
        ..., ge=0, description="Cost per million input tokens in USD"
    )
    output_cost_per_million_tokens_usd: float = Field(
        ..., ge=0, description="Cost per million output tokens in USD"
    )
    cache_hit_cost_per_million_tokens_usd: float = Field(
        0.0, ge=0, description="Cost per million cache hit tokens in USD"
    )
    cache_write_cost_per_million_tokens_usd: float = Field(
        0.0, ge=0, description="Cost per million cache write tokens in USD"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Last update timestamp"
    )

    def calculate_cost(
        self, input_tokens: int, output_tokens: int, cached_tokens: int = 0
    ) -> float:
        """Calculate total cost based on token usage

        Note: Currently only supports cached read tokens pricing.
        To use cached write tokens pricing, the usage tracking system
        needs to be updated to differentiate between read and write cached tokens.
        """
        input_cost = (input_tokens / 1_000_000) * self.input_cost_per_million_tokens_usd
        output_cost = (
            output_tokens / 1_000_000
        ) * self.output_cost_per_million_tokens_usd
        cached_cost = (
            cached_tokens / 1_000_000
        ) * self.cache_hit_cost_per_million_tokens_usd
        return input_cost + output_cost + cached_cost
