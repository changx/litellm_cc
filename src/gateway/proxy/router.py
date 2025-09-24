"""
Main proxy router for handling LLM requests
"""
import time
import logging
from typing import Dict, Any, Tuple
from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse
from gateway.models import Account, ApiKey
from gateway.auth.dependencies import require_model_access
from gateway.billing import BillingManager
from .litellm_client import LiteLLMClient, Provider
from .streaming import StreamingResponseHandler

logger = logging.getLogger(__name__)


class ProxyRouter:
    """Main proxy router for LLM API requests"""

    def __init__(self):
        self.litellm_client = LiteLLMClient()
        self.billing_manager = BillingManager()
        self.streaming_handler = StreamingResponseHandler(self.billing_manager)

    async def route_request(
        self,
        request: Request,
        api_key: ApiKey,
        account: Account,
        request_data: Dict[str, Any],
        endpoint: str
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
                    status_code=400,
                    content={"error": "Model name is required"}
                )

            # Check model access permissions
            require_model_access(api_key, model_name)

            # Check if this is a streaming request
            is_streaming = request_data.get("stream", False)

            # Execute the request through LiteLLM
            response = await self.litellm_client.completion(
                provider=provider,
                request_data=request_data,
                stream=is_streaming
            )

            if is_streaming:
                # Handle streaming response
                return await self.streaming_handler.handle_stream(
                    stream_generator=response,
                    api_key=api_key,
                    account=account,
                    request_data=request_data,
                    endpoint=endpoint,
                    client_ip=client_ip
                )
            else:
                # Handle non-streaming response
                return await self._handle_non_streaming_response(
                    response=response,
                    api_key=api_key,
                    account=account,
                    request_data=request_data,
                    endpoint=endpoint,
                    client_ip=client_ip,
                    processing_time_ms=(time.time() - start_time) * 1000
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
                    processing_time_ms=(time.time() - start_time) * 1000
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
                            "type": "rate_limit_exceeded"
                        }
                    }
                )
            elif "invalid" in str(e).lower() and "key" in str(e).lower():
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": {
                            "message": "Invalid API key provided to upstream service",
                            "type": "invalid_request_error"
                        }
                    }
                )
            else:
                return JSONResponse(
                    status_code=500,
                    content={
                        "error": {
                            "message": "Internal server error",
                            "type": "internal_error"
                        }
                    }
                )

    async def _handle_non_streaming_response(
        self,
        response,
        api_key: ApiKey,
        account: Account,
        request_data: Dict[str, Any],
        endpoint: str,
        client_ip: str = None,
        processing_time_ms: float = 0
    ) -> JSONResponse:
        """Handle non-streaming response with billing"""

        try:
            # Extract usage information
            usage_data = self.litellm_client.extract_usage_from_response(response)

            # Convert response to dictionary for JSON serialization
            if hasattr(response, 'dict'):
                response_dict = response.dict()
            elif hasattr(response, 'model_dump'):
                response_dict = response.model_dump()
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
                processing_time_ms=processing_time_ms
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
            if hasattr(response, 'dict'):
                response_dict = response.dict()
            elif hasattr(response, 'model_dump'):
                response_dict = response.model_dump()
            else:
                response_dict = dict(response)

            return JSONResponse(content=response_dict)