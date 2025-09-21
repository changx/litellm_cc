#!/usr/bin/env python3
"""
Management script to initialize pricing database with data from pricing.json
"""
import asyncio
import sys
import os

# Add the src directory to the path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from gateway.database.connection import db_manager
from gateway.utils.pricing_loader import PricingLoader


async def main():
    """Initialize pricing database with data from pricing.json"""
    try:
        # Initialize database connection
        await db_manager.connect()
        print("Connected to database")
        
        # Load and initialize pricing data
        print("Loading pricing configuration...")
        await PricingLoader.initialize_pricing_database()
        print("✅ Pricing database initialized successfully")
        
        # List supported models
        print("\n📋 Supported models by provider:")
        supported_models = PricingLoader.list_supported_models()
        for provider, models in supported_models.items():
            print(f"  {provider}: {len(models)} models")
            for model in models[:3]:  # Show first 3 models
                print(f"    - {model}")
            if len(models) > 3:
                print(f"    ... and {len(models) - 3} more")
        
    except Exception as e:
        print(f"❌ Error initializing pricing database: {e}")
        return 1
    finally:
        # Clean up database connection
        await db_manager.disconnect()
        print("\nDatabase connection closed")
    
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))