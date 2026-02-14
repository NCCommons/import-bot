"""
MediaWiki API wrapper using mwclient.

This module provides classes for interacting with NC Commons and Wikipedia
through the MediaWiki API.
"""

import logging
from typing import List

from .main_api import WikiAPI

logger = logging.getLogger(__name__)


class WikipediaAPI(WikiAPI):
    """
    API wrapper for Wikipedia operations.

    Provides methods specific to editing Wikipedia and uploading files.
    """

    def __init__(self, language_code: str, username: str, password: str):
        """
        Initialize Wikipedia API connection.

        Args:
            language_code: Wikipedia language code (e.g., 'en', 'ar', 'fr')
            username: Wikipedia username (use bot password format)
            password: Wikipedia password (bot password token)
        """
        self.lang = language_code
        site = f"{language_code}.wikipedia.org"
        super().__init__(site, username, password)

    def get_pages_with_template(self, template: str, limit: int = 5000) -> List[str]:
        """
        Get all pages that transclude a template.

        Args:
            template: Template name (with or without 'Template:' prefix)
            limit: Maximum number of pages to retrieve

        Returns:
            List of page titles
        """
        if not template.startswith("Template:"):
            template = f"Template:{template}"

        logger.info(f"Finding pages with template: {template}")

        template_page = self.site.pages[template]
        pages = [page.name for page in template_page.embeddedin(max_items=limit)]

        logger.info(f"Found {len(pages)} pages")
        return pages

    def upload_from_url(self, filename: str, url: str, description: str, comment: str) -> dict:
        """
        Upload a file from URL to Wikipedia.

        Args:
            filename: Target filename on Wikipedia
            url: Source URL of the file
            description: File description page content
            comment: Upload comment/summary

        Returns:
            Dictionary with upload result
        """
        logger.info(f"Uploading from URL: {filename}")

        result = self.upload(file=None, filename=filename, description=description, comment=comment, url=url)

        if result.get("success"):
            logger.info(f"Upload successful: {filename}")

        return result

    def upload_from_file(self, filename: str, filepath: str, description: str, comment: str) -> dict:
        """
        Upload a file from local filesystem to Wikipedia.

        Args:
            filename: Target filename on Wikipedia
            filepath: Path to local file
            description: File description page content
            comment: Upload comment/summary

        Returns:
            Dictionary with upload result
        """
        logger.info(f"Uploading from file: {filename}")

        with open(filepath, "rb") as f:
            result = self.upload(file=f, filename=filename, description=description, comment=comment)

        if result.get("success"):
            logger.info(f"Upload successful: {filename}")

        return result
