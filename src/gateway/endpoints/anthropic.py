import asyncio
from typing import Any, Dict, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request

from ..adapters.base import LLMMessage, LLMRequest
from ..adapters.litellm_forwarder import LiteLLMForwarder
from ..auth.dependencies import get_current_user
from ..database.operations import AccountRepository, UsageLogRepository
from ..models import Account, ApiKey
from ..utils.cost_calculator import CostCalculator

router = APIRouter()


def _extract_text_content(content):
    """Extract text content from Anthropic message content"""
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        text_content = ""
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text_content += block.get("text", "")
            # Note: Image content types are preserved in the original format
            # and passed through to the adapter
        return text_content
    return ""


def _validate_anthropic_request(request_data: Dict[str, Any]) -> None:
    """Validate Anthropic Messages API request"""
    if not request_data.get("model"):
        raise HTTPException(status_code=400, detail="model is required")

    if not request_data.get("messages"):
        raise HTTPException(status_code=400, detail="messages is required")

    if not request_data.get("max_tokens"):
        raise HTTPException(status_code=400, detail="max_tokens is required")

    messages = request_data.get("messages", [])
    if not isinstance(messages, list) or len(messages) == 0:
        raise HTTPException(
            status_code=400, detail="messages must be a non-empty array"
        )

    for i, msg in enumerate(messages):
        if not isinstance(msg, dict):
            raise HTTPException(
                status_code=400, detail=f"Message {i} must be an object"
            )

        if "role" not in msg:
            raise HTTPException(status_code=400, detail=f"Message {i} must have a role")

        if "content" not in msg:
            raise HTTPException(
                status_code=400, detail=f"Message {i} must have content"
            )

        role = msg["role"]
        if role not in ["user", "assistant", "system"]:
            raise HTTPException(
                status_code=400,
                detail=f"Message {i} role must be 'user', 'assistant', or 'system'",
            )


@router.post("/v1/messages")
async def messages(
    request: Request,
    request_data: Dict[str, Any],
    auth_data: Tuple[ApiKey, Account] = Depends(get_current_user),
):
    # Validate request format
    _validate_anthropic_request(request_data)

    apikey_obj, account = auth_data
    model_name = request_data.get("model", "")

    # Check model permission
    if apikey_obj.allowed_models and model_name not in apikey_obj.allowed_models:
        raise HTTPException(
            status_code=403, detail=f"Model '{model_name}' not allowed for this API key"
        )

    try:
        # Convert request to unified format - include system messages
        # The adapter will handle system message separation
        messages = [
            LLMMessage(role=msg["role"], content=_extract_text_content(msg["content"]))
            for msg in request_data.get("messages", [])
        ]

        # Add system message from top-level system parameter if present
        if "system" in request_data:
            system_msg = LLMMessage(role="system", content=request_data["system"])
            messages.insert(0, system_msg)

        llm_request = LLMRequest(
            model=model_name,
            messages=messages,
            max_tokens=request_data.get("max_tokens"),
            temperature=request_data.get("temperature"),
            top_p=request_data.get("top_p"),
            stop=request_data.get("stop_sequences"),
            stream=request_data.get("stream", False),
        )

        # Call LiteLLM forwarder
        forwarder = LiteLLMForwarder()
        response = await forwarder.chat_completion(llm_request)

        # Extract usage information
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        total_tokens = response.usage.total_tokens
        cache_write_tokens = response.usage.cache_write_tokens
        cache_read_tokens = response.usage.cache_read_tokens

        # Determine if this is a cache hit
        is_cache_hit = cache_read_tokens > 0

        # Calculate cost with enhanced cache token support
        cost_usd = await CostCalculator.calculate_cost(
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_write_tokens=cache_write_tokens,
            cache_read_tokens=cache_read_tokens,
            is_cache_hit=is_cache_hit,
        )

        # Update account spending atomically
        await AccountRepository.increment_spent(account.user_id, cost_usd)

        # Convert to Anthropic format
        anthropic_response = {
            "id": response.id,
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": response.content}],
            "model": response.model,
            "stop_reason": response.finish_reason,
            "stop_sequence": None,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_creation_input_tokens": cache_write_tokens,
                "cache_read_input_tokens": cache_read_tokens,
            },
        }

        # Log usage asynchronously
        asyncio.create_task(
            _log_usage(
                user_id=account.user_id,
                api_key=apikey_obj.api_key,
                model_name=model_name,
                is_cache_hit=is_cache_hit,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cost_usd=cost_usd,
                request_endpoint="/v1/messages",
                ip_address=request.client.host if request.client else None,
                request_payload=request_data,
                response_payload=anthropic_response,
                cache_write_tokens=cache_write_tokens,
                cache_read_tokens=cache_read_tokens,
            )
        )

        return anthropic_response

    except Exception as e:
        # Log error and re-raise
        asyncio.create_task(
            _log_usage(
                user_id=account.user_id,
                api_key=apikey_obj.api_key,
                model_name=model_name,
                is_cache_hit=False,
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                cost_usd=0.0,
                request_endpoint="/v1/messages",
                ip_address=request.client.host if request.client else None,
                request_payload=request_data,
                response_payload={"error": str(e)},
            )
        )
        raise


async def _log_usage(
    user_id: str,
    api_key: str,
    model_name: str,
    is_cache_hit: bool,
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
    cost_usd: float,
    request_endpoint: str,
    ip_address: str,
    request_payload: Dict[str, Any],
    response_payload: Dict[str, Any],
    cache_write_tokens: int = 0,
    cache_read_tokens: int = 0,
):
    try:
        await UsageLogRepository.create(
            {
                "user_id": user_id,
                "api_key": api_key,
                "model_name": model_name,
                "is_cache_hit": is_cache_hit,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_write_tokens": cache_write_tokens,
                "cache_read_tokens": cache_read_tokens,
                "total_tokens": total_tokens,
                "cost_usd": cost_usd,
                "request_endpoint": request_endpoint,
                "ip_address": ip_address,
                "request_payload": request_payload,
                "response_payload": response_payload,
            }
        )
    except Exception as e:
        # Don't fail the request if logging fails
        print(f"Failed to log usage: {e}")
