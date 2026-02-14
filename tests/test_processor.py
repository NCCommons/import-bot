"""
Tests for page processor module.
"""

from unittest.mock import MagicMock, Mock

import pytest
from src.parsers import NCTemplate
from src.processor import PageProcessor


class TestPageProcessor:
    """Tests for PageProcessor class."""

    @pytest.fixture
    def processor(self, mock_wiki_api, temp_db, sample_config):
        """Create PageProcessor instance for testing."""
        mock_uploader = Mock()
        return PageProcessor(mock_wiki_api, mock_uploader, temp_db, sample_config)

    def test_processor_initialization(self, mock_wiki_api, temp_db, sample_config):
        """Test processor initializes correctly."""
        mock_uploader = Mock()
        processor = PageProcessor(mock_wiki_api, mock_uploader, temp_db, sample_config)

        assert processor.wiki_api == mock_wiki_api
        assert processor.uploader == mock_uploader
        assert processor.db == temp_db
        assert processor.config == sample_config

    def test_process_page_no_templates(self, processor, mock_wiki_api, temp_db):
        """Test processing page with no NC templates."""
        mock_wiki_api.get_page_text.return_value = "Just plain text, no templates."
        mock_wiki_api.lang = "en"

        result = processor.process_page("Test Page")

        assert result is False

        # Should record page with 0 templates and 0 uploads
        with temp_db._get_connection() as conn:
            record = conn.execute("SELECT * FROM pages WHERE page_title='Test Page'").fetchone()
            assert record is not None
            assert record["templates_found"] == 0
            assert record["files_uploaded"] == 0

    def test_process_page_with_templates_successful_uploads(self, processor, mock_wiki_api, temp_db):
        """Test processing page with NC templates and successful uploads."""
        page_text = """
        Some text here.
        {{NC|file1.jpg|Caption 1}}
        More text.
        {{NC|file2.jpg|Caption 2}}
        """

        mock_wiki_api.get_page_text.return_value = page_text
        mock_wiki_api.lang = "en"

        # Mock successful uploads
        processor.uploader.upload_file.return_value = {"success": True}

        result = processor.process_page("Test Page")

        assert result is True

        # Verify uploads were attempted
        assert processor.uploader.upload_file.call_count == 2

        # Verify page was saved
        mock_wiki_api.save_page.assert_called_once()

        # Verify database record
        with temp_db._get_connection() as conn:
            record = conn.execute("SELECT * FROM pages WHERE page_title='Test Page'").fetchone()
            assert record["templates_found"] == 2
            assert record["files_uploaded"] == 2

    def test_process_page_partial_upload_success(self, processor, mock_wiki_api, temp_db):
        """Test processing when only some files upload successfully."""
        page_text = """
        {{NC|success.jpg|Caption 1}}
        {{NC|fail.jpg|Caption 2}}
        """

        mock_wiki_api.get_page_text.return_value = page_text
        mock_wiki_api.lang = "en"

        # First upload succeeds, second fails
        processor.uploader.upload_file.side_effect = [{"success": True}, {"success": False, "error": "exists"}]

        result = processor.process_page("Test Page")

        assert result is True  # Page should still be updated

        # Verify page record
        with temp_db._get_connection() as conn:
            record = conn.execute("SELECT * FROM pages WHERE page_title='Test Page'").fetchone()
            assert record["templates_found"] == 2
            assert record["files_uploaded"] == 1  # Only one succeeded

    def test_process_page_no_uploads_successful(self, processor, mock_wiki_api, temp_db):
        """Test processing when no uploads succeed."""
        page_text = "{{NC|fail.jpg|Caption}}"

        mock_wiki_api.get_page_text.return_value = page_text
        mock_wiki_api.lang = "en"

        # Upload fails
        processor.uploader.upload_file.return_value = {"success": False, "error": "failed"}

        result = processor.process_page("Test Page")

        assert result is False  # Page not modified

        # Page should not be saved
        mock_wiki_api.save_page.assert_not_called()

        # Database should still record the attempt
        with temp_db._get_connection() as conn:
            record = conn.execute("SELECT * FROM pages WHERE page_title='Test Page'").fetchone()
            assert record["templates_found"] == 1
            assert record["files_uploaded"] == 0

    def test_process_page_adds_category(self, processor, mock_wiki_api, temp_db, sample_config):
        """Test that processing adds NC Commons category."""
        page_text = "{{NC|test.jpg|Caption}}"

        mock_wiki_api.get_page_text.return_value = page_text
        mock_wiki_api.lang = "en"
        processor.uploader.upload_file.return_value = {"success": True}

        processor.process_page("Test Page")

        # Check the saved text
        call_args = mock_wiki_api.save_page.call_args
        saved_text = call_args[0][1]  # Second positional argument

        expected_category = sample_config["wikipedia"]["category"]
        assert f"[[{expected_category}]]" in saved_text

    def test_process_page_doesnt_duplicate_category(self, processor, mock_wiki_api, temp_db, sample_config):
        """Test that category isn't added if already present."""
        category = sample_config["wikipedia"]["category"]
        page_text = f"{{{{NC|test.jpg|Caption}}}}\n[[{category}]]"

        mock_wiki_api.get_page_text.return_value = page_text
        mock_wiki_api.lang = "en"
        processor.uploader.upload_file.return_value = {"success": True}

        processor.process_page("Test Page")

        # Check the saved text
        call_args = mock_wiki_api.save_page.call_args
        saved_text = call_args[0][1]

        # Should only appear once
        assert saved_text.count(f"[[{category}]]") == 1

    def test_process_page_replaces_templates_with_file_syntax(self, processor, mock_wiki_api, temp_db):
        """Test that NC templates are replaced with file syntax."""
        page_text = "Text before\n{{NC|test.jpg|My caption}}\nText after"

        mock_wiki_api.get_page_text.return_value = page_text
        mock_wiki_api.lang = "en"
        processor.uploader.upload_file.return_value = {"success": True}

        processor.process_page("Test Page")

        # Check the saved text
        call_args = mock_wiki_api.save_page.call_args
        saved_text = call_args[0][1]

        # Original template should be gone
        assert "{{NC|test.jpg|My caption}}" not in saved_text

        # Should be replaced with file syntax
        assert "[[File:test.jpg|thumb|My caption]]" in saved_text

        # Other text should remain
        assert "Text before" in saved_text
        assert "Text after" in saved_text

    def test_process_page_summary_message(self, processor, mock_wiki_api, temp_db):
        """Test that save summary is correct."""
        page_text = "{{NC|file1.jpg|C1}}\n{{NC|file2.jpg|C2}}"

        mock_wiki_api.get_page_text.return_value = page_text
        mock_wiki_api.lang = "en"
        processor.uploader.upload_file.return_value = {"success": True}

        processor.process_page("Test Page")

        # Check the summary
        call_args = mock_wiki_api.save_page.call_args
        summary = call_args[0][2]  # Third positional argument

        assert "Bot: Imported 2 file(s) from NC Commons" in summary

    def test_process_page_handles_upload_exception(self, processor, mock_wiki_api, temp_db):
        """Test that page processing continues on upload exception."""
        page_text = "{{NC|error.jpg|C1}}\n{{NC|success.jpg|C2}}"

        mock_wiki_api.get_page_text.return_value = page_text
        mock_wiki_api.lang = "en"

        # First raises exception, second succeeds
        processor.uploader.upload_file.side_effect = [Exception("Upload error"), {"success": True}]

        result = processor.process_page("Test Page")

        # Should still succeed because second file uploaded
        assert result is True

        # Both uploads should have been attempted
        assert processor.uploader.upload_file.call_count == 2

    def test_process_page_handles_page_fetch_error(self, processor, mock_wiki_api, temp_db):
        """Test handling error when fetching page."""
        mock_wiki_api.get_page_text.side_effect = Exception("Page not found")
        mock_wiki_api.lang = "en"

        result = processor.process_page("Missing Page")

        assert result is False

        # Should not save page
        mock_wiki_api.save_page.assert_not_called()

    def test_apply_replacements(self, processor):
        """Test _apply_replacements method."""
        text = "Start {{NC|file1.jpg|Cap1}} middle {{NC|file2.jpg|Cap2}} end"

        replacements = {
            "{{NC|file1.jpg|Cap1}}": "[[File:file1.jpg|thumb|Cap1]]",
            "{{NC|file2.jpg|Cap2}}": "[[File:file2.jpg|thumb|Cap2]]",
        }

        result = processor._apply_replacements(text, replacements)

        assert "{{NC|file1.jpg|Cap1}}" not in result
        assert "{{NC|file2.jpg|Cap2}}" not in result
        assert "[[File:file1.jpg|thumb|Cap1]]" in result
        assert "[[File:file2.jpg|thumb|Cap2]]" in result
        assert "Start" in result
        assert "middle" in result
        assert "end" in result

    def test_apply_replacements_empty(self, processor):
        """Test _apply_replacements with no replacements."""
        text = "Original text"

        result = processor._apply_replacements(text, {})

        assert result == text

    def test_process_page_multiple_templates_same_file(self, processor, mock_wiki_api, temp_db):
        """Test processing page with multiple references to same file."""
        page_text = """
        {{NC|same.jpg|First use}}
        Some text
        {{NC|same.jpg|Second use}}
        """

        mock_wiki_api.get_page_text.return_value = page_text
        mock_wiki_api.lang = "en"
        processor.uploader.upload_file.return_value = {"success": True}

        processor.process_page("Test Page")

        # Upload should be attempted for each template
        assert processor.uploader.upload_file.call_count == 2

        # Both templates should be replaced
        call_args = mock_wiki_api.save_page.call_args
        saved_text = call_args[0][1]

        assert saved_text.count("[[File:same.jpg|thumb|") == 2

    def test_process_page_records_language(self, processor, mock_wiki_api, temp_db):
        """Test that processor records correct language."""
        mock_wiki_api.get_page_text.return_value = "{{NC|test.jpg|Caption}}"
        mock_wiki_api.lang = "ar"  # Arabic
        processor.uploader.upload_file.return_value = {"success": True}

        processor.process_page("Test Page")

        # Verify language in database
        with temp_db._get_connection() as conn:
            record = conn.execute("SELECT language FROM pages WHERE page_title='Test Page'").fetchone()
            assert record["language"] == "ar"

    def test_process_page_with_empty_caption(self, processor, mock_wiki_api, temp_db):
        """Test processing template with empty caption."""
        page_text = "{{NC|test.jpg}}"

        mock_wiki_api.get_page_text.return_value = page_text
        mock_wiki_api.lang = "en"
        processor.uploader.upload_file.return_value = {"success": True}

        processor.process_page("Test Page")

        # Check the saved text
        call_args = mock_wiki_api.save_page.call_args
        saved_text = call_args[0][1]

        # Should still have file syntax, even with empty caption
        assert "[[File:test.jpg|thumb|]]" in saved_text
