"""
Tests for wiki API module.
"""

from unittest.mock import MagicMock, Mock, mock_open, patch

import mwclient.errors
import pytest
from src.wiki_api import WikipediaAPI


class TestWikipediaAPI:
    """Tests for WikipediaAPI class."""

    @patch("src.wiki_api.main_api.Site")
    def test_wikipedia_api_initialization(self, mock_site_class):
        """Test WikipediaAPI initializes with correct site."""
        mock_site = Mock()
        mock_site_class.return_value = mock_site

        api = WikipediaAPI("en", "user", "pass")

        mock_site_class.assert_called_once_with("en.wikipedia.org")
        assert api.lang == "en"

    @patch("src.wiki_api.main_api.Site")
    def test_wikipedia_api_different_language(self, mock_site_class):
        """Test WikipediaAPI with different language code."""
        mock_site = Mock()
        mock_site_class.return_value = mock_site

        api = WikipediaAPI("ar", "user", "pass")

        mock_site_class.assert_called_once_with("ar.wikipedia.org")
        assert api.lang == "ar"

    @patch("src.wiki_api.main_api.Site")
    def test_get_pages_with_template(self, mock_site_class):
        """Test getting pages that use a template."""
        # Create mock pages
        mock_page1 = Mock()
        mock_page1.name = "Page 1"
        mock_page2 = Mock()
        mock_page2.name = "Page 2"

        mock_template = Mock()
        mock_template.embeddedin.return_value = [mock_page1, mock_page2]

        mock_site = MagicMock()
        mock_site.pages.__getitem__.return_value = mock_template
        mock_site_class.return_value = mock_site

        api = WikipediaAPI("en", "user", "pass")
        pages = api.get_pages_with_template("NC")

        assert pages == ["Page 1", "Page 2"]
        mock_site.pages.__getitem__.assert_called_once_with("Template:NC")

    @patch("src.wiki_api.main_api.Site")
    def test_get_pages_with_template_adds_prefix(self, mock_site_class):
        """Test that Template: prefix is added if missing."""
        mock_template = Mock()
        mock_template.embeddedin.return_value = []

        mock_site = MagicMock()
        mock_site.pages.__getitem__.return_value = mock_template
        mock_site_class.return_value = mock_site

        api = WikipediaAPI("en", "user", "pass")
        api.get_pages_with_template("Template:NC")

        # Should not add duplicate prefix
        mock_site.pages.__getitem__.assert_called_once_with("Template:NC")

    @pytest.mark.skip(reason="this should mock mwclient_upload")
    @patch("src.wiki_api.main_api.Site")
    def test_upload_from_url_success(self, mock_site_class):
        """Test successful upload from URL."""
        mock_site = Mock()
        mock_site.upload.return_value = {"result": "Success"}
        mock_site_class.return_value = mock_site

        api = WikipediaAPI("en", "user", "pass")
        result = api.upload_from_url("test.jpg", "https://example.com/test.jpg", "Description", "Upload comment")

        assert result.get("success") is True
        mock_site.upload.assert_called_once_with(
            file=None,
            filename="test.jpg",
            description="Description",
            comment="Upload comment",
            url="https://example.com/test.jpg",
        )

    @pytest.mark.skip(reason="this should mock mwclient_upload")
    @patch("src.wiki_api.main_api.Site")
    def test_upload_from_url_duplicate(self, mock_site_class):
        """Test upload from URL with duplicate file."""
        mock_site = Mock()
        mock_site.upload.side_effect = mwclient.errors.APIError("fileexists-shared-forbidden", "Duplicate file", {})
        mock_site_class.return_value = mock_site

        api = WikipediaAPI("en", "user", "pass")

        result = api.upload_from_url("test.jpg", "https://example.com/test.jpg", "Description", "Comment")

        assert result.get("success") is False

    @pytest.mark.skip(reason="this should mock mwclient_upload")
    @patch("src.wiki_api.main_api.Site")
    @patch("builtins.open", new_callable=mock_open, read_data=b"image data")
    def test_upload_from_file_success(self, mock_file, mock_site_class):
        """Test successful upload from file."""
        mock_site = Mock()
        mock_site.upload.return_value = {"result": "Success"}
        mock_site_class.return_value = mock_site

        api = WikipediaAPI("en", "user", "pass")
        result = api.upload_from_file("test.jpg", "/tmp/test.jpg", "Description", "Comment")

        assert result.get("success") is True
        mock_file.assert_called_once_with("/tmp/test.jpg", "rb")

    @pytest.mark.skip(reason="this should mock mwclient_upload")
    @patch("src.wiki_api.main_api.Site")
    @patch("builtins.open", new_callable=mock_open, read_data=b"image data")
    def test_upload_from_file_duplicate(self, mock_file, mock_site_class):
        """Test upload from file with duplicate."""
        mock_site = Mock()
        mock_site.upload.side_effect = mwclient.errors.APIError("duplicate", "Duplicate file", {})
        mock_site_class.return_value = mock_site

        api = WikipediaAPI("en", "user", "pass")

        result = api.upload_from_file("test.jpg", "/tmp/test.jpg", "Description", "Comment")

        assert result.get("success") is False
