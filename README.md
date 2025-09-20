# LiteLLM Gateway

A high-performance, production-ready LLM API Gateway built on top of LiteLLM with advanced cost tracking, budget management, and audit logging.

## Features

- **Multi-format API Support**: Compatible with OpenAI Chat Completions, Anthropic Messages, and LiteLLM Responses
- **Account-level Budget Management**: Shared budget pools across all API keys for each user
- **Fine-grained Cost Control**: Per-model cost configuration with support for input, output, and cached read tokens
- **Comprehensive Audit Logging**: Detailed logging of all API calls for analytics and billing
- **High Performance**: Multi-level caching with Redis pub/sub for cache invalidation
- **Horizontal Scaling**: Stateless design supports unlimited horizontal scaling
- **Admin Management APIs**: Complete management interface for accounts, API keys, and model costs

## Architecture

The system uses a stateless application design with external centralized state management:

- **FastAPI Application**: Stateless proxy instances
- **MongoDB**: Primary data store for accounts, API keys, costs, and usage logs
- **Redis**: Pub/sub messaging for cache invalidation
- **Local Memory Cache**: L1 cache for high-performance reads

## Quick Start

### Using Docker Compose

1. Clone the repository:
```bash
git clone <repository-url>
cd litellm_cc
```

2. Copy and configure environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys and configuration
```

3. Start the services:
```bash
docker-compose up -d
```

The gateway will be available at `http://localhost:8000`.

### Manual Installation

1. Install dependencies:
```bash
uv install
```

2. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. Start MongoDB and Redis locally

4. Run the application:
```bash
python main.py
```

## API Endpoints

### Proxy Endpoints

- `POST /v1/chat/completions` - OpenAI Chat Completions compatible
- `POST /v1/messages` - Anthropic Messages compatible  
- `POST /v1/responses` - LiteLLM Responses format

### Admin Endpoints

- `POST /admin/accounts` - Create account
- `PATCH /admin/accounts/{user_id}` - Update account
- `POST /admin/keys` - Create API key
- `PATCH /admin/keys/{api_key}` - Update API key
- `POST /admin/costs` - Create/update model cost
- `GET /admin/usage/user/{user_id}` - Get user usage logs

All admin endpoints require authentication with the `ADMIN_API_KEY`.

## Authentication

All proxy endpoints use Bearer token authentication:
```
Authorization: Bearer <your-api-key>
```

## Configuration

Key environment variables:

- `MONGO_URI`: MongoDB connection string
- `REDIS_URL`: Redis connection string
- `OPENAI_API_KEY`: Your OpenAI API key
- `ANTHROPIC_API_KEY`: Your Anthropic API key
- `ADMIN_API_KEY`: Secure key for admin endpoints

See `.env.example` for all available configuration options.

## Budget Management

The system supports account-level budgets where all API keys belonging to a user share the same budget pool. Budget checks are performed before each API call, and spending is atomically updated using MongoDB's `$inc` operation to ensure accuracy under high concurrency.

## Cost Calculation

Costs are calculated based on:
- Input tokens × input cost per million tokens
- Output tokens × output cost per million tokens (or cached read cost for cache hits)

Model costs are configurable via the admin API and cached for performance.

## Monitoring

- Health check endpoint: `GET /health`
- Comprehensive logging with configurable levels
- Usage analytics via the admin API

## Deployment

The application is designed for containerized deployment with horizontal scaling:

1. Build and deploy multiple instances behind a load balancer
2. Ensure MongoDB is deployed as a replica set for high availability
3. Use Redis for cache coordination between instances
4. Configure appropriate resource limits and health checks

## License

MIT License