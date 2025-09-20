from typing import Dict, Any, List
from .base import BaseLLMAdapter, LLMRequest, LLMResponse, LLMUsage


class GoogleAdapter(BaseLLMAdapter):
    """Google Gemini API adapter"""
    
    def get_default_api_base(self) -> str:
        return "https://generativelanguage.googleapis.com"
    
    def get_headers(self) -> Dict[str, str]:
        return {
            "x-goog-api-key": self.api_key,
            "Content-Type": "application/json"
        }
    
    def get_endpoint(self, model: str, endpoint_type: str = "chat") -> str:
        return f"/v1beta/models/{model}:generateContent"
    
    def transform_request(self, request: LLMRequest) -> Dict[str, Any]:
        """Transform to Google Gemini format"""
        contents = []
        for msg in request.messages:
            role = "user" if msg.role in ["user", "system"] else "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg.content}]
            })
        
        data = {"contents": contents}
        
        # Add generation config if parameters are provided
        generation_config = {}
        if request.max_tokens is not None:
            generation_config["maxOutputTokens"] = request.max_tokens
        if request.temperature is not None:
            generation_config["temperature"] = request.temperature
        if request.top_p is not None:
            generation_config["topP"] = request.top_p
        if request.stop:
            generation_config["stopSequences"] = request.stop
        
        if generation_config:
            data["generationConfig"] = generation_config
            
        return data
    
    def transform_response(self, response_data: Dict[str, Any]) -> LLMResponse:
        """Transform Google response to unified format"""
        candidates = response_data.get("candidates", [])
        if not candidates:
            raise ValueError("No candidates in Google API response")
        
        candidate = candidates[0]
        content_data = candidate.get("content", {})
        parts = content_data.get("parts", [])
        
        content = ""
        for part in parts:
            if "text" in part:
                content += part["text"]
        
        # Extract usage info
        usage_metadata = response_data.get("usageMetadata", {})
        usage = LLMUsage(
            input_tokens=usage_metadata.get("promptTokenCount", 0),
            output_tokens=usage_metadata.get("candidatesTokenCount", 0),
            total_tokens=usage_metadata.get("totalTokenCount", 0)
        )
        
        return LLMResponse(
            id=response_data.get("modelVersion", ""),
            model=response_data.get("modelVersion", ""),
            content=content,
            finish_reason=candidate.get("finishReason", "STOP"),
            usage=usage
        )