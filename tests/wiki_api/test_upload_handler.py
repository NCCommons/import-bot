"""
Tests for wiki API module.
"""

from io import BytesIO
from unittest.mock import Mock, mock_open, patch

import mwclient.errors
import pytest
from src.wiki_api import WikipediaAPI
from src.wiki_api.api_errors import (
    DuplicateFileError,
    FileExistError,
    InsufficientPermissionError,
    UploadByUrlDisabledError,
)


class TestHandleApiResult:
    """Tests for UploadHandler.handle_api_result method."""

    def test_empty_api_response(self):
        """Test handling of empty API response."""
        from unittest.mock import Mock

        from src.wiki_api.upload_handler import UploadHandler

        mock_site = Mock()
        handler = UploadHandler(mock_site)

        result = handler.handle_api_result(None, {})

        assert result is False

    def test_empty_dict_api_response(self):
        """Test handling of empty dict API response."""
        from unittest.mock import Mock

        from src.wiki_api.upload_handler import UploadHandler

        mock_site = Mock()
        handler = UploadHandler(mock_site)

        result = handler.handle_api_result({}, {})

        # Empty dict is falsy so returns False (line 50-52)
        assert result is False

    def test_copyuploaddisabled_error(self):
        """Test handling of upload by URL disabled error."""
        from unittest.mock import Mock

        from src.wiki_api.upload_handler import UploadHandler

        mock_site = Mock()
        handler = UploadHandler(mock_site)

        info = {"error": {"code": "copyuploaddisabled", "info": "Upload by URL disabled."}}

        with pytest.raises(UploadByUrlDisabledError):
            handler.handle_api_result(info, {})

    def test_upload_by_url_disabled_case_insensitive(self):
        """Test handling of upload by URL disabled error (case insensitive match)."""
        from unittest.mock import Mock

        from src.wiki_api.upload_handler import UploadHandler

        mock_site = Mock()
        handler = UploadHandler(mock_site)

        info = {"error": {"code": "other", "info": "Upload by URL disabled."}}

        with pytest.raises(UploadByUrlDisabledError):
            handler.handle_api_result(info, {})

    def test_ratelimited_error(self):
        """Test handling of rate limited error."""
        from unittest.mock import Mock

        from src.wiki_api.api_errors import RateLimitedError
        from src.wiki_api.upload_handler import UploadHandler

        mock_site = Mock()
        handler = UploadHandler(mock_site)

        info = {"error": {"code": "ratelimited", "info": "Rate limit exceeded"}}

        with pytest.raises(RateLimitedError, match="ratelimited"):
            handler.handle_api_result(info, {})

    def test_throttled_error(self):
        """Test handling of throttled error."""
        from unittest.mock import Mock

        from src.wiki_api.api_errors import RateLimitedError
        from src.wiki_api.upload_handler import UploadHandler

        mock_site = Mock()
        handler = UploadHandler(mock_site)

        info = {"error": {"code": "throttled", "info": "Request throttled"}}

        with pytest.raises(RateLimitedError, match="throttled"):
            handler.handle_api_result(info, {})

    def test_rate_in_code_error(self):
        """Test handling of error with 'rate' in code."""
        from unittest.mock import Mock

        from src.wiki_api.upload_handler import UploadHandler

        mock_site = Mock()
        handler = UploadHandler(mock_site)

        info = {"error": {"code": "ratelimited", "info": "Rate limited"}}

        with pytest.raises(Exception, match="ratelimited"):
            handler.handle_api_result(info, {})

    def test_permission_denied_error(self):
        """Test handling of permission denied error."""
        from unittest.mock import Mock

        from src.wiki_api.upload_handler import UploadHandler

        mock_site = Mock()
        handler = UploadHandler(mock_site)

        info = {"error": {"code": "permissiondenied", "info": "Permission denied"}}

        with pytest.raises(InsufficientPermissionError):
            handler.handle_api_result(info, {})

    def test_badtoken_error(self):
        """Test handling of bad token error."""
        from unittest.mock import Mock

        from src.wiki_api.upload_handler import UploadHandler

        mock_site = Mock()
        handler = UploadHandler(mock_site)

        info = {"error": {"code": "badtoken", "info": "Invalid token"}}

        with pytest.raises(InsufficientPermissionError):
            handler.handle_api_result(info, {})

    def test_mwoauth_invalid_authorization_error(self):
        """Test handling of OAuth invalid authorization error."""
        from unittest.mock import Mock

        from src.wiki_api.upload_handler import UploadHandler

        mock_site = Mock()
        handler = UploadHandler(mock_site)

        info = {"error": {"code": "mwoauth-invalid-authorization", "info": "Invalid OAuth"}}

        with pytest.raises(InsufficientPermissionError):
            handler.handle_api_result(info, {})

    def test_generic_api_error(self):
        """Test handling of generic API error."""
        from unittest.mock import Mock

        from src.wiki_api.upload_handler import UploadHandler

        mock_site = Mock()
        handler = UploadHandler(mock_site)

        info = {"error": {"code": "unknown", "info": "Unknown error"}}

        with pytest.raises(Exception, match="('unknown', 'Unknown error', {})"):
            handler.handle_api_result(info, {})

    def test_success_result(self):
        """Test handling of successful upload result."""
        from unittest.mock import Mock

        from src.wiki_api.upload_handler import UploadHandler

        mock_site = Mock()
        handler = UploadHandler(mock_site)

        info = {"upload": {"result": "Success", "fileid": 123}}

        result = handler.handle_api_result(info, {})

        # Returns True on success (line 87)
        assert result is True

    def test_duplicate_warning(self):
        """Test handling of duplicate file warning."""
        from unittest.mock import Mock

        from src.wiki_api.upload_handler import UploadHandler

        mock_site = Mock()
        handler = UploadHandler(mock_site)

        info = {"upload": {"warnings": {"duplicate": ["Existing_File.jpg"]}}}

        with pytest.raises(DuplicateFileError) as exc_info:
            handler.handle_api_result(info, {"filename": "test.jpg"})

        assert exc_info.value.file_name == "test.jpg"
        assert exc_info.value.duplicate_name == "Existing File.jpg"

    def test_exists_warning(self):
        """Test handling of file exists warning."""
        from unittest.mock import Mock

        from src.wiki_api.upload_handler import UploadHandler

        mock_site = Mock()
        handler = UploadHandler(mock_site)

        info = {"upload": {"warnings": {"exists": "File exists"}}}

        with pytest.raises(FileExistError) as exc_info:
            handler.handle_api_result(info, {"filename": "test.jpg"})

        assert exc_info.value.file_name == "test.jpg"

    def test_unknown_result_returns_true(self):
        """Test handling of unknown result returns True."""
        from unittest.mock import Mock

        from src.wiki_api.upload_handler import UploadHandler

        mock_site = Mock()
        handler = UploadHandler(mock_site)

        info = {"upload": {"result": "Unknown"}}

        result = handler.handle_api_result(info, {})

        assert result is True


class TestMwclientUpload:
    """Tests for UploadHandler.mwclient_upload method."""

    def test_filename_required(self):
        """Test that filename parameter is required."""
        from unittest.mock import Mock

        from src.wiki_api.upload_handler import UploadHandler

        mock_site = Mock()
        handler = UploadHandler(mock_site)

        with pytest.raises(TypeError, match="filename must be specified"):
            handler.mwclient_upload(file=None, filename=None)

    def test_default_comment_equals_description(self):
        """Test that default comment equals description."""
        from unittest.mock import Mock

        from src.wiki_api.upload_handler import UploadHandler

        mock_site = Mock()
        mock_site.get_token.return_value = "test_token"
        mock_site.raw_call.return_value = '{"upload": {"result": "Success"}}'
        handler = UploadHandler(mock_site)

        handler.mwclient_upload(filename="test.jpg", description="Test description")

        call_args = mock_site.raw_call.call_args
        postdata = call_args[0][1]
        assert postdata["comment"] == "Test description"
        assert postdata["text"] == "Test description"

    def test_url_upload(self):
        """Test upload with URL parameter."""
        from unittest.mock import Mock

        from src.wiki_api.upload_handler import UploadHandler

        mock_site = Mock()
        mock_site.get_token.return_value = "test_token"
        mock_site.raw_call.return_value = '{"upload": {"result": "Success"}}'
        handler = UploadHandler(mock_site)

        handler.mwclient_upload(filename="test.jpg", description="Desc", url="https://example.com/image.jpg")

        call_args = mock_site.raw_call.call_args
        postdata = call_args[0][1]
        assert postdata["url"] == "https://example.com/image.jpg"

    @pytest.mark.skip(reason="Complex mocking of file operations")
    def test_file_upload_with_path(self):
        """Test upload with file path."""
        # This test is complex to mock due to file operations
        # The functionality is covered by test_upload_from_file_success
        pass  # noqa: PIE790

    def test_file_upload_with_file_object(self):
        """Test upload with file-like object."""
        from unittest.mock import Mock

        from src.wiki_api.upload_handler import UploadHandler

        mock_site = Mock()
        mock_site.get_token.return_value = "test_token"
        mock_site.raw_call.return_value = '{"upload": {"result": "Success"}}'
        handler = UploadHandler(mock_site)

        file_obj = BytesIO(b"image data")
        handler.mwclient_upload(file=file_obj, filename="test.jpg", description="Desc")

        call_args = mock_site.raw_call.call_args
        # files is passed as 3rd positional argument
        assert call_args[0][2] is not None

    def test_empty_response_handling(self):
        """Test handling of empty response from raw_call."""
        from unittest.mock import Mock

        from src.wiki_api.upload_handler import UploadHandler

        mock_site = Mock()
        mock_site.get_token.return_value = "test_token"
        mock_site.raw_call.return_value = "{}"
        handler = UploadHandler(mock_site)

        result = handler.mwclient_upload(filename="test.jpg", description="Desc")

        assert result == {}

    def test_api_deprecation_warning_cleanup(self):
        """Test cleanup of API deprecation warning in error."""
        from unittest.mock import Mock

        from src.wiki_api.upload_handler import UploadHandler

        mock_site = Mock()
        mock_site.get_token.return_value = "test_token"
        # When upload is successful AND there's a deprecation warning, the warning is cleared
        # and the success is returned (line 155-156 checks for success before error handling)
        mock_site.raw_call.return_value = '{"upload": {"result": "Success"}, "error": {"code": "test", "info": "test", "*": "for notice of API deprecations and breaking changes."}}'
        handler = UploadHandler(mock_site)

        result = handler.mwclient_upload(filename="test.jpg", description="Desc")

        # Returns full info on success, with error["*"] cleared
        assert result["upload"]["result"] == "Success"
        assert result["error"]["*"] == ""


class TestUploadExceptionHandling:
    """Tests for UploadHandler.upload method exception handling."""

    @patch("src.wiki_api.main_api.Site")
    def test_upload_file_exists_error(self, mock_site_class):
        """Test upload handles FileExistError."""
        mock_site = Mock()
        mock_site.host = "test.wikipedia.org"
        mock_site.username = "testuser"
        mock_site.raw_call.return_value = '{"upload": {"warnings": {"exists": "File exists"}}}'
        mock_site.get_token.return_value = "test_token"
        mock_site_class.return_value = mock_site

        api = WikipediaAPI("en", "user", "pass")
        result = api.upload(None, "test.jpg", "Description", "Comment")

        assert result["success"] is False
        assert result["error"] == "exists"

    @patch("src.wiki_api.main_api.Site")
    def test_upload_permission_error(self, mock_site_class):
        """Test upload handles InsufficientPermissionError."""
        mock_site = Mock()
        mock_site.host = "test.wikipedia.org"
        mock_site.username = "testuser"
        mock_site.raw_call.return_value = '{"error": {"code": "permissiondenied", "info": "Permission denied"}}'
        mock_site.get_token.return_value = "test_token"
        mock_site_class.return_value = mock_site

        api = WikipediaAPI("en", "user", "pass")
        result = api.upload(None, "test.jpg", "Description", "Comment")

        assert result["success"] is False
        assert result["error"] == "permission_denied"

    @patch("src.wiki_api.main_api.Site")
    def test_upload_url_disabled_error(self, mock_site_class):
        """Test upload handles UploadByUrlDisabledError."""
        mock_site = Mock()
        mock_site.host = "test.wikipedia.org"
        mock_site.raw_call.return_value = '{"error": {"code": "copyuploaddisabled", "info": "Upload by URL disabled."}}'
        mock_site.get_token.return_value = "test_token"
        mock_site_class.return_value = mock_site

        api = WikipediaAPI("en", "user", "pass")
        result = api.upload(None, "test.jpg", "Description", "Comment", url="https://example.com/test.jpg")

        assert result["success"] is False
        assert result["error"] == "url_disabled"

    @patch("src.wiki_api.main_api.Site")
    def test_upload_api_error(self, mock_site_class):
        """Test upload handles mwclient.errors.APIError."""
        mock_site = Mock()
        mock_site.host = "test.wikipedia.org"
        mock_site.raw_call.side_effect = mwclient.errors.APIError("code", "info", {})
        mock_site.get_token.return_value = "test_token"
        mock_site_class.return_value = mock_site

        api = WikipediaAPI("en", "user", "pass")
        result = api.upload(None, "test.jpg", "Description", "Comment")

        assert result["success"] is False
        # APIError string representation includes the args
        assert "code" in result["error"] or "info" in result["error"]

    @patch("src.wiki_api.main_api.Site")
    def test_upload_generic_exception(self, mock_site_class):
        """Test upload handles generic Exception."""
        mock_site = Mock()
        mock_site.host = "test.wikipedia.org"
        mock_site.raw_call.side_effect = ValueError("Unexpected error")
        mock_site.get_token.return_value = "test_token"
        mock_site_class.return_value = mock_site

        api = WikipediaAPI("en", "user", "pass")
        result = api.upload(None, "test.jpg", "Description", "Comment")

        assert result["success"] is False
        assert "Unexpected error" in result["error"]

    @patch("src.wiki_api.main_api.Site")
    def test_upload_removes_file_prefix(self, mock_site_class):
        """Test upload removes 'File:' prefix from filename."""
        mock_site = Mock()
        mock_site.raw_call.return_value = '{"upload": {"result": "Success"}}'
        mock_site.get_token.return_value = "test_token"
        mock_site_class.return_value = mock_site

        api = WikipediaAPI("en", "user", "pass")
        result = api.upload(None, "File:test.jpg", "Description", "Comment")

        assert result["success"] is True
        # Verify the filename passed to raw_call doesn't have File: prefix
        call_args = mock_site.raw_call.call_args
        postdata = call_args[0][1]
        assert postdata["filename"] == "test.jpg"


class TestWikipediaAPI:
    """Tests for WikipediaAPI class."""

    @patch("src.wiki_api.main_api.Site")
    def test_upload_from_url_success(self, mock_site_class):
        """Test successful upload from URL."""
        mock_site = Mock()
        mock_site.raw_call.return_value = '{"upload": {"result": "Success"}}'
        mock_site.get_token.return_value = "test_token"
        mock_site_class.return_value = mock_site

        api = WikipediaAPI("en", "user", "pass")
        result = api.upload_from_url("test.jpg", "https://example.com/test.jpg", "Description", "Upload comment")

        assert result.get("success") is True

    @patch("src.wiki_api.main_api.Site")
    def test_upload_from_url_duplicate(self, mock_site_class):
        """Test upload from URL with duplicate file."""
        mock_site = Mock()
        mock_site.raw_call.return_value = '{"upload": {"warnings": {"duplicate": ["Existing_file.jpg"]}}}'
        mock_site.get_token.return_value = "test_token"
        mock_site_class.return_value = mock_site

        api = WikipediaAPI("en", "user", "pass")

        result = api.upload_from_url("test.jpg", "https://example.com/test.jpg", "Description", "Comment")

        assert result.get("success") is False

    @patch("src.wiki_api.main_api.Site")
    @patch("builtins.open", new_callable=mock_open, read_data=b"image data")
    def test_upload_from_file_success(self, mock_file, mock_site_class):
        """Test successful upload from file."""
        mock_site = Mock()
        mock_site.raw_call.return_value = '{"upload": {"result": "Success"}}'
        mock_site.get_token.return_value = "test_token"
        mock_site_class.return_value = mock_site

        api = WikipediaAPI("en", "user", "pass")
        result = api.upload_from_file("test.jpg", "/tmp/test.jpg", "Description", "Comment")

        assert result.get("success") is True
        mock_file.assert_called_once_with("/tmp/test.jpg", "rb")

    @patch("src.wiki_api.main_api.Site")
    @patch("builtins.open", new_callable=mock_open, read_data=b"image data")
    def test_upload_from_file_duplicate(self, mock_file, mock_site_class):
        """Test upload from file with duplicate."""
        mock_site = Mock()
        mock_site.raw_call.return_value = '{"upload": {"warnings": {"duplicate": ["Existing_file.jpg"]}}}'
        mock_site.get_token.return_value = "test_token"
        mock_site_class.return_value = mock_site

        api = WikipediaAPI("en", "user", "pass")

        result = api.upload_from_file("test.jpg", "/tmp/test.jpg", "Description", "Comment")

        assert result.get("success") is False
