"""
SQLite database operations for tracking bot activity.

This module provides a Database class that handles persistent storage of
upload records, page processing history, and statistics. It uses SQLite
for its lightweight, serverless architecture suitable for single-bot deployments.

Database Schema:
    uploads:
        - id: Primary key
        - filename: Name of the uploaded file
        - language: Wikipedia language code (e.g., 'en', 'ar')
        - uploaded_at: Timestamp of upload
        - status: 'success', 'failed', or 'duplicate'
        - error: Error message if failed

    pages:
        - id: Primary key
        - page_title: Title of the processed page
        - language: Wikipedia language code
        - processed_at: Timestamp of processing
        - templates_found: Number of NC templates found
        - files_uploaded: Number of files successfully uploaded

Design Patterns:
    - Context Manager: Safe connection handling with auto-commit/rollback
    - Repository Pattern: Encapsulates data access logic

Example:
    >>> from src.database import Database
    >>> db = Database("./data/nc_files.db")
    >>> db.record_upload("image.jpg", "en", "success")
    >>> stats = db.get_statistics("en")
    >>> print(stats)
    {'total_uploads': 1, 'total_pages': 0}
"""

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

logger = logging.getLogger(__name__)


class Database:
    """
    SQLite database wrapper for bot operations.

    This class provides a high-level interface for storing and retrieving
    bot activity data. It uses context managers for safe connection handling
    and includes automatic schema initialization.

    Attributes:
        db_path: Path to the SQLite database file.

    Thread Safety:
        SQLite connections are not thread-safe. Create a new Database
        instance per thread if concurrent access is needed.

    Example:
        >>> db = Database("./data/bot.db")
        >>> # Record an upload
        >>> db.record_upload("photo.jpg", "en", "success")
        >>> # Check if file was uploaded
        >>> db.is_file_uploaded("photo.jpg", "en")
        True
        >>> # Get statistics
        >>> db.get_statistics("en")
        {'total_uploads': 1, 'total_pages': 0}

    Note:
        The database file and parent directories are created automatically
        if they don't exist.
    """

    def __init__(self, db_path: str) -> None:
        """
        Initialize database connection and create schema if needed.

        Creates the database file and any necessary parent directories.
        Initializes the schema (tables and indexes) if they don't exist.

        Args:
            db_path: Path to the SQLite database file. Can be relative or absolute.
                Parent directories will be created if they don't exist.

        Example:
            >>> db = Database("./data/nc_files.db")
            >>> # Database file created at ./data/nc_files.db
        """
        self.db_path: Path = Path(db_path)

        # Create parent directory if it doesn't exist
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database schema
        self._init_schema()

        logger.info(f"Database initialized at {self.db_path}")

    @contextmanager
    def _get_connection(self) -> Iterator[sqlite3.Connection]:
        """
        Context manager for database connections with automatic transaction handling.

        Creates a new database connection, yields it for operations, and handles
        commit/rollback automatically based on whether an exception occurred.

        Yields:
            sqlite3.Connection: A database connection configured with Row factory.

        Raises:
            sqlite3.Error: Any database errors that occur during operations.

        Example:
            >>> with db._get_connection() as conn:
            ...     conn.execute("SELECT * FROM uploads")
            ...     # Auto-commits on success, rollback on exception
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row  # Access columns by name

        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        """
        Initialize the database schema with tables and indexes.

        Creates the following tables if they don't exist:
        - uploads: Records of file upload attempts
        - pages: Records of page processing activity

        Creates indexes for efficient querying by language and status.
        Uses IF NOT EXISTS to make this operation idempotent.
        """
        with self._get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS uploads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    language TEXT NOT NULL,
                    uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    status TEXT NOT NULL,
                    error TEXT
                );

                CREATE TABLE IF NOT EXISTS pages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    page_title TEXT NOT NULL,
                    language TEXT NOT NULL,
                    processed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    templates_found INTEGER,
                    files_uploaded INTEGER
                );

                CREATE INDEX IF NOT EXISTS idx_uploads_filename_lang
                    ON uploads(filename, language);
                CREATE INDEX IF NOT EXISTS idx_uploads_lang ON uploads(language);
                CREATE INDEX IF NOT EXISTS idx_uploads_status ON uploads(status);
                CREATE INDEX IF NOT EXISTS idx_pages_lang ON pages(language);
                """
            )

        logger.debug("Database schema initialized")

    def record_upload(
        self,
        filename: str,
        language: str,
        status: str,
        error: Optional[str] = None,
    ) -> None:
        """
        Record a file upload attempt in the database.

        Logs the result of an upload operation, whether successful or failed.
        This data is used to prevent re-uploading files and to track bot activity.

        Args:
            filename: Name of the file that was uploaded or attempted.
            language: Wikipedia language code (e.g., 'en', 'ar', 'fr').
            status: Upload result status. Must be one of:
                - 'success': File uploaded successfully
                - 'failed': Upload failed with error
                - 'duplicate': File is a duplicate of existing file
            error: Optional error message or additional context.
                For duplicates, typically 'duplicate_of:filename'.

        Example:
            >>> db.record_upload("image.jpg", "en", "success")
            >>> db.record_upload("failed.jpg", "en", "failed", "Network timeout")
            >>> db.record_upload("dup.jpg", "en", "duplicate", "duplicate_of:original.jpg")
        """
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO uploads (filename, language, status, error, uploaded_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (filename, language, status, error),
            )

        logger.debug(f"Recorded upload: {filename} ({language}) - {status}")

    def record_page_processing(
        self,
        page_title: str,
        language: str,
        templates_found: int,
        files_uploaded: int,
    ) -> None:
        """
        Record page processing activity in the database.

        Logs when a page has been processed, including how many NC templates
        were found and how many files were successfully uploaded.

        Args:
            page_title: Title of the Wikipedia page that was processed.
            language: Wikipedia language code (e.g., 'en', 'ar', 'fr').
            templates_found: Number of {{NC}} templates found on the page.
            files_uploaded: Number of files successfully uploaded from this page.
                This should exclude files that already existed or failed.

        Example:
            >>> db.record_page_processing("Article Name", "en", 3, 2)
            # Page had 3 NC templates, 2 files were uploaded
        """
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO pages (page_title, language, templates_found, files_uploaded, processed_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (page_title, language, templates_found, files_uploaded),
            )

        logger.debug(f"Recorded page: {page_title} ({language})")

    def is_file_uploaded(self, filename: str, language: str) -> bool:
        """
        Check if a file was previously uploaded successfully.

        This method is used to prevent duplicate upload attempts and to
        track which files have already been imported.

        Args:
            filename: Name of the file to check.
            language: Wikipedia language code to check within.

        Returns:
            True if the file has a 'success' status record for the given language,
            False otherwise. Failed or duplicate uploads return False.

        Example:
            >>> db.record_upload("image.jpg", "en", "success")
            >>> db.is_file_uploaded("image.jpg", "en")
            True
            >>> db.is_file_uploaded("image.jpg", "ar")
            False
            >>> db.is_file_uploaded("other.jpg", "en")
            False
        """
        with self._get_connection() as conn:
            result = conn.execute(
                """
                SELECT COUNT(*) as count FROM uploads
                WHERE filename = ? AND language = ? AND status = 'success'
                """,
                (filename, language),
            ).fetchone()

            return result["count"] > 0 if result else False

    def get_statistics(self, language: Optional[str] = None) -> Dict[str, int]:
        """
        Get upload and processing statistics.

        Retrieves aggregate statistics about bot activity, optionally filtered
        by language.

        Args:
            language: Optional language code to filter statistics.
                If None, returns overall statistics across all languages.

        Returns:
            Dictionary containing:
            - total_uploads: Count of successful uploads
            - total_pages: Count of processed pages

        Example:
            >>> db.get_statistics()
            {'total_uploads': 150, 'total_pages': 45}
            >>> db.get_statistics("en")
            {'total_uploads': 50, 'total_pages': 15}
        """
        with self._get_connection() as conn:
            if language:
                # Stats for specific language
                uploads = conn.execute(
                    """
                    SELECT COUNT(*) as count FROM uploads
                    WHERE language = ? AND status = 'success'
                    """,
                    (language,),
                ).fetchone()["count"]

                pages = conn.execute(
                    """
                    SELECT COUNT(*) as count FROM pages
                    WHERE language = ?
                    """,
                    (language,),
                ).fetchone()["count"]
            else:
                # Overall stats
                uploads = conn.execute(
                    """
                    SELECT COUNT(*) as count FROM uploads
                    WHERE status = 'success'
                    """
                ).fetchone()["count"]

                pages = conn.execute(
                    """
                    SELECT COUNT(*) as count FROM pages
                    """
                ).fetchone()["count"]

            return {"total_uploads": uploads, "total_pages": pages}
