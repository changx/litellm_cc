import asyncio
from typing import Any, Dict, Tuple
from fastapi import APIRouter, Depends, Request, HTTPException
import litellm
from ..auth.dependencies import get_current_user
from ..models import ApiKey, Account
from ..database.operations import AccountRepository, UsageLogRepository
from ..utils.cost_calculator import CostCalculator

router = APIRouter()


@router.post("/v1/responses")
async def responses(
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
        # Call LiteLLM directly - this endpoint preserves the native LiteLLM format
        response = await litellm.acompletion(**request_data)
        
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
        
        # Add billing information to response
        response["_billing"] = {
            "cost_usd": cost_usd,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "is_cache_hit": is_cache_hit,
            "user_id": account.user_id,
            "api_key_name": apikey_obj.key_name
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
                response_payload=response
            )
        )
        
        return response
        
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
                response_payload={"error": str(e)}
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