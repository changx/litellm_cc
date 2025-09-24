"""
Configuration management using Pydantic settings
"""
import os
from typing import Optional, List
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Server settings
    host: str = Field("0.0.0.0", description="Host to bind the server to")
    port: int = Field(8000, description="Port to bind the server to")
    log_level: str = Field("INFO", description="Log level")

    # Database settings
    mongo_uri: str = Field(..., description="MongoDB connection URI")
    mongo_db_name: str = Field("llm_gateway", description="MongoDB database name")

    # Redis settings
    redis_url: str = Field("redis://localhost:6379", description="Redis connection URL")

    # Admin settings
    admin_api_key: str = Field(..., description="Admin API key for management endpoints")

    # Upstream provider settings
    openai_api_key: Optional[str] = Field(None, description="OpenAI API key")
    openai_base_url: str = Field("https://api.openai.com/v1", description="OpenAI base URL")

    anthropic_api_key: Optional[str] = Field(None, description="Anthropic API key")
    anthropic_base_url: str = Field("https://api.anthropic.com", description="Anthropic base URL")

    # Cache settings
    cache_size: int = Field(10000, description="L1 cache max size")
    cache_ttl: int = Field(300, description="L1 cache TTL in seconds")

    # Request settings
    max_request_size: int = Field(10 * 1024 * 1024, description="Max request size in bytes")
    request_timeout: int = Field(60, description="Request timeout in seconds")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False
    }

    def validate_provider_keys(self) -> List[str]:
        """Validate that at least one provider key is configured"""
        missing_keys = []

        if not self.openai_api_key:
            missing_keys.append("OPENAI_API_KEY")

        if not self.anthropic_api_key:
            missing_keys.append("ANTHROPIC_API_KEY")

        if len(missing_keys) == 2:
            raise ValueError("At least one provider API key must be configured")

        return missing_keys


# Global settings instance
settings = Settings()