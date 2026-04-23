from loguru import logger
from pydantic import BaseModel

from app.crud.page_summary import get_page_summary, upsert_page_rerank_score
from app.crud.research import update_research_rerank_links, update_research_stage
from app.crud.scrapped_page import get_scrapped_page
from app.models.research import RESEARCH_STAGES

from .base import ScoringPagesStepBase
from .chunks import chunk_text


class _RerankScore(BaseModel):
    score: float


class RerankScoringStep(ScoringPagesStepBase):
    """Шаг фильтрации страниц по алгоритму Reranker (LLM-скоринг релевантности)."""

    async def execute(self) -> None:
        """Вычисляет rerank-оценки страниц и сохраняет топ-N в research_result_rerank_links.

        Для каждой страницы из research_result_embed_links разбивает контент на чанки
        и просит reranker-модель оценить релевантность каждого чанка к запросу исследования.
        Лучший скор сохраняется в PageSummary.rerank_score.
        Топ-N URL записывает в Research.research_result_rerank_links.
        """
        research = self._research

        if not research.research_result_embed_links:
            logger.warning(f"{self._log_extra()} RerankScoringStep: no embed links found, skipping")
            return

        await update_research_stage(self._session, research, RESEARCH_STAGES["SCORING_RERANK"])

        llm = await self._get_llm(research.model_id_reranker)
        if llm is None:
            logger.warning(f"{self._log_extra()} RerankScoringStep: reranker model not found, skipping")
            return

        query: str = (research.research_body_start or {}).get("query", research.research_name)
        direction: str = research.research_direction_content or ""
        summary_text: str = f"{query} {direction}".strip()

        links: list[dict] = research.research_result_embed_links

        scored: list[tuple[str, float]] = []
        for link in links:
            url: str = link["url"]
            page = await get_scrapped_page(self._session, url)
            if page is None or not page.page_clean_content:
                logger.debug(f"{self._log_extra()} RerankScoringStep: no content for {url!r}, skipping")
                continue

            existing = await get_page_summary(self._session, url, research.research_id)
            if existing is not None and existing.rerank_score is not None:
                logger.debug(
                    f"{self._log_extra()} RerankScoringStep: {url!r} already scored ({existing.rerank_score:.3f}), skipping"
                )
                scored.append((url, existing.rerank_score))
                continue

            chunks = chunk_text(page.page_clean_content)
            best_score = 0.0

            for chunk_idx, chunk in enumerate(chunks):
                context = [
                    {
                        "role": "system",
                        "content": (
                            "You are a relevance scoring expert. "
                            "Given a research query and a text chunk, rate how relevant the chunk is to the query. "
                            "Return a score from 0.0 (not relevant) to 1.0 (highly relevant)."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (f"Research query: {summary_text}\n\n" f"Text chunk:\n{chunk}"),
                    },
                ]
                try:
                    result: _RerankScore = await llm.generate_structured(
                        context=context,
                        output_type=_RerankScore,
                        session=self._session,
                        model_id=research.model_id_reranker,
                        research_id=research.research_id,
                        step_type="rerank_chunk",
                    )
                    chunk_score = round(max(0.0, min(1.0, float(result.score))), 3)
                    if chunk_score > best_score:
                        best_score = chunk_score
                except Exception as exc:
                    logger.error(
                        f"{self._log_extra()} RerankScoringStep: failed to score chunk {chunk_idx} "
                        f"of {url!r}: {exc}"
                    )
                    continue

            try:
                await upsert_page_rerank_score(
                    session=self._session,
                    page_url=url,
                    research_id=research.research_id,
                    rerank_score=best_score,
                )
                scored.append((url, best_score))
                logger.debug(f"{self._log_extra()} RerankScoringStep: scored {url!r} = {best_score:.3f}")
            except Exception as exc:
                logger.error(f"{self._log_extra()} RerankScoringStep: failed to save score for {url!r}: {exc}")

        top_n: int = research.settings_n_rerank_pages
        top_urls = sorted(scored, key=lambda x: x[1], reverse=True)[:top_n]
        rerank_links = [{"url": url, "rerank_score": score} for url, score in top_urls]

        await update_research_rerank_links(self._session, research, rerank_links)
        logger.info(f"{self._log_extra()} RerankScoringStep: done (scored={len(scored)}, top={len(rerank_links)})")
