#!/usr/bin/env python3
"""
Demo script to showcase the cost calculation functionality
"""
import asyncio
import sys
import os

# Add the src directory to the path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from gateway.database.connection import db_manager
from gateway.utils.cost_calculator import CostCalculator
from gateway.utils.pricing_loader import PricingLoader


async def demo_cost_calculation():
    """Demonstrate cost calculation for different scenarios"""
    
    # Initialize database connection
    await db_manager.connect()
    
    # Make sure pricing data is loaded
    await PricingLoader.initialize_pricing_database()
    
    print("🧮 Cost Calculation Demo")
    print("=" * 50)
    
    # Test scenarios
    scenarios = [
        {
            "model": "claude-3-5-sonnet-20241022",
            "input_tokens": 1000,
            "output_tokens": 500,
            "cache_write_tokens": 0,
            "cache_read_tokens": 0,
            "description": "Standard Claude 3.5 Sonnet request"
        },
        {
            "model": "claude-3-5-sonnet-20241022",
            "input_tokens": 1000,
            "output_tokens": 500,
            "cache_write_tokens": 2000,
            "cache_read_tokens": 0,
            "description": "Claude 3.5 Sonnet with cache write"
        },
        {
            "model": "claude-3-5-sonnet-20241022",
            "input_tokens": 1000,
            "output_tokens": 500,
            "cache_write_tokens": 0,
            "cache_read_tokens": 1500,
            "description": "Claude 3.5 Sonnet with cache read"
        },
        {
            "model": "gpt-4o",
            "input_tokens": 1000,
            "output_tokens": 500,
            "cache_write_tokens": 0,
            "cache_read_tokens": 0,
            "description": "Standard GPT-4o request"
        },
        {
            "model": "gemini-1.5-pro",
            "input_tokens": 1000,
            "output_tokens": 500,
            "cache_write_tokens": 0,
            "cache_read_tokens": 1000,
            "description": "Gemini Pro with cache read"
        }
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{i}. {scenario['description']}")
        print(f"   Model: {scenario['model']}")
        print(f"   Input tokens: {scenario['input_tokens']:,}")
        print(f"   Output tokens: {scenario['output_tokens']:,}")
        
        if scenario['cache_write_tokens'] > 0:
            print(f"   Cache write tokens: {scenario['cache_write_tokens']:,}")
        if scenario['cache_read_tokens'] > 0:
            print(f"   Cache read tokens: {scenario['cache_read_tokens']:,}")
        
        try:
            cost = await CostCalculator.calculate_cost(
                model_name=scenario['model'],
                input_tokens=scenario['input_tokens'],
                output_tokens=scenario['output_tokens'],
                cache_write_tokens=scenario['cache_write_tokens'],
                cache_read_tokens=scenario['cache_read_tokens']
            )
            print(f"   💰 Total cost: ${cost:.6f}")
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    # Clean up
    await db_manager.disconnect()


if __name__ == "__main__":
    asyncio.run(demo_cost_calculation())