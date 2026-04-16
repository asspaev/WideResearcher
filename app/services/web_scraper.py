"""Получение HTML-контента с веб-страниц."""

import asyncio

from curl_cffi.requests import AsyncSession
from fake_useragent import UserAgent
from loguru import logger

SCRAPE_MAX_RETRIES = 3
SCRAPE_RETRY_DELAY = 1.0


class WebScraper:
    """Загружает сырой HTML с URL через curl_cffi с отпечатком браузера.

    Использует fake-useragent для генерации реалистичного User-Agent
    и curl_cffi для имитации TLS-отпечатка Chrome.
    """

    def __init__(self) -> None:
        self._ua = UserAgent()

    async def fetch(self, url: str) -> str | None:
        """Загружает HTML-контент по URL с повторными попытками.

        Args:
            url: URL страницы для загрузки.

        Returns:
            Сырой HTML-контент или None если все попытки завершились ошибкой.
        """
        for attempt in range(1, SCRAPE_MAX_RETRIES + 1):
            try:
                headers = {"User-Agent": self._ua.random}
                async with AsyncSession(impersonate="chrome") as session:
                    response = await session.get(url, headers=headers, timeout=15)
                    response.raise_for_status()
                    logger.debug(f"WebScraper: fetched {url!r} (attempt {attempt})")
                    return response.text
            except Exception as exc:
                logger.warning(f"WebScraper: attempt {attempt}/{SCRAPE_MAX_RETRIES} failed for {url!r}: {exc}")
                if attempt < SCRAPE_MAX_RETRIES:
                    await asyncio.sleep(SCRAPE_RETRY_DELAY)

        logger.error(f"WebScraper: all retries exhausted for {url!r}")
        return None
