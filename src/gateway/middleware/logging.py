"""
Request logging middleware
"""
import time
import logging
from typing import Callable
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log request details and response times"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        client_ip = request.client.host if request.client else "unknown"

        # Log request start
        logger.info(
            f"Request started: {request.method} {request.url.path} from {client_ip}"
        )

        # Process request
        response = await call_next(request)

        # Calculate processing time
        process_time = (time.time() - start_time) * 1000

        # Log request completion
        logger.info(
            f"Request completed: {request.method} {request.url.path} "
            f"-> {response.status_code} in {process_time:.2f}ms from {client_ip}"
        )

        # Add processing time header
        response.headers["X-Process-Time"] = f"{process_time:.2f}ms"

        return response


def add_logging_middleware(app: FastAPI):
    """Add request logging middleware to the FastAPI app"""
    app.add_middleware(RequestLoggingMiddleware)