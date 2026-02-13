"""
Tests for database operations.
"""

import pytest
from src.database import Database


class TestDatabase:
    """Tests for Database class."""

    def test_database_initialization(self, temp_db):
        """Test database initializes correctly."""
        # Tables should exist
        with temp_db._get_connection() as conn:
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()

            table_names = [t["name"] for t in tables]
            assert "uploads" in table_names
            assert "pages" in table_names

    def test_record_upload_success(self, temp_db):
        """Test recording a successful upload."""
        temp_db.record_upload("test.jpg", "en", "success")

        # Verify record exists
        with temp_db._get_connection() as conn:
            result = conn.execute("SELECT * FROM uploads WHERE filename='test.jpg'").fetchone()

            assert result is not None
            assert result["filename"] == "test.jpg"
            assert result["language"] == "en"
            assert result["status"] == "success"
            assert result["error"] is None

    def test_record_upload_failed(self, temp_db):
        """Test recording a failed upload."""
        temp_db.record_upload("fail.jpg", "ar", "failed", "Error message")

        with temp_db._get_connection() as conn:
            result = conn.execute("SELECT * FROM uploads WHERE filename='fail.jpg'").fetchone()

            assert result["status"] == "failed"
            assert result["error"] == "Error message"

    def test_record_upload_duplicate(self, temp_db):
        """Test recording duplicate file."""
        temp_db.record_upload("dup.jpg", "en", "duplicate")

        with temp_db._get_connection() as conn:
            result = conn.execute("SELECT * FROM uploads WHERE filename='dup.jpg'").fetchone()

            assert result["status"] == "duplicate"

    def test_record_page_processing(self, temp_db):
        """Test recording page processing."""
        temp_db.record_page_processing("Test Page", "en", 3, 2)

        with temp_db._get_connection() as conn:
            result = conn.execute("SELECT * FROM pages WHERE page_title='Test Page'").fetchone()

            assert result is not None
            assert result["page_title"] == "Test Page"
            assert result["language"] == "en"
            assert result["templates_found"] == 3
            assert result["files_uploaded"] == 2

    def test_is_file_uploaded_true(self, temp_db):
        """Test checking if file is uploaded (true case)."""
        temp_db.record_upload("uploaded.jpg", "en", "success")

        result = temp_db.is_file_uploaded("uploaded.jpg", "en")
        assert result is True

    def test_is_file_uploaded_false(self, temp_db):
        """Test checking if file is uploaded (false case)."""
        result = temp_db.is_file_uploaded("notfound.jpg", "en")
        assert result is False

    def test_is_file_uploaded_failed_not_counted(self, temp_db):
        """Test that failed uploads don't count as uploaded."""
        temp_db.record_upload("failed.jpg", "en", "failed", "Error")

        result = temp_db.is_file_uploaded("failed.jpg", "en")
        assert result is False

    def test_get_statistics_overall(self, temp_db):
        """Test getting overall statistics."""
        # Add some test data
        temp_db.record_upload("file1.jpg", "en", "success")
        temp_db.record_upload("file2.jpg", "ar", "success")
        temp_db.record_page_processing("Page1", "en", 2, 1)
        temp_db.record_page_processing("Page2", "ar", 1, 1)

        stats = temp_db.get_statistics()

        assert stats["total_uploads"] == 2
        assert stats["total_pages"] == 2

    def test_get_statistics_by_language(self, temp_db):
        """Test getting statistics for specific language."""
        temp_db.record_upload("file1.jpg", "en", "success")
        temp_db.record_upload("file2.jpg", "en", "success")
        temp_db.record_upload("file3.jpg", "ar", "success")
        temp_db.record_page_processing("Page1", "en", 2, 2)

        stats = temp_db.get_statistics("en")

        assert stats["total_uploads"] == 2
        assert stats["total_pages"] == 1

    def test_upsert_behavior(self, temp_db):
        """Test that recording same file twice updates record."""
        temp_db.record_upload("test.jpg", "en", "success")
        temp_db.record_upload("test.jpg", "en", "failed", "New error")

        with temp_db._get_connection() as conn:
            results = conn.execute("SELECT * FROM uploads WHERE filename='test.jpg'").fetchall()

            # Should only have one record (updated)
            assert len(results) == 1
            assert results[0]["status"] == "failed"
            assert results[0]["error"] == "New error"
