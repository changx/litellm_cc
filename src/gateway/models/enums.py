from enum import Enum


class BudgetDuration(str, Enum):
    TOTAL = "total"
    MONTHLY = "monthly"
    DAILY = "daily"


class Provider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    COHERE = "cohere"
    GOOGLE = "google"
    AZURE = "azure"
    OTHER = "other"
