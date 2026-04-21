from loguru import logger
from rank_bm25 import BM25Okapi

from app.config import get_settings
from app.crud.page_summary import upsert_page_summary
from app.crud.research import update_research_stage
from app.crud.scrapped_page import get_scrapped_page
from app.models.research import RESEARCH_STAGES

from .base import SummarizeStepBase


class BM25SummarizeStep(SummarizeStepBase):
    """Шаг суммаризации с использованием алгоритма BM25."""

    async def execute(self) -> None:
        """Выполняет суммаризацию страниц через BM25 без вызова LLM.

        Для каждой страницы разбивает чистый текст на чанки, извлекает
        полезный контекст через BM25 (query = промпт + direction), затем
        вычисляет итоговую оценку релевантности вторым проходом BM25.

        Args:
            direction: Результат шага direction_brainstorm.
        """
        research = self._research

        # Проверяем наличие ссылок для суммаризации — если нет, пропускаем шаг
        if not research.research_result_search_links:
            logger.warning(f"{self._log_extra()} BM25SummarizeStep: no links found")
            return

        # Переключаем стадию и получаем LLM-клиент
        await update_research_stage(self._session, research, RESEARCH_STAGES["SUMMARIZE"])
        llm = await self._get_llm(research.model_id_answer)
        if llm is None:
            logger.error(f"{self._log_extra()} BM25SummarizeStep: answer model {research.model_id_answer} not found")
            self.has_error = True
            return

        direction: str = research.research_direction_content
        chunk_size: int = get_settings().app.bm25_chunk_size
        query: str = (research.research_body_start or {}).get("query", research.research_name)
        query_tokens: list[str] = f"{query} {direction}".lower().split()

        links: list[dict] = research.research_result_search_links or []

        for link in links:
            url: str = link["url"]
            page = await get_scrapped_page(self._session, url)
            if page is None or not page.page_clean_content:
                logger.debug(f"{self._log_extra()} BM25SummarizeStep: no content for {url!r}, skipping")
                continue

            content: str = page.page_clean_content
            chunks: list[str] = [content[i : i + chunk_size] for i in range(0, len(content), chunk_size)]

            # Первый проход BM25: извлекаем полезный контекст из чанков
            tokenized_chunks = [chunk.lower().split() for chunk in chunks]
            bm25_first = BM25Okapi(tokenized_chunks)
            first_scores = bm25_first.get_scores(query_tokens)

            sorted_indices = first_scores.argsort()[::-1]
            useful_chunks = [chunks[i] for i in sorted_indices if first_scores[i] > 0]
            if not useful_chunks:
                useful_chunks = [chunks[int(sorted_indices[0])]]

            useful_context: str = "\n\n".join(useful_chunks)

            # Второй проход BM25: вычисляем итоговую оценку релевантности [0, 1]
            context_sub_chunks = [useful_context[i : i + chunk_size] for i in range(0, len(useful_context), chunk_size)]
            tokenized_context = [c.lower().split() for c in context_sub_chunks]
            bm25_second = BM25Okapi(tokenized_context)
            second_scores = bm25_second.get_scores(query_tokens)

            avg_score = float(second_scores.mean()) if len(second_scores) > 0 else 0.0
            relevance_score = round(max(0.0, min(1.0, avg_score / (1.0 + avg_score))), 3)

            try:
                await upsert_page_summary(
                    session=self._session,
                    page_url=url,
                    research_id=research.research_id,
                    page_summary=useful_context,
                    relevance_score=relevance_score,
                )
                logger.debug(
                    f"{self._log_extra()} BM25SummarizeStep: processed {url!r} "
                    f"(chunks={len(chunks)}, useful={len(useful_chunks)}, score={relevance_score:.3f})"
                )
            except Exception as exc:
                logger.error(f"{self._log_extra()} BM25SummarizeStep: failed for {url!r}: {exc}")

        logger.info(f"{self._log_extra()} BM25SummarizeStep: done")
