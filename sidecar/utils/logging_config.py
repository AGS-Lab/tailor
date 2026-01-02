"""
Tailor - Logging Configuration Module

Centralized logging configuration for the Tailor sidecar application.
Provides consistent logging across all modules with proper formatting and levels.
"""

import logging
import sys
from pathlib import Path
from typing import Optional
from logging.handlers import RotatingFileHandler

from ..constants import (
    LOG_FORMAT,
    LOG_DATE_FORMAT,
    DEFAULT_LOG_LEVEL,
    ENV_LOG_LEVEL,
)


# Module-level logger cache
_loggers: dict[str, logging.Logger] = {}
_configured: bool = False


def configure_logging(
    level: Optional[str] = None,
    log_file: Optional[Path] = None,
    verbose: bool = False,
) -> None:
    """
    Configure logging for the entire application.
    
    Should be called once at application startup.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR). If None, uses env var or default.
        log_file: Optional path to log file. If provided, logs to both file and console.
        verbose: If True, sets level to DEBUG and adds more details to format.
    
    Example:
        >>> configure_logging(level="INFO", log_file=Path("tailor.log"))
        >>> configure_logging(verbose=True)  # Debug mode
    """
    global _configured
    
    # Determine log level
    if verbose:
        log_level = "DEBUG"
    elif level:
        log_level = level.upper()
    else:
        import os
        log_level = os.getenv(ENV_LOG_LEVEL, DEFAULT_LOG_LEVEL).upper()
    
    # Convert string level to logging constant
    numeric_level = getattr(logging, log_level, logging.INFO)
    
    # Create formatters
    if verbose:
        # More detailed format for debugging
        format_str = "%(asctime)s [%(levelname)-8s] [%(name)-20s] [%(filename)s:%(lineno)d] %(message)s"
    else:
        format_str = LOG_FORMAT
    
    formatter = logging.Formatter(format_str, datefmt=LOG_DATE_FORMAT)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (if requested)
    if log_file:
        try:
            # Ensure parent directory exists
            log_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Rotating file handler (max 10MB, keep 5 backups)
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
                encoding='utf-8'
            )
            file_handler.setLevel(numeric_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
            
            root_logger.info(f"Logging to file: {log_file}")
        except Exception as e:
            root_logger.warning(f"Failed to configure file logging: {e}")
    
    _configured = True
    root_logger.info(f"Logging configured at {log_level} level")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module or component.
    
    This function caches loggers to avoid creating duplicates.
    
    Args:
        name: Logger name, typically __name__ of the calling module
    
    Returns:
        Configured logger instance
    
    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Plugin loaded successfully")
        >>> logger.error("Failed to connect", exc_info=True)
    """
    if name not in _loggers:
        logger = logging.getLogger(name)
        _loggers[name] = logger
    
    return _loggers[name]


def get_plugin_logger(plugin_name: str) -> logging.Logger:
    """
    Get a logger specifically for a plugin.
    
    Plugin loggers are prefixed with 'plugin:' for easy identification.
    
    Args:
        plugin_name: Name of the plugin
    
    Returns:
        Configured logger instance for the plugin
    
    Example:
        >>> logger = get_plugin_logger("example_plugin")
        >>> logger.info("Tick executed")
    """
    return get_logger(f"plugin:{plugin_name}")


def set_log_level(level: str) -> None:
    """
    Dynamically change the log level for all loggers.
    
    Args:
        level: New log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Example:
        >>> set_log_level("DEBUG")  # Enable debug logging
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    for handler in root_logger.handlers:
        handler.setLevel(numeric_level)
    
    root_logger.info(f"Log level changed to {level.upper()}")


def is_configured() -> bool:
    """
    Check if logging has been configured.
    
    Returns:
        True if configure_logging() has been called, False otherwise
    """
    return _configured


# Convenience function for quick setup during development
def setup_dev_logging() -> None:
    """
    Quick setup for development logging.
    
    Sets DEBUG level and verbose output.
    """
    configure_logging(verbose=True)
