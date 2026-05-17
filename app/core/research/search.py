"""Шаг поиска: SearXNG → скрейпинг → очистка HTML до набора рабочих ссылок."""

import asyncio
import re
from urllib.parse import urlparse

import trafilatura
from loguru import logger

from app.config import get_settings
from app.crud.research import update_research_search_links, update_research_stage
from app.crud.scrapped_page import upsert_scrapped_page
from app.models.research import RESEARCH_STAGES, Research
from app.models.scrapped_page import ScrapeStatus
from app.services.searxng_client import SearXNGClient
from app.services.web_scraper import WebScraper

from .base import ResearchStepBase

CONSECUTIVE_ERRORS_LIMIT = 3
SEARCH_MAX_PAGES = 5
_BINARY_EXTENSIONS = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".tar", ".gz", ".rar")
_DOMAIN_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}$")


def _is_binary_url(url: str) -> bool:
    """Проверяет, ведёт ли URL на бинарный файл, который мы не умеем парсить."""
    return url.lower().split("?")[0].endswith(_BINARY_EXTENSIONS)


def _parse_areas(areas_str: str | None) -> tuple[list[str], list[str]]:
    """Разбирает строку с источниками на конкретные URL и домены.

    Args:
        areas_str: Строка вида "https://site.com/path, domain.com, слово" (через запятую).

    Returns:
        Кортеж (specific_urls, domains): конкретные страницы и домены для site:-фильтра.
    """
    if not areas_str:
        return [], []

    specific_urls: list[str] = []
    domains: list[str] = []

    for raw in areas_str.split(","):
        item = raw.strip()
        if not item:
            continue
        if item.startswith(("http://", "https://")):
            parsed = urlparse(item)
            if parsed.path.rstrip("/"):
                specific_urls.append(item)
            else:
                domains.append(parsed.netloc)
        elif _DOMAIN_RE.match(item):
            domains.append(item)

    return specific_urls, domains


class SearchResearchStep(ResearchStepBase):
    """Поиск через SearXNG, скрейпинг и очистка HTML до набора top_n рабочих ссылок."""

    async def execute(self) -> None:
        """Собирает settings_n_top_search_results рабочих ссылок на каждое ключевое слово.

        Рабочая ссылка — это та, для которой удалось скачать HTML и trafilatura
        извлекла непустой текст. Если на странице SearXNG не хватает рабочих
        результатов, идём дальше по страницам до SEARCH_MAX_PAGES.

        Ключевые слова подтягиваются из research.research_search_keywords.
        """
        research: Research = self._research
        keywords: list[str] = research.research_search_keywords or []

        if not keywords:
            logger.warning(f"{self._log_extra()} SearchResearchStep: no keywords, skipping")
            self.has_error = True
            return

        await update_research_stage(self._session, research, RESEARCH_STAGES["SEARCH"])

        urls = await self._collect_working_urls(keywords)

        if not urls:
            logger.warning(f"{self._log_extra()} SearchResearchStep: no working URLs collected")
            self.has_error = True
            return

        await update_research_search_links(
            session=self._session,
            research=self._research,
            links=[{"url": url} for url in urls],
        )
        logger.info(f"{self._log_extra()} SearchResearchStep: collected {len(urls)} working URLs")

    async def _collect_working_urls(self, keywords: list[str]) -> list[str]:
        """Собирает уникальные рабочие URL по всем ключевым словам.

        Args:
            keywords: Поисковые запросы.

        Returns:
            Список URL, для которых scrapped_pages.status == SUCCESS, без дубликатов.

        Raises:
            Exception: Если SearXNG провалился CONSECUTIVE_ERRORS_LIMIT раз подряд.
        """
        client = SearXNGClient(base_url=get_settings().searxng.url)
        scraper = WebScraper()
        semaphore = asyncio.Semaphore(self._research.settings_n_async_parse)

        search_specific, search_domains = _parse_areas(self._research.settings_search_areas)
        _, exclude_domains = _parse_areas(self._research.settings_exclude_search_areas)

        site_include = " OR ".join(f"site:{d}" for d in search_domains)
        site_exclude = " ".join(f"-site:{d}" for d in exclude_domains)

        top_n: int = self._research.settings_n_top_search_results
        seen: set[str] = set()
        working_urls: list[str] = []

        forced_candidates: list[str] = []
        for u in search_specific:
            if _is_binary_url(u):
                logger.debug(f"{self._log_extra()} SearchResearchStep: skipping binary URL from search areas {u!r}")
                continue
            if u in seen:
                continue
            seen.add(u)
            forced_candidates.append(u)
        if forced_candidates:
            kept = await self._fetch_and_keep(forced_candidates, semaphore, scraper, limit=None)
            working_urls.extend(kept)
            logger.debug(
                f"{self._log_extra()} SearchResearchStep: forced URLs → "
                f"{len(kept)}/{len(forced_candidates)} working"
            )

        consecutive_errors = 0
        for keyword in keywords:
            query = keyword
            if site_include:
                query = f"{query} ({site_include})"
            if site_exclude:
                query = f"{query} {site_exclude}"

            try:
                kept = await self._collect_for_keyword(
                    client=client,
                    scraper=scraper,
                    semaphore=semaphore,
                    keyword=keyword,
                    query=query,
                    top_n=top_n,
                    seen=seen,
                )
            except Exception as exc:
                consecutive_errors += 1
                logger.error(
                    f"{self._log_extra()} SearchResearchStep: search failed for keyword={keyword!r} "
                    f"(consecutive_errors={consecutive_errors}): {exc}"
                )
                if consecutive_errors >= CONSECUTIVE_ERRORS_LIMIT:
                    self.has_error = True
                    raise
                continue

            consecutive_errors = 0
            working_urls.extend(kept)
            logger.debug(
                f"{self._log_extra()} SearchResearchStep: keyword={keyword!r} → " f"{len(kept)}/{top_n} working"
            )

        return working_urls

    async def _collect_for_keyword(
        self,
        *,
        client: SearXNGClient,
        scraper: WebScraper,
        semaphore: asyncio.Semaphore,
        keyword: str,
        query: str,
        top_n: int,
        seen: set[str],
    ) -> list[str]:
        """Идёт по страницам SearXNG, пока не наберётся top_n рабочих ссылок.

        Args:
            client: Клиент SearXNG.
            scraper: HTTP-скрейпер.
            semaphore: Ограничивает количество одновременных fetch.
            keyword: Ключевое слово (для логирования).
            query: Готовый поисковый запрос с site:-фильтрами.
            top_n: Сколько рабочих ссылок нужно набрать.
            seen: Множество уже виденных URL (обновляется на месте).

        Returns:
            До top_n рабочих URL в порядке ранжирования SearXNG.

        Raises:
            Exception: Если SearXNG отвечает ошибкой (пробрасывается наверх).
        """
        kept: list[str] = []
        for page in range(1, SEARCH_MAX_PAGES + 1):
            if len(kept) >= top_n:
                break

            results = await client.search(query, n_results=top_n * 5, page=page)
            if not results:
                break

            candidates: list[str] = []
            for r in results:
                if _is_binary_url(r.url) or r.url in seen:
                    continue
                seen.add(r.url)
                candidates.append(r.url)

            if not candidates:
                continue

            need = top_n - len(kept)
            new_working = await self._fetch_and_keep(candidates, semaphore, scraper, limit=need)
            kept.extend(new_working)
            logger.debug(
                f"{self._log_extra()} SearchResearchStep: keyword={keyword!r} page={page} → "
                f"{len(new_working)}/{len(candidates)} working (need={need})"
            )

        return kept[:top_n]

    async def _fetch_and_keep(
        self,
        urls: list[str],
        semaphore: asyncio.Semaphore,
        scraper: WebScraper,
        limit: int | None,
    ) -> list[str]:
        """Параллельно скачивает и очищает страницы, сохраняет в scrapped_pages.

        Параллелится только сетевой fetch (через semaphore). Извлечение текста и
        запись в БД выполняются последовательно — AsyncSession не безопасен для
        конкурентных операций.

        Args:
            urls: Кандидаты на обработку, в порядке приоритета.
            semaphore: Семафор для ограничения конкурентности fetch.
            scraper: HTTP-скрейпер.
            limit: Сколько максимум рабочих URL вернуть. None — все.

        Returns:
            URL'ы со SUCCESS-статусом в порядке `urls`. Не более limit (если задан).
        """

        async def _fetch(url: str) -> tuple[str, str | None]:
            async with semaphore:
                raw = await scraper.fetch(url)
            return url, raw

        fetched = await asyncio.gather(*[_fetch(u) for u in urls])

        kept: list[str] = []
        for url, raw_html in fetched:
            if raw_html is None:
                await upsert_scrapped_page(
                    session=self._session,
                    url=url,
                    raw_content="",
                    clean_content=None,
                    status=ScrapeStatus.ERROR,
                )
                logger.debug(f"{self._log_extra()} SearchResearchStep: fetch failed {url!r}")
                continue

            raw_content = raw_html.replace("\x00", "")
            try:
                clean_content = self._extract_clean_text(raw_content)
            except Exception as exc:
                logger.warning(f"{self._log_extra()} SearchResearchStep: clean failed for {url!r}: {exc}")
                clean_content = None

            if not clean_content:
                await upsert_scrapped_page(
                    session=self._session,
                    url=url,
                    raw_content=raw_content,
                    clean_content=None,
                    status=ScrapeStatus.ERROR,
                )
                logger.debug(f"{self._log_extra()} SearchResearchStep: empty clean for {url!r}")
                continue

            clean_safe = clean_content.replace("\x00", "")
            await upsert_scrapped_page(
                session=self._session,
                url=url,
                raw_content=raw_content,
                clean_content=clean_safe,
                status=ScrapeStatus.SUCCESS,
            )
            logger.debug(f"{self._log_extra()} SearchResearchStep: SUCCESS {url!r} (clean_len={len(clean_safe)})")

            if limit is None or len(kept) < limit:
                kept.append(url)

        return kept

    @staticmethod
    def _extract_clean_text(html: str) -> str | None:
        """Извлекает чистый текст из HTML через trafilatura.

        Args:
            html: Сырой HTML-контент страницы.

        Returns:
            Чистый текст или None если извлечение не удалось.
        """
        return trafilatura.extract(html, include_formatting=False, no_fallback=False)
