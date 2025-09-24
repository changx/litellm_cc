"""
Streaming response handling with proper billing
"""
import json
import logging
from typing import AsyncGenerator, Dict, Any, Optional
from fastapi import Response
from fastapi.responses import StreamingResponse
from gateway.models import Account, ApiKey
from gateway.billing import BillingManager

logger = logging.getLogger(__name__)


class StreamingResponseHandler:
    """Handle streaming responses with proper billing"""

    def __init__(self, billing_manager: BillingManager):
        self.billing_manager = billing_manager

    async def handle_stream(
        self,
        stream_generator: AsyncGenerator,
        api_key: ApiKey,
        account: Account,
        request_data: Dict[str, Any],
        endpoint: str,
        client_ip: Optional[str] = None
    ) -> StreamingResponse:
        """
        Handle streaming response with proper billing after stream completion
        """

        async def stream_with_billing():
            """Generator that yields stream chunks and handles billing at the end"""
            collected_chunks = []
            stream_wrapper = None

            try:
                # Stream the response chunks
                async for chunk in stream_generator:
                    if chunk:
                        # Store the stream wrapper reference for usage extraction
                        if hasattr(chunk, '__self__'):
                            stream_wrapper = chunk.__self__

                        # Convert chunk to string if needed
                        if hasattr(chunk, 'choices') and chunk.choices:
                            # Standard OpenAI-format streaming chunk
                            chunk_data = {
                                "id": getattr(chunk, 'id', ''),
                                "object": getattr(chunk, 'object', 'chat.completion.chunk'),
                                "created": getattr(chunk, 'created', 0),
                                "model": getattr(chunk, 'model', ''),
                                "choices": []
                            }

                            for choice in chunk.choices:
                                choice_data = {
                                    "index": getattr(choice, 'index', 0),
                                    "delta": {}
                                }

                                if hasattr(choice, 'delta'):
                                    if hasattr(choice.delta, 'content') and choice.delta.content:
                                        choice_data["delta"]["content"] = choice.delta.content
                                    if hasattr(choice.delta, 'role') and choice.delta.role:
                                        choice_data["delta"]["role"] = choice.delta.role

                                if hasattr(choice, 'finish_reason'):
                                    choice_data["finish_reason"] = choice.finish_reason

                                chunk_data["choices"].append(choice_data)

                            chunk_str = f"data: {json.dumps(chunk_data)}\n\n"
                        else:
                            # Fallback to string representation
                            chunk_str = str(chunk)

                        collected_chunks.append(chunk_str)
                        yield chunk_str

                # Signal end of stream
                yield "data: [DONE]\n\n"

            except Exception as e:
                logger.error(f"Error during streaming: {e}")
                error_chunk = {
                    "error": {
                        "message": "Streaming error occurred",
                        "type": "stream_error"
                    }
                }
                yield f"data: {json.dumps(error_chunk)}\n\n"
                raise

            finally:
                # Handle billing after stream completion
                try:
                    await self._handle_post_stream_billing(
                        stream_wrapper,
                        api_key,
                        account,
                        request_data,
                        endpoint,
                        collected_chunks,
                        client_ip
                    )
                except Exception as e:
                    logger.error(f"Error in post-stream billing: {e}")

        return StreamingResponse(
            stream_with_billing(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/plain; charset=utf-8"
            }
        )

    async def _handle_post_stream_billing(
        self,
        stream_wrapper,
        api_key: ApiKey,
        account: Account,
        request_data: Dict[str, Any],
        endpoint: str,
        collected_chunks: list,
        client_ip: Optional[str] = None
    ):
        """Handle billing after stream completion"""

        # Extract usage information from completed stream
        usage_data = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "is_cache_hit": False
        }

        if stream_wrapper:
            try:
                # Try to extract usage from the stream wrapper
                if hasattr(stream_wrapper, 'usage') and stream_wrapper.usage:
                    usage_data.update({
                        "input_tokens": getattr(stream_wrapper.usage, 'prompt_tokens', 0),
                        "output_tokens": getattr(stream_wrapper.usage, 'completion_tokens', 0),
                        "total_tokens": getattr(stream_wrapper.usage, 'total_tokens', 0)
                    })

                if hasattr(stream_wrapper, '_cache_hit'):
                    usage_data["is_cache_hit"] = stream_wrapper._cache_hit

            except Exception as e:
                logger.warning(f"Failed to extract usage from stream wrapper: {e}")

        # If we couldn't get usage data, try to estimate from the stream content
        if usage_data["total_tokens"] == 0:
            logger.warning("No usage data available from stream, attempting estimation")
            # This is a fallback - in production you might want to implement
            # more sophisticated token counting
            content = ''.join(collected_chunks)
            estimated_tokens = len(content.split()) * 1.3  # Rough estimation
            usage_data["output_tokens"] = int(estimated_tokens)
            usage_data["total_tokens"] = usage_data["input_tokens"] + usage_data["output_tokens"]

        # Process billing
        await self.billing_manager.process_usage_and_bill(
            api_key=api_key,
            account=account,
            model_name=request_data.get("model", "unknown"),
            usage_data=usage_data,
            request_endpoint=endpoint,
            request_payload=request_data,
            response_payload={"streaming": True, "chunks": len(collected_chunks)},
            client_ip=client_ip
        )

        logger.info(
            f"Stream billing processed for user {account.user_id}: "
            f"{usage_data['total_tokens']} tokens, ${usage_data.get('cost', 0):.4f}"
        )