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


def _validate_openai_request(
    request_data: Dict[str, Any], endpoint_type: str = "chat"
) -> None:
    """Validate OpenAI API request"""
    if not request_data.get("model"):
        raise HTTPException(status_code=400, detail="model is required")

    if endpoint_type == "responses":
        # Responses API validation
        if not request_data.get("input"):
            raise HTTPException(
                status_code=400, detail="input is required for Responses API"
            )
    else:
        # Chat Completions API validation
        if not request_data.get("messages"):
            raise HTTPException(status_code=400, detail="messages is required")

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
                raise HTTPException(
                    status_code=400, detail=f"Message {i} must have a role"
                )

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


@router.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    request_data: Dict[str, Any],
    auth_data: Tuple[ApiKey, Account] = Depends(get_current_user),
):
    # Validate request format
    _validate_openai_request(request_data, "chat")

    apikey_obj, account = auth_data
    model_name = request_data.get("model", "")

    # Check model permission
    if apikey_obj.allowed_models and model_name not in apikey_obj.allowed_models:
        raise HTTPException(
            status_code=403, detail=f"Model '{model_name}' not allowed for this API key"
        )

    try:
        # Convert request to unified format
        messages = [
            LLMMessage(role=msg["role"], content=msg["content"])
            for msg in request_data.get("messages", [])
        ]

        llm_request = LLMRequest(
            model=model_name,
            messages=messages,
            max_tokens=request_data.get("max_tokens"),
            temperature=request_data.get("temperature"),
            top_p=request_data.get("top_p"),
            stop=request_data.get("stop"),
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

        # Convert to OpenAI format
        openai_response = {
            "id": response.id,
            "object": "chat.completion",
            "created": int(__import__("time").time()),
            "model": response.model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": response.content},
                    "finish_reason": response.finish_reason,
                }
            ],
            "usage": {
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": total_tokens,
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
                request_endpoint="/v1/chat/completions",
                ip_address=request.client.host if request.client else None,
                request_payload=request_data,
                response_payload=openai_response,
                cache_write_tokens=cache_write_tokens,
                cache_read_tokens=cache_read_tokens,
            )
        )

        return openai_response

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
                request_endpoint="/v1/chat/completions",
                ip_address=request.client.host if request.client else None,
                request_payload=request_data,
                response_payload={"error": str(e)},
            )
        )
        raise


@router.post("/v1/responses")
async def responses(
    request: Request,
    request_data: Dict[str, Any],
    auth_data: Tuple[ApiKey, Account] = Depends(get_current_user),
):
    # Validate request format for Responses API
    _validate_openai_request(request_data, "responses")

    apikey_obj, account = auth_data
    model_name = request_data.get("model", "")

    # Check model permission
    if apikey_obj.allowed_models and model_name not in apikey_obj.allowed_models:
        raise HTTPException(
            status_code=403, detail=f"Model '{model_name}' not allowed for this API key"
        )

    try:
        # Convert Responses API format to unified format
        # Create messages from input and instructions
        messages = []

        # Add instructions as system message if present
        if "instructions" in request_data:
            messages.append(
                LLMMessage(role="system", content=request_data["instructions"])
            )

        # Add input as user message
        if "input" in request_data:
            messages.append(LLMMessage(role="user", content=request_data["input"]))

        llm_request = LLMRequest(
            model=model_name,
            messages=messages,
            max_tokens=request_data.get("max_tokens"),
            temperature=request_data.get("temperature"),
            top_p=request_data.get("top_p"),
            stop=request_data.get("stop"),
            stream=request_data.get("stream", False),
        )

        # Call LiteLLM forwarder with responses endpoint
        forwarder = LiteLLMForwarder()
        response = await forwarder.chat_completion(
            llm_request, endpoint_type="responses"
        )

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

        # Convert to OpenAI Responses API format
        openai_response = {
            "id": response.id,
            "object": "response",
            "created_at": float(__import__("time").time()),
            "model": response.model,
            "error": None,
            "incomplete_details": None,
            "instructions": request_data.get("instructions"),
            "metadata": {},
            "output": [
                {
                    "id": f"msg_{response.id}",
                    "content": [
                        {
                            "annotations": [],
                            "text": response.content,
                            "type": "output_text",
                        }
                    ],
                    "role": "assistant",
                    "status": None,
                    "type": "message",
                }
            ],
            "output_text": response.content,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
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
                request_endpoint="/v1/responses",
                ip_address=request.client.host if request.client else None,
                request_payload=request_data,
                response_payload=openai_response,
                cache_write_tokens=cache_write_tokens,
                cache_read_tokens=cache_read_tokens,
            )
        )

        return openai_response

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
                request_endpoint="/v1/responses",
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
