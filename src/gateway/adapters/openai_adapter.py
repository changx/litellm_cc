from typing import Any, Dict

from .base import BaseLLMAdapter, LLMRequest, LLMResponse, LLMUsage


class OpenAIAdapter(BaseLLMAdapter):
    """OpenAI API adapter"""

    def get_default_api_base(self) -> str:
        return "https://api.openai.com"

    def get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def get_endpoint(self, model: str, endpoint_type: str = "chat") -> str:
        if endpoint_type == "responses":
            return "/v1/responses"
        return "/v1/chat/completions"

    def transform_request(self, request: LLMRequest) -> Dict[str, Any]:
        """Transform to OpenAI format"""
        # Check if this is for responses endpoint by checking if messages contain instructions format
        # For responses API, we need to extract the user message as input

        data = {
            "model": request.model,
            "messages": [
                {"role": msg.role, "content": msg.content} for msg in request.messages
            ],
            "stream": request.stream,
        }

        if request.max_tokens is not None:
            data["max_tokens"] = request.max_tokens
        if request.temperature is not None:
            data["temperature"] = request.temperature
        if request.top_p is not None:
            data["top_p"] = request.top_p
        if request.stop:
            data["stop"] = request.stop

        return data

    def transform_request_responses(self, request: LLMRequest) -> Dict[str, Any]:
        """Transform to OpenAI Responses API format"""
        # Extract the last user message as input for Responses API
        user_input = ""
        instructions = ""

        for msg in request.messages:
            if msg.role == "system":
                instructions = msg.content
            elif msg.role == "user":
                user_input = msg.content

        data = {"model": request.model, "input": user_input}

        if instructions:
            data["instructions"] = instructions

        if request.stream:
            data["stream"] = request.stream

        return data

    def transform_response(self, response_data: Dict[str, Any]) -> LLMResponse:
        """Transform OpenAI response to unified format"""
        # Check if this is a Responses API response
        if response_data.get("object") == "response":
            return self.transform_response_responses(response_data)

        # Standard Chat Completions response
        choice = response_data["choices"][0]
        message = choice["message"]
        usage_data = response_data.get("usage", {})

        # OpenAI cache tokens (if available in future versions)
        cache_write_tokens = usage_data.get("cache_write_tokens", 0)
        cache_read_tokens = usage_data.get("cache_read_tokens", 0)

        usage = LLMUsage(
            input_tokens=usage_data.get("prompt_tokens", 0),
            output_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
            cache_write_tokens=cache_write_tokens,
            cache_read_tokens=cache_read_tokens,
        )

        return LLMResponse(
            id=response_data["id"],
            model=response_data["model"],
            content=message["content"],
            finish_reason=choice["finish_reason"],
            usage=usage,
        )

    def transform_response_responses(
        self, response_data: Dict[str, Any]
    ) -> LLMResponse:
        """Transform OpenAI Responses API response to unified format"""
        output_items = response_data.get("output", [])
        content = ""

        # Extract text content from output items
        for item in output_items:
            if item.get("type") == "message" and item.get("role") == "assistant":
                content_blocks = item.get("content", [])
                for block in content_blocks:
                    if block.get("type") == "output_text":
                        content += block.get("text", "")

        # Responses API usage format may be different - adapt as needed
        usage_data = response_data.get("usage", {})

        usage = LLMUsage(
            input_tokens=usage_data.get("input_tokens", 0),
            output_tokens=usage_data.get("output_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
            cache_write_tokens=usage_data.get("cache_write_tokens", 0),
            cache_read_tokens=usage_data.get("cache_read_tokens", 0),
        )

        return LLMResponse(
            id=response_data.get("id", ""),
            model=response_data.get("model", ""),
            content=content,
            finish_reason="stop",  # Responses API may not have finish_reason
            usage=usage,
        )
