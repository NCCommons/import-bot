# Simple pytest Testing Plan for NC Commons Bot

## Overview

Create simple, practical tests for the NC Commons bot. Focus on testing core functionality without over-complicating.

**Goal:** Write ~300-400 lines of tests to cover the most important parts.

---

## Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures (~80 lines)
├── test_parsers.py          # Parser tests (~60 lines)
├── test_database.py         # Database tests (~80 lines)
├── test_uploader.py         # Uploader tests (~80 lines)
└── test_processor.py        # Processor tests (~80 lines)
```

**Note:** We won't test `wiki_api.py` directly (it's mostly mwclient wrapper). We'll mock it in other tests.

---

## Installation

Add to `requirements.txt`:

```txt
# Existing dependencies
mwclient>=0.10.1
wikitextparser>=0.55.0
PyYAML>=6.0

# Testing dependencies
pytest>=7.4.0
pytest-cov>=4.1.0
pytest-mock>=3.12.0
```

---

## Step 1: Fixtures (`tests/conftest.py`)

Create reusable test fixtures for common objects.

```python
"""
Pytest fixtures for NC Commons bot tests.

Provides shared fixtures for mocking and test data.
"""

import pytest
import tempfile
import sqlite3
from pathlib import Path
from unittest.mock import Mock, MagicMock

from src.database import Database
from src.wiki_api import NCCommonsAPI, WikipediaAPI


@pytest.fixture
def temp_db():
    """
    Create a temporary database for testing.

    Automatically cleaned up after test.
    """
    # Create temporary file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    db_path = Path(temp_file.name)
    temp_file.close()

    # Initialize database
    db = Database(str(db_path))

    yield db

    # Cleanup
    db_path.unlink(missing_ok=True)


@pytest.fixture
def sample_config():
    """Sample configuration dictionary for tests."""
    return {
        'nc_commons': {
            'site': 'nccommons.org',
            'language_page': 'User:Mr. Ibrahem/import bot'
        },
        'wikipedia': {
            'upload_comment': 'Bot: import from nccommons.org',
            'category': 'Category:Contains images from NC Commons'
        },
        'database': {
            'path': './test.db'
        },
        'processing': {
            'max_pages_per_language': 1000,
            'max_retry_attempts': 3,
            'retry_delay_seconds': 5,
            'retry_backoff_multiplier': 2
        },
        'logging': {
            'level': 'INFO',
            'file': './test.log'
        }
    }


@pytest.fixture
def mock_nc_api():
    """Mock NC Commons API client."""
    api = Mock(spec=NCCommonsAPI)

    # Mock methods
    api.get_page_text.return_value = "Sample page text"
    api.get_image_url.return_value = "https://nccommons.org/file.jpg"
    api.get_file_description.return_value = "File description\n[[Category:Test]]"

    return api


@pytest.fixture
def mock_wiki_api():
    """Mock Wikipedia API client."""
    api = Mock(spec=WikipediaAPI)
    api.lang = 'en'

    # Mock methods
    api.get_pages_with_template.return_value = ['Page 1', 'Page 2']
    api.get_page_text.return_value = "{{NC|test.jpg|caption}}"
    api.save_page.return_value = None
    api.upload_from_url.return_value = True
    api.upload_from_file.return_value = True

    return api


@pytest.fixture
def sample_language_list_page():
    """Sample language list page content."""
    return """
    * {{User:Mr. Ibrahem/import bot/line|en}}
    * {{User:Mr. Ibrahem/import bot/line|ar}}
    * {{User:Mr. Ibrahem/import bot/line|fr}}
    """


@pytest.fixture
def sample_nc_template_page():
    """Sample Wikipedia page with NC templates."""
    return """
    This is a test page.

    {{NC|File1.jpg|First image caption}}

    Some text here.

    {{NC|File2.jpg|Second image caption}}

    More content.
    """
```

**Key points:**
- Temporary database that auto-cleans
- Mock API objects
- Sample data for common scenarios
- All fixtures well-documented

---

## Step 2: Parser Tests (`tests/test_parsers.py`)

Test wikitext parsing functions.

```python
"""
Tests for wikitext parsing functions.
"""

import pytest
from src.parsers import (
    parse_language_list,
    extract_nc_templates,
    remove_categories,
    NCTemplate
)


class TestParseLanguageList:
    """Tests for language list parsing."""

    def test_parse_simple_language_list(self, sample_language_list_page):
        """Test parsing a simple language list."""
        languages = parse_language_list(sample_language_list_page)

        assert len(languages) == 3
        assert 'en' in languages
        assert 'ar' in languages
        assert 'fr' in languages

    def test_parse_empty_page(self):
        """Test parsing an empty page."""
        languages = parse_language_list("")
        assert languages == []

    def test_parse_page_without_templates(self):
        """Test parsing a page with no language templates."""
        text = "This is just plain text without templates."
        languages = parse_language_list(text)
        assert languages == []

    def test_parse_mixed_templates(self):
        """Test parsing a page with mixed templates."""
        text = """
        * {{User:Mr. Ibrahem/import bot/line|en}}
        * {{SomeOtherTemplate|value}}
        * {{User:Mr. Ibrahem/import bot/line|ar}}
        """
        languages = parse_language_list(text)

        assert len(languages) == 2
        assert 'en' in languages
        assert 'ar' in languages


class TestExtractNCTemplates:
    """Tests for NC template extraction."""

    def test_extract_simple_template(self):
        """Test extracting a simple NC template."""
        text = "{{NC|test.jpg|Caption text}}"
        templates = extract_nc_templates(text)

        assert len(templates) == 1
        assert templates[0].filename == 'test.jpg'
        assert templates[0].caption == 'Caption text'

    def test_extract_multiple_templates(self, sample_nc_template_page):
        """Test extracting multiple NC templates."""
        templates = extract_nc_templates(sample_nc_template_page)

        assert len(templates) == 2
        assert templates[0].filename == 'File1.jpg'
        assert templates[0].caption == 'First image caption'
        assert templates[1].filename == 'File2.jpg'
        assert templates[1].caption == 'Second image caption'

    def test_extract_template_without_caption(self):
        """Test extracting template without caption."""
        text = "{{NC|image.jpg}}"
        templates = extract_nc_templates(text)

        assert len(templates) == 1
        assert templates[0].filename == 'image.jpg'
        assert templates[0].caption == ''

    def test_extract_no_templates(self):
        """Test page with no NC templates."""
        text = "This is plain text with {{OtherTemplate}} but no NC."
        templates = extract_nc_templates(text)

        assert templates == []


class TestNCTemplate:
    """Tests for NCTemplate dataclass."""

    def test_to_file_syntax(self):
        """Test conversion to file syntax."""
        template = NCTemplate(
            original_text="{{NC|test.jpg|My caption}}",
            filename="test.jpg",
            caption="My caption"
        )

        result = template.to_file_syntax()
        assert result == "[[File:test.jpg|thumb|My caption]]"

    def test_to_file_syntax_no_caption(self):
        """Test conversion without caption."""
        template = NCTemplate(
            original_text="{{NC|test.jpg}}",
            filename="test.jpg",
            caption=""
        )

        result = template.to_file_syntax()
        assert result == "[[File:test.jpg|thumb|]]"


class TestRemoveCategories:
    """Tests for category removal."""

    def test_remove_single_category(self):
        """Test removing a single category."""
        text = "Some text\n[[Category:Test]]\nMore text"
        result = remove_categories(text)

        assert '[[Category:Test]]' not in result
        assert 'Some text' in result
        assert 'More text' in result

    def test_remove_multiple_categories(self):
        """Test removing multiple categories."""
        text = """
        Content here
        [[Category:Cat1]]
        [[Category:Cat2]]
        [[Category:Cat3]]
        More content
        """
        result = remove_categories(text)

        assert '[[Category:' not in result
        assert 'Content here' in result
        assert 'More content' in result

    def test_remove_categories_case_insensitive(self):
        """Test case-insensitive category removal."""
        text = "[[category:Test]] [[CATEGORY:Test2]]"
        result = remove_categories(text)

        assert '[[category:' not in result.lower()

    def test_no_categories(self):
        """Test text without categories."""
        text = "Just plain text"
        result = remove_categories(text)

        assert result == text
```

**Coverage:**
- ✅ Language list parsing (normal, empty, mixed)
- ✅ NC template extraction (single, multiple, no caption)
- ✅ Template to file syntax conversion
- ✅ Category removal (single, multiple, case-insensitive)

---

## Step 3: Database Tests (`tests/test_database.py`)

Test database operations.

```python
"""
Tests for database operations.
"""

import pytest
from src.database import Database


class TestDatabase:
    """Tests for Database class."""

    def test_database_initialization(self, temp_db):
        """Test database initializes correctly."""
        # Tables should exist
        with temp_db._get_connection() as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()

            table_names = [t['name'] for t in tables]
            assert 'uploads' in table_names
            assert 'pages' in table_names

    def test_record_upload_success(self, temp_db):
        """Test recording a successful upload."""
        temp_db.record_upload('test.jpg', 'en', 'success')

        # Verify record exists
        with temp_db._get_connection() as conn:
            result = conn.execute(
                "SELECT * FROM uploads WHERE filename='test.jpg'"
            ).fetchone()

            assert result is not None
            assert result['filename'] == 'test.jpg'
            assert result['language'] == 'en'
            assert result['status'] == 'success'
            assert result['error'] is None

    def test_record_upload_failed(self, temp_db):
        """Test recording a failed upload."""
        temp_db.record_upload('fail.jpg', 'ar', 'failed', 'Error message')

        with temp_db._get_connection() as conn:
            result = conn.execute(
                "SELECT * FROM uploads WHERE filename='fail.jpg'"
            ).fetchone()

            assert result['status'] == 'failed'
            assert result['error'] == 'Error message'

    def test_record_upload_duplicate(self, temp_db):
        """Test recording duplicate file."""
        temp_db.record_upload('dup.jpg', 'en', 'duplicate')

        with temp_db._get_connection() as conn:
            result = conn.execute(
                "SELECT * FROM uploads WHERE filename='dup.jpg'"
            ).fetchone()

            assert result['status'] == 'duplicate'

    def test_record_page_processing(self, temp_db):
        """Test recording page processing."""
        temp_db.record_page_processing('Test Page', 'en', 3, 2)

        with temp_db._get_connection() as conn:
            result = conn.execute(
                "SELECT * FROM pages WHERE page_title='Test Page'"
            ).fetchone()

            assert result is not None
            assert result['page_title'] == 'Test Page'
            assert result['language'] == 'en'
            assert result['templates_found'] == 3
            assert result['files_uploaded'] == 2

    def test_is_file_uploaded_true(self, temp_db):
        """Test checking if file is uploaded (true case)."""
        temp_db.record_upload('uploaded.jpg', 'en', 'success')

        result = temp_db.is_file_uploaded('uploaded.jpg', 'en')
        assert result is True

    def test_is_file_uploaded_false(self, temp_db):
        """Test checking if file is uploaded (false case)."""
        result = temp_db.is_file_uploaded('notfound.jpg', 'en')
        assert result is False

    def test_is_file_uploaded_failed_not_counted(self, temp_db):
        """Test that failed uploads don't count as uploaded."""
        temp_db.record_upload('failed.jpg', 'en', 'failed', 'Error')

        result = temp_db.is_file_uploaded('failed.jpg', 'en')
        assert result is False

    def test_get_statistics_overall(self, temp_db):
        """Test getting overall statistics."""
        # Add some test data
        temp_db.record_upload('file1.jpg', 'en', 'success')
        temp_db.record_upload('file2.jpg', 'ar', 'success')
        temp_db.record_page_processing('Page1', 'en', 2, 1)
        temp_db.record_page_processing('Page2', 'ar', 1, 1)

        stats = temp_db.get_statistics()

        assert stats['total_uploads'] == 2
        assert stats['total_pages'] == 2

    def test_get_statistics_by_language(self, temp_db):
        """Test getting statistics for specific language."""
        temp_db.record_upload('file1.jpg', 'en', 'success')
        temp_db.record_upload('file2.jpg', 'en', 'success')
        temp_db.record_upload('file3.jpg', 'ar', 'success')
        temp_db.record_page_processing('Page1', 'en', 2, 2)

        stats = temp_db.get_statistics('en')

        assert stats['total_uploads'] == 2
        assert stats['total_pages'] == 1

    def test_upsert_behavior(self, temp_db):
        """Test that recording same file twice updates record."""
        temp_db.record_upload('test.jpg', 'en', 'success')
        temp_db.record_upload('test.jpg', 'en', 'failed', 'New error')

        with temp_db._get_connection() as conn:
            results = conn.execute(
                "SELECT * FROM uploads WHERE filename='test.jpg'"
            ).fetchall()

            # Should only have one record (updated)
            assert len(results) == 1
            assert results[0]['status'] == 'failed'
            assert results[0]['error'] == 'New error'
```

**Coverage:**
- ✅ Database initialization
- ✅ Recording uploads (success, failed, duplicate)
- ✅ Recording page processing
- ✅ Checking if file uploaded
- ✅ Statistics (overall and by language)
- ✅ UPSERT behavior

---

## Step 4: Uploader Tests (`tests/test_uploader.py`)

Test file upload logic with mocking.

```python
"""
Tests for file uploader.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.uploader import FileUploader


class TestFileUploader:
    """Tests for FileUploader class."""

    @pytest.fixture
    def uploader(self, mock_nc_api, mock_wiki_api, temp_db, sample_config):
        """Create FileUploader instance for testing."""
        return FileUploader(mock_nc_api, mock_wiki_api, temp_db, sample_config)

    def test_upload_file_success_url_method(self, uploader, mock_nc_api, mock_wiki_api):
        """Test successful file upload using URL method."""
        result = uploader.upload_file('test.jpg')

        # Should succeed
        assert result is True

        # Should have called NC Commons API
        mock_nc_api.get_image_url.assert_called_once_with('test.jpg')
        mock_nc_api.get_file_description.assert_called_once_with('test.jpg')

        # Should have called Wikipedia API
        mock_wiki_api.upload_from_url.assert_called_once()

    def test_upload_file_already_uploaded(self, uploader, temp_db):
        """Test uploading file that's already uploaded."""
        # Pre-populate database
        temp_db.record_upload('existing.jpg', 'en', 'success')

        result = uploader.upload_file('existing.jpg')

        # Should return False (not uploaded again)
        assert result is False

    def test_upload_file_duplicate(self, uploader, mock_wiki_api):
        """Test handling duplicate file error."""
        # Make upload return False (duplicate)
        mock_wiki_api.upload_from_url.return_value = False

        result = uploader.upload_file('duplicate.jpg')

        assert result is False

    def test_upload_file_falls_back_to_download(self, uploader, mock_wiki_api, mock_nc_api):
        """Test falling back to download method when URL upload fails."""
        # Make URL upload fail with copyupload error
        mock_wiki_api.upload_from_url.side_effect = Exception("copyupload disabled")

        # Mock download method
        with patch.object(uploader, '_upload_via_download') as mock_download:
            mock_download.return_value = True

            result = uploader.upload_file('test.jpg')

            # Should have tried download method
            mock_download.assert_called_once()

    def test_upload_file_error_recorded(self, uploader, mock_nc_api, temp_db):
        """Test that upload errors are recorded in database."""
        # Make API fail
        mock_nc_api.get_image_url.side_effect = Exception("API Error")

        result = uploader.upload_file('error.jpg')

        # Should return False
        assert result is False

        # Should record error in database
        with temp_db._get_connection() as conn:
            record = conn.execute(
                "SELECT * FROM uploads WHERE filename='error.jpg'"
            ).fetchone()

            assert record['status'] == 'failed'
            assert 'API Error' in record['error']

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
        assert '[[Category:OldCat1]]' not in result
        assert '[[Category:OldCat2]]' not in result

        # Should add NC Commons category
        assert '[[Category:Contains images from NC Commons]]' in result

        # Should preserve other text
        assert 'File description' in result
        assert 'More text' in result

    @patch('urllib.request.urlretrieve')
    @patch('tempfile.NamedTemporaryFile')
    def test_upload_via_download(
        self,
        mock_temp,
        mock_retrieve,
        uploader,
        mock_wiki_api,
        temp_db
    ):
        """Test upload via download method."""
        # Mock temporary file
        mock_temp.return_value.name = '/tmp/test.tmp'

        result = uploader._upload_via_download(
            'test.jpg',
            'http://example.com/test.jpg',
            'Description',
            'Comment',
            'en'
        )

        # Should have downloaded
        mock_retrieve.assert_called_once()

        # Should have uploaded from file
        mock_wiki_api.upload_from_file.assert_called_once()

        # Should succeed
        assert result is True
```

**Coverage:**
- ✅ Successful upload (URL method)
- ✅ Already uploaded check
- ✅ Duplicate file handling
- ✅ Fallback to download method
- ✅ Error recording in database
- ✅ Description processing
- ✅ Download and upload method

---

## Step 5: Processor Tests (`tests/test_processor.py`)

Test page processing logic.

```python
"""
Tests for page processor.
"""

import pytest
from unittest.mock import Mock
from src.processor import PageProcessor


class TestPageProcessor:
    """Tests for PageProcessor class."""

    @pytest.fixture
    def processor(self, mock_wiki_api, temp_db, sample_config):
        """Create PageProcessor instance for testing."""
        # Create mock uploader
        mock_uploader = Mock()
        mock_uploader.upload_file.return_value = True

        return PageProcessor(mock_wiki_api, mock_uploader, temp_db, sample_config)

    def test_process_page_with_templates(
        self,
        processor,
        mock_wiki_api,
        sample_nc_template_page,
        temp_db
    ):
        """Test processing page with NC templates."""
        # Set up mock to return page with templates
        mock_wiki_api.get_page_text.return_value = sample_nc_template_page

        result = processor.process_page('Test Page')

        # Should succeed
        assert result is True

        # Should have saved page
        mock_wiki_api.save_page.assert_called_once()

        # Check database record
        with temp_db._get_connection() as conn:
            record = conn.execute(
                "SELECT * FROM pages WHERE page_title='Test Page'"
            ).fetchone()

            assert record is not None
            assert record['templates_found'] == 2
            assert record['files_uploaded'] == 2

    def test_process_page_no_templates(self, processor, mock_wiki_api, temp_db):
        """Test processing page without NC templates."""
        mock_wiki_api.get_page_text.return_value = "Plain text page"

        result = processor.process_page('Plain Page')

        # Should return False (no modifications)
        assert result is False

        # Should NOT save page
        mock_wiki_api.save_page.assert_not_called()

        # Should still record in database
        with temp_db._get_connection() as conn:
            record = conn.execute(
                "SELECT * FROM pages WHERE page_title='Plain Page'"
            ).fetchone()

            assert record['templates_found'] == 0
            assert record['files_uploaded'] == 0

    def test_process_page_upload_fails(self, processor, mock_wiki_api, temp_db):
        """Test processing when file uploads fail."""
        mock_wiki_api.get_page_text.return_value = "{{NC|test.jpg|caption}}"

        # Make uploader fail
        processor.uploader.upload_file.return_value = False

        result = processor.process_page('Test Page')

        # Should return False (no files uploaded)
        assert result is False

        # Should NOT save page
        mock_wiki_api.save_page.assert_not_called()

    def test_process_page_adds_category(self, processor, mock_wiki_api):
        """Test that category is added to page."""
        page_text = "{{NC|test.jpg|caption}}"
        mock_wiki_api.get_page_text.return_value = page_text

        processor.process_page('Test Page')

        # Get the saved text
        call_args = mock_wiki_api.save_page.call_args
        saved_text = call_args[0][1]

        # Should contain category
        assert '[[Category:Contains images from NC Commons]]' in saved_text

    def test_process_page_doesnt_duplicate_category(self, processor, mock_wiki_api):
        """Test that category isn't added if already present."""
        page_text = """
        {{NC|test.jpg|caption}}
        [[Category:Contains images from NC Commons]]
        """
        mock_wiki_api.get_page_text.return_value = page_text

        processor.process_page('Test Page')

        call_args = mock_wiki_api.save_page.call_args
        saved_text = call_args[0][1]

        # Should only have one category
        assert saved_text.count('[[Category:Contains images from NC Commons]]') == 1

    def test_process_page_replaces_templates(self, processor, mock_wiki_api):
        """Test that NC templates are replaced with file syntax."""
        page_text = "Text before {{NC|test.jpg|My caption}} text after"
        mock_wiki_api.get_page_text.return_value = page_text

        processor.process_page('Test Page')

        call_args = mock_wiki_api.save_page.call_args
        saved_text = call_args[0][1]

        # Should replace template
        assert '{{NC|test.jpg|My caption}}' not in saved_text
        assert '[[File:test.jpg|thumb|My caption]]' in saved_text

    def test_process_page_continues_on_error(self, processor, mock_wiki_api, temp_db):
        """Test that processing continues when individual files fail."""
        page_text = """
        {{NC|success.jpg|caption1}}
        {{NC|fail.jpg|caption2}}
        {{NC|success2.jpg|caption3}}
        """
        mock_wiki_api.get_page_text.return_value = page_text

        # Make one upload fail
        def upload_side_effect(filename):
            if filename == 'fail.jpg':
                raise Exception("Upload error")
            return True

        processor.uploader.upload_file.side_effect = upload_side_effect

        result = processor.process_page('Test Page')

        # Should still succeed (2 out of 3 uploaded)
        assert result is True

        # Database should show 2 uploaded
        with temp_db._get_connection() as conn:
            record = conn.execute(
                "SELECT * FROM pages WHERE page_title='Test Page'"
            ).fetchone()

            assert record['templates_found'] == 3
            assert record['files_uploaded'] == 2

    def test_apply_replacements(self, processor):
        """Test template replacement logic."""
        text = "Before {{NC|file1.jpg}} middle {{NC|file2.jpg}} after"
        replacements = {
            '{{NC|file1.jpg}}': '[[File:file1.jpg|thumb|]]',
            '{{NC|file2.jpg}}': '[[File:file2.jpg|thumb|]]'
        }

        result = processor._apply_replacements(text, replacements)

        assert '{{NC|file1.jpg}}' not in result
        assert '{{NC|file2.jpg}}' not in result
        assert '[[File:file1.jpg|thumb|]]' in result
        assert '[[File:file2.jpg|thumb|]]' in result
```

**Coverage:**
- ✅ Processing page with templates
- ✅ Processing page without templates
- ✅ Handling upload failures
- ✅ Adding category
- ✅ Not duplicating category
- ✅ Template replacement
- ✅ Continuing on individual errors

---

## Running Tests

### Run all tests:
```bash
pytest
```

### Run with coverage:
```bash
pytest --cov=src --cov-report=html
```

### Run specific test file:
```bash
pytest tests/test_parsers.py
```

### Run specific test:
```bash
pytest tests/test_parsers.py::TestParseLanguageList::test_parse_simple_language_list
```

### Run with verbose output:
```bash
pytest -v
```

---

## Test Coverage Goals

Target coverage:
- ✅ Parsers: 90%+ (easy to test, pure functions)
- ✅ Database: 85%+ (straightforward SQLite operations)
- ✅ Uploader: 75%+ (mocking required)
- ✅ Processor: 75%+ (integration-like tests)
- ⚠️ wiki_api: Skip (mostly mwclient wrapper)
- ⚠️ bot.py: Skip (integration/manual testing)

---

## Summary

**Total test files:** 5
**Total test lines:** ~400
**Test cases:** ~35

**What we test:**
1. **Parsers** - Language lists, NC templates, category removal
2. **Database** - CRUD operations, statistics, UPSERT
3. **Uploader** - Upload methods, fallback, error handling
4. **Processor** - Page processing, template replacement, error recovery

**What we don't test:**
- `wiki_api.py` - It's mostly a thin wrapper around mwclient
- `bot.py` - Main orchestration (test manually)
- `reports.py` - Simple queries (test manually)

**Why this is good:**
- ✅ Tests core business logic
- ✅ Uses mocking appropriately
- ✅ Fast to run (no network calls)
- ✅ Easy to maintain
- ✅ Good coverage without over-testing
- ✅ All test code in English
