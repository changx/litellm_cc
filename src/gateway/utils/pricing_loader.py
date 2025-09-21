import json
import os
from typing import Dict, Any
from ..models import ModelCostCreate
from ..database.operations import ModelCostRepository


class PricingLoader:
    @staticmethod
    def load_pricing_config(config_path: str = None) -> Dict[str, Any]:
        """Load pricing configuration from JSON file."""
        if config_path is None:
            # Default path relative to this file
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "config",
                "pricing.json"
            )
        
        with open(config_path, 'r') as f:
            return json.load(f)
    
    @staticmethod
    async def initialize_pricing_database(config_path: str = None) -> None:
        """Initialize database with pricing data from JSON configuration."""
        pricing_config = PricingLoader.load_pricing_config(config_path)
        
        for provider_name, provider_data in pricing_config["providers"].items():
            for model_name, pricing_data in provider_data["models"].items():
                model_cost_data = ModelCostCreate(
                    model_name=model_name,
                    provider=provider_name,
                    input_cost_per_million_tokens_usd=pricing_data["input_cost_per_million_tokens_usd"],
                    output_cost_per_million_tokens_usd=pricing_data["output_cost_per_million_tokens_usd"],
                    cache_write_cost_per_million_tokens_usd=pricing_data["cache_write_cost_per_million_tokens_usd"],
                    cache_read_cost_per_million_tokens_usd=pricing_data["cache_read_cost_per_million_tokens_usd"]
                )
                
                await ModelCostRepository.create_or_update(model_cost_data)
    
    @staticmethod
    def get_model_pricing(model_name: str, provider: str = None, config_path: str = None) -> Dict[str, float]:
        """Get pricing data for a specific model from the JSON configuration."""
        pricing_config = PricingLoader.load_pricing_config(config_path)
        
        # If provider is specified, look in that provider only
        if provider:
            provider_data = pricing_config["providers"].get(provider)
            if provider_data and model_name in provider_data["models"]:
                return provider_data["models"][model_name]
        
        # Otherwise, search all providers
        for provider_name, provider_data in pricing_config["providers"].items():
            if model_name in provider_data["models"]:
                return provider_data["models"][model_name]
        
        return {}
    
    @staticmethod
    def list_supported_models(config_path: str = None) -> Dict[str, list]:
        """List all supported models grouped by provider."""
        pricing_config = PricingLoader.load_pricing_config(config_path)
        
        result = {}
        for provider_name, provider_data in pricing_config["providers"].items():
            result[provider_name] = list(provider_data["models"].keys())
        
        return result