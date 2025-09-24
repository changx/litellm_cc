"""
Logging configuration utilities
"""
import logging
import sys
from typing import Dict, Any


def setup_logging(level: str = "INFO") -> None:
    """Configure application logging"""

    # Create formatters
    detailed_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
    )

    simple_formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s"
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    root_logger.addHandler(console_handler)

    # Set specific logger levels
    logger_configs = {
        "uvicorn": logging.WARNING,
        "uvicorn.access": logging.WARNING,
        "fastapi": logging.INFO,
        "motor": logging.WARNING,
        "litellm": logging.WARNING,
        "gateway": getattr(logging, level.upper())
    }

    for logger_name, logger_level in logger_configs.items():
        logger = logging.getLogger(logger_name)
        logger.setLevel(logger_level)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance"""
    return logging.getLogger(name)