"""
NC Commons Import Bot

A simple bot to import files from NC Commons to Wikipedia.
"""

from pathlib import Path
from .logging_config import setup_logging

_dir = Path(__file__).parent.name

setup_logging(
    log_level="DEBUG",
    name=_dir,
    log_file="logs/bot.log",
    max_bytes=10 * 1024 * 1024,  # 10 MB
    backup_count=5,
)

__version__ = "0.0.1"
