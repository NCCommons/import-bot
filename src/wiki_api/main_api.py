"""
MediaWiki API wrapper using mwclient.

This module provides classes for interacting with NC Commons and Wikipedia
through the MediaWiki API.
"""

import logging
from typing import Any, Optional
import mwclient
from mwclient.client import Site

from .upload_handler import UploadHandler

logger = logging.getLogger(__name__)


class WikiAPI(UploadHandler):
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
        self.login_done = False
        self.username = username
        self.password = password

        if not username or not password:
            # XOR case: exactly one of username/password is provided
            logger.warning("Both username and password are required for login; skipping login")
            return

        try:
            self.site = Site(
                site,
                clients_useragent="NC Commons Import Bot/1.0 (https://github.com/your/repo)",
                force_login=True,
            )
        except Exception as e:
            logger.error(f"Failed to connect to {site}: {e}")
            raise

        super().__init__(self.site)

    def ensure_logged_in(self) -> None:
        """
        Ensure that the user is logged in before performing actions that require authentication.
        """
        if self.login_done:
            return
        login_type = ""
        try:
            logger.info(f"Logging in as {self.username}")
            self.site.login(self.username, self.password)
            login_type = "login"
        except mwclient.errors.LoginError as e:
            if "BotPasswordSessionProvider" in str(e):
                self.site.clientlogin(None, username=self.username, password=self.password)
                login_type = "clientlogin"
            else:
                logger.exception(f"Login failed for {self.username}: {e}")

        if self.site.logged_in:
            logger.info(f"Login (action:{login_type}) successful for {self.username}")
            self.login_done = True

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

    def upload(
        self,
        file: Any,
        filename: str,
        description: str,
        comment: str,
        url: str | None = None,
    ) -> dict:
        """
        Upload a file to the MediaWiki site.

        Args:
            file: File-like object to upload (or None if using URL upload)
            filename: Target filename on the wiki
            description: File description page content
            comment: Upload comment/summary
            url: Optional URL for direct upload (if supported)

        Returns:
            Dictionary with 'success' key indicating result and optional 'error' key for error details
        """

        self.ensure_logged_in()

        if not self.login_done:
            logger.error("Cannot save page without successful login")
            return False

        return self.upload_wrap(file=file, filename=filename, description=description, comment=comment, url=url)
