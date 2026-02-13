"""
Tests for file uploader module.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from src.uploader import FileUploader
from src.wiki_api import NCCommonsAPI, WikipediaAPI
from src.database import Database


class TestFileUploader:
    """Tests for FileUploader class."""

    @pytest.fixture
    def uploader(self, mock_nc_api, mock_wiki_api, temp_db, sample_config):
        """Create FileUploader instance for testing."""
        return FileUploader(mock_nc_api, mock_wiki_api, temp_db, sample_config)

    def test_uploader_initialization(self, mock_nc_api, mock_wiki_api, temp_db, sample_config):
        """Test uploader initializes correctly."""
        uploader = FileUploader(mock_nc_api, mock_wiki_api, temp_db, sample_config)

        assert uploader.nc_api == mock_nc_api
        assert uploader.wiki_api == mock_wiki_api
        assert uploader.db == temp_db
        assert uploader.config == sample_config

    def test_upload_file_already_uploaded(self, uploader, temp_db):
        """Test skipping file that's already uploaded."""
        # Mark file as already uploaded
        temp_db.record_upload('existing.jpg', 'en', 'success')

        result = uploader.upload_file('existing.jpg')

        assert result is False
        # Should not attempt to fetch from NC Commons
        uploader.nc_api.get_image_url.assert_not_called()

    def test_upload_file_success_url_method(self, uploader, mock_nc_api, mock_wiki_api, temp_db):
        """Test successful file upload via URL method."""
        # Setup mocks
        mock_nc_api.get_image_url.return_value = 'https://nccommons.org/image.jpg'
        mock_nc_api.get_file_description.return_value = 'Description\n[[Category:Test]]'
        mock_wiki_api.upload_from_url.return_value = True
        mock_wiki_api.lang = 'en'

        result = uploader.upload_file('test.jpg')

        assert result is True

        # Verify NC Commons was queried
        mock_nc_api.get_image_url.assert_called_once_with('test.jpg')
        mock_nc_api.get_file_description.assert_called_once_with('test.jpg')

        # Verify upload was attempted
        mock_wiki_api.upload_from_url.assert_called_once()

        # Verify database record
        assert temp_db.is_file_uploaded('test.jpg', 'en')

    def test_upload_file_duplicate(self, uploader, mock_nc_api, mock_wiki_api, temp_db):
        """Test handling duplicate file."""
        mock_nc_api.get_image_url.return_value = 'https://nccommons.org/dup.jpg'
        mock_nc_api.get_file_description.return_value = 'Description'
        mock_wiki_api.upload_from_url.return_value = False  # Duplicate
        mock_wiki_api.lang = 'en'

        result = uploader.upload_file('dup.jpg')

        assert result is False

        # Should be recorded as duplicate
        with temp_db._get_connection() as conn:
            record = conn.execute(
                "SELECT status FROM uploads WHERE filename='dup.jpg'"
            ).fetchone()
            assert record['status'] == 'duplicate'

    def test_upload_file_url_method_not_allowed_fallback(self, uploader, mock_nc_api, mock_wiki_api, temp_db):
        """Test fallback to file method when URL upload not allowed."""
        mock_nc_api.get_image_url.return_value = 'https://nccommons.org/file.jpg'
        mock_nc_api.get_file_description.return_value = 'Description'
        mock_wiki_api.upload_from_url.side_effect = Exception('URL upload not allowed')
        mock_wiki_api.upload_from_file.return_value = True
        mock_wiki_api.lang = 'en'

        with patch('urllib.request.urlretrieve') as mock_retrieve:
            with patch('pathlib.Path.unlink'):
                result = uploader.upload_file('file.jpg')

        assert result is True

        # Should have attempted file upload as fallback
        mock_wiki_api.upload_from_file.assert_called_once()

    def test_upload_file_complete_failure(self, uploader, mock_nc_api, mock_wiki_api, temp_db):
        """Test handling complete upload failure."""
        mock_nc_api.get_image_url.side_effect = Exception('Network error')
        mock_wiki_api.lang = 'en'

        result = uploader.upload_file('error.jpg')

        assert result is False

        # Should be recorded as failed
        with temp_db._get_connection() as conn:
            record = conn.execute(
                "SELECT status, error FROM uploads WHERE filename='error.jpg'"
            ).fetchone()
            assert record['status'] == 'failed'
            assert 'Network error' in record['error']

    @patch('urllib.request.urlretrieve')
    @patch('tempfile.NamedTemporaryFile')
    @patch('pathlib.Path.unlink')
    def test_upload_via_download_success(self, mock_unlink, mock_tempfile, mock_retrieve, uploader, mock_wiki_api, temp_db):
        """Test successful upload via download method."""
        # Setup temp file mock
        mock_temp = Mock()
        mock_temp.name = '/tmp/test123.tmp'
        mock_tempfile.return_value = mock_temp

        mock_wiki_api.upload_from_file.return_value = True

        result = uploader._upload_via_download(
            'test.jpg',
            'https://example.com/test.jpg',
            'Description',
            'Comment',
            'en'
        )

        assert result is True

        # Verify file was downloaded
        mock_retrieve.assert_called_once_with('https://example.com/test.jpg', '/tmp/test123.tmp')

        # Verify upload was attempted
        mock_wiki_api.upload_from_file.assert_called_once()

        # Verify cleanup
        mock_unlink.assert_called_once()

    @patch('urllib.request.urlretrieve')
    @patch('tempfile.NamedTemporaryFile')
    @patch('pathlib.Path.unlink')
    def test_upload_via_download_duplicate(self, mock_unlink, mock_tempfile, mock_retrieve, uploader, mock_wiki_api, temp_db):
        """Test upload via download with duplicate file."""
        mock_temp = Mock()
        mock_temp.name = '/tmp/test123.tmp'
        mock_tempfile.return_value = mock_temp

        mock_wiki_api.upload_from_file.return_value = False  # Duplicate

        result = uploader._upload_via_download(
            'dup.jpg',
            'https://example.com/dup.jpg',
            'Description',
            'Comment',
            'en'
        )

        assert result is False

        # Still should clean up temp file
        mock_unlink.assert_called_once()

    @patch('urllib.request.urlretrieve')
    @patch('tempfile.NamedTemporaryFile')
    @patch('pathlib.Path.unlink')
    def test_upload_via_download_cleanup_on_error(self, mock_unlink, mock_tempfile, mock_retrieve, uploader, mock_wiki_api):
        """Test temp file cleanup on error."""
        mock_temp = Mock()
        mock_temp.name = '/tmp/test123.tmp'
        mock_tempfile.return_value = mock_temp

        mock_retrieve.side_effect = Exception('Download failed')

        with pytest.raises(Exception, match='Download failed'):
            uploader._upload_via_download(
                'test.jpg',
                'https://example.com/test.jpg',
                'Description',
                'Comment',
                'en'
            )

        # Should still clean up temp file
        mock_unlink.assert_called_once()

    def test_process_description_removes_categories(self, uploader, sample_config):
        """Test description processing removes categories."""
        description = """
        Some text here.
        [[Category:Old Category]]
        [[Category:Another Category]]
        More text.
        """

        processed = uploader._process_description(description)

        # Categories should be removed
        assert '[[Category:Old Category]]' not in processed
        assert '[[Category:Another Category]]' not in processed

        # Original text should remain
        assert 'Some text here.' in processed
        assert 'More text.' in processed

    def test_process_description_adds_nc_category(self, uploader, sample_config):
        """Test description processing adds NC Commons category."""
        description = "Just a simple description"

        processed = uploader._process_description(description)

        # Should add NC Commons category from config
        expected_category = sample_config['wikipedia']['category']
        assert f"[[{expected_category}]]" in processed

    def test_process_description_empty_input(self, uploader):
        """Test processing empty description."""
        processed = uploader._process_description("")

        # Should still add category
        assert '[[Category:Contains images from NC Commons]]' in processed

    def test_upload_file_processes_description(self, uploader, mock_nc_api, mock_wiki_api, temp_db):
        """Test that file upload processes description correctly."""
        mock_nc_api.get_image_url.return_value = 'https://example.com/test.jpg'
        mock_nc_api.get_file_description.return_value = 'Original\n[[Category:OldCat]]'
        mock_wiki_api.upload_from_url.return_value = True
        mock_wiki_api.lang = 'en'

        uploader.upload_file('test.jpg')

        # Check the description passed to upload
        call_args = mock_wiki_api.upload_from_url.call_args
        description = call_args.kwargs['description']

        # Should not contain old category
        assert '[[Category:OldCat]]' not in description

        # Should contain NC Commons category
        assert '[[Category:Contains images from NC Commons]]' in description

    def test_upload_file_uses_config_comment(self, uploader, mock_nc_api, mock_wiki_api, temp_db, sample_config):
        """Test that upload uses comment from config."""
        mock_nc_api.get_image_url.return_value = 'https://example.com/test.jpg'
        mock_nc_api.get_file_description.return_value = 'Description'
        mock_wiki_api.upload_from_url.return_value = True
        mock_wiki_api.lang = 'en'

        uploader.upload_file('test.jpg')

        # Check the comment passed to upload
        call_args = mock_wiki_api.upload_from_url.call_args
        comment = call_args.kwargs['comment']

        assert comment == sample_config['wikipedia']['upload_comment']

    def test_upload_file_different_language(self, mock_nc_api, mock_wiki_api, temp_db, sample_config):
        """Test upload respects different Wikipedia language."""
        mock_wiki_api.lang = 'ar'  # Arabic Wikipedia
        mock_nc_api.get_image_url.return_value = 'https://example.com/test.jpg'
        mock_nc_api.get_file_description.return_value = 'Description'
        mock_wiki_api.upload_from_url.return_value = True

        uploader = FileUploader(mock_nc_api, mock_wiki_api, temp_db, sample_config)
        uploader.upload_file('test.jpg')

        # Should be recorded for Arabic Wikipedia
        assert temp_db.is_file_uploaded('test.jpg', 'ar')
        assert not temp_db.is_file_uploaded('test.jpg', 'en')

    def test_upload_via_download_copyupload_error_triggers_fallback(self, uploader, mock_nc_api, mock_wiki_api, temp_db):
        """Test that copyupload error triggers fallback to file download."""
        mock_nc_api.get_image_url.return_value = 'https://example.com/test.jpg'
        mock_nc_api.get_file_description.return_value = 'Description'
        mock_wiki_api.upload_from_url.side_effect = Exception('copyupload disabled')
        mock_wiki_api.upload_from_file.return_value = True
        mock_wiki_api.lang = 'en'

        with patch('urllib.request.urlretrieve'):
            with patch('pathlib.Path.unlink'):
                result = uploader.upload_file('test.jpg')

        assert result is True
        mock_wiki_api.upload_from_file.assert_called_once()