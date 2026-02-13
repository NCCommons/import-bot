"""
Tests for wikitext parsing functions.
"""

import pytest
from src.parsers import parse_language_list, extract_nc_templates, remove_categories, NCTemplate


class TestParseLanguageList:
    """Tests for language list parsing."""

    def test_parse_simple_language_list(self, sample_language_list_page):
        """Test parsing a simple language list."""
        languages = parse_language_list(sample_language_list_page)

        assert len(languages) == 3
        assert "en" in languages
        assert "ar" in languages
        assert "fr" in languages

    def test_parse_empty_page(self):
        """Test parsing an empty page."""
        languages = parse_language_list("")
        assert languages == []

    def test_parse_page_without_templates(self):
        """Test parsing a page with no language templates."""
        text = "This is just plain text without templates."
        languages = parse_language_list(text)
        assert languages == []

    def test_parse_mixed_templates(self):
        """Test parsing a page with mixed templates."""
        text = """
        * {{User:Mr. Ibrahem/import bot/line|en}}
        * {{SomeOtherTemplate|value}}
        * {{User:Mr. Ibrahem/import bot/line|ar}}
        """
        languages = parse_language_list(text)

        assert len(languages) == 2
        assert "en" in languages
        assert "ar" in languages


class TestExtractNCTemplates:
    """Tests for NC template extraction."""

    def test_extract_simple_template(self):
        """Test extracting a simple NC template."""
        text = "{{NC|test.jpg|Caption text}}"
        templates = extract_nc_templates(text)

        assert len(templates) == 1
        assert templates[0].filename == "test.jpg"
        assert templates[0].caption == "Caption text"

    def test_extract_multiple_templates(self, sample_nc_template_page):
        """Test extracting multiple NC templates."""
        templates = extract_nc_templates(sample_nc_template_page)

        assert len(templates) == 2
        assert templates[0].filename == "File1.jpg"
        assert templates[0].caption == "First image caption"
        assert templates[1].filename == "File2.jpg"
        assert templates[1].caption == "Second image caption"

    def test_extract_template_without_caption(self):
        """Test extracting template without caption."""
        text = "{{NC|image.jpg}}"
        templates = extract_nc_templates(text)

        assert len(templates) == 1
        assert templates[0].filename == "image.jpg"
        assert templates[0].caption == ""

    def test_extract_no_templates(self):
        """Test page with no NC templates."""
        text = "This is plain text with {{OtherTemplate}} but no NC."
        templates = extract_nc_templates(text)

        assert templates == []


class TestNCTemplate:
    """Tests for NCTemplate dataclass."""

    def test_to_file_syntax(self):
        """Test conversion to file syntax."""
        template = NCTemplate(original_text="{{NC|test.jpg|My caption}}", filename="test.jpg", caption="My caption")

        result = template.to_file_syntax()
        assert result == "[[File:test.jpg|thumb|My caption]]"

    def test_to_file_syntax_no_caption(self):
        """Test conversion without caption."""
        template = NCTemplate(original_text="{{NC|test.jpg}}", filename="test.jpg", caption="")

        result = template.to_file_syntax()
        assert result == "[[File:test.jpg|thumb|]]"


class TestRemoveCategories:
    """Tests for category removal."""

    def test_remove_single_category(self):
        """Test removing a single category."""
        text = "Some text\n[[Category:Test]]\nMore text"
        result = remove_categories(text)

        assert "[[Category:Test]]" not in result
        assert "Some text" in result
        assert "More text" in result

    def test_remove_multiple_categories(self):
        """Test removing multiple categories."""
        text = """
        Content here
        [[Category:Cat1]]
        [[Category:Cat2]]
        [[Category:Cat3]]
        More content
        """
        result = remove_categories(text)

        assert "[[Category:" not in result
        assert "Content here" in result
        assert "More content" in result

    def test_remove_categories_case_insensitive(self):
        """Test case-insensitive category removal."""
        text = "[[category:Test]] [[CATEGORY:Test2]]"
        result = remove_categories(text)

        assert "[[category:" not in result.lower()

    def test_no_categories(self):
        """Test text without categories."""
        text = "Just plain text"
        result = remove_categories(text)

        assert result == text
