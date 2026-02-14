""" """

from mwclient.errors import APIError


class UploadError(APIError):
    """Raised when an upload operation fails."""

    pass


class DuplicateFileError(APIError):
    """Raised when a duplicate file is detected during upload."""

    pass


class UploadByUrlDisabledError(APIError):
    """Raised when URL upload is disabled for a file."""

    pass
