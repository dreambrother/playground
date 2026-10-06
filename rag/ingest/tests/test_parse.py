"""Тесты HTML → Markdown и метаданных страницы."""

from __future__ import annotations

from ingest.crawl import relative_page_file, slug_for
from ingest.parse import parse_page

URL = "https://fastapi.tiangolo.com/tutorial/first-steps/"


def test_title_from_h1(sample_html: str) -> None:
    page = parse_page(sample_html, URL)
    assert page.title == "First Steps"


def test_section_and_path(sample_html: str) -> None:
    page = parse_page(sample_html, URL)
    assert page.path == "/tutorial/first-steps/"
    assert page.section == "tutorial"


def test_markdown_has_python_fence(sample_html: str) -> None:
    page = parse_page(sample_html, URL)
    assert "```python" in page.markdown
    assert "from fastapi import FastAPI" in page.markdown
    assert "```bash" in page.markdown


def test_markdown_drops_navigation_junk(sample_html: str) -> None:
    page = parse_page(sample_html, URL)
    assert "Navigation junk" not in page.markdown
    assert "Footer junk" not in page.markdown
    assert "Was this page helpful" not in page.markdown
    assert "console.log" not in page.markdown
    assert "Permanent link" not in page.markdown
    assert "¶" not in page.markdown


def test_sha256_is_deterministic(sample_html: str) -> None:
    first = parse_page(sample_html, URL)
    second = parse_page(sample_html, URL)
    assert first.content_sha256 == second.content_sha256
    assert first.char_count == len(first.markdown)


def test_title_falls_back_to_document_title() -> None:
    html = (
        "<html><head><title>Reference - FastAPI</title></head>"
        "<body><main><p>x</p></main></body></html>"
    )
    page = parse_page(html, "https://fastapi.tiangolo.com/reference/")
    assert page.title == "Reference"
    assert page.section == "reference"


def test_slug_and_page_file() -> None:
    assert slug_for("/") == "index"
    assert slug_for("/tutorial/first-steps/") == "tutorial_first-steps"
    html = (
        "<html><body><article class='md-content__inner md-typeset'>"
        "<h1>T</h1></article></body></html>"
    )
    page = parse_page(html, "https://fastapi.tiangolo.com/")
    assert relative_page_file(page) == "raw/pages/general/index.md"
