import asyncio
import json
import logging
import os
from typing import Any, AsyncGenerator, Dict, Tuple, Union

import aiohttp

from gateway.models.usage_log import UsageData

from .base import BaseProvider

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseProvider):
    def __init__(self):
        base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
        api_key = os.getenv("ANTHROPIC_API_KEY")
        super().__init__(base_url=base_url, api_key=api_key)

    async def forward_messages(
        self, request_data: Dict[str, Any], stream: bool = False
    ) -> Union[Dict[str, Any], Tuple[AsyncGenerator[str, None], UsageData, Dict[str, Any]]]:
        """
        Forward request to Anthropic Messages API

        Returns:
            For non-streaming: Dict containing the response
            For streaming: Tuple of (stream_generator, usage_data, complete_message)
        """
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }

        url = f"{self.base_url}/v1/messages"

        # Set stream parameter
        payload = {**request_data, "stream": stream}

        if stream:
            return await self._handle_streaming_request(url, headers, payload)
        else:
            return await self._handle_non_streaming_request(url, headers, payload)

    async def _handle_non_streaming_request(
        self, url: str, headers: Dict[str, str], payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle non-streaming request"""
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Anthropic API error ({response.status}): {error_text}")

                response_data = await response.json()
                return response_data

    async def _handle_streaming_request(
        self, url: str, headers: Dict[str, str], payload: Dict[str, Any]
    ) -> Tuple[AsyncGenerator[str, None], UsageData, Dict[str, Any]]:
        """Handle streaming request and extract usage data"""

        # Variables to accumulate streaming data
        accumulated_usage = UsageData(
            input_tokens=0,
            output_tokens=0,
            cached_tokens=0,
            cache_creation_tokens=0
        )
        complete_message = {
            "id": "",
            "type": "message",
            "role": "assistant",
            "content": [],
            "model": payload.get("model", ""),
            "stop_reason": None,
            "stop_sequence": None,
            "usage": {}
        }

        async def stream_generator():
            nonlocal accumulated_usage, complete_message

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Anthropic API error ({response.status}): {error_text}")

                    current_content_block = None

                    async for line in response.content:
                        line = line.decode('utf-8').strip()

                        if not line or not line.startswith('data: '):
                            continue

                        if line == 'data: [DONE]':
                            yield line + '\n\n'
                            break

                        try:
                            event_data = json.loads(line[6:])  # Remove 'data: ' prefix
                            event_type = event_data.get('type')

                            # Process different event types
                            if event_type == 'message_start':
                                message = event_data.get('message', {})
                                complete_message.update({
                                    'id': message.get('id', ''),
                                    'model': message.get('model', ''),
                                    'role': message.get('role', 'assistant'),
                                    'content': message.get('content', []),
                                    'stop_reason': message.get('stop_reason'),
                                    'stop_sequence': message.get('stop_sequence'),
                                    'usage': message.get('usage', {})
                                })

                            elif event_type == 'content_block_start':
                                content_block = event_data.get('content_block', {})
                                current_content_block = {
                                    'type': content_block.get('type', 'text'),
                                    'text': '' if content_block.get('type') == 'text' else content_block
                                }
                                complete_message['content'].append(current_content_block)

                            elif event_type == 'content_block_delta':
                                if current_content_block and 'delta' in event_data:
                                    delta = event_data['delta']
                                    if delta.get('type') == 'text_delta' and 'text' in delta:
                                        current_content_block['text'] += delta['text']

                            elif event_type == 'content_block_stop':
                                current_content_block = None

                            elif event_type == 'message_delta':
                                delta = event_data.get('delta', {})
                                if 'stop_reason' in delta:
                                    complete_message['stop_reason'] = delta['stop_reason']
                                if 'stop_sequence' in delta:
                                    complete_message['stop_sequence'] = delta['stop_sequence']

                                # Extract usage data from message_delta
                                usage = event_data.get('usage', {})
                                if usage:
                                    accumulated_usage = UsageData(
                                        input_tokens=usage.get('input_tokens', 0),
                                        output_tokens=usage.get('output_tokens', 0),
                                        cached_tokens=usage.get('cache_read_input_tokens', 0),
                                        cache_creation_tokens=usage.get('cache_creation_input_tokens', 0)
                                    )
                                    complete_message['usage'] = usage

                            elif event_type == 'message_stop':
                                # Final event, stream is complete
                                pass

                            # Yield the event as SSE format
                            yield line + '\n\n'

                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to parse streaming event: {e}")
                            continue

                    # Yield final [DONE] event
                    yield 'data: [DONE]\n\n'

        return stream_generator(), accumulated_usage, complete_message

    def extract_usage_from_response(self, response: Dict[str, Any]) -> UsageData:
        """Extract usage data from non-streaming response"""
        usage = response.get('usage', {})

        return UsageData(
            input_tokens=usage.get('input_tokens', 0),
            output_tokens=usage.get('output_tokens', 0),
            cached_tokens=usage.get('cache_read_input_tokens', 0),
            cache_creation_tokens=usage.get('cache_creation_input_tokens', 0),
        )

    async def count_tokens(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Count tokens for a messages request without creating a message

        Args:
            request_data: The request payload containing model, messages, etc.

        Returns:
            Dict containing input_tokens count
        """
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }

        url = f"{self.base_url}/v1/messages/count_tokens"

        # Create payload for token counting
        payload = dict(request_data)
        # Ensure stream is False for token counting
        payload["stream"] = False

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Anthropic API error ({response.status}): {error_text}")

                response_data = await response.json()
                return response_data
