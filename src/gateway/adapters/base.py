from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel


class LLMMessage(BaseModel):
    role: str
    content: str


class LLMRequest(BaseModel):
    model: str
    messages: List[LLMMessage]
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    stop: Optional[List[str]] = None
    stream: bool = False


class LLMUsage(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0


class LLMResponse(BaseModel):
    id: str
    model: str
    content: str
    finish_reason: str
    usage: LLMUsage


class BaseLLMAdapter(ABC):
    """Base class for all LLM provider adapters"""

    def __init__(self, api_key: str, api_base: Optional[str] = None):
        self.api_key = api_key
        self.api_base = api_base
        self.client = httpx.AsyncClient(timeout=60.0)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    @abstractmethod
    def get_default_api_base(self) -> str:
        """Get the default API base URL for this provider"""
        pass

    @abstractmethod
    def get_headers(self) -> Dict[str, str]:
        """Get the headers required for API requests"""
        pass

    @abstractmethod
    def transform_request(self, request: LLMRequest) -> Dict[str, Any]:
        """Transform unified request to provider-specific format"""
        pass

    @abstractmethod
    def transform_response(self, response_data: Dict[str, Any]) -> LLMResponse:
        """Transform provider-specific response to unified format"""
        pass

    @abstractmethod
    def get_endpoint(self, model: str, endpoint_type: str = "chat") -> str:
        """Get the API endpoint for the given model and endpoint type"""
        pass

    def get_api_base(self) -> str:
        """Get the API base URL (custom or default)"""
        return self.api_base or self.get_default_api_base()

    async def chat_completion(
        self, request: LLMRequest, endpoint_type: str = "chat"
    ) -> LLMResponse:
        """Make a chat completion request"""
        url = f"{self.get_api_base()}{self.get_endpoint(request.model, endpoint_type)}"
        headers = self.get_headers()

        # Use specific transform method for responses endpoint
        if endpoint_type == "responses" and hasattr(
            self, "transform_request_responses"
        ):
            data = self.transform_request_responses(request)
        else:
            data = self.transform_request(request)

        response = await self.client.post(url, headers=headers, json=data)
        response.raise_for_status()

        response_data = response.json()
        return self.transform_response(response_data)
