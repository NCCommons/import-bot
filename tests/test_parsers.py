"""
Tests for wikitext parsing functions.
"""

import pytest
from src.parsers import NCTemplate, extract_nc_templates, parse_language_list, remove_categories


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

    def test_remove_categories_with_newlines_inside(self):
        """Test removing categories that span multiple lines."""
        text = "Text\n[[Category:Test\nwith newline]]\nMore"
        result = remove_categories(text)

        # Should remove category even with newline inside
        assert "[[Category:" not in result

    def test_remove_categories_preserves_other_links(self):
        """Test that other wiki links are preserved."""
        text = "[[File:Test.jpg]] [[Category:Remove]] [[Link to page]]"
        result = remove_categories(text)

        assert "[[File:Test.jpg]]" in result
        assert "[[Link to page]]" in result
        assert "[[Category:Remove]]" not in result


class TestParseLanguageListEdgeCases:
    """Additional edge case tests for language list parsing."""

    def test_parse_with_whitespace_in_lang_code(self):
        """Test parsing with extra whitespace."""
        text = "{{User:Mr. Ibrahem/import bot/line| en }}"
        languages = parse_language_list(text)

        # Should trim whitespace
        assert "en" in languages

    def test_parse_with_different_case_template_name(self):
        """Test parsing with different case in template name."""
        text = "{{user:mr. ibrahem/import bot/line|fr}}"
        languages = parse_language_list(text)

        assert "fr" in languages

    def test_parse_with_underscores_in_template_name(self):
        """Test parsing with underscores in template name."""
        text = "{{User:Mr._Ibrahem/import_bot/line|de}}"
        languages = parse_language_list(text)

        assert "de" in languages

    def test_parse_duplicate_languages(self):
        """Test parsing list with duplicate language codes."""
        text = """
        {{User:Mr. Ibrahem/import bot/line|en}}
        {{User:Mr. Ibrahem/import bot/line|ar}}
        {{User:Mr. Ibrahem/import bot/line|en}}
        """
        languages = parse_language_list(text)

        # Should include duplicates (up to caller to dedupe if needed)
        assert languages.count("en") == 2
        assert "ar" in languages


class TestExtractNCTemplatesEdgeCases:
    """Additional edge case tests for NC template extraction."""

    def test_extract_template_with_extra_whitespace(self):
        """Test extracting template with extra whitespace."""
        text = "{{NC| test.jpg | Caption text }}"
        templates = extract_nc_templates(text)

        assert len(templates) == 1
        # Should trim whitespace
        assert templates[0].filename == "test.jpg"
        assert templates[0].caption == "Caption text"

    def test_extract_template_with_newlines(self):
        """Test extracting template with newlines in parameters."""
        text = """{{NC|test.jpg|Caption with
        newline inside}}"""
        templates = extract_nc_templates(text)

        assert len(templates) == 1
        assert templates[0].filename == "test.jpg"
        assert "Caption with" in templates[0].caption

    def test_extract_template_case_sensitive(self):
        """Test that template name matching is case-insensitive."""
        text = "{{nc|test.jpg|Caption}}"
        templates = extract_nc_templates(text)

        assert len(templates) == 1
        assert templates[0].filename == "test.jpg"

    def test_extract_template_without_filename(self):
        """Test extracting template without filename (malformed)."""
        text = "{{NC||Caption only}}"
        templates = extract_nc_templates(text)

        # Should skip templates without filename
        assert len(templates) == 0

    def test_extract_template_with_extra_parameters(self):
        """Test extracting template with more than 2 parameters."""
        text = "{{NC|test.jpg|Caption|extra|params}}"
        templates = extract_nc_templates(text)

        # Should extract first two parameters
        assert len(templates) == 1
        assert templates[0].filename == "test.jpg"
        assert templates[0].caption == "Caption"

    def test_extract_template_with_wikitext_in_caption(self):
        """Test extracting template with wikitext in caption."""
        text = "{{NC|test.jpg|Caption with [[link]] and '''bold'''}}"
        templates = extract_nc_templates(text)

        assert len(templates) == 1
        assert templates[0].filename == "test.jpg"
        assert "[[link]]" in templates[0].caption
        assert "'''bold'''" in templates[0].caption

    def test_extract_template_with_unicode_filename(self):
        """Test extracting template with unicode filename."""
        text = "{{NC|文件名.jpg|标题}}"
        templates = extract_nc_templates(text)

        assert len(templates) == 1
        assert templates[0].filename == "文件名.jpg"
        assert templates[0].caption == "标题"

    def test_extract_template_with_special_chars_filename(self):
        """Test extracting template with special characters in filename."""
        text = "{{NC|File's name (2).jpg|Caption}}"
        templates = extract_nc_templates(text)

        assert len(templates) == 1
        assert templates[0].filename == "File's name (2).jpg"


class TestNCTemplateEdgeCases:
    """Additional edge case tests for NCTemplate dataclass."""

    def test_to_file_syntax_with_special_chars(self):
        """Test conversion with special characters."""
        template = NCTemplate(
            original_text="{{NC|test's (2).jpg|Caption}}", filename="test's (2).jpg", caption='Caption with "quotes"'
        )

        result = template.to_file_syntax()
        assert result == '[[File:test\'s (2).jpg|thumb|Caption with "quotes"]]'

    def test_to_file_syntax_with_unicode(self):
        """Test conversion with unicode characters."""
        template = NCTemplate(original_text="{{NC|文件.jpg|标题}}", filename="文件.jpg", caption="标题")

        result = template.to_file_syntax()
        assert result == "[[File:文件.jpg|thumb|标题]]"

    def test_to_file_syntax_with_wikitext_caption(self):
        """Test conversion preserves wikitext in caption."""
        template = NCTemplate(
            original_text="{{NC|test.jpg|Caption with [[link]]}}", filename="test.jpg", caption="Caption with [[link]]"
        )

        result = template.to_file_syntax()
        assert result == "[[File:test.jpg|thumb|Caption with [[link]]]]"

    def test_original_text_preserved(self):
        """Test that original text is preserved in dataclass."""
        original = "{{NC|test.jpg|Caption}}"
        template = NCTemplate(original_text=original, filename="test.jpg", caption="Caption")

        assert template.original_text == original
