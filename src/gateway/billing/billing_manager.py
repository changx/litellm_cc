"""
Billing management with atomic operations
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from gateway.models import Account, ApiKey, UsageLog
from gateway.database.repositories import AccountRepository, UsageLogRepository
from gateway.cache import get_cache_manager
from .cost_calculator import CostCalculator

logger = logging.getLogger(__name__)


class BillingManager:
    """Manage billing operations with atomic account updates"""

    def __init__(self):
        self.account_repo = AccountRepository()
        self.usage_repo = UsageLogRepository()
        self.cost_calculator = CostCalculator()
        self.cache_manager = get_cache_manager()

    async def process_usage_and_bill(
        self,
        api_key: ApiKey,
        account: Account,
        model_name: str,
        usage_data: Dict[str, Any],
        request_endpoint: str,
        request_payload: Dict[str, Any],
        response_payload: Dict[str, Any],
        client_ip: Optional[str] = None,
        processing_time_ms: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Process usage data, calculate cost, and atomically update account billing
        """
        try:
            # Calculate cost breakdown
            cost_breakdown = await self.cost_calculator.calculate_cost(
                model_name=model_name,
                usage_data=usage_data
            )

            total_cost = cost_breakdown["total_cost_usd"]

            # Atomically update account spending
            if total_cost > 0:
                success = await self.account_repo.atomic_spend(account.user_id, total_cost)
                if not success:
                    logger.error(
                        f"Failed to atomically update spending for user {account.user_id}. "
                        f"Cost: ${total_cost:.6f}"
                    )
                    # Continue with logging even if billing update failed
                else:
                    logger.info(
                        f"Billing updated for user {account.user_id}: "
                        f"${total_cost:.6f} for {usage_data.get('total_tokens', 0)} tokens"
                    )

                    # Invalidate account cache to reflect updated spending
                    await self.cache_manager.invalidate_account(account.user_id)

            # Create usage log entry
            usage_log = UsageLog(
                user_id=account.user_id,
                api_key=api_key.api_key,
                model_name=model_name,
                is_cache_hit=usage_data.get("is_cache_hit", False),
                input_tokens=usage_data.get("input_tokens", 0),
                output_tokens=usage_data.get("output_tokens", 0),
                cached_tokens=usage_data.get("cached_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
                cost_usd=total_cost,
                request_endpoint=request_endpoint,
                ip_address=client_ip,
                request_payload=request_payload,
                response_payload=response_payload,
                timestamp=datetime.utcnow(),
                processing_time_ms=processing_time_ms
            )

            # Log usage asynchronously
            await self.usage_repo.create_log(usage_log)

            # Return combined cost breakdown and billing info
            result = {
                **cost_breakdown,
                "billing_success": success if total_cost > 0 else True,
                "usage_logged": True
            }

            return result

        except Exception as e:
            logger.error(f"Error in billing process: {e}")

            # Try to log the error request
            try:
                await self.log_failed_request(
                    api_key=api_key,
                    account=account,
                    request_data=request_payload,
                    endpoint=request_endpoint,
                    error_message=f"Billing error: {str(e)}",
                    client_ip=client_ip,
                    processing_time_ms=processing_time_ms
                )
            except Exception as log_error:
                logger.error(f"Failed to log billing error: {log_error}")

            # Re-raise the original exception
            raise

    async def log_failed_request(
        self,
        api_key: ApiKey,
        account: Account,
        request_data: Dict[str, Any],
        endpoint: str,
        error_message: str,
        client_ip: Optional[str] = None,
        processing_time_ms: Optional[float] = None
    ):
        """Log failed requests for audit purposes"""
        try:
            error_log = UsageLog(
                user_id=account.user_id,
                api_key=api_key.api_key,
                model_name=request_data.get("model", "unknown"),
                is_cache_hit=False,
                input_tokens=0,
                output_tokens=0,
                cached_tokens=0,
                total_tokens=0,
                cost_usd=0.0,
                request_endpoint=endpoint,
                ip_address=client_ip,
                request_payload=request_data,
                response_payload={"error": True},
                timestamp=datetime.utcnow(),
                processing_time_ms=processing_time_ms,
                error_message=error_message
            )

            await self.usage_repo.create_log(error_log)
            logger.info(f"Error request logged for user {account.user_id}: {error_message}")

        except Exception as e:
            logger.error(f"Failed to log error request: {e}")

    async def check_budget_before_request(
        self,
        account: Account,
        model_name: str,
        request_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Pre-check if account has budget for estimated request cost
        Returns budget check results
        """
        try:
            # Estimate request cost
            estimated_cost = await self.cost_calculator.estimate_request_cost(
                model_name=model_name,
                request_data=request_data
            )

            remaining_budget = account.remaining_budget_usd
            can_afford = account.can_spend(estimated_cost)

            result = {
                "estimated_cost_usd": estimated_cost,
                "remaining_budget_usd": remaining_budget,
                "can_afford": can_afford,
                "budget_exceeded": account.is_over_budget
            }

            if not can_afford:
                logger.warning(
                    f"Budget check failed for user {account.user_id}: "
                    f"estimated ${estimated_cost:.4f}, remaining ${remaining_budget:.2f}"
                )

            return result

        except Exception as e:
            logger.error(f"Error in budget check: {e}")
            # On error, allow the request but log the issue
            return {
                "estimated_cost_usd": 0.0,
                "remaining_budget_usd": account.remaining_budget_usd,
                "can_afford": True,
                "budget_exceeded": False,
                "check_error": str(e)
            }

    async def get_usage_summary(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get usage summary for a user"""
        try:
            summary = await self.usage_repo.get_usage_summary(
                user_id=user_id,
                start_date=start_date,
                end_date=end_date
            )

            # Get current account state
            account = await self.cache_manager.get_account(user_id)
            if account:
                summary.update({
                    "current_budget_usd": account.budget_usd,
                    "current_spent_usd": account.spent_usd,
                    "remaining_budget_usd": account.remaining_budget_usd,
                    "budget_exceeded": account.is_over_budget
                })

            return summary

        except Exception as e:
            logger.error(f"Error getting usage summary for user {user_id}: {e}")
            return {
                "total_requests": 0,
                "total_cost": 0.0,
                "total_tokens": 0,
                "error": str(e)
            }