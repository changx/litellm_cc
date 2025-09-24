"""
FastAPI dependencies for authentication and authorization
"""
import logging
from typing import Tuple, Optional
from fastapi import Depends, HTTPException, Header, Request
from gateway.models import Account, ApiKey
from gateway.cache import get_cache_manager
from gateway.utils.config import settings
from .exceptions import AuthenticationError, AuthorizationError, BudgetExceededError

logger = logging.getLogger(__name__)


async def extract_api_key(authorization: Optional[str] = Header(None)) -> str:
    """Extract API key from Authorization header"""
    if not authorization:
        raise AuthenticationError("Missing Authorization header")

    if not authorization.startswith("Bearer "):
        raise AuthenticationError("Invalid Authorization header format")

    api_key = authorization[7:]  # Remove "Bearer " prefix
    if not api_key:
        raise AuthenticationError("Missing API key")

    return api_key


async def get_authenticated_user(
    request: Request,
    api_key: str = Depends(extract_api_key)
) -> Tuple[ApiKey, Account]:
    """
    FastAPI dependency for authentication and authorization
    Returns the authenticated API key and account objects
    """
    cache_manager = get_cache_manager()

    # Get API key from cache/database
    key_obj = await cache_manager.get_api_key(api_key)
    if not key_obj:
        logger.warning(f"Invalid API key attempted: {api_key[:10]}... from {request.client.host}")
        raise AuthenticationError("Invalid API key")

    # Check if API key is active
    if not key_obj.is_active:
        logger.warning(f"Inactive API key attempted: {api_key[:10]}... from {request.client.host}")
        raise AuthorizationError("API key is deactivated")

    # Get associated account
    account = await cache_manager.get_account(key_obj.user_id)
    if not account:
        logger.error(f"Account not found for API key: {key_obj.user_id}")
        raise AuthorizationError("Account not found")

    # Check if account is active
    if not account.is_active:
        logger.warning(f"Inactive account attempted: {account.user_id}")
        raise AuthorizationError("Account is deactivated")

    # Check budget (pre-authorization check)
    if account.is_over_budget:
        logger.warning(f"Budget exceeded for account: {account.user_id}")
        raise BudgetExceededError(
            f"Budget exceeded. Spent: ${account.spent_usd:.2f}, "
            f"Budget: ${account.budget_usd:.2f}"
        )

    logger.debug(f"Authenticated user: {account.user_id} with key: {api_key[:10]}...")
    return key_obj, account


async def get_admin_auth(authorization: Optional[str] = Header(None)):
    """
    FastAPI dependency for admin authentication
    """
    if not authorization:
        raise AuthenticationError("Missing Authorization header")

    if not authorization.startswith("Bearer "):
        raise AuthenticationError("Invalid Authorization header format")

    admin_key = authorization[7:]  # Remove "Bearer " prefix
    if not admin_key:
        raise AuthenticationError("Missing admin key")

    if admin_key != settings.admin_api_key:
        logger.warning(f"Invalid admin key attempted: {admin_key[:10]}...")
        raise AuthenticationError("Invalid admin key")

    return True


def require_model_access(api_key: ApiKey, model_name: str):
    """Check if API key has access to the specified model"""
    if not api_key.is_model_allowed(model_name):
        raise AuthorizationError(f"API key does not have access to model: {model_name}")


def check_budget_for_cost(account: Account, estimated_cost: float):
    """Check if account can afford the estimated cost"""
    if not account.can_spend(estimated_cost):
        remaining = account.remaining_budget_usd
        raise BudgetExceededError(
            f"Insufficient budget. Estimated cost: ${estimated_cost:.4f}, "
            f"Remaining budget: ${remaining:.2f}"
        )