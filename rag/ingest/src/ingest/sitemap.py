"""Разбор sitemap.xml и отбор нужных URL."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from urllib.parse import urlsplit, urlunsplit


def parse_sitemap(xml: str) -> list[str]:
    """Вернуть список ``<loc>`` из sitemap (в порядке следования)."""
    root = ET.fromstring(xml)
    urls: list[str] = []
    for element in root.iter():
        if element.tag.endswith("loc") and element.text:
            text = element.text.strip()
            if text:
                urls.append(text)
    return urls


def normalize_url(url: str) -> str:
    """Убрать query-fragment и добавить завершающий слэш к пути."""
    parts = urlsplit(url.strip())
    path = parts.path or "/"
    if not path.endswith("/"):
        path += "/"
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def url_path(url: str) -> str:
    """Путь URL без query/fragment."""
    return urlsplit(url).path or "/"


def select_urls(urls: list[str], prefixes: list[str]) -> list[str]:
    """Нормализовать, убрать дубли и оставить только разрешённые разделы."""
    selected: list[str] = []
    seen: set[str] = set()
    for raw in urls:
        url = normalize_url(raw)
        if url in seen:
            continue
        if not any(url_path(url).startswith(prefix) for prefix in prefixes):
            continue
        seen.add(url)
        selected.append(url)
    return selected
