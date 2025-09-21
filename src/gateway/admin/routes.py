from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any
from ..auth.dependencies import authenticate_admin
from ..models import (
    Account, AccountCreate, AccountUpdate,
    ApiKey, ApiKeyCreate, ApiKeyUpdate,
    ModelCost, ModelCostCreate, ModelCostUpdate,
    UsageLog
)
from ..database.operations import (
    AccountRepository, 
    ApiKeyRepository,
    ModelCostRepository,
    UsageLogRepository
)
from ..cache.manager import cache_manager
from ..utils.provider_info import get_supported_providers

router = APIRouter(prefix="/admin", tags=["admin"])


# Account management
@router.post("/accounts", response_model=Account)
async def create_account(
    account_data: AccountCreate,
    _: str = Depends(authenticate_admin)
):
    try:
        account = await AccountRepository.create(account_data)
        return account
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create account: {str(e)}"
        )


@router.get("/accounts/{user_id}", response_model=Account)
async def get_account(
    user_id: str,
    _: str = Depends(authenticate_admin)
):
    account = await AccountRepository.get_by_user_id(user_id)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found"
        )
    return account


@router.patch("/accounts/{user_id}", response_model=Account)
async def update_account(
    user_id: str,
    update_data: AccountUpdate,
    _: str = Depends(authenticate_admin)
):
    account = await AccountRepository.update(user_id, update_data)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found"
        )
    
    # Invalidate cache
    await cache_manager.publish_cache_invalidation("account", user_id)
    
    return account


# API Key management
@router.post("/keys", response_model=ApiKey)
async def create_api_key(
    apikey_data: ApiKeyCreate,
    _: str = Depends(authenticate_admin)
):
    try:
        # Verify that the user_id exists
        account = await AccountRepository.get_by_user_id(apikey_data.user_id)
        if not account:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User ID does not exist"
            )
        
        apikey = await ApiKeyRepository.create(apikey_data)
        return apikey
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create API key: {str(e)}"
        )


@router.get("/keys/{api_key}", response_model=ApiKey)
async def get_api_key(
    api_key: str,
    _: str = Depends(authenticate_admin)
):
    apikey = await ApiKeyRepository.get_by_key(api_key)
    if not apikey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    return apikey


@router.get("/keys/user/{user_id}", response_model=List[ApiKey])
async def get_user_api_keys(
    user_id: str,
    _: str = Depends(authenticate_admin)
):
    apikeys = await ApiKeyRepository.get_by_user_id(user_id)
    return apikeys


@router.patch("/keys/{api_key}", response_model=ApiKey)
async def update_api_key(
    api_key: str,
    update_data: ApiKeyUpdate,
    _: str = Depends(authenticate_admin)
):
    apikey = await ApiKeyRepository.update(api_key, update_data)
    if not apikey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    # Invalidate cache
    await cache_manager.publish_cache_invalidation("apikey", api_key)
    
    return apikey


# Model cost management
@router.post("/costs", response_model=ModelCost)
async def create_or_update_model_cost(
    cost_data: ModelCostCreate,
    _: str = Depends(authenticate_admin)
):
    try:
        model_cost = await ModelCostRepository.create_or_update(cost_data)
        
        # Invalidate cache
        await cache_manager.publish_cache_invalidation("modelcost", cost_data.model_name)
        
        return model_cost
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create/update model cost: {str(e)}"
        )


@router.get("/costs", response_model=List[ModelCost])
async def get_all_model_costs(
    _: str = Depends(authenticate_admin)
):
    costs = await ModelCostRepository.get_all()
    return costs


@router.get("/costs/{model_name}", response_model=ModelCost)
async def get_model_cost(
    model_name: str,
    _: str = Depends(authenticate_admin)
):
    cost = await ModelCostRepository.get_by_model_name(model_name)
    if not cost:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model cost not found"
        )
    return cost


# Usage logs
@router.get("/usage/user/{user_id}", response_model=List[UsageLog])
async def get_user_usage_logs(
    user_id: str,
    limit: int = 100,
    skip: int = 0,
    _: str = Depends(authenticate_admin)
):
    logs = await UsageLogRepository.get_by_user_id(user_id, limit, skip)
    return logs


@router.get("/usage/key/{api_key}", response_model=List[UsageLog])
async def get_api_key_usage_logs(
    api_key: str,
    limit: int = 100,
    skip: int = 0,
    _: str = Depends(authenticate_admin)
):
    logs = await UsageLogRepository.get_by_api_key(api_key, limit, skip)
    return logs


# Provider configuration
@router.get("/providers")
async def get_provider_configuration(
    _: str = Depends(authenticate_admin)
) -> Dict[str, Any]:
    """
    Get information about configured LLM providers and their custom endpoints.
    """
    providers = get_supported_providers()
    
    return {
        "providers": providers,
        "total_configured": len(providers),
        "configuration_notes": {
            "custom_endpoints": "Custom API base URLs are configured for providers that have api_base set",
            "supported_formats": ["OpenAI Chat Completions", "Anthropic Messages", "LiteLLM Responses"],
            "authentication": "All providers require valid API keys"
        }
    }