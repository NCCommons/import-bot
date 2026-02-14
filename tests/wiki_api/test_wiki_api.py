"""
Tests for wiki API module.
"""

from unittest.mock import MagicMock, Mock, patch
from src.wiki_api import WikiAPI


class TestWikiAPI:
    """Tests for WikiAPI base class."""

    @patch("src.wiki_api.main_api.Site")
    def test_wiki_api_initialization(self, mock_site_class):
        """Test WikiAPI initializes connection."""
        mock_site = Mock()
        mock_site_class.return_value = mock_site

        api = WikiAPI("test.wikipedia.org")

        mock_site_class.assert_called_once_with("test.wikipedia.org")
        assert api.site == mock_site

    @patch("src.wiki_api.main_api.Site")
    def test_get_page_text(self, mock_site_class):
        """Test getting page text."""
        mock_page = Mock()
        mock_page.text.return_value = "Page content"

        mock_site = MagicMock()
        mock_site.pages.__getitem__.return_value = mock_page
        mock_site_class.return_value = mock_site

        api = WikiAPI("test.wikipedia.org")
        text = api.get_page_text("Test Page")

        assert text == "Page content"
        mock_site.pages.__getitem__.assert_called_once_with("Test Page")

    @patch("src.wiki_api.main_api.Site")
    def test_save_page(self, mock_site_class):
        """Test saving page."""
        mock_page = Mock()
        mock_site = MagicMock()
        mock_site.pages.__getitem__.return_value = mock_page
        mock_site_class.return_value = mock_site

        api = WikiAPI("test.wikipedia.org")
        api.save_page("Test Page", "New content", "Edit summary")

        mock_page.save.assert_called_once_with("New content", summary="Edit summary")

    @patch("src.wiki_api.main_api.Site")
    def test_get_page_text_retries_on_failure(self, mock_site_class):
        """Test get_page_text retries on failure."""
        call_count = 0

        def side_effect():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Network error")
            return "Success"

        mock_page = Mock()
        mock_page.text.side_effect = side_effect

        mock_site = MagicMock()
        mock_site.pages.__getitem__.return_value = mock_page
        mock_site_class.return_value = mock_site

        api = WikiAPI("test.wikipedia.org")

        # Patch time.sleep to speed up test
        with patch("time.sleep"):
            text = api.get_page_text("Test Page")

        assert text == "Success"
        assert call_count == 2
