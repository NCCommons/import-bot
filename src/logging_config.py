"""
Logging configuration module for NC Commons Import Bot.

Provides colored console output and rotating file logging.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import colorlog


def setup_logging(config: dict):
    """
    Configure logging based on configuration.

    Sets up both file and console logging with appropriate formatters
    and handlers. Console output uses colored formatting while file
    logs remain plain text.

    Args:
        config: Logging configuration dictionary with keys:
            - level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            - file: Path to log file
            - max_bytes: Maximum size of log file before rotation
            - backup_count: Number of backup files to keep
    """
    # Get logging configuration
    log_level = getattr(logging, config.get("level", "INFO").upper())
    log_file = Path(config.get("file", "./logs/bot.log"))
    max_bytes = config.get("max_bytes", 10485760)  # 10MB default
    backup_count = config.get("backup_count", 5)

    # Create logs directory
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # File formatter (plain text for log files)
    file_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

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

    # File handler with rotation
    file_handler = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count)
    file_handler.setFormatter(file_formatter)

    # Console handler with colors
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    logging.info("Logging configured")
