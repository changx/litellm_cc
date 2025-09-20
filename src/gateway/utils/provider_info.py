from typing import Dict, Optional
from .config import settings


def get_supported_providers() -> Dict[str, Dict[str, Optional[str]]]:
    """
    Get information about configured providers and their endpoints.
    
    Returns:
        Dictionary with provider information
    """
    providers = {}
    
    if settings.openai_api_key:
        providers["openai"] = {
            "api_key_configured": True,
            "api_base": settings.openai_api_base,
            "models": "gpt-4, gpt-3.5-turbo, text-davinci-003, etc."
        }
    
    if settings.anthropic_api_key:
        providers["anthropic"] = {
            "api_key_configured": True,
            "api_base": settings.anthropic_api_base,
            "models": "claude-3-sonnet, claude-3-haiku, etc."
        }
    
    if settings.cohere_api_key:
        providers["cohere"] = {
            "api_key_configured": True,
            "api_base": settings.cohere_api_base,
            "models": "command, command-light, etc."
        }
    
    if settings.google_api_key:
        providers["google"] = {
            "api_key_configured": True,
            "api_base": settings.google_api_base,
            "models": "gemini-pro, palm2, etc."
        }
    
    if settings.azure_api_key:
        providers["azure"] = {
            "api_key_configured": True,
            "api_base": settings.azure_api_base,
            "models": "azure/gpt-4, azure/gpt-35-turbo, etc."
        }
    
    if settings.custom_llm_provider:
        providers[settings.custom_llm_provider] = {
            "api_key_configured": bool(settings.custom_api_key),
            "api_base": settings.custom_api_base,
            "models": "Custom provider models"
        }
    
    return providers