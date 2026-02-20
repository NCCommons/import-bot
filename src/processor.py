"""
Wikipedia page processing operations.

This module handles finding and processing pages that contain NC templates,
coordinating the upload of files and updating of page content. The
PageProcessor class orchestrates the complete workflow for each page.

Processing Workflow:
    1. Fetch page content from Wikipedia
    2. Extract all {{NC|filename|caption}} templates
    3. For each template:
       a. Check if file already exists on Wikipedia
       b. If not, upload from NC Commons
       c. Handle duplicates and errors
    4. Replace NC templates with [[File:...]] syntax
    5. Add tracking category to page
    6. Save updated page to Wikipedia
    7. Record processing in database

Example:
    >>> from src.processor import PageProcessor
    >>> processor = PageProcessor(wiki_api, uploader, database, config)
    >>> modified = processor.process_page("Article Name")
    >>> if modified:
    ...     print("Page was updated")
"""

import logging
from typing import Dict, List, Optional

from .database import Database
from .parsers import NCTemplate, extract_nc_templates
from .uploader import FileUploader
from .wiki_api import WikipediaAPI

logger = logging.getLogger(__name__)


class PageProcessor:
    """
    Processes Wikipedia pages containing NC templates.

    This class orchestrates the complete workflow for importing files from
    NC Commons to Wikipedia pages. It coordinates file uploads, template
    replacement, page editing, and database recording.

    Attributes:
        wiki_api: Wikipedia API client for page operations.
        uploader: FileUploader for importing files from NC Commons.
        db: Database instance for recording activity.
        config: Configuration dictionary with Wikipedia settings.

    Example:
        >>> processor = PageProcessor(wiki_api, uploader, db, config)
        >>> was_modified = processor.process_page("Article with NC template")
        >>> print(f"Page modified: {was_modified}")
    """

    def __init__(
        self,
        wiki_api: WikipediaAPI,
        uploader: FileUploader,
        database: Database,
        config: dict,
    ) -> None:
        """
        Initialize page processor with dependencies.

        Args:
            wiki_api: Authenticated Wikipedia API client.
            uploader: FileUploader instance for file imports.
            database: Database for tracking processing.
            config: Configuration with 'wikipedia' settings for
                pagecategory and other options.
        """
        self.wiki_api: WikipediaAPI = wiki_api
        self.uploader: FileUploader = uploader
        self.db: Database = database
        self.config: dict = config

    def process_page(self, page_title: str) -> bool:
        """
        Process a single Wikipedia page with NC templates.

        Executes the complete import workflow for a page:
        1. Fetches page content
        2. Extracts NC templates
        3. Uploads/processes each file
        4. Replaces templates with file syntax
        5. Saves updated page

        Args:
            page_title: Title of the Wikipedia page to process.

        Returns:
            True if the page was modified (files uploaded/replaced),
            False if no changes were made (no templates, all failed,
            or fetch error).

        Example:
            >>> modified = processor.process_page("Test Article")
            >>> if modified:
            ...     print("Files were imported and page updated")

        Note:
            Even if the page fetch fails, the attempt is recorded in
            the database for tracking purposes.
        """
        logger.info(f"Processing page: {page_title}")

        templates: List[NCTemplate] = []

        # Step 1: Fetch page content
        try:
            page_text: str = self.wiki_api.get_page_text(page_title)
        except Exception:
            logger.exception(f"Failed to fetch page {page_title}")
            # Record the attempt even though it failed
            self._safe_record_page(page_title, 0, 0)
            return False

        # Step 2: Extract NC templates
        templates = extract_nc_templates(page_text)

        if not templates:
            logger.info("No NC templates found on page")
            self._safe_record_page(page_title, 0, 0)
            return False

        logger.info(f"Found {len(templates)} NC templates")

        # Step 3-4: Process each template
        replacements: Dict[str, str] = {}
        files_changed: int = 0
        files_exists: int = 0
        files_uploaded: int = 0
        files_duplicate: int = 0

        for template in templates:
            logger.info(f"Processing file: {template.filename}")

            try:
                result: Dict[str, any] = self._process_template(template)

            except Exception:
                logger.exception(f"Exception uploading file {template.filename}")
                # Continue processing other files even if one fails

            if result["action"] == "exists":
                files_changed += 1
                files_exists += 1
                replacements[template.original_text] = result["replacement"]
                logger.info(f"File already exists: {template.filename}")

            elif result["action"] == "uploaded":
                files_changed += 1
                files_uploaded += 1
                replacements[template.original_text] = result["replacement"]
                logger.info(f"File uploaded successfully: {template.filename}")

            elif result["action"] == "duplicate":
                files_changed += 1
                files_duplicate += 1
                replacements[template.original_text] = result["replacement"]
                logger.info(f"File is duplicate of {result['duplicate_of']}, using existing")

            else:
                logger.info(f"File not uploaded (error: {result.get('error')}): {template.filename}")

        # Step 5-6: Update page if there are replacements
        if replacements:
            return self._update_page(
                page_title,
                page_text,
                replacements,
                len(templates),
                files_uploaded + files_duplicate,
            )
        else:
            # No files were processed successfully
            self._safe_record_page(page_title, len(templates), 0)
            logger.info("No files were uploaded, page not modified")
            return False

    def _process_template(self, template: NCTemplate) -> Dict[str, any]:
        """
        Process a single NC template (upload file if needed).

        Args:
            template: NCTemplate to process.

        Returns:
            Dictionary with processing result:
            - {'action': 'exists', 'replacement': '[[File:...]]'}
            - {'action': 'uploaded', 'replacement': '[[File:...]]'}
            - {'action': 'duplicate', 'replacement': '...', 'duplicate_of': 'name'}
            - {'action': 'error', 'error': 'error_message'}
        """
        # First check if file already exists (avoid unnecessary uploads)
        if self.wiki_api.file_exists(template.filename):
            return {
                "action": "exists",
                "replacement": template.to_file_syntax(),
            }

        # Upload file from NC Commons
        result = self.uploader.upload_file(template.filename)

        if result.get("success"):
            return {
                "action": "uploaded",
                "replacement": template.to_file_syntax(),
            }

        elif result.get("error") in ("exists", "already_uploaded"):
            return {
                "action": "exists",
                "replacement": template.to_file_syntax(),
            }

        elif result.get("error") == "duplicate":
            duplicate_of: str = result.get("duplicate_of", template.filename)
            return {
                "action": "duplicate",
                "replacement": template.to_file_syntax(duplicate_of),
                "duplicate_of": duplicate_of,
            }

        else:
            return {
                "action": "error",
                "error": result.get("error"),
            }

    def _update_page(
        self,
        page_title: str,
        page_text: str,
        replacements: Dict[str, str],
        templates_found: int,
        files_uploaded: int,
    ) -> bool:
        """
        Update the page with file replacements and category.

        Args:
            page_title: Title of the page to update.
            page_text: Original page text.
            replacements: Dict mapping original template text to file syntax.
            templates_found: Number of templates found (for logging).
            files_uploaded: Number of files uploaded (for database).

        Returns:
            True if page was saved successfully, False otherwise.
        """
        # Apply replacements
        new_text: str = self._apply_replacements(page_text, replacements)

        # Add tracking category if not present
        category: str = f"[[{self.config['wikipedia']['pagecategory']}]]"
        if category not in new_text:
            new_text += f"\n{category}"
            logger.debug("Added NC Commons category to page")

        # Save page
        summary: str = f"Bot: Imported {len(replacements)} file(s) from NC Commons"
        try:
            self.wiki_api.save_page(page_title, new_text, summary)
        except Exception:
            logger.exception(f"Failed to save page {page_title}")
            self._safe_record_page(page_title, templates_found, files_uploaded)
            return False

        # Record successful processing
        self._safe_record_page(page_title, templates_found, files_uploaded)
        logger.info(f"Page updated: {len(replacements)} files imported")
        return True

    def _apply_replacements(self, text: str, replacements: Dict[str, str]) -> str:
        """
        Apply template replacements to page text.

        Performs simple string replacement for each template found.

        Args:
            text: Original page text.
            replacements: Dictionary mapping original template text to
                new file syntax.

        Returns:
            Updated page text with all replacements applied.

        Note:
            This uses simple string replacement, which works correctly
            because original_text contains the exact wikitext from the
            parsed template.
        """
        new_text: str = text

        for original, replacement in replacements.items():
            new_text = new_text.replace(original, replacement)
            logger.debug(f"Replaced: {original[:50]}... -> {replacement[:50]}...")

        return new_text

    def _safe_record_page(
        self,
        page_title: str,
        templates_found: int,
        files_uploaded: int,
    ) -> None:
        """
        Safely record page processing in database (never raises).

        Wraps database recording in try/except to ensure processing
        continues even if database operations fail.

        Args:
            page_title: Title of the processed page.
            templates_found: Number of NC templates found.
            files_uploaded: Number of files successfully uploaded.
        """
        try:
            self.db.record_page_processing(page_title, self.wiki_api.lang, templates_found, files_uploaded)
        except Exception as e:
            logger.error(f"Failed to record page processing: {e}")
