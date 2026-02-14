"""
MediaWiki API wrapper using mwclient.

This module provides classes for interacting with NC Commons and Wikipedia
through the MediaWiki API.
"""

import json
import logging
from typing import Any, BinaryIO, Dict, Optional, Union, cast

import mwclient
from mwclient.client import Site

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

    def mwclient_upload(
        self,
        file: Union[str, BinaryIO, None] = None,
        filename: Optional[str] = None,
        description: str = "",
        url: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Upload a file to the site.
        """

        if filename is None:
            raise TypeError("filename must be specified")

        if comment is None:
            comment = description
            text = None
        else:
            comment = comment
            text = description

        if file is not None:
            if not hasattr(file, "read"):
                file = open(file, "rb")

            # Narrowing the type of file from Union[str, BinaryIO, None]
            # to BinaryIO, since we know it's not a str at this point.
            file = cast(BinaryIO, file)
            file.seek(0)

        predata = {
            "action": "upload",
            "format": "json",
            "filename": filename,
            "comment": comment,
            "text": text,
            "token": self.site.get_token("edit"),
        }
        if url:
            predata["url"] = url

        postdata = predata
        files = None
        if file is not None:
            # Workaround for https://github.com/mwclient/mwclient/issues/65
            # ----------------------------------------------------------------
            # Since the filename in Content-Disposition is not interpreted,
            # we can send some ascii-only dummy name rather than the real
            # filename, which might contain non-ascii.
            files = {"file": ("fake-filename", file)}

        data = self.site.raw_call("api", postdata, files)
        info = json.loads(data)

        if not info:
            info = {}

        if self.site.handle_api_result(info, kwargs=predata):
            response = info.get("upload", {})

        if file is not None:
            file.close()
        return response

    def upload(self, file, filename: str, description: str, comment: str, url: Optional[str] = None) -> dict:
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
        try:
            logger.info(f"Uploading file: {filename}")
            result = self.mwclient_upload(
                file=file,
                filename=filename,
                description=description,
                comment=comment,
                url=url,
            )
            logger.info(f"Upload successful: {filename}")
            return {"success": True}

        except (mwclient.errors.APIError, UploadError) as e:
            error_msg = str(e).lower()

            if "duplicate" in error_msg:
                logger.warning(f"File is duplicate: {filename}")
                return {"success": False, "error": "duplicate"}

            elif "upload by url disabled" in error_msg or "copyuploaddisabled" in error_msg:
                logger.warning(f"URL upload disabled in {self.site.host}")
                return {"success": False, "error": "url_disabled"}

            logger.error(f"Upload failed: {e}")
            return {"success": False, "error": str(e)}
