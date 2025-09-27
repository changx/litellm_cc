"""
Main proxy router for handling LLM requests
"""

import logging
import time
from typing import Any, Dict, Tuple

from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse

from gateway.auth.dependencies import require_model_access
from gateway.billing import BillingManager
from gateway.models import Account, ApiKey
from gateway.providers.anthropic import AnthropicProvider

from .litellm_client import LiteLLMClient
from .streaming import StreamingResponseHandler

logger = logging.getLogger(__name__)


class ProxyRouter:
    """Main proxy router for LLM API requests"""

    def __init__(self):
        self.litellm_client = LiteLLMClient()
        self.anthropic_provider = AnthropicProvider()
        self.billing_manager = BillingManager()
        self.streaming_handler = StreamingResponseHandler(self.billing_manager)

    async def route_request(
        self,
        request: Request,
        api_key: ApiKey,
        account: Account,
        request_data: Dict[str, Any],
        endpoint: str,
    ) -> Tuple[JSONResponse, StreamingResponse]:
        """
        Route request to appropriate provider and handle response
        """
        start_time = time.time()
        client_ip = request.client.host if request.client else None

        try:
            # Determine provider based on endpoint
            provider = self.litellm_client.get_provider_from_endpoint(endpoint)
            logger.info(f"Routing request to {provider} for endpoint {endpoint}")

            # Extract model name from request
            model_name = request_data.get("model")
            if not model_name:
                return JSONResponse(
                    status_code=400, content={"error": "Model name is required"}
                )

            # Check model access permissions
            require_model_access(api_key, model_name)

            # Check if this is a streaming request
            is_streaming = request_data.get("stream", False)

            # Route to appropriate provider
            if provider == "anthropic":
                # Use direct Anthropic provider
                response = await self.anthropic_provider.forward_messages(
                    request_data=request_data, stream=is_streaming
                )

                if is_streaming:
                    # For Anthropic streaming, response is a tuple
                    stream_generator, usage_data, complete_message = response
                    return await self._handle_anthropic_streaming_response(
                        stream_generator=stream_generator,
                        usage_data=usage_data,
                        complete_message=complete_message,
                        api_key=api_key,
                        account=account,
                        request_data=request_data,
                        endpoint=endpoint,
                        client_ip=client_ip,
                        processing_time_ms=(time.time() - start_time) * 1000,
                    )
                else:
                    # For Anthropic non-streaming, response is a dict
                    usage_data = self.anthropic_provider.extract_usage_from_response(response)
                    return await self._handle_anthropic_non_streaming_response(
                        response=response,
                        usage_data=usage_data,
                        api_key=api_key,
                        account=account,
                        request_data=request_data,
                        endpoint=endpoint,
                        client_ip=client_ip,
                        processing_time_ms=(time.time() - start_time) * 1000,
                    )
            else:
                # Use LiteLLM for other providers
                response = await self.litellm_client.completion(
                    provider=provider, request_data=request_data, stream=is_streaming
                )

                if is_streaming:
                    # Handle streaming response
                    return await self.streaming_handler.handle_stream(
                        stream_generator=response,
                        api_key=api_key,
                        account=account,
                        request_data=request_data,
                        endpoint=endpoint,
                        client_ip=client_ip,
                    )
                else:
                    # Handle non-streaming response
                    logger.debug(
                        f"#response_debug router: non-streaming response: {response}"
                    )
                    return await self._handle_non_streaming_response(
                        response=response,
                        api_key=api_key,
                        account=account,
                        request_data=request_data,
                        endpoint=endpoint,
                        client_ip=client_ip,
                        processing_time_ms=(time.time() - start_time) * 1000,
                    )

        except Exception as e:
            logger.error(f"Error in proxy routing: {e}")

            # Log the failed request for audit purposes
            try:
                await self.billing_manager.log_failed_request(
                    api_key=api_key,
                    account=account,
                    request_data=request_data,
                    endpoint=endpoint,
                    error_message=str(e),
                    client_ip=client_ip,
                    processing_time_ms=(time.time() - start_time) * 1000,
                )
            except Exception as log_error:
                logger.error(f"Failed to log error request: {log_error}")

            # Return error response based on exception type
            if "rate_limit" in str(e).lower():
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "message": "Rate limit exceeded",
                            "type": "rate_limit_exceeded",
                        }
                    },
                )
            elif "invalid" in str(e).lower() and "key" in str(e).lower():
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": {
                            "message": "Invalid API key provided to upstream service",
                            "type": "invalid_request_error",
                        }
                    },
                )
            else:
                return JSONResponse(
                    status_code=500,
                    content={
                        "error": {
                            "message": "Internal server error",
                            "type": "internal_error",
                        }
                    },
                )

    async def _handle_non_streaming_response(
        self,
        response,
        api_key: ApiKey,
        account: Account,
        request_data: Dict[str, Any],
        endpoint: str,
        client_ip: str = None,
        processing_time_ms: float = 0,
    ) -> JSONResponse:
        """Handle non-streaming response with billing"""

        try:
            # Extract usage information
            usage_data = self.litellm_client.extract_usage_from_response(response)

            # Convert response to dictionary for JSON serialization
            if hasattr(response, "model_dump"):
                response_dict = response.model_dump()
            elif hasattr(response, "dict"):
                response_dict = response.dict()
            else:
                response_dict = dict(response)

            # Process billing
            await self.billing_manager.process_usage_and_bill(
                api_key=api_key,
                account=account,
                model_name=request_data.get("model", "unknown"),
                usage_data=usage_data,
                request_endpoint=endpoint,
                request_payload=request_data,
                response_payload=response_dict,
                client_ip=client_ip,
                processing_time_ms=processing_time_ms,
            )

            logger.info(
                f"Request processed for user {account.user_id}: "
                f"model {request_data.get('model')}, "
                f"{usage_data['total_tokens']} tokens"
            )

            return JSONResponse(content=response_dict)

        except Exception as e:
            logger.error(f"Error handling non-streaming response: {e}")
            # Still return the response even if billing failed
            if hasattr(response, "model_dump"):
                response_dict = response.model_dump()
            elif hasattr(response, "dict"):
                response_dict = response.dict()
            else:
                response_dict = dict(response)

            return JSONResponse(content=response_dict)

    async def _handle_anthropic_non_streaming_response(
        self,
        response: Dict[str, Any],
        usage_data: Any,
        api_key: ApiKey,
        account: Account,
        request_data: Dict[str, Any],
        endpoint: str,
        client_ip: str = None,
        processing_time_ms: float = 0,
    ) -> JSONResponse:
        """Handle Anthropic non-streaming response with billing"""

        try:
            # Convert usage_data to dict for billing
            if hasattr(usage_data, '__dict__'):
                usage_dict = usage_data.__dict__
            else:
                usage_dict = {
                    "input_tokens": getattr(usage_data, 'input_tokens', 0),
                    "output_tokens": getattr(usage_data, 'output_tokens', 0),
                    "cached_tokens": getattr(usage_data, 'cached_tokens', 0),
                    "cache_creation_tokens": getattr(usage_data, 'cache_creation_tokens', 0),
                    "total_tokens": getattr(usage_data, 'total_tokens', 0),
                    "is_cache_hit": False,
                }

            # Process billing
            await self.billing_manager.process_usage_and_bill(
                api_key=api_key,
                account=account,
                model_name=request_data.get("model", "unknown"),
                usage_data=usage_dict,
                request_endpoint=endpoint,
                request_payload=request_data,
                response_payload=response,
                client_ip=client_ip,
                processing_time_ms=processing_time_ms,
            )

            logger.info(
                f"Anthropic request processed for user {account.user_id}: "
                f"model {request_data.get('model')}, "
                f"{usage_dict['total_tokens']} tokens"
            )

            return JSONResponse(content=response)

        except Exception as e:
            logger.error(f"Error handling Anthropic non-streaming response: {e}")
            return JSONResponse(content=response)

    async def _handle_anthropic_streaming_response(
        self,
        stream_generator,
        usage_data: Any,
        complete_message: Dict[str, Any],
        api_key: ApiKey,
        account: Account,
        request_data: Dict[str, Any],
        endpoint: str,
        client_ip: str = None,
        processing_time_ms: float = 0,
    ) -> StreamingResponse:
        """Handle Anthropic streaming response with billing"""

        async def billing_wrapper():
            # Stream all events
            async for chunk in stream_generator:
                yield chunk

            # After streaming completes, process billing
            try:
                # Convert usage_data to dict for billing
                if hasattr(usage_data, '__dict__'):
                    usage_dict = usage_data.__dict__
                else:
                    usage_dict = {
                        "input_tokens": getattr(usage_data, 'input_tokens', 0),
                        "output_tokens": getattr(usage_data, 'output_tokens', 0),
                        "cached_tokens": getattr(usage_data, 'cached_tokens', 0),
                        "cache_creation_tokens": getattr(usage_data, 'cache_creation_tokens', 0),
                        "total_tokens": getattr(usage_data, 'total_tokens', 0),
                        "is_cache_hit": False,
                    }

                await self.billing_manager.process_usage_and_bill(
                    api_key=api_key,
                    account=account,
                    model_name=request_data.get("model", "unknown"),
                    usage_data=usage_dict,
                    request_endpoint=endpoint,
                    request_payload=request_data,
                    response_payload=complete_message,
                    client_ip=client_ip,
                    processing_time_ms=processing_time_ms,
                )

                logger.info(
                    f"Anthropic streaming request processed for user {account.user_id}: "
                    f"model {request_data.get('model')}, "
                    f"{usage_dict['total_tokens']} tokens"
                )

            except Exception as e:
                logger.error(f"Error in Anthropic streaming billing: {e}")

        return StreamingResponse(
            billing_wrapper(),
            media_type="text/plain",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )

    async def count_tokens(
        self,
        request_data: Dict[str, Any],
        api_key: ApiKey,
        account: Account,
    ) -> JSONResponse:
        """
        Count tokens for a request without creating a message
        """
        try:
            # Extract model name from request
            model_name = request_data.get("model")
            if not model_name:
                return JSONResponse(
                    status_code=400, content={"error": "Model name is required"}
                )

            # Determine if this is an Anthropic model
            if any(provider in model_name.lower() for provider in ["claude", "anthropic"]):
                # Use Anthropic provider for token counting
                response = await self.anthropic_provider.count_tokens(request_data)
                return JSONResponse(content=response)
            else:
                # For non-Anthropic models, return an error for now
                # In the future, could add support for other providers
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "Token counting only supported for Anthropic models currently"
                    }
                )

        except Exception as e:
            logger.error(f"Error in token counting: {e}")
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "message": "Internal server error",
                        "type": "internal_error",
                    }
                },
            )
