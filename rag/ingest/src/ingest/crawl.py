"""Оркестрация crawl: sitemap → fetch → parse → запись страниц и манифеста."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from .fetch import fetch_all, fetch_text, make_client
from .parse import Page, parse_page
from .settings import Settings
from .sitemap import parse_sitemap, select_urls

log = logging.getLogger(__name__)

MANIFEST_NAME = "manifest.jsonl"
RAW_SUBDIR = Path("raw")
PAGES_SUBDIR = RAW_SUBDIR / "pages"


@dataclass(slots=True)
class CrawlReport:
    """Итоги одного запуска crawl."""

    total_selected: int = 0
    fetched: int = 0
    failed: int = 0
    written: int = 0
    skipped: int = 0
    total_chars: int = 0
    manifest_size_bytes: int = 0
    md_files: int = 0
    errors: list[str] = field(default_factory=list)


def slug_for(path: str) -> str:
    """Слаг файла: слэши → ``_``, корневой путь → ``index``."""
    stripped = path.strip("/")
    if not stripped:
        return "index"
    return stripped.replace("/", "_")


def relative_page_file(page: Page) -> str:
    """Относительный путь страницы внутри каталога данных."""
    return (PAGES_SUBDIR / page.section / f"{slug_for(page.path)}.md").as_posix()


def _read_manifest(path: Path) -> dict[str, dict[str, object]]:
    """Прочитать существующий манифест в словарь ``url → запись``."""
    entries: dict[str, dict[str, object]] = {}
    if not path.exists():
        return entries
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        url = entry.get("url")
        if isinstance(url, str):
            entries[url] = entry
    return entries


def _write_page(page: Page, out_dir: Path) -> None:
    """Записать Markdown-страницу."""
    target = out_dir / relative_page_file(page)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page.markdown + "\n", encoding="utf-8")


async def crawl(
    *,
    settings: Settings | None = None,
    base_url: str | None = None,
    limit: int | None = None,
    concurrency: int | None = None,
    out_dir: Path | None = None,
    force: bool = False,
) -> CrawlReport:
    """Скачать и распарсить корпус. Без эмбеддингов и Qdrant (фаза 1)."""
    settings = settings or Settings()
    base = (base_url or settings.docs_base_url).rstrip("/")
    out_dir = Path(out_dir) if out_dir else settings.data_dir
    workers = concurrency or settings.concurrency
    report = CrawlReport()

    pages_dir = out_dir / PAGES_SUBDIR
    manifest_path = out_dir / RAW_SUBDIR / MANIFEST_NAME
    existing = _read_manifest(manifest_path)

    async with make_client(settings) as client:
        sitemap_url = f"{base}/sitemap.xml"
        log.info("читаю sitemap: %s", sitemap_url)
        sitemap_xml = await fetch_text(client, sitemap_url)

        urls = select_urls(parse_sitemap(sitemap_xml), settings.include_prefixes)
        if limit is not None:
            urls = urls[:limit]
        report.total_selected = len(urls)
        log.info("к загрузке: %d страниц (concurrency=%d)", len(urls), workers)

        results = await fetch_all(client, urls, workers)

        parsed: list[Page] = []
        fresh_entries: dict[str, dict[str, object]] = {}
        for result in results:
            if not result.ok:
                report.failed += 1
                report.errors.append(f"{result.url}: {result.error}")
                continue
            report.fetched += 1
            page = parse_page(result.text or "", result.url)
            parsed.append(page)
            report.total_chars += page.char_count
            rel_file = relative_page_file(page)

            unchanged = (
                not force
                and existing.get(page.url, {}).get("content_sha256") == page.content_sha256
                and (out_dir / rel_file).exists()
            )
            if unchanged:
                report.skipped += 1
                log.info("= %s (%d симв.) — без изменений", page.url, page.char_count)
                continue

            _write_page(page, out_dir)
            report.written += 1
            fresh_entries[page.url] = page.manifest_entry(rel_file)
            log.info("+ %s (%d симв.)", page.url, page.char_count)

    if limit is not None:
        # Частичный прогон (--limit) не должен затирать полный манифест.
        log.warning("--limit задан: манифест не перезаписываю (частичный прогон)")
        report.manifest_size_bytes = manifest_path.stat().st_size if manifest_path.exists() else 0
    else:
        # Манифест: для перезаписанных — свежие записи, для пропущенных — старые.
        manifest: dict[str, dict[str, object]] = {}
        for page in parsed:
            if page.url in fresh_entries:
                manifest[page.url] = fresh_entries[page.url]
            elif page.url in existing:
                manifest[page.url] = existing[page.url]

        lines = [
            json.dumps(manifest[page.url], ensure_ascii=False)
            for page in parsed
            if page.url in manifest
        ]
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        report.manifest_size_bytes = manifest_path.stat().st_size
    report.md_files = sum(1 for _ in pages_dir.rglob("*.md")) if pages_dir.exists() else 0

    log.info(
        "готово: скачано=%d, ошибок=%d, записано=%d, пропущено=%d, .md=%d, manifest=%.1f КБ",
        report.fetched,
        report.failed,
        report.written,
        report.skipped,
        report.md_files,
        report.manifest_size_bytes / 1024,
    )
    return report
