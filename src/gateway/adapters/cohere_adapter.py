from typing import Dict, Any
from .base import BaseLLMAdapter, LLMRequest, LLMResponse, LLMUsage


class CohereAdapter(BaseLLMAdapter):
    """Cohere API adapter"""
    
    def get_default_api_base(self) -> str:
        return "https://api.cohere.com"
    
    def get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def get_endpoint(self, model: str, endpoint_type: str = "chat") -> str:
        return "/v2/chat"
    
    def transform_request(self, request: LLMRequest) -> Dict[str, Any]:
        """Transform to Cohere format"""
        data = {
            "model": request.model,
            "messages": [
                {"role": msg.role, "content": msg.content}
                for msg in request.messages
            ],
            "stream": request.stream
        }
        
        if request.max_tokens is not None:
            data["max_tokens"] = request.max_tokens
        if request.temperature is not None:
            data["temperature"] = request.temperature
        if request.top_p is not None:
            data["p"] = request.top_p
        if request.stop:
            data["stop_sequences"] = request.stop
            
        return data
    
    def transform_response(self, response_data: Dict[str, Any]) -> LLMResponse:
        """Transform Cohere response to unified format"""
        message = response_data.get("message", {})
        content_blocks = message.get("content", [])
        
        content = ""
        for block in content_blocks:
            if block.get("type") == "text":
                content += block.get("text", "")
        
        usage_data = response_data.get("usage", {})
        billed_usage = usage_data.get("billed_usage", {})
        
        usage = LLMUsage(
            input_tokens=billed_usage.get("input_tokens", 0),
            output_tokens=billed_usage.get("output_tokens", 0),
            total_tokens=billed_usage.get("input_tokens", 0) + billed_usage.get("output_tokens", 0)
        )
        
        return LLMResponse(
            id=response_data.get("id", ""),
            model=response_data.get("model", ""),
            content=content,
            finish_reason=response_data.get("finish_reason", "COMPLETE"),
            usage=usage
        )