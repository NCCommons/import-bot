# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NC Commons Import Bot - A Python bot that automatically imports files from NC Commons (nccommons.org) to Wikipedia across multiple languages. It finds Wikipedia pages containing `{{NC|filename.jpg}}` templates, uploads the referenced files from NC Commons to Wikipedia, replaces templates with `[[File:filename.jpg|thumb|caption]]` syntax, and tracks all activity in SQLite.

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt
pip install -r dev-requirements.txt

# Run the bot
python bot.py                  # Process all languages
python bot.py --lang ar        # Process specific language(s)
python bot.py --lang en --lang fr  # Multiple languages
python bot.py --config my_config.yaml  # Custom config

# Run tests
pytest                                    # All tests
pytest --cov=src --cov-report=term -v     # With coverage (CI command)

# Generate reports
python -m src.reports ./data/nc_files.db ./reports/summary.json

# Linting/formatting
black .
ruff check .
isort .
mypy src/
```

## Architecture

The codebase follows a modular class-based design with dependency injection:

```
bot.py (entry point)
    └── src/
        ├── wiki_api.py      # MediaWiki API layer
        │   ├── WikiAPI (base class with retry decorator)
        │   ├── NCCommonsAPI (file info retrieval)
        │   └── WikipediaAPI (page editing, file upload)
        ├── parsers.py       # Wikitext parsing (NCTemplate dataclass)
        ├── uploader.py      # FileUploader (URL upload → file download fallback)
        ├── processor.py     # PageProcessor (orchestrates upload + page edit)
        ├── database.py      # SQLite with context managers (uploads, pages tables)
        ├── reports.py       # JSON report generation
        └── logging_config.py # Colored console + rotating file logs
```

### Key Patterns

- **Two-stage upload**: Try URL upload first, fall back to download-then-upload if disabled
- **Dependency injection**: Components receive dependencies via constructor
- **Context managers**: Safe database connection handling with auto-commit/rollback

## Configuration

- `config.yaml`: Main config (site URLs, limits, logging, database path)
- `.env`: Credentials (NCCOMMONS_USERNAME/PASSWORD, WIKIPEDIA_USERNAME/PASSWORD)
  - Wikipedia uses bot password format: `BotName@BotPassword`

## Code Style

- Line length: 120 characters
- Python target: 3.13
- Type hints on all functions
- Vertical list formatting for multi-line imports (isort `multi_line_output = 3`)
- All code, comments, docstrings, and variable names in English
