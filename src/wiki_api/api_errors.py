""" """

from mwclient.errors import APIError


class DuplicateFileError(Exception):
    """
    Raised when trying to upload a file that duplicates an existing file.
    """

    def __init__(self, file_name: str, duplicate_name: str):
        self.file_name = file_name
        self.duplicate_name = duplicate_name

    def __str__(self):
        return f"The file '{self.file_name}' already exists in a different name: '{self.duplicate_name}'."


class FileExistsError(Exception):
    """
    Raised when trying to upload a file that already exists.

    See also: https://www.mediawiki.org/wiki/API:Upload#Upload_warnings
    """

    def __init__(self, file_name: str):
        self.file_name = file_name

    def __str__(self):
        return f"The file '{self.file_name}' already exists. Set ignore=True to overwrite it."


class InsufficientPermission(Exception):
    pass


class UploadByUrlDisabledError(Exception):
    """
    Raised when URL upload is disabled for a file.
    {'error': {'code': 'copyuploaddisabled', 'info': 'Upload by URL disabled.', '*': ''}}
    """

    pass
