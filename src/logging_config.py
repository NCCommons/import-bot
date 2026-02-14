"""
Logging configuration module for NC Commons Import Bot.

This module provides centralized logging setup with colored console output
and optional rotating file logging. It ensures consistent log formatting
across all bot components.

Features:
    - Colored console output using colorlog library
    - Rotating file handler with configurable size and backup count
    - Configurable log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - Automatic log directory creation

Design Rationale:
    Logging is configured on a per-module basis rather than globally to
    allow different log levels for different components. The root logger
    is configured with a specific name to avoid interfering with other
    libraries' logging.

Example:
    >>> from src.logging_config import setup_logging
    >>> setup_logging(
    ...     log_level="DEBUG",
    ...     name="bot",
    ...     log_file="logs/bot.log",
    ...     max_bytes=10*1024*1024,  # 10MB
    ...     backup_count=5
    ... )
    >>> import logging
    >>> logger = logging.getLogger("bot")
    >>> logger.info("Bot started")
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

import colorlog


def setup_logging(
    log_level: str,
    name: str = __name__,
    log_file: Optional[str] = None,
    max_bytes: int = 0,
    backup_count: int = 0,
) -> None:
    """
    Configure logging with colored console output and optional file logging.

    Sets up a logger with both console (colored) and optional file (plain text)
    handlers. If handlers are already configured for the logger, this function
    returns early to prevent duplicate handlers.

    Args:
        log_level: Logging level as a string. Valid values (case-insensitive):
            - 'DEBUG': Detailed diagnostic information
            - 'INFO': Confirmation of expected operation
            - 'WARNING': Something unexpected happened (default for production)
            - 'ERROR': A more serious problem occurred
            - 'CRITICAL': A fatal error occurred
        name: Logger name to configure. Using a specific name allows
            multiple loggers with different configurations. Default: __name__.
        log_file: Optional path to the log file. If provided, enables
            rotating file logging. Parent directories are created automatically.
            Default: None (no file logging).
        max_bytes: Maximum size of each log file in bytes before rotation.
            Only used when log_file is provided. Default: 0 (no rotation).
        backup_count: Number of rotated log files to keep.
            Only used when log_file is provided. Default: 0 (no backups).

    Example:
        >>> # Basic console-only logging
        >>> setup_logging(log_level="INFO", name="bot")

        >>> # Full logging with file rotation
        >>> setup_logging(
        ...     log_level="DEBUG",
        ...     name="bot",
        ...     log_file="logs/bot.log",
        ...     max_bytes=10*1024*1024,  # 10 MB
        ...     backup_count=5
        ... )

    Note:
        - Console output uses colorlog for colored level names
        - File output is plain text for compatibility with log tools
        - The logger has propagate=False to prevent duplicate logs

    Warning:
        Calling this function multiple times with the same logger name
        will not add duplicate handlers (early return on existing handlers).
    """
    root_logger = logging.getLogger(name)

    # Prevent duplicate handlers if called multiple times
    if root_logger.handlers:
        return

    # Convert log level string to logging constant
    level = getattr(logging, log_level.upper(), logging.INFO)

    # Console formatter with colors (only for levelname)
    console_formatter = colorlog.ColoredFormatter(
        "%(asctime)s - %(name)s - %(log_color)s%(levelname)s%(reset)s - %(message)s",
        log_colors={
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "red,bg_white",
        },
    )

    # Console handler with colors
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)

    # Configure root logger
    root_logger.setLevel(level)
    root_logger.addHandler(console_handler)
    root_logger.propagate = False

    # Optional file logging with rotation
    if log_file:
        log_file_path = Path(log_file)

        # Create logs directory if it doesn't exist
        log_file_path.parent.mkdir(parents=True, exist_ok=True)

        # File formatter (plain text for log files)
        file_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

        # File handler with rotation
        file_handler = RotatingFileHandler(
            log_file_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",  # Ensure UTF-8 encoding for international characters
        )
        file_handler.setFormatter(file_formatter)

        root_logger.addHandler(file_handler)

    logging.info("Logging configured")
