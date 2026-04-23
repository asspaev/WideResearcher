from loguru import logger
from rank_bm25 import BM25Okapi
from sqlalchemy import select

from app.crud.research import update_research_bm25_chunks, update_research_stage
from app.models.chunk_summary import ChunkSummary
from app.models.research import RESEARCH_STAGES

from .base import ScoringPagesStepBase


class BM25ScoringStep(ScoringPagesStepBase):
    """Шаг фильтрации чанков по алгоритму BM25."""

    async def execute(self) -> None:
        """Вычисляет BM25-оценки чанков и сохраняет топ-N в research_result_bm25_chunks.

        Строит корпус из контента всех чанков исследования, вычисляет BM25-скоры
        относительно запроса + направления, нормализует к [0, 1] и сохраняет
        результаты в ChunkSummary.bm25_score. Топ-N чанков записывает в
        Research.research_result_bm25_chunks.
        """
        research = self._research

        await update_research_stage(self._session, research, RESEARCH_STAGES["SCORING_BM25"])

        result = await self._session.execute(
            select(ChunkSummary).where(ChunkSummary.research_id == research.research_id)
        )
        chunks: list[ChunkSummary] = list(result.scalars().all())

        if not chunks:
            logger.warning(f"{self._log_extra()} BM25ScoringStep: no chunks found, skipping")
            return

        query: str = (research.research_body_start or {}).get("query", research.research_name)
        direction: str = research.research_direction_content or ""
        query_tokens: list[str] = f"{query} {direction}".lower().split()

        tokenized_corpus = [chunk.chunk_content.lower().split() for chunk in chunks]
        bm25 = BM25Okapi(tokenized_corpus)
        raw_scores = bm25.get_scores(query_tokens)

        max_score = float(max(raw_scores)) if max(raw_scores) > 0 else 1.0

        for chunk, raw in zip(chunks, raw_scores):
            chunk.bm25_score = round(float(raw) / max_score, 3)

        await self._session.commit()

        scored = sorted(
            [(chunk, chunk.bm25_score) for chunk in chunks],
            key=lambda x: x[1],
            reverse=True,
        )

        top_n: int = research.settings_n_top_bm25_chunks
        top_chunks = [
            {
                "chunk_id": chunk.chunk_id,
                "page_url": chunk.page_url,
                "chunk_index": chunk.chunk_index,
                "bm25_score": score,
            }
            for chunk, score in scored[:top_n]
        ]

        await update_research_bm25_chunks(self._session, research, top_chunks)
        logger.info(f"{self._log_extra()} BM25ScoringStep: done " f"(chunks={len(chunks)}, top={len(top_chunks)})")
