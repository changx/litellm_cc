"""
Main API routes for LLM proxy endpoints
"""

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from gateway.auth.dependencies import get_authenticated_user, require_model_access
from gateway.models import Account, ApiKey
from gateway.proxy import ProxyRouter

logger = logging.getLogger(__name__)

# Create the API router
api_router = APIRouter(prefix="/v1", tags=["llm-proxy"])

# Initialize proxy router
proxy_router = ProxyRouter()


@api_router.post("/chat/completions")
async def chat_completions(
    request: Request,
    auth_data: tuple[ApiKey, Account] = Depends(get_authenticated_user),
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
        endpoint="/v1/chat/completions",
    )

    logger.debug(f"#response_debug /chat/completions to_client: {response}")

    return response


@api_router.post("/messages")
async def anthropic_messages(
    request: Request,
    auth_data: tuple[ApiKey, Account] = Depends(get_authenticated_user),
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
        endpoint="/v1/messages",
    )

    logger.debug(f"#response_debug /messages to_client: {response}")

    return response


@api_router.post("/responses")
async def litellm_responses(
    request: Request,
    auth_data: tuple[ApiKey, Account] = Depends(get_authenticated_user),
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
        endpoint="/v1/responses",
    )

    logger.debug(f"#response_debug /responses to_client: {response}")

    return response


@api_router.get("/models")
async def list_models(
    auth_data: tuple[ApiKey, Account] = Depends(get_authenticated_user),
):
    """List available models (simplified implementation)"""
    api_key, account = auth_data

    # Return a basic model list
    # In a production system, you might want to query the actual upstream providers
    # or maintain a dynamic list based on configured model costs
    models = {
        "object": "list",
        "data": [
            {"id": "gpt-4", "object": "model", "owned_by": "openai"},
            {"id": "gpt-3.5-turbo", "object": "model", "owned_by": "openai"},
            {
                "id": "claude-3-opus-20240229",
                "object": "model",
                "owned_by": "anthropic",
            },
            {
                "id": "claude-3-sonnet-20240229",
                "object": "model",
                "owned_by": "anthropic",
            },
            {
                "id": "claude-3-haiku-20240307",
                "object": "model",
                "owned_by": "anthropic",
            },
        ],
    }

    # Filter by allowed models if API key has restrictions
    if api_key.allowed_models:
        models["data"] = [
            model for model in models["data"] if model["id"] in api_key.allowed_models
        ]

    return JSONResponse(content=models)


@api_router.post("/messages/count_tokens")
async def count_tokens(
    request: Request,
    auth_data: tuple[ApiKey, Account] = Depends(get_authenticated_user),
):
    """Count tokens for a messages request without creating a message"""
    api_key, account = auth_data

    # Get request body
    request_data = await request.json()

    # Extract model name from request
    model_name = request_data.get("model")
    if not model_name:
        return JSONResponse(
            status_code=400, content={"error": "Model name is required"}
        )

    # Check model access permissions
    require_model_access(api_key, model_name)

    # Route to count tokens
    response = await proxy_router.count_tokens(
        request_data=request_data,
        api_key=api_key,
        account=account,
    )

    return response


@api_router.get("/account")
async def get_account_info(
    auth_data: tuple[ApiKey, Account] = Depends(get_authenticated_user),
):
    """Get account information for the authenticated user"""
    api_key, account = auth_data

    return JSONResponse(
        content={
            "user_id": account.user_id,
            "account_name": account.account_name,
            "budget_usd": account.budget_usd,
            "spent_usd": account.spent_usd,
            "remaining_budget_usd": account.remaining_budget_usd,
            "budget_duration": account.budget_duration.value,
            "is_active": account.is_active,
            "is_over_budget": account.is_over_budget,
            "api_key_name": api_key.key_name,
            "allowed_models": api_key.allowed_models,
        }
    )
