"""
Tests for wiki API module.
"""

from unittest.mock import MagicMock, Mock, patch

import mwclient.errors
import pytest
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
    def test_wiki_api_connection_error(self, mock_site_class):
        """Test WikiAPI raises connection errors."""
        mock_site_class.side_effect = ConnectionError("Failed to connect")

        with pytest.raises(ConnectionError, match="Failed to connect"):
            WikiAPI("test.wikipedia.org")

    @patch("src.wiki_api.main_api.Site")
    def test_wiki_api_with_credentials(self, mock_site_class):
        """Test WikiAPI initialization with username and password."""
        mock_site = Mock()
        mock_site_class.return_value = mock_site

        api = WikiAPI("test.wikipedia.org", username="testuser", password="testpass")

        assert api.username == "testuser"
        assert api.password == "testpass"
        assert api.login_done is False

    @patch("src.wiki_api.main_api.Site")
    def test_wiki_api_without_credentials(self, mock_site_class):
        """Test WikiAPI initialization without credentials skips login setup."""
        mock_site = Mock()
        mock_site_class.return_value = mock_site

        api = WikiAPI("test.wikipedia.org")

        # Verify UploadHandler is NOT initialized (no credentials)
        assert not hasattr(api, 'login_done') or api.login_done is False

    @patch("src.wiki_api.main_api.Site")
    def test_wiki_api_only_username(self, mock_site_class):
        """Test WikiAPI with only username warns about missing password."""
        mock_site = Mock()
        mock_site_class.return_value = mock_site

        api = WikiAPI("test.wikipedia.org", username="testuser", password=None)

        assert api.username == "testuser"
        assert api.password is None

    @patch("src.wiki_api.main_api.Site")
    def test_wiki_api_only_password(self, mock_site_class):
        """Test WikiAPI with only password warns about missing username."""
        mock_site = Mock()
        mock_site_class.return_value = mock_site

        api = WikiAPI("test.wikipedia.org", username=None, password="testpass")

        assert api.username is None
        assert api.password == "testpass"

    @patch("src.wiki_api.main_api.Site")
    def test_ensure_logged_in_success(self, mock_site_class):
        """Test successful login."""
        mock_site = Mock()
        mock_site_class.return_value = mock_site

        api = WikiAPI("test.wikipedia.org", username="testuser", password="testpass")
        api.ensure_logged_in()

        mock_site.login.assert_called_once_with("testuser", "testpass")
        assert api.login_done is True

    @patch("src.wiki_api.main_api.Site")
    def test_ensure_logged_in_failure(self, mock_site_class):
        """Test login failure handling."""
        mock_site = Mock()
        mock_site.login.side_effect = mwclient.errors.LoginError("Invalid credentials")
        mock_site_class.return_value = mock_site

        api = WikiAPI("test.wikipedia.org", username="testuser", password="wrongpass")
        api.ensure_logged_in()

        assert api.login_done is False

    @patch("src.wiki_api.main_api.Site")
    def test_save_page_not_logged_in(self, mock_site_class):
        """Test save_page when not logged in returns False."""
        mock_site = MagicMock()
        mock_site_class.return_value = mock_site

        api = WikiAPI("test.wikipedia.org", username="testuser", password="testpass")
        # Don't call ensure_logged_in, so login_done remains False
        result = api.save_page("Test Page", "New content", "Edit summary")

        assert result is False

    @patch("src.wiki_api.main_api.Site")
    def test_save_page_after_login(self, mock_site_class):
        """Test save_page after successful login."""
        mock_page = Mock()
        mock_site = MagicMock()
        mock_site.pages.__getitem__.return_value = mock_page
        mock_site_class.return_value = mock_site

        api = WikiAPI("test.wikipedia.org", username="testuser", password="testpass")
        api.ensure_logged_in()
        result = api.save_page("Test Page", "New content", "Edit summary")

        mock_page.save.assert_called_once_with("New content", summary="Edit summary")
        assert result == mock_page.save.return_value

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
