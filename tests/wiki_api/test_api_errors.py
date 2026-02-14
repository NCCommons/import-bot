"""
Tests for api_errors module.
"""

import pytest
from src.wiki_api.api_errors import (
    DuplicateFileError,
    FileExistError,
    InsufficientPermission,
    UploadByUrlDisabledError,
)


class TestDuplicateFileError:
    """Tests for DuplicateFileError class."""

    def test_duplicate_file_error_attributes(self):
        """Test DuplicateFileError stores file attributes correctly."""
        error = DuplicateFileError("test_file.jpg", "existing_file.jpg")

        assert error.file_name == "test_file.jpg"
        assert error.duplicate_name == "existing_file.jpg"

    def test_duplicate_file_error_str(self):
        """Test DuplicateFileError __str__ method."""
        error = DuplicateFileError("test_file.jpg", "existing_file.jpg")

        expected = "The file 'test_file.jpg' already exists in a different name: 'existing_file.jpg'."
        assert str(error) == expected


class TestFileExistError:
    """Tests for FileExistError class."""

    def test_file_exists_error_attribute(self):
        """Test FileExistError stores file name correctly."""
        error = FileExistError("existing_file.jpg")

        assert error.file_name == "existing_file.jpg"

    def test_file_exists_error_str(self):
        """Test FileExistError __str__ method."""
        error = FileExistError("existing_file.jpg")

        expected = "The file 'existing_file.jpg' already exists. Set ignore=True to overwrite it."
        assert str(error) == expected


class TestInsufficientPermission:
    """Tests for InsufficientPermission class."""

    def test_insufficient_permission_is_exception(self):
        """Test InsufficientPermission is a valid exception."""
        error = InsufficientPermission()

        assert isinstance(error, Exception)

    def test_insufficient_permission_can_be_raised(self):
        """Test InsufficientPermission can be raised and caught."""
        with pytest.raises(InsufficientPermission):
            raise InsufficientPermission()


class TestUploadByUrlDisabledError:
    """Tests for UploadByUrlDisabledError class."""

    def test_upload_by_url_disabled_is_exception(self):
        """Test UploadByUrlDisabledError is a valid exception."""
        error = UploadByUrlDisabledError()

        assert isinstance(error, Exception)

    def test_upload_by_url_disabled_can_be_raised(self):
        """Test UploadByUrlDisabledError can be raised and caught."""
        with pytest.raises(UploadByUrlDisabledError):
            raise UploadByUrlDisabledError()
