"""Пайплайн выполнения исследования."""

import asyncio
import json
import random
import re

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.crud.model import get_model_by_id
from app.crud.model_output import create_model_output
from app.crud.research import update_research_stage, update_research_status
from app.crud.research_epoch import (
    create_research_epoch,
    get_research_epoch,
    update_research_epoch_body_finish,
    update_research_epoch_keywords,
    update_research_epoch_search_links,
)
from app.crud.scrapped_page import get_scrapped_page, upsert_scrapped_page
from app.models.model_output import ModelResponseStatus
from app.models.research import RESEARCH_STAGES, Research, ResearchStatus
from app.models.scrapped_page import ScrapeStatus
from app.services.llm_client import LLMClient
from app.services.page_cleaner import PageCleaner
from app.services.prompts import (
    SearchResultScores,
    SearchResultToScore,
    build_direction_messages,
    build_relevance_messages,
    build_search_keywords_messages,
    build_write_article_messages,
)
from app.services.searxng_client import SearXNGClient
from app.services.web_scraper import WebScraper

PAGE_CONTENT_MAX_CHARS = 8000

SEARCH_RESULTS_PER_KEYWORD = 20
RELEVANCE_BATCH_SIZE = 10
SEARCH_KEYWORDS_COUNT = 5
RELEVANCE_MAX_RETRIES = 5
SCRAPE_SEMAPHORE_LIMIT = 5


class ResearchPipeline:
    """Пайплайн выполнения одного исследования.

    Инкапсулирует все шаги: определение направления, генерацию поисковых
    запросов, поиск через SearXNG и оценку релевантности результатов.

    Args:
        session: Активная сессия БД.
        research: ORM-объект исследования.
        n_results: Количество результатов поиска на каждый keyword.
        relevance_batch_size: Размер батча при оценке релевантности.
        n_keywords: Количество поисковых запросов.
    """

    def __init__(
        self,
        session: AsyncSession,
        research: Research,
        n_results: int = SEARCH_RESULTS_PER_KEYWORD,
        relevance_batch_size: int = RELEVANCE_BATCH_SIZE,
        n_keywords: int = SEARCH_KEYWORDS_COUNT,
    ) -> None:
        self._session = session
        self._research = research
        self._fast = get_settings().app.fast
        self._n_results = n_results
        self._n_keywords = n_keywords
        self._relevance_batch_size = relevance_batch_size
        self._has_error = False

    async def run(self) -> None:
        """Запускает полный пайплайн исследования.

        Шаги выполняются последовательно; результат каждого шага передаётся
        в следующий.
        """
        try:
            direction = await self._step_direction_brainstorm()
        except Exception:
            await update_research_status(self._session, self._research, ResearchStatus.ERROR)
            return

        keywords = await self._step_search_keywords(direction)
        await self._step_search(keywords, direction)
        await self._step_scrape()
        await self._step_write_article(direction)
        if self._has_error:
            await update_research_status(self._session, self._research, ResearchStatus.ERROR)
        else:
            await update_research_stage(self._session, self._research, RESEARCH_STAGES["DONE"])
            await update_research_status(self._session, self._research, ResearchStatus.COMPLETE)

    # ------------------------------------------------------------------
    # Шаг 1: направление исследования
    # ------------------------------------------------------------------

    async def _step_direction_brainstorm(self) -> str:
        """Определяет направление исследования через LLM.

        Выполняет один вызов model_id_direction и сохраняет результат
        в model_outputs (epoch_id=0, step_type="direction_brainstorm"),
        затем создаёт запись ResearchEpoch.

        Returns:
            Ответ модели или пустую строку при ошибке / отсутствии модели.
        """
        research = self._research
        await update_research_stage(self._session, research, RESEARCH_STAGES["DIRECTION"])

        if research.model_id_direction is None:
            logger.warning(
                f"_step_direction_brainstorm: research {research.research_id} " f"has no model_id_direction, skipping"
            )
            return ""

        model = await get_model_by_id(self._session, research.model_id_direction)
        if model is None:
            logger.error(f"_step_direction_brainstorm: direction model " f"{research.model_id_direction} not found")
            return ""

        llm = LLMClient(
            model_name=model.model_api_model,
            base_url=model.model_base_url,
            api_key=model.model_key_api,
        )
        messages = build_direction_messages(query=research.research_name)

        status = ModelResponseStatus.COMPLETE
        output_payload: dict = {}
        direction_content: str | None = None

        caught_exc: Exception | None = None
        try:
            result = await llm.generate(messages)
            output_payload = {"content": result}
            direction_content = result
            logger.info(f"_step_direction_brainstorm: done (research_id={research.research_id})")
        except Exception as exc:
            status = ModelResponseStatus.ERROR
            output_payload = {"error": str(exc)}
            caught_exc = exc
            logger.exception(f"_step_direction_brainstorm: failed (research_id={research.research_id}): {exc}")

        await create_model_output(
            session=self._session,
            model_id=research.model_id_direction,
            research_id=research.research_id,
            epoch_id=0,
            step_type="direction_brainstorm",
            model_input={"messages": messages},
            model_output=output_payload,
            response_status=status,
        )

        await create_research_epoch(
            session=self._session,
            research_id=research.research_id,
            epoch_id=0,
            body_start={"query": research.research_name},
            body_finish={},
            direction_content=direction_content,
        )

        if caught_exc is not None:
            raise caught_exc

        return direction_content or ""

    # ------------------------------------------------------------------
    # Шаг 2: генерация поисковых запросов
    # ------------------------------------------------------------------

    async def _step_search_keywords(self, direction: str) -> list[str]:
        """Генерирует поисковые запросы для SearXNG.

        Вызывает model_id_search с темой и направлением исследования,
        парсит JSON-массив строк и сохраняет в research_search_keywords эпохи.

        Args:
            direction: Результат шага direction_brainstorm.

        Returns:
            Список поисковых запросов или пустой список при ошибке.
        """
        research = self._research
        if self._has_error:
            logger.debug(f"_step_search_keywords: skipping due to previous error (research_id={research.research_id})")
            return []

        await update_research_stage(self._session, research, RESEARCH_STAGES["KEYWORDS"])

        model = await get_model_by_id(self._session, research.model_id_search)
        if model is None:
            logger.error(f"_step_search_keywords: search model " f"{research.model_id_search} not found")
            return []

        llm = LLMClient(
            model_name=model.model_api_model,
            base_url=model.model_base_url,
            api_key=model.model_key_api,
        )
        messages = build_search_keywords_messages(
            query=research.research_name,
            direction=direction,
            n_keywords=self._n_keywords,
        )

        status = ModelResponseStatus.COMPLETE
        output_payload: dict = {}
        keywords: list[str] = []

        try:
            result = await llm.generate(messages)
            keywords = json.loads(result)
            if not isinstance(keywords, list):
                raise ValueError(f"expected JSON array, got {type(keywords).__name__}")
            keywords = [str(k) for k in keywords]
            output_payload = {"keywords": keywords}
            logger.info(
                f"_step_search_keywords: generated {len(keywords)} keywords " f"(research_id={research.research_id})"
            )
        except Exception as exc:
            status = ModelResponseStatus.ERROR
            output_payload = {"error": str(exc)}
            self._has_error = True
            logger.error(f"_step_search_keywords: failed " f"(research_id={research.research_id}): {exc}")

        await create_model_output(
            session=self._session,
            model_id=research.model_id_search,
            research_id=research.research_id,
            epoch_id=0,
            step_type="search_keywords",
            model_input={"messages": messages},
            model_output=output_payload,
            response_status=status,
        )

        if keywords:
            await update_research_epoch_keywords(
                session=self._session,
                research_id=research.research_id,
                epoch_id=0,
                keywords=keywords,
            )

        return keywords

    # ------------------------------------------------------------------
    # Шаг 3: поиск + оценка релевантности
    # ------------------------------------------------------------------

    async def _step_search(self, keywords: list[str], direction: str) -> None:
        """Выполняет поиск через SearXNG и оценивает релевантность результатов.

        Для каждого ключевого слова выполняет поиск, затем отправляет результаты
        батчами по self._relevance_batch_size в model_id_search для оценки
        релевантности по шкале 0.0–1.0 (10 критериев). Сохраняет топ-10 ссылок
        в эпохе.

        Args:
            keywords: Список поисковых запросов из шага search_keywords.
            direction: Результат шага direction_brainstorm (векторы исследования).
        """
        research = self._research
        if self._has_error:
            logger.debug(f"_step_search: skipping due to previous error (research_id={research.research_id})")
            return

        if not keywords:
            logger.warning(f"_step_search: no keywords, skipping (research_id={research.research_id})")
            return

        await update_research_stage(self._session, research, RESEARCH_STAGES["SEARCH"])

        settings = get_settings()
        client = SearXNGClient(base_url=settings.searxng.url)

        model = await get_model_by_id(self._session, research.model_id_search)
        llm: LLMClient | None = None
        if model is None:
            logger.warning(
                f"_step_search: search model {research.model_id_search} not found, "
                f"skipping relevance scoring (research_id={research.research_id})"
            )
        else:
            llm = LLMClient(
                model_name=model.model_api_model,
                base_url=model.model_base_url,
                api_key=model.model_key_api,
            )

        # (title, url, total_score) по всем keyword'ам
        scored_documents: list[tuple[str, str, float]] = []

        for keyword in keywords:
            try:
                results = await client.search(keyword, n_results=self._n_results)
                logger.debug(
                    f"_step_search: keyword={keyword!r} → {len(results)} results "
                    f"(research_id={research.research_id})"
                )
                for i, r in enumerate(results, 1):
                    logger.debug(f"  [{i}] title={r.title!r} url={r.url!r} " f"description={r.description!r}")
            except Exception as exc:
                logger.error(
                    f"_step_search: failed for keyword={keyword!r} " f"(research_id={research.research_id}): {exc}"
                )
                continue

            if llm is None:
                continue

            for batch_start in range(0, len(results), self._relevance_batch_size):
                batch = results[batch_start : batch_start + self._relevance_batch_size]
                batch_label = f"{batch_start + 1}-{batch_start + len(batch)}"

                if self._fast:
                    for idx, r in enumerate(batch):
                        points = [random.random() for _ in range(10)]
                        total = sum(points)
                        scored_documents.append((r.title, r.url, total))
                        logger.debug(
                            f"  [{batch_start + idx + 1}] fast/random total={total:.1f} "
                            f"(research_id={research.research_id})"
                        )
                    continue

                to_score = [SearchResultToScore(title=r.title, description=r.description) for r in batch]
                messages = build_relevance_messages(
                    query=research.research_name,
                    direction=direction,
                    keyword=keyword,
                    results=to_score,
                )
                for attempt in range(1, RELEVANCE_MAX_RETRIES + 1):
                    try:
                        raw = await llm.generate(messages)
                        scores = [SearchResultScores(**item) for item in json.loads(raw)]
                        logger.debug(
                            f"_step_search: relevance scores for keyword={keyword!r} "
                            f"batch={batch_label} attempt={attempt} "
                            f"(research_id={research.research_id})"
                        )
                        for idx, s in enumerate(scores):
                            result = batch[idx]
                            total = (
                                s.point_1
                                + s.point_2
                                + s.point_3
                                + s.point_4
                                + s.point_5
                                + s.point_6
                                + s.point_7
                                + s.point_8
                                + s.point_9
                                + s.point_10
                            )
                            scored_documents.append((result.title, result.url, total))
                            logger.debug(
                                f"  [{batch_start + idx + 1}] total={total:.1f} "
                                f"p1={s.point_1} p2={s.point_2} p3={s.point_3} "
                                f"p4={s.point_4} p5={s.point_5} p6={s.point_6} "
                                f"p7={s.point_7} p8={s.point_8} p9={s.point_9} "
                                f"p10={s.point_10}"
                            )
                        break
                    except Exception as exc:
                        logger.warning(
                            f"_step_search: relevance scoring attempt {attempt}/{RELEVANCE_MAX_RETRIES} "
                            f"failed for keyword={keyword!r} batch={batch_label} "
                            f"(research_id={research.research_id}): {exc}"
                        )
                        if attempt == RELEVANCE_MAX_RETRIES:
                            logger.error(
                                f"_step_search: relevance scoring gave up for "
                                f"keyword={keyword!r} batch={batch_label} "
                                f"(research_id={research.research_id})"
                            )

        if scored_documents:
            top10 = sorted(scored_documents, key=lambda x: x[2], reverse=True)[:10]
            logger.debug(f"_step_search: top-10 documents by total score " f"(research_id={research.research_id})")
            for rank, (title, url, total) in enumerate(top10, 1):
                logger.debug(f"  #{rank} total={total:.1f} title={title!r} url={url!r}")

            await update_research_epoch_search_links(
                session=self._session,
                research_id=research.research_id,
                epoch_id=0,
                links=[{"title": title, "url": url, "total_score": total} for title, url, total in top10],
            )

    # ------------------------------------------------------------------
    # Шаг 4: парсинг страниц
    # ------------------------------------------------------------------

    async def _step_scrape(self) -> None:
        """Скрапит топ-ссылки из эпохи и сохраняет результаты в scrapped_pages.

        Читает research_result_search_links из эпохи 0, загружает каждую
        страницу через WebScraper (до 5 одновременных запросов), очищает
        контент через PageCleaner и сохраняет в таблицу scrapped_pages.
        """
        research = self._research
        if self._has_error:
            logger.debug(f"_step_scrape: skipping due to previous error (research_id={research.research_id})")
            return

        epoch = await get_research_epoch(self._session, research.research_id, 0)
        if epoch is None or not epoch.research_result_search_links:
            logger.warning(f"_step_scrape: no links to scrape (research_id={research.research_id})")
            return

        await update_research_stage(self._session, research, RESEARCH_STAGES["SCRAPE"])

        links: list[dict] = epoch.research_result_search_links
        research_id = research.research_id  # кэшируем до цикла — сессия может сломаться
        logger.info(f"_step_scrape: scraping {len(links)} pages (research_id={research_id})")

        _BINARY_EXTENSIONS = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".tar", ".gz", ".rar")
        scraper = WebScraper()
        cleaner = PageCleaner()
        semaphore = asyncio.Semaphore(SCRAPE_SEMAPHORE_LIMIT)

        async def _fetch_one(link: dict) -> tuple[str, str | None, str | None]:
            url: str = link["url"]
            if url.lower().split("?")[0].endswith(_BINARY_EXTENSIONS):
                logger.debug(f"_step_scrape: skipping binary URL {url!r}")
                return url, None, None
            async with semaphore:
                raw_html = await scraper.fetch(url)
            if raw_html is None:
                logger.warning(f"_step_scrape: failed to fetch {url!r}")
                return url, None, None
            clean_text = cleaner.clean(raw_html)
            return url, raw_html, clean_text

        fetched = await asyncio.gather(*[_fetch_one(link) for link in links])

        for url, raw_html, clean_text in fetched:
            try:
                raw_content = raw_html.replace("\x00", "") if raw_html else ""
                clean_content = clean_text.replace("\x00", "") if clean_text else None
                await upsert_scrapped_page(
                    session=self._session,
                    url=url,
                    raw_content=raw_content,
                    clean_content=clean_content,
                    status=ScrapeStatus.SUCCESS if raw_html is not None else ScrapeStatus.ERROR,
                )
                if raw_html is not None:
                    logger.debug(
                        f"_step_scrape: saved {url!r} (clean_len={len(clean_content) if clean_content else 0})"
                    )
            except Exception as exc:
                self._has_error = True
                await self._session.rollback()
                logger.error(f"_step_scrape: failed to save {url!r} (research_id={research_id}): {exc}")

        if not self._has_error:
            logger.info(f"_step_scrape: done (research_id={research_id})")

    # ------------------------------------------------------------------
    # Шаг 5: написание итоговой статьи
    # ------------------------------------------------------------------

    async def _step_write_article(self, direction: str) -> None:
        """Пишет итоговую исследовательскую статью на основе собранных материалов.

        Читает скрапнутые страницы для топ-ссылок эпохи 0, формирует контекст,
        вызывает model_id_answer для генерации статьи, обрабатывает результат
        через _format_as_html и сохраняет в research_body_finish эпохи 0.

        Args:
            direction: Результат шага direction_brainstorm (векторы исследования).
        """
        research = self._research
        if self._has_error:
            logger.debug(f"_step_write_article: skipping due to previous error (research_id={research.research_id})")
            return

        epoch = await get_research_epoch(self._session, research.research_id, 0)
        if epoch is None:
            logger.warning(f"_step_write_article: epoch 0 not found (research_id={research.research_id})")
            return

        await update_research_stage(self._session, research, RESEARCH_STAGES["WRITE"])

        model = await get_model_by_id(self._session, research.model_id_answer)
        if model is None:
            logger.error(f"_step_write_article: answer model {research.model_id_answer} not found")
            self._has_error = True
            return

        links: list[dict] = epoch.research_result_search_links or []
        pages_content: list[dict] = []
        for link in links:
            url: str = link["url"]
            page = await get_scrapped_page(self._session, url)
            if page is not None and page.page_clean_content:
                content = page.page_clean_content[:PAGE_CONTENT_MAX_CHARS]
                pages_content.append({"url": url, "content": content})

        query: str = (epoch.research_body_start or {}).get("query", research.research_name)
        messages = build_write_article_messages(
            query=query,
            direction=direction or "",
            pages_content=pages_content,
        )

        llm = LLMClient(
            model_name=model.model_api_model,
            base_url=model.model_base_url,
            api_key=model.model_key_api,
        )

        status = ModelResponseStatus.COMPLETE
        output_payload: dict = {}
        segments: list[dict] = []

        try:
            raw = await llm.generate(messages)
            segments = self._format_as_segments(raw)
            output_payload = {"segments": segments}
            logger.info(f"_step_write_article: done (research_id={research.research_id})")
        except Exception as exc:
            status = ModelResponseStatus.ERROR
            output_payload = {"error": str(exc)}
            self._has_error = True
            logger.exception(f"_step_write_article: failed (research_id={research.research_id}): {exc}")

        await create_model_output(
            session=self._session,
            model_id=research.model_id_answer,
            research_id=research.research_id,
            epoch_id=0,
            step_type="write_article",
            model_input={"messages": messages},
            model_output=output_payload,
            response_status=status,
        )

        if segments:
            await update_research_epoch_body_finish(
                session=self._session,
                research_id=research.research_id,
                epoch_id=0,
                body_finish={"segments": segments},
            )

    @staticmethod
    def _apply_inline_markdown(text: str) -> str:
        """Заменяет inline Markdown-разметку на HTML-теги <b> и <i>.

        Args:
            text: Строка с возможной inline-разметкой.

        Returns:
            Строка с заменёнными тегами <b> и <i>.
        """
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
        text = re.sub(r"_(.+?)_", r"<i>\1</i>", text)
        return text

    @staticmethod
    def _format_as_segments(text: str) -> list[dict]:
        """Конвертирует Markdown-текст в список сегментов с типом и контентом.

        Args:
            text: Текст в Markdown-разметке от LLM.

        Returns:
            Список словарей с ключами type, content, is_like, is_dislike, comment.
            Поддерживаемые типы: h1, h2, h3, p, li.
            Inline-разметка **bold** и *italic*/_italic_ конвертируется в <b>/<i>.
        """
        apply = ResearchPipeline._apply_inline_markdown

        def make_segment(tag: str, content: str) -> dict:
            return {
                "type": tag,
                "content": apply(content),
                "is_like": False,
                "is_dislike": False,
                "comment": None,
            }

        lines = text.splitlines()
        segments: list[dict] = []
        paragraph_lines: list[str] = []

        def flush_paragraph() -> None:
            if paragraph_lines:
                content = " ".join(paragraph_lines).strip()
                if content:
                    segments.append(make_segment("p", content))
                paragraph_lines.clear()

        for line in lines:
            stripped = line.strip()
            if not stripped:
                flush_paragraph()
                continue
            if stripped.startswith("### "):
                flush_paragraph()
                segments.append(make_segment("h3", stripped[4:].strip()))
            elif stripped.startswith("## "):
                flush_paragraph()
                segments.append(make_segment("h2", stripped[3:].strip()))
            elif stripped.startswith("# "):
                flush_paragraph()
                segments.append(make_segment("h1", stripped[2:].strip()))
            elif stripped.startswith(("- ", "* ", "• ")):
                flush_paragraph()
                segments.append(make_segment("li", stripped[2:].strip()))
            else:
                paragraph_lines.append(stripped)

        flush_paragraph()
        return segments
