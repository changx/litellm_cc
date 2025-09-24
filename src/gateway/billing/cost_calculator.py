"""
Cost calculation logic
"""
import logging
from typing import Dict, Any, Optional
from gateway.models import ModelCost
from gateway.cache import get_cache_manager

logger = logging.getLogger(__name__)


class CostCalculator:
    """Calculate costs based on token usage and model pricing"""

    def __init__(self):
        self.cache_manager = get_cache_manager()

    async def calculate_cost(
        self,
        model_name: str,
        usage_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate cost based on model and usage data
        Returns dict with cost breakdown
        """
        # Get model cost configuration
        model_cost = await self.cache_manager.get_model_cost(model_name)

        if not model_cost:
            logger.warning(f"No cost configuration found for model: {model_name}")
            # Return default cost structure with zero cost
            return {
                "total_cost_usd": 0.0,
                "input_cost_usd": 0.0,
                "output_cost_usd": 0.0,
                "cached_cost_usd": 0.0,
                "model_found": False,
                "model_name": model_name
            }

        # Extract token counts from usage data
        input_tokens = usage_data.get("input_tokens", 0)
        output_tokens = usage_data.get("output_tokens", 0)
        cached_tokens = usage_data.get("cached_tokens", 0)
        is_cache_hit = usage_data.get("is_cache_hit", False)

        # Calculate individual costs
        input_cost = self._calculate_token_cost(
            input_tokens,
            model_cost.input_cost_per_million_tokens_usd
        )

        output_cost = self._calculate_token_cost(
            output_tokens,
            model_cost.output_cost_per_million_tokens_usd
        )

        cached_cost = 0.0
        if is_cache_hit or cached_tokens > 0:
            cached_cost = self._calculate_token_cost(
                cached_tokens,
                model_cost.cached_read_cost_per_million_tokens_usd
            )

        total_cost = input_cost + output_cost + cached_cost

        cost_breakdown = {
            "total_cost_usd": round(total_cost, 6),
            "input_cost_usd": round(input_cost, 6),
            "output_cost_usd": round(output_cost, 6),
            "cached_cost_usd": round(cached_cost, 6),
            "model_found": True,
            "model_name": model_name,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cached_tokens": cached_tokens,
            "is_cache_hit": is_cache_hit,
            "rate_input": model_cost.input_cost_per_million_tokens_usd,
            "rate_output": model_cost.output_cost_per_million_tokens_usd,
            "rate_cached": model_cost.cached_read_cost_per_million_tokens_usd
        }

        logger.debug(
            f"Cost calculated for {model_name}: "
            f"${total_cost:.6f} "
            f"(input: {input_tokens}, output: {output_tokens}, cached: {cached_tokens})"
        )

        return cost_breakdown

    def _calculate_token_cost(self, token_count: int, cost_per_million: float) -> float:
        """Calculate cost for a specific number of tokens"""
        if token_count <= 0:
            return 0.0
        return (token_count / 1_000_000) * cost_per_million

    async def estimate_cost(
        self,
        model_name: str,
        estimated_input_tokens: int,
        estimated_output_tokens: int = 0
    ) -> float:
        """
        Estimate cost for a request before processing
        Used for budget pre-checks
        """
        model_cost = await self.cache_manager.get_model_cost(model_name)

        if not model_cost:
            logger.warning(f"No cost configuration for model {model_name}, using zero cost")
            return 0.0

        input_cost = self._calculate_token_cost(
            estimated_input_tokens,
            model_cost.input_cost_per_million_tokens_usd
        )

        output_cost = self._calculate_token_cost(
            estimated_output_tokens,
            model_cost.output_cost_per_million_tokens_usd
        )

        return input_cost + output_cost

    def estimate_tokens_from_text(self, text: str) -> int:
        """
        Rough estimation of token count from text
        This is a simplified estimation - in production you might want to use
        a proper tokenizer
        """
        if not text:
            return 0

        # Simple word-based estimation (multiply by 1.3 to account for tokenization)
        words = len(text.split())
        return int(words * 1.3)

    async def estimate_request_cost(
        self,
        model_name: str,
        request_data: Dict[str, Any]
    ) -> float:
        """
        Estimate cost for a complete request
        """
        # Extract text from request to estimate input tokens
        input_text = ""

        if "messages" in request_data:
            # Chat completion format
            for message in request_data["messages"]:
                if isinstance(message, dict) and "content" in message:
                    content = message["content"]
                    if isinstance(content, str):
                        input_text += content + " "
                    elif isinstance(content, list):
                        # Handle multimodal content
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "text":
                                input_text += item.get("text", "") + " "

        elif "prompt" in request_data:
            # Completion format
            prompt = request_data["prompt"]
            if isinstance(prompt, str):
                input_text = prompt
            elif isinstance(prompt, list):
                input_text = " ".join(str(p) for p in prompt)

        # Estimate input tokens
        input_tokens = self.estimate_tokens_from_text(input_text)

        # Estimate output tokens based on max_tokens parameter
        max_tokens = request_data.get("max_tokens", 0)
        estimated_output_tokens = min(max_tokens, input_tokens) if max_tokens > 0 else int(input_tokens * 0.5)

        return await self.estimate_cost(model_name, input_tokens, estimated_output_tokens)