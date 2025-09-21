from typing import Optional
from ..models import ModelCost
from ..database.operations import ModelCostRepository
from ..cache.manager import cache_manager


class CostCalculator:
    @staticmethod
    async def get_model_cost(model_name: str) -> Optional[ModelCost]:
        # Check cache first
        cached_cost = cache_manager.get_model_cost(model_name)
        if cached_cost:
            return cached_cost
            
        # Query database
        model_cost = await ModelCostRepository.get_by_model_name(model_name)
        if model_cost:
            cache_manager.set_model_cost(model_name, model_cost)
            
        return model_cost
    
    @staticmethod
    async def calculate_cost(
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        cache_write_tokens: int = 0,
        cache_read_tokens: int = 0,
        is_cache_hit: bool = False
    ) -> float:
        model_cost = await CostCalculator.get_model_cost(model_name)
        if not model_cost:
            return 0.0
            
        # Calculate cost based on token usage
        input_cost = (input_tokens / 1_000_000) * model_cost.input_cost_per_million_tokens_usd
        output_cost = (output_tokens / 1_000_000) * model_cost.output_cost_per_million_tokens_usd
        
        # Calculate cache costs
        cache_write_cost = (cache_write_tokens / 1_000_000) * model_cost.cache_write_cost_per_million_tokens_usd
        cache_read_cost = (cache_read_tokens / 1_000_000) * model_cost.cache_read_cost_per_million_tokens_usd
        
        # For backward compatibility: if is_cache_hit is True and cache_read_tokens is 0,
        # treat output tokens as cache read tokens
        if is_cache_hit and cache_read_tokens == 0:
            cache_read_cost = (output_tokens / 1_000_000) * model_cost.cache_read_cost_per_million_tokens_usd
            output_cost = 0.0  # Don't double-count output tokens as both output and cache read
            
        return input_cost + output_cost + cache_write_cost + cache_read_cost