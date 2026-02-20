"""
Tests for site.pages vs site.images access patterns on commons.wikimedia.org.

This module tests how WikiAPI handles file access using both
self.site.pages and self.site.images, with and without 'File:' prefix.
"""
import pytest
from src.wiki_api import WikiAPI


@pytest.mark.network
def test_pages_access_with_file_prefix():
    """Test accessing file via site.pages with File: prefix."""
    api = WikiAPI("commons.wikimedia.org", "user", "pass")

    # Access with File: prefix
    page = api.site.pages["File:Cardiovascular-disease-death-rates,_1980_to_2021,_DEU.svg"]

    assert page.exists is True

    # Access without File: prefix
    page2 = api.site.pages["Cardiovascular-disease-death-rates,_1980_to_2021,_DEU.svg"]

    assert page2.exists is False


@pytest.mark.network
def test_images_access_with_file_prefix():
    """Test accessing file via site.images with File: prefix."""
    api = WikiAPI("commons.wikimedia.org", "user", "pass")

    # Access with File: prefix
    page = api.site.images["File:Cardiovascular-disease-death-rates,_1980_to_2021,_DEU.svg"]

    assert page.exists is False

    # Access without File: prefix
    page2 = api.site.images["Cardiovascular-disease-death-rates,_1980_to_2021,_DEU.svg"]

    assert page2.exists is True
