import os
from typing import Any, Dict, List, Optional

import litellm

from ..utils.config import settings
from .base import LLMMessage, LLMRequest, LLMResponse, LLMUsage


class LiteLLMForwarder:
    """LiteLLM-based provider forwarder for unified API requests"""

    def __init__(self):
        self._setup_api_keys()
        # Configure litellm settings
        litellm.drop_params = True  # Drop unsupported params instead of erroring
        litellm.set_verbose = False  # Disable verbose logging

    def _setup_api_keys(self):
        """Setup API keys for all configured providers"""
        if settings.openai_api_key:
            os.environ["OPENAI_API_KEY"] = settings.openai_api_key

        if settings.anthropic_api_key:
            os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key

        if settings.google_api_key:
            os.environ["GOOGLE_API_KEY"] = settings.google_api_key

        if settings.cohere_api_key:
            os.environ["COHERE_API_KEY"] = settings.cohere_api_key

        if settings.azure_api_key:
            os.environ["AZURE_API_KEY"] = settings.azure_api_key

        if settings.custom_api_key and settings.custom_llm_provider:
            # Set custom provider key with appropriate environment variable
            env_key = f"{settings.custom_llm_provider.upper()}_API_KEY"
            os.environ[env_key] = settings.custom_api_key

    def _get_litellm_model_name(self, model: str) -> str:
        """Convert model name to LiteLLM format if needed"""
        model_lower = model.lower()

        # Azure models need special formatting
        if model_lower.startswith("azure/"):
            return model

        # For custom providers, prefix with provider name
        if settings.custom_llm_provider and model_lower.startswith(
            settings.custom_llm_provider.lower()
        ):
            return model

        # For other providers, use model name as-is
        # LiteLLM automatically detects provider based on model name
        return model

    def _setup_custom_api_base(self, model: str) -> Dict[str, Any]:
        """Setup custom API base URLs if configured"""
        api_base_config = {}

        # Set custom API bases based on provider
        if model.startswith("gpt-") and settings.openai_api_base:
            api_base_config["api_base"] = settings.openai_api_base
        elif model.startswith("claude-") and settings.anthropic_api_base:
            api_base_config["api_base"] = settings.anthropic_api_base
        elif (
            any(model.startswith(prefix) for prefix in ["gemini", "text-", "chat-"])
            and settings.google_api_base
        ):
            api_base_config["api_base"] = settings.google_api_base
        elif model.startswith("command-") and settings.cohere_api_base:
            api_base_config["api_base"] = settings.cohere_api_base
        elif model.startswith("azure/") and settings.azure_api_base:
            api_base_config["api_base"] = settings.azure_api_base
        elif (
            settings.custom_llm_provider
            and model.startswith(settings.custom_llm_provider.lower())
            and settings.custom_api_base
        ):
            api_base_config["api_base"] = settings.custom_api_base

        return api_base_config

    async def chat_completion(
        self, request: LLMRequest, endpoint_type: str = "chat"
    ) -> LLMResponse:
        """Forward chat completion request using LiteLLM"""

        # Convert unified request to LiteLLM format
        litellm_model = self._get_litellm_model_name(request.model)

        # Prepare messages in OpenAI format
        messages = [
            {"role": msg.role, "content": msg.content} for msg in request.messages
        ]

        # Prepare request parameters
        completion_params = {
            "model": litellm_model,
            "messages": messages,
            "stream": request.stream,
        }

        # Add optional parameters if present
        if request.max_tokens is not None:
            completion_params["max_tokens"] = request.max_tokens

        if request.temperature is not None:
            completion_params["temperature"] = request.temperature

        if request.top_p is not None:
            completion_params["top_p"] = request.top_p

        if request.stop is not None:
            completion_params["stop"] = request.stop

        # Add custom API base if configured
        api_base_config = self._setup_custom_api_base(request.model)
        completion_params.update(api_base_config)

        try:
            # Make async request using litellm
            response = await litellm.acompletion(**completion_params)

            # Extract response data
            choice = response.choices[0]
            usage = response.usage

            # Handle cache tokens if present (mainly for Anthropic)
            cache_write_tokens = 0
            cache_read_tokens = 0

            # Check for cache-related usage info
            if hasattr(usage, "cache_creation_input_tokens"):
                cache_write_tokens = getattr(usage, "cache_creation_input_tokens", 0)
            if hasattr(usage, "cache_read_input_tokens"):
                cache_read_tokens = getattr(usage, "cache_read_input_tokens", 0)

            # Convert to unified response format
            llm_usage = LLMUsage(
                input_tokens=usage.prompt_tokens,
                output_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
                cache_write_tokens=cache_write_tokens,
                cache_read_tokens=cache_read_tokens,
            )

            llm_response = LLMResponse(
                id=response.id,
                model=response.model,
                content=choice.message.content,
                finish_reason=choice.finish_reason,
                usage=llm_usage,
            )

            return llm_response

        except Exception as e:
            # Re-raise with more context
            raise Exception(
                f"LiteLLM completion failed for model {request.model}: {str(e)}"
            )
