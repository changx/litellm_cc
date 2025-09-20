# Cost Tracking Feature

## Overview

The LLM Gateway now includes comprehensive cost tracking functionality that supports detailed billing for input tokens, output tokens, cache write tokens, and cache read tokens across multiple LLM providers.

## Features

### 1. Multi-Provider Cost Configuration
- Built-in pricing data for OpenAI, Anthropic, Google Gemini, and Cohere models
- JSON-based configuration file for easy pricing updates
- Automatic cost calculation based on actual API responses

### 2. Enhanced Token Tracking
- **Input tokens**: Standard input/prompt tokens
- **Output tokens**: Generated response tokens
- **Cache write tokens**: Tokens written to cache (when supported by provider)
- **Cache read tokens**: Tokens read from cache (for cache hits)

### 3. Provider-Specific Cache Support
- **Anthropic**: Full cache support with `cache_creation_input_tokens` and `cache_read_input_tokens`
- **Google Gemini**: Cache read support with `cachedContentTokenCount`
- **OpenAI**: Prepared for future cache token support
- **Cohere**: Basic tracking (cache tokens not yet supported by provider)

## Configuration

### Pricing Configuration File
The pricing data is stored in `src/gateway/config/pricing.json`:

```json
{
  "providers": {
    "anthropic": {
      "models": {
        "claude-3-5-sonnet-20241022": {
          "input_cost_per_million_tokens_usd": 3.00,
          "output_cost_per_million_tokens_usd": 15.00,
          "cache_write_cost_per_million_tokens_usd": 3.75,
          "cache_read_cost_per_million_tokens_usd": 0.30
        }
      }
    }
  }
}
```

### Database Schema Updates
The following models have been enhanced:

- **ModelCost**: Added `cache_write_cost_per_million_tokens_usd` field
- **UsageLog**: Added `cache_write_tokens` and `cache_read_tokens` fields
- **LLMUsage**: Added cache token tracking in base adapter

## Usage

### Initialize Pricing Database
```bash
python src/gateway/management/init_pricing.py
```

### Cost Calculation Example
```python
from gateway.utils.cost_calculator import CostCalculator

cost = await CostCalculator.calculate_cost(
    model_name="claude-3-5-sonnet-20241022",
    input_tokens=1000,
    output_tokens=500,
    cache_write_tokens=2000,  # Cache write tokens
    cache_read_tokens=0       # Cache read tokens
)
```

### Demo Script
Run the cost calculation demo:
```bash
python examples/cost_calculation_demo.py
```

## API Integration

The cost tracking is automatically integrated into all API endpoints:

- `/v1/chat/completions` (OpenAI format)
- `/v1/responses` (OpenAI responses format)
- `/v1/messages` (Anthropic format)

### Enhanced Usage Logging
All API calls now log detailed usage information including:
- Standard token counts
- Cache token counts
- Accurate cost calculations
- Cache hit detection

## Backward Compatibility

The implementation maintains full backward compatibility:
- Existing cost calculations continue to work
- Cache token fields default to 0 for providers that don't support them
- Legacy `is_cache_hit` field is still supported

## Cost Calculation Logic

1. **Input Cost**: `(input_tokens / 1M) × input_cost_per_million_tokens_usd`
2. **Output Cost**: `(output_tokens / 1M) × output_cost_per_million_tokens_usd`
3. **Cache Write Cost**: `(cache_write_tokens / 1M) × cache_write_cost_per_million_tokens_usd`
4. **Cache Read Cost**: `(cache_read_tokens / 1M) × cache_read_cost_per_million_tokens_usd`
5. **Total Cost**: Sum of all component costs

## Management Commands

### Initialize Pricing Database
```bash
python src/gateway/management/init_pricing.py
```
This command loads all pricing data from the JSON configuration into the database.

## Files Modified/Created

### New Files
- `src/gateway/config/pricing.json` - Pricing configuration
- `src/gateway/utils/pricing_loader.py` - Pricing data loader utility
- `src/gateway/management/init_pricing.py` - Database initialization script
- `examples/cost_calculation_demo.py` - Cost calculation demo

### Modified Files
- `src/gateway/models/model_cost.py` - Added cache write cost field
- `src/gateway/models/usage_log.py` - Added cache token fields
- `src/gateway/adapters/base.py` - Enhanced LLMUsage model
- `src/gateway/adapters/anthropic_adapter.py` - Cache token parsing
- `src/gateway/adapters/openai_adapter.py` - Prepared for cache tokens
- `src/gateway/adapters/google_adapter.py` - Google cache token support
- `src/gateway/adapters/cohere_adapter.py` - Basic cache token structure
- `src/gateway/utils/cost_calculator.py` - Enhanced cost calculation
- `src/gateway/endpoints/openai.py` - Updated usage tracking
- `src/gateway/endpoints/anthropic.py` - Updated usage tracking

## Future Enhancements

1. **Real-time Pricing Updates**: API endpoints to update pricing without database migration
2. **Cost Alerts**: Configurable spending limits and alerts
3. **Detailed Cost Analytics**: Per-user, per-model cost reporting
4. **Bulk Pricing Operations**: Import/export pricing configurations
5. **Provider-specific Optimizations**: Enhanced cache token support as providers add features