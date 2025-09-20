from typing import Dict, Any
from .base import BaseLLMAdapter, LLMRequest, LLMResponse, LLMUsage


class OpenAIAdapter(BaseLLMAdapter):
    """OpenAI API adapter"""
    
    def get_default_api_base(self) -> str:
        return "https://api.openai.com"
    
    def get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def get_endpoint(self, model: str, endpoint_type: str = "chat") -> str:
        if endpoint_type == "responses":
            return "/v1/responses"
        return "/v1/chat/completions"
    
    def transform_request(self, request: LLMRequest) -> Dict[str, Any]:
        """Transform to OpenAI format (already standard)"""
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
            data["top_p"] = request.top_p
        if request.stop:
            data["stop"] = request.stop
            
        return data
    
    def transform_response(self, response_data: Dict[str, Any]) -> LLMResponse:
        """Transform OpenAI response to unified format"""
        choice = response_data["choices"][0]
        message = choice["message"]
        usage_data = response_data.get("usage", {})
        
        usage = LLMUsage(
            input_tokens=usage_data.get("prompt_tokens", 0),
            output_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0)
        )
        
        return LLMResponse(
            id=response_data["id"],
            model=response_data["model"],
            content=message["content"],
            finish_reason=choice["finish_reason"],
            usage=usage
        )