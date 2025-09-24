"""
Global exception handlers for the FastAPI application
"""
import logging
from typing import Union
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError
import litellm

logger = logging.getLogger(__name__)


def add_exception_handlers(app: FastAPI):
    """Add global exception handlers to the FastAPI app"""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Handle FastAPI HTTPException"""
        logger.warning(
            f"HTTP {exc.status_code} at {request.url.path}: {exc.detail} "
            f"from {request.client.host if request.client else 'unknown'}"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "message": exc.detail,
                    "type": "http_exception",
                    "status_code": exc.status_code
                }
            }
        )

    @app.exception_handler(StarletteHTTPException)
    async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException):
        """Handle Starlette HTTPException"""
        logger.warning(
            f"HTTP {exc.status_code} at {request.url.path}: {exc.detail} "
            f"from {request.client.host if request.client else 'unknown'}"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "message": exc.detail,
                    "type": "http_exception",
                    "status_code": exc.status_code
                }
            }
        )

    @app.exception_handler(ValidationError)
    async def validation_exception_handler(request: Request, exc: ValidationError):
        """Handle Pydantic validation errors"""
        logger.warning(f"Validation error at {request.url.path}: {str(exc)}")
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "message": "Validation error",
                    "type": "validation_error",
                    "details": exc.errors()
                }
            }
        )

    @app.exception_handler(litellm.AuthenticationError)
    async def litellm_auth_exception_handler(request: Request, exc: litellm.AuthenticationError):
        """Handle LiteLLM authentication errors"""
        logger.error(f"LiteLLM authentication error at {request.url.path}: {str(exc)}")
        return JSONResponse(
            status_code=401,
            content={
                "error": {
                    "message": "Authentication failed with upstream provider",
                    "type": "authentication_error"
                }
            }
        )

    @app.exception_handler(litellm.RateLimitError)
    async def litellm_rate_limit_exception_handler(request: Request, exc: litellm.RateLimitError):
        """Handle LiteLLM rate limit errors"""
        logger.warning(f"LiteLLM rate limit error at {request.url.path}: {str(exc)}")
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "message": "Rate limit exceeded by upstream provider",
                    "type": "rate_limit_exceeded"
                }
            }
        )

    @app.exception_handler(litellm.APIError)
    async def litellm_api_exception_handler(request: Request, exc: litellm.APIError):
        """Handle LiteLLM API errors"""
        logger.error(f"LiteLLM API error at {request.url.path}: {str(exc)}")

        # Map different API errors to appropriate status codes
        if "invalid" in str(exc).lower() and ("model" in str(exc).lower() or "parameter" in str(exc).lower()):
            status_code = 400
            error_type = "invalid_request_error"
        elif "not found" in str(exc).lower():
            status_code = 404
            error_type = "not_found_error"
        else:
            status_code = 502
            error_type = "upstream_api_error"

        return JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "message": f"Upstream API error: {str(exc)}",
                    "type": error_type
                }
            }
        )

    @app.exception_handler(litellm.ServiceUnavailableError)
    async def litellm_service_unavailable_exception_handler(request: Request, exc: litellm.ServiceUnavailableError):
        """Handle LiteLLM service unavailable errors"""
        logger.error(f"LiteLLM service unavailable at {request.url.path}: {str(exc)}")
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "message": "Upstream service temporarily unavailable",
                    "type": "service_unavailable_error"
                }
            }
        )

    @app.exception_handler(litellm.Timeout)
    async def litellm_timeout_exception_handler(request: Request, exc: litellm.Timeout):
        """Handle LiteLLM timeout errors"""
        logger.error(f"LiteLLM timeout at {request.url.path}: {str(exc)}")
        return JSONResponse(
            status_code=504,
            content={
                "error": {
                    "message": "Request timeout from upstream provider",
                    "type": "timeout_error"
                }
            }
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle all other exceptions"""
        logger.error(
            f"Unhandled exception at {request.url.path}: {type(exc).__name__}: {str(exc)}",
            exc_info=True
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "message": "Internal server error",
                    "type": "internal_server_error"
                }
            }
        )