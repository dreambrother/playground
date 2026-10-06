"""HTML → Markdown и метаданные страницы."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from urllib.parse import urlsplit

from bs4 import BeautifulSoup, Tag
from markdownify import markdownify as _markdownify

from .sitemap import normalize_url

# Навигационная обвязка и мусор, который не нужен в корпусе.
REMOVE_SELECTORS = [
    "script",
    "style",
    "nav",
    "header",
    "footer",
    ".md-header-anchor",
    "a.headerlink",
    ".md-source",
    ".md-content__button",
    ".md-feedback",
    ".md-skip",
    ".md-dialog",
    ".md-top",
]

_FEEDBACK_RE = re.compile(r"was this page helpful", re.IGNORECASE)
_ARTICLE_SELECTOR = "article.md-content__inner.md-typeset"


@dataclass(slots=True)
class Page:
    """Одна распарсенная страница документации."""

    url: str
    path: str
    section: str
    title: str
    markdown: str
    content_sha256: str
    char_count: int
    fetched_at: str

    def manifest_entry(self, file: str) -> dict[str, object]:
        """Запись манифеста: всё, кроме самого ``markdown``."""
        return {
            "url": self.url,
            "path": self.path,
            "section": self.section,
            "title": self.title,
            "content_sha256": self.content_sha256,
            "char_count": self.char_count,
            "fetched_at": self.fetched_at,
            "file": file,
        }


def section_for(path: str) -> str:
    """Первый сегмент пути; корневая страница → ``general``."""
    segments = [segment for segment in path.split("/") if segment]
    return segments[0] if segments else "general"


def _strip_navigation(article: Tag) -> None:
    for selector in REMOVE_SELECTORS:
        for element in article.select(selector):
            element.decompose()
    # Блок «Was this page helpful?» может не иметь класса .md-feedback.
    for heading in article.find_all(["h1", "h2", "h3", "p"]):
        if heading.parent is None:
            continue
        if _FEEDBACK_RE.search(heading.get_text(" ", strip=True)):
            container = heading.find_parent(["section", "div"]) or heading
            container.decompose()


def _code_language(element: Tag) -> str | None:
    """Язык кода из класса ``language-…`` (у тега ``code`` или ``pre``)."""
    for candidate in (element, element.find_parent("pre"), element.find("code")):
        if not isinstance(candidate, Tag):
            continue
        for css_class in candidate.get("class") or []:
            if css_class.startswith("language-"):
                language = css_class[len("language-") :].strip()
                if language:
                    return language
    return None


def extract_article(soup: BeautifulSoup) -> Tag | None:
    """Найти основной блок: article → main → body."""
    for selector in (_ARTICLE_SELECTOR, "article", "main", "body"):
        element = soup.select_one(selector)
        if element is not None:
            return element
    return None


def extract_title(soup: BeautifulSoup) -> str:
    """Заголовок из ``<h1>``, иначе из ``<title>`` без суффикса ``- FastAPI``."""
    h1 = soup.find("h1")
    if isinstance(h1, Tag):
        for anchor in h1.select("a.headerlink"):
            anchor.decompose()
        text = h1.get_text(" ", strip=True)
        if text:
            return text
    if soup.title is not None:
        title = soup.title.get_text(" ", strip=True)
        suffix = " - FastAPI"
        if title.endswith(suffix):
            title = title[: -len(suffix)]
        return title.strip()
    return ""


def extract_markdown(article: Tag) -> str:
    """Сконвертировать блок статьи в Markdown (ATX-заголовки)."""
    html = str(article)
    markdown = _markdownify(
        html,
        heading_style="ATX",
        code_language_callback=_code_language,
    )
    return markdown.strip()


def parse_page(html: str, url: str) -> Page:
    """Распарсить HTML в :class:`Page`."""
    normalized = normalize_url(url)
    path = urlsplit(normalized).path or "/"
    soup = BeautifulSoup(html, "html.parser")

    title = extract_title(soup)
    article = extract_article(soup)
    markdown = ""
    if article is not None:
        _strip_navigation(article)
        markdown = extract_markdown(article)

    digest = sha256(markdown.encode("utf-8")).hexdigest()
    return Page(
        url=normalized,
        path=path,
        section=section_for(path),
        title=title,
        markdown=markdown,
        content_sha256=digest,
        char_count=len(markdown),
        fetched_at=datetime.now(UTC).isoformat(),
    )
