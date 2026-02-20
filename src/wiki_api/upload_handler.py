"""
MediaWiki file upload handler using raw API calls.

This module provides the UploadHandler class that implements file upload
functionality for MediaWiki sites. It uses raw API calls via mwclient's
raw_call method to have fine-grained control over upload parameters and
error handling.

Architecture Decision - Why raw API calls?
    mwclient's built-in upload method has limitations with error handling
    and doesn't properly support all upload scenarios. Using raw_call gives
    us complete control over the request parameters and response parsing.

Upload Flow:
    1. Prepare upload parameters (filename, description, comment, token)
    2. Add URL parameter for URL uploads, or file data for file uploads
    3. Send request to MediaWiki API
    4. Parse response and handle errors/warnings
    5. Return structured result dictionary
"""

import json
import logging
from typing import Any, BinaryIO, Dict, Optional, Union, cast

import mwclient
from mwclient.client import Site
from mwclient.errors import APIError

from .api_errors import (
    DuplicateFileError,
    FileExistError,
    InsufficientPermissionError,
    RateLimitedError,
    UploadByUrlDisabledError,
)

logger = logging.getLogger(__name__)


class UploadHandler:
    """
    Handles file uploads to a MediaWiki site using raw API calls.

    This class provides low-level upload functionality by directly
    calling the MediaWiki upload API. It handles various error conditions
    including duplicates, existing files, permission issues, and URL
    upload restrictions.

    Attributes:
        site: mwclient Site object for the target wiki.

    Error Handling Strategy:
        - API errors are converted to custom exceptions
        - Upload warnings (duplicates, exists) are handled gracefully
        - Rate limiting errors are surfaced for caller handling
        - All errors are logged with appropriate severity

    Example:
        >>> handler = UploadHandler(site)
        >>> with open("image.jpg", "rb") as f:
        ...     result = handler.upload_wrap(
        ...         file=f,
        ...         filename="image.jpg",
        ...         description="Test image",
        ...         comment="Bot: upload test"
        ...     )
    """

    # Error messages that indicate URL upload is disabled
    URL_DISABLED_MESSAGES: tuple[str, ...] = (
        "uploads by url are not allowed from this domain.",
        "upload by url disabled.",
    )

    def __init__(self, site: Site) -> None:
        """
        Initialize the upload handler with a wiki site connection.

        Args:
            site: mwclient Site object representing an authenticated
                connection to a MediaWiki wiki.
        """
        self.site: Site = site

    def handle_api_result(self, info: dict, kwargs: dict) -> bool:
        """
        Parse and handle the result of a MediaWiki API upload call.

        Processes the API response to detect errors and warnings,
        raising appropriate exceptions for various failure modes.

        Args:
            info: Parsed JSON response from the MediaWiki API.
            kwargs: The request parameters (for error context/logging).

        Returns:
            True if the response indicates success (no errors/warnings).

        Raises:
            UploadByUrlDisabledError: If URL upload is not allowed.
            RateLimitedError: If the server is rate limiting or throttling requests.
            InsufficientPermissionError: If user lacks upload permission.
            APIError: For other API errors.
            DuplicateFileError: If file content matches existing file.
            FileExistError: If file with same name already exists.

        Note:
            This method does not return False - all failure cases either
            raise exceptions or return True for caller handling.
        """
        if not info:
            logger.error("Empty API response")
            return False

        # Handle standard API error envelope
        if "error" in info:
            code: str = info["error"].get("code", "")
            err_info: str = info["error"].get("info", "")

            logger.error(f"API error: {info}")

            # Check for URL upload disabled
            if code == "copyuploaddisabled" or any(e in err_info.lower() for e in self.URL_DISABLED_MESSAGES):
                raise UploadByUrlDisabledError()

            # Surface rate limiting for caller to handle (e.g., retry)
            if code in {"ratelimited", "throttled"}:
                raise RateLimitedError(f"{code}: {err_info}")

            # Permission issues
            if code in {"permissiondenied", "badtoken", "mwoauth-invalid-authorization"}:
                raise InsufficientPermissionError(f"{code}: {err_info}")

            # Generic API error
            raise APIError(code, err_info, {})

        # Check upload warnings
        upload = info.get("upload", {})
        warnings = upload.get("warnings", {})

        # Handle duplicate file warning
        duplicate_list = warnings.get("duplicate", [""])
        if duplicate_list and duplicate_list[0]:
            duplicate = duplicate_list[0].replace("_", " ")
            raise DuplicateFileError(kwargs.get("filename", ""), duplicate)

        # Handle existing file warning
        if "exists" in warnings:
            raise FileExistError(kwargs.get("filename", ""))

        return True

    def mwclient_upload(
        self,
        file: Union[BinaryIO, None] = None,
        filename: Optional[str] = None,
        description: str = "",
        url: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a raw upload API call to MediaWiki.

        This method constructs and sends the upload API request,
        handling both file-based and URL-based uploads.

        Args:
            file: File-like object opened in binary mode, or None for URL uploads.
            filename: Target filename on the wiki (without File: prefix). Required.
            description: Wikitext for the file description page.
            url: Source URL for URL-based uploads. If provided, file is ignored.
            comment: Upload summary/comment. Defaults to description if not provided.

        Returns:
            Dictionary containing the parsed API response.

        Raises:
            TypeError: If filename is not provided.
            APIError: If the API returns an error (after handle_api_result processing).
            DuplicateFileError: If file is a duplicate.
            FileExistError: If file already exists.
            UploadByUrlDisabledError: If URL upload is disabled.
            InsufficientPermissionError: If user lacks permission.

        Note:
            This is a low-level method. Most callers should use upload_wrap()
            which provides better error handling and returns a standardized result.
        """
        if filename is None:
            raise TypeError("filename must be specified")

        if comment is None:
            comment = description

        text = description

        # Build API request parameters
        predata: Dict[str, Any] = {
            "action": "upload",
            "format": "json",
            "filename": filename,
            "comment": comment,
            "text": text,
            "assertuser": self.site.username,
            "token": self.site.get_token("edit"),
        }

        if url:
            predata["url"] = url

        files: Optional[Dict[str, tuple]] = None

        if file is not None:
            # Type narrowing: we know file is not None here
            file = cast(BinaryIO, file)
            file.seek(0)

            # Workaround for mwclient issue #65:
            # The Content-Disposition filename is not interpreted, so we can
            # use an ASCII-only dummy name to avoid encoding issues with
            # non-ASCII filenames.
            files = {"file": ("fake-filename", file)}

        # Execute raw API call
        data = self.site.raw_call("api", predata, files)
        info: Dict[str, Any] = json.loads(data)

        if not info:
            info = {}

        response: Dict[str, Any] = info

        # Clear deprecation notices from error field
        if "for notice of API deprecations and breaking changes." in info.get("error", {}).get("*", ""):
            info["error"]["*"] = ""

        # Check for successful upload
        if info.get("upload", {}).get("result") == "Success":
            return info

        # Handle errors and warnings
        if self.handle_api_result(info, kwargs=predata):
            response = info.get("upload", {})

        return response

    def upload_wrap(
        self,
        file: BinaryIO | None,
        filename: str,
        description: str,
        comment: str,
        url: str | None = None,
    ) -> dict:
        """
        Upload a file to the MediaWiki site with comprehensive error handling.

        This is the primary upload method that wraps mwclient_upload with
        exception handling and returns a standardized result dictionary.

        Args:
            file: File-like object (binary mode) or None for URL uploads.
            filename: Target filename on the wiki (File: prefix is stripped).
            description: Wikitext content for the file description page.
            comment: Upload summary shown in file history.
            url: Optional URL for direct URL-based upload.

        Returns:
            Dictionary with upload result:
            - {'success': True} on successful upload
            - {'success': False, 'error': 'duplicate', 'duplicate_of': 'name'}
              when file content matches existing file
            - {'success': False, 'error': 'exists'} when filename already exists
            - {'success': False, 'error': 'permission_denied'} on auth failure
            - {'success': False, 'error': 'url_disabled'} when URL upload disabled
            - {'success': False, 'error': 'error_message'} on other failures

        Example:
            >>> result = handler.upload_wrap(
            ...     file=None,
            ...     filename="image.jpg",
            ...     description="Test image",
            ...     comment="Bot: upload",
            ...     url="https://example.com/image.jpg"
            ... )
            >>> if result['success']:
            ...     print("Uploaded!")
            ... elif result['error'] == 'duplicate':
            ...     print(f"Duplicate of {result['duplicate_of']}")
        """
        # Normalize filename by removing File: prefix
        filename = filename.removeprefix("file:").removeprefix("File:")

        try:
            logger.info(f"Uploading file: {filename}")
            _response = self.mwclient_upload(
                file=file,
                filename=filename,
                description=description,
                comment=comment,
                url=url,
            )
            logger.info(f"Upload successful: {filename}")
            return {"success": True}

        except DuplicateFileError as e:
            logger.warning(f"Duplicate file detected: {e.file_name} is a duplicate of {e.duplicate_name}")
            return {
                "success": False,
                "error": "duplicate",
                "duplicate_of": e.duplicate_name,
            }

        except FileExistError as e:
            logger.warning(f"File already exists: {e.file_name}")
            return {"success": False, "error": "exists"}

        except InsufficientPermissionError:
            logger.exception(f"Insufficient permissions to upload for user {self.site.username} on {self.site.host}")
            return {"success": False, "error": "permission_denied"}
        except RateLimitedError as e:
            logger.error(f"Rate limited during upload: {str(e)}")
            return {"success": False, "error": "rate_limited", "message": str(e)}

        except UploadByUrlDisabledError:
            logger.warning(f"URL upload disabled on {self.site.host}")
            return {"success": False, "error": "url_disabled"}

        except mwclient.errors.APIError as e:
            error_msg = str(e)
            logger.error(f"Upload failed: {error_msg}")
            return {"success": False, "error": error_msg}

        except Exception as e:
            logger.exception("Unexpected error during upload")
            return {"success": False, "error": str(e)}
