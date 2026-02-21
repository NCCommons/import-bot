#!/usr/bin/env python3
"""
NC Commons to Wikipedia Import Bot

Main entry point for the bot that imports files from NC Commons to Wikipedia
across multiple languages. This bot automates the process of:
1. Finding Wikipedia pages with {{NC|filename}} templates
2. Downloading files from NC Commons
3. Uploading files to Wikipedia
4. Replacing templates with standard [[File:...]] syntax
5. Tracking all activity in SQLite database

Usage:
    python bot.py                  # Process all languages
    python bot.py --lang ar        # Process only Arabic Wikipedia
    python bot.py --lang en --lang fr  # Process English and French
    python bot.py --config custom.yaml  # Use custom config file

Architecture Overview:
    bot.py (entry point)
        └── src/
            ├── wiki_api/      # MediaWiki API clients
            │   ├── main_api.py      # Base WikiAPI class
            │   ├── nccommons_api.py # NC Commons client
            │   ├── wikipedia_api.py # Wikipedia client
            │   └── upload_handler.py # File upload logic
            ├── parsers.py     # Wikitext parsing
            ├── uploader.py    # File upload orchestration
            ├── processor.py   # Page processing workflow
            ├── database.py    # SQLite operations
            └── logging_config.py # Logging setup

Environment Variables (required in .env):
    NCCOMMONS_USERNAME: NC Commons username
    NCCOMMONS_PASSWORD: NC Commons password
    WIKIPEDIA_USERNAME: Wikipedia bot username (BotName@BotPassword)
    WIKIPEDIA_PASSWORD: Wikipedia bot password token
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml
from dotenv import load_dotenv
from src.database import Database
from src.logging_config import setup_logging
from src.parsers import parse_language_list
from src.processor import PageProcessor
from src.uploader import FileUploader
from src.wiki_api import NCCommonsAPI, WikipediaAPI

# Initialize logging before any module-level operations
setup_logging(log_level="DEBUG", name="bot")

logger = logging.getLogger("bot")


def load_credentials() -> Dict[str, str]:
    """
    Load credentials from environment variables or .env file.

    Credentials are loaded from a .env file in the project root or from
    existing environment variables. The .env file should contain:
        NCCOMMONS_USERNAME=your_username
        NCCOMMONS_PASSWORD=your_password
        WIKIPEDIA_USERNAME=BotName@BotPasswordName
        WIKIPEDIA_PASSWORD=bot_password_token

    Returns:
        Dictionary with keys:
        - nc_username: NC Commons username
        - nc_password: NC Commons password
        - wiki_username: Wikipedia bot username
        - wiki_password: Wikipedia bot password

    Raises:
        FileNotFoundError: If .env file doesn't exist.
        KeyError: If any required environment variable is missing.

    Example:
        >>> creds = load_credentials()
        >>> print(f"Logging in as {creds['wiki_username']}")
    """
    env_file: str = ".env"
    env_path: Path = Path(env_file)

    if env_path.exists():
        load_dotenv(env_file)
    else:
        raise FileNotFoundError(
            f"Environment file not found: {env_file}\n" "Please copy .env.example to .env and fill in your credentials"
        )

    try:
        return {
            "nc_username": os.environ["NCCOMMONS_USERNAME"],
            "nc_password": os.environ["NCCOMMONS_PASSWORD"],
            "wiki_username": os.environ["WIKIPEDIA_USERNAME"],
            "wiki_password": os.environ["WIKIPEDIA_PASSWORD"],
        }
    except KeyError as e:
        missing_var: str = str(e).strip("'")
        raise KeyError(
            f"Missing environment variable: {missing_var}\n" "Please ensure all required variables are set in .env file"
        ) from e


def process_language(
    language_code: str,
    config: Dict[str, Any],
    credentials: Dict[str, str],
    nc_api: NCCommonsAPI,
    database: Database,
) -> Dict[str, int]:
    """
    Process all pages for a single Wikipedia language.

    Creates the necessary API clients and processors for a language,
    then iterates through all pages containing the NC template.

    Args:
        language_code: Wikipedia language code (e.g., 'en', 'ar', 'fr').
        config: Configuration dictionary from YAML file.
        credentials: Dictionary with Wikipedia login credentials.
        nc_api: Shared NC Commons API client.
        database: Database instance for tracking.

    Returns:
        Dictionary with processing statistics:
        - pages_processed: Number of pages examined
        - pages_modified: Number of pages with changes
        - errors: Number of processing errors
        - total_uploads: Total successful uploads (from database)
        - total_pages: Total pages processed (from database)

    Example:
        >>> stats = process_language("en", config, credentials, nc_api, db)
        >>> print(f"Processed {stats['pages_processed']} pages")
    """
    logger.info("=" * 60)
    logger.info(f"Processing language: {language_code}")
    logger.info("=" * 60)

    # Create Wikipedia API client for this language
    wiki_api: WikipediaAPI = WikipediaAPI(
        language_code,
        credentials["wiki_username"],
        credentials["wiki_password"],
    )

    # Create uploader for this language
    uploader: FileUploader = FileUploader(nc_api, wiki_api, database, config)

    # Create page processor
    processor: PageProcessor = PageProcessor(wiki_api, uploader, database, config)

    # Get pages with NC template
    max_pages: int = config["processing"]["max_pages_per_language"]
    pages: List[str] = wiki_api.get_pages_with_template("Template:NC", limit=max_pages)

    logger.info(f"Found {len(pages)} pages to process")

    # Process each page
    stats: Dict[str, int] = {
        "pages_processed": 0,
        "pages_modified": 0,
        "errors": 0,
    }

    for i, page_title in enumerate(pages, 1):
        logger.info(f"[{i}/{len(pages)}] Processing: {page_title}")

        try:
            modified: bool = processor.process_page(page_title)
            stats["pages_processed"] += 1

            if modified:
                stats["pages_modified"] += 1

        except Exception as e:
            logger.error(f"Error processing page {page_title}: {e}")
            stats["errors"] += 1

    # Add database statistics for this language
    db_stats: Dict[str, int] = database.get_statistics(language_code)
    stats.update(db_stats)

    # Log summary
    logger.info(f"Language {language_code} complete:")
    logger.info(f"  Pages processed: {stats['pages_processed']}")
    logger.info(f"  Pages modified: {stats['pages_modified']}")
    logger.info(f"  Total uploads: {stats['total_uploads']}")
    logger.info(f"  Errors: {stats['errors']}")

    return stats


def retrieve_language_list(
    args: argparse.Namespace,
    language_page: str,
    nc_api: NCCommonsAPI,
) -> List[str]:
    """
    Determine which languages to process.

    Languages can come from:
    1. Command-line arguments (--lang option)
    2. NC Commons configuration page (parsed wikitext)

    Args:
        args: Parsed command-line arguments.
        language_page: Title of the NC Commons page with language list.
        nc_api: NC Commons API client for fetching the page.

    Returns:
        List of language codes to process.

    Example:
        >>> languages = retrieve_language_list(args, "User:Bot/languages", nc_api)
        >>> print(f"Processing: {', '.join(languages)}")
    """
    languages: List[str] = []

    if args.languages:
        # Use languages from command line
        languages = args.languages
        logger.info(f"Processing {len(languages)} specified languages: {languages}")
    else:
        # Get all languages from NC Commons page
        page_text: str = nc_api.get_page_text(language_page)
        languages = parse_language_list(page_text)
        logger.info(f"Processing {len(languages)} languages from {language_page}")

    return languages


def parse_command_line_args() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
        Namespace with attributes:
        - config: Path to configuration file (default: "config.yaml")
        - languages: List of language codes (or None for all)

    Example:
        >>> args = parse_command_line_args()
        >>> print(f"Config file: {args.config}")
    """
    parser = argparse.ArgumentParser(
        description="NC Commons to Wikipedia Import Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python bot.py                     # Process all languages
    python bot.py --lang ar           # Process only Arabic
    python bot.py --lang en --lang fr # Process English and French
        """,
    )

    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to configuration file (default: config.yaml)",
    )

    parser.add_argument(
        "--lang",
        action="append",
        dest="languages",
        help="Process only specific language(s) (can be used multiple times)",
    )

    return parser.parse_args()


def process_languages(
    config: Dict[str, Any],
    credentials: Dict[str, str],
    database: Database,
    nc_api: NCCommonsAPI,
    languages: List[str],
) -> Dict[str, int]:
    """
    Process multiple Wikipedia languages.

    Iterates through the language list and processes each one,
    accumulating statistics and handling errors gracefully.

    Args:
        config: Configuration dictionary.
        credentials: Wikipedia credentials.
        database: Database instance.
        nc_api: NC Commons API client.
        languages: List of language codes to process.

    Returns:
        Dictionary with overall statistics:
        - languages_processed: Number of languages completed
        - total_pages_processed: Total pages across all languages
        - total_pages_modified: Total pages modified
        - total_uploads: Total uploads across all languages
        - total_errors: Total errors encountered
    """
    overall_stats: Dict[str, int] = {
        "languages_processed": 0,
        "total_pages_processed": 0,
        "total_pages_modified": 0,
        "total_uploads": 0,
        "total_errors": 0,
    }

    for lang in languages:
        try:
            stats: Dict[str, int] = process_language(lang, config, credentials, nc_api, database)

            overall_stats["languages_processed"] += 1
            overall_stats["total_pages_processed"] += stats["pages_processed"]
            overall_stats["total_pages_modified"] += stats["pages_modified"]
            overall_stats["total_uploads"] += stats["total_uploads"]
            overall_stats["total_errors"] += stats["errors"]

        except Exception as e:
            logger.error(f"Failed to process language {lang}: {e}")
            overall_stats["total_errors"] += 1

    # Log final summary
    logger.info("=" * 60)
    logger.info("Bot Completed")
    logger.info("=" * 60)
    logger.info(f"Languages processed: {overall_stats['languages_processed']}")
    logger.info(f"Pages processed: {overall_stats['total_pages_processed']}")
    logger.info(f"Pages modified: {overall_stats['total_pages_modified']}")
    logger.info(f"Total uploads: {overall_stats['total_uploads']}")
    logger.info(f"Errors: {overall_stats['total_errors']}")

    return overall_stats


def main() -> int:
    """
    Main entry point for the bot.

    Orchestrates the complete bot workflow:
    1. Parse command-line arguments
    2. Load configuration
    3. Load credentials
    4. Initialize database
    5. Connect to NC Commons
    6. Process all languages
    7. Report statistics

    Returns:
        Exit code (0 for success, non-zero for errors).
    """
    # Parse command-line arguments
    args: argparse.Namespace = parse_command_line_args()

    # Load configuration
    with open(args.config, "r", encoding="utf-8") as f:
        config: Dict[str, Any] = yaml.safe_load(f)

    logger.info("=" * 60)
    logger.info("NC Commons Import Bot Starting")
    logger.info("=" * 60)
    logger.info(f"Configuration loaded from: {args.config}")

    # Load credentials
    credentials: Dict[str, str] = load_credentials()
    logger.info("Credentials loaded")

    # Initialize database
    database: Database = Database(config["database"]["path"])

    # Connect to NC Commons
    nc_api: NCCommonsAPI = NCCommonsAPI(
        credentials["nc_username"],
        credentials["nc_password"],
    )

    # Get language list
    language_page: str = config["nc_commons"]["language_page"]
    languages: List[str] = retrieve_language_list(args, language_page, nc_api)

    # Process all languages
    process_languages(config, credentials, database, nc_api, languages)

    # Get overall database statistics
    db_stats: Dict[str, int] = database.get_statistics()
    logger.info(f"Database totals: {db_stats}")

    return 0


def safe_main() -> int:
    """
    Safe wrapper around main() with exception handling.

    Catches KeyboardInterrupt for graceful shutdown and any
    unexpected exceptions for logging.

    Returns:
        Exit code (0 for success, 130 for KeyboardInterrupt, 1 for errors).
    """
    try:
        return main()
    except KeyboardInterrupt:
        logger.info("Bot interrupted by user")
        return 130
    except Exception as e:
        logger.exception(f"Bot failed with unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(safe_main())
