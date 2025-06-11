#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Logger Utility for Jarvis Assistant

This module provides logging functionality for the Jarvis assistant.
"""

import os
import logging
from logging.handlers import RotatingFileHandler
import sys
from datetime import datetime


def setup_logger(level=logging.INFO, log_to_file=True, log_dir="logs"):
    """Set up the logger for the Jarvis assistant
    
    Args:
        level: The logging level (default: INFO)
        log_to_file: Whether to log to a file (default: True)
        log_dir: Directory to store log files (default: "logs")
        
    Returns:
        The configured logger
    """
    # Create logger
    logger = logging.getLogger("jarvis")
    logger.setLevel(level)
    
    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Create file handler if enabled
    if log_to_file:
        # Create log directory if it doesn't exist
        os.makedirs(log_dir, exist_ok=True)
        
        # Create log file with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"jarvis_{timestamp}.log")
        
        # Set up rotating file handler (10 MB max size, keep 5 backup files)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # Prevent logging from propagating to the root logger
    logger.propagate = False
    
    logger.info(f"Logger initialized with level: {logging.getLevelName(level)}")
    if log_to_file:
        logger.info(f"Logging to file: {log_file}")
    
    return logger


def get_logger(name):
    """Get a logger with the specified name
    
    Args:
        name: The name for the logger
        
    Returns:
        A logger instance
    """
    return logging.getLogger(f"jarvis.{name}")