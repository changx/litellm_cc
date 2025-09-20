from typing import Dict, Any
from .base import BaseLLMAdapter, LLMRequest, LLMResponse, LLMUsage


class AnthropicAdapter(BaseLLMAdapter):
    """Anthropic Claude API adapter"""
    
    def get_default_api_base(self) -> str:
        return "https://api.anthropic.com"
    
    def get_headers(self) -> Dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
    
    def get_endpoint(self, model: str, endpoint_type: str = "chat") -> str:
        return "/v1/messages"
    
    def transform_request(self, request: LLMRequest) -> Dict[str, Any]:
        """Transform to Anthropic format"""
        data = {
            "model": request.model,
            "max_tokens": request.max_tokens or 4096,
            "messages": [
                {"role": msg.role, "content": msg.content}
                for msg in request.messages
            ]
        }
        
        if request.temperature is not None:
            data["temperature"] = request.temperature
        if request.top_p is not None:
            data["top_p"] = request.top_p
        if request.stop:
            data["stop_sequences"] = request.stop
            
        return data
    
    def transform_response(self, response_data: Dict[str, Any]) -> LLMResponse:
        """Transform Anthropic response to unified format"""
        content_blocks = response_data.get("content", [])
        content = ""
        if content_blocks and isinstance(content_blocks, list):
            for block in content_blocks:
                if block.get("type") == "text":
                    content += block.get("text", "")
        
        usage_data = response_data.get("usage", {})
        cache_write_tokens = usage_data.get("cache_creation_input_tokens", 0)
        cache_read_tokens = usage_data.get("cache_read_input_tokens", 0)
        
        usage = LLMUsage(
            input_tokens=usage_data.get("input_tokens", 0),
            output_tokens=usage_data.get("output_tokens", 0),
            total_tokens=usage_data.get("input_tokens", 0) + usage_data.get("output_tokens", 0),
            cache_write_tokens=cache_write_tokens,
            cache_read_tokens=cache_read_tokens
        )
        
        return LLMResponse(
            id=response_data.get("id", ""),
            model=response_data.get("model", ""),
            content=content,
            finish_reason=response_data.get("stop_reason", "end_turn"),
            usage=usage
        )