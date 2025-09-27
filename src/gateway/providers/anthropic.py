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

                    current_event_lines = []

                    while True:
                        try:
                            line_bytes = await response.content.readline()
                            if not line_bytes:
                                break

                            line = line_bytes.decode('utf-8').rstrip('\r\n')

                            if not line:
                                # Empty line indicates end of SSE event
                                if current_event_lines:
                                    # Forward the complete event as-is
                                    event_text = '\n'.join(current_event_lines) + '\n\n'
                                    yield event_text

                                    # Process data line for internal tracking
                                    data_line = None
                                    for event_line in current_event_lines:
                                        if event_line.startswith('data: '):
                                            data_line = event_line
                                            break

                                    if data_line:
                                        if data_line == 'data: [DONE]':
                                            return

                                        try:
                                            event_data = json.loads(data_line[6:])  # Remove 'data: ' prefix
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

                                                # Extract initial usage from message_start if present
                                                initial_usage = message.get('usage', {})
                                                if initial_usage:
                                                    accumulated_usage.input_tokens = initial_usage.get('input_tokens', 0)
                                                    accumulated_usage.output_tokens = initial_usage.get('output_tokens', 0)
                                                    accumulated_usage.cached_tokens = initial_usage.get('cache_read_input_tokens', 0)
                                                    accumulated_usage.cache_creation_tokens = initial_usage.get('cache_creation_input_tokens', 0)

                                            elif event_type == 'content_block_start':
                                                content_block = event_data.get('content_block', {})
                                                block_type = content_block.get('type', 'text')

                                                if block_type == 'text':
                                                    current_content_block = {
                                                        'type': 'text',
                                                        'text': ''
                                                    }
                                                elif block_type == 'tool_use':
                                                    current_content_block = {
                                                        'type': 'tool_use',
                                                        'id': content_block.get('id', ''),
                                                        'name': content_block.get('name', ''),
                                                        'input': {}
                                                    }
                                                else:
                                                    # Handle other content block types
                                                    current_content_block = dict(content_block)

                                                complete_message['content'].append(current_content_block)

                                            elif event_type == 'content_block_delta':
                                                if current_content_block and 'delta' in event_data:
                                                    delta = event_data['delta']
                                                    delta_type = delta.get('type')

                                                    if delta_type == 'text_delta' and 'text' in delta:
                                                        current_content_block['text'] += delta['text']
                                                    elif delta_type == 'input_json_delta' and 'partial_json' in delta:
                                                        # Handle tool use input JSON delta
                                                        if 'input' not in current_content_block:
                                                            current_content_block['input'] = {}
                                                        # Note: For complete JSON reconstruction, need proper JSON streaming parser
                                                        # For now, just track that we received input delta
                                                        pass
                                                    elif delta_type == 'thinking_delta' and 'text' in delta:
                                                        # Handle thinking/reasoning delta
                                                        if 'thinking' not in current_content_block:
                                                            current_content_block['thinking'] = ''
                                                        current_content_block['thinking'] += delta['text']

                                            elif event_type == 'content_block_stop':
                                                current_content_block = None

                                            elif event_type == 'message_delta':
                                                delta = event_data.get('delta', {})
                                                if 'stop_reason' in delta:
                                                    complete_message['stop_reason'] = delta['stop_reason']
                                                if 'stop_sequence' in delta:
                                                    complete_message['stop_sequence'] = delta['stop_sequence']

                                                # Extract usage data from message_delta (cumulative)
                                                usage = event_data.get('usage', {})
                                                if usage:
                                                    # Update accumulated usage (handle multiple message_delta events)
                                                    accumulated_usage.input_tokens = usage.get('input_tokens', accumulated_usage.input_tokens)
                                                    accumulated_usage.output_tokens = usage.get('output_tokens', accumulated_usage.output_tokens)
                                                    accumulated_usage.cached_tokens = usage.get('cache_read_input_tokens', accumulated_usage.cached_tokens)
                                                    accumulated_usage.cache_creation_tokens = usage.get('cache_creation_input_tokens', accumulated_usage.cache_creation_tokens)
                                                    complete_message['usage'] = usage

                                            elif event_type == 'message_stop':
                                                # Final event, stream is complete
                                                pass

                                            elif event_type == 'ping':
                                                # Heartbeat event, no processing needed
                                                pass

                                            elif event_type == 'error':
                                                # Error event
                                                error_info = event_data.get('error', {})
                                                logger.error(f"Anthropic streaming error: {error_info}")

                                            else:
                                                # Unknown event type - log for debugging
                                                logger.warning(f"Unknown event type: {event_type}")

                                        except json.JSONDecodeError as e:
                                            logger.warning(f"Failed to parse streaming event: {e}")

                                    current_event_lines = []
                                continue

                            # Accumulate lines for current event
                            current_event_lines.append(line)

                        except Exception as e:
                            logger.error(f"Error reading SSE stream: {e}")
                            break

                    # Handle any remaining event
                    if current_event_lines:
                        event_text = '\n'.join(current_event_lines) + '\n\n'
                        yield event_text

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
