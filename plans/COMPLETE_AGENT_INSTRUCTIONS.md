# AGENT INSTRUCTIONS: Build NC Commons Bot from Scratch

## Mission

You will write a complete NC Commons Import Bot from scratch. The old code will be deleted - you are creating everything new using modern libraries (mwclient, wikitextparser, logging).

**IMPORTANT:** All code comments, docstrings, variable names, and commit messages MUST be in English only.

---

## Understanding the Bot's Purpose

The bot performs 5 simple steps:

1. **Fetch language list** from NC Commons page
2. **Find pages** containing {{NC|filename.jpg}} templates on Wikipedia
3. **Upload files** from NC Commons to Wikipedia
4. **Replace templates** with [[File:filename.jpg|thumb|caption]]
5. **Record everything** in SQLite database

**Keep it simple!** Don't over-engineer.

---

## Project Structure to Create

```
nc_commons_bot/
├── config.yaml              # Configuration file
├── credentials.ini.example  # Credentials template
├── requirements.txt         # Python dependencies
├── README.md               # Documentation
├── .gitignore              # Git ignore file
├── bot.py                  # Main entry point
├── src/                    # Source code directory
│   ├── __init__.py         # Package init (can be empty)
│   ├── wiki_api.py         # MediaWiki API wrapper (200 lines)
│   ├── parsers.py          # Wikitext parsing (100 lines)
│   ├── uploader.py         # File upload logic (100 lines)
│   ├── processor.py        # Page processing (100 lines)
│   ├── database.py         # SQLite operations (150 lines)
│   └── reports.py          # Reporting (50 lines)
└── tests/
    ├── __init__.py
    └── conftest.py
```

**Total target: ~900 lines of clean Python code**

---

## Step-by-Step Implementation

### Step 1: Create Project Files

Start by creating the basic project structure and configuration files.

#### 1.1 Create `requirements.txt`

```txt
mwclient>=0.10.1
wikitextparser>=0.55.0
PyYAML>=6.0
```

**Why these libraries:**

-   `mwclient`: Standard library for MediaWiki API (replaces custom newapi)
-   `wikitextparser`: Parse wikitext templates
-   `PyYAML`: Load configuration from YAML files

#### 1.2 Create `config.yaml`

```yaml
# NC Commons configuration
nc_commons:
    site: "nccommons.org"
    language_page: "User:Mr. Ibrahem/import bot"

# Wikipedia configuration
wikipedia:
    upload_comment: "Bot: import from nccommons.org"
    category: "Category:Contains images from NC Commons"

# Database configuration
database:
    path: "./data/nc_files.db"

# Processing limits and retry logic
processing:
    max_pages_per_language: 5000
    max_retry_attempts: 3
    retry_delay_seconds: 5
    retry_backoff_multiplier: 2

# Logging configuration
logging:
    level: "INFO" # DEBUG, INFO, WARNING, ERROR
    file: "./logs/bot.log"
    max_bytes: 10485760 # 10MB
    backup_count: 5
```

**Configuration explained:**

-   `nc_commons.site`: NC Commons domain
-   `nc_commons.language_page`: Page containing list of languages to process
-   `wikipedia.upload_comment`: Edit summary for uploads
-   `wikipedia.category`: Category to add to imported files
-   `database.path`: SQLite database file location
-   `processing.*`: Retry logic and limits
-   `logging.*`: Where and how to log

#### 1.3 Create `credentials.ini.example`

```ini
# Copy this file to credentials.ini and fill in your credentials
# NEVER commit credentials.ini to git!

[nccommons]
username = YourNCCommonsUsername
password = YourNCCommonsPassword

[wikipedia]
# Use bot password format: BotName@BotPassword
username = YourWikipediaBot@BotPassword
password = YourBotPasswordToken
```

**Security note:** credentials.ini should be in .gitignore

#### 1.4 Create `.gitignore`

```gitignore
# Credentials - NEVER commit!
credentials.ini

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
*.egg-info/

# Data and logs
data/
logs/
*.db
*.log

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
```

#### 1.5 Create `src/__init__.py`

```python
"""
NC Commons Import Bot

A simple bot to import files from NC Commons to Wikipedia.
"""

__version__ = "2.0.0"
```

---

### Step 2: Implement Core API Wrapper

Create `src/wiki_api.py` - this is the foundation of the bot.

#### Design Requirements:

1. **Base class `WikiAPI`:**

    - Connect to MediaWiki sites using mwclient
    - Handle login
    - Implement retry logic with exponential backoff
    - Log all API operations
    - Methods: `get_page_text()`, `save_page()`

2. **Subclass `NCCommonsAPI(WikiAPI)`:**

    - Specific to NC Commons operations
    - Methods: `get_image_url()`, `get_file_description()`

3. **Subclass `WikipediaAPI(WikiAPI)`:**
    - Specific to Wikipedia operations
    - Methods: `get_pages_with_template()`, `upload_from_url()`, `upload_from_file()`

#### Implementation Guide:

```python
"""
MediaWiki API wrapper using mwclient.

This module provides classes for interacting with NC Commons and Wikipedia
through the MediaWiki API.
"""

import mwclient
import logging
import time
from typing import List, Dict, Optional
from functools import wraps

logger = logging.getLogger(__name__)

# Retry decorator implementation
def retry(max_attempts: int = 3, delay: int = 5, backoff: int = 2):
    """
    Decorator to retry functions with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay in seconds
        backoff: Multiplier for exponential backoff

    Returns:
        Decorated function that retries on failure
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            current_delay = delay

            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempt += 1
                    if attempt >= max_attempts:
                        logger.error(f"All {max_attempts} attempts failed for {func.__name__}")
                        raise

                    logger.warning(
                        f"Attempt {attempt}/{max_attempts} failed for {func.__name__}: {e}. "
                        f"Retrying in {current_delay}s..."
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff

        return wrapper
    return decorator


class WikiAPI:
    """
    Base class for MediaWiki API interactions using mwclient.

    Provides common functionality for connecting to and interacting with
    MediaWiki sites.
    """

    def __init__(self, site: str, username: Optional[str] = None, password: Optional[str] = None):
        """
        Initialize connection to MediaWiki site.

        Args:
            site: Site URL (e.g., 'en.wikipedia.org')
            username: Optional username for login
            password: Optional password for login
        """
        logger.info(f"Connecting to {site}")
        self.site = mwclient.Site(site)

        if username and password:
            logger.info(f"Logging in as {username}")
            self.site.login(username, password)

    def get_page_text(self, title: str) -> str:
        """
        Get the text content of a page.

        Args:
            title: Page title

        Returns:
            Page text content
        """
        logger.debug(f"Fetching page: {title}")
        page = self.site.pages[title]
        return page.text()

    def save_page(self, title: str, text: str, summary: str):
        """
        Save content to a page.

        Args:
            title: Page title
            text: New page content
            summary: Edit summary
        """
        logger.info(f"Saving page: {title}")
        page = self.site.pages[title]
        page.save(text, summary=summary)


class NCCommonsAPI(WikiAPI):
    """
    API wrapper for NC Commons operations.

    Provides methods specific to fetching files and information from NC Commons.
    """

    def __init__(self, username: str, password: str):
        """
        Initialize NC Commons API connection.

        Args:
            username: NC Commons username
            password: NC Commons password
        """
        super().__init__('nccommons.org', username, password)

    def get_image_url(self, filename: str) -> str:
        """
        Get the direct URL to an image file.

        Args:
            filename: Image filename (with or without 'File:' prefix)

        Returns:
            Direct URL to the image file
        """
        if not filename.startswith('File:'):
            filename = f'File:{filename}'

        logger.debug(f"Getting image URL for: {filename}")
        page = self.site.pages[filename]
        return page.imageinfo['url']

    def get_file_description(self, filename: str) -> str:
        """
        Get the file description page content.

        Args:
            filename: Image filename (with or without 'File:' prefix)

        Returns:
            File description page wikitext
        """
        if not filename.startswith('File:'):
            filename = f'File:{filename}'

        return self.get_page_text(filename)


class WikipediaAPI(WikiAPI):
    """
    API wrapper for Wikipedia operations.

    Provides methods specific to editing Wikipedia and uploading files.
    """

    def __init__(self, language_code: str, username: str, password: str):
        """
        Initialize Wikipedia API connection.

        Args:
            language_code: Wikipedia language code (e.g., 'en', 'ar', 'fr')
            username: Wikipedia username (use bot password format)
            password: Wikipedia password (bot password token)
        """
        self.lang = language_code
        site = f'{language_code}.wikipedia.org'
        super().__init__(site, username, password)

    def get_pages_with_template(self, template: str, limit: int = 5000) -> List[str]:
        """
        Get all pages that transclude a template.

        Args:
            template: Template name (with or without 'Template:' prefix)
            limit: Maximum number of pages to retrieve

        Returns:
            List of page titles
        """
        if not template.startswith('Template:'):
            template = f'Template:{template}'

        logger.info(f"Finding pages with template: {template}")

        template_page = self.site.pages[template]
        pages = [page.name for page in template_page.embeddedin(limit=limit)]

        logger.info(f"Found {len(pages)} pages")
        return pages

    def upload_from_url(self, filename: str, url: str, description: str, comment: str) -> bool:
        """
        Upload a file from URL to Wikipedia.

        Args:
            filename: Target filename on Wikipedia
            url: Source URL of the file
            description: File description page content
            comment: Upload comment/summary

        Returns:
            True if successful, False if duplicate

        Raises:
            Exception: If upload fails for reasons other than duplicate
        """
        try:
            logger.info(f"Uploading from URL: {filename}")

            result = self.site.upload(
                file=None,
                filename=filename,
                description=description,
                comment=comment,
                url=url
            )

            logger.info(f"Upload successful: {filename}")
            return True

        except mwclient.errors.APIError as e:
            error_msg = str(e).lower()

            if 'duplicate' in error_msg:
                logger.warning(f"File is duplicate: {filename}")
                return False

            logger.error(f"Upload failed: {e}")
            raise

    def upload_from_file(self, filename: str, filepath: str, description: str, comment: str) -> bool:
        """
        Upload a file from local filesystem to Wikipedia.

        Args:
            filename: Target filename on Wikipedia
            filepath: Path to local file
            description: File description page content
            comment: Upload comment/summary

        Returns:
            True if successful, False if duplicate

        Raises:
            Exception: If upload fails for reasons other than duplicate
        """
        try:
            logger.info(f"Uploading from file: {filename}")

            with open(filepath, 'rb') as f:
                result = self.site.upload(
                    file=f,
                    filename=filename,
                    description=description,
                    comment=comment
                )

            logger.info(f"Upload successful: {filename}")
            return True

        except mwclient.errors.APIError as e:
            error_msg = str(e).lower()

            if 'duplicate' in error_msg:
                logger.warning(f"File is duplicate: {filename}")
                return False

            logger.error(f"Upload failed: {e}")
            raise
```

**Key points:**

-   All API calls wrapped with retry decorator
-   Clear logging at appropriate levels
-   Type hints for all parameters
-   Comprehensive docstrings
-   Handle duplicate files gracefully
-   All strings in English

---

### Step 3: Implement Wikitext Parsers

Create `src/parsers.py` for parsing wikitext using wikitextparser.

#### Requirements:

1. Parse language list from NC Commons page format: `{{User:Mr. Ibrahem/import bot/line|LANG}}`
2. Extract {{NC}} templates from Wikipedia pages: `{{NC|filename.jpg|caption}}`
3. Convert templates to file syntax: `[[File:filename.jpg|thumb|caption]]`
4. Remove category tags from text

#### Implementation:

```python
"""
Wikitext parsing utilities using wikitextparser.

This module provides functions to parse and manipulate wikitext content.
"""

import wikitextparser as wtp
import re
import logging
from typing import List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


def parse_language_list(page_text: str) -> List[str]:
    """
    Extract language codes from the NC Commons language list page.

    Expected format: {{User:Mr. Ibrahem/import bot/line|LANGUAGE_CODE}}

    Args:
        page_text: Wikitext content of the language list page

    Returns:
        List of language codes (e.g., ['en', 'ar', 'fr'])
    """
    logger.info("Parsing language list")

    parsed = wtp.parse(page_text)
    languages = []

    template_name_pattern = "user:mr. ibrahem/import bot/line"

    for template in parsed.templates:
        # Normalize template name for comparison
        template_name = str(template.normal_name()).strip().lower().replace('_', ' ')

        if template_name_pattern in template_name:
            # Extract first positional argument (language code)
            arg = template.get_arg('1')
            if arg and arg.value:
                lang_code = arg.value.strip()
                languages.append(lang_code)
                logger.debug(f"Found language: {lang_code}")

    logger.info(f"Parsed {len(languages)} languages: {languages}")
    return languages


@dataclass
class NCTemplate:
    """
    Represents a {{NC}} template found in a Wikipedia page.

    Attributes:
        original_text: Original template wikitext
        filename: Image filename
        caption: Image caption (optional)
    """
    original_text: str
    filename: str
    caption: str = ""

    def to_file_syntax(self) -> str:
        """
        Convert NC template to standard Wikipedia file syntax.

        Returns:
            Wikitext for embedded file (e.g., [[File:example.jpg|thumb|caption]])
        """
        return f"[[File:{self.filename}|thumb|{self.caption}]]"


def extract_nc_templates(page_text: str) -> List[NCTemplate]:
    """
    Extract all {{NC}} templates from a Wikipedia page.

    Expected format: {{NC|filename.jpg|caption}}

    Args:
        page_text: Wikitext content of the page

    Returns:
        List of NCTemplate objects
    """
    logger.debug("Extracting NC templates")

    parsed = wtp.parse(page_text)
    templates = []

    for template in parsed.templates:
        # Check if this is an NC template
        template_name = str(template.normal_name()).strip().lower()

        if template_name == 'nc':
            # Extract filename (first argument)
            filename = ""
            arg1 = template.get_arg('1')
            if arg1 and arg1.value:
                filename = arg1.value.strip()

            # Extract caption (second argument, optional)
            caption = ""
            arg2 = template.get_arg('2')
            if arg2 and arg2.value:
                caption = arg2.value.strip()

            # Only add if filename exists
            if filename:
                nc_template = NCTemplate(
                    original_text=template.string,
                    filename=filename,
                    caption=caption
                )
                templates.append(nc_template)
                logger.debug(f"Found NC template: {filename}")

    logger.info(f"Extracted {len(templates)} NC templates")
    return templates


def remove_categories(text: str) -> str:
    """
    Remove all category tags from wikitext.

    Args:
        text: Wikitext content

    Returns:
        Text with all [[Category:...]] tags removed
    """
    # Remove category tags (case-insensitive)
    cleaned = re.sub(r'\[\[Category:.*?\]\]', '', text, flags=re.IGNORECASE | re.DOTALL)
    return cleaned.strip()
```

**Key points:**

-   Dataclass for template representation
-   Clear conversion to file syntax
-   Robust parsing with fallbacks
-   Comprehensive logging
-   All documentation in English

---

### Step 4: Implement Database Layer

Create `src/database.py` for SQLite operations.

#### Database Schema:

```sql
-- Tracks all file uploads
CREATE TABLE uploads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    language TEXT NOT NULL,
    uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL,  -- 'success', 'failed', 'duplicate'
    error TEXT,
    UNIQUE(filename, language)
);

-- Tracks page processing
CREATE TABLE pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_title TEXT NOT NULL,
    language TEXT NOT NULL,
    processed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    templates_found INTEGER,
    files_uploaded INTEGER,
    UNIQUE(page_title, language)
);

-- Indexes for performance
CREATE INDEX idx_uploads_lang ON uploads(language);
CREATE INDEX idx_uploads_status ON uploads(status);
CREATE INDEX idx_pages_lang ON pages(language);
```

#### Implementation:

```python
"""
SQLite database operations for tracking bot activity.

This module handles all database interactions including recording uploads,
page processing, and generating statistics.
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class Database:
    """
    SQLite database wrapper for bot operations.

    Handles storage and retrieval of upload records, page processing logs,
    and statistics.
    """

    def __init__(self, db_path: str):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)

        # Create parent directory if it doesn't exist
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database schema
        self._init_schema()

        logger.info(f"Database initialized at {self.db_path}")

    @contextmanager
    def _get_connection(self):
        """
        Context manager for database connections.

        Automatically handles commit/rollback and connection cleanup.

        Yields:
            sqlite3.Connection: Database connection
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row  # Access columns by name

        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()

    def _init_schema(self):
        """Create database tables if they don't exist."""
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS uploads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    language TEXT NOT NULL,
                    uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    status TEXT NOT NULL,
                    error TEXT,
                    UNIQUE(filename, language)
                );

                CREATE TABLE IF NOT EXISTS pages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    page_title TEXT NOT NULL,
                    language TEXT NOT NULL,
                    processed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    templates_found INTEGER,
                    files_uploaded INTEGER,
                    UNIQUE(page_title, language)
                );

                CREATE INDEX IF NOT EXISTS idx_uploads_lang ON uploads(language);
                CREATE INDEX IF NOT EXISTS idx_uploads_status ON uploads(status);
                CREATE INDEX IF NOT EXISTS idx_pages_lang ON pages(language);
            """)

        logger.debug("Database schema initialized")

    def record_upload(self, filename: str, language: str, status: str, error: Optional[str] = None):
        """
        Record a file upload attempt.

        Args:
            filename: Name of the uploaded file
            language: Wikipedia language code
            status: Upload status ('success', 'failed', 'duplicate')
            error: Error message if failed (optional)
        """
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO uploads
                (filename, language, status, error, uploaded_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (filename, language, status, error))

        logger.debug(f"Recorded upload: {filename} ({language}) - {status}")

    def record_page_processing(
        self,
        page_title: str,
        language: str,
        templates_found: int,
        files_uploaded: int
    ):
        """
        Record page processing activity.

        Args:
            page_title: Title of the processed page
            language: Wikipedia language code
            templates_found: Number of NC templates found
            files_uploaded: Number of files successfully uploaded
        """
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO pages
                (page_title, language, templates_found, files_uploaded, processed_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (page_title, language, templates_found, files_uploaded))

        logger.debug(f"Recorded page: {page_title} ({language})")

    def is_file_uploaded(self, filename: str, language: str) -> bool:
        """
        Check if a file was already uploaded successfully.

        Args:
            filename: Name of the file
            language: Wikipedia language code

        Returns:
            True if file was previously uploaded successfully
        """
        with self._get_connection() as conn:
            result = conn.execute("""
                SELECT COUNT(*) as count FROM uploads
                WHERE filename = ? AND language = ? AND status = 'success'
            """, (filename, language)).fetchone()

            return result['count'] > 0

    def get_statistics(self, language: Optional[str] = None) -> Dict[str, int]:
        """
        Get upload and processing statistics.

        Args:
            language: Optional language code to filter by

        Returns:
            Dictionary with statistics (total_uploads, total_pages, etc.)
        """
        with self._get_connection() as conn:
            if language:
                # Stats for specific language
                uploads = conn.execute("""
                    SELECT COUNT(*) as count FROM uploads
                    WHERE language = ? AND status = 'success'
                """, (language,)).fetchone()['count']

                pages = conn.execute("""
                    SELECT COUNT(*) as count FROM pages
                    WHERE language = ?
                """, (language,)).fetchone()['count']
            else:
                # Overall stats
                uploads = conn.execute("""
                    SELECT COUNT(*) as count FROM uploads
                    WHERE status = 'success'
                """).fetchone()['count']

                pages = conn.execute("""
                    SELECT COUNT(*) as count FROM pages
                """).fetchone()['count']

            return {
                'total_uploads': uploads,
                'total_pages': pages
            }
```

**Key points:**

-   Context manager for safe connection handling
-   Proper error handling with rollback
-   UPSERT logic (INSERT OR REPLACE)
-   Indexes for performance
-   Statistics queries
-   All comments in English

---

### Step 5: Implement File Uploader

Create `src/uploader.py` for file upload logic.

#### Requirements:

1. Check if file already uploaded (avoid duplicates)
2. Get file URL from NC Commons
3. Get file description from NC Commons
4. Process description (remove categories, add NC Commons category)
5. Try URL upload first (faster)
6. Fall back to download+upload if URL upload disabled
7. Record all attempts in database

#### Implementation:

```python
"""
File upload operations from NC Commons to Wikipedia.

This module handles downloading files from NC Commons and uploading them
to Wikipedia, with appropriate error handling and database recording.
"""

import logging
import tempfile
import urllib.request
from pathlib import Path

from src.wiki_api import NCCommonsAPI, WikipediaAPI
from src.database import Database
from src.parsers import remove_categories

logger = logging.getLogger(__name__)


class FileUploader:
    """
    Handles file uploads from NC Commons to Wikipedia.

    Manages the complete upload workflow including fetching from NC Commons,
    processing descriptions, uploading to Wikipedia, and recording results.
    """

    def __init__(
        self,
        nc_api: NCCommonsAPI,
        wiki_api: WikipediaAPI,
        database: Database,
        config: dict
    ):
        """
        Initialize file uploader.

        Args:
            nc_api: NC Commons API client
            wiki_api: Wikipedia API client
            database: Database instance for recording uploads
            config: Configuration dictionary
        """
        self.nc_api = nc_api
        self.wiki_api = wiki_api
        self.db = database
        self.config = config

    def upload_file(self, filename: str) -> bool:
        """
        Upload a file from NC Commons to Wikipedia.

        Workflow:
        1. Check if already uploaded
        2. Fetch file info from NC Commons
        3. Process file description
        4. Try URL upload
        5. Fall back to file upload if needed
        6. Record result in database

        Args:
            filename: Name of the file to upload

        Returns:
            True if upload succeeded, False if duplicate or already uploaded
        """
        lang = self.wiki_api.lang

        # Check if already uploaded
        if self.db.is_file_uploaded(filename, lang):
            logger.info(f"File already uploaded: {filename}")
            return False

        try:
            # Get file information from NC Commons
            logger.info(f"Fetching file from NC Commons: {filename}")
            file_url = self.nc_api.get_image_url(filename)
            description = self.nc_api.get_file_description(filename)

            # Process description
            description = self._process_description(description)

            # Upload comment from config
            comment = self.config['wikipedia']['upload_comment']

            # Try URL upload first (faster, doesn't require download)
            try:
                success = self.wiki_api.upload_from_url(
                    filename=filename,
                    url=file_url,
                    description=description,
                    comment=comment
                )

                if success:
                    self.db.record_upload(filename, lang, 'success')
                    logger.info(f"Upload successful (URL method): {filename}")
                    return True
                else:
                    # Duplicate file
                    self.db.record_upload(filename, lang, 'duplicate')
                    return False

            except Exception as url_error:
                # URL upload not allowed or failed, try file upload
                error_msg = str(url_error).lower()

                if 'url' in error_msg or 'copyupload' in error_msg:
                    logger.info(f"URL upload not allowed, trying file upload: {filename}")
                    return self._upload_via_download(filename, file_url, description, comment, lang)
                else:
                    # Other error, don't retry
                    raise

        except Exception as e:
            logger.error(f"Upload failed for {filename}: {e}")
            self.db.record_upload(filename, lang, 'failed', str(e))
            return False

    def _upload_via_download(
        self,
        filename: str,
        url: str,
        description: str,
        comment: str,
        language: str
    ) -> bool:
        """
        Download file from URL then upload to Wikipedia.

        Fallback method when direct URL upload is not allowed.

        Args:
            filename: Target filename
            url: Source URL
            description: File description
            comment: Upload comment
            language: Language code

        Returns:
            True if successful, False if duplicate
        """
        temp_file = None

        try:
            # Download to temporary file
            logger.info(f"Downloading file: {filename}")
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.tmp')
            temp_path = temp_file.name
            temp_file.close()

            urllib.request.urlretrieve(url, temp_path)
            logger.debug(f"Downloaded to: {temp_path}")

            # Upload from file
            success = self.wiki_api.upload_from_file(
                filename=filename,
                filepath=temp_path,
                description=description,
                comment=comment
            )

            if success:
                self.db.record_upload(filename, language, 'success')
                logger.info(f"Upload successful (file method): {filename}")
                return True
            else:
                # Duplicate
                self.db.record_upload(filename, language, 'duplicate')
                return False

        finally:
            # Clean up temporary file
            if temp_file:
                Path(temp_path).unlink(missing_ok=True)
                logger.debug(f"Cleaned up temp file: {temp_path}")

    def _process_description(self, description: str) -> str:
        """
        Process file description for upload to Wikipedia.

        Removes existing categories and adds NC Commons import category.

        Args:
            description: Original file description from NC Commons

        Returns:
            Processed description ready for Wikipedia
        """
        # Remove all existing categories
        processed = remove_categories(description)

        # Add NC Commons category
        category = self.config['wikipedia']['category']
        processed += f"\n[[{category}]]"

        return processed.strip()
```

**Key points:**

-   Two upload methods (URL and file)
-   Automatic fallback on error
-   Temporary file cleanup
-   Database recording for all outcomes
-   Description processing
-   Comprehensive error handling

---

### Step 6: Implement Page Processor

Create `src/processor.py` for processing Wikipedia pages.

#### Requirements:

1. Fetch page content
2. Extract {{NC}} templates
3. Upload each file
4. Build replacement map
5. Replace templates with file syntax
6. Add category if not present
7. Save page with summary
8. Record in database

#### Implementation:

```python
"""
Wikipedia page processing operations.

This module handles finding and processing pages that contain NC templates,
coordinating the upload of files and updating of page content.
"""

import logging

from src.wiki_api import WikipediaAPI
from src.database import Database
from src.uploader import FileUploader
from src.parsers import extract_nc_templates

logger = logging.getLogger(__name__)


class PageProcessor:
    """
    Processes Wikipedia pages containing NC templates.

    Finds NC templates, uploads the referenced files, and replaces templates
    with standard Wikipedia file syntax.
    """

    def __init__(
        self,
        wiki_api: WikipediaAPI,
        uploader: FileUploader,
        database: Database,
        config: dict
    ):
        """
        Initialize page processor.

        Args:
            wiki_api: Wikipedia API client
            uploader: File uploader instance
            database: Database instance
            config: Configuration dictionary
        """
        self.wiki_api = wiki_api
        self.uploader = uploader
        self.db = database
        self.config = config

    def process_page(self, page_title: str) -> bool:
        """
        Process a single Wikipedia page.

        Workflow:
        1. Fetch page content
        2. Extract NC templates
        3. Upload files
        4. Replace templates
        5. Add category
        6. Save page
        7. Record in database

        Args:
            page_title: Title of the page to process

        Returns:
            True if page was modified, False otherwise
        """
        logger.info(f"Processing page: {page_title}")

        try:
            # Get page content
            page_text = self.wiki_api.get_page_text(page_title)

            # Extract NC templates
            templates = extract_nc_templates(page_text)

            if not templates:
                logger.info("No NC templates found on page")
                self.db.record_page_processing(page_title, self.wiki_api.lang, 0, 0)
                return False

            logger.info(f"Found {len(templates)} NC templates")

            # Process each template
            replacements = {}
            files_uploaded = 0

            for template in templates:
                logger.info(f"Processing file: {template.filename}")

                try:
                    # Upload file
                    uploaded = self.uploader.upload_file(template.filename)

                    if uploaded:
                        files_uploaded += 1
                        # Map original template to file syntax
                        replacements[template.original_text] = template.to_file_syntax()
                        logger.info(f"File uploaded successfully: {template.filename}")
                    else:
                        logger.info(f"File not uploaded (duplicate or error): {template.filename}")

                except Exception as e:
                    logger.error(f"Failed to upload {template.filename}: {e}")
                    # Continue with other files

            # Record page processing
            self.db.record_page_processing(
                page_title,
                self.wiki_api.lang,
                len(templates),
                files_uploaded
            )

            # If any files were uploaded, update the page
            if replacements:
                new_text = self._apply_replacements(page_text, replacements)

                # Add category if not present
                category = f"[[{self.config['wikipedia']['category']}]]"
                if category not in new_text:
                    new_text += f"\n{category}"
                    logger.debug("Added NC Commons category to page")

                # Save page
                summary = f"Bot: Imported {files_uploaded} file(s) from NC Commons"
                self.wiki_api.save_page(page_title, new_text, summary)

                logger.info(f"Page updated: {files_uploaded} files imported")
                return True
            else:
                logger.info("No files were uploaded, page not modified")
                return False

        except Exception as e:
            logger.error(f"Error processing page {page_title}: {e}")
            return False

    def _apply_replacements(self, text: str, replacements: dict) -> str:
        """
        Apply template replacements to page text.

        Args:
            text: Original page text
            replacements: Dictionary mapping original templates to new syntax

        Returns:
            Updated page text with replacements applied
        """
        new_text = text

        for original, replacement in replacements.items():
            new_text = new_text.replace(original, replacement)
            logger.debug(f"Replaced: {original[:50]}... -> {replacement[:50]}...")

        return new_text
```

**Key points:**

-   Continue processing even if individual files fail
-   Build replacement map before modifying text
-   Add category only if not present
-   Informative edit summary
-   Comprehensive logging

---

### Step 7: Implement Simple Reporting

Create `src/reports.py` for generating reports.

#### Implementation:

```python
"""
Report generation from database.

This module provides functionality to generate summary reports and statistics
from the bot's database.
"""

import json
import logging
from pathlib import Path

from src.database import Database

logger = logging.getLogger(__name__)


class Reporter:
    """
    Generates reports from bot activity database.

    Provides methods to generate summary statistics and export to JSON.
    """

    def __init__(self, database: Database):
        """
        Initialize reporter.

        Args:
            database: Database instance to query
        """
        self.db = database

    def generate_summary(self) -> dict:
        """
        Generate summary report of bot activity.

        Returns:
            Dictionary containing summary statistics
        """
        logger.info("Generating summary report")

        with self.db._get_connection() as conn:
            # Overall statistics
            total_stats = self.db.get_statistics()

            # Per-language statistics
            by_language = conn.execute("""
                SELECT
                    language,
                    COUNT(*) as upload_count
                FROM uploads
                WHERE status = 'success'
                GROUP BY language
                ORDER BY upload_count DESC
            """).fetchall()

            # Recent errors
            recent_errors = conn.execute("""
                SELECT
                    filename,
                    language,
                    error,
                    uploaded_at
                FROM uploads
                WHERE status = 'failed'
                ORDER BY uploaded_at DESC
                LIMIT 10
            """).fetchall()

            # Build report
            report = {
                'total': dict(total_stats),
                'by_language': [dict(row) for row in by_language],
                'recent_errors': [dict(row) for row in recent_errors]
            }

            return report

    def save_report(self, output_path: str = './reports/summary.json'):
        """
        Generate and save summary report to JSON file.

        Args:
            output_path: Path to save the report
        """
        # Generate report
        report = self.generate_summary()

        # Ensure output directory exists
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Write to file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"Report saved to {output_path}")


# Standalone script functionality
if __name__ == '__main__':
    # Allow running as standalone script
    import sys

    db_path = sys.argv[1] if len(sys.argv) > 1 else './data/nc_files.db'
    output = sys.argv[2] if len(sys.argv) > 2 else './reports/summary.json'

    db = Database(db_path)
    reporter = Reporter(db)
    reporter.save_report(output)

    print(f"Report generated: {output}")
```

**Key points:**

-   Queries for overall and per-language stats
-   Recent errors tracking
-   JSON export with proper encoding
-   Can run standalone
-   Simple and focused

---

### Step 8: Implement Main Bot Entry Point

Create `bot.py` at the project root.

#### Requirements:

1. Parse command-line arguments
2. Load configuration from YAML
3. Setup logging
4. Load credentials
5. Initialize database
6. Connect to NC Commons
7. Get language list or use filter
8. Process each language
9. Show statistics

#### Implementation:

```python
#!/usr/bin/env python3
"""
NC Commons to Wikipedia Import Bot

Main entry point for the bot that imports files from NC Commons to Wikipedia
across multiple languages.

Usage:
    python bot.py                  # Process all languages
    python bot.py --lang ar        # Process only Arabic Wikipedia
    python bot.py --config custom.yaml  # Use custom config file
"""

import sys
import logging
import yaml
import argparse
import configparser
from pathlib import Path

from src.wiki_api import NCCommonsAPI, WikipediaAPI
from src.database import Database
from src.uploader import FileUploader
from src.processor import PageProcessor
from src.parsers import parse_language_list


def setup_logging(config: dict):
    """
    Configure logging based on configuration.

    Sets up both file and console logging with appropriate formatters
    and handlers.

    Args:
        config: Logging configuration dictionary
    """
    # Get logging configuration
    log_level = getattr(logging, config.get('level', 'INFO').upper())
    log_file = Path(config.get('file', './logs/bot.log'))
    max_bytes = config.get('max_bytes', 10485760)  # 10MB default
    backup_count = config.get('backup_count', 5)

    # Create logs directory
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Create formatters
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # File handler with rotation
    from logging.handlers import RotatingFileHandler
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    file_handler.setFormatter(formatter)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    logging.info("Logging configured")


def load_credentials(creds_file: str = 'credentials.ini') -> dict:
    """
    Load credentials from INI file.

    Args:
        creds_file: Path to credentials file

    Returns:
        Dictionary with NC Commons and Wikipedia credentials

    Raises:
        FileNotFoundError: If credentials file doesn't exist
    """
    if not Path(creds_file).exists():
        raise FileNotFoundError(
            f"Credentials file not found: {creds_file}\n"
            f"Please copy credentials.ini.example to credentials.ini and fill in your credentials"
        )

    config = configparser.ConfigParser()
    config.read(creds_file)

    return {
        'nc_username': config['nccommons']['username'],
        'nc_password': config['nccommons']['password'],
        'wiki_username': config['wikipedia']['username'],
        'wiki_password': config['wikipedia']['password']
    }


def process_language(
    language_code: str,
    config: dict,
    credentials: dict,
    nc_api: NCCommonsAPI,
    database: Database
) -> dict:
    """
    Process all pages for a single language.

    Args:
        language_code: Wikipedia language code (e.g., 'en', 'ar')
        config: Configuration dictionary
        credentials: Credentials dictionary
        nc_api: NC Commons API client
        database: Database instance

    Returns:
        Dictionary with processing statistics
    """
    logger = logging.getLogger(__name__)
    logger.info(f"{'='*60}")
    logger.info(f"Processing language: {language_code}")
    logger.info(f"{'='*60}")

    # Create Wikipedia API client for this language
    wiki_api = WikipediaAPI(
        language_code,
        credentials['wiki_username'],
        credentials['wiki_password']
    )

    # Create uploader
    uploader = FileUploader(nc_api, wiki_api, database, config)

    # Create page processor
    processor = PageProcessor(wiki_api, uploader, database, config)

    # Get pages with NC template
    max_pages = config['processing']['max_pages_per_language']
    pages = wiki_api.get_pages_with_template('Template:NC', limit=max_pages)

    logger.info(f"Found {len(pages)} pages to process")

    # Process each page
    stats = {
        'pages_processed': 0,
        'pages_modified': 0,
        'errors': 0
    }

    for i, page_title in enumerate(pages, 1):
        logger.info(f"[{i}/{len(pages)}] Processing: {page_title}")

        try:
            modified = processor.process_page(page_title)
            stats['pages_processed'] += 1

            if modified:
                stats['pages_modified'] += 1

        except Exception as e:
            logger.error(f"Error processing page {page_title}: {e}")
            stats['errors'] += 1

    # Get database statistics for this language
    db_stats = database.get_statistics(language_code)
    stats.update(db_stats)

    logger.info(f"Language {language_code} complete:")
    logger.info(f"  Pages processed: {stats['pages_processed']}")
    logger.info(f"  Pages modified: {stats['pages_modified']}")
    logger.info(f"  Total uploads: {stats['total_uploads']}")
    logger.info(f"  Errors: {stats['errors']}")

    return stats


def main():
    """Main entry point for the bot."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='NC Commons to Wikipedia Import Bot',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python bot.py                     # Process all languages
  python bot.py --lang ar           # Process only Arabic
  python bot.py --lang en --lang fr # Process English and French
        """
    )

    parser.add_argument(
        '--config',
        default='config.yaml',
        help='Path to configuration file (default: config.yaml)'
    )

    parser.add_argument(
        '--lang',
        action='append',
        dest='languages',
        help='Process only specific language(s) (can be used multiple times)'
    )

    parser.add_argument(
        '--creds',
        default='credentials.ini',
        help='Path to credentials file (default: credentials.ini)'
    )

    args = parser.parse_args()

    try:
        # Load configuration
        with open(args.config, 'r') as f:
            config = yaml.safe_load(f)

        # Setup logging
        setup_logging(config['logging'])

        logger = logging.getLogger(__name__)
        logger.info("="*60)
        logger.info("NC Commons Import Bot Starting")
        logger.info("="*60)
        logger.info(f"Configuration loaded from: {args.config}")

        # Load credentials
        credentials = load_credentials(args.creds)
        logger.info("Credentials loaded")

        # Initialize database
        database = Database(config['database']['path'])

        # Connect to NC Commons
        nc_api = NCCommonsAPI(
            credentials['nc_username'],
            credentials['nc_password']
        )

        # Determine which languages to process
        if args.languages:
            # Use languages from command line
            languages = args.languages
            logger.info(f"Processing {len(languages)} specified languages: {languages}")
        else:
            # Get all languages from NC Commons page
            language_page = config['nc_commons']['language_page']
            page_text = nc_api.get_page_text(language_page)
            languages = parse_language_list(page_text)
            logger.info(f"Processing {len(languages)} languages from {language_page}")

        # Process each language
        overall_stats = {
            'languages_processed': 0,
            'total_pages_processed': 0,
            'total_pages_modified': 0,
            'total_uploads': 0,
            'total_errors': 0
        }

        for lang in languages:
            try:
                stats = process_language(lang, config, credentials, nc_api, database)

                overall_stats['languages_processed'] += 1
                overall_stats['total_pages_processed'] += stats['pages_processed']
                overall_stats['total_pages_modified'] += stats['pages_modified']
                overall_stats['total_uploads'] += stats['total_uploads']
                overall_stats['total_errors'] += stats['errors']

            except Exception as e:
                logger.error(f"Failed to process language {lang}: {e}")
                overall_stats['total_errors'] += 1

        # Final summary
        logger.info("="*60)
        logger.info("Bot Completed")
        logger.info("="*60)
        logger.info(f"Languages processed: {overall_stats['languages_processed']}")
        logger.info(f"Pages processed: {overall_stats['total_pages_processed']}")
        logger.info(f"Pages modified: {overall_stats['total_pages_modified']}")
        logger.info(f"Total uploads: {overall_stats['total_uploads']}")
        logger.info(f"Errors: {overall_stats['total_errors']}")

        # Get overall database statistics
        db_stats = database.get_statistics()
        logger.info(f"Database totals: {db_stats}")

        return 0

    except KeyboardInterrupt:
        logger = logging.getLogger(__name__)
        logger.info("Bot interrupted by user")
        return 130

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Fatal error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
```

**Key points:**

-   Comprehensive command-line interface
-   Rotating file logs
-   Graceful error handling
-   Progress tracking
-   Summary statistics
-   Exit codes for automation

---

### Step 9: Create README.md

Create comprehensive documentation:

````markdown
# NC Commons Import Bot

A Python bot that automatically imports files from [NC Commons](https://nccommons.org) to Wikipedia across multiple languages.

## Features

-   🌍 Multi-language support (processes multiple Wikipedias)
-   📁 Automatic file uploads from NC Commons
-   🔄 Template replacement ({{NC}} → [[File:...]])
-   💾 SQLite database for tracking
-   🔁 Automatic retry with exponential backoff
-   📊 Statistics and reporting
-   🪵 Comprehensive logging

## How It Works

1. Reads a list of languages from NC Commons
2. For each language:
    - Finds Wikipedia pages with `{{NC|filename.jpg}}` templates
    - Downloads file info from NC Commons
    - Uploads files to Wikipedia
    - Replaces templates with `[[File:filename.jpg|thumb|caption]]`
    - Adds "Files imported from NC Commons" category
3. Records everything in SQLite database

## Installation

### Requirements

-   Python 3.8 or higher
-   pip

### Setup

1. **Clone or download this repository**

2. **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

3. **Configure credentials:**

    ```bash
    cp credentials.ini.example credentials.ini
    ```

    Edit `credentials.ini` and add your credentials:

    - NC Commons: Your username and password
    - Wikipedia: Your bot username and bot password token

4. **Configure settings (optional):**

    Edit `config.yaml` to customize:

    - Processing limits
    - Retry behavior
    - Logging levels
    - Database path

## Usage

### Process All Languages

```bash
python bot.py
```

### Process Specific Language(s)

```bash
python bot.py --lang ar
python bot.py --lang en --lang fr
```

### Use Custom Config

```bash
python bot.py --config my_config.yaml
```

### Generate Reports

```bash
python -m src.reports ./data/nc_files.db ./reports/summary.json
```

## Project Structure

```
nc_commons_bot/
├── bot.py                  # Main entry point
├── config.yaml             # Configuration
├── credentials.ini         # Credentials (gitignored)
├── requirements.txt        # Python dependencies
└── src/                    # Source code
    ├── wiki_api.py         # MediaWiki API wrapper
    ├── parsers.py          # Wikitext parsing
    ├── uploader.py         # File upload logic
    ├── processor.py        # Page processing
    ├── database.py         # SQLite operations
    └── reports.py          # Reporting
```

## Configuration

### config.yaml

Main configuration file:

-   `nc_commons`: NC Commons site settings
-   `wikipedia`: Wikipedia upload settings
-   `database`: Database path
-   `processing`: Limits and retry configuration
-   `logging`: Log file and level

### credentials.ini

Credentials file (never commit to git):

-   `nccommons`: NC Commons login
-   `wikipedia`: Wikipedia bot password

## Database

The bot uses SQLite to track:

-   **uploads**: Every file upload attempt (success/failed/duplicate)
-   **pages**: Every page processed

Database location: `./data/nc_files.db` (configurable)

## Logging

Logs are written to both console and file:

-   Default location: `./logs/bot.log`
-   Rotating logs (10MB max, 5 backups)
-   Configurable log level

## Troubleshooting

### "Credentials file not found"

Make sure you copied `credentials.ini.example` to `credentials.ini` and filled in your credentials.

### "Login failed"

-   For Wikipedia: Use bot password format (`BotName@BotPassword`, not your main password)
-   Check that credentials are correct
-   Ensure bot has appropriate permissions

### "Upload failed: copyupload"

This means URL upload is disabled. The bot will automatically retry with file download method.

## Development

### Code Style

-   All code uses English for comments, docstrings, and variable names
-   Type hints for all functions
-   Comprehensive docstrings
-   PEP 8 compliant

### Testing

Run manual tests:

```bash
# Test configuration
python -c "import yaml; print(yaml.safe_load(open('config.yaml')))"

# Test API connection
python -c "from src.wiki_api import NCCommonsAPI; api = NCCommonsAPI('user', 'pass'); print('OK')"

# Test database
python -c "from src.database import Database; db = Database('./test.db'); print('OK')"
```

## License

[Your license here]

## Credits

Created for the NC Commons to Wikipedia import workflow.

Uses:

-   [mwclient](https://github.com/mwclient/mwclient) - MediaWiki API client
-   [wikitextparser](https://github.com/5j9/wikitextparser) - Wikitext parsing
-   [PyYAML](https://pyyaml.org/) - YAML configuration

## Support

For issues or questions:

-   Open an issue on GitHub
-   Contact: [Your contact]
````

---

### Step 10: Final Checklist

Before finishing, verify:

**Files Created:**

-   [ ] `requirements.txt`
-   [ ] `config.yaml`
-   [ ] `credentials.ini.example`
-   [ ] `.gitignore`
-   [ ] `README.md`
-   [ ] `bot.py`
-   [ ] `src/__init__.py`
-   [ ] `src/wiki_api.py`
-   [ ] `src/parsers.py`
-   [ ] `src/database.py`
-   [ ] `src/uploader.py`
-   [ ] `src/processor.py`
-   [ ] `src/reports.py`

**Code Quality:**

-   [ ] All comments in English
-   [ ] All docstrings in English
-   [ ] All variable names in English
-   [ ] Type hints on all functions
-   [ ] Comprehensive error handling
-   [ ] Proper logging throughout
-   [ ] No hardcoded values (use config)

**Functionality:**

-   [ ] Can connect to NC Commons
-   [ ] Can connect to Wikipedia
-   [ ] Can parse language list
-   [ ] Can extract NC templates
-   [ ] Can upload files
-   [ ] Can process pages
-   [ ] Can save to database
-   [ ] Can generate reports

**Testing:**

-   [ ] Configuration loads correctly
-   [ ] Credentials load correctly
-   [ ] Database initializes
-   [ ] API connections work
-   [ ] Parsing functions work
-   [ ] Bot runs without errors

---

## Key Reminders

### Language Requirements

-   **ALL** code comments in English
-   **ALL** docstrings in English
-   **ALL** variable names in English
-   **ALL** log messages in English
-   **ALL** documentation in English

### Simplicity

-   Don't over-engineer
-   Keep files small (50-200 lines each)
-   Use standard libraries
-   Clear, readable code
-   Simple is better than complex

### Best Practices

-   Type hints everywhere
-   Comprehensive error handling
-   Proper logging levels
-   Context managers for resources
-   Clean code structure

---

## Success Criteria

The refactored bot is successful when:

-   ✅ All 8 files created and working
-   ✅ Total code ~900 lines
-   ✅ Uses mwclient (no custom API)
-   ✅ Uses wikitextparser
-   ✅ Uses Python logging
-   ✅ Configuration in YAML
-   ✅ All English documentation/code
-   ✅ Can run `python bot.py` successfully
-   ✅ Simple, clean, maintainable

---

## Final Note

You are creating a **new, clean codebase** from scratch. Don't try to preserve old code patterns - write it fresh using modern best practices. Focus on:

1. **Clarity** - Easy to understand
2. **Simplicity** - Not over-engineered
3. **Reliability** - Proper error handling
4. **Maintainability** - Well-documented

Good luck! Create clean, professional code that does the job well.
