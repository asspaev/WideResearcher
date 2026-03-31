from dataclasses import dataclass

import aiohttp
from loguru import logger


@dataclass
class SearchResult:
    title: str
    url: str
    description: str


class SearXNGClient:
    """Клиент для поиска через SearXNG JSON API."""

    def __init__(self, base_url: str) -> None:
        """Инициализирует клиент.

        Args:
            base_url: Базовый URL SearXNG (например, "http://localhost:8080").
        """
        self._base_url = base_url.rstrip("/")

    async def search(self, query: str, n_results: int = 20) -> list[SearchResult]:
        """Выполняет поиск и возвращает список результатов.

        Args:
            query: Поисковый запрос.
            n_results: Максимальное количество результатов.

        Returns:
            Список результатов с title, url, description.
        """
        params = {
            "q": query,
            "format": "json",
            "pageno": 1,
        }
        url = f"{self._base_url}/search"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                response.raise_for_status()
                data = await response.json()

        results: list[SearchResult] = []
        for item in data.get("results", [])[:n_results]:
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    description=item.get("content", ""),
                )
            )

        logger.debug(f"SearXNGClient: query={query!r} → {len(results)} results")
        return results
