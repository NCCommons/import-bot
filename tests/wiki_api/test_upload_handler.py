"""
Tests for wiki API module.
"""

from unittest.mock import Mock, mock_open, patch

import mwclient.errors
import pytest
from src.wiki_api import WikipediaAPI


class TestWikipediaAPI:
    """Tests for WikipediaAPI class."""

    @patch("src.wiki_api.main_api.Site")
    def test_upload_from_url_success(self, mock_site_class):
        """Test successful upload from URL."""
        mock_site = Mock()
        mock_site.raw_call.return_value = '{"upload": {"result": "Success"}}'
        mock_site.get_token.return_value = "test_token"
        mock_site_class.return_value = mock_site

        api = WikipediaAPI("en", "user", "pass")
        result = api.upload_from_url("test.jpg", "https://example.com/test.jpg", "Description", "Upload comment")

        assert result.get("success") is True

    @patch("src.wiki_api.main_api.Site")
    def test_upload_from_url_duplicate(self, mock_site_class):
        """Test upload from URL with duplicate file."""
        mock_site = Mock()
        mock_site.raw_call.return_value = '{"upload": {"warnings": {"duplicate": ["Existing_file.jpg"]}}}'
        mock_site.get_token.return_value = "test_token"
        mock_site_class.return_value = mock_site

        api = WikipediaAPI("en", "user", "pass")

        result = api.upload_from_url("test.jpg", "https://example.com/test.jpg", "Description", "Comment")

        assert result.get("success") is False

    @patch("src.wiki_api.main_api.Site")
    @patch("builtins.open", new_callable=mock_open, read_data=b"image data")
    def test_upload_from_file_success(self, mock_file, mock_site_class):
        """Test successful upload from file."""
        mock_site = Mock()
        mock_site.raw_call.return_value = '{"upload": {"result": "Success"}}'
        mock_site.get_token.return_value = "test_token"
        mock_site_class.return_value = mock_site

        api = WikipediaAPI("en", "user", "pass")
        result = api.upload_from_file("test.jpg", "/tmp/test.jpg", "Description", "Comment")

        assert result.get("success") is True
        mock_file.assert_called_once_with("/tmp/test.jpg", "rb")

    @patch("src.wiki_api.main_api.Site")
    @patch("builtins.open", new_callable=mock_open, read_data=b"image data")
    def test_upload_from_file_duplicate(self, mock_file, mock_site_class):
        """Test upload from file with duplicate."""
        mock_site = Mock()
        mock_site.raw_call.return_value = '{"upload": {"warnings": {"duplicate": ["Existing_file.jpg"]}}}'
        mock_site.get_token.return_value = "test_token"
        mock_site_class.return_value = mock_site

        api = WikipediaAPI("en", "user", "pass")

        result = api.upload_from_file("test.jpg", "/tmp/test.jpg", "Description", "Comment")

        assert result.get("success") is False
