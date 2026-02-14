"""
Base MediaWiki API wrapper using mwclient.

This module provides the WikiAPI base class that establishes connections to
MediaWiki sites and handles authentication. It serves as the foundation for
specialized API clients (NCCommonsAPI, WikipediaAPI).

Architecture Decision - Inheritance from UploadHandler:
    WikiAPI inherits from UploadHandler to provide upload functionality to
    all API clients. This follows composition over inheritance for the upload
    logic while maintaining a clean class hierarchy for API operations.

Authentication Flow:
    1. Connect to site with optional credentials
    2. Call ensure_logged_in() before authenticated operations
    3. Try standard login first, fall back to clientlogin for bot passwords

Example:
    >>> from src.wiki_api import WikiAPI
    >>> api = WikiAPI("en.wikipedia.org", "username", "password")
    >>> api.ensure_logged_in()
    >>> text = api.get_page_text("Main Page")
"""

import logging
from typing import Any, BinaryIO, Optional

import mwclient
from mwclient.client import Site

from .upload_handler import UploadHandler

logger = logging.getLogger(__name__)


class WikiAPI(UploadHandler):
    """
    Base class for MediaWiki API interactions using mwclient.

    Provides common functionality for connecting to and interacting with
    MediaWiki sites, including authentication, page operations, and file
    uploads. This class should be subclassed for specific wiki targets.

    Inheritance:
        UploadHandler: Provides file upload functionality via composition.

    Attributes:
        site: mwclient Site object for API communication.
        login_done: Flag indicating successful authentication.
        username: Configured username (stored for deferred login).
        password: Configured password (stored for deferred login).

    Example:
        >>> api = WikiAPI("en.wikipedia.org", "bot@password", "token")
        >>> api.ensure_logged_in()
        >>> text = api.get_page_text("Article")
        >>> api.save_page("Article", "New content", "Bot: update")
    """

    def __init__(
        self,
        site: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        """
        Initialize connection to a MediaWiki site.

        Establishes a connection to the specified MediaWiki site. If both
        username and password are provided, authentication will be deferred
        until ensure_logged_in() is called or an authenticated operation
        is attempted.

        Args:
            site: Site hostname without protocol (e.g., 'en.wikipedia.org',
                'nccommons.org').
            username: Optional username for authentication. For Wikipedia,
                use bot password format: 'BotName@BotPasswordName'.
            password: Optional password or bot password token.

        Raises:
            mwclient.errors.LoginError: If connection fails with credentials.
            Exception: If site connection fails entirely.

        Example:
            >>> # Anonymous connection
            >>> api = WikiAPI("en.wikipedia.org")

            >>> # Authenticated connection (login deferred)
            >>> api = WikiAPI("en.wikipedia.org", "MyBot@upload", "token123")
        """
        logger.info(f"Connecting to {site}")
        self.login_done: bool = False
        self.username: Optional[str] = username
        self.password: Optional[str] = password

        # Validate credentials: both or neither must be provided
        if not username or not password:
            if username or password:  # XOR: exactly one provided
                logger.warning("Both username and password are required for login; skipping login")
            return

        try:
            self.site: Site = Site(
                site,
                clients_useragent="NC Commons Import Bot/1.0 (https://github.com/NCCommons)",
                force_login=True,
            )
        except Exception as e:
            logger.error(f"Failed to connect to {site}: {e}")
            raise

        # Initialize upload handler with site connection
        super().__init__(self.site)

    def ensure_logged_in(self) -> None:
        """
        Ensure the user is authenticated before performing protected operations.

        Attempts to authenticate with the configured credentials. Uses a two-step
        login process:
        1. Try standard login (for regular accounts)
        2. Fall back to clientlogin (for bot passwords with 2FA-style auth)

        This method is idempotent - subsequent calls return immediately if
        already logged in.

        Side Effects:
            Sets self.login_done to True on successful authentication.

        Note:
            Bot passwords on Wikimedia wikis use a special authentication
            flow (clientlogin) rather than the standard login API.

        Warning:
            If login fails, the method logs an error but does not raise
            an exception. Callers should check self.login_done or handle
            subsequent API errors.
        """
        if self.login_done:
            return

        login_type: str = ""
        try:
            logger.info(f"Logging in as {self.username}")
            self.site.login(self.username, self.password)
            login_type = "login"
        except mwclient.errors.LoginError as e:
            # Bot passwords may require clientlogin instead of standard login
            if "BotPasswordSessionProvider" in str(e):
                self.site.clientlogin(None, username=self.username, password=self.password)
                login_type = "clientlogin"
            else:
                logger.exception(f"Login failed for {self.username}: {e}")
                return

        if self.site.logged_in:
            logger.info(f"Login (action:{login_type}) successful for {self.username}")
            self.login_done = True

    def get_page_text(self, title: str) -> str:
        """
        Retrieve the text content of a wiki page.

        Fetches the current revision's wikitext content for the specified page.

        Args:
            title: Page title (with or without namespace prefix).

        Returns:
            The page's wikitext content as a string.
            Returns empty string for non-existent pages.

        Example:
            >>> text = api.get_page_text("Wikipedia:Bot policy")
            >>> "bot" in text.lower()
            True
        """
        logger.debug(f"Fetching page: {title}")
        page = self.site.pages[title]
        return page.text()

    def save_page(self, title: str, text: str, summary: str):
        """
        Save new content to a wiki page.

        Updates the specified page with new wikitext content. Requires
        authentication - ensure_logged_in() must have succeeded.

        Args:
            title: Page title to edit.
            text: New wikitext content for the page.
            summary: Edit summary displayed in page history.

        Returns:
            The result from page.save() on success, or False if login
            is required or failed.

        Example:
            >>> result = api.save_page(
            ...     "User:Bot/Sandbox",
            ...     "== Test ==\\nHello world",
            ...     "Bot: Testing edit"
            ... )
            >>> if result:
            ...     print("Save successful")

        Note:
            This method does not handle edit conflicts. If the page has
            been edited since it was fetched, the save may fail.
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

        Supports two upload methods:
        1. URL upload: Provide url parameter (if allowed by wiki config)
        2. File upload: Provide file parameter with a file-like object

        Args:
            file: File-like object (opened in binary mode) to upload.
                Pass None when using URL upload.
            filename: Target filename on the wiki (without File: prefix).
            description: Wikitext content for the file description page.
            comment: Upload summary shown in file history.
            url: Optional URL to upload from directly (URL upload).

        Returns:
            Dictionary with upload result:
            - {'success': True} on successful upload
            - {'success': False, 'error': 'error_type'} on failure
            - May include 'duplicate_of' key for duplicate file errors

        Example:
            >>> # Upload from file
            >>> with open("image.jpg", "rb") as f:
            ...     result = api.upload(f, "image.jpg", "Description", "Bot: upload")

            >>> # Upload from URL
            >>> result = api.upload(
            ...     None, "image.jpg", "Description", "Bot: upload",
            ...     url="https://example.com/image.jpg"
            ... )
        """
        self.ensure_logged_in()

        if not self.login_done:
            logger.error("Cannot upload without successful login")
            return {"success": False, "error": "login_required"}

        return self.upload_wrap(
            file=file,
            filename=filename,
            description=description,
            comment=comment,
            url=url,
        )
