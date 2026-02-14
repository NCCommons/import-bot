"""
Test script for uploading a file to Wikipedia from URL.

This script tests the upload_from_url functionality directly using the WikipediaAPI class.
"""

import os
import sys

from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file
# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.logging_config import setup_logging  # noqa: E402
from src.wiki_api import WikipediaAPI  # noqa: E402

setup_logging(
    "INFO",
    "./logs/bot.log",
    10485760,
    5,
)


def main():

    # Test image URL from NC Commons
    image_url = "https://nccommons.org/m/a/ae/President_Jacbo_Zuma_attends_The_New_Age_and_SABC_Business_briefing%2C_16_Mar_2012.jpg"

    # Target filename on Wikipedia
    target_filename = "File:President Jacbo Zuma attends The New Age and SABC Business briefing, 16 Mar 2012.jpg"

    # File description (wikitext)
    description = """== Summary ==
    President Jacob Zuma attends The New Age and SABC Business briefing, 16 Mar 2012.

    == Licensing ==
    {{NC Commons license}}

    [[Category:Imported from NC Commons]]"""

    # Upload comment
    comment = "Test upload from NC Commons via URL"

    """Run the upload test."""
    # Get credentials from environment variables
    username = os.environ.get("WIKIPEDIA_USERNAME")
    password = os.environ.get("WIKIPEDIA_PASSWORD")
    lang = os.environ.get("WIKI_LANG", "af")

    if not username or not password:
        print("Error: Please set WIKIPEDIA_USERNAME and WIKIPEDIA_PASSWORD environment variables")
        print("Example:")
        print("  set WIKIPEDIA_USERNAME=YourBotUsername")
        print("  set WIKIPEDIA_PASSWORD=YourBotPassword")
        print("  set WIKI_LANG=af")
        sys.exit(1)

    print(f"Connecting to {lang}.wikipedia.org...")
    print(f"Username: {username}")
    print(f"Target file: {target_filename}")
    print(f"Source URL: {image_url}")
    print("-" * 50)

    # Initialize Wikipedia API
    wiki_api = WikipediaAPI(
        language_code=lang,
        username=username,
        password=password,
    )

    print("Connected successfully!")
    print("Attempting upload from URL...")
    print("-" * 50)

    # Attempt upload
    result = wiki_api.upload_from_url(
        filename=target_filename,
        url=image_url,
        description=description,
        comment=comment,
    )

    if result.get("success"):
        print("✓ Upload successful!")
        print(f"File uploaded to: https://{lang}.wikipedia.org/wiki/File:{target_filename}")
    else:
        print(f"✗ Upload failed: {result.get('error')}")


if __name__ == "__main__":
    main()
