"""Общие фикстуры тестов (без сети)."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture(scope="session")
def sitemap_xml() -> str:
    return (FIXTURES / "sitemap.xml").read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def sample_html() -> str:
    return (FIXTURES / "sample_page.html").read_text(encoding="utf-8")
