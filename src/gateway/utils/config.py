from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database settings
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "litellm_gateway"
    
    # Redis settings
    redis_url: str = "redis://localhost:6379"
    
    # Cache settings
    cache_ttl: int = 3600  # 1 hour
    
    # LLM Provider API Keys
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    cohere_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    azure_api_key: Optional[str] = None
    
    # Admin settings
    admin_api_key: str = "admin-change-me"
    
    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    
    # CORS settings
    cors_origins: list = ["*"]
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()