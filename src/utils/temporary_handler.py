"""
Utility module for handling temporary files during uploads.
"""

import logging
import tempfile
from pathlib import Path
from types import TracebackType
from typing import Optional, Type

logger = logging.getLogger(__name__)


class TemporaryDownloadFile:
    """
    Context manager for temporary file downloads.

    Creates a temporary file on enter and automatically cleans it up on exit.
    """

    def __init__(self, suffix: str = ".tmp"):
        self.suffix = suffix
        self.temp_path: Optional[str] = None
        self._temp_file = None

    def __enter__(self) -> str:
        """Create temporary file and return its path."""
        self._temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=self.suffix)
        self.temp_path = self._temp_file.name
        self._temp_file.close()
        logger.debug(f"Created temporary file: {self.temp_path}")
        return self.temp_path

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType]
    ) -> None:
        """Clean up temporary file on exit."""
        if self.temp_path:
            Path(self.temp_path).unlink(missing_ok=True)
            logger.debug(f"Cleaned up temporary file: {self.temp_path}")
