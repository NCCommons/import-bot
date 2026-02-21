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
    cp .env.example .env
    ```

    Edit `.env` and add your credentials:

    - `NCCOMMONS_USERNAME`: Your NC Commons username
    - `NCCOMMONS_PASSWORD`: Your NC Commons password
    - `WIKIPEDIA_USERNAME`: Your Wikipedia bot username (format: `BotName@BotPassword`)
    - `WIKIPEDIA_PASSWORD`: Your Wikipedia bot password token

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
├── .env                    # Credentials (gitignored)
├── .env.example            # Credentials template
├── requirements.txt        # Python dependencies
├── .gitignore              # Git ignore file
└── src/                    # Source code
    ├── __init__.py         # Package init
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

### .env

Credentials file (never commit to git):

-   `NCCOMMONS_USERNAME`: NC Commons username
-   `NCCOMMONS_PASSWORD`: NC Commons password
-   `WIKIPEDIA_USERNAME`: Wikipedia bot username
-   `WIKIPEDIA_PASSWORD`: Wikipedia bot password

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

Make sure you copied `.env.example` to `.env` and filled in your credentials.

### "Login failed"

-   For Wikipedia: Use bot password format (`BotName@BotPassword`, not your main password)
-   Check that credentials are correct
-   Ensure bot has appropriate permissions:
    - Edit existing pages
    - Create, edit, and move pages
    - Upload new files
    - Upload, replace, and move files

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

MIT License

## Credits

Created for the NC Commons to Wikipedia import workflow.

Uses:

-   [mwclient](https://github.com/mwclient/mwclient) - MediaWiki API client
-   [wikitextparser](https://github.com/5j9/wikitextparser) - Wikitext parsing
-   [PyYAML](https://pyyaml.org/) - YAML configuration

## Support

For issues or questions, open an issue on GitHub.
