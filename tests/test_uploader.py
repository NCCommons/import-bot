"""
Tests for file uploader.
"""

import pytest
from unittest.mock import Mock, patch
from src.uploader import FileUploader


class TestFileUploader:
    """Tests for FileUploader class."""

    @pytest.fixture
    def uploader(self, mock_nc_api, mock_wiki_api, temp_db, sample_config):
        """Create FileUploader instance for testing."""
        return FileUploader(mock_nc_api, mock_wiki_api, temp_db, sample_config)

    def test_upload_file_success_url_method(self, uploader, mock_nc_api, mock_wiki_api):
        """Test successful file upload using URL method."""
        result = uploader.upload_file("test.jpg")

        # Should succeed
        assert result is True

        # Should have called NC Commons API
        mock_nc_api.get_image_url.assert_called_once_with("test.jpg")
        mock_nc_api.get_file_description.assert_called_once_with("test.jpg")

        # Should have called Wikipedia API
        mock_wiki_api.upload_from_url.assert_called_once()

    def test_upload_file_already_uploaded(self, uploader, temp_db):
        """Test uploading file that's already uploaded."""
        # Pre-populate database
        temp_db.record_upload("existing.jpg", "en", "success")

        result = uploader.upload_file("existing.jpg")

        # Should return False (not uploaded again)
        assert result is False

    def test_upload_file_duplicate(self, uploader, mock_wiki_api):
        """Test handling duplicate file error."""
        # Make upload return False (duplicate)
        mock_wiki_api.upload_from_url.return_value = False

        result = uploader.upload_file("duplicate.jpg")

        assert result is False

    def test_upload_file_falls_back_to_download(self, uploader, mock_wiki_api, mock_nc_api):
        """Test falling back to download method when URL upload fails."""
        # Make URL upload fail with copyupload error
        mock_wiki_api.upload_from_url.side_effect = Exception("copyupload disabled")

        # Mock download method
        with patch.object(uploader, "_upload_via_download") as mock_download:
            mock_download.return_value = True

            result = uploader.upload_file("test.jpg")

            # Should have tried download method
            mock_download.assert_called_once()

    def test_upload_file_error_recorded(self, uploader, mock_nc_api, temp_db):
        """Test that upload errors are recorded in database."""
        # Make API fail
        mock_nc_api.get_image_url.side_effect = Exception("API Error")

        result = uploader.upload_file("error.jpg")

        # Should return False
        assert result is False

        # Should record error in database
        with temp_db._get_connection() as conn:
            record = conn.execute("SELECT * FROM uploads WHERE filename='error.jpg'").fetchone()

            assert record["status"] == "failed"
            assert "API Error" in record["error"]

    def test_process_description(self, uploader):
        """Test description processing."""
        description = """
        File description
        [[Category:OldCat1]]
        [[Category:OldCat2]]
        More text
        """

        result = uploader._process_description(description)

        # Should remove old categories
        assert "[[Category:OldCat1]]" not in result
        assert "[[Category:OldCat2]]" not in result

        # Should add NC Commons category
        assert "[[Category:Contains images from NC Commons]]" in result

        # Should preserve other text
        assert "File description" in result
        assert "More text" in result

    @patch("urllib.request.urlretrieve")
    @patch("tempfile.NamedTemporaryFile")
    def test_upload_via_download(self, mock_temp, mock_retrieve, uploader, mock_wiki_api):
        """Test upload via download method."""
        # Mock temporary file
        mock_temp_file = Mock()
        mock_temp_file.name = "/tmp/test.tmp"
        mock_temp.return_value = mock_temp_file

        result = uploader._upload_via_download(
            "test.jpg", "http://example.com/test.jpg", "Description", "Comment", "en"
        )

        # Should have downloaded
        mock_retrieve.assert_called_once()

        # Should have uploaded from file
        mock_wiki_api.upload_from_file.assert_called_once()

        # Should succeed
        assert result is True
