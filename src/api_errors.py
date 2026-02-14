"""
"""


class DuplicateFileError(Exception):
    """Raised when a duplicate file is detected during upload."""
    pass


class UploadByUrlDisabledError(Exception):
    """Raised when URL upload is disabled for a file."""
    pass
