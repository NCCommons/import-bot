# AGENT INSTRUCTIONS: NC Commons Bot Simple Refactoring

## Mission

Refactor the NC Commons Import Bot to use modern libraries (mwclient, wikitextparser, logging) while keeping the code SIMPLE. The bot has 5 simple steps - don't over-engineer it!

## Core Principle: KISS (Keep It Simple, Stupid)

The current bot works fine. We're only fixing:

1. Replace custom `newapi` → standard `mwclient`
2. Replace 24KB `printe.py` → Python's `logging`
3. Remove hardcoded paths → `config.yaml`
4. Improve database schema slightly

**DO NOT create 50 files! Keep it to 8 clean files.**

---

## Step 1: Analyze Current Code

Before starting, understand what the bot does:

1. **Read language list** from NC Commons page
2. **Find pages** with {{NC}} template on each Wikipedia
3. **Upload files** from NC Commons to Wikipedia
4. **Replace templates** with [[File:...]] syntax
5. **Record in database** for tracking

Ask yourself: Does this need complex architecture? NO!

---

## Step 2: Create New Structure

Create this simple structure:

```
nc_commons_bot/
├── config.yaml              # All configuration
├── credentials.ini.example  # Credentials template
├── requirements.txt         # Dependencies
├── README.md               # Documentation
├── bot.py                  # Main entry (150 lines)
└── src/                    # All logic in src/
    ├── __init__.py
    ├── wiki_api.py         # mwclient wrapper (200 lines)
    ├── parsers.py          # wikitextparser helpers (100 lines)
    ├── uploader.py         # Upload logic (100 lines)
    ├── processor.py        # Page processing (100 lines)
    ├── database.py         # SQLite operations (150 lines)
    └── reports.py          # Simple reporting (50 lines)
```

**Total: 8 files, ~900 lines**

---

## Step 3: Implementation Order

### 3.1 Setup Files First

Create these immediately:

**requirements.txt:**

```txt
mwclient>=0.10.1
wikitextparser>=0.55.0
PyYAML>=6.0
```

**config.yaml:**

```yaml
nc_commons:
    site: "nccommons.org"
    language_page: "User:Mr. Ibrahem/import bot"

wikipedia:
    upload_comment: "Bot: import from nccommons.org"
    category: "Category:Contains images from NC Commons"

database:
    path: "./data/nc_files.db"

processing:
    max_pages: 10000
    max_retries: 3
    retry_delay: 5

logging:
    level: "INFO"
    file: "./logs/bot.log"
```

**credentials.ini.example:**

```ini
[nccommons]
username = YourUsername
password = YourPassword

[wikipedia]
username = YourBot@BotPassword
password = YourToken
```

### 3.2 Core Module: src/wiki_api.py

This is the MOST IMPORTANT file. It replaces `wiki_page.py`, `page_ncc.py`, and custom `newapi`.

**Requirements:**

-   Use `mwclient.Site()` for connections
-   Create base `WikiAPI` class with retry decorator
-   Create `NCCommonsAPI(WikiAPI)` for NC Commons operations
-   Create `WikipediaAPI(WikiAPI)` for Wikipedia operations

**Key methods:**

```python
class WikiAPI:
    def __init__(site, username, password)
    def get_page_text(title) -> str
    def save_page(title, text, summary)

class NCCommonsAPI(WikiAPI):
    def get_image_url(filename) -> str
    def get_file_description(filename) -> str

class WikipediaAPI(WikiAPI):
    def get_pages_with_template(template, limit) -> List[str]
    def upload_from_url(filename, url, description, comment) -> bool
    def upload_from_file(filename, filepath, description, comment) -> bool
```

**Add simple retry decorator:**

```python
def retry(max_attempts=3, delay=5):
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
                    logger.warning(f"Retry in {wait}s: {e}")
                    time.sleep(wait)
        return wrapper
    return decorator
```

### 3.3 Simple Parsers: src/parsers.py

Replace `get_langs.py` and template parsing from `wrk_pages.py`.

**Functions needed:**

1. `parse_language_list(text) -> List[str]` - Extract language codes
2. `extract_nc_templates(text) -> List[NCTemplate]` - Find {{NC}} templates
3. `remove_categories(text) -> str` - Clean up file descriptions

**Define simple dataclass:**

```python
@dataclass
class NCTemplate:
    original: str
    filename: str
    caption: str = ""

    def to_file_syntax(self) -> str:
        return f"[[File:{self.filename}|thumb|{self.caption}]]"
```

### 3.4 Database: src/database.py

Replace `db.py` and `db_bot.py` with simpler version.

**Schema:**

```sql
-- Main uploads table
CREATE TABLE uploads (
    id INTEGER PRIMARY KEY,
    filename TEXT,
    language TEXT,
    uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    status TEXT,  -- 'success', 'failed', 'duplicate'
    error TEXT,
    UNIQUE(filename, language)
);

-- Pages processed
CREATE TABLE pages (
    id INTEGER PRIMARY KEY,
    page_title TEXT,
    language TEXT,
    processed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    templates_found INTEGER,
    files_uploaded INTEGER,
    UNIQUE(page_title, language)
);
```

**Methods:**

```python
class Database:
    def __init__(db_path)
    def record_upload(filename, language, status, error=None)
    def record_page(page_title, language, templates_found, files_uploaded)
    def is_uploaded(filename, language) -> bool
    def get_stats(language=None) -> Dict
```

**Use context manager for connections:**

```python
@contextmanager
def _connection(self):
    conn = sqlite3.connect(self.db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

### 3.5 File Uploader: src/uploader.py

Replace `upload_file.py` and `import_files.py`.

**Simple class:**

```python
class FileUploader:
    def __init__(nc_api, wiki_api, db, config)

    def upload_file(filename) -> bool:
        # 1. Check if already uploaded
        # 2. Get file URL from NC Commons
        # 3. Get description, process it
        # 4. Try upload_from_url first
        # 5. If fails, download and upload_from_file
        # 6. Record result in database
        # 7. Return success/failure
```

**Handle two upload methods:**

1. Direct URL upload (faster)
2. Download then upload (fallback)

### 3.6 Page Processor: src/processor.py

Replace `wrk_pages.py`.

**Simple class:**

```python
class PageProcessor:
    def __init__(wiki_api, uploader, db, config)

    def process_page(page_title) -> bool:
        # 1. Get page text
        # 2. Extract NC templates
        # 3. Upload each file
        # 4. Track replacements
        # 5. If any uploaded: replace templates, add category, save
        # 6. Record in database
        # 7. Return whether page was modified
```

### 3.7 Main Entry: bot.py

Replace original `bot.py` with cleaner version.

**Flow:**

```python
def main():
    # 1. Parse arguments (--lang, --config)
    # 2. Load config.yaml
    # 3. Setup logging
    # 4. Load credentials
    # 5. Initialize database
    # 6. Connect to NC Commons
    # 7. Get language list (or use --lang argument)
    # 8. For each language:
    #    - Create Wikipedia API
    #    - Create uploader, processor
    #    - Get pages with template
    #    - Process each page
    # 9. Show statistics
```

**Note:** bot.py imports from src:

```python
from src.wiki_api import NCCommonsAPI, WikipediaAPI
from src.database import Database
from src.uploader import FileUploader
from src.processor import PageProcessor
from src.parsers import parse_language_list
```

**Logging setup:**

```python
def setup_logging(config):
    level = getattr(logging, config.get('level', 'INFO'))
    log_file = Path(config.get('file', './logs/bot.log'))
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
```

### 3.8 Simple Reports: src/reports.py

New simple reporting feature.

```python
class Reporter:
    def __init__(db)

    def generate_summary() -> dict:
        # Query database for:
        # - Total uploads
        # - Per-language stats
        # - Recent errors

    def save_report(output_file='report.json'):
        # Save to JSON file
```

---

## Step 4: Code Quality Rules

Follow these SIMPLE rules:

### 1. Type Hints

```python
def process_page(self, page_title: str) -> bool:
    ...
```

### 2. Docstrings (brief!)

```python
def upload_file(self, filename: str) -> bool:
    """Upload file from NC Commons to Wikipedia."""
    ...
```

### 3. Use logging, not print

```python
logger.info(f"Processing: {page_title}")
logger.error(f"Failed: {e}")
```

### 4. Simple error handling

```python
try:
    result = self.wiki_api.get_page_text(title)
    return result
except Exception as e:
    logger.error(f"Error: {e}")
    raise
```

### 5. Context managers for resources

```python
with self._connection() as conn:
    conn.execute(...)
```

---

## Step 5: Testing

Create simple manual tests:

1. **Test configuration:**

    ```python
    python -c "import yaml; print(yaml.safe_load(open('config.yaml')))"
    ```

2. **Test API connection:**

    ```python
    from src.wiki_api import NCCommonsAPI
    api = NCCommonsAPI('user', 'pass')
    print(api.get_page_text('User:Mr. Ibrahem/import bot'))
    ```

3. **Test parsing:**

    ```python
    from src.parsers import parse_language_list
    text = "* {{User:Mr. Ibrahem/import bot/line|ar}}"
    print(parse_language_list(text))
    ```

4. **Test database:**
    ```python
    from src.database import Database
    db = Database('./test.db')
    db.record_upload('test.jpg', 'en', 'success')
    print(db.get_stats())
    ```

---

## Step 6: README.md

Create clear, simple documentation:

````markdown
# NC Commons Import Bot

Imports files from NC Commons to Wikipedia.

## Setup

1. `pip install -r requirements.txt`
2. Copy `credentials.ini.example` to `credentials.ini`
3. Edit credentials

## Usage

```bash
python bot.py              # All languages
python bot.py --lang ar    # Specific language
python reports.py          # Generate reports
```
````

## How It Works

1. Reads language list from NC Commons
2. Finds pages with {{NC}} templates
3. Uploads files
4. Replaces templates
5. Records in database

```

---

## What NOT to Do

❌ Don't create 50 files
❌ Don't over-engineer with complex patterns
❌ Don't add unnecessary abstraction layers
❌ Don't write 1000-line classes
❌ Don't create complex configuration systems
❌ Don't add features that weren't requested

## What to Do

✅ Keep files small (50-200 lines each)
✅ Use standard libraries (mwclient, logging)
✅ Write clear, simple code
✅ Add type hints
✅ Handle errors properly
✅ Log important events
✅ Keep it maintainable

---

## Final Checklist

Before finishing, verify:

- [ ] All 8 files created
- [ ] Total code < 1000 lines
- [ ] Uses mwclient (not custom API)
- [ ] Uses logging (not printe.py)
- [ ] Configuration in YAML
- [ ] Database schema improved
- [ ] Type hints added
- [ ] README.md written
- [ ] Can run `python bot.py` successfully
- [ ] Simple and maintainable

---

## Summary

**Old code:** 12 files, ~1500 lines + 24KB custom logging
**New code:** 8 files, ~900 lines, standard libraries

**Keep it simple!** The bot does 5 things - don't make it complicated.
```
