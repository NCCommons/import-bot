"""
MediaWiki API wrapper using mwclient.

This module provides classes for interacting with NC Commons and Wikipedia
through the MediaWiki API.
"""

import mwclient
import logging
import time
from typing import List, Dict, Optional
from functools import wraps

logger = logging.getLogger(__name__)

# Retry decorator implementation
def retry(max_attempts: int = 3, delay: int = 5, backoff: int = 2):
    """
    Decorator to retry functions with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay in seconds
        backoff: Multiplier for exponential backoff

    Returns:
        Decorated function that retries on failure
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            current_delay = delay

            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempt += 1
                    if attempt >= max_attempts:
                        logger.error(f"All {max_attempts} attempts failed for {func.__name__}")
                        raise

                    logger.warning(
                        f"Attempt {attempt}/{max_attempts} failed for {func.__name__}: {e}. "
                        f"Retrying in {current_delay}s..."
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff

        return wrapper
    return decorator


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
        self.site = mwclient.Site(site)

        if username and password:
            logger.info(f"Logging in as {username}")
            self.site.login(username, password)

    @retry(max_attempts=3, delay=5, backoff=2)
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

    @retry(max_attempts=3, delay=5, backoff=2)
    def save_page(self, title: str, text: str, summary: str):
        """
        Save content to a page.

        Args:
            title: Page title
            text: New page content
            summary: Edit summary
        """
        logger.info(f"Saving page: {title}")
        page = self.site.pages[title]
        page.save(text, summary=summary)


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
        super().__init__('nccommons.org', username, password)

    @retry(max_attempts=3, delay=5, backoff=2)
    def get_image_url(self, filename: str) -> str:
        """
        Get the direct URL to an image file.

        Args:
            filename: Image filename (with or without 'File:' prefix)

        Returns:
            Direct URL to the image file
        """
        if not filename.startswith('File:'):
            filename = f'File:{filename}'

        logger.debug(f"Getting image URL for: {filename}")
        page = self.site.pages[filename]
        return page.imageinfo['url']

    def get_file_description(self, filename: str) -> str:
        """
        Get the file description page content.

        Args:
            filename: Image filename (with or without 'File:' prefix)

        Returns:
            File description page wikitext
        """
        if not filename.startswith('File:'):
            filename = f'File:{filename}'

        return self.get_page_text(filename)


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
        site = f'{language_code}.wikipedia.org'
        super().__init__(site, username, password)

    @retry(max_attempts=3, delay=5, backoff=2)
    def get_pages_with_template(self, template: str, limit: int = 5000) -> List[str]:
        """
        Get all pages that transclude a template.

        Args:
            template: Template name (with or without 'Template:' prefix)
            limit: Maximum number of pages to retrieve

        Returns:
            List of page titles
        """
        if not template.startswith('Template:'):
            template = f'Template:{template}'

        logger.info(f"Finding pages with template: {template}")

        template_page = self.site.pages[template]
        pages = [page.name for page in template_page.embeddedin(limit=limit)]

        logger.info(f"Found {len(pages)} pages")
        return pages

    @retry(max_attempts=3, delay=5, backoff=2)
    def upload_from_url(self, filename: str, url: str, description: str, comment: str) -> bool:
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

            result = self.site.upload(
                file=None,
                filename=filename,
                description=description,
                comment=comment,
                url=url
            )

            logger.info(f"Upload successful: {filename}")
            return True

        except mwclient.errors.APIError as e:
            error_msg = str(e).lower()

            if 'duplicate' in error_msg:
                logger.warning(f"File is duplicate: {filename}")
                return False

            logger.error(f"Upload failed: {e}")
            raise

    @retry(max_attempts=3, delay=5, backoff=2)
    def upload_from_file(self, filename: str, filepath: str, description: str, comment: str) -> bool:
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

            with open(filepath, 'rb') as f:
                result = self.site.upload(
                    file=f,
                    filename=filename,
                    description=description,
                    comment=comment
                )

            logger.info(f"Upload successful: {filename}")
            return True

        except mwclient.errors.APIError as e:
            error_msg = str(e).lower()

            if 'duplicate' in error_msg:
                logger.warning(f"File is duplicate: {filename}")
                return False

            logger.error(f"Upload failed: {e}")
            raise
