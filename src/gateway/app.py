"""
Main FastAPI application
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

from gateway.utils.config import settings
from gateway.database import connect_to_mongo, close_mongo_connection
from gateway.cache import connect_to_redis, close_redis_connection, get_cache_manager
from gateway.middleware import add_exception_handlers, add_cors_middleware, add_logging_middleware
from gateway.api import api_router
from gateway.admin import admin_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting LLM Gateway application")

    # Display configuration (for debugging)
    settings.log_configuration()

    # Validate configuration
    try:
        missing_keys = settings.validate_provider_keys(strict=False)
        available_providers = settings.get_available_providers()

        if missing_keys:
            logger.warning(f"Missing provider keys: {missing_keys}")

        if available_providers:
            logger.info(f"Available LLM providers: {available_providers}")
        else:
            logger.warning(
                "No LLM provider API keys configured! "
                "Set OPENAI_API_KEY or ANTHROPIC_API_KEY to enable LLM functionality."
            )
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        raise

    # Initialize database connections
    try:
        await connect_to_mongo()
        logger.info("MongoDB connection established")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise

    # Initialize Redis connection
    try:
        await connect_to_redis()
        logger.info("Redis connection established")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        raise

    # Start cache manager
    try:
        cache_manager = get_cache_manager()
        await cache_manager.start()
        logger.info("Cache manager started")
    except Exception as e:
        logger.error(f"Failed to start cache manager: {e}")
        raise

    logger.info("LLM Gateway application startup completed")

    yield

    # Shutdown
    logger.info("Shutting down LLM Gateway application")

    # Stop cache manager
    try:
        cache_manager = get_cache_manager()
        await cache_manager.stop()
        logger.info("Cache manager stopped")
    except Exception as e:
        logger.error(f"Error stopping cache manager: {e}")

    # Close connections
    try:
        await close_redis_connection()
        logger.info("Redis connection closed")
    except Exception as e:
        logger.error(f"Error closing Redis connection: {e}")

    try:
        await close_mongo_connection()
        logger.info("MongoDB connection closed")
    except Exception as e:
        logger.error(f"Error closing MongoDB connection: {e}")

    logger.info("LLM Gateway application shutdown completed")


# Create FastAPI application
app = FastAPI(
    title="LLM API Gateway",
    description="High-performance LLM API Gateway with cost tracking and budget management",
    version="1.0.0",
    lifespan=lifespan
)

# Add middleware
add_cors_middleware(app)
add_logging_middleware(app)

# Add exception handlers
add_exception_handlers(app)

# Include routers
app.include_router(api_router)
app.include_router(admin_router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "LLM API Gateway",
        "version": "1.0.0",
        "status": "healthy",
        "endpoints": {
            "chat_completions": "/v1/chat/completions",
            "anthropic_messages": "/v1/messages",
            "anthropic_count_tokens": "/v1/messages/count_tokens",
            "litellm_responses": "/v1/responses",
            "models": "/v1/models",
            "account": "/v1/account",
            "admin": "/admin/"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "llm-api-gateway",
        "version": "1.0.0"
    }


# Export the app
__all__ = ["app"]