import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .admin.routes import router as admin_router
from .cache.manager import cache_manager
from .database.connection import db_manager
from .endpoints.anthropic import router as anthropic_router
from .endpoints.openai import router as openai_router
from .utils.config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Direct LLM Gateway...")

    # Log configured providers
    if settings.openai_api_key:
        base_info = (
            f" at {settings.openai_api_base}" if settings.openai_api_base else ""
        )
        logger.info(f"Configured OpenAI provider{base_info}")

    if settings.anthropic_api_key:
        base_info = (
            f" at {settings.anthropic_api_base}" if settings.anthropic_api_base else ""
        )
        logger.info(f"Configured Anthropic provider{base_info}")

    if settings.cohere_api_key:
        base_info = (
            f" at {settings.cohere_api_base}" if settings.cohere_api_base else ""
        )
        logger.info(f"Configured Cohere provider{base_info}")

    if settings.google_api_key:
        base_info = (
            f" at {settings.google_api_base}" if settings.google_api_base else ""
        )
        logger.info(f"Configured Google provider{base_info}")

    if settings.azure_api_key:
        base_info = f" at {settings.azure_api_base}" if settings.azure_api_base else ""
        logger.info(f"Configured Azure provider{base_info}")

    # Custom provider support
    if (
        settings.custom_llm_provider
        and settings.custom_api_key
        and settings.custom_api_base
    ):
        logger.info(
            f"Configured custom provider: {settings.custom_llm_provider} at {settings.custom_api_base}"
        )

    # Connect to databases
    try:
        await db_manager.connect(settings.mongo_uri, settings.mongo_db_name)
        logger.info("Connected to MongoDB")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise

    # Connect to Redis cache
    try:
        cache_manager.redis_url = settings.redis_url
        cache_manager.cache_ttl = settings.cache_ttl
        await cache_manager.connect()
        logger.info("Connected to Redis")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        raise

    logger.info("Direct LLM Gateway started successfully")

    yield

    # Shutdown
    logger.info("Shutting down Direct LLM Gateway...")

    try:
        await cache_manager.disconnect()
        logger.info("Disconnected from Redis")
    except Exception as e:
        logger.error(f"Error disconnecting from Redis: {e}")

    try:
        await db_manager.disconnect()
        logger.info("Disconnected from MongoDB")
    except Exception as e:
        logger.error(f"Error disconnecting from MongoDB: {e}")

    logger.info("Direct LLM Gateway shutdown complete")


app = FastAPI(
    title="Direct LLM Gateway",
    description="High-performance LLM API Gateway with direct provider integration and cost tracking",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "direct-llm-gateway", "version": "1.0.0"}


# Include routers
app.include_router(openai_router, tags=["OpenAI"])
app.include_router(anthropic_router, tags=["Anthropic"])
app.include_router(admin_router, tags=["Admin"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "gateway.app:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        reload=False,
    )
