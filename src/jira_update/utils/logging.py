"""
Logging configuration for JIRA Update Hook.
"""

import os
import logging
import logging.handlers
from typing import Optional

from .config import get_config


def setup_logging(log_level: Optional[str] = None, log_file: Optional[str] = None) -> None:
    """
    Set up logging for the application.
    
    Args:
        log_level: Log level (debug, info, warning, error). If None, uses the value from config.
        log_file: Path to log file. If None, uses the value from config.
    """
    config = get_config()
    
    # Get log level from config if not provided
    if log_level is None:
        log_level = config.get('advanced', 'log_level', 'info')
    
    # Convert string log level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Get log file from config if not provided
    if log_file is None:
        log_file = config.get('advanced', 'log_file', 'jira_update.log')
    
    # Create log directory if it doesn't exist
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_formatter = logging.Formatter(
        '%(levelname)s: %(message)s'
    )
    
    # Set up file handler
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10*1024*1024, backupCount=5
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Set up console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # Log initial message
    logging.info(f"Logging initialized at level {log_level.upper()}") 