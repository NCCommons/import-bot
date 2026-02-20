"""
Custom exception classes for MediaWiki API operations.

This module defines specialized exception types for handling various error
conditions that can occur during interactions with MediaWiki APIs, including
upload failures, permission issues, and file conflicts.

Exception Hierarchy:
    Exception
    ├── DuplicateFileError      - File content matches existing file
    ├── FileExistError          - File with same name already exists
    ├── InsufficientPermissionError - User lacks required permissions
    ├── RateLimitedError            - Rate limiting or throttling in effect
    └── UploadByUrlDisabledError    - URL upload feature is disabled

Example:
    >>> from src.wiki_api.api_errors import FileExistError
    >>> try:
    ...     upload_file("example.jpg")
    ... except FileExistError as e:
    ...     print(f"Cannot upload: {e.file_name}")
    Cannot upload: example.jpg
"""

from typing import Optional


class DuplicateFileError(Exception):
    """
    Raised when attempting to upload a file that is a duplicate of an existing file.

    This occurs when the MediaWiki API detects that the file content (via hash)
    matches an already uploaded file, even if the filename differs.

    Attributes:
        file_name: The name of the file being uploaded.
        duplicate_name: The name of the existing file that has identical content.

    Example:
        >>> try:
        ...     api.upload(file, "new_image.jpg", ...)
        ... except DuplicateFileError as e:
        ...     print(f"Use existing file: {e.duplicate_name}")
        ...     # Update page to reference the existing file instead
    """

    def __init__(self, file_name: str, duplicate_name: str) -> None:
        """
        Initialize DuplicateFileError with file information.

        Args:
            file_name: The name of the file attempted to be uploaded.
            duplicate_name: The name of the existing duplicate file on the wiki.
        """
        self.file_name: str = file_name
        self.duplicate_name: str = duplicate_name
        super().__init__(file_name, duplicate_name)

    def __str__(self) -> str:
        """
        Return a human-readable error message.

        Returns:
            A formatted string describing the duplicate file situation.
        """
        return f"The file '{self.file_name}' already exists in a different name: '{self.duplicate_name}'."


class FileExistError(Exception):
    """
    Raised when attempting to upload a file that already exists with the same name.

    This exception indicates that a file with the exact same filename already exists
    on the wiki. To overwrite, the upload must be called with ignore=True.

    Note:
        For MediaWiki upload warnings, see:
        https://www.mediawiki.org/wiki/API:Upload#Upload_warnings

    Attributes:
        file_name: The name of the file that already exists.

    Example:
        >>> try:
        ...     api.upload(file, "existing.jpg", ...)
        ... except FileExistError as e:
        ...     # Option 1: Skip upload, use existing file
        ...     # Option 2: Re-upload with ignore=True to overwrite
        ...     pass
    """

    def __init__(self, file_name: str) -> None:
        """
        Initialize FileExistError with the conflicting filename.

        Args:
            file_name: The name of the file that already exists on the wiki.
        """
        self.file_name: str = file_name
        super().__init__(file_name)

    def __str__(self) -> str:
        """
        Return a human-readable error message with overwrite hint.

        Returns:
            A formatted string indicating the file exists and how to overwrite.
        """
        return f"The file '{self.file_name}' already exists. " f"Set ignore=True to overwrite it."


class InsufficientPermissionError(Exception):
    """
    Raised when the user lacks required permissions to perform an action.

    This exception is raised when the MediaWiki API returns a permission-related
    error code such as 'permissiondenied', 'badtoken', or 'mwoauth-invalid-authorization'.

    Common causes:
        - User is not logged in
        - User account lacks 'upload' or 'edit' rights
        - Bot password has insufficient scopes
        - CSRF token is invalid or expired

    Example:
        >>> try:
        ...     api.upload(file, "image.jpg", ...)
        ... except InsufficientPermissionError:
        ...     logger.error("Check bot permissions and credentials")
        ...     raise
    """

    def __init__(self, message: Optional[str] = None) -> None:
        """
        Initialize InsufficientPermissionError with optional context.

        Args:
            message: Optional additional context about the permission failure.
        """
        self.message: Optional[str] = message
        super().__init__(message or "Insufficient permissions to perform this action.")

    def __str__(self) -> str:
        """
        Return a human-readable error message.

        Returns:
            A string describing the permission issue.
        """
        return self.message or "Insufficient permissions to perform this action."


class RateLimitedError(Exception):
    """
    Raised when API requests are rate limited or throttled by the server.

    This exception occurs when the MediaWiki API returns a rate limiting error
    such as 'ratelimited' or 'throttled'. Callers should catch this exception
    and implement appropriate retry logic with exponential backoff.

    Attributes:
        message: The error message from the API, including the 'info' field.

    Example:
        >>> try:
        ...     api.upload(file, "image.jpg", ...)
        ... except RateLimitedError as e:
        ...     logger.warning(f"Rate limited: {e}")
        ...     time.sleep(RETRY_DELAY)
        ...     retry_upload()
    """

    def __init__(self, message: Optional[str] = None) -> None:
        """
        Initialize RateLimitedError with optional context.

        Args:
            message: The error message from the API, typically containing the 'info' field.
        """
        self.message: Optional[str] = message
        super().__init__(message or "Rate limited. Please try again later.")

    def __str__(self) -> str:
        """
        Return a human-readable error message.

        Returns:
            A string describing the rate limiting issue.
        """
        return self.message or "Rate limited. Please try again later."


class UploadByUrlDisabledError(Exception):
    """
    Raised when URL-based file upload is disabled on the target wiki.

    This exception occurs when attempting to use the 'url' parameter in the
    upload API but the wiki has disabled this feature. The typical API response
    that triggers this exception looks like:

        {'error': {'code': 'copyuploaddisabled', 'info': 'Upload by URL disabled.', '*': ''}}

    Handling Strategy:
        When this error is caught, the uploader should fall back to downloading
        the file locally and then uploading it via the standard file upload method.

    Example:
        >>> try:
        ...     result = api.upload_from_url("image.jpg", url, ...)
        ... except UploadByUrlDisabledError:
        ...     # Fallback: download and upload as file
        ...     local_path = download_file(url)
        ...     result = api.upload_from_file("image.jpg", local_path, ...)
    """

    def __init__(self, message: Optional[str] = None) -> None:
        """
        Initialize UploadByUrlDisabledError.

        Args:
            message: Optional additional context (default: standard disabled message).
        """
        self.message: Optional[str] = message or "Upload by URL is disabled on this wiki."
        super().__init__(self.message)

    def __str__(self) -> str:
        """
        Return a human-readable error message.

        Returns:
            A string indicating that URL upload is disabled.
        """
        return self.message
