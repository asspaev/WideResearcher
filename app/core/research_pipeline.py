"""Research execution pipeline."""

import asyncio
import functools
import inspect
import json
import random
import re
import time

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.crud.model import get_model_by_id
from app.crud.model_output import create_model_output
from app.crud.page_summary import get_page_summaries_by_research, upsert_page_summary
from app.crud.research import (
    update_research_body_finish,
    update_research_body_start,
    update_research_direction_content,
    update_research_duration,
    update_research_search_keywords,
    update_research_search_links,
    update_research_stage,
    update_research_status,
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
    build_plan_structure_messages,
    build_relevance_messages,
    build_search_keywords_messages,
    build_summarize_page_messages,
    build_write_article_messages,
    build_write_chapter_messages,
)
from app.services.searxng_client import SearXNGClient
from app.services.web_scraper import WebScraper

PAGE_CONTENT_MAX_CHARS = 8000
WRITTEN_SO_FAR_MAX_CHARS = 40_000  # ~10k tokens

SEARCH_RESULTS_PER_KEYWORD = 20
RELEVANCE_BATCH_SIZE = 10
SEARCH_KEYWORDS_COUNT = 5
RELEVANCE_MAX_RETRIES = 5
SCRAPE_SEMAPHORE_LIMIT = 5


def _fmt_param(value: object) -> str:
    """Returns a compact string representation of a parameter value for logging."""
    if isinstance(value, list):
        return f"[{len(value)} items]"
    if isinstance(value, str) and len(value) > 80:
        return repr(value[:80]) + "..."
    return repr(value)


def pipeline_step(step_number: int, step_name: str):
    """Decorator that logs START/DONE/FAILED with timing and input parameters.

    Wraps an async pipeline step method. Logs:
    - START: step number, name, user_id, research_id, all parameters.
    - DONE: step number, name, research_id, elapsed time.
    - FAILED: step number, name, research_id, elapsed time (then re-raises).

    Args:
        step_number: Sequential step number shown in logs.
        step_name: Short uppercase label for the step (e.g. "DIRECTION").
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self: "ResearchPipeline", *args, **kwargs):
            research = self._research

            sig = inspect.signature(func)
            bound = sig.bind(self, *args, **kwargs)
            bound.apply_defaults()
            # skip 'self' when building params string
            params_str = " | ".join(f"{name}={_fmt_param(val)}" for name, val in list(bound.arguments.items())[1:])

            logger.info(
                f"[STEP {step_number} | {step_name}] START"
                f" | user_id={research.user_id}"
                f" | research_id={research.research_id}" + (f" | {params_str}" if params_str else "")
            )
            t0 = time.monotonic()
            try:
                result = await func(self, *args, **kwargs)
            except Exception:
                elapsed = time.monotonic() - t0
                logger.info(
                    f"[STEP {step_number} | {step_name}] FAILED"
                    f" | research_id={research.research_id}"
                    f" | elapsed={elapsed:.2f}s"
                )
                raise
            elapsed = time.monotonic() - t0
            logger.info(
                f"[STEP {step_number} | {step_name}] DONE"
                f" | research_id={research.research_id}"
                f" | elapsed={elapsed:.2f}s"
            )
            return result

        return wrapper

    return decorator


class ResearchPipeline:
    """Pipeline for executing a single research.

    Encapsulates all steps: direction brainstorm, search keyword generation,
    SearXNG search with relevance scoring, page scraping, summarization,
    and article writing.

    Args:
        session: Active database session.
        research: Research ORM object.
        n_results: Number of search results per keyword.
        relevance_batch_size: Batch size for relevance scoring.
        n_keywords: Number of search queries to generate.
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
        """Runs the full research pipeline.

        Steps execute sequentially; each step's result is passed to the next.
        """
        pipeline_start = time.monotonic()
        try:
            direction = await self._step_direction_brainstorm()
        except Exception:
            await update_research_status(self._session, self._research, ResearchStatus.ERROR)
            return

        keywords = await self._step_search_keywords(direction)
        await self._step_search(keywords, direction)
        await self._step_scrape()
        await self._step_summarize_pages(direction)
        structure = await self._step_plan_structure(direction)
        await self._step_write_article(direction, structure)

        duration_seconds = int(time.monotonic() - pipeline_start)
        await update_research_duration(
            session=self._session,
            research=self._research,
            duration_seconds=duration_seconds,
        )

        if self._has_error:
            await update_research_status(self._session, self._research, ResearchStatus.ERROR)
        else:
            await update_research_stage(self._session, self._research, RESEARCH_STAGES["DONE"])
            await update_research_status(self._session, self._research, ResearchStatus.COMPLETE)

    # ------------------------------------------------------------------
    # Step 1: research direction
    # ------------------------------------------------------------------

    @pipeline_step(1, "DIRECTION")
    async def _step_direction_brainstorm(self) -> str:
        """Determines the research direction via LLM.

        Makes a single call to model_id_direction and saves the result
        to model_outputs (step_type="direction_brainstorm"),
        then saves body_start and direction_content to the research record.

        Returns:
            Model response or empty string on error / missing model.
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
            step_type="direction_brainstorm",
            model_input={"messages": messages},
            model_output=output_payload,
            response_status=status,
        )

        await update_research_body_start(
            session=self._session,
            research=research,
            body_start={"query": research.research_name},
        )
        await update_research_direction_content(
            session=self._session,
            research=research,
            direction_content=direction_content,
        )

        if caught_exc is not None:
            raise caught_exc

        return direction_content or ""

    # ------------------------------------------------------------------
    # Step 2: search keyword generation
    # ------------------------------------------------------------------

    @pipeline_step(2, "KEYWORDS")
    async def _step_search_keywords(self, direction: str) -> list[str]:
        """Generates search queries for SearXNG.

        Calls model_id_search with the research topic and direction,
        parses a JSON array of strings, and saves to the epoch's
        research_search_keywords field.

        Args:
            direction: Result of the direction_brainstorm step.

        Returns:
            List of search queries or empty list on error.
        """
        research = self._research
        if self._has_error:
            logger.debug(f"_step_search_keywords: skipping due to previous error (research_id={research.research_id})")
            return []

        await update_research_stage(self._session, research, RESEARCH_STAGES["KEYWORDS"])

        model = await get_model_by_id(self._session, research.model_id_search)
        if model is None:
            logger.error(f"_step_search_keywords: search model {research.model_id_search} not found")
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
            logger.error(f"_step_search_keywords: failed (research_id={research.research_id}): {exc}")

        await create_model_output(
            session=self._session,
            model_id=research.model_id_search,
            research_id=research.research_id,
            step_type="search_keywords",
            model_input={"messages": messages},
            model_output=output_payload,
            response_status=status,
        )

        if keywords:
            await update_research_search_keywords(
                session=self._session,
                research=research,
                keywords=keywords,
            )

        return keywords

    # ------------------------------------------------------------------
    # Step 3: search + relevance scoring
    # ------------------------------------------------------------------

    @pipeline_step(3, "SEARCH")
    async def _step_search(self, keywords: list[str], direction: str) -> None:
        """Searches via SearXNG and scores result relevance.

        For each keyword performs a search, then sends results in batches
        of self._relevance_batch_size to model_id_search for relevance
        scoring on a 0.0–1.0 scale (10 criteria). Saves the top-10 links
        to the epoch.

        Args:
            keywords: Search queries from the search_keywords step.
            direction: Result of the direction_brainstorm step.
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

        # (title, url, total_score) across all keywords
        scored_documents: list[tuple[str, str, float]] = []

        for keyword in keywords:
            try:
                results = await client.search(keyword, n_results=self._n_results)
                logger.debug(
                    f"_step_search: keyword={keyword!r} → {len(results)} results "
                    f"(research_id={research.research_id})"
                )
                for i, r in enumerate(results, 1):
                    logger.debug(f"  [{i}] title={r.title!r} url={r.url!r} description={r.description!r}")
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
                        await create_model_output(
                            session=self._session,
                            model_id=research.model_id_search,
                            research_id=research.research_id,
                            step_type="relevance_scoring",
                            model_input={"messages": messages, "keyword": keyword, "batch": batch_label},
                            model_output={"raw": raw},
                            response_status=ModelResponseStatus.COMPLETE,
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
                            await create_model_output(
                                session=self._session,
                                model_id=research.model_id_search,
                                research_id=research.research_id,
                                step_type="relevance_scoring",
                                model_input={"messages": messages, "keyword": keyword, "batch": batch_label},
                                model_output={"error": str(exc)},
                                response_status=ModelResponseStatus.ERROR,
                            )

        if scored_documents:
            top10 = sorted(scored_documents, key=lambda x: x[2], reverse=True)[:10]
            logger.debug(f"_step_search: top-10 documents by total score (research_id={research.research_id})")
            for rank, (title, url, total) in enumerate(top10, 1):
                logger.debug(f"  #{rank} total={total:.1f} title={title!r} url={url!r}")

            await update_research_search_links(
                session=self._session,
                research=research,
                links=[{"title": title, "url": url, "total_score": total} for title, url, total in top10],
            )

    # ------------------------------------------------------------------
    # Step 4: page scraping
    # ------------------------------------------------------------------

    @pipeline_step(4, "SCRAPE")
    async def _step_scrape(self) -> None:
        """Scrapes top links from the epoch and saves results to scrapped_pages.

        Reads research_result_search_links from epoch 0, fetches each page
        via WebScraper (up to 5 concurrent requests), cleans content via
        PageCleaner, and saves to the scrapped_pages table.
        """
        research = self._research
        if self._has_error:
            logger.debug(f"_step_scrape: skipping due to previous error (research_id={research.research_id})")
            return

        if not research.research_result_search_links:
            logger.warning(f"_step_scrape: no links to scrape (research_id={research.research_id})")
            return

        await update_research_stage(self._session, research, RESEARCH_STAGES["SCRAPE"])

        links: list[dict] = research.research_result_search_links
        research_id = research.research_id  # cache before loop — session may break
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
    # Step 5: page summarization
    # ------------------------------------------------------------------

    @pipeline_step(5, "SUMMARIZE")
    async def _step_summarize_pages(self, direction: str) -> None:
        """Generates a summary for each scraped page in the current epoch.

        Reads top links from epoch 0, calls model_id_answer for each page
        with content to generate a summary, and saves the result to
        page_summaries.

        Args:
            direction: Result of the direction_brainstorm step.
        """
        research = self._research
        if self._has_error:
            logger.debug(f"_step_summarize_pages: skipping due to previous error (research_id={research.research_id})")
            return

        if not research.research_result_search_links:
            logger.warning(f"_step_summarize_pages: no links found (research_id={research.research_id})")
            return

        await update_research_stage(self._session, research, RESEARCH_STAGES["SUMMARIZE"])

        model = await get_model_by_id(self._session, research.model_id_answer)
        if model is None:
            logger.error(f"_step_summarize_pages: answer model {research.model_id_answer} not found")
            self._has_error = True
            return

        llm = LLMClient(
            model_name=model.model_api_model,
            base_url=model.model_base_url,
            api_key=model.model_key_api,
        )

        query: str = (research.research_body_start or {}).get("query", research.research_name)
        links: list[dict] = research.research_result_search_links or []

        for link in links:
            url: str = link["url"]
            page = await get_scrapped_page(self._session, url)
            if page is None or not page.page_clean_content:
                logger.debug(f"_step_summarize_pages: no content for {url!r}, skipping")
                continue

            content = page.page_clean_content[:PAGE_CONTENT_MAX_CHARS]
            messages = build_summarize_page_messages(
                query=query,
                direction=direction or "",
                page_content=content,
            )

            try:
                summary = await llm.generate(messages)
                await upsert_page_summary(
                    session=self._session,
                    page_url=url,
                    research_id=research.research_id,
                    page_summary=summary,
                )
                await create_model_output(
                    session=self._session,
                    model_id=research.model_id_answer,
                    research_id=research.research_id,
                    step_type="summarize_page",
                    model_input={"messages": messages},
                    model_output={"url": url, "summary": summary},
                    response_status=ModelResponseStatus.COMPLETE,
                )
                logger.debug(
                    f"_step_summarize_pages: summarized {url!r} "
                    f"(summary_len={len(summary)} research_id={research.research_id})"
                )
            except Exception as exc:
                logger.error(
                    f"_step_summarize_pages: failed for {url!r} " f"(research_id={research.research_id}): {exc}"
                )
                await create_model_output(
                    session=self._session,
                    model_id=research.model_id_answer,
                    research_id=research.research_id,
                    step_type="summarize_page",
                    model_input={"messages": messages},
                    model_output={"url": url, "error": str(exc)},
                    response_status=ModelResponseStatus.ERROR,
                )

        logger.info(f"_step_summarize_pages: done (research_id={research.research_id})")

    # ------------------------------------------------------------------
    # Step 6: research structure planning
    # ------------------------------------------------------------------

    @pipeline_step(6, "STRUCTURE")
    async def _step_plan_structure(self, direction: str) -> str:
        """Plans the hierarchical outline of the research article.

        Reads page_summaries for epoch 0, builds context, calls
        model_id_answer to generate a Markdown outline (h1/h2/h3),
        and saves the result to model_outputs.

        Args:
            direction: Result of the direction_brainstorm step.

        Returns:
            Structure string (Markdown outline) or empty string on error.
        """
        research = self._research
        if self._has_error:
            logger.debug(f"_step_plan_structure: skipping due to previous error (research_id={research.research_id})")
            return ""

        await update_research_stage(self._session, research, RESEARCH_STAGES["STRUCTURE"])

        model = await get_model_by_id(self._session, research.model_id_answer)
        if model is None:
            logger.error(f"_step_plan_structure: answer model {research.model_id_answer} not found")
            self._has_error = True
            return ""

        page_summaries = await get_page_summaries_by_research(self._session, research.research_id)
        summaries: list[dict] = [{"url": ps.page_url, "summary": ps.page_summary} for ps in page_summaries]

        query: str = (research.research_body_start or {}).get("query", research.research_name)
        messages = build_plan_structure_messages(
            query=query,
            direction=direction or "",
            summaries=summaries,
        )

        llm = LLMClient(
            model_name=model.model_api_model,
            base_url=model.model_base_url,
            api_key=model.model_key_api,
        )

        status = ModelResponseStatus.COMPLETE
        structure = ""

        try:
            structure = await llm.generate(messages)
            output_payload: dict = {"structure": structure}
            logger.info(f"_step_plan_structure: done (research_id={research.research_id})")
        except Exception as exc:
            status = ModelResponseStatus.ERROR
            output_payload = {"error": str(exc)}
            self._has_error = True
            logger.exception(f"_step_plan_structure: failed (research_id={research.research_id}): {exc}")

        await create_model_output(
            session=self._session,
            model_id=research.model_id_answer,
            research_id=research.research_id,
            step_type="plan_structure",
            model_input={"messages": messages},
            model_output=output_payload,
            response_status=status,
        )

        return structure

    # ------------------------------------------------------------------
    # Step 7: iterative article writing by chapter
    # ------------------------------------------------------------------

    @pipeline_step(7, "WRITE")
    async def _step_write_article(self, direction: str, structure: str) -> None:
        """Writes the research article iteratively, one chapter at a time.

        Parses the structure into h2 chapters, then calls model_id_answer
        for each chapter sequentially, accumulating written content as context.
        Each chapter call is saved to model_outputs. The combined article is
        formatted as segments and saved to research_body_finish of epoch 0.

        Args:
            direction: Result of the direction_brainstorm step.
            structure: Markdown outline from the plan_structure step.
        """
        research = self._research
        if self._has_error:
            logger.debug(f"_step_write_article: skipping due to previous error (research_id={research.research_id})")
            return

        await update_research_stage(self._session, research, RESEARCH_STAGES["WRITE"])

        model = await get_model_by_id(self._session, research.model_id_answer)
        if model is None:
            logger.error(f"_step_write_article: answer model {research.model_id_answer} not found")
            self._has_error = True
            return

        page_summaries = await get_page_summaries_by_research(self._session, research.research_id)
        summaries: list[dict] = [{"url": ps.page_url, "summary": ps.page_summary} for ps in page_summaries]

        query: str = (research.research_body_start or {}).get("query", research.research_name)

        llm = LLMClient(
            model_name=model.model_api_model,
            base_url=model.model_base_url,
            api_key=model.model_key_api,
        )

        chapters = self._parse_chapters(structure)
        if not chapters:
            logger.warning(
                f"_step_write_article: no chapters parsed from structure, "
                f"falling back to full article write (research_id={research.research_id})"
            )
            chapters = [structure or query]

        written_so_far = ""
        all_text_parts: list[str] = []

        for i, chapter_block in enumerate(chapters):
            messages = build_write_chapter_messages(
                query=query,
                direction=direction or "",
                summaries=summaries,
                structure=structure or "",
                chapter=chapter_block,
                written_so_far=written_so_far[-WRITTEN_SO_FAR_MAX_CHARS:],
            )

            status = ModelResponseStatus.COMPLETE
            output_payload: dict = {}

            try:
                chapter_text = await llm.generate(messages)
                output_payload = {"chapter_index": i, "chapter_text": chapter_text}
                all_text_parts.append(chapter_text)
                written_so_far += "\n\n" + chapter_text
                logger.info(
                    f"_step_write_article: chapter {i + 1}/{len(chapters)} done "
                    f"(research_id={research.research_id})"
                )
            except Exception as exc:
                status = ModelResponseStatus.ERROR
                output_payload = {"chapter_index": i, "error": str(exc)}
                self._has_error = True
                logger.exception(
                    f"_step_write_article: chapter {i + 1}/{len(chapters)} failed "
                    f"(research_id={research.research_id}): {exc}"
                )

            await create_model_output(
                session=self._session,
                model_id=research.model_id_answer,
                research_id=research.research_id,
                step_type="write_chapter",
                model_input={"messages": messages},
                model_output=output_payload,
                response_status=status,
            )

        full_text = "\n\n".join(all_text_parts)
        segments = self._format_as_segments(full_text)

        combined_payload: dict = {"segments": segments} if segments else {"error": "no chapters written"}
        combined_status = ModelResponseStatus.COMPLETE if segments else ModelResponseStatus.ERROR
        await create_model_output(
            session=self._session,
            model_id=research.model_id_answer,
            research_id=research.research_id,
            step_type="write_article",
            model_input={"structure": structure, "chapters_count": len(chapters)},
            model_output=combined_payload,
            response_status=combined_status,
        )

        if segments:
            await update_research_body_finish(
                session=self._session,
                research=research,
                body_finish={"segments": segments},
            )
            logger.info(f"_step_write_article: done (research_id={research.research_id})")

    @staticmethod
    def _parse_chapters(structure: str) -> list[str]:
        """Splits a Markdown outline into h2-level chapter blocks.

        Each block contains the ## heading line and all following ### lines
        until the next ## heading. The top-level # heading is ignored.

        Args:
            structure: Markdown outline string produced by _step_plan_structure.

        Returns:
            List of chapter block strings (one per ## heading).
        """
        lines = structure.splitlines()
        chapters: list[str] = []
        current: list[str] = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("## "):
                if current:
                    chapters.append("\n".join(current))
                current = [line]
            elif stripped.startswith("# "):
                # top-level title — skip
                pass
            elif current:
                current.append(line)
        if current:
            chapters.append("\n".join(current))
        return chapters

    @staticmethod
    def _apply_inline_markdown(text: str) -> str:
        """Replaces inline Markdown markup with <b> and <i> HTML tags.

        Args:
            text: String with possible inline markup.

        Returns:
            String with <b> and <i> tags substituted.
        """
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
        text = re.sub(r"_(.+?)_", r"<i>\1</i>", text)
        return text

    @staticmethod
    def _format_as_segments(text: str) -> list[dict]:
        """Converts Markdown text into a list of typed content segments.

        Args:
            text: Markdown-formatted text from the LLM.

        Returns:
            List of dicts with keys: type, content, is_like, is_dislike, comment.
            Supported types: h1, h2, h3, p, li.
            Inline markup **bold** and *italic*/_italic_ is converted to <b>/<i>.
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
