"""
Tests for page processor.
"""

import pytest
from unittest.mock import Mock
from src.processor import PageProcessor


class TestPageProcessor:
    """Tests for PageProcessor class."""

    @pytest.fixture
    def processor(self, mock_wiki_api, temp_db, sample_config):
        """Create PageProcessor instance for testing."""
        # Create mock uploader
        mock_uploader = Mock()
        mock_uploader.upload_file.return_value = True

        return PageProcessor(mock_wiki_api, mock_uploader, temp_db, sample_config)

    def test_process_page_with_templates(
        self,
        processor,
        mock_wiki_api,
        sample_nc_template_page,
        temp_db
    ):
        """Test processing page with NC templates."""
        # Set up mock to return page with templates
        mock_wiki_api.get_page_text.return_value = sample_nc_template_page

        result = processor.process_page('Test Page')

        # Should succeed
        assert result is True

        # Should have saved page
        mock_wiki_api.save_page.assert_called_once()

        # Check database record
        with temp_db._get_connection() as conn:
            record = conn.execute(
                "SELECT * FROM pages WHERE page_title='Test Page'"
            ).fetchone()

            assert record is not None
            assert record['templates_found'] == 2
            assert record['files_uploaded'] == 2

    def test_process_page_no_templates(self, processor, mock_wiki_api, temp_db):
        """Test processing page without NC templates."""
        mock_wiki_api.get_page_text.return_value = "Plain text page"

        result = processor.process_page('Plain Page')

        # Should return False (no modifications)
        assert result is False

        # Should NOT save page
        mock_wiki_api.save_page.assert_not_called()

        # Should still record in database
        with temp_db._get_connection() as conn:
            record = conn.execute(
                "SELECT * FROM pages WHERE page_title='Plain Page'"
            ).fetchone()

            assert record['templates_found'] == 0
            assert record['files_uploaded'] == 0

    def test_process_page_upload_fails(self, processor, mock_wiki_api, temp_db):
        """Test processing when file uploads fail."""
        mock_wiki_api.get_page_text.return_value = "{{NC|test.jpg|caption}}"

        # Make uploader fail
        processor.uploader.upload_file.return_value = False

        result = processor.process_page('Test Page')

        # Should return False (no files uploaded)
        assert result is False

        # Should NOT save page
        mock_wiki_api.save_page.assert_not_called()

    def test_process_page_adds_category(self, processor, mock_wiki_api):
        """Test that category is added to page."""
        page_text = "{{NC|test.jpg|caption}}"
        mock_wiki_api.get_page_text.return_value = page_text

        processor.process_page('Test Page')

        # Get the saved text
        call_args = mock_wiki_api.save_page.call_args
        saved_text = call_args[0][1]

        # Should contain category
        assert '[[Category:Contains images from NC Commons]]' in saved_text

    def test_process_page_doesnt_duplicate_category(self, processor, mock_wiki_api):
        """Test that category isn't added if already present."""
        page_text = """
        {{NC|test.jpg|caption}}
        [[Category:Contains images from NC Commons]]
        """
        mock_wiki_api.get_page_text.return_value = page_text

        processor.process_page('Test Page')

        call_args = mock_wiki_api.save_page.call_args
        saved_text = call_args[0][1]

        # Should only have one category
        assert saved_text.count('[[Category:Contains images from NC Commons]]') == 1

    def test_process_page_replaces_templates(self, processor, mock_wiki_api):
        """Test that NC templates are replaced with file syntax."""
        page_text = "Text before {{NC|test.jpg|My caption}} text after"
        mock_wiki_api.get_page_text.return_value = page_text

        processor.process_page('Test Page')

        call_args = mock_wiki_api.save_page.call_args
        saved_text = call_args[0][1]

        # Should replace template
        assert '{{NC|test.jpg|My caption}}' not in saved_text
        assert '[[File:test.jpg|thumb|My caption]]' in saved_text

    def test_process_page_continues_on_error(self, processor, mock_wiki_api, temp_db):
        """Test that processing continues when individual files fail."""
        page_text = """
        {{NC|success.jpg|caption1}}
        {{NC|fail.jpg|caption2}}
        {{NC|success2.jpg|caption3}}
        """
        mock_wiki_api.get_page_text.return_value = page_text

        # Make one upload fail
        def upload_side_effect(filename):
            if filename == 'fail.jpg':
                raise Exception("Upload error")
            return True

        processor.uploader.upload_file.side_effect = upload_side_effect

        result = processor.process_page('Test Page')

        # Should still succeed (2 out of 3 uploaded)
        assert result is True

        # Database should show 2 uploaded
        with temp_db._get_connection() as conn:
            record = conn.execute(
                "SELECT * FROM pages WHERE page_title='Test Page'"
            ).fetchone()

            assert record['templates_found'] == 3
            assert record['files_uploaded'] == 2

    def test_apply_replacements(self, processor):
        """Test template replacement logic."""
        text = "Before {{NC|file1.jpg}} middle {{NC|file2.jpg}} after"
        replacements = {
            '{{NC|file1.jpg}}': '[[File:file1.jpg|thumb|]]',
            '{{NC|file2.jpg}}': '[[File:file2.jpg|thumb|]]'
        }

        result = processor._apply_replacements(text, replacements)

        assert '{{NC|file1.jpg}}' not in result
        assert '{{NC|file2.jpg}}' not in result
        assert '[[File:file1.jpg|thumb|]]' in result
        assert '[[File:file2.jpg|thumb|]]' in result
