# Migration from LiteLLM to Direct API Integration

## Overview

This project has been successfully migrated from using LiteLLM as an intermediary layer to direct integration with upstream LLM provider APIs. This change provides:

- **Better Performance**: Direct API calls eliminate the overhead of LiteLLM abstraction
- **More Control**: Full control over request/response handling and error management
- **Custom Base URLs**: Native support for custom API endpoints for each provider
- **Simplified Dependencies**: Removed the large LiteLLM dependency

## Architecture Changes

### Before (LiteLLM-based)
```
Client Request → Gateway → LiteLLM → Provider API
```

### After (Direct Integration)
```
Client Request → Gateway → Provider Adapter → Provider API
```

## New Architecture Components

### 1. Provider Adapters (`src/gateway/adapters/`)
- **Base Adapter**: `base.py` - Common interface for all providers
- **OpenAI Adapter**: `openai_adapter.py` - Direct OpenAI API integration
- **Anthropic Adapter**: `anthropic_adapter.py` - Direct Claude API integration
- **Google Adapter**: `google_adapter.py` - Direct Gemini API integration
- **Cohere Adapter**: `cohere_adapter.py` - Direct Cohere API integration

### 2. Provider Router (`provider_router.py`)
- Automatically routes requests to the correct adapter based on model name
- Handles provider detection and adapter instantiation

### 3. Unified Data Models
- `LLMRequest`: Standardized request format across all providers
- `LLMResponse`: Standardized response format across all providers
- `LLMMessage`: Standardized message format

## Supported Providers

| Provider | Endpoint | Authentication | Custom Base URL |
|----------|----------|----------------|-----------------|
| OpenAI | `/v1/chat/completions` | Bearer Token | ✅ OPENAI_API_BASE |
| Anthropic | `/v1/messages` | x-api-key | ✅ ANTHROPIC_API_BASE |
| Google Gemini | `/v1beta/models/{model}:generateContent` | x-goog-api-key | ✅ GOOGLE_API_BASE |
| Cohere | `/v2/chat` | Bearer Token | ✅ COHERE_API_BASE |
| Azure OpenAI | `/v1/chat/completions` | Bearer Token | ✅ AZURE_API_BASE |

## Configuration

The same environment variables are used, but now they directly configure the adapters:

```bash
# Provider API Keys
OPENAI_API_KEY=your-openai-key
ANTHROPIC_API_KEY=your-anthropic-key
GOOGLE_API_KEY=your-google-key
COHERE_API_KEY=your-cohere-key
AZURE_API_KEY=your-azure-key

# Custom API Base URLs
OPENAI_API_BASE=https://custom-openai-endpoint.com
ANTHROPIC_API_BASE=https://custom-anthropic-endpoint.com
GOOGLE_API_BASE=https://custom-google-endpoint.com
COHERE_API_BASE=https://custom-cohere-endpoint.com
AZURE_API_BASE=https://custom-azure-endpoint.com

# Custom Provider Support
CUSTOM_LLM_PROVIDER=my-provider
CUSTOM_API_KEY=your-custom-key
CUSTOM_API_BASE=https://my-provider-endpoint.com
```

## API Compatibility

The external API interface remains **100% compatible** with additional OpenAI endpoints:

- **OpenAI Chat Completions**: `/v1/chat/completions` endpoint maintains OpenAI API compatibility
- **OpenAI Responses**: `/v1/responses` endpoint provides OpenAI responses API compatibility
- **Anthropic Format**: `/v1/messages` endpoint maintains Anthropic API compatibility
- **All Features Preserved**: Authentication, cost tracking, usage logging, and admin endpoints work exactly the same

### OpenAI API Endpoints

| Endpoint | Purpose | Request Format | Response Format |
|----------|---------|----------------|-----------------|
| `/v1/chat/completions` | Standard chat completions | OpenAI format | OpenAI format |
| `/v1/responses` | OpenAI responses API | OpenAI format | OpenAI format |

Both endpoints:
- Support the same request parameters (`model`, `messages`, `max_tokens`, `temperature`, etc.)
- Return the same response format with `choices`, `usage`, and metadata
- Route automatically to the correct upstream provider based on model name
- Support custom API base URLs for each provider

## Benefits

### Performance Improvements
- **Reduced Latency**: No LiteLLM processing overhead
- **Lower Memory Usage**: Smaller dependency footprint
- **Direct Error Handling**: Native error responses from providers

### Enhanced Control
- **Request Customization**: Full control over request formatting per provider
- **Response Processing**: Custom response handling for each provider
- **Error Management**: Provider-specific error handling and retry logic

### Maintainability
- **Simpler Dependencies**: Removed large LiteLLM dependency and its sub-dependencies
- **Clear Architecture**: Explicit adapter pattern for each provider
- **Easy Extension**: Simple to add new providers by implementing the base adapter

## Migration Summary

### Files Added
- `src/gateway/adapters/` - New adapter system
- `src/gateway/utils/provider_info.py` - Provider information utility

### Files Removed
- `src/gateway/endpoints/litellm_responses.py` - No longer needed
- `src/gateway/utils/llm_config.py` - Replaced by adapter system

### Files Modified
- `src/gateway/endpoints/openai.py` - Uses new adapter system
- `src/gateway/endpoints/anthropic.py` - Uses new adapter system
- `src/gateway/app.py` - Removed LiteLLM configuration
- `pyproject.toml` - Removed LiteLLM dependency

### Dependencies
- **Removed**: `litellm>=1.40.0`
- **Added**: Direct usage of existing `httpx>=0.25.0`

## Testing

Run the test suite to verify the migration:

```bash
uv run python test_direct_api.py
```

This confirms:
- Provider routing works correctly
- Request/response formats are properly handled
- All providers are correctly detected
- Custom API base URL support is functional

## Future Enhancements

The new architecture makes it easy to add:
- **Streaming Support**: Provider-specific streaming implementations
- **Advanced Error Handling**: Retry logic and fallback providers
- **Request Caching**: Provider-aware caching strategies
- **New Providers**: Easy to add by implementing the base adapter interface