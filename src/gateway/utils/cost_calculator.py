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
        is_cache_hit: bool = False
    ) -> float:
        model_cost = await CostCalculator.get_model_cost(model_name)
        if not model_cost:
            return 0.0
            
        # Calculate cost based on token usage
        input_cost = (input_tokens / 1_000_000) * model_cost.input_cost_per_million_tokens_usd
        
        if is_cache_hit:
            # Use cached read cost for cached responses
            output_cost = (output_tokens / 1_000_000) * model_cost.cached_read_cost_per_million_tokens_usd
        else:
            output_cost = (output_tokens / 1_000_000) * model_cost.output_cost_per_million_tokens_usd
            
        return input_cost + output_cost