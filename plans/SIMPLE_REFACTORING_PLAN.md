# NC Commons Bot - Simplified Refactoring Plan

## Philosophy: Keep It Simple, Stupid (KISS)

Your current code works fine. We only need to fix:

-   Replace custom `newapi` with standard `mwclient`
-   Replace 24KB `printe.py` with Python's `logging`
-   Remove hardcoded paths
-   Better database schema with simple reporting

**Goal:** Modern, maintainable code WITHOUT over-engineering!

---

## New Simple Structure

```
nc_commons_bot/
├── config.yaml              # Single config file
├── requirements.txt
├── README.md
├── bot.py                   # Main entry point (was: bot.py)
└── src/                     # All logic in src/
    ├── __init__.py
    ├── wiki_api.py          # mwclient wrapper (replaces: wiki_page.py, page_ncc.py)
    ├── parsers.py           # wikitextparser helpers (replaces: get_langs.py + part of wrk_pages.py)
    ├── uploader.py          # File upload logic (replaces: upload_file.py, import_files.py)
    ├── processor.py         # Page processing (replaces: wrk_pages.py)
    ├── database.py          # SQLite operations (replaces: db.py, db_bot.py)
    └── reports.py           # Simple reporting (new)
```

**Total: 8 files instead of 12!**

---

## File-by-File Implementation

### 1. `config.yaml` - Simple Configuration

```yaml
# NC Commons settings
nc_commons:
    site: "nccommons.org"
    language_page: "User:Mr. Ibrahem/import bot"

# Wikipedia settings
wikipedia:
    upload_comment: "Bot: import from nccommons.org"
    category: "Category:Contains images from NC Commons"

# Database
database:
    path: "./data/nc_files.db"

# Processing limits
processing:
    max_pages: 10000
    max_retries: 3
    retry_delay: 5

# Logging
logging:
    level: "INFO"
    file: "./logs/bot.log"
```

Load with:

```python
import yaml
with open('config.yaml') as f:
    config = yaml.safe_load(f)
```

---

### 2. `src/wiki_api.py` - mwclient Wrapper (200 lines)

**Replaces:** `wiki_page.py`, `page_ncc.py`, and custom `newapi`

```python
"""
Simple mwclient wrapper for NC Commons and Wikipedia.
Handles all MediaWiki API interactions.
"""
import mwclient
import logging
import time
from typing import List, Dict, Optional
from functools import wraps

logger = logging.getLogger(__name__)

def retry(max_attempts=3, delay=5):
    """Simple retry decorator with exponential backoff"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    wait = delay * (2 ** attempt)
                    logger.warning(f"Attempt {attempt + 1} failed: {e}. Retry in {wait}s")
                    time.sleep(wait)
        return wrapper
    return decorator


class WikiAPI:
    """Base class for MediaWiki API interactions using mwclient"""

    def __init__(self, site: str, username: str = None, password: str = None):
        logger.info(f"Connecting to {site}")
        self.site = mwclient.Site(site)

        if username and password:
            logger.info(f"Logging in as {username}")
            self.site.login(username, password)

    @retry(max_attempts=3)
    def get_page_text(self, title: str) -> str:
        """Get page content"""
        page = self.site.pages[title]
        return page.text()

    @retry(max_attempts=3)
    def save_page(self, title: str, text: str, summary: str):
        """Save page content"""
        page = self.site.pages[title]
        page.save(text, summary=summary)
        logger.info(f"Saved: {title}")


class NCCommonsAPI(WikiAPI):
    """NC Commons specific operations"""

    def __init__(self, username: str, password: str):
        super().__init__('nccommons.org', username, password)

    def get_image_url(self, filename: str) -> str:
        """Get direct URL to image file"""
        if not filename.startswith('File:'):
            filename = f'File:{filename}'

        page = self.site.pages[filename]
        return page.imageinfo['url']

    def get_file_description(self, filename: str) -> str:
        """Get file page content"""
        if not filename.startswith('File:'):
            filename = f'File:{filename}'
        return self.get_page_text(filename)


class WikipediaAPI(WikiAPI):
    """Wikipedia specific operations"""

    def __init__(self, lang: str, username: str, password: str):
        self.lang = lang
        site = f'{lang}.wikipedia.org'
        super().__init__(site, username, password)

    def get_pages_with_template(self, template: str, limit: int = 10000) -> List[str]:
        """Get all pages transcluding a template"""
        logger.info(f"Finding pages with {template}")

        template_page = self.site.pages[template]
        pages = [p.name for p in template_page.embeddedin(limit=limit)]

        logger.info(f"Found {len(pages)} pages")
        return pages

    @retry(max_attempts=3)
    def upload_from_url(self, filename: str, url: str, description: str, comment: str) -> bool:
        """Upload file from URL"""
        try:
            result = self.site.upload(
                file=None,
                filename=filename,
                description=description,
                comment=comment,
                url=url
            )
            logger.info(f"Uploaded: {filename}")
            return True
        except mwclient.errors.APIError as e:
            if 'duplicate' in str(e).lower():
                logger.warning(f"Duplicate: {filename}")
                return False
            raise

    @retry(max_attempts=3)
    def upload_from_file(self, filename: str, filepath: str, description: str, comment: str) -> bool:
        """Upload file from local path"""
        try:
            with open(filepath, 'rb') as f:
                result = self.site.upload(
                    file=f,
                    filename=filename,
                    description=description,
                    comment=comment
                )
            logger.info(f"Uploaded: {filename}")
            return True
        except mwclient.errors.APIError as e:
            if 'duplicate' in str(e).lower():
                logger.warning(f"Duplicate: {filename}")
                return False
            raise
```

---

### 3. `src/parsers.py` - Simple wikitextparser Helpers (100 lines)

**Replaces:** `get_langs.py` and template parsing from `wrk_pages.py`

```python
"""
Wikitext parsing helpers using wikitextparser.
"""
import wikitextparser as wtp
import logging
from typing import List, Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)

def parse_language_list(text: str) -> List[str]:
    """
    Extract language codes from NC Commons page.
    Format: {{User:Mr. Ibrahem/import bot/line|LANG}}
    """
    parsed = wtp.parse(text)
    languages = []

    for template in parsed.templates:
        name = str(template.normal_name()).strip().lower().replace('_', ' ')
        if 'import bot/line' in name:
            arg = template.get_arg('1')
            if arg and arg.value:
                languages.append(arg.value.strip())

    logger.info(f"Found {len(languages)} languages: {languages}")
    return languages


@dataclass
class NCTemplate:
    """Represents a {{NC}} template"""
    original: str
    filename: str
    caption: str = ""

    def to_file_syntax(self) -> str:
        """Convert to [[File:...]] syntax"""
        return f"[[File:{self.filename}|thumb|{self.caption}]]"


def extract_nc_templates(text: str) -> List[NCTemplate]:
    """
    Extract all {{NC}} templates from page.
    Format: {{NC|filename.jpg|caption}}
    """
    parsed = wtp.parse(text)
    templates = []

    for template in parsed.templates:
        name = str(template.normal_name()).strip().lower()
        if name == 'nc':
            filename = template.get_arg('1').value.strip() if template.get_arg('1') else ""
            caption = template.get_arg('2').value.strip() if template.get_arg('2') else ""

            if filename:
                templates.append(NCTemplate(
                    original=template.string,
                    filename=filename,
                    caption=caption
                ))

    logger.info(f"Found {len(templates)} NC templates")
    return templates


def remove_categories(text: str) -> str:
    """Remove all category tags from text"""
    import re
    return re.sub(r'\[\[Category:.*?\]\]', '', text, flags=re.IGNORECASE)
```

---

### 4. `src/database.py` - Simple SQLite Operations (150 lines)

**Replaces:** `db.py`, `db_bot.py`

```python
"""
Simple SQLite database for tracking uploads.
"""
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class Database:
    """Simple SQLite database wrapper"""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
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
        """Create tables if they don't exist"""
        with self._connection() as conn:
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
            """)

    def record_upload(self, filename: str, language: str, status: str, error: str = None):
        """Record a file upload attempt"""
        with self._connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO uploads (filename, language, status, error, uploaded_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (filename, language, status, error))

        logger.debug(f"Recorded upload: {filename} ({status})")

    def record_page(self, page_title: str, language: str, templates_found: int, files_uploaded: int):
        """Record page processing"""
        with self._connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO pages
                (page_title, language, templates_found, files_uploaded, processed_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (page_title, language, templates_found, files_uploaded))

        logger.debug(f"Recorded page: {page_title}")

    def is_uploaded(self, filename: str, language: str) -> bool:
        """Check if file was already uploaded successfully"""
        with self._connection() as conn:
            result = conn.execute("""
                SELECT COUNT(*) as count FROM uploads
                WHERE filename = ? AND language = ? AND status = 'success'
            """, (filename, language)).fetchone()
            return result['count'] > 0

    def get_stats(self, language: str = None) -> Dict:
        """Get statistics"""
        with self._connection() as conn:
            if language:
                uploads = conn.execute(
                    "SELECT COUNT(*) as count FROM uploads WHERE language = ? AND status = 'success'",
                    (language,)
                ).fetchone()['count']

                pages = conn.execute(
                    "SELECT COUNT(*) as count FROM pages WHERE language = ?",
                    (language,)
                ).fetchone()['count']
            else:
                uploads = conn.execute(
                    "SELECT COUNT(*) as count FROM uploads WHERE status = 'success'"
                ).fetchone()['count']

                pages = conn.execute(
                    "SELECT COUNT(*) as count FROM pages"
                ).fetchone()['count']

            return {
                'total_uploads': uploads,
                'total_pages': pages
            }
```

---

### 5. `src/uploader.py` - File Upload Logic (100 lines)

**Replaces:** `upload_file.py`, `import_files.py`

```python
"""
File upload operations.
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
    """Handles file uploads from NC Commons to Wikipedia"""

    def __init__(self, nc_api: NCCommonsAPI, wiki_api: WikipediaAPI, db: Database, config: dict):
        self.nc_api = nc_api
        self.wiki_api = wiki_api
        self.db = db
        self.config = config

    def upload_file(self, filename: str) -> bool:
        """
        Upload a file from NC Commons to Wikipedia.
        Returns True if successful, False if duplicate or already uploaded.
        """
        lang = self.wiki_api.lang

        # Check if already uploaded
        if self.db.is_uploaded(filename, lang):
            logger.info(f"Already uploaded: {filename}")
            return False

        try:
            # Get file info from NC Commons
            file_url = self.nc_api.get_image_url(filename)
            description = self.nc_api.get_file_description(filename)

            # Process description
            description = remove_categories(description)
            description += "\n[[Category:Files imported from NC Commons]]"

            comment = self.config['wikipedia']['upload_comment']

            # Try URL upload first
            try:
                success = self.wiki_api.upload_from_url(filename, file_url, description, comment)

                if success:
                    self.db.record_upload(filename, lang, 'success')
                    return True
                else:
                    self.db.record_upload(filename, lang, 'duplicate')
                    return False

            except Exception as e:
                # If URL upload fails, try downloading first
                if 'url' in str(e).lower() or 'copyupload' in str(e).lower():
                    logger.info(f"URL upload failed, trying file upload")
                    return self._upload_via_download(filename, file_url, description, comment, lang)
                raise

        except Exception as e:
            logger.error(f"Upload failed for {filename}: {e}")
            self.db.record_upload(filename, lang, 'failed', str(e))
            return False

    def _upload_via_download(self, filename: str, url: str, description: str, comment: str, lang: str) -> bool:
        """Download file then upload"""
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.tmp')
        temp_path = temp_file.name

        try:
            # Download
            urllib.request.urlretrieve(url, temp_path)

            # Upload
            success = self.wiki_api.upload_from_file(filename, temp_path, description, comment)

            if success:
                self.db.record_upload(filename, lang, 'success')
                return True
            else:
                self.db.record_upload(filename, lang, 'duplicate')
                return False

        finally:
            Path(temp_path).unlink(missing_ok=True)
```

---

### 6. `src/processor.py` - Page Processing (100 lines)

**Replaces:** `wrk_pages.py`

```python
"""
Wikipedia page processing.
"""
import logging
from src.wiki_api import WikipediaAPI
from src.database import Database
from src.uploader import FileUploader
from src.parsers import extract_nc_templates

logger = logging.getLogger(__name__)

class PageProcessor:
    """Process Wikipedia pages with {{NC}} templates"""

    def __init__(self, wiki_api: WikipediaAPI, uploader: FileUploader, db: Database, config: dict):
        self.wiki_api = wiki_api
        self.uploader = uploader
        self.db = db
        self.config = config

    def process_page(self, page_title: str) -> bool:
        """
        Process a single page.
        Returns True if page was modified.
        """
        logger.info(f"Processing: {page_title}")

        try:
            # Get page content
            text = self.wiki_api.get_page_text(page_title)

            # Extract templates
            templates = extract_nc_templates(text)

            if not templates:
                logger.info("No NC templates found")
                return False

            # Process each template
            replacements = {}
            uploaded_count = 0

            for template in templates:
                logger.info(f"File: {template.filename}")

                # Upload file
                if self.uploader.upload_file(template.filename):
                    uploaded_count += 1
                    replacements[template.original] = template.to_file_syntax()

            # Record in database
            self.db.record_page(page_title, self.wiki_api.lang, len(templates), uploaded_count)

            # Update page if any files were uploaded
            if replacements:
                new_text = text
                for old, new in replacements.items():
                    new_text = new_text.replace(old, new)

                # Add category if not present
                category = f"[[{self.config['wikipedia']['category']}]]"
                if category not in new_text:
                    new_text += f"\n{category}"

                # Save
                summary = f"Bot: Imported {uploaded_count} file(s) from NC Commons"
                self.wiki_api.save_page(page_title, new_text, summary)

                logger.info(f"Updated page: {uploaded_count} files")
                return True

            return False

        except Exception as e:
            logger.error(f"Error processing {page_title}: {e}")
            return False
```

---

### 7. `bot.py` - Main Entry Point (150 lines)

**Replaces:** Original `bot.py`

```python
#!/usr/bin/env python3
"""
NC Commons to Wikipedia Import Bot

Simple bot that:
1. Gets language list from NC Commons
2. Finds pages with {{NC}} template
3. Uploads files
4. Replaces templates
5. Records in database
"""
import sys
import logging
import yaml
import argparse
from pathlib import Path

from src.wiki_api import NCCommonsAPI, WikipediaAPI
from src.database import Database
from src.uploader import FileUploader
from src.processor import PageProcessor
from src.parsers import parse_language_list

# Setup logging
def setup_logging(config: dict):
    """Configure logging"""
    level = getattr(logging, config.get('level', 'INFO'))

    # Create logs directory
    log_file = Path(config.get('file', './logs/bot.log'))
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Configure
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

logger = logging.getLogger(__name__)

def load_credentials() -> dict:
    """Load credentials from file or environment"""
    import configparser
    config = configparser.ConfigParser()
    config.read('credentials.ini')

    return {
        'nc_username': config['nccommons']['username'],
        'nc_password': config['nccommons']['password'],
        'wiki_username': config['wikipedia']['username'],
        'wiki_password': config['wikipedia']['password']
    }

def process_language(lang: str, config: dict, creds: dict, nc_api: NCCommonsAPI, db: Database):
    """Process all pages for one language"""
    logger.info(f"=== Processing language: {lang} ===")

    # Create Wikipedia API
    wiki_api = WikipediaAPI(lang, creds['wiki_username'], creds['wiki_password'])

    # Create uploader
    uploader = FileUploader(nc_api, wiki_api, db, config)

    # Create processor
    processor = PageProcessor(wiki_api, uploader, db, config)

    # Get pages with NC template
    pages = wiki_api.get_pages_with_template('Template:NC', limit=config['processing']['max_pages'])

    # Process each page
    modified = 0
    for page_title in pages:
        if processor.process_page(page_title):
            modified += 1

    logger.info(f"Language {lang} complete: {modified}/{len(pages)} pages modified")
    return modified

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='NC Commons Import Bot')
    parser.add_argument('--lang', help='Process only this language')
    parser.add_argument('--config', default='config.yaml', help='Config file path')
    args = parser.parse_args()

    # Load config
    with open(args.config) as f:
        config = yaml.safe_load(f)

    # Setup logging
    setup_logging(config['logging'])

    logger.info("NC Commons Import Bot starting")

    # Load credentials
    creds = load_credentials()

    # Initialize database
    db = Database(config['database']['path'])

    # Connect to NC Commons
    nc_api = NCCommonsAPI(creds['nc_username'], creds['nc_password'])

    # Get languages
    if args.lang:
        languages = [args.lang]
    else:
        page_text = nc_api.get_page_text(config['nc_commons']['language_page'])
        languages = parse_language_list(page_text)

    # Process each language
    total_modified = 0
    for lang in languages:
        try:
            modified = process_language(lang, config, creds, nc_api, db)
            total_modified += modified
        except Exception as e:
            logger.error(f"Failed to process {lang}: {e}")

    logger.info(f"Bot finished. Total pages modified: {total_modified}")

    # Show stats
    stats = db.get_stats()
    logger.info(f"Database stats: {stats}")

if __name__ == '__main__':
    main()
```

---

### 8. `src/reports.py` - Simple Reporting (50 lines)

**New feature - simple reports**

```python
"""
Simple reporting from database.
"""
import json
import logging
from src.database import Database

logger = logging.getLogger(__name__)

class Reporter:
    """Generate simple reports"""

    def __init__(self, db: Database):
        self.db = db

    def generate_summary(self) -> dict:
        """Generate summary report"""
        with self.db._connection() as conn:
            # Total stats
            total = self.db.get_stats()

            # Per language
            by_lang = conn.execute("""
                SELECT language, COUNT(*) as count
                FROM uploads
                WHERE status = 'success'
                GROUP BY language
                ORDER BY count DESC
            """).fetchall()

            # Recent errors
            errors = conn.execute("""
                SELECT filename, language, error
                FROM uploads
                WHERE status = 'failed'
                ORDER BY uploaded_at DESC
                LIMIT 10
            """).fetchall()

            return {
                'total': dict(total),
                'by_language': [dict(row) for row in by_lang],
                'recent_errors': [dict(row) for row in errors]
            }

    def save_report(self, output_file: str = 'report.json'):
        """Save report to JSON file"""
        report = self.generate_summary()

        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)

        logger.info(f"Report saved to {output_file}")

if __name__ == '__main__':
    db = Database('./data/nc_files.db')
    reporter = Reporter(db)
    reporter.save_report()
```

---

## Additional Files

### `requirements.txt`

```txt
mwclient>=0.10.1
wikitextparser>=0.55.0
PyYAML>=6.0
```

### `credentials.ini.example`

```ini
[nccommons]
username = YourNCCommonsUsername
password = YourNCCommonsPassword

[wikipedia]
username = YourWikipediaBot@BotPassword
password = YourBotPasswordToken
```

### `README.md`

````markdown
# NC Commons Import Bot

Simple bot to import files from NC Commons to Wikipedia.

## Setup

1. Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
````

2. Copy credentials file:

    ```bash
    cp credentials.ini.example credentials.ini
    ```

3. Edit `credentials.ini` with your credentials

## Usage

Process all languages:

```bash
python bot.py
```

Process specific language:

```bash
python bot.py --lang ar
```

Generate reports:

```bash
python reports.py
```

## How It Works

1. Reads language list from NC Commons
2. For each language:
    - Finds pages with {{NC|filename.jpg}} templates
    - Downloads file info from NC Commons
    - Uploads to Wikipedia
    - Replaces template with [[File:filename.jpg]]
    - Adds category
3. Records everything in SQLite database

```

---

## Summary: What Changed?

### Old Structure (12 files):
- bot.py
- views.py
- import_bots/db.py
- import_bots/db_bot.py
- import_bots/get_langs.py
- import_bots/import_files.py
- import_bots/page_ncc.py
- import_bots/printe.py (24KB!)
- import_bots/upload_file.py
- import_bots/wiki_page.py
- import_bots/wrk_pages.py

### New Structure (8 files):
- bot.py (main)
- src/wiki_api.py (replaces 3 files)
- src/parsers.py (replaces 1.5 files)
- src/uploader.py (replaces 2 files)
- src/processor.py (replaces 1 file)
- src/database.py (replaces 2 files)
- src/reports.py (new, simple)
- config.yaml (replaces hardcoded values)

### Lines of Code:
- **Old:** ~1,500 lines + 24KB printe.py
- **New:** ~900 lines of clean, typed Python

### Key Improvements:
✅ Uses standard `mwclient` instead of custom API
✅ Uses Python `logging` instead of 24KB custom module
✅ Configuration in YAML file
✅ Simple retry logic with decorator
✅ Better database schema
✅ Type hints throughout
✅ Proper error handling
✅ Simple reporting

### Migration:
1. Keep old database or migrate data
2. Create config.yaml from old settings
3. Create credentials.ini
4. Run new bot.py

**This is practical, maintainable, and not over-engineered!**
```
