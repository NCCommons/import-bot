"""
MediaWiki API wrapper using mwclient.

This module provides classes for interacting with NC Commons and Wikipedia
through the MediaWiki API.
"""

import logging
import mwclient
from typing import Optional
from mwclient.client import Site
from mwclient.errors import APIError
from .api_errors import UploadError

logger = logging.getLogger(__name__)


class WikiAPI:
    """
    Base class for MediaWiki API interactions using mwclient.

    Provides common functionality for connecting to and interacting with
    MediaWiki sites.
    """

    def __init__(self, site: str, username: Optional[str] = None, password: Optional[str] = None):
        """
        Initialize connection to MediaWiki site.

        Args:
            site: Site URL (e.g., 'en.wikipedia.org')
            username: Optional username for login
            password: Optional password for login
        """
        logger.info(f"Connecting to {site}")
        try:
            self.site = Site(site)
        except Exception as e:
            logger.error(f"Failed to connect to {site}: {e}")
            raise
        self.login_done = False
        self.username = username
        self.password = password

        if not username or not password:
            # XOR case: exactly one of username/password is provided
            logger.warning("Both username and password are required for login; skipping login")
            return

    def ensure_logged_in(self) -> None:
        """
        Ensure that the user is logged in before performing actions that require authentication.
        """
        try:
            logger.info(f"Logging in as {self.username}")
            self.site.login(self.username, self.password)
            self.login_done = True
        except mwclient.errors.LoginError as e:
            logger.error(f"Login failed for {self.username}: {e}")
            return False

    def get_page_text(self, title: str) -> str:
        """
        Get the text content of a page.

        Args:
            title: Page title

        Returns:
            Page text content
        """
        logger.debug(f"Fetching page: {title}")
        page = self.site.pages[title]
        return page.text()

    def save_page(self, title: str, text: str, summary: str):
        """
        Save content to a page.

        Args:
            title: Page title
            text: New page content
            summary: Edit summary
        """
        logger.info(f"Saving page: {title}")
        self.ensure_logged_in()

        if not self.login_done:
            logger.error("Cannot save page without successful login")
            return False

        page = self.site.pages[title]
        return page.save(text, summary=summary)

    def upload(self, site: Site, file, filename: str, description: str, comment: str, url: Optional[str] = None) -> dict:
        """
        Upload a file to the MediaWiki site.

        Args:
            site: mwclient Site object
            file: File-like object to upload (or None if using URL upload)
            filename: Target filename on the wiki
            description: File description page content
            comment: Upload comment/summary
            url: Optional URL for direct upload (if supported)

        Returns:
            Dictionary with 'success' key indicating result and optional 'error' key for error details
        """
        try:
            logger.info(f"Uploading file: {filename}")
            _result = site.upload(file=file, filename=filename, description=description, comment=comment, url=url)
            logger.info(f"Upload successful: {filename}")
            return {"success": True}
        except APIError as e:
            error_msg = str(e).lower()
            logger.error(f"Upload failed for {filename}: {error_msg}")
            return {"success": False, "error": error_msg}

        except UploadError as e:
            error_msg = str(e).lower()

            if "duplicate" in error_msg:
                logger.warning(f"File is duplicate: {filename}")
                return {"success": False, "error": "duplicate"}

            elif "Upload by URL disabled" in error_msg:
                logger.warning(f"URL upload disabled for {filename}")
                return {"success": False, "error": "url_disabled"}

            logger.error(f"Upload failed: {e}")
            return {"success": False, "error": str(e)}
