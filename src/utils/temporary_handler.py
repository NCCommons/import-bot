"""
Temporary file handling utilities for download operations.

This module provides context managers for safely handling temporary files
during file download and upload operations. The primary use case is the
two-stage upload fallback: when URL upload fails, files are downloaded
to a temporary location before being uploaded.

Design Rationale:
    Using a context manager ensures proper cleanup of temporary files even
    when exceptions occur. This prevents disk space leaks from abandoned
    temporary files during error conditions.

Example:
    >>> from src.utils.temporary_handler import TemporaryDownloadFile
    >>>
    >>> # Automatic cleanup on exit (even on exception)
    >>> with TemporaryDownloadFile(suffix=".jpg") as temp_path:
    ...     urllib.request.urlretrieve(file_url, temp_path)
    ...     api.upload_from_file("image.jpg", temp_path, ...)
    >>> # temp_path is now deleted

Security Consideration:
    Temporary files are created with restrictive permissions by the OS.
    The file is deleted automatically when exiting the context manager,
    preventing residual data leakage.
"""

import logging
import tempfile
from pathlib import Path
from types import TracebackType
from typing import Optional, Type

logger = logging.getLogger(__name__)


class TemporaryDownloadFile:
    """
    Context manager for creating and automatically cleaning up temporary files.

    This class provides a safe way to handle temporary files during download
    operations. It creates a named temporary file on entry and guarantees
    deletion on exit, regardless of whether an exception occurred.

    The file is created with delete=False to allow it to be closed and
    reopened by other operations (like urllib.request.urlretrieve), then
    manually deleted in the __exit__ method.

    Attributes:
        suffix: File extension/suffix for the temporary file.
        temp_path: Path to the created temporary file (available after __enter__).
        _temp_file: Internal reference to the NamedTemporaryFile object.

    Example:
        >>> with TemporaryDownloadFile(suffix=".png") as temp_path:
        ...     # Download file to temp location
        ...     urllib.request.urlretrieve(image_url, temp_path)
        ...     # Process/upload the file
        ...     upload_result = api.upload_from_file("image.png", temp_path, ...)
        ...     # File is automatically deleted when exiting the block

        >>> # Handle exceptions - cleanup still happens
        >>> try:
        ...     with TemporaryDownloadFile() as temp_path:
        ...         raise ValueError("Something went wrong")
        ... except ValueError:
        ...     pass  # temp file was still cleaned up

    Thread Safety:
        Each instance creates its own unique temporary file, so instances
        can be safely used across threads.

    Note:
        The temporary file is created in the system's default temporary
        directory (typically /tmp on Unix or %TEMP% on Windows).
    """

    def __init__(self, suffix: str = ".tmp") -> None:
        """
        Initialize the TemporaryDownloadFile context manager.

        Args:
            suffix: File suffix/extension to append to the temporary filename.
                This is useful for tools that infer file type from extension.
                Default: ".tmp"
        """
        self.suffix: str = suffix
        self.temp_path: Optional[str] = None
        self._temp_file: Optional[tempfile.NamedTemporaryFile] = None

    def __enter__(self) -> str:
        """
        Create the temporary file and return its path.

        Creates a named temporary file that persists until explicitly deleted
        in __exit__. The file is immediately closed after creation to allow
        other operations to write to it.

        Returns:
            The absolute path to the created temporary file as a string.

        Example:
            >>> with TemporaryDownloadFile(suffix=".jpg") as path:
            ...     print(f"File created at: {path}")
            File created at: /tmp/tmpXXXXXX.jpg
        """
        self._temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=self.suffix,
            prefix="nc_import_",  # Prefix for easier identification
        )
        self.temp_path = self._temp_file.name
        self._temp_file.close()  # Close so other operations can open it
        logger.debug(f"Created temporary file: {self.temp_path}")
        return self.temp_path

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """
        Clean up the temporary file on context exit.

        This method is called automatically when exiting the 'with' block,
        regardless of whether an exception occurred. It deletes the temporary
        file to prevent disk space leaks.

        Args:
            exc_type: The type of exception that was raised, if any.
                None if no exception occurred.
            exc_val: The exception instance that was raised, if any.
                None if no exception occurred.
            exc_tb: The traceback object for the exception, if any.
                None if no exception occurred.

        Note:
            This method does not suppress exceptions - it always returns None,
            allowing any exception to propagate after cleanup.

        Warning:
            If the file has already been deleted externally, this method
            will log a debug message but not raise an error (missing_ok=True).
        """
        if self.temp_path:
            path = Path(self.temp_path)
            path.unlink(missing_ok=True)
            logger.debug(f"Cleaned up temporary file: {self.temp_path}")
        self.temp_path = None
        self._temp_file = None
