"""HTTP-загрузка страниц: IPv4-only клиент, ретраи, ограничение параллелизма."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .settings import Settings

log = logging.getLogger(__name__)


@dataclass(slots=True)
class FetchResult:
    """Результат загрузки одной страницы."""

    url: str
    text: str | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.text is not None


def make_client(settings: Settings) -> httpx.AsyncClient:
    """Клиент, который обязан ходить только по IPv4.

    На хосте нет IPv6, поэтому ``local_address="0.0.0.0"`` форсит IPv4.
    Ретраи httpx отключены — за них отвечает tenacity.
    """
    transport = httpx.AsyncHTTPTransport(local_address="0.0.0.0", retries=0)
    return httpx.AsyncClient(
        transport=transport,
        timeout=settings.request_timeout,
        follow_redirects=True,
        headers={"User-Agent": settings.user_agent},
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
    retry=retry_if_exception_type(httpx.TransportError),
    reraise=True,
)
async def fetch_text(client: httpx.AsyncClient, url: str) -> str:
    """Скачать URL как текст. Ошибки транспорта повторяются 3 раза."""
    response = await client.get(url)
    response.raise_for_status()
    return response.text


async def fetch_all(
    client: httpx.AsyncClient,
    urls: list[str],
    concurrency: int,
) -> list[FetchResult]:
    """Скачать все URL параллельно, не падая на отдельных ошибках."""
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def _one(url: str) -> FetchResult:
        async with semaphore:
            try:
                text = await fetch_text(client, url)
                return FetchResult(url=url, text=text)
            except Exception as exc:  # noqa: BLE001 — изолируем сбой одной страницы
                log.warning("не удалось скачать %s: %s", url, exc)
                return FetchResult(url=url, error=f"{type(exc).__name__}: {exc}")

    return await asyncio.gather(*(_one(url) for url in urls))
