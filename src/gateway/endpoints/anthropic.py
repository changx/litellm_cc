import asyncio
from typing import Any, Dict, Tuple
from fastapi import APIRouter, Depends, Request, HTTPException
import litellm
from ..auth.dependencies import get_current_user
from ..models import ApiKey, Account
from ..database.operations import AccountRepository, UsageLogRepository
from ..utils.cost_calculator import CostCalculator

router = APIRouter()


@router.post("/v1/messages")
async def messages(
    request: Request,
    request_data: Dict[str, Any],
    auth_data: Tuple[ApiKey, Account] = Depends(get_current_user)
):
    apikey_obj, account = auth_data
    model_name = request_data.get("model", "")
    
    # Check model permission
    if apikey_obj.allowed_models and model_name not in apikey_obj.allowed_models:
        raise HTTPException(
            status_code=403,
            detail=f"Model '{model_name}' not allowed for this API key"
        )
    
    try:
        # Convert Anthropic format to LiteLLM compatible format
        litellm_request = _convert_anthropic_to_litellm(request_data)
        
        # Call LiteLLM
        response = await litellm.acompletion(**litellm_request)
        
        # Convert LiteLLM response back to Anthropic format
        anthropic_response = _convert_litellm_to_anthropic(response)
        
        # Extract usage information
        usage = response.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", input_tokens + output_tokens)
        
        # Check for cache hit
        is_cache_hit = getattr(response, "_cache_hit", False)
        
        # Calculate cost
        cost_usd = await CostCalculator.calculate_cost(
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            is_cache_hit=is_cache_hit
        )
        
        # Update account spending atomically
        await AccountRepository.increment_spent(account.user_id, cost_usd)
        
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
                response_payload=anthropic_response
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
                response_payload={"error": str(e)}
            )
        )
        raise


def _convert_anthropic_to_litellm(anthropic_request: Dict[str, Any]) -> Dict[str, Any]:
    """Convert Anthropic messages format to LiteLLM chat completions format"""
    messages = []
    
    # Convert Anthropic messages to OpenAI format
    for message in anthropic_request.get("messages", []):
        role = message.get("role")
        content = message.get("content", "")
        
        # Handle content that might be a list of content blocks
        if isinstance(content, list):
            # For now, just join text content blocks
            text_content = ""
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_content += block.get("text", "")
            content = text_content
            
        messages.append({"role": role, "content": content})
    
    litellm_request = {
        "model": anthropic_request.get("model"),
        "messages": messages,
    }
    
    # Copy other parameters if they exist
    if "max_tokens" in anthropic_request:
        litellm_request["max_tokens"] = anthropic_request["max_tokens"]
    if "temperature" in anthropic_request:
        litellm_request["temperature"] = anthropic_request["temperature"]
    if "top_p" in anthropic_request:
        litellm_request["top_p"] = anthropic_request["top_p"]
    if "stop_sequences" in anthropic_request:
        litellm_request["stop"] = anthropic_request["stop_sequences"]
        
    return litellm_request


def _convert_litellm_to_anthropic(litellm_response: Dict[str, Any]) -> Dict[str, Any]:
    """Convert LiteLLM response to Anthropic messages format"""
    choices = litellm_response.get("choices", [])
    if not choices:
        return {"content": [], "role": "assistant"}
        
    choice = choices[0]
    message = choice.get("message", {})
    content = message.get("content", "")
    
    # Convert to Anthropic format
    anthropic_response = {
        "id": litellm_response.get("id", ""),
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": content}],
        "model": litellm_response.get("model", ""),
        "stop_reason": "end_turn",  # This might need to be mapped from choice.finish_reason
        "stop_sequence": None,
        "usage": {
            "input_tokens": litellm_response.get("usage", {}).get("prompt_tokens", 0),
            "output_tokens": litellm_response.get("usage", {}).get("completion_tokens", 0)
        }
    }
    
    return anthropic_response


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
    response_payload: Dict[str, Any]
):
    try:
        await UsageLogRepository.create({
            "user_id": user_id,
            "api_key": api_key,
            "model_name": model_name,
            "is_cache_hit": is_cache_hit,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "cost_usd": cost_usd,
            "request_endpoint": request_endpoint,
            "ip_address": ip_address,
            "request_payload": request_payload,
            "response_payload": response_payload
        })
    except Exception as e:
        # Don't fail the request if logging fails
        print(f"Failed to log usage: {e}")