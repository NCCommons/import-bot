"""
Tests for wiki API module.
"""

from unittest.mock import MagicMock, Mock, patch

from src.wiki_api import WikipediaAPI


class TestWikipediaAPI:
    """Tests for WikipediaAPI class."""

    @patch("src.wiki_api.main_api.Site")
    def test_wikipedia_api_initialization(self, mock_site_class):
        """Test WikipediaAPI initializes with correct site."""
        mock_site = Mock()
        mock_site_class.return_value = mock_site

        api = WikipediaAPI("en", "user", "pass")

        mock_site_class.assert_called_once_with(
            "en.wikipedia.org",
            clients_useragent="NC Commons Import Bot/1.0 (https://github.com/NCCommons)",
            force_login=True,
        )
        assert api.lang == "en"

    @patch("src.wiki_api.main_api.Site")
    def test_wikipedia_api_different_language(self, mock_site_class):
        """Test WikipediaAPI with different language code."""
        mock_site = Mock()
        mock_site_class.return_value = mock_site

        api = WikipediaAPI("ar", "user", "pass")

        mock_site_class.assert_called_once_with(
            "ar.wikipedia.org",
            clients_useragent="NC Commons Import Bot/1.0 (https://github.com/NCCommons)",
            force_login=True,
        )
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
