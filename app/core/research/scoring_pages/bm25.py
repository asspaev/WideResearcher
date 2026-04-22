from loguru import logger
from rank_bm25 import BM25Okapi

from app.crud.page_summary import upsert_page_bm25_score
from app.crud.research import update_research_bm25_links, update_research_stage
from app.crud.scrapped_page import get_scrapped_page
from app.models.research import RESEARCH_STAGES

from .base import ScoringPagesStepBase


class BM25ScoringStep(ScoringPagesStepBase):
    """Шаг фильтрации страниц по алгоритму BM25."""

    async def execute(self) -> None:
        """Вычисляет BM25-оценки страниц и сохраняет топ-N в research_result_bm25_links.

        Строит корпус из очищенного контента всех страниц, вычисляет BM25-скоры
        относительно запроса + направления, нормализует к [0, 1] и сохраняет
        результаты в PageSummary.bm25_score. Топ-N URL записывает в
        Research.research_result_bm25_links.
        """
        research = self._research

        if not research.research_result_search_links:
            logger.warning(f"{self._log_extra()} BM25ScoringStep: no links found, skipping")
            return

        await update_research_stage(self._session, research, RESEARCH_STAGES["SCORING_BM25"])

        query: str = (research.research_body_start or {}).get("query", research.research_name)
        direction: str = research.research_direction_content or ""
        query_tokens: list[str] = f"{query} {direction}".lower().split()

        links: list[dict] = research.research_result_search_links

        # Собираем контент всех страниц
        pages: list[tuple[str, str]] = []
        for link in links:
            url: str = link["url"]
            page = await get_scrapped_page(self._session, url)
            if page is None or not page.page_clean_content:
                logger.debug(f"{self._log_extra()} BM25ScoringStep: no content for {url!r}, skipping")
                continue
            pages.append((url, page.page_clean_content))

        if not pages:
            logger.warning(f"{self._log_extra()} BM25ScoringStep: no pages with content, skipping")
            return

        # Строим корпус и вычисляем BM25-скоры
        tokenized_corpus = [content.lower().split() for _, content in pages]
        bm25 = BM25Okapi(tokenized_corpus)
        raw_scores = bm25.get_scores(query_tokens)

        max_score = float(max(raw_scores)) if max(raw_scores) > 0 else 1.0

        # Сохраняем нормализованные скоры в PageSummary
        scored: list[tuple[str, float]] = []
        for (url, _), raw in zip(pages, raw_scores):
            score = round(float(raw) / max_score, 3)
            try:
                await upsert_page_bm25_score(
                    session=self._session,
                    page_url=url,
                    research_id=research.research_id,
                    bm25_score=score,
                )
                scored.append((url, score))
                logger.debug(f"{self._log_extra()} BM25ScoringStep: scored {url!r} = {score:.3f}")
            except Exception as exc:
                logger.error(f"{self._log_extra()} BM25ScoringStep: failed for {url!r}: {exc}")

        # Топ-N по убыванию скора
        top_n: int = research.settings_n_bm25_pages
        top_urls = sorted(scored, key=lambda x: x[1], reverse=True)[:top_n]
        bm25_links = [{"url": url, "bm25_score": score} for url, score in top_urls]

        await update_research_bm25_links(self._session, research, bm25_links)
        logger.info(f"{self._log_extra()} BM25ScoringStep: done " f"(scored={len(scored)}, top={len(bm25_links)})")
