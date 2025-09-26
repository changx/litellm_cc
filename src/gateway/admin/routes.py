"""
Admin API routes for managing accounts, API keys, and model costs
"""

import secrets
import string
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from gateway.auth.dependencies import get_admin_auth
from gateway.billing import BillingManager
from gateway.cache import get_cache_manager
from gateway.database.repositories import (
    AccountRepository,
    ApiKeyRepository,
    ModelCostRepository,
    UsageLogRepository,
)
from gateway.models import Account, ApiKey, ModelCost

from .schemas import (
    AccountCreateRequest,
    AccountResponse,
    AccountUpdateRequest,
    ApiKeyCreateRequest,
    ApiKeyResponse,
    ApiKeyUpdateRequest,
    BulkApiKeyCreateRequest,
    ModelCostCreateRequest,
    ModelCostResponse,
    UsageSummaryResponse,
)

# Create the admin router
admin_router = APIRouter(prefix="/admin", tags=["admin"])

# Initialize repositories
account_repo = AccountRepository()
apikey_repo = ApiKeyRepository()
modelcost_repo = ModelCostRepository()
usage_repo = UsageLogRepository()
billing_manager = BillingManager()


def generate_api_key() -> str:
    """Generate a secure random API key"""
    alphabet = string.ascii_letters + string.digits
    key = "".join(secrets.choice(alphabet) for _ in range(48))
    return f"llm-{key}"


# Account Management Routes
@admin_router.post("/accounts", response_model=AccountResponse)
async def create_account(
    request: AccountCreateRequest, _: bool = Depends(get_admin_auth)
):
    """Create a new account"""
    try:
        # Check if user_id already exists
        existing = await account_repo.get_by_user_id(request.user_id)
        if existing:
            raise HTTPException(status_code=400, detail="User ID already exists")

        # Create account
        account = Account(
            user_id=request.user_id,
            account_name=request.account_name,
            budget_usd=request.budget_usd,
            budget_duration=request.budget_duration,
            is_active=request.is_active,
        )

        created_account = await account_repo.create_account(account)

        return AccountResponse(
            user_id=created_account.user_id,
            account_name=created_account.account_name,
            budget_usd=created_account.budget_usd,
            spent_usd=created_account.spent_usd,
            remaining_budget_usd=created_account.remaining_budget_usd,
            budget_duration=created_account.budget_duration,
            is_active=created_account.is_active,
            is_over_budget=created_account.is_over_budget,
            created_at=created_account.created_at,
            updated_at=created_account.updated_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to create account: {str(e)}"
        )


@admin_router.patch("/accounts/{user_id}", response_model=AccountResponse)
async def update_account(
    user_id: str, request: AccountUpdateRequest, _: bool = Depends(get_admin_auth)
):
    """Update an account"""
    try:
        # Prepare update data
        updates = {}
        if request.account_name is not None:
            updates["account_name"] = request.account_name
        if request.budget_usd is not None:
            updates["budget_usd"] = request.budget_usd
        if request.budget_duration is not None:
            updates["budget_duration"] = request.budget_duration.value
        if request.is_active is not None:
            updates["is_active"] = request.is_active

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        # Update account
        updated_account = await account_repo.update_account(user_id, updates)
        if not updated_account:
            raise HTTPException(status_code=404, detail="Account not found")

        # Invalidate cache
        cache_manager = get_cache_manager()
        await cache_manager.invalidate_account(user_id)

        return AccountResponse(
            user_id=updated_account.user_id,
            account_name=updated_account.account_name,
            budget_usd=updated_account.budget_usd,
            spent_usd=updated_account.spent_usd,
            remaining_budget_usd=updated_account.remaining_budget_usd,
            budget_duration=updated_account.budget_duration,
            is_active=updated_account.is_active,
            is_over_budget=updated_account.is_over_budget,
            created_at=updated_account.created_at,
            updated_at=updated_account.updated_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to update account: {str(e)}"
        )


@admin_router.get("/accounts/{user_id}", response_model=AccountResponse)
async def get_account(user_id: str, _: bool = Depends(get_admin_auth)):
    """Get account details"""
    account = await account_repo.get_by_user_id(user_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    return AccountResponse(
        user_id=account.user_id,
        account_name=account.account_name,
        budget_usd=account.budget_usd,
        spent_usd=account.spent_usd,
        remaining_budget_usd=account.remaining_budget_usd,
        budget_duration=account.budget_duration,
        is_active=account.is_active,
        is_over_budget=account.is_over_budget,
        created_at=account.created_at,
        updated_at=account.updated_at,
    )


@admin_router.get("/accounts", response_model=List[AccountResponse])
async def list_accounts(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    _: bool = Depends(get_admin_auth),
):
    """List all accounts with pagination"""
    accounts = await account_repo.list_accounts(skip=skip, limit=limit)

    return [
        AccountResponse(
            user_id=account.user_id,
            account_name=account.account_name,
            budget_usd=account.budget_usd,
            spent_usd=account.spent_usd,
            remaining_budget_usd=account.remaining_budget_usd,
            budget_duration=account.budget_duration,
            is_active=account.is_active,
            is_over_budget=account.is_over_budget,
            created_at=account.created_at,
            updated_at=account.updated_at,
        )
        for account in accounts
    ]


# API Key Management Routes
@admin_router.post("/keys", response_model=ApiKeyResponse)
async def create_api_key(
    request: ApiKeyCreateRequest, _: bool = Depends(get_admin_auth)
):
    """Create a new API key"""
    try:
        # Verify user exists
        account = await account_repo.get_by_user_id(request.user_id)
        if not account:
            raise HTTPException(status_code=404, detail="User not found")

        # Generate API key
        api_key_str = generate_api_key()

        # Create API key object
        api_key = ApiKey(
            api_key=api_key_str,
            user_id=request.user_id,
            key_name=request.key_name,
            is_active=request.is_active,
            allowed_models=request.allowed_models,
        )

        created_key = await apikey_repo.create_api_key(api_key)

        return ApiKeyResponse(
            api_key=created_key.api_key,
            user_id=created_key.user_id,
            key_name=created_key.key_name,
            is_active=created_key.is_active,
            allowed_models=created_key.allowed_models,
            created_at=created_key.created_at,
            updated_at=created_key.updated_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to create API key: {str(e)}"
        )


@admin_router.patch("/keys/{api_key}", response_model=ApiKeyResponse)
async def update_api_key(
    api_key: str, request: ApiKeyUpdateRequest, _: bool = Depends(get_admin_auth)
):
    """Update an API key"""
    try:
        # Prepare update data
        updates = {}
        if request.key_name is not None:
            updates["key_name"] = request.key_name
        if request.allowed_models is not None:
            updates["allowed_models"] = request.allowed_models
        if request.is_active is not None:
            updates["is_active"] = request.is_active

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        # Update API key
        updated_key = await apikey_repo.update_api_key(api_key, updates)
        if not updated_key:
            raise HTTPException(status_code=404, detail="API key not found")

        # Invalidate cache
        cache_manager = get_cache_manager()
        await cache_manager.invalidate_api_key(api_key)

        return ApiKeyResponse(
            api_key=updated_key.api_key,
            user_id=updated_key.user_id,
            key_name=updated_key.key_name,
            is_active=updated_key.is_active,
            allowed_models=updated_key.allowed_models,
            created_at=updated_key.created_at,
            updated_at=updated_key.updated_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to update API key: {str(e)}"
        )


@admin_router.get("/keys/{user_id}", response_model=List[ApiKeyResponse])
async def get_user_keys(user_id: str, _: bool = Depends(get_admin_auth)):
    """Get all API keys for a user"""
    keys = await apikey_repo.get_by_user_id(user_id)

    return [
        ApiKeyResponse(
            api_key=key.api_key,
            user_id=key.user_id,
            key_name=key.key_name,
            is_active=key.is_active,
            allowed_models=key.allowed_models,
            created_at=key.created_at,
            updated_at=key.updated_at,
        )
        for key in keys
    ]


@admin_router.post("/keys/bulk", response_model=List[ApiKeyResponse])
async def create_bulk_api_keys(
    request: BulkApiKeyCreateRequest, _: bool = Depends(get_admin_auth)
):
    """Create multiple API keys for a user"""
    try:
        # Verify user exists
        account = await account_repo.get_by_user_id(request.user_id)
        if not account:
            raise HTTPException(status_code=404, detail="User not found")

        created_keys = []

        for i in range(request.count):
            # Generate API key
            api_key_str = generate_api_key()

            # Create API key object
            api_key = ApiKey(
                api_key=api_key_str,
                user_id=request.user_id,
                key_name=f"{request.key_prefix}-{i + 1}",
                is_active=request.is_active,
                allowed_models=request.allowed_models,
            )

            created_key = await apikey_repo.create_api_key(api_key)
            created_keys.append(
                ApiKeyResponse(
                    api_key=created_key.api_key,
                    user_id=created_key.user_id,
                    key_name=created_key.key_name,
                    is_active=created_key.is_active,
                    allowed_models=created_key.allowed_models,
                    created_at=created_key.created_at,
                    updated_at=created_key.updated_at,
                )
            )

        return created_keys

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to create bulk API keys: {str(e)}"
        )


# Model Cost Management Routes
@admin_router.post("/costs", response_model=ModelCostResponse)
async def create_or_update_model_cost(
    request: ModelCostCreateRequest, _: bool = Depends(get_admin_auth)
):
    """Create or update model cost configuration"""
    try:
        model_cost = ModelCost(
            model_name=request.model_name,
            provider=request.provider,
            input_cost_per_million_tokens_usd=request.input_cost_per_million_tokens_usd,
            output_cost_per_million_tokens_usd=request.output_cost_per_million_tokens_usd,
            cached_read_cost_per_million_tokens_usd=request.cached_read_cost_per_million_tokens_usd,
            cached_write_cost_per_million_tokens_usd=request.cached_write_cost_per_million_tokens_usd,
        )

        updated_cost = await modelcost_repo.create_or_update_cost(model_cost)

        # Invalidate cache
        cache_manager = get_cache_manager()
        await cache_manager.invalidate_model_cost(request.model_name)

        return ModelCostResponse(
            model_name=updated_cost.model_name,
            provider=updated_cost.provider,
            input_cost_per_million_tokens_usd=updated_cost.input_cost_per_million_tokens_usd,
            output_cost_per_million_tokens_usd=updated_cost.output_cost_per_million_tokens_usd,
            cached_read_cost_per_million_tokens_usd=updated_cost.cached_read_cost_per_million_tokens_usd,
            cached_write_cost_per_million_tokens_usd=updated_cost.cached_write_cost_per_million_tokens_usd,
            updated_at=updated_cost.updated_at,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to create/update model cost: {str(e)}"
        )


@admin_router.get("/costs", response_model=List[ModelCostResponse])
async def list_model_costs(_: bool = Depends(get_admin_auth)):
    """List all model cost configurations"""
    costs = await modelcost_repo.list_all_costs()

    return [
        ModelCostResponse(
            model_name=cost.model_name,
            provider=cost.provider,
            input_cost_per_million_tokens_usd=cost.input_cost_per_million_tokens_usd,
            output_cost_per_million_tokens_usd=cost.output_cost_per_million_tokens_usd,
            cached_read_cost_per_million_tokens_usd=cost.cached_read_cost_per_million_tokens_usd,
            cached_write_cost_per_million_tokens_usd=cost.cached_write_cost_per_million_tokens_usd,
            updated_at=cost.updated_at,
        )
        for cost in costs
    ]


@admin_router.get("/costs/{model_name}", response_model=ModelCostResponse)
async def get_model_cost(model_name: str, _: bool = Depends(get_admin_auth)):
    """Get model cost configuration"""
    cost = await modelcost_repo.get_by_model_name(model_name)
    if not cost:
        raise HTTPException(status_code=404, detail="Model cost not found")

    return ModelCostResponse(
        model_name=cost.model_name,
        provider=cost.provider,
        input_cost_per_million_tokens_usd=cost.input_cost_per_million_tokens_usd,
        output_cost_per_million_tokens_usd=cost.output_cost_per_million_tokens_usd,
        cached_read_cost_per_million_tokens_usd=cost.cached_read_cost_per_million_tokens_usd,
        cached_write_cost_per_million_tokens_usd=cost.cached_write_cost_per_million_tokens_usd,
        updated_at=cost.updated_at,
    )


@admin_router.delete("/costs/{model_name}")
async def delete_model_cost(model_name: str, _: bool = Depends(get_admin_auth)):
    """Delete model cost configuration"""
    success = await modelcost_repo.delete_cost(model_name)
    if not success:
        raise HTTPException(status_code=404, detail="Model cost not found")

    # Invalidate cache
    cache_manager = get_cache_manager()
    await cache_manager.invalidate_model_cost(model_name)

    return {"message": "Model cost deleted successfully"}


# Usage Analytics Routes
@admin_router.get("/usage/{user_id}", response_model=UsageSummaryResponse)
async def get_user_usage_summary(
    user_id: str,
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    _: bool = Depends(get_admin_auth),
):
    """Get usage summary for a user"""
    summary = await billing_manager.get_usage_summary(
        user_id=user_id, start_date=start_date, end_date=end_date
    )

    return UsageSummaryResponse(**summary)


# System Health Routes
@admin_router.get("/health")
async def admin_health_check(_: bool = Depends(get_admin_auth)):
    """Admin health check with system information"""
    cache_manager = get_cache_manager()
    cache_stats = cache_manager.get_cache_stats()

    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "cache_stats": cache_stats,
        "admin_access": True,
    }
