from loguru import logger
from pydantic import BaseModel
from sqlalchemy import select

from app.crud.research import update_research_rerank_chunks, update_research_stage
from app.models.chunk_summary import ChunkSummary
from app.models.research import RESEARCH_STAGES

from .base import ScoringPagesStepBase


class _RerankScore(BaseModel):
    score: float


class RerankScoringStep(ScoringPagesStepBase):
    """Шаг фильтрации чанков по алгоритму Reranker (LLM-скоринг релевантности)."""

    async def execute(self) -> None:
        """Вычисляет rerank-оценки чанков и сохраняет топ-N в research_result_rerank_chunks.

        Для каждого чанка из research_result_embed_chunks проверяет кэш rerank_score
        в ChunkSummary. Если скора нет — просит reranker-модель оценить релевантность
        чанка к саммари исследования. Топ-N чанков записывает в Research.research_result_rerank_chunks.
        """
        research = self._research

        if not research.research_result_embed_chunks:
            logger.warning(f"{self._log_extra()} RerankScoringStep: no embed chunks found, skipping")
            return

        await update_research_stage(self._session, research, RESEARCH_STAGES["SCORING_RERANK"])

        llm = await self._get_llm(research.model_id_reranker)
        if llm is None:
            logger.warning(f"{self._log_extra()} RerankScoringStep: reranker model not found, skipping")
            return

        query: str = (research.research_body_start or {}).get("query", research.research_name)
        direction: str = research.research_direction_content or ""
        summary_text: str = f"{query} {direction}".strip()

        embed_chunks: list[dict] = research.research_result_embed_chunks
        chunk_ids = [c["chunk_id"] for c in embed_chunks]

        result = await self._session.execute(select(ChunkSummary).where(ChunkSummary.chunk_id.in_(chunk_ids)))
        chunks_by_id: dict[int, ChunkSummary] = {c.chunk_id: c for c in result.scalars().all()}

        scored: list[tuple[int, str, int, float]] = []
        for item in embed_chunks:
            chunk_id: int = item["chunk_id"]
            chunk = chunks_by_id.get(chunk_id)
            if chunk is None:
                logger.debug(f"{self._log_extra()} RerankScoringStep: chunk_id={chunk_id} not found, skipping")
                continue

            if chunk.rerank_score is not None:
                logger.debug(
                    f"{self._log_extra()} RerankScoringStep: chunk_id={chunk_id} already scored "
                    f"({chunk.rerank_score:.3f}), skipping"
                )
                scored.append((chunk.chunk_id, chunk.page_url, chunk.chunk_index, float(chunk.rerank_score)))
                continue

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
                    "content": (f"Research query: {summary_text}\n\nText chunk:\n{chunk.chunk_content}"),
                },
            ]
            try:
                rerank_result: _RerankScore = await llm.generate_structured(
                    context=context,
                    output_type=_RerankScore,
                    session=self._session,
                    model_id=research.model_id_reranker,
                    research_id=research.research_id,
                    step_type="rerank_chunk",
                )
                score = round(max(0.0, min(1.0, float(rerank_result.score))), 3)
                chunk.rerank_score = score
                scored.append((chunk.chunk_id, chunk.page_url, chunk.chunk_index, score))
                logger.debug(f"{self._log_extra()} RerankScoringStep: chunk_id={chunk_id} score={score:.3f}")
            except Exception as exc:
                logger.error(f"{self._log_extra()} RerankScoringStep: failed to score chunk_id={chunk_id}: {exc}")
                continue

        await self._session.commit()

        top_n: int = research.settings_n_top_rerank_chunks
        top_chunks = [
            {
                "chunk_id": chunk_id,
                "page_url": page_url,
                "chunk_index": chunk_index,
                "rerank_score": score,
            }
            for chunk_id, page_url, chunk_index, score in sorted(scored, key=lambda x: x[3], reverse=True)[:top_n]
        ]

        await update_research_rerank_chunks(self._session, research, top_chunks)
        logger.info(f"{self._log_extra()} RerankScoringStep: done (scored={len(scored)}, top={len(top_chunks)})")
