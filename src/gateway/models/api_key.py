"""
API Key model for authentication
"""
from datetime import datetime
from typing import List, Optional
from pydantic import Field
from .base import MongoBaseModel


class ApiKey(MongoBaseModel):
    """API Key model for authentication and authorization"""
    api_key: str = Field(..., unique=True, index=True, description="The API key string")
    user_id: str = Field(..., index=True, description="Associated user ID")
    key_name: str = Field(..., description="Human-readable key name")
    is_active: bool = Field(True, description="Whether key is active")
    allowed_models: Optional[List[str]] = Field(
        None,
        description="List of allowed models, None means all models allowed"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Key creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last update timestamp"
    )

    def is_model_allowed(self, model_name: str) -> bool:
        """Check if the model is allowed for this API key"""
        if not self.is_active:
            return False
        if self.allowed_models is None:
            return True  # All models allowed
        return model_name in self.allowed_models