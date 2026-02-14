"""
SQLite database operations for tracking bot activity.

This module handles all database interactions including recording uploads,
page processing, and generating statistics.
"""

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class Database:
    """
    SQLite database wrapper for bot operations.

    Handles storage and retrieval of upload records, page processing logs,
    and statistics.
    """

    def __init__(self, db_path: str):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)

        # Create parent directory if it doesn't exist
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database schema
        self._init_schema()

        logger.info(f"Database initialized at {self.db_path}")

    @contextmanager
    def _get_connection(self):
        """
        Context manager for database connections.

        Automatically handles commit/rollback and connection cleanup.

        Yields:
            sqlite3.Connection: Database connection
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

    def _init_schema(self):
        """Create database tables if they don't exist."""
        with self._get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS uploads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    language TEXT NOT NULL,
                    uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    status TEXT NOT NULL,
                    error TEXT,
                    UNIQUE(filename, language)
                );

                CREATE TABLE IF NOT EXISTS pages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    page_title TEXT NOT NULL,
                    language TEXT NOT NULL,
                    processed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    templates_found INTEGER,
                    files_uploaded INTEGER,
                    UNIQUE(page_title, language)
                );

                CREATE INDEX IF NOT EXISTS idx_uploads_lang ON uploads(language);
                CREATE INDEX IF NOT EXISTS idx_uploads_status ON uploads(status);
                CREATE INDEX IF NOT EXISTS idx_pages_lang ON pages(language);
            """
            )

        logger.debug("Database schema initialized")

    def record_upload(self, filename: str, language: str, status: str, error: Optional[str] = None):
        """
        Record a file upload attempt.

        Args:
            filename: Name of the uploaded file
            language: Wikipedia language code
            status: Upload status ('success', 'failed', 'duplicate')
            error: Error message if failed (optional)
        """
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO uploads
                (filename, language, status, error, uploaded_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (filename, language, status, error),
            )

        logger.debug(f"Recorded upload: {filename} ({language}) - {status}")

    def record_page_processing(self, page_title: str, language: str, templates_found: int, files_uploaded: int):
        """
        Record page processing activity.

        Args:
            page_title: Title of the processed page
            language: Wikipedia language code
            templates_found: Number of NC templates found
            files_uploaded: Number of files successfully uploaded
        """
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO pages
                (page_title, language, templates_found, files_uploaded, processed_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (page_title, language, templates_found, files_uploaded),
            )

        logger.debug(f"Recorded page: {page_title} ({language})")

    def is_file_uploaded(self, filename: str, language: str) -> bool:
        """
        Check if a file was already uploaded successfully.

        Args:
            filename: Name of the file
            language: Wikipedia language code

        Returns:
            True if file was previously uploaded successfully
        """
        with self._get_connection() as conn:
            result = conn.execute(
                """
                SELECT COUNT(*) as count FROM uploads
                WHERE filename = ? AND language = ? AND status = 'success'
            """,
                (filename, language),
            ).fetchone()

            return result["count"] > 0

    def get_statistics(self, language: Optional[str] = None) -> Dict[str, int]:
        """
        Get upload and processing statistics.

        Args:
            language: Optional language code to filter by

        Returns:
            Dictionary with statistics (total_uploads, total_pages, etc.)
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
