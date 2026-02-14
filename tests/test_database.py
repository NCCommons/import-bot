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

    def test_record_upload_with_special_characters(self, temp_db):
        """Test recording upload with special characters in filename."""
        temp_db.record_upload("file's name (2).jpg", "en", "success")

        with temp_db._get_connection() as conn:
            result = conn.execute("SELECT * FROM uploads WHERE filename=?", ("file's name (2).jpg",)).fetchone()

            assert result is not None
            assert result["filename"] == "file's name (2).jpg"

    def test_record_upload_with_unicode_filename(self, temp_db):
        """Test recording upload with unicode characters."""
        temp_db.record_upload("测试文件.jpg", "zh", "success")

        with temp_db._get_connection() as conn:
            result = conn.execute("SELECT * FROM uploads WHERE filename='测试文件.jpg'").fetchone()

            assert result is not None
            assert result["filename"] == "测试文件.jpg"

    def test_record_upload_with_long_error_message(self, temp_db):
        """Test recording upload with very long error message."""
        long_error = "Error: " + "x" * 10000
        temp_db.record_upload("fail.jpg", "en", "failed", long_error)

        with temp_db._get_connection() as conn:
            result = conn.execute("SELECT error FROM uploads WHERE filename='fail.jpg'").fetchone()

            assert result["error"] == long_error

    def test_record_page_processing_with_zero_values(self, temp_db):
        """Test recording page with zero templates and uploads."""
        temp_db.record_page_processing("Empty Page", "en", 0, 0)

        with temp_db._get_connection() as conn:
            result = conn.execute("SELECT * FROM pages WHERE page_title='Empty Page'").fetchone()

            assert result is not None
            assert result["templates_found"] == 0
            assert result["files_uploaded"] == 0

    def test_record_page_processing_with_unicode_title(self, temp_db):
        """Test recording page with unicode characters in title."""
        temp_db.record_page_processing("页面标题", "zh", 5, 3)

        with temp_db._get_connection() as conn:
            result = conn.execute("SELECT * FROM pages WHERE page_title='页面标题'").fetchone()

            assert result is not None
            assert result["page_title"] == "页面标题"

    def test_is_file_uploaded_different_languages(self, temp_db):
        """Test that file upload status is language-specific."""
        temp_db.record_upload("test.jpg", "en", "success")
        temp_db.record_upload("test.jpg", "ar", "failed", "Error")

        # Should be uploaded for English
        assert temp_db.is_file_uploaded("test.jpg", "en") is True

        # Should NOT be uploaded for Arabic (failed)
        assert temp_db.is_file_uploaded("test.jpg", "ar") is False

        # Should NOT be uploaded for French (not recorded)
        assert temp_db.is_file_uploaded("test.jpg", "fr") is False

    def test_get_statistics_with_mixed_statuses(self, temp_db):
        """Test statistics correctly filter by success status."""
        temp_db.record_upload("success1.jpg", "en", "success")
        temp_db.record_upload("success2.jpg", "en", "success")
        temp_db.record_upload("failed1.jpg", "en", "failed", "Error")
        temp_db.record_upload("duplicate1.jpg", "en", "duplicate")

        stats = temp_db.get_statistics("en")

        # Should only count successful uploads
        assert stats["total_uploads"] == 2

    def test_get_statistics_empty_language(self, temp_db):
        """Test statistics for language with no data."""
        temp_db.record_upload("test.jpg", "en", "success")

        stats = temp_db.get_statistics("ar")

        assert stats["total_uploads"] == 0
        assert stats["total_pages"] == 0

    def test_database_concurrent_operations(self, temp_db):
        """Test multiple operations in sequence."""
        # Add multiple records
        for i in range(100):
            temp_db.record_upload(f"file{i}.jpg", "en", "success")

        stats = temp_db.get_statistics("en")
        assert stats["total_uploads"] == 100
