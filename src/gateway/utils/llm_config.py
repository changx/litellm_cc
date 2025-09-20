import litellm
from typing import Dict, Any, Optional
from .config import settings


def get_llm_config_for_model(model_name: str) -> Dict[str, Any]:
    """
    Get LiteLLM configuration including custom API base URLs for a specific model.
    
    Args:
        model_name: The model name (e.g., "gpt-4", "claude-3-sonnet", etc.)
    
    Returns:
        Dictionary with LiteLLM configuration parameters
    """
    config = {"model": model_name}
    
    # Detect provider from model name and apply custom base URLs
    if model_name.startswith(("gpt-", "text-", "davinci", "curie", "babbage", "ada")):
        # OpenAI models
        if settings.openai_api_key:
            config["api_key"] = settings.openai_api_key
        if settings.openai_api_base:
            config["api_base"] = settings.openai_api_base
            
    elif model_name.startswith(("claude-", "anthropic")):
        # Anthropic models
        if settings.anthropic_api_key:
            config["api_key"] = settings.anthropic_api_key
        if settings.anthropic_api_base:
            config["api_base"] = settings.anthropic_api_base
            
    elif model_name.startswith(("command", "cohere")):
        # Cohere models
        if settings.cohere_api_key:
            config["api_key"] = settings.cohere_api_key
        if settings.cohere_api_base:
            config["api_base"] = settings.cohere_api_base
            
    elif model_name.startswith(("gemini", "palm", "vertex")):
        # Google models
        if settings.google_api_key:
            config["api_key"] = settings.google_api_key
        if settings.google_api_base:
            config["vertex_project"] = settings.google_api_base
            
    elif model_name.startswith("azure/"):
        # Azure OpenAI models
        if settings.azure_api_key:
            config["api_key"] = settings.azure_api_key
        if settings.azure_api_base:
            config["api_base"] = settings.azure_api_base
    
    # Custom provider support
    elif settings.custom_llm_provider and model_name.startswith(settings.custom_llm_provider):
        config["api_key"] = settings.custom_api_key
        config["api_base"] = settings.custom_api_base
        config["custom_llm_provider"] = settings.custom_llm_provider
    
    return config


def configure_litellm_for_request(model_name: str, request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Configure request data with appropriate API base URLs and keys for LiteLLM.
    
    Args:
        model_name: The model name
        request_data: Original request data
    
    Returns:
        Modified request data with provider-specific configuration
    """
    config = get_llm_config_for_model(model_name)
    
    # Merge configuration with request data
    enhanced_request = request_data.copy()
    
    # Add provider-specific parameters
    for key, value in config.items():
        if key not in enhanced_request and value is not None:
            enhanced_request[key] = value
    
    return enhanced_request


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