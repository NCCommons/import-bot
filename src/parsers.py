"""
Wikitext parsing utilities using wikitextparser.

This module provides functions and data classes for parsing and manipulating
wikitext content, specifically focusing on:

1. NC Template Extraction: Finding {{NC|filename|caption}} templates
2. Language List Parsing: Extracting language codes from configuration pages
3. Category Manipulation: Removing category tags from file descriptions

Architecture Decision - Why wikitextparser?
    The wikitextparser library provides robust parsing of MediaWiki wikitext
    while handling edge cases like nested templates, complex argument values,
    and various formatting quirks. Regex-based parsing would be fragile for
    these use cases.

Example:
    >>> from src.parsers import extract_nc_templates, NCTemplate
    >>> text = "{{NC|photo.jpg|A beautiful photo}}"
    >>> templates = extract_nc_templates(text)
    >>> templates[0].filename
    'photo.jpg'
    >>> templates[0].to_file_syntax()
    '[[File:photo.jpg|thumb|A beautiful photo]]'
"""

import logging
import re
from dataclasses import dataclass, field
from typing import List

import wikitextparser as wtp

logger = logging.getLogger(__name__)


@dataclass
class NCTemplate:
    """
    Represents a {{NC}} template found in a Wikipedia page.

    The NC (NC Commons) template is used to mark files that should be imported
    from NC Commons to Wikipedia. This dataclass captures the template's
    components for processing and conversion.

    Template Format:
        {{NC|filename.jpg|optional caption}}

    Attributes:
        original_text: The complete original template wikitext as found in the page.
            This is used for accurate string replacement during page updates.
        filename: The name of the file to import from NC Commons.
            May or may not include the 'File:' prefix.
        caption: Optional caption for the file when displayed in articles.
            Defaults to empty string if not provided in template.

    Example:
        >>> template = NCTemplate(
        ...     original_text="{{NC|Example.jpg|An example image}}",
        ...     filename="Example.jpg",
        ...     caption="An example image"
        ... )
        >>> template.to_file_syntax()
        '[[File:Example.jpg|thumb|An example image]]'
    """

    original_text: str
    filename: str
    caption: str = ""

    def to_file_syntax(self, filename: str | None = None) -> str:
        """
        Convert NC template to standard Wikipedia file syntax.

        Transforms the NC template into the standard [[File:...]] syntax
        used to embed images in Wikipedia articles.

        Args:
            filename: Optional alternative filename to use instead of self.filename.
                Useful when the file is a duplicate and should reference
                the original file instead. Defaults to self.filename.

        Returns:
            Wikipedia file syntax string in the format:
            [[File:filename.jpg|thumb|caption]]

        Example:
            >>> template = NCTemplate("{{NC|Test.jpg|Test image}}", "Test.jpg", "Test image")
            >>> template.to_file_syntax()
            '[[File:Test.jpg|thumb|Test image]]'
            >>> template.to_file_syntax("Original.jpg")  # For duplicate handling
            '[[File:Original.jpg|thumb|Test image]]'
        """
        use_filename = filename or self.filename
        # Normalize filename by removing 'File:' prefix if present
        use_filename = use_filename.removeprefix("File:").removeprefix("file:")
        return f"[[File:{use_filename}|thumb|{self.caption}]]"


def parse_language_list(page_text: str) -> List[str]:
    """
    Extract language codes from the NC Commons language list page.

    Parses a wikitext page containing a list of languages to process,
    extracting the language codes from specific template invocations.

    Expected Template Format:
        {{User:Mr. Ibrahem/import bot/line|LANGUAGE_CODE}}

    Args:
        page_text: Raw wikitext content of the language list page from NC Commons.

    Returns:
        List of lowercase language codes (e.g., ['en', 'ar', 'fr', 'de']).
        Returns empty list if no matching templates are found.

    Example:
        >>> page = "{{User:Mr. Ibrahem/import bot/line|en}}{{User:Mr. Ibrahem/import bot/line|ar}}"
        >>> parse_language_list(page)
        ['en', 'ar']

    Note:
        Language codes are extracted from the first positional parameter (|1= or |arg).
        The template name matching is case-insensitive and ignores underscores.
    """
    logger.info("Parsing language list")

    parsed = wtp.parse(page_text)
    languages: List[str] = []

    # Template name pattern - normalized for case-insensitive matching
    template_name_pattern = "user:mr. ibrahem/import bot/line"

    for template in parsed.templates:
        # Normalize template name for comparison (lowercase, spaces instead of underscores)
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

    Parses wikitext content and finds all NC template invocations,
    extracting their filenames and captions for processing.

    Template Format:
        {{NC|filename.jpg}}              - Without caption
        {{NC|filename.jpg|caption}}      - With caption

    Args:
        page_text: Raw wikitext content of a Wikipedia page.

    Returns:
        List of NCTemplate objects, one for each NC template found.
        Templates with empty filenames are skipped.

    Example:
        >>> text = "Article text {{NC|Photo1.jpg|First}} more text {{NC|Photo2.jpg}}"
        >>> templates = extract_nc_templates(text)
        >>> len(templates)
        2
        >>> templates[0].filename
        'Photo1.jpg'
        >>> templates[0].caption
        'First'
        >>> templates[1].caption
        ''

    Note:
        The template name matching is case-insensitive, so {{nc}}, {{Nc}},
        and {{NC}} are all recognized.
    """
    logger.debug("Extracting NC templates")

    parsed = wtp.parse(page_text)
    templates: List[NCTemplate] = []

    for template in parsed.templates:
        # Check if this is an NC template (case-insensitive)
        template_name = str(template.normal_name()).strip().lower()

        if template_name == "nc":
            # Extract filename (first positional argument)
            filename = ""
            arg1 = template.get_arg("1")
            if arg1 and arg1.value:
                filename = arg1.value.strip()

            # Extract caption (second positional argument, optional)
            caption = ""
            arg2 = template.get_arg("2")
            if arg2 and arg2.value:
                caption = arg2.value.strip()

            # Only add if filename exists
            if filename:
                nc_template = NCTemplate(
                    original_text=template.string,
                    filename=filename,
                    caption=caption,
                )
                templates.append(nc_template)
                logger.debug(f"Found NC template: {filename}")

    logger.info(f"Extracted {len(templates)} NC templates")
    return templates


def remove_categories(text: str) -> str:
    """
    Remove all category tags from wikitext.

    Strips [[Category:...]] or [[category:...]] links from wikitext content.
    This is used when processing file descriptions to remove source wiki
    categories before importing to the target wiki.

    Args:
        text: Wikitext content potentially containing category tags.

    Returns:
        Text with all category tags removed, trimmed of leading/trailing whitespace.

    Example:
        >>> text = "Description\\n[[Category:Images]][[Category:Photos]]"
        >>> remove_categories(text)
        'Description'

    Note:
        - The regex uses re.DOTALL to handle multi-line category tags
        - Matching is case-insensitive to catch [[category:]], [[Category:]], etc.
        - The function handles both [[Category:Name]] and [[Category:Name|SortKey]] formats
    """
    # Remove category tags (case-insensitive)
    cleaned = re.sub(r"\[\[Category:.*?\]\]", "", text, flags=re.IGNORECASE | re.DOTALL)
    return cleaned.strip()
