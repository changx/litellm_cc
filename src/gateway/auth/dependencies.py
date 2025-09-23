from typing import Tuple

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..cache.manager import cache_manager
from ..database.operations import AccountRepository, ApiKeyRepository
from ..models import Account, ApiKey

security = HTTPBearer()


class AuthenticationError(HTTPException):
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


class AuthorizationError(HTTPException):
    def __init__(self, detail: str = "Authorization failed"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class BudgetExceededError(HTTPException):
    def __init__(self, detail: str = "Budget exceeded"):
        super().__init__(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail)


async def get_api_key_from_header(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> str:
    if not credentials or not credentials.credentials:
        raise AuthenticationError("Missing API key")
    return credentials.credentials


async def authenticate_and_authorize(
    api_key: str = Depends(get_api_key_from_header),
) -> Tuple[ApiKey, Account]:
    # Check L1 cache first
    cached_apikey = cache_manager.get_apikey(api_key)
    if cached_apikey:
        if not cached_apikey.is_active:
            raise AuthorizationError("API key is disabled")

        # Get account from cache
        cached_account = cache_manager.get_account(cached_apikey.user_id)
        if cached_account:
            if not cached_account.is_active:
                raise AuthorizationError("Account is disabled")

            # Check budget
            if cached_account.spent_usd >= cached_account.budget_usd:
                raise BudgetExceededError("Account budget exceeded")

            return cached_apikey, cached_account

    # Cache miss - query database
    apikey_obj = await ApiKeyRepository.get_by_key(api_key)
    if not apikey_obj:
        raise AuthenticationError("Invalid API key")

    if not apikey_obj.is_active:
        raise AuthorizationError("API key is disabled")

    # Cache the API key
    cache_manager.set_apikey(api_key, apikey_obj)

    # Get account
    account = await AccountRepository.get_by_user_id(apikey_obj.user_id)
    if not account:
        raise AuthorizationError("Account not found")

    if not account.is_active:
        raise AuthorizationError("Account is disabled")

    # Check budget
    if account.spent_usd >= account.budget_usd:
        raise BudgetExceededError("Account budget exceeded")

    # Cache the account
    cache_manager.set_account(apikey_obj.user_id, account)

    return apikey_obj, account


async def get_current_user(
    auth_data: Tuple[ApiKey, Account] = Depends(authenticate_and_authorize),
) -> Tuple[ApiKey, Account]:
    return auth_data


async def check_model_permission(
    model_name: str, auth_data: Tuple[ApiKey, Account] = Depends(get_current_user)
) -> Tuple[ApiKey, Account]:
    apikey_obj, account = auth_data

    # Check if model is allowed for this API key
    if apikey_obj.allowed_models and model_name not in apikey_obj.allowed_models:
        raise AuthorizationError(f"Model '{model_name}' not allowed for this API key")

    return apikey_obj, account


# Admin authentication
async def authenticate_admin(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> str:
    if not credentials or not credentials.credentials:
        raise AuthenticationError("Missing admin API key")

    # This should be set via environment variable
    from ..utils.config import settings

    if credentials.credentials != settings.admin_api_key:
        raise AuthenticationError("Invalid admin API key")

    return credentials.credentials
