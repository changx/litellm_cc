# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Technology Stack
- Language: Python 3.10+
- Package Manager: uv
- Web Framework: FastAPI with Uvicorn
- Database: MongoDB with Motor (async driver)
- Cache: Redis with async client
- HTTP Client: httpx for LLM provider API calls
- Project Type: LLM Gateway with LiteLLM provider forwarding

## Key Architecture
- **Stateless Design**: Application instances are stateless; all state is in MongoDB/Redis
- **LiteLLM Provider Forwarding**: Using LiteLLM for unified provider API forwarding
- **LiteLLM Forwarder**: Centralized provider forwarding layer (`src/gateway/adapters/litellm_forwarder.py`)
- **Authentication & Budget Integration**: Pre-request auth and budget checks before forwarding to LiteLLM
- **Multi-level Caching**: Local memory cache + Redis with pub/sub invalidation
- **Comprehensive Cost Tracking**: Input/output/cache tokens with per-provider pricing

## Development Commands

### Setup and Installation
```bash
# Install dependencies
uv install

# Copy environment configuration
cp .env.example .env
# Edit .env with your API keys and settings

# Initialize pricing database (required for cost tracking)
uv run python src/gateway/management/init_pricing.py
```

### Running the Application
```bash
# Run the main application
uv run python main.py

# Or via uvicorn directly
uv run uvicorn gateway.app:app --host 0.0.0.0 --port 8000 --reload
```

### Testing and Quality
```bash
# Run the LiteLLM integration test suite
uv run python test_direct_api.py

# Format code with black
uv run black src/

# Sort imports with isort
uv run isort src/

# Type checking with mypy
uv run mypy src/

# Lint with flake8
uv run flake8 src/
```

### Development with Docker
```bash
# Start all services (app, MongoDB, Redis)
docker-compose up -d

# View logs
docker-compose logs -f app

# Stop services
docker-compose down
```

## Core Architecture Components

### LiteLLM Integration (`src/gateway/adapters/`)
LiteLLM-based provider forwarding with preserved authentication:
- `litellm_forwarder.py` - LiteLLM-based unified provider forwarding
- `base.py` - Base models and interfaces for unified request/response handling
- Legacy adapters maintained for reference but replaced by LiteLLM

### API Endpoints (`src/gateway/endpoints/`)
- `openai.py` - OpenAI-compatible endpoints (`/v1/chat/completions`, `/v1/responses`)
- `anthropic.py` - Anthropic-compatible endpoint (`/v1/messages`)

### Database Models (`src/gateway/models/`)
- `account.py` - User accounts with budget management
- `apikey.py` - API key management and user association
- `model_cost.py` - Per-model pricing with cache token support
- `usage_log.py` - Detailed API usage tracking with cost calculation

### Authentication (`src/gateway/auth/`)
- Bearer token authentication for all proxy endpoints
- Admin API key authentication for management endpoints
- User budget enforcement before API calls

### Cost Tracking (`src/gateway/utils/`)
- `cost_calculator.py` - Calculates costs from token usage
- `pricing_loader.py` - Loads pricing from JSON config
- `config/pricing.json` - Pricing configuration for all providers

## Configuration

### Required Environment Variables
```bash
# Database
MONGO_URI=mongodb://localhost:27017
REDIS_URL=redis://localhost:6379

# Admin access
ADMIN_API_KEY=your_secure_admin_key

# LLM Provider API Keys (at least one required)
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
GOOGLE_API_KEY=your_google_key
COHERE_API_KEY=your_cohere_key
AZURE_API_KEY=your_azure_key

# Custom Provider Support
CUSTOM_LLM_PROVIDER=provider_name
CUSTOM_API_KEY=custom_key
CUSTOM_API_BASE=https://custom-endpoint.com/v1
```

### Custom API Base URLs (Optional)
Override default provider endpoints:
```bash
OPENAI_API_BASE=https://custom-openai.com/v1
ANTHROPIC_API_BASE=https://custom-anthropic.com
GOOGLE_API_BASE=custom_vertex_project_id
COHERE_API_BASE=https://custom-cohere.com
AZURE_API_BASE=https://your-resource.openai.azure.com
```

## API Compatibility

### Proxy Endpoints (require Bearer token auth)
- `POST /v1/chat/completions` - OpenAI Chat Completions format
- `POST /v1/responses` - OpenAI Responses format
- `POST /v1/messages` - Anthropic Messages format

### Admin Endpoints (require ADMIN_API_KEY)
- `POST /admin/accounts` - Create user account
- `PATCH /admin/accounts/{user_id}` - Update account
- `POST /admin/keys` - Create API key
- `PATCH /admin/keys/{api_key}` - Update API key
- `POST /admin/costs` - Create/update model costs
- `GET /admin/usage/user/{user_id}` - Get usage logs
- `GET /admin/providers` - List configured providers

## Important Implementation Details

### Provider Auto-Detection
LiteLLM automatically detects providers based on model names:
- `gpt-*` → OpenAI
- `claude-*` → Anthropic
- `gemini-*`, `text-*`, `chat-*` → Google
- `command-*` → Cohere
- Custom providers supported via environment configuration

### Cost Calculation with Cache Tokens
Supports advanced token billing:
- Input tokens × input cost
- Output tokens × output cost
- Cache write tokens × cache write cost (Anthropic)
- Cache read tokens × cache read cost (Anthropic, Google)

### Budget Management
- Account-level budgets shared across all user's API keys
- Atomic budget checks using MongoDB `$inc` operations
- Real-time spending tracking with detailed usage logs

### Horizontal Scaling
- Stateless application design allows unlimited scaling
- Redis pub/sub for cache invalidation across instances
- MongoDB replica sets recommended for production

## Common Development Tasks

### Adding a New Provider
1. Add provider API key to environment variables
2. Configure custom API base URL if needed
3. Add pricing to `src/gateway/config/pricing.json`
4. LiteLLM automatically handles the provider integration
5. Test with the provider's model names

### Updating Model Pricing
1. Modify `src/gateway/config/pricing.json`
2. Run `uv run python src/gateway/management/init_pricing.py`
3. Or use admin API: `POST /admin/costs`

### Debugging API Issues
1. Check logs for provider-specific errors
2. Verify API keys and base URLs in environment
3. Test provider adapters individually
4. Use `test_direct_api.py` for LiteLLM integration testing