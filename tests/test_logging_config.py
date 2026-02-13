"""
Tests for logging configuration module.
"""

import pytest
import logging
import tempfile
from pathlib import Path

from src.logging_config import setup_logging


class TestSetupLogging:
    """Tests for logging setup function."""

    def test_setup_logging_default_level(self, tmp_path):
        """Test logging setup with default INFO level."""
        log_file = tmp_path / "test.log"

        config = {
            'level': 'INFO',
            'file': str(log_file)
        }

        # Clear existing handlers
        root_logger = logging.getLogger()
        root_logger.handlers = []

        setup_logging(config)

        # Verify log level is set
        assert root_logger.level == logging.INFO

        # Verify handlers were added
        assert len(root_logger.handlers) >= 2  # File and console handlers

        # Verify log file was created
        assert log_file.parent.exists()

    def test_setup_logging_debug_level(self, tmp_path):
        """Test logging setup with DEBUG level."""
        log_file = tmp_path / "debug.log"

        config = {
            'level': 'DEBUG',
            'file': str(log_file)
        }

        root_logger = logging.getLogger()
        root_logger.handlers = []

        setup_logging(config)

        assert root_logger.level == logging.DEBUG

    def test_setup_logging_warning_level(self, tmp_path):
        """Test logging setup with WARNING level."""
        log_file = tmp_path / "warning.log"

        config = {
            'level': 'WARNING',
            'file': str(log_file)
        }

        root_logger = logging.getLogger()
        root_logger.handlers = []

        setup_logging(config)

        assert root_logger.level == logging.WARNING

    def test_setup_logging_creates_log_directory(self, tmp_path):
        """Test that logging creates parent directories."""
        log_file = tmp_path / "nested" / "dirs" / "test.log"

        config = {
            'level': 'INFO',
            'file': str(log_file)
        }

        root_logger = logging.getLogger()
        root_logger.handlers = []

        setup_logging(config)

        # Verify directory was created
        assert log_file.parent.exists()

    def test_setup_logging_with_rotation_settings(self, tmp_path):
        """Test logging setup with custom rotation settings."""
        log_file = tmp_path / "rotated.log"

        config = {
            'level': 'INFO',
            'file': str(log_file),
            'max_bytes': 1024,
            'backup_count': 3
        }

        root_logger = logging.getLogger()
        root_logger.handlers = []

        setup_logging(config)

        # Find the RotatingFileHandler
        file_handler = None
        for handler in root_logger.handlers:
            if hasattr(handler, 'maxBytes'):
                file_handler = handler
                break

        assert file_handler is not None
        assert file_handler.maxBytes == 1024
        assert file_handler.backupCount == 3

    def test_setup_logging_lowercase_level(self, tmp_path):
        """Test that lowercase level names work."""
        log_file = tmp_path / "test.log"

        config = {
            'level': 'info',  # lowercase
            'file': str(log_file)
        }

        root_logger = logging.getLogger()
        root_logger.handlers = []

        setup_logging(config)

        assert root_logger.level == logging.INFO

    def test_setup_logging_missing_config_uses_defaults(self, tmp_path):
        """Test that missing config values use defaults."""
        log_file = tmp_path / "default.log"

        # Minimal config
        config = {
            'file': str(log_file)
        }

        root_logger = logging.getLogger()
        root_logger.handlers = []

        setup_logging(config)

        # Should default to INFO
        assert root_logger.level == logging.INFO

    def test_setup_logging_both_handlers_present(self, tmp_path):
        """Test that both file and console handlers are added."""
        log_file = tmp_path / "test.log"

        config = {
            'level': 'INFO',
            'file': str(log_file)
        }

        root_logger = logging.getLogger()
        root_logger.handlers = []

        setup_logging(config)

        # Should have at least 2 handlers (file and console)
        assert len(root_logger.handlers) >= 2

        # Check handler types
        handler_types = [type(h).__name__ for h in root_logger.handlers]
        assert 'RotatingFileHandler' in handler_types
        assert 'StreamHandler' in handler_types