from loguru import logger
from sqlalchemy import select

from app.crud.research import update_research_stage
from app.models.chunk_summary import ChunkSummary
from app.models.research import RESEARCH_STAGES
from app.services.llm_client import LLMGenerationError

from .base import ResearchStepBase


class SummarizeResearchStep(ResearchStepBase):
    """Шаг суммаризации чанков в виде bullet-points через LLM."""

    def _pick_chunks(self) -> list[dict] | None:
        """Выбирает чанки для суммаризации по приоритету: rerank → embed → bm25.

        Returns:
            Список словарей с chunk_id или None если нет подходящих чанков.
        """
        research = self._research
        if research.research_result_rerank_chunks:
            return research.research_result_rerank_chunks
        n = research.settings_n_top_chunks
        if research.research_result_embed_chunks:
            return research.research_result_embed_chunks[:n]
        if research.research_result_bm25_chunks:
            return research.research_result_bm25_chunks[:n]
        return None

    async def execute(self) -> None:
        """Генерирует bullet-summary для каждого чанка и сохраняет в ChunkSummary.page_summary.

        Для каждого выбранного чанка проверяет кэш page_summary в ChunkSummary.
        Если summary ещё нет — параллельно запрашивает LLM (model_id_answer) с
        конкурентностью ``model.model_n_async`` и ждёт завершения всех запросов
        перед выходом из шага.
        """
        research = self._research

        chunks = self._pick_chunks()
        if not chunks:
            logger.warning(f"{self._log_extra()} SummarizeResearchStep: no chunks found, skipping")
            return

        await update_research_stage(self._session, research, RESEARCH_STAGES["SUMMARIZE"])

        llm = await self._get_llm(research.model_id_answer)
        if llm is None:
            logger.error(
                f"{self._log_extra()} SummarizeResearchStep: answer model {research.model_id_answer} not found"
            )
            self.has_error = True
            return

        query: str = (research.research_body_start or {}).get("query", research.research_name)
        direction: str = research.research_direction_content or ""

        chunk_ids = [c["chunk_id"] for c in chunks]
        result = await self._session.execute(select(ChunkSummary).where(ChunkSummary.chunk_id.in_(chunk_ids)))
        chunks_by_id: dict[int, ChunkSummary] = {c.chunk_id: c for c in result.scalars().all()}

        pending: list[ChunkSummary] = []
        contexts: list[list[dict]] = []
        skipped = 0
        for item in chunks:
            chunk_id: int = item["chunk_id"]
            chunk = chunks_by_id.get(chunk_id)
            if chunk is None:
                logger.debug(f"{self._log_extra()} SummarizeResearchStep: chunk_id={chunk_id} not found, skipping")
                continue

            if chunk.page_summary:
                logger.debug(
                    f"{self._log_extra()} SummarizeResearchStep: chunk_id={chunk_id} already summarized, skipping"
                )
                skipped += 1
                continue

            context = [
                {
                    "role": "system",
                    "content": (
                        "You are a research assistant. "
                        "Given a text chunk, extract the most relevant key facts and insights "
                        "as concise bullet points (markdown list with '-'). "
                        "Focus only on information relevant to the research query. "
                        "Be factual and specific. Do not include irrelevant details."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Research query: {query}\n"
                        f"Research direction: {direction}\n\n"
                        f"Text chunk:\n{chunk.chunk_content}\n\n"
                        "Extract key information as bullet points:"
                    ),
                },
            ]
            pending.append(chunk)
            contexts.append(context)

        if not pending:
            logger.info(
                f"{self._log_extra()} SummarizeResearchStep: nothing to summarize "
                f"(total={len(chunks)}, cached={skipped})"
            )
            return

        results = await llm.generate_many(
            contexts=contexts,
            model_id=research.model_id_answer,
            research_id=research.research_id,
            step_type="summarize_bullet",
        )

        done = 0
        for chunk, summary in zip(pending, results):
            if isinstance(summary, LLMGenerationError):
                logger.error(
                    f"{self._log_extra()} SummarizeResearchStep: failed to summarize "
                    f"chunk_id={chunk.chunk_id}: {summary}"
                )
                continue
            chunk.page_summary = summary
            done += 1
            logger.debug(f"{self._log_extra()} SummarizeResearchStep: chunk_id={chunk.chunk_id} summarized")

        await self._session.commit()
        logger.info(
            f"{self._log_extra()} SummarizeResearchStep: done "
            f"(total={len(chunks)}, summarized={done}, cached={skipped})"
        )
