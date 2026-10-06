"""CLI сервиса ingest: ``python -m ingest crawl [...]``."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from .crawl import crawl
from .settings import Settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ingest",
        description="Сбор и парсинг корпуса документации (фаза 1).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    crawl_parser = subparsers.add_parser("crawl", help="скачать и распарсить документацию")
    crawl_parser.add_argument("--limit", type=int, default=None, help="ограничить число страниц")
    crawl_parser.add_argument("--concurrency", type=int, default=None, help="параллельных загрузок")
    crawl_parser.add_argument("--out", type=Path, default=None, help="каталог данных (DATA_DIR)")
    crawl_parser.add_argument("--base-url", type=str, default=None, help="базовый URL документации")
    crawl_parser.add_argument("--force", action="store_true", help="перезаписать без проверки хэша")
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    # httpx/httpcore логируют каждый запрос на INFO — это слишком шумно.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    args = build_parser().parse_args(argv)

    if args.command == "crawl":
        report = asyncio.run(
            crawl(
                settings=Settings(),
                base_url=args.base_url,
                limit=args.limit,
                concurrency=args.concurrency,
                out_dir=args.out,
                force=args.force,
            )
        )
        if report.total_selected > 0 and report.fetched == 0:
            logging.error("ни одна страница не скачалась")
            return 1
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
