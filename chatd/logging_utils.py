"""
Logging utilities for the chatd-internships bot.

This module sets up and manages logging for the application,
including dynamic log level adjustment.
"""

import logging
import os
import signal
from logging import Logger
from logging.handlers import RotatingFileHandler
from typing import Dict, Optional

# Define log levels and their string representations
LOG_LEVELS: Dict[str, int] = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL,
}

# Root logger name
LOGGER_NAME = 'chatd-internships'

# Default log file settings
DEFAULT_LOG_FILE = 'chatd.log'
DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10MB
DEFAULT_BACKUP_COUNT = 5

# Global logger instance
logger: Optional[Logger] = None


def setup_logging(log_level: str = 'INFO', log_file: Optional[str] = None, 
                 max_bytes: int = DEFAULT_MAX_BYTES, 
                 backup_count: int = DEFAULT_BACKUP_COUNT) -> Logger:
    """
    Set up logging with the specified log level and optional file rotation.
    
    Args:
        log_level: The log level to use (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file for file logging with rotation
        max_bytes: Maximum size of log file before rotation (default: 10MB)
        backup_count: Number of backup log files to keep (default: 5)
        
    Returns:
        Logger: The configured logger instance
    """
    global logger
    
    # Normalize log level
    log_level = log_level.upper()
    if log_level not in LOG_LEVELS:
        log_level = 'INFO'
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVELS[log_level])
    
    # Remove any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create formatter
    formatter = logging.Formatter('[%(asctime)s] [%(levelname)-7s] %(name)s: %(message)s')
    
    # Always add console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Add file handler if log file is specified
    if log_file:
        try:
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count
            )
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            # If file handler setup fails, log to console
            console_handler.setLevel(logging.WARNING)
            root_logger.warning(f"Failed to set up file logging to {log_file}: {e}")
    
    # Get or create the logger
    logger = logging.getLogger(LOGGER_NAME)
    
    # Log the setup
    logger.info(f"Logging configured with level: {log_level}")
    if log_file:
        logger.info(f"Log file: {log_file} (max size: {max_bytes/1024/1024:.1f}MB, backups: {backup_count})")
    
    return logger


def get_logger() -> Logger:
    """
    Get the configured logger instance.
    
    Returns:
        Logger: The logger instance
    """
    global logger
    if logger is None:
        # Get log level from environment
        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        
        # Get log file settings from environment
        log_file = os.getenv('LOG_FILE', DEFAULT_LOG_FILE)
        max_bytes = int(os.getenv('LOG_MAX_BYTES', str(DEFAULT_MAX_BYTES)))
        backup_count = int(os.getenv('LOG_BACKUP_COUNT', str(DEFAULT_BACKUP_COUNT)))
        
        logger = setup_logging(log_level, log_file, max_bytes, backup_count)
    return logger


def change_log_level(level: str) -> bool:
    """
    Change the log level at runtime.
    
    Args:
        level: The new log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        
    Returns:
        bool: True if successful, False otherwise
    """
    global logger
    
    # Normalize level
    level = level.upper()
    
    # Validate level
    if level not in LOG_LEVELS:
        if logger:
            logger.error(f"Invalid log level: {level}")
        return False
    
    # Set new level for our logger
    if logger:
        logger.setLevel(LOG_LEVELS[level])
        logger.info(f"Log level changed to: {level}")
    
    # Update root logger too
    logging.getLogger().setLevel(LOG_LEVELS[level])
    
    return True


def setup_signal_handlers():
    """
    Set up signal handlers for changing log levels.
    
    SIGUSR1: Increase log verbosity (e.g., INFO -> DEBUG)
    SIGUSR2: Decrease log verbosity (e.g., DEBUG -> INFO)
    """
    def increase_verbosity(sig, frame):
        """Increase log verbosity on SIGUSR1."""
        global logger
        if not logger:
            return
            
        current_level = logger.getEffectiveLevel()
        levels = list(LOG_LEVELS.values())
        levels.sort()  # Sort from least to most verbose
        
        # Find the next more verbose level
        for level in reversed(levels):
            if level < current_level:
                level_name = next(k for k, v in LOG_LEVELS.items() if v == level)
                change_log_level(level_name)
                break
    
    def decrease_verbosity(sig, frame):
        """Decrease log verbosity on SIGUSR2."""
        global logger
        if not logger:
            return
            
        current_level = logger.getEffectiveLevel()
        levels = list(LOG_LEVELS.values())
        levels.sort()  # Sort from least to most verbose
        
        # Find the next less verbose level
        for level in levels:
            if level > current_level:
                level_name = next(k for k, v in LOG_LEVELS.items() if v == level)
                change_log_level(level_name)
                break
    
    # Register signal handlers
    signal.signal(signal.SIGUSR1, increase_verbosity)
    signal.signal(signal.SIGUSR2, decrease_verbosity)
    
    if logger:
        logger.info("Log level signal handlers registered (SIGUSR1/SIGUSR2)")
