"""
NC Commons-specific API operations.

This module provides the NCCommonsAPI class that extends WikiAPI with
NC Commons-specific functionality, primarily for retrieving file information
and URLs for files hosted on nccommons.org.

NC Commons is a free media file repository similar to Wikimedia Commons,
hosting educational content that can be imported to Wikipedia.
"""

import logging
from typing import Optional

from .main_api import WikiAPI

logger = logging.getLogger(__name__)


class NCCommonsAPI(WikiAPI):
    """
    API wrapper for NC Commons operations.

    Provides methods specific to fetching files and information from
    NC Commons (nccommons.org). This is used as the source for files
    that will be imported to various Wikipedia language editions.

    Example:
        >>> api = NCCommonsAPI("username", "password")
        >>> url = api.get_image_url("Example.jpg")
        >>> print(url)
        'https://nccommons.org/images/Example.jpg'
        >>> description = api.get_file_description("Example.jpg")
    """

    def __init__(self, username: str, password: str) -> None:
        """
        Initialize NC Commons API connection.

        Args:
            username: NC Commons username.
            password: NC Commons password.

        Example:
            >>> api = NCCommonsAPI("MyBot", "password123")
            >>> # Connected to nccommons.org
        """
        super().__init__("nccommons.org", username, password)

    def get_image_url(self, filename: str) -> str:
        """
        Get the direct download URL for an image file.

        Retrieves the full URL that can be used to download the original
        file from NC Commons. This URL is used for importing files to Wikipedia.

        Args:
            filename: Image filename, with or without 'File:' prefix.
                Both "Example.jpg" and "File:Example.jpg" are valid.

        Returns:
            Direct URL to the original file on NC Commons servers.

        Raises:
            FileNotFoundError: If the file does not exist on NC Commons,
                or if the file has no image info (e.g., deleted file).

        Example:
            >>> url = api.get_image_url("Example.jpg")
            >>> url
            'https://upload.nccommons.org/wikipedia/commons/.../Example.jpg'

        Note:
            The returned URL may point to a CDN or file storage server
            rather than the main nccommons.org domain.
        """
        # Normalize filename with File: prefix
        if not filename.lower().startswith("file:"):
            filename = f"File:{filename}"

        logger.debug(f"Getting image URL for: {filename}")
        page = self.site.images[filename] or self.site.images[filename.removeprefix("File:")]

        if not page.exists:
            raise FileNotFoundError(f"File not found: {filename}")

        if not page.imageinfo:
            raise FileNotFoundError(f"No image info available for: {filename}")

        try:
            url: str = page.imageinfo["url"]
            return url
        except (KeyError, TypeError) as e:
            raise FileNotFoundError(f"No URL available for file: {filename}") from e

    def get_file_description(self, filename: str) -> str:
        """
        Get the file description page content.

        Retrieves the wikitext content of the file's description page
        on NC Commons. This typically includes license information,
        source details, and categories.

        Args:
            filename: Image filename, with or without 'File:' prefix.

        Returns:
            Wikitext content of the file description page.

        Example:
            >>> desc = api.get_file_description("Example.jpg")
            >>> "{{Information" in desc
            True

        Note:
            The returned description may contain NC Commons-specific
            categories that should be removed or replaced before
            uploading to Wikipedia.
        """
        # Normalize filename with File: prefix
        if not filename.lower().startswith("file:"):
            filename = f"File:{filename}"

        return self.get_page_text(filename)
