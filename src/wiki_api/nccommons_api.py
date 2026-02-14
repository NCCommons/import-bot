"""
MediaWiki API wrapper using mwclient.

This module provides classes for interacting with NC Commons and Wikipedia
through the MediaWiki API.
"""

import logging
from .main_api import WikiAPI

logger = logging.getLogger(__name__)


class NCCommonsAPI(WikiAPI):
    """
    API wrapper for NC Commons operations.

    Provides methods specific to fetching files and information from NC Commons.
    """

    def __init__(self, username: str, password: str):
        """
        Initialize NC Commons API connection.

        Args:
            username: NC Commons username
            password: NC Commons password
        """
        super().__init__("nccommons.org", username, password)

    def get_image_url(self, filename: str) -> str:
        """
        Get the direct URL to an image file.

        Args:
            filename: Image filename (with or without 'File:' prefix)

        Returns:
            Direct URL to the image file

        Raises:
            FileNotFoundError: If the file does not exist or has no imageinfo
        """
        if not filename.startswith("File:"):
            filename = f"File:{filename}"

        logger.debug(f"Getting image URL for: {filename}")
        page = self.site.pages[filename]

        if not page.exists:
            raise FileNotFoundError(f"File not found: {filename}")

        if not page.imageinfo:
            raise FileNotFoundError(f"No image info available for: {filename}")

        try:
            return page.imageinfo["url"]
        except (KeyError, TypeError) as e:
            raise FileNotFoundError(f"No URL available for file: {filename}") from e

    def get_file_description(self, filename: str) -> str:
        """
        Get the file description page content.

        Args:
            filename: Image filename (with or without 'File:' prefix)

        Returns:
            File description page wikitext
        """
        if not filename.startswith("File:"):
            filename = f"File:{filename}"

        return self.get_page_text(filename)
