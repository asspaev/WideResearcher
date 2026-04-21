"""Шаг поиска: SearXNG → скрейпинг → очистка HTML."""

import asyncio

import trafilatura
from loguru import logger

from app.config import get_settings
from app.crud.research import update_research_search_links, update_research_stage
from app.crud.scrapped_page import get_scrapped_page, upsert_scrapped_page
from app.models.research import RESEARCH_STAGES, Research
from app.models.scrapped_page import ScrapeStatus
from app.services.searxng_client import SearXNGClient
from app.services.web_scraper import WebScraper

from .base import ResearchStepBase

CONSECUTIVE_ERRORS_LIMIT = 3
_BINARY_EXTENSIONS = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".tar", ".gz", ".rar")


class SearchResearchStep(ResearchStepBase):
    """Поиск через SearXNG, скрейпинг и очистка HTML найденных страниц."""

    async def execute(self) -> None:
        """Ищет страницы по ключевым словам, скрейпит и очищает HTML.

        Ключевые слова подтягиваются из research.research_search_keywords.
        """
        research: Research = self._research
        keywords: list[str] = research.research_search_keywords or []

        if not keywords:
            logger.warning(f"{self._log_extra()} SearchResearchStep: no keywords, skipping")
            self.has_error = True
            return

        await update_research_stage(self._session, research, RESEARCH_STAGES["SEARCH"])

        urls = await self._search_top_pages(keywords)
        await self._parse_pages(urls)
        await self._clean_pages(urls)

    async def _search_top_pages(self, keywords: list[str]) -> list[str]:
        """Ищет research.settings_n_top_pages страниц через SearXNG для каждого ключевого слова.

        Args:
            keywords: Список поисковых запросов.

        Returns:
            Список уникальных URL из результатов поиска.

        Raises:
            Exception: Если произошло CONSECUTIVE_ERRORS_LIMIT ошибок подряд.
        """
        client = SearXNGClient(base_url=get_settings().searxng.url)
        urls: list[str] = []
        seen: set[str] = set()
        consecutive_errors = 0

        for keyword in keywords:
            try:
                results = await client.search(keyword, n_results=self._research.settings_n_top_pages)
                consecutive_errors = 0
                for r in results:
                    if r.url not in seen:
                        seen.add(r.url)
                        urls.append(r.url)
                logger.debug(f"{self._log_extra()} SearchResearchStep: keyword={keyword!r} → {len(results)} results")
            except Exception as exc:
                consecutive_errors += 1
                logger.error(
                    f"{self._log_extra()} SearchResearchStep: search failed for keyword={keyword!r} "
                    f"(consecutive_errors={consecutive_errors}): {exc}"
                )
                if consecutive_errors >= CONSECUTIVE_ERRORS_LIMIT:
                    self.has_error = True
                    raise

        if urls:
            await update_research_search_links(
                session=self._session,
                research=self._research,
                links=[{"url": url} for url in urls],
            )
            logger.info(f"{self._log_extra()} SearchResearchStep: found {len(urls)} unique URLs")

        return urls

    async def _parse_pages(self, urls: list[str]) -> None:
        """Асинхронно скрейпит страницы с ограничением конкурентности research.settings_n_async_parse.

        Сохраняет в scrapped_pages: IN_PROGRESS — если успешно спаршено,
        ERROR — если не удалось.

        Args:
            urls: Список URL для скрейпинга.
        """
        scraper = WebScraper()
        semaphore = asyncio.Semaphore(self._research.settings_n_async_parse)

        async def _fetch_one(url: str) -> tuple[str, str | None]:
            if url.lower().split("?")[0].endswith(_BINARY_EXTENSIONS):
                logger.debug(f"{self._log_extra()} SearchResearchStep: skipping binary URL {url!r}")
                return url, None
            async with semaphore:
                raw_html = await scraper.fetch(url)
            if raw_html is None:
                logger.warning(f"{self._log_extra()} SearchResearchStep: failed to fetch {url!r}")
            return url, raw_html

        fetched = await asyncio.gather(*[_fetch_one(url) for url in urls])

        for url, raw_html in fetched:
            if raw_html is not None:
                status = ScrapeStatus.IN_PROGRESS
                raw_content = raw_html.replace("\x00", "")
            else:
                status = ScrapeStatus.ERROR
                raw_content = ""
            await upsert_scrapped_page(
                session=self._session,
                url=url,
                raw_content=raw_content,
                clean_content=None,
                status=status,
            )
            logger.debug(f"{self._log_extra()} SearchResearchStep: parsed {url!r} → {status.value}")

    async def _clean_pages(self, urls: list[str]) -> None:
        """Очищает HTML каждой успешно спаршенной страницы.

        Пропускает страницы со статусом ERROR. Обновляет статус в scrapped_pages:
        SUCCESS — если очистка прошла успешно, ERROR — если нет.

        Args:
            urls: Список URL страниц для очистки.

        Raises:
            Exception: Если во время очистки HTML возникла ошибка.
        """
        for url in urls:
            page = await get_scrapped_page(self._session, url)
            if page is None or page.page_scrapped_status == ScrapeStatus.ERROR:
                continue

            try:
                clean_content = self._extract_clean_text(page.page_raw_content)
            except Exception as exc:
                logger.error(f"{self._log_extra()} SearchResearchStep: failed to clean {url!r}: {exc}")
                await upsert_scrapped_page(
                    session=self._session,
                    url=url,
                    raw_content=page.page_raw_content,
                    clean_content=None,
                    status=ScrapeStatus.ERROR,
                )
                self.has_error = True
                raise

            clean_content_safe = clean_content.replace("\x00", "") if clean_content else None
            await upsert_scrapped_page(
                session=self._session,
                url=url,
                raw_content=page.page_raw_content,
                clean_content=clean_content_safe,
                status=ScrapeStatus.SUCCESS,
            )
            logger.debug(
                f"{self._log_extra()} SearchResearchStep: cleaned {url!r} "
                f"(clean_len={len(clean_content_safe) if clean_content_safe else 0})"
            )

    @staticmethod
    def _extract_clean_text(html: str) -> str | None:
        """Извлекает чистый текст из HTML через trafilatura.

        Args:
            html: Сырой HTML-контент страницы.

        Returns:
            Чистый текст или None если извлечение не удалось.
        """
        return trafilatura.extract(html, include_formatting=False, no_fallback=False)
