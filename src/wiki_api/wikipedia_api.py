"""
MediaWiki API wrapper using mwclient.

This module provides classes for interacting with NC Commons and Wikipedia
through the MediaWiki API.
"""

import logging
import mwclient
from typing import List
from mwclient.errors import APIError
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
            True if successful, False if duplicate

        Raises:
            Exception: If upload fails for reasons other than duplicate
        """
        try:
            logger.info(f"Uploading from URL: {filename}")

            result = self.site.upload(file=None, filename=filename, description=description, comment=comment, url=url)

            logger.info(f"Upload successful: {filename}")
            return {"success": True}

        except APIError as e:
            error_msg = str(e).lower()

            if "duplicate" in error_msg:
                logger.warning(f"File is duplicate: {filename}")
                return {"success": False, "error": "duplicate"}

            elif "Upload by URL disabled" in error_msg:
                logger.warning(f"URL upload disabled for {filename}")
                return {"success": False, "error": "url_disabled"}

            logger.error(f"Upload failed: {e}")
            return {"success": False, "error": str(e)}

    def upload_from_file(self, filename: str, filepath: str, description: str, comment: str) -> dict:
        """
        Upload a file from local filesystem to Wikipedia.

        Args:
            filename: Target filename on Wikipedia
            filepath: Path to local file
            description: File description page content
            comment: Upload comment/summary

        Returns:
            True if successful, False if duplicate

        Raises:
            Exception: If upload fails for reasons other than duplicate
        """
        try:
            logger.info(f"Uploading from file: {filename}")

            with open(filepath, "rb") as f:
                result = self.site.upload(file=f, filename=filename, description=description, comment=comment)

            logger.info(f"Upload successful: {filename}")
            return {"success": True}

        except mwclient.errors.APIError as e:
            error_msg = str(e).lower()

            if "duplicate" in error_msg:
                logger.warning(f"File is duplicate: {filename}")
                return {"success": False, "error": "duplicate"}

            logger.error(f"Upload failed: {e}")
            return {"success": False, "error": str(e)}
