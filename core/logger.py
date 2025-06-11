#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Centralized Logging Configuration for Jarvis Assistant

This module provides a unified logging interface using loguru for the entire application.
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from loguru import logger
import speech_recognition as sr

# Default log format
DEFAULT_FORMAT = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"

# Log levels
LOG_LEVELS = {
    "TRACE": 5,
    "DEBUG": 10,
    "INFO": 20,
    "SUCCESS": 25,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50
}

def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    rotation: str = "1 day",
    retention: str = "1 week",
    compression: str = "zip",
    format_string: str = DEFAULT_FORMAT,
    config: Optional[Dict[str, Any]] = None
) -> None:
    """
    Set up logging configuration for the application.
    
    Args:
        log_level: Minimum log level to display
        log_file: Path to log file (if None, logs only to console)
        rotation: When to rotate log files
        retention: How long to keep log files
        compression: Compression format for rotated logs
        format_string: Log message format
        config: Additional configuration options
    """
    # Remove default logger
    logger.remove()
    
    # Add console handler
    logger.add(
        sys.stderr,
        format=format_string,
        level=log_level,
        colorize=True
    )
    
    # Add file handler if log_file is specified
    if log_file:
        # Create logs directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.add(
            log_file,
            format=format_string,
            level=log_level,
            rotation=rotation,
            retention=retention,
            compression=compression,
            enqueue=True  # Thread-safe logging
        )
    
    # Add additional handlers from config if provided
    if config and "handlers" in config:
        for handler_config in config["handlers"]:
            logger.add(**handler_config)
    
    logger.info(f"Logging initialized with level: {log_level}")

def get_logger(name: str) -> logger:
    """
    Get a logger instance for a specific module.
    
    Args:
        name: Name of the module/logger
        
    Returns:
        Logger instance
    """
    return logger.bind(name=name)

# Initialize default logging
setup_logging()

print(sr.Microphone.list_microphone_names())