#!/usr/bin/env python3
"""
LiteLLM Gateway - Main Entry Point

High-performance LLM API Gateway with cost tracking and budget management.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from gateway.app import app
from gateway.utils.config import settings

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        reload=False
    )