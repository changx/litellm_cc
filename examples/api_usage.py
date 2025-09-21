#!/usr/bin/env python3
"""
Example usage of the Direct LLM Gateway APIs

This shows how to use both OpenAI endpoints:
1. /v1/chat/completions - Standard chat completions
2. /v1/responses - OpenAI responses API

Both endpoints support the same request format and return compatible responses.
"""

import asyncio
import httpx
import json


# Example configuration
GATEWAY_BASE_URL = "http://localhost:8000"
API_KEY = "your-api-key-here"


async def example_chat_completions():
    """Example using /v1/chat/completions endpoint"""
    
    print("=== Chat Completions API Example ===")
    
    request_data = {
        "model": "gpt-4",
        "messages": [
            {"role": "user", "content": "Hello! How are you today?"}
        ],
        "max_tokens": 100,
        "temperature": 0.7
    }
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{GATEWAY_BASE_URL}/v1/chat/completions",
                headers=headers,
                json=request_data,
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Success!")
                print(f"Model: {result['model']}")
                print(f"Response: {result['choices'][0]['message']['content']}")
                print(f"Usage: {result['usage']}")
            else:
                print(f"❌ Error: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"❌ Request failed: {e}")


async def example_responses_api():
    """Example using /v1/responses endpoint"""
    
    print("\n=== Responses API Example ===")
    
    request_data = {
        "model": "gpt-4",
        "messages": [
            {"role": "user", "content": "What's the weather like today?"}
        ],
        "max_tokens": 100,
        "temperature": 0.7
    }
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{GATEWAY_BASE_URL}/v1/responses",
                headers=headers,
                json=request_data,
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Success!")
                print(f"Model: {result['model']}")
                print(f"Response: {result['choices'][0]['message']['content']}")
                print(f"Usage: {result['usage']}")
            else:
                print(f"❌ Error: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"❌ Request failed: {e}")


async def example_anthropic_format():
    """Example using Anthropic format endpoint"""
    
    print("\n=== Anthropic Messages API Example ===")
    
    request_data = {
        "model": "claude-3-sonnet",
        "max_tokens": 100,
        "messages": [
            {"role": "user", "content": "Hello Claude! How can you help me today?"}
        ]
    }
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{GATEWAY_BASE_URL}/v1/messages",
                headers=headers,
                json=request_data,
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Success!")
                print(f"Model: {result['model']}")
                print(f"Response: {result['content'][0]['text']}")
                print(f"Usage: {result['usage']}")
            else:
                print(f"❌ Error: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"❌ Request failed: {e}")


async def main():
    """Run all examples"""
    print("Direct LLM Gateway API Usage Examples")
    print("=" * 50)
    print("\nNote: This is a demonstration script.")
    print("Make sure to:")
    print("1. Start the gateway server: uv run python main.py")
    print("2. Configure your API keys in environment variables")
    print("3. Update GATEWAY_BASE_URL and API_KEY variables above")
    print("\n" + "=" * 50)
    
    # These examples will fail without proper configuration,
    # but they show the correct usage patterns
    await example_chat_completions()
    await example_responses_api()
    await example_anthropic_format()
    
    print("\n" + "=" * 50)
    print("🎉 Examples complete!")
    print("\nKey Features Demonstrated:")
    print("- ✅ OpenAI Chat Completions API compatibility")
    print("- ✅ OpenAI Responses API compatibility")
    print("- ✅ Anthropic Messages API compatibility")
    print("- ✅ Automatic provider routing based on model name")
    print("- ✅ Unified authentication and response handling")


if __name__ == "__main__":
    asyncio.run(main())