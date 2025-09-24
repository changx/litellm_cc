"""
LiteLLM client wrapper for provider routing
"""
import os
import logging
from typing import Dict, Any, AsyncGenerator, Union, Optional
from enum import Enum
import litellm
from litellm import ModelResponse, CustomStreamWrapper

logger = logging.getLogger(__name__)

# Configure LiteLLM
litellm.success_callback = []
litellm.failure_callback = []
litellm.set_verbose = False


class Provider(str, Enum):
    """Supported LLM providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class LiteLLMClient:
    """Wrapper for LiteLLM with provider routing"""

    def __init__(self):
        self.provider_configs = {
            Provider.OPENAI: {
                "api_key": os.getenv("OPENAI_API_KEY"),
                "api_base": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            },
            Provider.ANTHROPIC: {
                "api_key": os.getenv("ANTHROPIC_API_KEY"),
                "api_base": os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
            }
        }

    def get_provider_from_endpoint(self, endpoint: str) -> Provider:
        """Determine provider based on endpoint path"""
        endpoint_lower = endpoint.lower()

        if "/chat/completions" in endpoint_lower or "/responses" in endpoint_lower:
            return Provider.OPENAI
        elif "/messages" in endpoint_lower:
            return Provider.ANTHROPIC
        else:
            # Default to OpenAI for unknown endpoints
            logger.warning(f"Unknown endpoint {endpoint}, defaulting to OpenAI")
            return Provider.OPENAI

    def _get_provider_config(self, provider: Provider) -> Dict[str, str]:
        """Get configuration for the specified provider"""
        config = self.provider_configs.get(provider)
        if not config:
            raise ValueError(f"Provider {provider} not configured")

        if not config["api_key"]:
            raise ValueError(f"API key not configured for provider {provider}")

        return config

    async def completion(
        self,
        provider: Provider,
        request_data: Dict[str, Any],
        stream: bool = False
    ) -> Union[ModelResponse, AsyncGenerator[str, None]]:
        """
        Execute completion request via LiteLLM
        """
        config = self._get_provider_config(provider)

        # Prepare arguments for litellm.acompletion
        litellm_args = {
            **request_data,  # Pass through all client request data
            "api_key": config["api_key"],
            "stream": stream
        }

        # Add base URL if configured
        if config["api_base"]:
            litellm_args["api_base"] = config["api_base"]

        try:
            logger.debug(
                f"Calling LiteLLM with provider {provider}, "
                f"model: {request_data.get('model')}, stream: {stream}"
            )

            response = await litellm.acompletion(**litellm_args)

            if stream:
                # Return the async generator directly
                return response
            else:
                # Return the ModelResponse object
                return response

        except Exception as e:
            logger.error(f"LiteLLM error with provider {provider}: {str(e)}")
            raise

    def extract_usage_from_response(self, response: ModelResponse) -> Dict[str, Any]:
        """Extract usage information from LiteLLM response"""
        usage_data = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "is_cache_hit": False
        }

        if hasattr(response, 'usage') and response.usage:
            usage_data.update({
                "input_tokens": getattr(response.usage, 'prompt_tokens', 0),
                "output_tokens": getattr(response.usage, 'completion_tokens', 0),
                "total_tokens": getattr(response.usage, 'total_tokens', 0)
            })

        # Check for cache hit (LiteLLM specific)
        if hasattr(response, '_cache_hit'):
            usage_data["is_cache_hit"] = response._cache_hit

        return usage_data

    def extract_usage_from_stream(self, stream_wrapper: CustomStreamWrapper) -> Dict[str, Any]:
        """Extract usage information from completed stream"""
        usage_data = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "is_cache_hit": False
        }

        # For streaming responses, usage info is available after the stream completes
        if hasattr(stream_wrapper, 'usage') and stream_wrapper.usage:
            usage_data.update({
                "input_tokens": getattr(stream_wrapper.usage, 'prompt_tokens', 0),
                "output_tokens": getattr(stream_wrapper.usage, 'completion_tokens', 0),
                "total_tokens": getattr(stream_wrapper.usage, 'total_tokens', 0)
            })

        if hasattr(stream_wrapper, '_cache_hit'):
            usage_data["is_cache_hit"] = stream_wrapper._cache_hit

        return usage_data