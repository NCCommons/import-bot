"""
Tests for wiki API module.
"""

import pytest
import time
from unittest.mock import Mock, MagicMock, patch, mock_open
import mwclient.errors

from src.wiki_api import retry, WikiAPI, NCCommonsAPI, WikipediaAPI


class TestRetryDecorator:
    """Tests for retry decorator."""

    def test_retry_succeeds_first_attempt(self):
        """Test function succeeds on first attempt."""
        call_count = 0

        @retry(max_attempts=3, delay=0.01, backoff=2)
        def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_func()

        assert result == "success"
        assert call_count == 1

    def test_retry_succeeds_after_failures(self):
        """Test function succeeds after some failures."""
        call_count = 0

        @retry(max_attempts=3, delay=0.01, backoff=2)
        def eventually_succeeds():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"

        result = eventually_succeeds()

        assert result == "success"
        assert call_count == 3

    def test_retry_exhausts_attempts(self):
        """Test all retry attempts are exhausted."""
        call_count = 0

        @retry(max_attempts=3, delay=0.01, backoff=2)
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise Exception("Permanent failure")

        with pytest.raises(Exception, match="Permanent failure"):
            always_fails()

        assert call_count == 3

    def test_retry_exponential_backoff(self):
        """Test exponential backoff timing."""
        call_times = []

        @retry(max_attempts=3, delay=0.05, backoff=2)
        def track_timing():
            call_times.append(time.time())
            if len(call_times) < 3:
                raise Exception("Retry")
            return "done"

        track_timing()

        # Should have 3 calls
        assert len(call_times) == 3

        # Check delays (with tolerance for timing variance)
        # First retry: ~0.05s delay
        delay1 = call_times[1] - call_times[0]
        assert 0.04 < delay1 < 0.1

        # Second retry: ~0.1s delay (0.05 * 2)
        delay2 = call_times[2] - call_times[1]
        assert 0.08 < delay2 < 0.2

    def test_retry_preserves_function_metadata(self):
        """Test decorator preserves function metadata."""
        @retry(max_attempts=3, delay=1, backoff=2)
        def documented_func():
            """Test docstring."""
            pass

        assert documented_func.__name__ == 'documented_func'
        assert documented_func.__doc__ == 'Test docstring.'

    def test_retry_with_args_and_kwargs(self):
        """Test retry works with function arguments."""
        call_count = 0

        @retry(max_attempts=3, delay=0.01, backoff=2)
        def func_with_args(x, y, z=10):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Retry")
            return x + y + z

        result = func_with_args(1, 2, z=3)

        assert result == 6
        assert call_count == 2


class TestWikiAPI:
    """Tests for WikiAPI base class."""

    @patch('src.wiki_api.mwclient.Site')
    def test_wiki_api_initialization(self, mock_site_class):
        """Test WikiAPI initializes connection."""
        mock_site = Mock()
        mock_site_class.return_value = mock_site

        api = WikiAPI('test.wikipedia.org')

        mock_site_class.assert_called_once_with('test.wikipedia.org')
        assert api.site == mock_site

    @patch('src.wiki_api.mwclient.Site')
    def test_wiki_api_initialization_with_login(self, mock_site_class):
        """Test WikiAPI logs in when credentials provided."""
        mock_site = Mock()
        mock_site_class.return_value = mock_site

        api = WikiAPI('test.wikipedia.org', 'user', 'pass')

        mock_site.login.assert_called_once_with('user', 'pass')

    @patch('src.wiki_api.mwclient.Site')
    def test_get_page_text(self, mock_site_class):
        """Test getting page text."""
        mock_page = Mock()
        mock_page.text.return_value = "Page content"

        mock_site = MagicMock()
        mock_site.pages.__getitem__.return_value = mock_page
        mock_site_class.return_value = mock_site

        api = WikiAPI('test.wikipedia.org')
        text = api.get_page_text('Test Page')

        assert text == "Page content"
        mock_site.pages.__getitem__.assert_called_once_with('Test Page')

    @patch('src.wiki_api.mwclient.Site')
    def test_save_page(self, mock_site_class):
        """Test saving page."""
        mock_page = Mock()
        mock_site = MagicMock()
        mock_site.pages.__getitem__.return_value = mock_page
        mock_site_class.return_value = mock_site

        api = WikiAPI('test.wikipedia.org')
        api.save_page('Test Page', 'New content', 'Edit summary')

        mock_page.save.assert_called_once_with('New content', summary='Edit summary')

    @patch('src.wiki_api.mwclient.Site')
    def test_get_page_text_retries_on_failure(self, mock_site_class):
        """Test get_page_text retries on failure."""
        call_count = 0

        def side_effect():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Network error")
            return "Success"

        mock_page = Mock()
        mock_page.text.side_effect = side_effect

        mock_site = MagicMock()
        mock_site.pages.__getitem__.return_value = mock_page
        mock_site_class.return_value = mock_site

        api = WikiAPI('test.wikipedia.org')

        # Patch time.sleep to speed up test
        with patch('time.sleep'):
            text = api.get_page_text('Test Page')

        assert text == "Success"
        assert call_count == 2


class TestNCCommonsAPI:
    """Tests for NCCommonsAPI class."""

    @patch('src.wiki_api.mwclient.Site')
    def test_nc_commons_api_initialization(self, mock_site_class):
        """Test NCCommonsAPI initializes with nccommons.org."""
        mock_site = Mock()
        mock_site_class.return_value = mock_site

        api = NCCommonsAPI('user', 'pass')

        mock_site_class.assert_called_once_with('nccommons.org')
        mock_site.login.assert_called_once_with('user', 'pass')

    @patch('src.wiki_api.mwclient.Site')
    def test_get_image_url(self, mock_site_class):
        """Test getting image URL."""
        mock_page = Mock()
        mock_page.imageinfo = {'url': 'https://example.com/image.jpg'}

        mock_site = MagicMock()
        mock_site.pages.__getitem__.return_value = mock_page
        mock_site_class.return_value = mock_site

        api = NCCommonsAPI('user', 'pass')
        url = api.get_image_url('test.jpg')

        assert url == 'https://example.com/image.jpg'
        mock_site.pages.__getitem__.assert_called_once_with('File:test.jpg')

    @patch('src.wiki_api.mwclient.Site')
    def test_get_image_url_adds_file_prefix(self, mock_site_class):
        """Test get_image_url adds File: prefix if missing."""
        mock_page = Mock()
        mock_page.imageinfo = {'url': 'https://example.com/image.jpg'}

        mock_site = MagicMock()
        mock_site.pages.__getitem__.return_value = mock_page
        mock_site_class.return_value = mock_site

        api = NCCommonsAPI('user', 'pass')
        url = api.get_image_url('File:test.jpg')

        # Should not add duplicate prefix
        assert url == 'https://example.com/image.jpg'
        mock_site.pages.__getitem__.assert_called_once_with('File:test.jpg')

    @patch('src.wiki_api.mwclient.Site')
    def test_get_file_description(self, mock_site_class):
        """Test getting file description."""
        mock_page = Mock()
        mock_page.text.return_value = "File description content"

        mock_site = MagicMock()
        mock_site.pages.__getitem__.return_value = mock_page
        mock_site_class.return_value = mock_site

        api = NCCommonsAPI('user', 'pass')
        desc = api.get_file_description('test.jpg')

        assert desc == "File description content"
        mock_site.pages.__getitem__.assert_called_with('File:test.jpg')


class TestWikipediaAPI:
    """Tests for WikipediaAPI class."""

    @patch('src.wiki_api.mwclient.Site')
    def test_wikipedia_api_initialization(self, mock_site_class):
        """Test WikipediaAPI initializes with correct site."""
        mock_site = Mock()
        mock_site_class.return_value = mock_site

        api = WikipediaAPI('en', 'user', 'pass')

        mock_site_class.assert_called_once_with('en.wikipedia.org')
        assert api.lang == 'en'
        mock_site.login.assert_called_once_with('user', 'pass')

    @patch('src.wiki_api.mwclient.Site')
    def test_wikipedia_api_different_language(self, mock_site_class):
        """Test WikipediaAPI with different language code."""
        mock_site = Mock()
        mock_site_class.return_value = mock_site

        api = WikipediaAPI('ar', 'user', 'pass')

        mock_site_class.assert_called_once_with('ar.wikipedia.org')
        assert api.lang == 'ar'

    @patch('src.wiki_api.mwclient.Site')
    def test_get_pages_with_template(self, mock_site_class):
        """Test getting pages that use a template."""
        # Create mock pages
        mock_page1 = Mock()
        mock_page1.name = 'Page 1'
        mock_page2 = Mock()
        mock_page2.name = 'Page 2'

        mock_template = Mock()
        mock_template.embeddedin.return_value = [mock_page1, mock_page2]

        mock_site = MagicMock()
        mock_site.pages.__getitem__.return_value = mock_template
        mock_site_class.return_value = mock_site

        api = WikipediaAPI('en', 'user', 'pass')
        pages = api.get_pages_with_template('NC')

        assert pages == ['Page 1', 'Page 2']
        mock_site.pages.__getitem__.assert_called_once_with('Template:NC')

    @patch('src.wiki_api.mwclient.Site')
    def test_get_pages_with_template_adds_prefix(self, mock_site_class):
        """Test that Template: prefix is added if missing."""
        mock_template = Mock()
        mock_template.embeddedin.return_value = []

        mock_site = MagicMock()
        mock_site.pages.__getitem__.return_value = mock_template
        mock_site_class.return_value = mock_site

        api = WikipediaAPI('en', 'user', 'pass')
        api.get_pages_with_template('Template:NC')

        # Should not add duplicate prefix
        mock_site.pages.__getitem__.assert_called_once_with('Template:NC')

    @patch('src.wiki_api.mwclient.Site')
    def test_upload_from_url_success(self, mock_site_class):
        """Test successful upload from URL."""
        mock_site = Mock()
        mock_site.upload.return_value = {'result': 'Success'}
        mock_site_class.return_value = mock_site

        api = WikipediaAPI('en', 'user', 'pass')
        result = api.upload_from_url(
            'test.jpg',
            'https://example.com/test.jpg',
            'Description',
            'Upload comment'
        )

        assert result is True
        mock_site.upload.assert_called_once_with(
            file=None,
            filename='test.jpg',
            description='Description',
            comment='Upload comment',
            url='https://example.com/test.jpg'
        )

    @patch('src.wiki_api.mwclient.Site')
    def test_upload_from_url_duplicate(self, mock_site_class):
        """Test upload from URL with duplicate file."""
        mock_site = Mock()
        mock_site.upload.side_effect = mwclient.errors.APIError(
            'fileexists-shared-forbidden',
            'Duplicate file',
            {}
        )
        mock_site_class.return_value = mock_site

        api = WikipediaAPI('en', 'user', 'pass')

        # Patch time.sleep to speed up test
        with patch('time.sleep'):
            result = api.upload_from_url(
                'test.jpg',
                'https://example.com/test.jpg',
                'Description',
                'Comment'
            )

        assert result is False

    @patch('src.wiki_api.mwclient.Site')
    def test_upload_from_url_other_error_raises(self, mock_site_class):
        """Test upload from URL with non-duplicate error raises."""
        mock_site = Mock()
        mock_site.upload.side_effect = mwclient.errors.APIError(
            'permission-denied',
            'No permission',
            {}
        )
        mock_site_class.return_value = mock_site

        api = WikipediaAPI('en', 'user', 'pass')

        # Patch time.sleep to speed up test
        with patch('time.sleep'):
            with pytest.raises(mwclient.errors.APIError):
                api.upload_from_url(
                    'test.jpg',
                    'https://example.com/test.jpg',
                    'Description',
                    'Comment'
                )

    @patch('src.wiki_api.mwclient.Site')
    @patch('builtins.open', new_callable=mock_open, read_data=b'image data')
    def test_upload_from_file_success(self, mock_file, mock_site_class):
        """Test successful upload from file."""
        mock_site = Mock()
        mock_site.upload.return_value = {'result': 'Success'}
        mock_site_class.return_value = mock_site

        api = WikipediaAPI('en', 'user', 'pass')
        result = api.upload_from_file(
            'test.jpg',
            '/tmp/test.jpg',
            'Description',
            'Comment'
        )

        assert result is True
        mock_file.assert_called_once_with('/tmp/test.jpg', 'rb')

    @patch('src.wiki_api.mwclient.Site')
    @patch('builtins.open', new_callable=mock_open, read_data=b'image data')
    def test_upload_from_file_duplicate(self, mock_file, mock_site_class):
        """Test upload from file with duplicate."""
        mock_site = Mock()
        mock_site.upload.side_effect = mwclient.errors.APIError(
            'duplicate',
            'Duplicate file',
            {}
        )
        mock_site_class.return_value = mock_site

        api = WikipediaAPI('en', 'user', 'pass')

        # Patch time.sleep to speed up test
        with patch('time.sleep'):
            result = api.upload_from_file(
                'test.jpg',
                '/tmp/test.jpg',
                'Description',
                'Comment'
            )

        assert result is False