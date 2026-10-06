"""Тесты разбора sitemap и фильтрации URL."""

from __future__ import annotations

from ingest.parse import section_for
from ingest.settings import DEFAULT_INCLUDE_PREFIXES
from ingest.sitemap import normalize_url, parse_sitemap, select_urls


def test_parse_sitemap_returns_all_locs(sitemap_xml: str) -> None:
    urls = parse_sitemap(sitemap_xml)
    assert len(urls) == 5
    assert "https://fastapi.tiangolo.com/tutorial/first-steps/" in urls


def test_normalize_url_strips_query_fragment_and_adds_slash() -> None:
    assert (
        normalize_url("https://fastapi.tiangolo.com/features/?highlight=fast#top")
        == "https://fastapi.tiangolo.com/features/"
    )
    assert (
        normalize_url("https://fastapi.tiangolo.com/reference")
        == "https://fastapi.tiangolo.com/reference/"
    )


def test_select_urls_filters_disallowed_sections(sitemap_xml: str) -> None:
    selected = select_urls(parse_sitemap(sitemap_xml), DEFAULT_INCLUDE_PREFIXES)
    assert "https://fastapi.tiangolo.com/tutorial/first-steps/" in selected
    assert "https://fastapi.tiangolo.com/reference/" in selected
    # /features/?highlight=...#top нормализуется и попадает (он в allowlist)
    assert "https://fastapi.tiangolo.com/features/" in selected
    assert all("translations" not in url for url in selected)
    # корень не входит в allowlist по умолчанию
    assert "https://fastapi.tiangolo.com/" not in selected


def test_select_urls_normalizes_and_dedupes() -> None:
    urls = [
        "https://fastapi.tiangolo.com/tutorial/first-steps",
        "https://fastapi.tiangolo.com/tutorial/first-steps/",
        "https://fastapi.tiangolo.com/translations/",
    ]
    selected = select_urls(urls, ["/tutorial/"])
    assert selected == ["https://fastapi.tiangolo.com/tutorial/first-steps/"]


def test_section_for() -> None:
    assert section_for("/tutorial/first-steps/") == "tutorial"
    assert section_for("/reference/") == "reference"
    assert section_for("/") == "general"
