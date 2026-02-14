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

import argparse
import logging
import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv
from src.database import Database
from src.logging_config import setup_logging
from src.parsers import parse_language_list
from src.processor import PageProcessor
from src.uploader import FileUploader
from src.wiki_api import NCCommonsAPI, WikipediaAPI

setup_logging(log_level="DEBUG", name="bot")

logger = logging.getLogger("bot")


def load_credentials() -> dict:
    """
    Load credentials from environment variables or .env file.

    Returns:
        Dictionary with NC Commons and Wikipedia credentials

    Raises:
        FileNotFoundError: If .env file doesn't exist
        KeyError: If required environment variables are missing
    """
    # Load from .env file if it exists
    env_file = ".env"
    if Path(env_file).exists():
        load_dotenv(env_file)
    else:
        raise FileNotFoundError(
            f"Environment file not found: {env_file}\nPlease copy .env.example to .env and fill in your credentials"
        )

    # Get credentials from environment variables
    try:
        return {
            "nc_username": os.environ["NCCOMMONS_USERNAME"],
            "nc_password": os.environ["NCCOMMONS_PASSWORD"],
            "wiki_username": os.environ["WIKIPEDIA_USERNAME"],
            "wiki_password": os.environ["WIKIPEDIA_PASSWORD"],
        }
    except KeyError as e:
        raise KeyError(
            f"Missing environment variable: {e}\nPlease ensure all required variables are set in .env file"
        ) from e


def process_language(
    language_code: str,
    config: dict,
    credentials: dict,
    nc_api: NCCommonsAPI,
    database: Database,
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

    logger.info(f"{'='*60}")
    logger.info(f"Processing language: {language_code}")
    logger.info(f"{'='*60}")

    # Create Wikipedia API client for this language
    wiki_api = WikipediaAPI(language_code, credentials["wiki_username"], credentials["wiki_password"])

    # Create uploader
    uploader = FileUploader(nc_api, wiki_api, database, config)

    # Create page processor
    processor = PageProcessor(wiki_api, uploader, database, config)

    # Get pages with NC template
    max_pages = config["processing"]["max_pages_per_language"]
    pages = wiki_api.get_pages_with_template("Template:NC", limit=max_pages)

    logger.info(f"Found {len(pages)} pages to process")

    # Process each page
    stats = {"pages_processed": 0, "pages_modified": 0, "errors": 0}

    for i, page_title in enumerate(pages, 1):
        logger.info(f"[{i}/{len(pages)}] Processing: {page_title}")

        try:
            modified = processor.process_page(page_title)
            stats["pages_processed"] += 1

            if modified:
                stats["pages_modified"] += 1

        except Exception as e:
            logger.error(f"Error processing page {page_title}: {e}")
            stats["errors"] += 1

    # Get database statistics for this language
    db_stats = database.get_statistics(language_code)
    stats.update(db_stats)

    logger.info(f"Language {language_code} complete:")
    logger.info(f"  Pages processed: {stats['pages_processed']}")
    logger.info(f"  Pages modified: {stats['pages_modified']}")
    logger.info(f"  Total uploads: {stats['total_uploads']}")
    logger.info(f"  Errors: {stats['errors']}")

    return stats


def retrieve_language_list(
    args,
    language_page,
    nc_api: NCCommonsAPI,
):

    languages = {}
    # Determine which languages to process
    if args.languages:
        # Use languages from command line
        languages = args.languages
        logger.info(f"Processing {len(languages)} specified languages: {languages}")
    else:
        # Get all languages from NC Commons page
        page_text = nc_api.get_page_text(language_page)
        languages = parse_language_list(page_text)
        logger.info(f"Processing {len(languages)} languages from {language_page}")
    return languages


def parse_command_line_args():
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

    parser.add_argument("--config", default="config.yaml", help="Path to configuration file (default: config.yaml)")

    parser.add_argument(
        "--lang",
        action="append",
        dest="languages",
        help="Process only specific language(s) (can be used multiple times)",
    )

    args = parser.parse_args()
    return args


def process_languages(
    config,
    credentials,
    database,
    nc_api: NCCommonsAPI,
    languages,
):

    # Process each language
    overall_stats = {
        "languages_processed": 0,
        "total_pages_processed": 0,
        "total_pages_modified": 0,
        "total_uploads": 0,
        "total_errors": 0,
    }

    for lang in languages:
        try:
            stats = process_language(lang, config, credentials, nc_api, database)

            overall_stats["languages_processed"] += 1
            overall_stats["total_pages_processed"] += stats["pages_processed"]
            overall_stats["total_pages_modified"] += stats["pages_modified"]
            overall_stats["total_uploads"] += stats["total_uploads"]
            overall_stats["total_errors"] += stats["errors"]

        except Exception as e:
            logger.error(f"Failed to process language {lang}: {e}")
            overall_stats["total_errors"] += 1

    # Final summary
    logger.info("=" * 60)
    logger.info("Bot Completed")
    logger.info("=" * 60)
    logger.info(f"Languages processed: {overall_stats['languages_processed']}")
    logger.info(f"Pages processed: {overall_stats['total_pages_processed']}")
    logger.info(f"Pages modified: {overall_stats['total_pages_modified']}")
    logger.info(f"Total uploads: {overall_stats['total_uploads']}")
    logger.info(f"Errors: {overall_stats['total_errors']}")


def main():
    """Main entry point for the bot."""
    # Parse command-line arguments
    args = parse_command_line_args()

    # Load configuration
    with open(args.config, "r") as f:
        config = yaml.safe_load(f)

    logger.info("=" * 60)
    logger.info("NC Commons Import Bot Starting")
    logger.info("=" * 60)
    logger.info(f"Configuration loaded from: {args.config}")

    # Load credentials
    credentials = load_credentials()
    logger.info("Credentials loaded")

    # Initialize database
    database = Database(config["database"]["path"])

    # Connect to NC Commons
    nc_api = NCCommonsAPI(credentials["nc_username"], credentials["nc_password"])

    language_page = config["nc_commons"]["language_page"]
    languages = retrieve_language_list(args, language_page, nc_api)

    process_languages(config, credentials, database, nc_api, languages)

    # Get overall database statistics
    db_stats = database.get_statistics()
    logger.info(f"Database totals: {db_stats}")

    return 0


def safe_main():
    try:
        return main()
    except KeyboardInterrupt:

        logger.info("Bot interrupted by user")
        return 130


if __name__ == "__main__":
    sys.exit(safe_main())
