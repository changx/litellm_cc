"""
Main API routes for LLM proxy endpoints
"""
import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from gateway.models import Account, ApiKey
from gateway.auth.dependencies import get_authenticated_user
from gateway.proxy import ProxyRouter

logger = logging.getLogger(__name__)

# Create the API router
api_router = APIRouter(prefix="/v1", tags=["llm-proxy"])

# Initialize proxy router
proxy_router = ProxyRouter()


@api_router.post("/chat/completions")
async def chat_completions(
    request: Request,
    auth_data: tuple[ApiKey, Account] = Depends(get_authenticated_user)
):
    """OpenAI Chat Completions API endpoint"""
    api_key, account = auth_data

    # Get request body
    request_data = await request.json()

    # Route through proxy
    response = await proxy_router.route_request(
        request=request,
        api_key=api_key,
        account=account,
        request_data=request_data,
        endpoint="/v1/chat/completions"
    )

    return response


@api_router.post("/messages")
async def anthropic_messages(
    request: Request,
    auth_data: tuple[ApiKey, Account] = Depends(get_authenticated_user)
):
    """Anthropic Messages API endpoint"""
    api_key, account = auth_data

    # Get request body
    request_data = await request.json()

    # Route through proxy
    response = await proxy_router.route_request(
        request=request,
        api_key=api_key,
        account=account,
        request_data=request_data,
        endpoint="/v1/messages"
    )

    return response


@api_router.post("/responses")
async def litellm_responses(
    request: Request,
    auth_data: tuple[ApiKey, Account] = Depends(get_authenticated_user)
):
    """LiteLLM Responses API endpoint (routes to OpenAI)"""
    api_key, account = auth_data

    # Get request body
    request_data = await request.json()

    # Route through proxy
    response = await proxy_router.route_request(
        request=request,
        api_key=api_key,
        account=account,
        request_data=request_data,
        endpoint="/v1/responses"
    )

    return response


@api_router.get("/models")
async def list_models(
    auth_data: tuple[ApiKey, Account] = Depends(get_authenticated_user)
):
    """List available models (simplified implementation)"""
    api_key, account = auth_data

    # Return a basic model list
    # In a production system, you might want to query the actual upstream providers
    # or maintain a dynamic list based on configured model costs
    models = {
        "object": "list",
        "data": [
            {
                "id": "gpt-4",
                "object": "model",
                "owned_by": "openai"
            },
            {
                "id": "gpt-3.5-turbo",
                "object": "model",
                "owned_by": "openai"
            },
            {
                "id": "claude-3-opus-20240229",
                "object": "model",
                "owned_by": "anthropic"
            },
            {
                "id": "claude-3-sonnet-20240229",
                "object": "model",
                "owned_by": "anthropic"
            },
            {
                "id": "claude-3-haiku-20240307",
                "object": "model",
                "owned_by": "anthropic"
            }
        ]
    }

    # Filter by allowed models if API key has restrictions
    if api_key.allowed_models:
        models["data"] = [
            model for model in models["data"]
            if model["id"] in api_key.allowed_models
        ]

    return JSONResponse(content=models)


@api_router.get("/account")
async def get_account_info(
    auth_data: tuple[ApiKey, Account] = Depends(get_authenticated_user)
):
    """Get account information for the authenticated user"""
    api_key, account = auth_data

    return JSONResponse(content={
        "user_id": account.user_id,
        "account_name": account.account_name,
        "budget_usd": account.budget_usd,
        "spent_usd": account.spent_usd,
        "remaining_budget_usd": account.remaining_budget_usd,
        "budget_duration": account.budget_duration.value,
        "is_active": account.is_active,
        "is_over_budget": account.is_over_budget,
        "api_key_name": api_key.key_name,
        "allowed_models": api_key.allowed_models
    })