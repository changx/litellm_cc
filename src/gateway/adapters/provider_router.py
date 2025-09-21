from typing import Optional, Dict, Any
from .base import BaseLLMAdapter, LLMRequest, LLMResponse
from .openai_adapter import OpenAIAdapter
from .anthropic_adapter import AnthropicAdapter
from .google_adapter import GoogleAdapter
from .cohere_adapter import CohereAdapter
from ..utils.config import settings


class ProviderRouter:
    """Router to select the appropriate LLM adapter based on model name"""
    
    @staticmethod
    def get_provider_for_model(model_name: str) -> str:
        """Determine provider based on model name"""
        model_lower = model_name.lower()
        
        if any(prefix in model_lower for prefix in ["gpt-", "text-", "davinci", "curie", "babbage", "ada"]):
            return "openai"
        elif any(prefix in model_lower for prefix in ["claude-", "anthropic"]):
            return "anthropic"
        elif any(prefix in model_lower for prefix in ["gemini", "palm", "vertex"]):
            return "google"
        elif any(prefix in model_lower for prefix in ["command", "cohere"]):
            return "cohere"
        elif model_lower.startswith("azure/"):
            return "azure"
        else:
            # Try custom provider if configured
            if settings.custom_llm_provider and model_lower.startswith(settings.custom_llm_provider.lower()):
                return settings.custom_llm_provider
            # Default to OpenAI for unknown models
            return "openai"
    
    @staticmethod
    def get_adapter(model_name: str) -> Optional[BaseLLMAdapter]:
        """Get the appropriate adapter for a model"""
        provider = ProviderRouter.get_provider_for_model(model_name)
        
        if provider == "openai":
            if not settings.openai_api_key:
                raise ValueError("OpenAI API key not configured")
            return OpenAIAdapter(
                api_key=settings.openai_api_key,
                api_base=settings.openai_api_base
            )
        
        elif provider == "anthropic":
            if not settings.anthropic_api_key:
                raise ValueError("Anthropic API key not configured")
            return AnthropicAdapter(
                api_key=settings.anthropic_api_key,
                api_base=settings.anthropic_api_base
            )
        
        elif provider == "google":
            if not settings.google_api_key:
                raise ValueError("Google API key not configured")
            return GoogleAdapter(
                api_key=settings.google_api_key,
                api_base=settings.google_api_base
            )
        
        elif provider == "cohere":
            if not settings.cohere_api_key:
                raise ValueError("Cohere API key not configured")
            return CohereAdapter(
                api_key=settings.cohere_api_key,
                api_base=settings.cohere_api_base
            )
        
        elif provider == "azure":
            if not settings.azure_api_key:
                raise ValueError("Azure API key not configured")
            return OpenAIAdapter(  # Azure uses OpenAI-compatible format
                api_key=settings.azure_api_key,
                api_base=settings.azure_api_base
            )
        
        elif provider == settings.custom_llm_provider:
            if not settings.custom_api_key:
                raise ValueError(f"Custom provider {provider} API key not configured")
            return OpenAIAdapter(  # Assume custom provider uses OpenAI format
                api_key=settings.custom_api_key,
                api_base=settings.custom_api_base
            )
        
        raise ValueError(f"Unsupported provider: {provider}")
    
    @staticmethod
    async def chat_completion(request: LLMRequest, endpoint_type: str = "chat") -> LLMResponse:
        """Make a chat completion request using the appropriate adapter"""
        async with ProviderRouter.get_adapter(request.model) as adapter:
            return await adapter.chat_completion(request, endpoint_type)