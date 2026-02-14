"""
File upload operations from NC Commons to Wikipedia.

This module handles downloading files from NC Commons and uploading them
to Wikipedia, with appropriate error handling and database recording.
"""

import logging
import urllib.parse
import urllib.request

from .database import Database
from .parsers import remove_categories
from .wiki_api import NCCommonsAPI, WikipediaAPI
from .utils.temporary_handler import TemporaryDownloadFile

logger = logging.getLogger(__name__)


class FileUploader:
    """
    Handles file uploads from NC Commons to Wikipedia.

    Manages the complete upload workflow including fetching from NC Commons,
    processing descriptions, uploading to Wikipedia, and recording results.
    """

    def __init__(self, nc_api: NCCommonsAPI, wiki_api: WikipediaAPI, database: Database, config: dict):
        """
        Initialize file uploader.

        Args:
            nc_api: NC Commons API client
            wiki_api: Wikipedia API client
            database: Database instance for recording uploads
            config: Configuration dictionary
        """
        self.nc_api = nc_api
        self.wiki_api = wiki_api
        self.db = database
        self.config = config

    def upload_file(self, filename: str) -> dict:
        """
        Upload a file from NC Commons to Wikipedia.

        Workflow:
        1. Check if already uploaded
        2. Fetch file info from NC Commons
        3. Process file description
        4. Try URL upload
        5. Fall back to file upload if needed
        6. Record result in database

        Args:
            filename: Name of the file to upload

        Returns:
            Dictionary with 'success' key and optional 'duplicate_of' key
            - {'success': True} if upload succeeded
            - {'success': False, 'error': 'already_uploaded'} if file was already uploaded
            - {'success': False, 'error': 'duplicate', 'duplicate_of': 'filename'} if duplicate detected
            - {'success': False, 'error': 'error_message'} if upload failed
        """
        lang = self.wiki_api.lang

        # Check if already uploaded
        if self.db.is_file_uploaded(filename, lang):
            logger.info(f"File already uploaded: {filename}")
            return {"success": False, "error": "already_uploaded"}

        # try:
        # Get file information from NC Commons
        logger.info(f"Fetching file from NC Commons: {filename}")
        file_url = self.nc_api.get_image_url(filename)
        description = self.nc_api.get_file_description(filename)

        # Process description
        description = self._process_description(description)

        # Upload comment from config
        comment = self.config["wikipedia"]["upload_comment"]

        # Try URL upload first (faster, doesn't require download)
        result = self.wiki_api.upload_from_url(
            filename=filename,
            url=file_url,
            description=description,
            comment=comment,
        )

        if result.get("success"):
            self.db.record_upload(filename, lang, "success")
            logger.info(f"Upload successful (URL method): {filename}")
            return {"success": True}

        # URL upload not allowed or failed, try file upload
        error_msg = result.get("error")

        if error_msg == "url_disabled":
            logger.info("URL upload not allowed.")
            return self._upload_via_download(filename, file_url, description, comment, lang)
        elif error_msg == "duplicate":
            duplicate_of = result.get("duplicate_of", "")
            logger.warning(f"Duplicate file detected: {filename} is a duplicate of {duplicate_of}")
            self.db.record_upload(filename, lang, "duplicate", f"duplicate_of:{duplicate_of}")
            return {"success": False, "error": "duplicate", "duplicate_of": duplicate_of}
        else:
            logger.error(f"Upload failed for {filename}: {error_msg}")
            self.db.record_upload(filename, lang, "failed", error_msg)
            return {"success": False, "error": error_msg}

    def _upload_via_download(self, filename: str, url: str, description: str, comment: str, language: str) -> dict:
        """
        Download file from URL then upload to Wikipedia.

        Fallback method when direct URL upload is not allowed.

        Args:
            filename: Target filename
            url: Source URL
            description: File description
            comment: Upload comment
            language: Language code

        Returns:
            Dictionary with 'success' key and optional 'duplicate_of' key
            - {'success': True} if upload succeeded
            - {'success': False, 'error': 'duplicate', 'duplicate_of': 'filename'} if duplicate detected
            - {'success': False, 'error': 'error_message'} if upload failed
        """
        logger.info(f"Attempting file upload for {filename} after URL upload failed")
        # Validate URL scheme
        parsed_url = urllib.parse.urlparse(url)
        if parsed_url.scheme != "https":
            raise ValueError(f"Invalid URL scheme '{parsed_url.scheme}' for {filename}: only HTTPS is allowed")

        # Download to temporary file
        logger.info(f"Downloading file: {filename}")

        with TemporaryDownloadFile(suffix=".tmp") as temp_path:
            urllib.request.urlretrieve(url, temp_path)
            logger.debug(f"Downloaded to: {temp_path}")

            # Upload from file
            result = self.wiki_api.upload_from_file(
                filename=filename,
                filepath=temp_path,
                description=description,
                comment=comment,
            )

        error = result.get("error", "unknown error")
        error_msg = str(error).lower()

        if result.get("success"):
            self.db.record_upload(filename, language, "success")
            logger.info(f"Upload successful (file method): {filename}")
            return {"success": True}
        elif error_msg == "duplicate":
            duplicate_of = result.get("duplicate_of", "")
            logger.warning(f"Duplicate file detected: {filename} is a duplicate of {duplicate_of}")
            self.db.record_upload(filename, language, "duplicate", f"duplicate_of:{duplicate_of}")
            return {"success": False, "error": "duplicate", "duplicate_of": duplicate_of}
        else:
            logger.error(f"Upload failed for {filename}: {error_msg}")
            self.db.record_upload(filename, language, "failed", error_msg)
            return {"success": False, "error": error_msg}

    def _process_description(self, description: str) -> str:
        """
        Process file description for upload to Wikipedia.

        Removes existing categories and adds NC Commons import category.

        Args:
            description: Original file description from NC Commons

        Returns:
            Processed description ready for Wikipedia
        """
        # Remove all existing categories
        processed = remove_categories(description)

        # Add NC Commons category
        category = self.config["wikipedia"]["filecategory"]
        processed += f"\n[[{category}]]"

        return processed.strip()
