"""
Wikipedia-specific API operations.

This module provides the WikipediaAPI class that extends WikiAPI with
Wikipedia-specific functionality, including finding pages with specific
templates and checking file existence.

Wikipedia Considerations:
    - Uses language-specific subdomains (e.g., en.wikipedia.org, ar.wikipedia.org)
    - Bot passwords require special authentication flow (clientlogin)
    - URL uploads may be restricted based on $wgAllowCopyUploads configuration
"""

import logging
from typing import List

from .main_api import WikiAPI

logger = logging.getLogger(__name__)


class WikipediaAPI(WikiAPI):
    """
    API wrapper for Wikipedia operations.

    Extends WikiAPI with methods specific to Wikipedia workflows,
    including finding pages that transclude templates, checking file
    existence, and performing uploads via URL or file.

    Attributes:
        lang: The Wikipedia language code (e.g., 'en', 'ar', 'fr').

    Example:
        >>> api = WikipediaAPI("en", "MyBot@upload", "password_token")
        >>> pages = api.get_pages_with_template("Template:NC", limit=100)
        >>> for page in pages:
        ...     text = api.get_page_text(page)
        ...     # Process page...
    """

    def __init__(self, language_code: str, username: str, password: str) -> None:
        """
        Initialize Wikipedia API connection for a specific language.

        Args:
            language_code: Wikipedia language code determining the subdomain.
                Common codes: 'en' (English), 'ar' (Arabic), 'fr' (French),
                'de' (German), 'es' (Spanish), etc.
            username: Wikipedia username. For bot operations, use bot password
                format: 'BotName@BotPasswordName'.
            password: Bot password token (not the account password).

        Example:
            >>> api = WikipediaAPI("ar", "MyBot@import", "abc123xyz")
            >>> # Connects to ar.wikipedia.org
        """
        self.lang: str = language_code
        site = f"{language_code}.wikipedia.org"
        super().__init__(site, username, password)

    def get_pages_with_template(self, template: str, limit: int = 5000) -> List[str]:
        """
        Get all pages that transclude (embed) a specific template.

        Uses the MediaWiki embeddedin API to find pages that contain
        a given template. This is useful for finding pages with the
        {{NC}} template that need processing.

        Args:
            template: Template name with or without 'Template:' prefix.
                Both "Template:NC" and "NC" are valid.
            limit: Maximum number of pages to retrieve. Default: 5000.
                This prevents unbounded queries on large result sets.

        Returns:
            List of page titles (strings) that transclude the template.
            The list may be shorter than `limit` if fewer pages exist.

        Example:
            >>> pages = api.get_pages_with_template("Template:NC", limit=100)
            >>> len(pages)
            42
            >>> pages[:3]
            ['Article1', 'Article2', 'Article3']

        Note:
            The embeddedin API may not include redirects to the template.
            Pages are returned in an arbitrary order (not alphabetical).
        """
        # Normalize template name
        if not template.startswith("Template:"):
            template = f"Template:{template}"

        logger.info(f"Finding pages with template: {template}")

        template_page = self.site.pages[template]
        pages: List[str] = [page.name for page in template_page.embeddedin(max_items=limit)]

        logger.info(f"Found {len(pages)} pages")
        return pages

    def upload_from_url(
        self,
        filename: str,
        url: str,
        description: str,
        comment: str,
    ) -> dict:
        """
        Upload a file to Wikipedia directly from a URL.

        Uses MediaWiki's URL upload feature to import files without
        downloading them locally first. This is more efficient but
        may be disabled on some wikis.

        Args:
            filename: Target filename on Wikipedia (without File: prefix).
            url: Source URL of the file to upload. Must be accessible
                from Wikipedia's servers.
            description: Wikitext for the file description page.
            comment: Upload summary shown in file history.

        Returns:
            Dictionary with upload result:
            - {'success': True} on success
            - {'success': False, 'error': 'url_disabled'} if URL uploads disabled
            - {'success': False, 'error': 'duplicate', 'duplicate_of': 'name'}
              if file is a duplicate
            - {'success': False, 'error': 'error_message'} on other failures

        Example:
            >>> result = api.upload_from_url(
            ...     "photo.jpg",
            ...     "https://nccommons.org/images/photo.jpg",
            ...     "== Summary ==\\nImported from NC Commons",
            ...     "Bot: Import from NC Commons"
            ... )
            >>> if result['success']:
            ...     print("Upload successful")

        Note:
            URL upload requires the 'upload_by_url' user right. This is
            typically granted to bot accounts but may be restricted.
        """
        logger.info(f"Uploading from URL: {filename}")

        result = self.upload(
            file=None,
            filename=filename,
            description=description,
            comment=comment,
            url=url,
        )

        if result.get("success"):
            logger.info(f"Upload successful: {filename}")

        return result

    def upload_from_file(
        self,
        filename: str,
        filepath: str,
        description: str,
        comment: str,
    ) -> dict:
        """
        Upload a file to Wikipedia from the local filesystem.

        Fallback method when URL upload is disabled or fails. Downloads
        the file locally first, then uploads it to Wikipedia.

        Args:
            filename: Target filename on Wikipedia (without File: prefix).
            filepath: Local filesystem path to the file to upload.
            description: Wikitext for the file description page.
            comment: Upload summary shown in file history.

        Returns:
            Dictionary with upload result:
            - {'success': True} on success
            - {'success': False, 'error': 'duplicate', 'duplicate_of': 'name'}
              if file is a duplicate
            - {'success': False, 'error': 'error_message'} on failure

        Raises:
            FileNotFoundError: If the local file does not exist.
            IOError: If the file cannot be read.

        Example:
            >>> # After downloading file to temp location
            >>> result = api.upload_from_file(
            ...     "photo.jpg",
            ...     "/tmp/downloaded_photo.jpg",
            ...     "== Summary ==\\nImported from NC Commons",
            ...     "Bot: Import from NC Commons"
            ... )
        """
        logger.info(f"Uploading from file: {filename}")

        with open(filepath, "rb") as f:
            result = self.upload(
                file=f,
                filename=filename,
                description=description,
                comment=comment,
            )

        if result.get("success"):
            logger.info(f"Upload successful: {filename}")

        return result

    def file_exists(self, filename: str) -> bool:
        """
        Check if a file already exists on Wikipedia.

        Queries the wiki to determine if a file with the given name
        has already been uploaded. This is used to skip unnecessary
        upload attempts.

        Args:
            filename: Filename to check (with or without File: prefix).

        Returns:
            True if the file exists on Wikipedia, False otherwise.

        Example:
            >>> api.file_exists("Commons-logo.svg")
            True
            >>> api.file_exists("NonExistentFile12345.jpg")
            False

        Note:
            This check does not verify file content, only existence.
            A file with the same name but different content will still
            return True.
        """
        logger.info(f"Checking if file exists: {filename}")

        file_page = self.site.images[filename]
        exists: bool = file_page.exists

        if exists:
            logger.info(f"File exists: {filename}")
        else:
            logger.info(f"File does not exist: {filename}")

        return exists
