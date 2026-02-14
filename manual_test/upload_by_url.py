"""
Test script for uploading a file to Wikipedia from URL.

This script tests the upload_from_url functionality directly using the WikipediaAPI class.
"""

import os
import sys
import urllib.request

from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file
# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.temporary_handler import TemporaryDownloadFile  # noqa: E402
from src.wiki_api import WikipediaAPI  # noqa: E402


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
    lang = os.environ.get("WIKI_LANG", "test")

    if not username or not password:
        print("Error: Please set WIKIPEDIA_USERNAME and WIKIPEDIA_PASSWORD environment variables")
        print("Example:")
        print("  set WIKIPEDIA_USERNAME=YourBotUsername")
        print("  set WIKIPEDIA_PASSWORD=YourBotPassword")
        print("  set WIKI_LANG=..")
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
        target_filename = target_filename.replace("File:", "").replace(" ", "_")
        print(f"File uploaded to: https://{lang}.wikipedia.org/wiki/File:{target_filename}")
        return True

    # URL upload not allowed or failed, try file upload
    error_msg = result.get("error")

    if error_msg == "url_disabled":
        print(f"URL upload not allowed, trying file upload: {target_filename}")

        with TemporaryDownloadFile(suffix=".tmp") as temp_path:
            urllib.request.urlretrieve(image_url, temp_path)
            print(f"Downloaded to: {temp_path}")

            # Upload from file
            result = wiki_api.upload_from_file(
                filename=target_filename,
                filepath=temp_path,
                description=description,
                comment=comment,
            )
            if result.get("success"):
                print("✓ Upload successful via file upload!")
                print(f"File uploaded to: https://{lang}.wikipedia.org/wiki/File:{target_filename}")
    else:
        print(f"✗ Upload failed: {error_msg}")


if __name__ == "__main__":
    main()
