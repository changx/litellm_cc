import os

from gateway.models.usage_log import UsageData

from .base import BaseProvider


class AnthropicProvider(BaseProvider):
    def __init__(self):
        base_url = os.getenv("ANTHROPIC_BASE_URL")
        api_key = os.getenv("ANTHROPIC_API_KEY")
        super().__init__(base_url=base_url, api_key=api_key)

    def extract_usage_from_response(response: any) -> UsageData:
        usage = response.usage

        return UsageData(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cached_tokens=usage.cache_read_input_tokens or 0,
            cache_creation_tokens=usage.cache_creation_input_tokens or 0,
        )
