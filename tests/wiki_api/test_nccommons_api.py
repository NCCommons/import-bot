"""
Tests for wiki API module.
"""

from unittest.mock import MagicMock, Mock, patch

from src.wiki_api import NCCommonsAPI


class TestNCCommonsAPI:
    """Tests for NCCommonsAPI class."""

    @patch("src.wiki_api.main_api.Site")
    def test_nc_commons_api_initialization(self, mock_site_class):
        """Test NCCommonsAPI initializes with nccommons.org."""
        mock_site = Mock()
        mock_site_class.return_value = mock_site

        api = NCCommonsAPI("user", "pass")

        mock_site_class.assert_called_once_with(
            "nccommons.org",
            clients_useragent="NC Commons Import Bot/1.0 (https://github.com/NCCommons)",
            force_login=True,
        )

    @patch("src.wiki_api.main_api.Site")
    def test_get_image_url(self, mock_site_class):
        """Test getting image URL."""
        mock_page = Mock()
        mock_page.imageinfo = {"url": "https://example.com/image.jpg"}

        mock_site = MagicMock()
        mock_site.images.__getitem__.return_value = mock_page
        mock_site_class.return_value = mock_site

        api = NCCommonsAPI("user", "pass")
        url = api.get_image_url("test.jpg")

        assert url == "https://example.com/image.jpg"
        mock_site.images.__getitem__.assert_called_once_with("test.jpg")

    @patch("src.wiki_api.main_api.Site")
    def test_get_image_url_adds_file_prefix(self, mock_site_class):
        """Test get_image_url adds File: prefix if missing."""
        mock_page = Mock()
        mock_page.imageinfo = {"url": "https://example.com/image.jpg"}

        mock_site = MagicMock()
        mock_site.images.__getitem__.return_value = mock_page
        mock_site_class.return_value = mock_site

        api = NCCommonsAPI("user", "pass")
        url = api.get_image_url("File:test.jpg")

        # Should not add duplicate prefix
        assert url == "https://example.com/image.jpg"
        mock_site.images.__getitem__.assert_called_once_with("test.jpg")

    @patch("src.wiki_api.main_api.Site")
    def test_get_file_description(self, mock_site_class):
        """Test getting file description."""
        mock_page = Mock()
        mock_page.text.return_value = "File description content"

        mock_site = MagicMock()
        mock_site.pages.__getitem__.return_value = mock_page
        mock_site_class.return_value = mock_site

        api = NCCommonsAPI("user", "pass")
        desc = api.get_file_description("test.jpg")

        assert desc == "File description content"
        mock_site.pages.__getitem__.assert_called_with("File:test.jpg")
