"""
Account model for user budget management
"""
from datetime import datetime
from typing import Optional
from pydantic import Field
from .base import MongoBaseModel, BudgetDuration


class Account(MongoBaseModel):
    """Account model for budget management"""
    user_id: str = Field(..., index=True, unique=True, description="Unique user identifier")
    account_name: Optional[str] = Field(None, description="Human-readable account name")
    budget_usd: float = Field(0.0, ge=0, description="Budget limit in USD")
    spent_usd: float = Field(0.0, ge=0, description="Amount spent in USD")
    budget_duration: BudgetDuration = Field(
        BudgetDuration.TOTAL,
        description="Budget duration period"
    )
    is_active: bool = Field(True, description="Whether account is active")
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Account creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last update timestamp"
    )

    @property
    def remaining_budget_usd(self) -> float:
        """Calculate remaining budget"""
        return max(0, self.budget_usd - self.spent_usd)

    @property
    def is_over_budget(self) -> bool:
        """Check if account is over budget"""
        return self.spent_usd >= self.budget_usd

    def can_spend(self, amount_usd: float) -> bool:
        """Check if account can spend the specified amount"""
        if not self.is_active:
            return False
        return self.spent_usd + amount_usd <= self.budget_usd