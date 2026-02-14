"""
Wikitext parsing utilities using wikitextparser.

This module provides functions to parse and manipulate wikitext content.
"""

import logging
import re
from dataclasses import dataclass
from typing import List

import wikitextparser as wtp

logger = logging.getLogger(__name__)


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
        template_name = str(template.normal_name()).strip().lower().replace("_", " ")

        if template_name_pattern in template_name:
            # Extract first positional argument (language code)
            arg = template.get_arg("1")
            if arg and arg.value:
                lang_code = arg.value.strip()
                languages.append(lang_code)
                logger.debug(f"Found language: {lang_code}")

    logger.info(f"Parsed {len(languages)} languages: {languages}")
    return languages


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

        if template_name == "nc":
            # Extract filename (first argument)
            filename = ""
            arg1 = template.get_arg("1")
            if arg1 and arg1.value:
                filename = arg1.value.strip()

            # Extract caption (second argument, optional)
            caption = ""
            arg2 = template.get_arg("2")
            if arg2 and arg2.value:
                caption = arg2.value.strip()

            # Only add if filename exists
            if filename:
                nc_template = NCTemplate(original_text=template.string, filename=filename, caption=caption)
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
    cleaned = re.sub(r"\[\[Category:.*?\]\]", "", text, flags=re.IGNORECASE | re.DOTALL)
    return cleaned.strip()
