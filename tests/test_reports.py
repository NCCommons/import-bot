"""
Tests for report generation module.
"""

import json
from pathlib import Path

import pytest
from src.database import Database
from src.reports import Reporter


class TestReporter:
    """Tests for Reporter class."""

    def test_reporter_initialization(self, temp_db):
        """Test reporter initializes correctly."""
        reporter = Reporter(temp_db)

        assert reporter.db is temp_db

    def test_generate_summary_empty_database(self, temp_db):
        """Test generating summary with empty database."""
        reporter = Reporter(temp_db)

        summary = reporter.generate_summary()

        assert "total" in summary
        assert "by_language" in summary
        assert "recent_errors" in summary

        # Empty database should have zero totals
        assert summary["total"]["total_uploads"] == 0
        assert summary["total"]["total_pages"] == 0
        assert len(summary["by_language"]) == 0
        assert len(summary["recent_errors"]) == 0

    def test_generate_summary_with_uploads(self, temp_db):
        """Test generating summary with upload data."""
        # Add test data
        temp_db.record_upload("file1.jpg", "en", "success")
        temp_db.record_upload("file2.jpg", "en", "success")
        temp_db.record_upload("file3.jpg", "ar", "success")
        temp_db.record_page_processing("Page1", "en", 2, 2)

        reporter = Reporter(temp_db)
        summary = reporter.generate_summary()

        # Verify totals
        assert summary["total"]["total_uploads"] == 3
        assert summary["total"]["total_pages"] == 1

        # Verify by-language stats
        assert len(summary["by_language"]) == 2

        # Check language stats (order may vary)
        lang_dict = {lang["language"]: lang["upload_count"] for lang in summary["by_language"]}
        assert lang_dict["en"] == 2
        assert lang_dict["ar"] == 1

    def test_generate_summary_with_errors(self, temp_db):
        """Test generating summary includes recent errors."""
        # Add successful and failed uploads
        temp_db.record_upload("success.jpg", "en", "success")
        temp_db.record_upload("error1.jpg", "en", "failed", "Network error")
        temp_db.record_upload("error2.jpg", "ar", "failed", "Permission denied")

        reporter = Reporter(temp_db)
        summary = reporter.generate_summary()

        # Should only count successful uploads
        assert summary["total"]["total_uploads"] == 1

        # Should list errors
        assert len(summary["recent_errors"]) == 2

        # Verify error details
        errors = summary["recent_errors"]
        error_files = [e["filename"] for e in errors]
        assert "error1.jpg" in error_files
        assert "error2.jpg" in error_files

    def test_generate_summary_limits_recent_errors(self, temp_db):
        """Test that recent errors are limited to 10."""
        # Add more than 10 errors
        for i in range(15):
            temp_db.record_upload(f"error{i}.jpg", "en", "failed", f"Error {i}")

        reporter = Reporter(temp_db)
        summary = reporter.generate_summary()

        # Should only return 10 most recent errors
        assert len(summary["recent_errors"]) == 10

    def test_generate_summary_ignores_duplicates_in_totals(self, temp_db):
        """Test that duplicate status doesn't count in totals."""
        temp_db.record_upload("dup.jpg", "en", "duplicate")
        temp_db.record_upload("success.jpg", "en", "success")

        reporter = Reporter(temp_db)
        summary = reporter.generate_summary()

        # Only successful uploads should count
        assert summary["total"]["total_uploads"] == 1

    def test_save_report_creates_file(self, temp_db, tmp_path):
        """Test saving report creates JSON file."""
        # Add some data
        temp_db.record_upload("file1.jpg", "en", "success")

        reporter = Reporter(temp_db)
        output_path = tmp_path / "report.json"

        reporter.save_report(str(output_path))

        # Verify file was created
        assert output_path.exists()

        # Verify it's valid JSON
        with open(output_path, "r") as f:
            data = json.load(f)

        assert "total" in data
        assert "by_language" in data
        assert "recent_errors" in data

    def test_save_report_creates_directory(self, temp_db, tmp_path):
        """Test saving report creates parent directories."""
        reporter = Reporter(temp_db)
        output_path = tmp_path / "nested" / "reports" / "summary.json"

        reporter.save_report(str(output_path))

        # Verify directory and file were created
        assert output_path.parent.exists()
        assert output_path.exists()

    def test_save_report_json_structure(self, temp_db, tmp_path):
        """Test saved report has correct JSON structure."""
        # Add varied data
        temp_db.record_upload("file1.jpg", "en", "success")
        temp_db.record_upload("file2.jpg", "ar", "success")
        temp_db.record_upload("error.jpg", "en", "failed", "Test error")
        temp_db.record_page_processing("Page1", "en", 2, 1)

        reporter = Reporter(temp_db)
        output_path = tmp_path / "report.json"

        reporter.save_report(str(output_path))

        # Load and verify structure
        with open(output_path, "r") as f:
            data = json.load(f)

        # Check total structure
        assert isinstance(data["total"], dict)
        assert "total_uploads" in data["total"]
        assert "total_pages" in data["total"]

        # Check by_language structure
        assert isinstance(data["by_language"], list)
        if len(data["by_language"]) > 0:
            assert "language" in data["by_language"][0]
            assert "upload_count" in data["by_language"][0]

        # Check recent_errors structure
        assert isinstance(data["recent_errors"], list)
        if len(data["recent_errors"]) > 0:
            assert "filename" in data["recent_errors"][0]
            assert "error" in data["recent_errors"][0]

    def test_save_report_overwrites_existing(self, temp_db, tmp_path):
        """Test that saving report overwrites existing file."""
        output_path = tmp_path / "report.json"

        # Create initial report
        temp_db.record_upload("file1.jpg", "en", "success")
        reporter = Reporter(temp_db)
        reporter.save_report(str(output_path))

        # Add more data and save again
        temp_db.record_upload("file2.jpg", "en", "success")
        reporter.save_report(str(output_path))

        # Load and verify it has updated data
        with open(output_path, "r") as f:
            data = json.load(f)

        assert data["total"]["total_uploads"] == 2

    def test_generate_summary_by_language_sorted(self, temp_db):
        """Test that by_language results are sorted by upload count."""
        # Add uploads with different counts per language
        temp_db.record_upload("file1.jpg", "en", "success")
        temp_db.record_upload("file2.jpg", "en", "success")
        temp_db.record_upload("file3.jpg", "en", "success")
        temp_db.record_upload("file4.jpg", "ar", "success")
        temp_db.record_upload("file5.jpg", "ar", "success")
        temp_db.record_upload("file6.jpg", "fr", "success")

        reporter = Reporter(temp_db)
        summary = reporter.generate_summary()

        # Should be sorted by count descending
        by_lang = summary["by_language"]
        assert len(by_lang) >= 2

        # First should have highest count (en with 3)
        assert by_lang[0]["language"] == "en"
        assert by_lang[0]["upload_count"] == 3

        # Second should be ar with 2
        assert by_lang[1]["language"] == "ar"
        assert by_lang[1]["upload_count"] == 2
