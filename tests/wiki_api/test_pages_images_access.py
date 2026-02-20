"""
Tests for site.pages vs site.images access patterns on commons.wikimedia.org.

This module tests how WikiAPI handles file access using both
self.site.pages and self.site.images, with and without 'File:' prefix.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from src.wiki_api import WikiAPI


class TestPagesImagesAccess:
    """Tests for site.pages and site.images access patterns."""

    @patch("src.wiki_api.main_api.Site")
    def test_pages_access_with_file_prefix(self, mock_site_class):
        """Test accessing file via site.pages with File: prefix."""
        mock_page = Mock()
        mock_page.exists = True
        mock_page.imageinfo = {"url": "https://upload.wikimedia.org/wikipedia/commons/.../image.jpg"}

        mock_site = MagicMock()
        mock_site.pages.__getitem__.return_value = mock_page
        mock_site_class.return_value = mock_site

        api = WikiAPI("commons.wikimedia.org", "user", "pass")
        # Access with File: prefix
        page = api.site.pages["File:Cardiovascular-disease-death-rates,_1980_to_2021,_DEU.svg"]

        assert page.exists is True
        mock_site.pages.__getitem__.assert_called_with(
            "File:Cardiovascular-disease-death-rates,_1980_to_2021,_DEU.svg"
        )

    @patch("src.wiki_api.main_api.Site")
    def test_pages_access_without_file_prefix(self, mock_site_class):
        """Test accessing file via site.pages without File: prefix."""
        mock_page = Mock()
        mock_page.exists = True
        mock_page.imageinfo = {"url": "https://upload.wikimedia.org/wikipedia/commons/.../image.jpg"}

        mock_site = MagicMock()
        mock_site.pages.__getitem__.return_value = mock_page
        mock_site_class.return_value = mock_site

        api = WikiAPI("commons.wikimedia.org", "user", "pass")
        # Access without File: prefix
        page = api.site.pages["Cardiovascular-disease-death-rates,_1980_to_2021,_DEU.svg"]

        assert page.exists is True
        mock_site.pages.__getitem__.assert_called_with(
            "Cardiovascular-disease-death-rates,_1980_to_2021,_DEU.svg"
        )

    @patch("src.wiki_api.main_api.Site")
    def test_images_access_without_file_prefix(self, mock_site_class):
        """Test accessing file via site.images (always without File: prefix)."""
        mock_page = Mock()
        mock_page.exists = True
        mock_page.imageinfo = {"url": "https://upload.wikimedia.org/wikipedia/commons/.../image.jpg"}

        mock_site = MagicMock()
        mock_site.images.__getitem__.return_value = mock_page
        mock_site_class.return_value = mock_site

        api = WikiAPI("commons.wikimedia.org", "user", "pass")
        # site.images always uses filename without File: prefix
        page = api.site.images["Cardiovascular-disease-death-rates,_1980_to_2021,_DEU.svg"]

        assert page.exists is True
        mock_site.images.__getitem__.assert_called_with(
            "Cardiovascular-disease-death-rates,_1980_to_2021,_DEU.svg"
        )

    @patch("src.wiki_api.main_api.Site")
    def test_pages_exists_false(self, mock_site_class):
        """Test page.exists returns False when file doesn't exist."""
        mock_page = Mock()
        mock_page.exists = False

        mock_site = MagicMock()
        mock_site.pages.__getitem__.return_value = mock_page
        mock_site_class.return_value = mock_site

        api = WikiAPI("commons.wikimedia.org", "user", "pass")
        page = api.site.pages["File:NonExistentFile.svg"]

        assert page.exists is False

    @patch("src.wiki_api.main_api.Site")
    def test_images_exists_false(self, mock_site_class):
        """Test image.exists returns False when file doesn't exist."""
        mock_page = Mock()
        mock_page.exists = False

        mock_site = MagicMock()
        mock_site.images.__getitem__.return_value = mock_page
        mock_site_class.return_value = mock_site

        api = WikiAPI("commons.wikimedia.org", "user", "pass")
        page = api.site.images["NonExistentFile.svg"]

        assert page.exists is False


class TestCommonsWikimediaAccess:
    """Tests simulating access patterns for commons.wikimedia.org."""

    @patch("src.wiki_api.main_api.Site")
    def test_commons_file_access_with_prefix(self, mock_site_class):
        """Test accessing a Commons file with File: prefix via site.pages."""
        mock_page = Mock()
        mock_page.exists = True
        mock_page.imageinfo = {
            "url": "https://upload.wikimedia.org/wikipedia/commons/.../Cardiovascular-disease-death-rates.svg"
        }

        mock_site = MagicMock()
        mock_site.pages.__getitem__.return_value = mock_page
        mock_site_class.return_value = mock_site

        api = WikiAPI("commons.wikimedia.org", "user", "pass")

        # Access the file page with File: prefix
        filename = "File:Cardiovascular-disease-death-rates,_1980_to_2021,_DEU.svg"
        page = api.site.pages[filename]

        # Verify exists check
        assert page.exists is True
        assert page.imageinfo["url"].endswith(".svg")

    @patch("src.wiki_api.main_api.Site")
    def test_commons_file_access_without_prefix_via_pages(self, mock_site_class):
        """Test accessing a Commons file without File: prefix via site.pages."""
        mock_page = Mock()
        mock_page.exists = True
        mock_page.imageinfo = {
            "url": "https://upload.wikimedia.org/wikipedia/commons/.../Cardiovascular-disease-death-rates.svg"
        }

        mock_site = MagicMock()
        mock_site.pages.__getitem__.return_value = mock_page
        mock_site_class.return_value = mock_site

        api = WikiAPI("commons.wikimedia.org", "user", "pass")

        # Access the file page without File: prefix
        filename = "Cardiovascular-disease-death-rates,_1980_to_2021,_DEU.svg"
        page = api.site.pages[filename]

        # Verify exists check
        assert page.exists is True
        assert page.imageinfo["url"].endswith(".svg")

    @patch("src.wiki_api.main_api.Site")
    def test_commons_file_access_via_images(self, mock_site_class):
        """Test accessing a Commons file via site.images (without prefix)."""
        mock_page = Mock()
        mock_page.exists = True
        mock_page.imageinfo = {
            "url": "https://upload.wikimedia.org/wikipedia/commons/.../Cardiovascular-disease-death-rates.svg"
        }

        mock_site = MagicMock()
        mock_site.images.__getitem__.return_value = mock_page
        mock_site_class.return_value = mock_site

        api = WikiAPI("commons.wikimedia.org", "user", "pass")

        # Access via images (no File: prefix)
        filename = "Cardiovascular-disease-death-rates,_1980_to_2021,_DEU.svg"
        page = api.site.images[filename]

        # Verify exists check
        assert page.exists is True
        assert page.imageinfo["url"].endswith(".svg")

    @patch("src.wiki_api.main_api.Site")
    def test_commons_file_not_exists_pages(self, mock_site_class):
        """Test handling non-existent Commons file via site.pages."""
        mock_page = Mock()
        mock_page.exists = False

        mock_site = MagicMock()
        mock_site.pages.__getitem__.return_value = mock_page
        mock_site_class.return_value = mock_site

        api = WikiAPI("commons.wikimedia.org", "user", "pass")

        # Test with File: prefix
        page_with_prefix = api.site.pages["File:NonExistentFile_12345.svg"]
        assert page_with_prefix.exists is False

        # Test without File: prefix
        page_without_prefix = api.site.pages["NonExistentFile_12345.svg"]
        assert page_without_prefix.exists is False

    @patch("src.wiki_api.main_api.Site")
    def test_commons_file_not_exists_images(self, mock_site_class):
        """Test handling non-existent Commons file via site.images."""
        mock_page = Mock()
        mock_page.exists = False

        mock_site = MagicMock()
        mock_site.images.__getitem__.return_value = mock_page
        mock_site_class.return_value = mock_site

        api = WikiAPI("commons.wikimedia.org", "user", "pass")

        filename = "NonExistentFile_12345.svg"
        page = api.site.images[filename]
        assert page.exists is False

    @patch("src.wiki_api.main_api.Site")
    def test_commons_file_various_names_with_prefix(self, mock_site_class):
        """Test various Commons file names with File: prefix."""
        test_cases = [
            "File:Cardiovascular-disease-death-rates,_1980_to_2021,_DEU.svg",
            "File:Example.jpg",
            "File:Test image (1).png",
            "File:My_File-Name.2.jpg",
        ]

        for filename in test_cases:
            mock_page = Mock()
            mock_page.exists = True

            mock_site = MagicMock()
            mock_site.pages.__getitem__.return_value = mock_page
            mock_site_class.return_value = mock_site

            api = WikiAPI("commons.wikimedia.org", "user", "pass")
            page = api.site.pages[filename]

            assert page.exists is True, f"Failed for {filename}"

    @patch("src.wiki_api.main_api.Site")
    def test_commons_file_various_names_without_prefix(self, mock_site_class):
        """Test various Commons file names without File: prefix."""
        test_cases = [
            "Cardiovascular-disease-death-rates,_1980_to_2021,_DEU.svg",
            "Example.jpg",
            "Test image (1).png",
            "My_File-Name.2.jpg",
        ]

        for filename in test_cases:
            mock_page = Mock()
            mock_page.exists = True

            mock_site = MagicMock()
            mock_site.images.__getitem__.return_value = mock_page
            mock_site_class.return_value = mock_site

            api = WikiAPI("commons.wikimedia.org", "user", "pass")
            page = api.site.images[filename]

            assert page.exists is True, f"Failed for {filename}"
