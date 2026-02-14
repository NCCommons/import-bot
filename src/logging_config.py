"""
Logging configuration module for NC Commons Import Bot.

Provides colored console output and rotating file logging.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import colorlog


def setup_logging(
    log_level: str,
    name: str = __name__,
    log_file: str = None,
    max_bytes: int = 0,
    backup_count: int = 0,
) -> None:
    """
    Configure logging based on configuration.

    Sets up both file and console logging with appropriate formatters
    and handlers. Console output uses colored formatting while file
    logs remain plain text.

    Args:
        log_level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file
        max_bytes: Maximum size of log file before rotation
        backup_count: Number of backup files to keep
    """
    root_logger = logging.getLogger(name)

    if root_logger.handlers:
        return

    # Convert log level string to logging constant
    level = getattr(logging, log_level.upper())

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

    if log_file:
        log_file_path = Path(log_file)

        # Create logs directory
        log_file_path.parent.mkdir(parents=True, exist_ok=True)

        # File formatter (plain text for log files)
        file_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

        # File handler with rotation
        file_handler = RotatingFileHandler(log_file_path, maxBytes=max_bytes, backupCount=backup_count)
        file_handler.setFormatter(file_formatter)

        root_logger.addHandler(file_handler)

    logging.info("Logging configured")
