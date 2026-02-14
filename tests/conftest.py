"""
Pytest fixtures for NC Commons bot tests.

Provides shared fixtures for mocking and test data.
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest
from src.database import Database
from src.wiki_api import NCCommonsAPI, WikipediaAPI


@pytest.fixture
def temp_db():
    """
    Create a temporary database for testing.

    Automatically cleaned up after test.
    """
    # Create temporary file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
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
        "nc_commons": {"site": "nccommons.org", "language_page": "User:Mr. Ibrahem/import bot"},
        "wikipedia": {
            "upload_comment": "Bot: import from nccommons.org",
            "category": "Category:Contains images from NC Commons",
        },
        "database": {"path": "./test.db"},
        "processing": {
            "max_pages_per_language": 1000,
            "max_retry_attempts": 3,
            "retry_delay_seconds": 5,
            "retry_backoff_multiplier": 2,
        },
        "logging": {"level": "INFO", "file": "./test.log"},
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
    api.lang = "en"

    # Mock methods
    api.get_pages_with_template.return_value = ["Page 1", "Page 2"]
    api.get_page_text.return_value = "{{NC|test.jpg|caption}}"
    api.save_page.return_value = None
    api.upload_from_url.return_value = {"success": True}
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
