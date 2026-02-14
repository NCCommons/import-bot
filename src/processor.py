"""
Wikipedia page processing operations.

This module handles finding and processing pages that contain NC templates,
coordinating the upload of files and updating of page content.
"""

import logging

from .database import Database
from .parsers import extract_nc_templates
from .uploader import FileUploader
from .wiki_api import WikipediaAPI

logger = logging.getLogger(__name__)


class PageProcessor:
    """
    Processes Wikipedia pages containing NC templates.

    Finds NC templates, uploads the referenced files, and replaces templates
    with standard Wikipedia file syntax.
    """

    def __init__(self, wiki_api: WikipediaAPI, uploader: FileUploader, database: Database, config: dict):
        """
        Initialize page processor.

        Args:
            wiki_api: Wikipedia API client
            uploader: File uploader instance
            database: Database instance
            config: Configuration dictionary
        """
        self.wiki_api = wiki_api
        self.uploader = uploader
        self.db = database
        self.config = config

    def process_page(self, page_title: str) -> bool:
        """
        Process a single Wikipedia page.

        Workflow:
        1. Fetch page content
        2. Extract NC templates
        3. Upload files
        4. Replace templates
        5. Add category
        6. Save page
        7. Record in database

        Args:
            page_title: Title of the page to process

        Returns:
            True if page was modified, False otherwise
        """
        logger.info(f"Processing page: {page_title}")

        templates: list = []

        # Get page content
        page_text = self.wiki_api.get_page_text(page_title)

        # Extract NC templates
        templates = extract_nc_templates(page_text)

        if not templates:
            logger.info("No NC templates found on page")
            self.db.record_page_processing(page_title, self.wiki_api.lang, 0, 0)
            return False

        logger.info(f"Found {len(templates)} NC templates")

        # Process each template
        replacements = {}
        files_changed = 0
        files_exists = 0
        files_uploaded = 0
        files_duplicate = 0

        for template in templates:
            logger.info(f"Processing file: {template.filename}")

            # Upload file
            result = self.uploader.upload_file(template.filename)

            if result.get("success"):
                files_changed += 1
                files_uploaded += 1
                # Map original template to file syntax
                replacements[template.original_text] = template.to_file_syntax()
                logger.info(f"File uploaded successfully: {template.filename}")

            elif result.get("error") == "exists":
                files_changed += 1
                files_exists += 1
                # Map original template to file syntax
                replacements[template.original_text] = template.to_file_syntax()
                logger.info(f"File already exists: {template.filename}")

            elif result.get("error") == "duplicate":
                # File is a duplicate, use the existing file's name
                files_changed += 1
                files_duplicate += 1
                duplicate_of = result.get("duplicate_of", template.filename)
                # Create replacement with the duplicate filename
                replacements[template.original_text] = template.to_file_syntax(duplicate_of)

                logger.info(f"File is duplicate of {duplicate_of}, using existing file: {duplicate_of}")
            else:
                logger.info(f"File not uploaded (error: {result.get('error')}): {template.filename}")

        # If any files were uploaded, update the page
        if replacements:
            new_text = self._apply_replacements(page_text, replacements)

            # Add category if not present
            category = f"[[{self.config['wikipedia']['category']}]]"
            if category not in new_text:
                new_text += f"\n{category}"
                logger.debug("Added NC Commons category to page")

            # Save page
            summary = f"Bot: Imported {files_changed} file(s) from NC Commons"
            self.wiki_api.save_page(page_title, new_text, summary)

            # Record successful page processing after successful save
            self.db.record_page_processing(page_title, self.wiki_api.lang, len(templates), files_changed)

            logger.info(f"Page updated: {files_changed} files imported")
            return True
        else:
            # Record that processing was skipped (no files uploaded)
            self.db.record_page_processing(page_title, self.wiki_api.lang, len(templates), 0)
            logger.info("No files were uploaded, page not modified")
            return False

    def _apply_replacements(self, text: str, replacements: dict) -> str:
        """
        Apply template replacements to page text.

        Args:
            text: Original page text
            replacements: Dictionary mapping original templates to new syntax

        Returns:
            Updated page text with replacements applied
        """
        new_text = text

        for original, replacement in replacements.items():
            new_text = new_text.replace(original, replacement)
            logger.debug(f"Replaced: {original[:50]}... -> {replacement[:50]}...")

        return new_text
